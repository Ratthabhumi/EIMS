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
from backend.domain.telemetry.broker import TELEMETRY_STREAM_KEY
from backend.domain.telemetry.models import TelemetryMetric, WindowsEventLog
from backend.infrastructure.cache import cache_manager
from backend.infrastructure.database import database_engine

logger = get_logger("eims.telemetry.worker")

class TelemetryStreamConsumer:
    """
    Authoritative background consumer worker daemon responsible for draining
    Redis Stream buffers in batch increments and synchronizing structured diagnostic
    records into relational persistence tables under zero database pool contention.
    Includes Real-Time Anomaly Engine (Sliding Window Compliance).
    """
    def __init__(self, polling_interval: float = 1.0):
        self.polling_interval = polling_interval
        self._running = False
        self._task = None
        self._last_id = "0-0"
        self.resolver: dict[str, uuid.UUID] = {}

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

    async def process_batch(self, batch_size: int = 50) -> int:
        if not cache_manager.redis:
            return 0

        # Read from Redis Stream (eims:telemetry:ingestion)
        try:
            streams = await cache_manager.redis.xread({TELEMETRY_STREAM_KEY: self._last_id}, count=batch_size, block=10)
        except Exception:
            return 0

        if not streams:
            return 0

        processed_count = 0
        db_metrics = []
        db_winlogs = []
        anomalies_to_trigger = []

        stream_key, messages = streams[0]
        
        for message_id, entry_data in messages:
            self._last_id = message_id.decode('utf-8') if isinstance(message_id, bytes) else message_id
            
            entry = {k.decode('utf-8') if isinstance(k, bytes) else k: v.decode('utf-8') if isinstance(v, bytes) else v for k, v in entry_data.items()}
            event_type = entry.get("event_type")
            cert_hash = entry.get("cert_fingerprint", "")
            raw_payload = json.loads(entry.get("payload", "{}"))
            target_asset_id = await self._resolve_asset(cert_hash)

            if event_type == "heartbeat":
                metrics = raw_payload.get("metrics", {})
                cpu = metrics.pop("cpu_utilization", 0.0)
                timestamp_str = raw_payload.get("timestamp")
                ev_time = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(UTC)
                
                db_metrics.append(TelemetryMetric(
                    metric_id=uuid.uuid4(),
                    asset_id=target_asset_id,
                    event_time=ev_time,
                    cpu_utilization=float(cpu),
                    diagnostic_payload=metrics
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
                    evtx_metadata=meta
                ))
                processed_count += 1

                # -------------------------------------------------------------
                # Sliding Window Anomaly Rule Engine (Sprint 5)
                # -------------------------------------------------------------
                if event_id == 4625:  # Failed Logon
                    src_ip = meta.get("source_network_ip")
                    if src_ip:
                        redis_key = f"eims:sec:bruteforce:{src_ip}"
                        count = await cache_manager.redis.incr(redis_key)
                        if count == 1:
                            await cache_manager.redis.expire(redis_key, 60)
                        
                        # Trigger quarantine if > 5 failed logins within 60s
                        if count > 5:
                            anomalies_to_trigger.append((target_asset_id, src_ip, count))
                            # Prevent multiple triggers in same minute
                            await cache_manager.redis.expire(redis_key, 300) 

        # Database Insertion and Anomaly State Transition 
        if db_metrics or db_winlogs or anomalies_to_trigger:
            session_maker = database_engine.get_session_maker()
            if session_maker:
                async with session_maker() as session:
                    async with session.begin():
                        if db_metrics:
                            session.add_all(db_metrics)
                        if db_winlogs:
                            session.add_all(db_winlogs)
                        
                        # Apply Quarantines transactionally
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
                                
                                # Emulate Redis PubSub Notification (SAD 6.3)
                                await cache_manager.redis.publish("eims:events:alerts", json.dumps({
                                    "event_type": "SECURITY_QUARANTINE_EXCEPTION",
                                    "severity": "Critical",
                                    "asset_id": str(asset.asset_id),
                                    "source_ip": src_ip
                                }))

            # Truncate stream up to last processed ID to save Redis memory
            try:
                await cache_manager.redis.xtrim(TELEMETRY_STREAM_KEY, minid=self._last_id, approximate=True)
            except Exception:
                pass
                
        return processed_count

# Singleton worker instance
telemetry_worker = TelemetryStreamConsumer()
