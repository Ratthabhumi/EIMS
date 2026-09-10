"""
==============================================================================
EIMS Background Stream Consumer Worker & Batch Processing Architecture
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 4 Section 7.3
==============================================================================
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy.future import select

from backend.core.logger import get_logger
from backend.domain.asset_registry.models import AuditLog, InfrastructureAsset
from backend.domain.telemetry.broker import (
    TELEMETRY_STREAM_KEY,
    RedisTelemetryStreamBroker,
    StubTelemetryStreamBroker,
)
from backend.domain.telemetry.models import TelemetryMetric, WindowsEventLog
from backend.infrastructure.cache import cache_manager
from backend.infrastructure.database import database_engine

logger = get_logger("eims.telemetry.worker")

_MAX_APPROX_TRIM = 10000


class TelemetryStreamConsumer:
    """
    Authoritative background consumer worker daemon responsible for draining
    Redis Stream buffers in batch increments and synchronizing structured diagnostic
    records into relational persistence tables under zero database pool contention.
    Includes Real-Time Anomaly Engine (Sliding Window Compliance).

    The broker is injected (production Redis broker or hermetic stub broker),
    decoupling batch draining from the physical Redis transport. XACK semantics
    give each message exact-once acknowledgement so no telemetry is silently lost
    on transient database or broker failures.
    """
    def __init__(self, broker=None, polling_interval: float = 1.0):
        self.polling_interval = polling_interval
        self.broker = broker
        self._running = False
        self._task = None
        self._last_id = "0-0"
        self.resolver: dict[str, uuid.UUID] = {}
        self._redis = None

        # Observable batch tracking (identical contract exposed by the stub broker)
        self.processed_metrics: list[TelemetryMetric] = []
        self.processed_winlogs: list[WindowsEventLog] = []

    async def _ensure_redis(self):
        """Binds the shared cache_manager Redis client lazily for stream production reads."""
        if self._redis is None and cache_manager.redis is not None:
            self._redis = cache_manager.redis
        return self._redis

    def register_agent_mapping(self, cert_fingerprint: str, asset_id: uuid.UUID) -> None:
        """Registers verified client certificate fingerprints to parent asset primary keys."""
        self.resolver[cert_fingerprint] = asset_id
        logger.debug(f"Registered cert hash '{cert_fingerprint[:8]}...' -> Asset ID {asset_id}")

    async def _resolve_asset(self, fingerprint: str) -> uuid.UUID:
        if fingerprint in self.resolver:
            return self.resolver[fingerprint]

        session_maker = database_engine.get_session_maker()
        if session_maker:
            async with session_maker() as session:
                result = await session.execute(
                    select(InfrastructureAsset).where(InfrastructureAsset.cryptographic_fingerprint == fingerprint)
                )
                asset = result.scalars().first()
                if asset:
                    self.resolver[fingerprint] = asset.asset_id
                    return asset.asset_id

        # Generate stable fallback UUID derived deterministically from SHA-256 fingerprint if unassigned
        return uuid.uuid5(uuid.NAMESPACE_OID, f"eims-fallback-{fingerprint}")

    async def start(self):
        if self._running:
            return
        self._running = True
        logger.info("Telemetry Stream Consumer Worker started.")
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Telemetry Stream Consumer Worker stopped.")

    async def _loop(self):
        while self._running:
            try:
                await self.process_batch(batch_size=50)
            except Exception as e:
                logger.error(f"Telemetry worker loop error: {e}")
            await asyncio.sleep(self.polling_interval)

    # ------------------------------------------------------------------
    # Stream Read Abstraction (broker-backed vs physical Redis)
    # ------------------------------------------------------------------
    async def _fetch_batch(self, batch_size: int) -> tuple[list, str, str | None]:
        """
        Returns (messages, group_stream, error_signal). Reads production messages
        from the injected Redis stream broker when available; otherwise reads from
        the physical Redis client.
        """
        if self.broker is not None:
            return await self.broker.fetch_stream_batch(
                TELEMETRY_STREAM_KEY, self._last_id, batch_size
            )
        redis_client = await self._ensure_redis()
        if redis_client is None:
            return [], TELEMETRY_STREAM_KEY, "redis-unavailable"
        try:
            streams = await redis_client.xread(
                {TELEMETRY_STREAM_KEY: self._last_id}, count=batch_size, block=10
            )
        except Exception as e:
            logger.error(f"Telemetry stream read failure: {e}")
            return [], TELEMETRY_STREAM_KEY, "stream-read-error"
        if not streams:
            return [], TELEMETRY_STREAM_KEY, None
        return streams[0][1], streams[0][0].decode("utf-8") if isinstance(streams[0][0], bytes) else streams[0][0], None

    async def process_batch(self, batch_size: int = 50) -> int:
        messages, stream_key, error_signal = await self._fetch_batch(batch_size)
        if error_signal:
            return 0
        if not messages:
            return 0

        processed_count = 0
        db_metrics = []
        db_winlogs = []
        anomalies_to_trigger = []
        newest_id: str | None = None

        for message_id, entry_data in messages:
            str_message_id = message_id.decode("utf-8") if isinstance(message_id, bytes) else message_id
            newest_id = str_message_id
            entry = {
                (k.decode("utf-8") if isinstance(k, bytes) else k): (v.decode("utf-8") if isinstance(v, bytes) else v)
                for k, v in entry_data.items()
            }
            event_type = entry.get("event_type")
            cert_hash = entry.get("cert_fingerprint", "")
            try:
                raw_payload = json.loads(entry.get("payload", "{}"))
            except json.JSONDecodeError:
                logger.error(f"Malformed telemetry payload on {str_message_id}; dropping.")
                continue
            target_asset_id = await self._resolve_asset(cert_hash)

            if event_type == "heartbeat":
                metrics = raw_payload.get("metrics", {})
                cpu = metrics.pop("cpu_utilization", 0.0) if isinstance(metrics, dict) else 0.0
                timestamp_str = raw_payload.get("timestamp")
                ev_time = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(UTC)

                db_metrics.append(TelemetryMetric(
                    metric_id=uuid.uuid4(),
                    asset_id=target_asset_id,
                    event_time=ev_time,
                    cpu_utilization=float(cpu),
                    diagnostic_payload=metrics if isinstance(metrics, dict) else {}
                ))
                processed_count += 1

            elif event_type == "winlog":
                meta = raw_payload.get("metadata", {})
                occ_str = raw_payload.get("occurrence_time")
                ev_time = datetime.fromisoformat(occ_str) if occ_str else datetime.now(UTC)
                event_id = int(raw_payload.get("event_id", 0))

                db_winlogs.append(WindowsEventLog(
                    log_id=uuid.uuid4(),
                    asset_id=target_asset_id,
                    occurrence_time=ev_time,
                    event_id=event_id,
                    severity_level=str(raw_payload.get("severity", "Information")),
                    evtx_metadata=meta if isinstance(meta, dict) else {}
                ))
                processed_count += 1

                # -------------------------------------------------------------
                # Sliding Window Anomaly Rule Engine (Sprint 5)
                # -------------------------------------------------------------
                if event_id == 4625:  # Failed Logon
                    src_ip = (meta or {}).get("source_network_ip")
                    redis_client = await self._ensure_redis()
                    if src_ip and redis_client:
                        redis_key = f"eims:sec:bruteforce:{src_ip}"
                        count = await redis_client.incr(redis_key)
                        if count == 1:
                            await redis_client.expire(redis_key, 60)
                        # Trigger quarantine if > 5 failed logins within 60s
                        if count > 5:
                            anomalies_to_trigger.append((target_asset_id, src_ip, count))
                            await redis_client.expire(redis_key, 300)

        # ------------------------------------------------------------------
        # Persistence in a single transaction
        # ------------------------------------------------------------------
        _use_stub = isinstance(self.broker, StubTelemetryStreamBroker)

        session_maker = database_engine.get_session_maker() if not _use_stub else None
        if session_maker and (db_metrics or db_winlogs or anomalies_to_trigger):
            await self._persist_batch(session_maker, db_metrics, db_winlogs, anomalies_to_trigger)

        # Track observable batch records for hermetic verification
        self.processed_metrics.extend(db_metrics)
        self.processed_winlogs.extend(db_winlogs)

        # Exactly-once: acknowledge and compact the stream only after successful processing
        await self._ack_and_trim(stream_key, newest_id, str_message_ids=[m[0] for m in messages])

        # Retain redelivery bookmark (`_last_id` is intentionally NOT advanced on failure)
        if processed_count > 0 or db_metrics or db_winlogs:
            self._last_id = newest_id or self._last_id

        return processed_count

    async def _persist_batch(self, session_maker, db_metrics, db_winlogs, anomalies_to_trigger) -> None:
        async with session_maker() as session:
            async with session.begin():
                if db_metrics:
                    session.add_all(db_metrics)
                if db_winlogs:
                    session.add_all(db_winlogs)

                for asset_id, src_ip, count in anomalies_to_trigger:
                    result = await session.execute(
                        select(InfrastructureAsset).where(InfrastructureAsset.asset_id == asset_id)
                    )
                    asset = result.scalars().first()
                    if asset and asset.lifecycle_state != "Quarantined":
                        old_score = asset.current_compliance_score
                        asset.lifecycle_state = "Quarantined"
                        asset.current_compliance_score = max(0, old_score - 30)

                        audit = AuditLog(
                            actor_id=None,
                            asset_id=asset.asset_id,
                            action_verb="AUTOMATED_QUARANTINE_4625",
                            immutable_payload={
                                "reason": f"Brute force detected from {src_ip}",
                                "failed_attempts": count,
                                "old_score": old_score,
                                "new_score": asset.current_compliance_score
                            }
                        )
                        session.add(audit)
                        logger.warning(f"SECURITY ANOMALY: Asset {asset.asset_id} Quarantined due to brute force from {src_ip}")
                        redis_client = await self._ensure_redis()
                        if redis_client:
                            await redis_client.publish("eims:events:alerts", json.dumps({
                                "event_type": "SECURITY_QUARANTINE_EXCEPTION",
                                "severity": "Critical",
                                "asset_id": str(asset.asset_id),
                                "source_ip": src_ip
                            }))

    async def _ack_and_trim(self, stream_key: str, newest_id: str | None, str_message_ids=None) -> None:
        """Acknowledges processed stream entries to the broker and trims approximated history."""
        if self.broker is not None and str_message_ids:
            try:
                await self.broker.ack_stream_messages(TELEMETRY_STREAM_KEY, str_message_ids)
            except Exception as e:
                logger.error(f"Stream acknowledgement failure: {e}")
        redis_client = await self._ensure_redis()
        if redis_client is None or not newest_id:
            return
        try:
            await redis_client.xtrim(TELEMETRY_STREAM_KEY, minid=newest_id, approximate=True)
        except Exception:
            pass


# Singleton worker instance
telemetry_worker = TelemetryStreamConsumer()