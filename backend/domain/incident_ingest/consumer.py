"""Incident ingestion consumer: Redis Stream -> IncidentService, ACK only after the incident commit.

Guarantees (no cross-transaction atomicity is claimed):
* Source side: the source row and its outbox row commit together when the outbox insert
  succeeds. A missing outbox table keeps the pre-v1.1 behaviour (source commits, intent loss
  is logged and counted); any other outbox database error fails the source transaction so
  evidence and intent retry together.
* Incident + evidence + audit are atomic (IncidentService owns its commit on a dedicated
  session). Between the two transactions: durable intent, at-least-once delivery, idempotent
  sink (UNIQUE(source_type, source_id) + evidence lookup).
* A stream entry is ACKed only after IncidentService returned (i.e. committed).
* Transient infrastructure failures never ACK and never dead-letter. Deterministic poison is
  dead-lettered only once the Redis delivery count reaches the cap. Lease refresh uses
  XCLAIM JUSTID, which does not increment the delivery count; XAUTOCLAIM reclaims do count.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum

from redis.exceptions import RedisError, ResponseError
from sqlalchemy.exc import DataError, DBAPIError, IntegrityError
from sqlalchemy.exc import TimeoutError as SATimeoutError

from backend.core.logger import get_logger
from backend.domain.incident.service import (
    EvidenceInput, IncidentConflict, IncidentError, IncidentService,
)
from backend.domain.incident_ingest.dispatcher import dispatch_pending_safely
from backend.domain.incident_ingest.envelope import (
    INGEST_ACTOR, INGEST_DEAD_LETTER_KEY, INGEST_GROUP, INGEST_STREAM_KEY, EnvelopeError, IngestEnvelope,
)
from backend.domain.incident_ingest.outbox import register_wakeup, unregister_wakeup
from backend.infrastructure.cache import cache_manager
from backend.infrastructure.database import database_engine

logger = get_logger("eims.incident_ingest.consumer")

REASON_INVALID_ENVELOPE = "invalid-envelope"
REASON_INCIDENT_REJECTED = "incident-validation-rejected"
REASON_ROW_REJECTED = "row-rejected-by-database"
REASON_UNCLASSIFIED = "unclassified-processing-error"


class FailureKind(Enum):
    TRANSIENT = "transient"  # never ACK, never DLQ
    POISON = "poison"        # DLQ only after the delivery cap


def classify_error(exc: BaseException) -> tuple[FailureKind, str]:
    """Stable classification. Only row/identity-specific failures may ever be dead-lettered."""
    if isinstance(exc, EnvelopeError):
        return FailureKind.POISON, REASON_INVALID_ENVELOPE
    if isinstance(exc, IncidentConflict):
        return FailureKind.TRANSIENT, "incident-conflict"
    if isinstance(exc, IncidentError):
        return FailureKind.POISON, REASON_INCIDENT_REJECTED
    if isinstance(exc, (IntegrityError, DataError)):
        return FailureKind.POISON, REASON_ROW_REJECTED
    if isinstance(exc, (DBAPIError, SATimeoutError, RedisError, OSError, asyncio.TimeoutError)):
        # Outage, lost connection, pool timeout, missing relation during a rollout: environmental.
        return FailureKind.TRANSIENT, "infrastructure-unavailable"
    # F4: an unknown exception is NOT proof the entry is poison (it may be a code bug or an
    # environmental fault); it stays pending/transient and is surfaced via structured logging.
    return FailureKind.TRANSIENT, REASON_UNCLASSIFIED


# F6: winlog provenance severity -> Incident severity. Incident Core defaults are untouched
# (analysis evidence passes severity=None, i.e. the service default).
WINLOG_SEVERITY_MAP = {"critical": "critical", "error": "high", "warning": "medium"}
MAX_DB_CONCURRENCY = 8  # F5: hard cap on per-entry dedicated DB sessions held at once


def incident_severity_for(envelope) -> str | None:
    if envelope.source_type != "winlog":
        return None
    raw = envelope.provenance.get("severity")
    return WINLOG_SEVERITY_MAP.get(raw.strip().lower()) if isinstance(raw, str) else None


def _text(value) -> str:
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)


class IncidentIngestConsumer:
    def __init__(self, *, redis_provider: Callable[[], object] | None = None,
                 session_maker_provider: Callable[[], object] | None = None,
                 consumer_name: str | None = None, polling_interval: float = 1.0,
                 batch_size: int = 20, concurrency: int = 4, reclaim_idle_ms: int = 30000,
                 max_delivery_attempts: int = 5, dispatch_limit: int = 100,
                 actor: str = INGEST_ACTOR, stop_grace_seconds: float = 5.0):
        self._redis_provider = redis_provider or (lambda: cache_manager.redis)
        self._session_maker_provider = session_maker_provider or database_engine.get_session_maker
        self.consumer_name = consumer_name or f"eims-ingest-{uuid.uuid4().hex[:12]}"
        self.polling_interval = polling_interval
        self.batch_size = max(1, batch_size)
        self.concurrency = max(1, min(int(concurrency), MAX_DB_CONCURRENCY))
        self.reclaim_idle_ms = max(0, int(reclaim_idle_ms))
        self.max_delivery_attempts = max(1, max_delivery_attempts)
        self.dispatch_limit = dispatch_limit
        self.actor = actor
        self.stop_grace_seconds = stop_grace_seconds
        self._ready = False
        self._running = False
        self._task: asyncio.Task | None = None
        self._wakeup = asyncio.Event()
        self.metrics: dict[str, int] = {
            "dispatched": 0, "acked": 0, "incidents_created": 0, "incidents_reused": 0,
            "transient_retries": 0, "poison_retained": 0, "dead_lettered": 0, "ack_failures": 0}

    # ------------------------------------------------------------------ lifecycle
    def _signal(self) -> None:
        self._wakeup.set()

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._wakeup = asyncio.Event()
        register_wakeup(self._signal)
        self._task = asyncio.create_task(self._loop())
        logger.info("Incident ingest consumer started")

    async def stop(self) -> None:
        """Let the in-flight batch finish (bounded), then cancel. Unacked entries stay pending."""
        self._running = False
        self._signal()
        unregister_wakeup(self._signal)
        task, self._task = self._task, None
        if task is None:
            return
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=self.stop_grace_seconds)
        except asyncio.TimeoutError:
            await self._cancel_task(task)
        except asyncio.CancelledError:
            # stop() itself was cancelled (F11): still tear the loop down, then propagate.
            await self._cancel_task(task)
            raise
        except Exception:
            pass
        logger.info("Incident ingest consumer stopped")

    @staticmethod
    async def _cancel_task(task: asyncio.Task) -> None:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.process_batch()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Incident ingest batch failed; entries remain pending (%s)", type(exc).__name__)
            if not self._running:
                break
            try:
                await asyncio.wait_for(self._wakeup.wait(), timeout=self.polling_interval)
            except asyncio.TimeoutError:
                pass
            self._wakeup.clear()

    # ------------------------------------------------------------------ redis plumbing
    async def _ensure_group(self, client) -> None:
        if self._ready:
            return
        try:
            await client.xgroup_create(name=INGEST_STREAM_KEY, groupname=INGEST_GROUP, id="0-0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc).upper():
                raise
        self._ready = True

    async def _fetch(self, client) -> list[tuple[str, dict[str, str]]]:
        await self._ensure_group(client)
        try:
            claimed = await client.xautoclaim(
                name=INGEST_STREAM_KEY, groupname=INGEST_GROUP, consumername=self.consumer_name,
                min_idle_time=self.reclaim_idle_ms, start_id="0-0", count=self.batch_size)
            pending = claimed[1] if isinstance(claimed, (tuple, list)) else claimed.get("messages", [])
            if pending:
                return [(_text(mid), self._normalise(fields)) for mid, fields in pending if fields is not None]
            streams = await client.xreadgroup(
                groupname=INGEST_GROUP, consumername=self.consumer_name,
                streams={INGEST_STREAM_KEY: ">"}, count=self.batch_size)
        except ResponseError as exc:
            if "NOGROUP" in str(exc).upper():
                self._ready = False  # recreate on next pass; never delete streams/groups
                return []
            raise
        return [(_text(mid), self._normalise(fields)) for _, entries in streams for mid, fields in entries]

    @staticmethod
    def _normalise(fields: dict) -> dict[str, str]:
        return {_text(k): _text(v) for k, v in fields.items()}

    async def _refresh_loop(self, client, in_flight: set[str]) -> None:
        """Keep claimed entries leased. XCLAIM JUSTID resets idle time WITHOUT bumping delivery count."""
        interval = max(0.05, self.reclaim_idle_ms / 3000)
        while True:
            await asyncio.sleep(interval)
            ids = list(in_flight)
            if not ids:
                continue
            try:
                await client.xclaim(
                    name=INGEST_STREAM_KEY, groupname=INGEST_GROUP, consumername=self.consumer_name,
                    min_idle_time=0, message_ids=ids, idle=0, justid=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Incident ingest lease refresh failed (%s); entries remain pending",
                               type(exc).__name__)

    async def _delivery_count(self, client, message_id: str) -> int | None:
        rows = await client.xpending_range(
            INGEST_STREAM_KEY, INGEST_GROUP, min=message_id, max=message_id, count=1)
        if not rows:
            return None
        row = rows[0]
        value = row.get("times_delivered") if isinstance(row, dict) else row[3]
        return int(value)

    async def _ack(self, client, message_id: str) -> bool:
        try:
            acked = await client.xack(INGEST_STREAM_KEY, INGEST_GROUP, message_id)
        except Exception as exc:
            self.metrics["ack_failures"] += 1
            logger.warning("Incident ingest ACK failed (%s); entry will be redelivered (idempotent)",
                           type(exc).__name__)
            return False
        if acked != 1:
            self.metrics["ack_failures"] += 1
            return False
        self.metrics["acked"] += 1
        try:  # best-effort cleanup only after the durable ACK
            await client.xdel(INGEST_STREAM_KEY, message_id)
        except Exception:
            logger.debug("Incident ingest stream cleanup failed after ACK")
        return True

    async def _dead_letter(self, client, message_id: str, fields: dict[str, str],
                           reason: str, deliveries: int) -> bool:
        entry = json.dumps(fields, ensure_ascii=False, default=str)[:2048]
        stream_id = await client.xadd(INGEST_DEAD_LETTER_KEY, {
            "source_stream": INGEST_STREAM_KEY, "source_stream_id": message_id, "reason": reason,
            "deliveries": str(deliveries), "entry": entry,
            "failed_at": datetime.now(UTC).isoformat()})
        if not stream_id:
            raise RuntimeError("Dead-letter write not confirmed")
        self.metrics["dead_lettered"] += 1
        return await self._ack(client, message_id)

    # ------------------------------------------------------------------ processing
    async def _create_incident(self, session_maker, envelope: IngestEnvelope) -> bool:
        """Dedicated session per entry; IncidentService owns (and commits) its own transaction."""
        evidence = EvidenceInput(
            source_type=envelope.source_type, source_id=envelope.source_id,
            observed_at=envelope.observed_at, source_event_key=envelope.source_event_key)
        async with session_maker() as session:
            service = IncidentService(session)
            items, asset_id = await service.enrich_evidence([evidence], envelope.asset_id)
            # Offline imports store arrival time when the log carries none and assume UTC for zone-less times. Such a
            # value is not an event time: never let it drive an automatic merge.
            quality = envelope.provenance.get("time_quality")
            if quality is None and envelope.provenance.get("origin") == "offline_import":
                quality = "absent"  # queued before time quality was recorded: arrival time must not pass as event time
            if envelope.source_type == "winlog" and quality in {"absent", "source_naive"}:
                items = [replace(i, event_time=None, time_basis="offline_import_time_" + quality,
                                 time_confidence="missing" if quality == "absent" else "ambiguous", time_original=None)
                         for i in items]
            _incident, created = await service.create_from_evidence(
                items, actor=self.actor, asset_id=asset_id,
                severity=incident_severity_for(envelope))
        return created

    async def _handle_failure(self, client, message_id: str, fields: dict[str, str],
                              kind: FailureKind, reason: str) -> None:
        if kind is FailureKind.TRANSIENT:
            self.metrics["transient_retries"] += 1
            logger.warning("Incident ingest %s transient failure (%s); left pending", message_id, reason)
            return
        try:
            deliveries = await self._delivery_count(client, message_id)
            if deliveries is not None and deliveries >= self.max_delivery_attempts:
                await self._dead_letter(client, message_id, fields, reason, deliveries)
                logger.error("Incident ingest %s dead-lettered (%s) after %s deliveries",
                             message_id, reason, deliveries)
                return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Incident ingest poison handling failed (%s); entry stays pending", type(exc).__name__)
            return
        self.metrics["poison_retained"] += 1
        logger.warning("Incident ingest %s poison (%s); retained until delivery cap", message_id, reason)

    async def _process_message(self, client, session_maker, message_id: str, fields: dict[str, str]) -> None:
        try:
            envelope = IngestEnvelope.from_stream_fields(fields)
            created = await self._create_incident(session_maker, envelope)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            kind, reason = classify_error(exc)
            await self._handle_failure(client, message_id, fields, kind, reason)
            return
        self.metrics["incidents_created" if created else "incidents_reused"] += 1
        await self._ack(client, message_id)  # only after the incident transaction committed

    async def process_batch(self) -> int:
        """One dispatch + consume cycle. Returns the number of entries ACKed this cycle."""
        client = self._redis_provider()
        session_maker = self._session_maker_provider()
        if client is None or session_maker is None:
            return 0
        self.metrics["dispatched"] += await dispatch_pending_safely(session_maker, client, self.dispatch_limit)
        messages = await self._fetch(client)
        if not messages:
            return 0
        acked_before = self.metrics["acked"]
        in_flight = {mid for mid, _ in messages}
        lease = asyncio.create_task(self._refresh_loop(client, in_flight))
        semaphore = asyncio.Semaphore(self.concurrency)

        async def run(message_id: str, fields: dict[str, str]) -> None:
            async with semaphore:
                try:
                    await self._process_message(client, session_maker, message_id, fields)
                finally:
                    in_flight.discard(message_id)

        try:
            await asyncio.gather(*(run(mid, fields) for mid, fields in messages))
        finally:
            lease.cancel()
            try:
                await lease
            except asyncio.CancelledError:
                pass
        return self.metrics["acked"] - acked_before


incident_ingest_consumer = IncidentIngestConsumer()
