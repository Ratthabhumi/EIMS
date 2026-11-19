"""Durable Redis consumer-group worker for telemetry persistence."""
import asyncio
import ipaddress
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.exceptions import RedisError
from sqlalchemy import func, literal_column, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.future import select

from backend.core.logger import get_logger
from backend.domain.asset_registry.models import AuditLog, InfrastructureAsset
from backend.domain.telemetry.broker import (
    TELEMETRY_STREAM_KEY, RedisTelemetryStreamBroker, StubTelemetryStreamBroker, is_nogroup_error,
)
from backend.domain.incident_ingest.outbox import (
    enqueue_incident_ingest,
    nudge_dispatch,
    winlog_items_from_returned,
)
from backend.domain.telemetry.models import TelemetryAlertOutbox, TelemetryMetric, WindowsEventLog
from backend.domain.telemetry.schemas import AgentHeartbeatRequest, AgentWinlogRequest
from backend.infrastructure.cache import cache_manager
from backend.infrastructure.database import database_engine

logger = get_logger("eims.telemetry.worker")

UNRESOLVED_ASSET_REASON = "unresolved-asset-reference"
ROW_REJECTED_REASON = "row-rejected-by-database"
BRUTE_FORCE_EVENT_ID = 4625
BRUTE_FORCE_THRESHOLD = 5
BRUTE_FORCE_WINDOW = timedelta(seconds=60)
ALERT_CHANNEL = "eims:events:alerts"
ALERT_STREAM_KEY = "eims:events:alerts:stream"  # durable; entries carry alert_id for consumer dedupe
OUTBOX_DISPATCH_BATCH = 100


def _is_countable_source_ip(value) -> bool:
    """True only for a well-formed, routable-looking source IP (no '-', loopback, unspecified, etc.).

    The exact stored string is used as the grouping/count key, so no normalisation is applied.
    """
    if not isinstance(value, str) or not value:
        return False
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    for candidate in (ip, getattr(ip, "ipv4_mapped", None)):
        if candidate is not None and (candidate.is_loopback or candidate.is_unspecified
                                      or candidate.is_multicast or candidate.is_reserved):
            return False
    return True


class UnresolvedAssetError(Exception):
    """Fingerprint does not map to a registered infrastructure asset."""


class DatabaseUnavailableError(RuntimeError):
    """Retryable infrastructure error: no DB session factory, so identity cannot be decided."""


@dataclass
class _Record:
    message_id: str
    entry: dict
    event_type: str
    row: object  # TelemetryMetric | WindowsEventLog (transient, not yet persisted)


class TelemetryStreamConsumer:
    """At-least-once consumer; SQL idempotency makes crash/restart replay safe."""
    def __init__(self, broker=None, polling_interval: float = 1.0):
        self.polling_interval = polling_interval
        self.broker = broker or RedisTelemetryStreamBroker(cache_manager)
        self._running = False
        self._task = None
        self._last_id = "0-0"  # Observability only; Redis consumer groups own delivery state.
        self.resolver: dict[str, uuid.UUID] = {}
        self._redis = None
        self.processed_metrics: list[TelemetryMetric] = []
        self.processed_winlogs: list[WindowsEventLog] = []

    async def _ensure_redis(self):
        if self._redis is None and cache_manager.redis is not None:
            self._redis = cache_manager.redis
        return self._redis

    def register_agent_mapping(self, cert_fingerprint: str, asset_id: uuid.UUID) -> None:
        self.resolver[cert_fingerprint] = asset_id
        logger.debug("Registered verified agent fingerprint %s...", cert_fingerprint[:8])

    async def _resolve_asset(self, fingerprint: str) -> uuid.UUID:
        """Resolve a registered asset or raise UnresolvedAssetError (never fabricate an ID).

        Database errors propagate so the batch stays pending and is retried.
        """
        if fingerprint in self.resolver:
            return self.resolver[fingerprint]
        session_maker = database_engine.get_session_maker()
        if session_maker is None and not isinstance(self.broker, StubTelemetryStreamBroker):
            # Absence of the DB is not evidence the asset is unknown: never DLQ/ACK on it.
            raise DatabaseUnavailableError("Database session unavailable; asset lookup not performed")
        if session_maker:
            async with session_maker() as session:
                result = await session.execute(
                    select(InfrastructureAsset).where(InfrastructureAsset.cryptographic_fingerprint == fingerprint)
                )
                asset = result.scalars().first()
                if asset:
                    self.resolver[fingerprint] = asset.asset_id
                    return asset.asset_id
        raise UnresolvedAssetError(UNRESOLVED_ASSET_REASON)

    async def start(self):
        if self._running:
            return
        self._running = True
        logger.info("Telemetry consumer-group worker started")
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=0.5)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                pass
        logger.info("Telemetry consumer-group worker stopped")

    async def _loop(self):
        while self._running:
            try:
                await self.process_batch(batch_size=50)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Telemetry batch failed; pending entries retained for retry (%s)", type(exc).__name__)
            try:
                await asyncio.sleep(self.polling_interval)
            except asyncio.CancelledError:
                break

    async def _fetch_batch(self, batch_size: int) -> tuple[list, str, str | None]:
        return await self.broker.fetch_stream_batch(TELEMETRY_STREAM_KEY, self._last_id, batch_size)

    @staticmethod
    def _decode_queue_value(value) -> tuple[str, bool]:
        if not isinstance(value, bytes):
            return str(value), True
        try:
            return value.decode("utf-8"), True
        except UnicodeDecodeError:
            import base64
            return "base64:" + base64.b64encode(value).decode("ascii"), False

    @classmethod
    def _normalise_entry_checked(cls, entry_data: dict) -> tuple[dict[str, str], list[str]]:
        entry: dict[str, str] = {}
        undecodable: list[str] = []
        for key, value in entry_data.items():
            name, key_ok = cls._decode_queue_value(key)
            decoded, value_ok = cls._decode_queue_value(value)
            entry[name] = decoded
            if not (key_ok and value_ok):
                undecodable.append(name)
        return entry, undecodable

    @classmethod
    def _normalise_entry(cls, entry_data: dict) -> dict[str, str]:
        return cls._normalise_entry_checked(entry_data)[0]

    @staticmethod
    def _dead_letter_reason(event_type: str, error: Exception) -> str:
        return f"invalid-{event_type or 'unknown'}-event:{type(error).__name__}"

    def _outbox_session_maker(self):
        if isinstance(self.broker, StubTelemetryStreamBroker):
            return None
        return database_engine.get_session_maker()

    async def _refresh_claim_loop(self, stream_key: str, message_ids: list[str]) -> None:
        """Keep a claimed Redis batch leased while parsing/persistence is still in progress.

        XCLAIM JUSTID resets idle time without incrementing the delivery counter. Infrastructure
        failures are logged and leave the entries pending; a later consumer can reclaim them.
        """
        if not isinstance(self.broker, RedisTelemetryStreamBroker):
            return
        client = self.broker._cache._redis_client
        refresh = getattr(client, "xclaim", None) if client is not None else None
        if refresh is None:
            return
        interval = max(0.1, self.broker.reclaim_idle_ms / 3000)
        while True:
            await asyncio.sleep(interval)
            try:
                await refresh(
                    name=stream_key,
                    groupname=self.broker.group_name,
                    consumername=self.broker.consumer_name,
                    min_idle_time=0,
                    message_ids=message_ids,
                    idle=0,
                    justid=True,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Telemetry claim refresh failed (%s); entries remain pending", type(exc).__name__)
                if is_nogroup_error(exc):
                    self.broker._ready_groups.discard((stream_key, self.broker.group_name))
                    return

    async def process_batch(self, batch_size: int = 50) -> int:
        # Drain alerts committed earlier (Redis outage, crash) even if no telemetry arrives.
        await self._dispatch_outbox_safely()
        messages, stream_key, error_signal = await self._fetch_batch(batch_size)
        if error_signal or not messages:
            return 0

        message_ids = [
            message_id.decode("utf-8") if isinstance(message_id, bytes) else str(message_id)
            for message_id, _ in messages
        ]
        lease_task = asyncio.create_task(self._refresh_claim_loop(stream_key, message_ids))
        try:
            return await self._process_fetched_batch(messages, stream_key, message_ids)
        finally:
            lease_task.cancel()
            try:
                await lease_task
            except asyncio.CancelledError:
                pass

    async def _process_fetched_batch(self, messages, stream_key: str, message_ids: list[str]) -> int:
        records: list[_Record] = []
        dead_letters: list[tuple[str, dict, str]] = []
        unresolved: set[str] = set()  # per-batch memo; never cached across batches
        newest_id: str | None = message_ids[-1] if message_ids else None

        for (_, entry_data), str_message_id in zip(messages, message_ids):
            newest_id = str_message_id
            entry, undecodable = self._normalise_entry_checked(entry_data)
            event_type = entry.get("event_type", "")
            if undecodable:
                dead_letters.append((str_message_id, {**entry, "undecodable_fields": ",".join(undecodable)},
                                     "undecodable-queue-field"))
                continue
            try:
                raw_payload = json.loads(entry.get("payload", ""))
                if not isinstance(raw_payload, dict):
                    raise ValueError("payload must be a JSON object")
                source_event_key = entry.get("source_event_key") or str_message_id
                if not source_event_key or len(source_event_key) > 160:
                    raise ValueError("source event key is invalid")
                cert_hash = entry.get("cert_fingerprint", "")
                if event_type not in ("heartbeat", "winlog"):
                    raise ValueError("unsupported event type")
                if cert_hash in unresolved:
                    raise UnresolvedAssetError(UNRESOLVED_ASSET_REASON)
                try:
                    target_asset_id = await self._resolve_asset(cert_hash)
                except UnresolvedAssetError:
                    unresolved.add(cert_hash)
                    raise

                if event_type == "heartbeat":
                    heartbeat = AgentHeartbeatRequest.model_validate(raw_payload)
                    metrics = heartbeat.metrics.model_dump()
                    cpu = metrics.pop("cpu_utilization")
                    row = TelemetryMetric(
                        metric_id=uuid.uuid4(), asset_id=target_asset_id,
                        event_time=heartbeat.timestamp, cpu_utilization=float(cpu),
                        diagnostic_payload=metrics, source_event_key=source_event_key,
                    )
                else:
                    winlog = AgentWinlogRequest.model_validate(raw_payload)
                    meta = winlog.metadata.model_dump(exclude_none=True)
                    row = WindowsEventLog(
                        log_id=uuid.uuid4(), asset_id=target_asset_id,
                        occurrence_time=winlog.occurrence_time, event_id=winlog.event_id,
                        severity_level=winlog.severity, evtx_metadata=meta,
                        source_event_key=source_event_key,
                    )
                records.append(_Record(str_message_id, entry, event_type, row))
            except UnresolvedAssetError:
                # Isolated from valid rows; DLQ'd below with a stable reason.
                dead_letters.append((str_message_id, entry, UNRESOLVED_ASSET_REASON))
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                dead_letters.append((str_message_id, entry, self._dead_letter_reason(event_type, exc)))

        is_stub = isinstance(self.broker, StubTelemetryStreamBroker)
        session_maker = database_engine.get_session_maker() if not is_stub else None
        if not is_stub and session_maker is None and records:
            raise DatabaseUnavailableError("Database session unavailable; telemetry batch not persisted")
        persisted = records
        if session_maker and records:
            # Transient DB failures raise here (nothing ACKed -> retried). Only rows the
            # database deterministically rejects come back as poison.
            poison = await self._persist_isolating(session_maker, records)
            poison_ids = {id(record) for record, _ in poison}
            persisted = [r for r in records if id(r) not in poison_ids]
            for record, reason in poison:
                dead_letters.append((record.message_id, record.entry, reason))

        processed_count = len(persisted)
        self.processed_metrics.extend(r.row for r in persisted if r.event_type == "heartbeat")
        self.processed_winlogs.extend(r.row for r in persisted if r.event_type == "winlog")

        # Poison/unknown entries are retained until their DLQ write is confirmed.
        for message_id, entry, reason in dead_letters:
            await self.broker.dead_letter_stream_message(stream_key, message_id, entry, reason)

        # ACK is deliberately last: DB commit and any DLQ write must both succeed.
        await self._ack_and_trim(stream_key, newest_id, str_message_ids=message_ids)
        if newest_id:
            self._last_id = newest_id
        return processed_count

    async def _persist_isolating(self, session_maker, records: list[_Record]) -> list[tuple[_Record, str]]:
        """Persist records; return (record, reason) for rows the database deterministically rejects.

        Only IntegrityError/DataError (row-specific) trigger isolation by recursive split, so
        valid siblings still commit. Any other error (outage, timeout, lost connection) propagates:
        nothing is ACKed or dead-lettered and the batch is retried. Replaying committed halves
        is safe because inserts are ON CONFLICT DO NOTHING on source_event_key and quarantine
        is a no-op for an already Quarantined asset.
        """
        metrics = [r.row for r in records if r.event_type == "heartbeat"]
        winlogs = [r.row for r in records if r.event_type == "winlog"]
        try:
            await self._persist_batch(session_maker, metrics, winlogs)
            return []
        except (IntegrityError, DataError) as exc:
            if len(records) == 1:
                logger.warning("Telemetry row rejected by database (%s); dead-lettering", type(exc).__name__)
                return [(records[0], ROW_REJECTED_REASON)]
            mid = len(records) // 2
            left = await self._persist_isolating(session_maker, records[:mid])
            right = await self._persist_isolating(session_maker, records[mid:])
            return left + right

    @staticmethod
    async def _insert_rows(session, model, rows: list[dict]) -> list:
        """Bulk INSERT … ON CONFLICT DO NOTHING.

        For windows_event_logs the statement RETURNS the rows the database actually inserted, so the
        incident-ingest outbox is fed only from durable identities (a replayed row's transient uuid4
        primary key is dropped by ON CONFLICT and never returned). Metrics need no return value.
        """
        stmt = pg_insert(model).values(rows).on_conflict_do_nothing(index_elements=[model.source_event_key])
        if model is not WindowsEventLog:
            await session.execute(stmt)
            return []
        result = await session.execute(stmt.returning(
            model.log_id, model.asset_id, model.occurrence_time, model.severity_level,
            model.event_id, model.source_event_key))
        return list(result.all())

    @staticmethod
    async def _count_failed_logons(session, src_ip: str, window_end, window_start, *, asset_id=None) -> int:
        """Durable count of committed (plus this transaction's) 4625 rows; replay-safe via unique key.

        Detection always passes asset_id so counts never span unrelated assets.
        """
        conditions = [
            # Inline literal (not a bind param) so the planner can match the partial index
            # predicate `event_id = 4625` even under a generic prepared-statement plan.
            WindowsEventLog.event_id == literal_column(str(int(BRUTE_FORCE_EVENT_ID))),
            WindowsEventLog.evtx_metadata["source_network_ip"].as_string() == src_ip,
            WindowsEventLog.occurrence_time >= window_start,
            WindowsEventLog.occurrence_time <= window_end]
        if asset_id is not None:
            conditions.append(WindowsEventLog.asset_id == asset_id)
        result = await session.execute(select(func.count()).select_from(WindowsEventLog).where(*conditions))
        return int(result.scalar() or 0)

    async def _persist_batch(self, session_maker, db_metrics, db_winlogs) -> None:
        alerts: list[dict] = []
        emitted = 0
        async with session_maker() as session:
            async with session.begin():
                if db_metrics:
                    await self._insert_rows(session, TelemetryMetric, [{
                        "metric_id": item.metric_id, "asset_id": item.asset_id,
                        "event_time": item.event_time, "cpu_utilization": item.cpu_utilization,
                        "diagnostic_payload": item.diagnostic_payload,
                        "source_event_key": item.source_event_key,
                    } for item in db_metrics])
                if db_winlogs:
                    inserted = await self._insert_rows(session, WindowsEventLog, [{
                        "log_id": item.log_id, "asset_id": item.asset_id,
                        "occurrence_time": item.occurrence_time, "event_id": item.event_id,
                        "severity_level": item.severity_level, "evtx_metadata": item.evtx_metadata,
                        "source_event_key": item.source_event_key,
                    } for item in db_winlogs])
                    # Same transaction as the source rows; only RETURNING rows (newly inserted) qualify.
                    emitted = await enqueue_incident_ingest(
                        session, winlog_items_from_returned(inserted or [], origin="telemetry_worker"))
                    alerts = await self._detect_brute_force(session, db_winlogs)
        # Commit succeeded (alert rows are durable in the outbox); only now publish.
        # A rollback raises above, leaving neither the quarantine nor the outbox row.
        if alerts:
            await self._dispatch_outbox_safely(session_maker)
        if emitted:
            # Single dispatch owner (F3): the incident-ingest consumer dispatches. The worker only
            # nudges it post-commit (non-blocking, never raises, no network, no concurrent publish).
            nudge_dispatch()

    async def _detect_brute_force(self, session, db_winlogs) -> list[dict]:
        """Quarantine inside the persisting transaction using a durable row-derived count.

        Counts committed 4625 rows per (asset, valid source IP) in a 60s window ending at EACH
        candidate event's occurrence_time (so a burst early in a long batch is not hidden by a
        later event), so duplicates (same source_event_key, dropped by ON CONFLICT) and replays
        can never inflate it. Placeholder/loopback/invalid IPs are ignored. Threshold stays > 5 per 60s.
        """
        by_key: dict[tuple, list] = {}
        for item in db_winlogs:
            src_ip = (item.evtx_metadata or {}).get("source_network_ip")
            if item.event_id == BRUTE_FORCE_EVENT_ID and _is_countable_source_ip(src_ip):
                by_key.setdefault((item.asset_id, src_ip), []).append(item)

        # Lock the affected asset rows (sorted: consistent order avoids deadlocks) BEFORE counting.
        # A concurrent consumer then waits here until the other commits, so its count sees the
        # other's rows (no missed threshold) and it sees lifecycle_state already Quarantined
        # (no duplicate AuditLog/outbox). populate_existing keeps the locked read authoritative.
        assets: dict = {}
        for asset_id in sorted({asset_id for asset_id, _ in by_key}, key=str):
            result = await session.execute(
                select(InfrastructureAsset).where(InfrastructureAsset.asset_id == asset_id)
                .with_for_update().execution_options(populate_existing=True))
            assets[asset_id] = result.scalars().first()  # None => unresolved: skipped below, as before

        alerts: list[dict] = []
        for (asset_id, src_ip), items in by_key.items():
            asset = assets.get(asset_id)
            if not asset or asset.lifecycle_state == "Quarantined":
                continue
            count = 0
            for window_end in sorted({i.occurrence_time for i in items}):
                count = await self._count_failed_logons(
                    session, src_ip, window_end, window_end - BRUTE_FORCE_WINDOW, asset_id=asset_id)
                if count > BRUTE_FORCE_THRESHOLD:
                    break
            if count <= BRUTE_FORCE_THRESHOLD:
                continue
            old_score = asset.current_compliance_score
            asset.lifecycle_state = "Quarantined"
            asset.current_compliance_score = max(0, old_score - 30)
            session.add(AuditLog(
                actor_id=None, asset_id=asset.asset_id,
                action_verb="AUTOMATED_QUARANTINE_4625",
                immutable_payload={"reason": f"Brute force detected from {src_ip}",
                                   "failed_attempts": count, "old_score": old_score,
                                   "new_score": asset.current_compliance_score}))
            alert = {"event_type": "SECURITY_QUARANTINE_EXCEPTION", "severity": "Critical",
                     "asset_id": str(asset.asset_id), "source_ip": src_ip}
            # Same transaction as the state change: exactly one row per real transition.
            session.add(TelemetryAlertOutbox(
                alert_id=uuid.uuid4(), payload=alert, created_at=datetime.now(UTC)))
            alerts.append(alert)
            logger.warning("Asset %s quarantined after failed logons from %s", asset.asset_id, src_ip)
        return alerts

    async def _dispatch_outbox_safely(self, session_maker=None) -> int:
        """Never let alert delivery fail telemetry processing; pending rows stay for the next pass."""
        try:
            return await self.dispatch_outbox(session_maker or self._outbox_session_maker())
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Alert outbox dispatch failed (%s); rows remain pending", type(exc).__name__)
            return 0

    async def dispatch_outbox(self, session_maker, limit: int = OUTBOX_DISPATCH_BATCH) -> int:
        """Publish pending outbox rows to a durable Redis Stream; stamp published_at after XADD.

        Rows are selected with FOR UPDATE SKIP LOCKED and copied inside a short DB transaction.
        Locks are released before Redis I/O; concurrent dispatchers can therefore publish the same
        alert_id, which downstream consumers must deduplicate. Redis down / XADD failure leaves
        the row pending; published_at is stamped only after confirmed XADD.
        """
        if session_maker is None:
            return 0
        redis_client = await self._ensure_redis()
        if not redis_client:
            return 0
        # Claim and copy rows in a short DB transaction, then release every row lock
        # before Redis I/O. Concurrent dispatchers may publish the same alert_id (at-least-once);
        # downstream consumers must deduplicate by alert_id. A crash before the stamp is replay-safe.
        async with session_maker() as session:
            async with session.begin():
                result = await session.execute(
                    select(TelemetryAlertOutbox)
                    .where(TelemetryAlertOutbox.published_at.is_(None))
                    .order_by(TelemetryAlertOutbox.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True))
                pending = [
                    (row.alert_id, {**row.payload, "alert_id": str(row.alert_id)})
                    for row in result.scalars().all()
                ]

        published = 0
        for alert_id, message in pending:
            try:
                stream_id = await redis_client.xadd(
                    ALERT_STREAM_KEY,
                    {"alert_id": str(alert_id), "payload": json.dumps(message)})
            except (RedisError, OSError, asyncio.TimeoutError) as exc:
                logger.error("Durable alert XADD failed (%s); outbox row stays pending", type(exc).__name__)
                break
            if not stream_id:
                logger.error("Durable alert XADD unconfirmed; outbox row stays pending")
                break

            # Stamp only after XADD is confirmed. This transaction contains no network awaits.
            async with session_maker() as stamp_session:
                async with stamp_session.begin():
                    await stamp_session.execute(
                        update(TelemetryAlertOutbox)
                        .where(TelemetryAlertOutbox.alert_id == alert_id)
                        .where(TelemetryAlertOutbox.published_at.is_(None))
                        .values(published_at=datetime.now(UTC)))
            published += 1
            try:  # Best-effort live fan-out; the durable record already exists.
                await redis_client.publish(ALERT_CHANNEL, json.dumps(message))
            except (RedisError, OSError, asyncio.TimeoutError) as exc:
                logger.warning("Alert PubSub broadcast failed (%s); durable stream entry exists",
                               type(exc).__name__)
        return published

    async def _ack_and_trim(self, stream_key: str, newest_id: str | None, str_message_ids=None) -> None:
        """Confirm consumer-group ACKs. No XTRIM: it can erase pending entries."""
        if str_message_ids:
            await self.broker.ack_stream_messages(stream_key, str_message_ids)


telemetry_worker = TelemetryStreamConsumer()
