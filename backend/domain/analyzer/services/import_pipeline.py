"""
backend/domain/analyzer/services/import_pipeline.py

EIMS Sprint 13 - Offline USB Auditor Event Evidence -> AI Analysis pipeline.

Ingests the bounded `event_logs` collection from a USB Auditor offline report
into the WindowsEventLog store (JSONB dedup, no migration), then runs the
EXISTING Analyzer pipeline on a bounded subset, prioritizing Critical/Error
events first. Provenance for every analyzed event is recorded inside the
analysis_history.event_metadata JSON column so findings can be traced back to
the exact collected evidence.

Design invariants:
    - No DB migration required (JSONB dedup + JSON provenance, no new columns).
    - Reuses analyzer services (search_solutions / build_summary /
      format_summary_text) - no analyzer logic is duplicated.
    - Bounded AI: at most `analyze_max` events are analyzed per import,
      Critical/Error first; curated catalog is consulted first by build_summary.
    - Analysis failures are strictly non-fatal and must never lose evidence.
    - Duplicate events do not create duplicate analyses (dedup via
      _reporter_dedup on both WindowsEventLog and AnalysisHistory).
"""

import asyncio
import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import List, Optional

from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger import get_logger
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.schemas.analyze import EventMetadata
from backend.domain.analyzer.services.summary import (
    build_summary,
    format_summary_text,
    search_solutions,
)
from backend.domain.telemetry.models import WindowsEventLog

logger = get_logger("eims.domain.import_pipeline")

# Provenance marker: evidence collected by the offline USB Auditor tool.
SOURCE_TYPE = "USB_OFFLINE_COLLECTION"

# Bounded AI analysis cap (default max events analyzed per import).
DEFAULT_ANALYZE_MAX = 10

# Severity priority for analysis ordering (higher = analyzed first).
_SEVERITY_PRIORITY = {"critical": 3, "error": 2, "warning": 1}

# Max message length retained as evidence text.
_MAX_MESSAGE_LEN = 1000


@dataclass
class EventIngestResult:
    """Ingestion counters returned to the import endpoint and clients."""

    events_received: int = 0
    events_new: int = 0
    events_duplicate: int = 0
    events_failed: int = 0
    events_analyzed: int = 0
    analysis_failed: int = 0
    summary: str = ""


# ---------------------------------------------------------------------------
# Pure / deterministic helpers (hermetic-testable)
# ---------------------------------------------------------------------------


def normalize_report_event(event: dict) -> Optional[dict]:
    """
    Normalize one USB Auditor `event_logs` entry into the field set required
    by WindowsEventLog plus the evidence-provenance envelope.
    Returns None when the event is not structurally usable.
    """
    if not isinstance(event, dict):
        return None

    try:
        event_id = int(event.get("event_id"))
    except (TypeError, ValueError):
        return None
    if event_id < 0:
        return None

    severity = str(event.get("severity", "Information")).strip() or "Information"
    severity = severity[:16]

    channel = str(event.get("channel", "System")).strip() or "System"
    provider = str(event.get("provider", "Unknown")).strip() or "Unknown"

    occurrence_time = event.get("occurrence_time")
    parsed_time: Optional[datetime] = None
    if occurrence_time:
        try:
            parsed_time = datetime.fromisoformat(str(occurrence_time))
            if parsed_time.tzinfo is None:
                parsed_time = parsed_time.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            parsed_time = None

    record_id = event.get("record_id")
    message = str(event.get("message", ""))[:_MAX_MESSAGE_LEN]

    return {
        "event_id": event_id,
        "severity_level": severity,
        "occurrence_time": parsed_time,
        "channel": channel,
        "provider": provider,
        "record_id": record_id,
        "message": message,
    }


def compute_dedup_key(asset_id, event: dict) -> str:
    """
    Deterministic evidence identity for a collected event. Stable across
    re-collections of the same physical record on the same asset, so duplicate
    imports never re-create events or re-run analysis.
    """
    raw = "|".join(
        str(value)
        for value in (
            str(asset_id),
            event.get("channel", ""),
            event.get("provider", ""),
            event.get("record_id", ""),
            event.get("occurrence_time", ""),
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_evtx_metadata(event: dict, dedup_key: str) -> dict:
    """Evidence-provenance envelope stored inside WindowsEventLog.evtx_metadata."""
    return {
        "channel": event.get("channel"),
        "provider": event.get("provider"),
        "record_id": event.get("record_id"),
        "message": event.get("message"),
        "source_type": SOURCE_TYPE,
        "source_subtype": "WINDOWS_EVENT_LOG",
        "collected_at": datetime.now(UTC).isoformat(),
        "_reporter_dedup": dedup_key,
    }


def build_analysis_provenance(event_log_id, asset_id, event: dict) -> dict:
    """
    Provenance labels embedded into analysis_history.event_metadata so every
    AI finding can be traced back to the specific collected WindowsEventLog row.
    All values are JSON-serializable (datetime is normalized to ISO-8601).
    """
    occurrence_time = event.get("occurrence_time")
    if hasattr(occurrence_time, "isoformat"):
        occurrence_time = occurrence_time.isoformat()
    return {
        "source_type": SOURCE_TYPE,
        "source_subtype": "WINDOWS_EVENT_LOG",
        "asset_id": str(asset_id),
        "event_source_id": str(event_log_id),
        "channel": event.get("channel"),
        "provider": event.get("provider"),
        "record_id": event.get("record_id"),
        "occurrence_time": occurrence_time,
    }


def analysis_priority(event: dict) -> int:
    """Return analysis priority for an event (Critical/Error first)."""
    severity = str(event.get("severity_level", "")).strip().lower()
    return _SEVERITY_PRIORITY.get(severity, 0)


def build_event_metadata(event: dict) -> EventMetadata:
    """Construct the analyzer EventMetadata directly from collected fields."""
    return EventMetadata(
        eventId=str(event.get("event_id", "Unknown")),
        provider=event.get("provider", "Unknown"),
        level=event.get("severity_level", ""),
        logName=event.get("channel", ""),
        timestamp=str(event.get("occurrence_time", "")),
        computer=event.get("computer", ""),
        isCritical=analysis_priority(event) >= 2,
        faultingApp=event.get("faulting_app", ""),
    )


def format_event_description(event: dict) -> str:
    """Render a human-readable event description for the analyzer."""
    message = event.get("message", "").strip()
    if message:
        return message
    return (
        f"Event ID {event.get('event_id')} from {event.get('provider')} "
        f"({event.get('channel')}) - no message text collected."
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


# WindowsEventLog fields are JSONB: use -> (JSON) indexing via .astext (->>),
# and for plain JSON columns cast to JSONB first. Plain `cast(col->'key', String)`
# would render `CAST(metadata->'key' AS TEXT)` which KEEPS surrounding quotes on
# PostgreSQL and never matches unquoted key values (verified against live PG).
async def _fetch_duplicate_keys(db: AsyncSession, asset_id, keys: List[str]) -> set:
    """Return the subset of dedup keys already persisted for this asset."""
    if not keys:
        return set()
    dedup_expr = WindowsEventLog.evtx_metadata["_reporter_dedup"].astext
    stmt = (
        select(dedup_expr)
        .where(WindowsEventLog.asset_id == asset_id)
        .where(dedup_expr.in_(keys))
    )
    result = await db.execute(stmt)
    return set(result.scalars().all())


async def _fetch_analyzed_keys(db: AsyncSession, keys: List[str]) -> set:
    """Return the subset of dedup keys already analyzed in history."""
    if not keys:
        return set()
    dedup_expr = cast(AnalysisHistory.event_metadata, JSONB)["_reporter_dedup"].astext
    stmt = select(dedup_expr).where(dedup_expr.in_(keys))
    try:
        result = await db.execute(stmt)
        return set(result.scalars().all())
    except Exception as exc:  # conservative: JSON cast unsupported in some DBs
        logger.warning("Analyzed-key lookup failed (treated as none): %s", exc)
        return set()


async def _persist_event(db: AsyncSession, asset_id, event: dict, dedup_key: str) -> uuid.UUID:
    """Create a WindowsEventLog row for a new event and return its log_id."""
    event_log_id = uuid.uuid4()
    row = WindowsEventLog(
        log_id=event_log_id,
        asset_id=asset_id,
        occurrence_time=event.get("occurrence_time") or datetime.now(UTC),
        event_id=event.get("event_id"),
        severity_level=event.get("severity_level", "Information"),
        evtx_metadata=build_evtx_metadata(event, dedup_key),
    )
    db.add(row)
    return event_log_id


async def _find_event_log_id(db: AsyncSession, asset_id, dedup_key: str) -> Optional[str]:
    """Resolve the persisted log_id for a dedup key (for provenance)."""
    try:
        stmt = select(WindowsEventLog.log_id).where(
            WindowsEventLog.asset_id == asset_id,
            WindowsEventLog.evtx_metadata["_reporter_dedup"].astext == dedup_key,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception:
        return None


async def _safe_rollback(db: AsyncSession) -> None:
    try:
        await db.rollback()
    except Exception:
        pass


async def _analyze_event(
    db: AsyncSession,
    asset_id,
    event: dict,
    dedup_key: str,
    language: str = "th",
    api_key: Optional[str] = None,
) -> bool:
    """
    Run the existing analyzer pipeline for one event and persist the finding
    with provenance. Returns True on success; never raises.
    """
    event_id = str(event.get("event_id", "Unknown"))
    provider = event.get("provider", "Unknown")
    description = format_event_description(event)

    try:
        results, combined_snippets = await asyncio.to_thread(
            search_solutions, event_id, provider
        )
        solution = await build_summary(
            event_id,
            provider,
            combined_snippets,
            results,
            language,
            event.get("faulting_app", ""),
            api_key,
            description,
            db,
        )
        final_summary = format_summary_text(solution, language)

        metadata_dict = build_event_metadata(event).model_dump()
        metadata_dict["_reporter_dedup"] = dedup_key
        metadata_dict.update(build_analysis_provenance(None, asset_id, event))

        event_log_id = await _find_event_log_id(db, asset_id, dedup_key)
        if event_log_id:
            metadata_dict["event_source_id"] = str(event_log_id)

        row = AnalysisHistory(
            event_id=event_id,
            provider=provider,
            parse_method=f"USB_OFFLINE_COLLECTION:{SOURCE_TYPE}",
            description=description,
            ai_summary=final_summary,
            solution_summary=solution.model_dump(),
            event_metadata=metadata_dict,
            search_results=[res.model_dump() for res in results],
            search_time_ms=0.0,
            username="system",
        )
        db.add(row)
        await db.commit()
        return True
    except Exception as exc:
        logger.warning("Analysis failed for event %s/%s (non-fatal): %s", event_id, provider, exc)
        await _safe_rollback(db)
        return False


async def ingest_report_events(
    db: AsyncSession,
    asset_id,
    report_data: dict,
    analyze_max: int = DEFAULT_ANALYZE_MAX,
    language: str = "th",
    api_key: Optional[str] = None,
) -> EventIngestResult:
    """
    Ingest the `event_logs` evidence collection of an offline USB Auditor report.

    Returns EventIngestResult. Never raises - evidence loss is impossible;
    report persistence in the caller is unaffected by event-ingestion failures.
    """
    result = EventIngestResult()

    event_logs = report_data.get("event_logs", {}) if isinstance(report_data, dict) else {}
    if not isinstance(event_logs, dict):
        event_logs = {}
    events = event_logs.get("events", [])
    if not isinstance(events, list) or not events:
        result.summary = "No event evidence in report"
        return result

    result.events_received = len(events)

    # 1. Normalize (drop structurally unusable entries, counted as failed)
    normalized: List[dict] = []
    for raw_event in events:
        clean = normalize_report_event(raw_event)
        if clean is None:
            result.events_failed += 1
            logger.warning("Skipping unusable event_logs entry: %s", raw_event)
            continue
        normalized.append(clean)

    # 2. Dedup against already-persisted WindowsEventLog rows for this asset
    keys = [compute_dedup_key(asset_id, ev) for ev in normalized]
    try:
        existing_keys = await _fetch_duplicate_keys(db, asset_id, keys)
    except Exception as exc:
        logger.warning("Dedup lookup failed; treating all as new: %s", exc)
        existing_keys = set()

    if analyze_max < 0:
        analyze_max = DEFAULT_ANALYZE_MAX

    # 3. Persist new events (one transaction, atomic)
    new_rows: List[tuple] = []  # (event, dedup_key, event_log_id)
    for event, dedup_key in zip(normalized, keys):
        if dedup_key in existing_keys:
            result.events_duplicate += 1
            continue
        event_log_id = await _persist_event(db, asset_id, event, dedup_key)
        new_rows.append((event, dedup_key, event_log_id))
        result.events_new += 1

    if new_rows:
        try:
            await db.commit()
        except Exception as exc:
            logger.error("Failed to persist event evidence batch: %s", exc)
            await _safe_rollback(db)
            result.events_failed += result.events_new
            result.events_new = 0
            new_rows = []
            result.summary = (
                f"events_received={result.events_received} "
                f"events_new=0 events_duplicate={result.events_duplicate} "
                f"events_failed={result.events_failed} (persistence error)"
            )
            return result

    # 4. Bounded analysis: Critical/Error first, skip already-analyzed keys
    if new_rows:
        new_rows.sort(key=lambda item: analysis_priority(item[0]), reverse=True)
        candidates = new_rows[:analyze_max]
        candidate_keys = [item[1] for item in candidates]
        try:
            analyzed_keys = await _fetch_analyzed_keys(db, candidate_keys)
        except Exception:
            analyzed_keys = set()

        for event, dedup_key, _ in candidates:
            if dedup_key in analyzed_keys:
                continue
            ok = await _analyze_event(db, asset_id, event, dedup_key, language, api_key)
            if ok:
                result.events_analyzed += 1
            else:
                result.analysis_failed += 1

    result.summary = (
        f"events_received={result.events_received} "
        f"events_new={result.events_new} "
        f"events_duplicate={result.events_duplicate} "
        f"events_failed={result.events_failed} "
        f"events_analyzed={result.events_analyzed} "
        f"analysis_failed={result.analysis_failed}"
    )
    return result