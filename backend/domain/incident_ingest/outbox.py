"""Source-side emission helpers: insert outbox rows inside the caller's source transaction.

Nothing here commits, rolls back, or awaits a network service. Callers own the transaction.
"""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger import get_logger
from backend.domain.incident_ingest.envelope import (
    SOURCE_EVENT_KEY_MAX, SOURCE_ID_MAX, EnvelopeError, qualifies_winlog_severity,
    sanitize_provenance, to_utc,
)
from backend.domain.incident_ingest.models import OUTBOX_SOURCE_TYPES, IncidentIngestOutbox

logger = get_logger("eims.incident_ingest.outbox")

_wakeup_hooks: list[Callable[[], None]] = []


def register_wakeup(hook: Callable[[], None]) -> None:
    if hook not in _wakeup_hooks:
        _wakeup_hooks.append(hook)


def unregister_wakeup(hook: Callable[[], None]) -> None:
    if hook in _wakeup_hooks:
        _wakeup_hooks.remove(hook)


def nudge_dispatch() -> None:
    """Non-blocking, never raises: ask the running consumer to dispatch now (post-commit hint)."""
    for hook in list(_wakeup_hooks):
        try:
            hook()
        except Exception:  # a hint must never fail ingestion
            logger.debug("incident-ingest wakeup hook failed", exc_info=True)


@dataclass(frozen=True)
class OutboxItem:
    source_type: str
    source_id: str
    observed_at: datetime
    source_event_key: str | None = None
    asset_id: uuid.UUID | None = None
    provenance: dict[str, Any] | None = None


def _row(item: OutboxItem) -> dict[str, Any]:
    if item.source_type not in OUTBOX_SOURCE_TYPES:
        raise EnvelopeError("unsupported source_type")
    source_id = str(item.source_id)
    if not source_id or len(source_id) > SOURCE_ID_MAX:
        raise EnvelopeError("invalid source_id")
    if item.source_event_key is not None and len(item.source_event_key) > SOURCE_EVENT_KEY_MAX:
        raise EnvelopeError("invalid source_event_key")
    return {
        "outbox_id": uuid.uuid4(), "source_type": item.source_type, "source_id": source_id,
        "source_event_key": item.source_event_key or None, "asset_id": item.asset_id,
        "observed_at": to_utc(item.observed_at), "provenance": sanitize_provenance(item.provenance),
    }


metrics: dict[str, int] = {"invalid_items_skipped": 0, "outbox_insert_failures": 0, "unsupported_session_skips": 0}

# Each row binds 7 parameters; asyncpg caps a statement at 32767 parameters.
MAX_ROWS_PER_INSERT = 500


def _sqlstate(exc: BaseException) -> str | None:
    """Best-effort SQLSTATE extraction across SQLAlchemy/asyncpg wrapping."""
    orig = getattr(exc, "orig", None)
    return (getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
            or getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None))


def _is_missing_table(exc: BaseException) -> bool:
    """True only for 'relation does not exist' (migration not applied yet).

    That single case keeps pre-v1.1 behaviour: source evidence is still persisted so the
    deployment never fails open. Any other database error is a real fault and must not be
    silently absorbed, because the source row would then commit without its incident intent.
    """
    if _sqlstate(exc) == "42P01":
        return True
    text = str(exc).lower()
    return "undefinedtable" in text or (
        "incident_ingest_outbox" in text and "does not exist" in text)


async def enqueue_incident_ingest(session, items: Iterable[OutboxItem]) -> int:
    """INSERT … ON CONFLICT DO NOTHING on (source_type, source_id) in the caller's transaction.

    Guarantee, stated precisely (no fake atomicity):
    * when the outbox INSERT succeeds, the source rows and the intent commit together;
    * a missing outbox table (migration not applied) keeps the pre-v1.1 behaviour: the
      savepoint rolls back, the source evidence still commits, and the loss is logged,
      counted in ``metrics`` and recoverable only by operator re-emission;
    * any other database error is re-raised, so the caller's source transaction fails and
      retries as a unit instead of committing evidence without its intent.

    Items are prevalidated individually: an invalid item is logged, counted and skipped so it
    can never poison the source batch. Rows are chunked to stay well below the driver's
    parameter limit. Returns the number of rows submitted (duplicates are absorbed).
    """
    rows: list[dict[str, Any]] = []
    for item in items:
        try:
            rows.append(_row(item))
        except EnvelopeError as exc:
            metrics["invalid_items_skipped"] += 1
            logger.error("Incident-ingest item skipped before enqueue (%s): %s/%s",
                         exc, getattr(item, "source_type", "?"), getattr(item, "source_id", "?"))
    if not rows:
        return 0
    try:
        async with session.begin_nested():
            for start in range(0, len(rows), MAX_ROWS_PER_INSERT):
                chunk = rows[start:start + MAX_ROWS_PER_INSERT]
                await session.execute(pg_insert(IncidentIngestOutbox).values(chunk)
                                      .on_conflict_do_nothing(index_elements=["source_type", "source_id"]))
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        metrics["outbox_insert_failures"] += 1
        if _is_missing_table(exc):
            logger.error("Incident-ingest outbox table is missing (%s); source evidence preserved, "
                         "%d incident intent(s) NOT recorded", type(exc).__name__, len(rows))
            return 0
        logger.error("Incident-ingest outbox insert failed (%s); failing the source transaction so "
                     "evidence and intent retry together", type(exc).__name__)
        raise
    return len(rows)


def winlog_items_from_returned(returned: Sequence[Any], *, origin: str) -> list[OutboxItem]:
    """Build outbox items ONLY from rows the database actually inserted (INSERT … RETURNING).

    Rows suppressed by ON CONFLICT DO NOTHING are never returned, so a replay's transient uuid4
    primary key can never become a source identity. Severity policy: Critical/Error/Warning only.
    Expected row shape: (log_id, asset_id, occurrence_time, severity_level, event_id, source_event_key).
    """
    items: list[OutboxItem] = []
    for log_id, asset_id, occurrence_time, severity, event_id, source_event_key in returned:
        if not qualifies_winlog_severity(severity):
            continue
        items.append(OutboxItem(
            source_type="winlog", source_id=str(log_id), observed_at=occurrence_time,
            source_event_key=source_event_key, asset_id=asset_id,
            provenance={"origin": origin, "event_id": event_id, "severity": severity}))
    return items


async def enqueue_analysis_history(db, history, *, origin: str, asset_id: uuid.UUID | None = None) -> int:
    """Flush (no commit) so the persisted history id/created_at exist, then enqueue in the same transaction.

    ``asset_id`` must be an already-verified registry id (offline import) or None; it is never inferred.

    Emission requires a real SQLAlchemy ``AsyncSession`` (every production session is one). In-memory
    session doubles used by hermetic evaluation/unit harnesses have no outbox table and are skipped.
    """
    if not isinstance(db, AsyncSession):
        # Deliberate test doubles stay supported, but the skip is never silent (F9).
        metrics["unsupported_session_skips"] += 1
        logger.warning("Incident-ingest emission skipped: unsupported session type %s", type(db).__name__)
        return 0
    await db.flush()
    created = history.created_at
    if history.id is None or created is None:
        metrics["invalid_items_skipped"] += 1
        logger.error("Incident-ingest emission skipped: analysis history id/created_at not populated")
        return 0
    return await enqueue_incident_ingest(db, [OutboxItem(
        source_type="analysis", source_id=str(history.id), observed_at=created,
        asset_id=asset_id, provenance={"origin": origin, "event_id": history.event_id})])
