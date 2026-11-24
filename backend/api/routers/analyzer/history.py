from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import Date, case, cast, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.domain.analyzer.auth import get_current_user
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.models.knowledge import KnowledgeEntry
from backend.domain.analyzer.schemas.analyze import EventMetadata, SolutionSummary
from backend.domain.analyzer.schemas.history import HistoryResponse
from backend.infrastructure.database import get_db_session as get_db

router = APIRouter()


def _safe_solution_summary(raw) -> "SolutionSummary | None":
    """Defensively parse stored solution JSON.

    Historical rows may carry legacy shapes (e.g. confidence stored as a
    dict).  One malformed row must never 500 the whole history response,
    so coerce known fields and degrade to overview-only instead of raising.
    """
    if not isinstance(raw, dict):
        return None
    cleaned = dict(raw)
    conf = cleaned.get("confidence")
    if isinstance(conf, dict):
        level = conf.get("level")
        cleaned["confidence"] = level if isinstance(level, str) else ""
    elif conf is not None and not isinstance(conf, str):
        cleaned["confidence"] = str(conf)
    for key in ("causes", "steps", "evidence", "limitations", "nextEvidence"):
        val = cleaned.get(key)
        if val is not None and not isinstance(val, list):
            cleaned[key] = [str(val)]
    try:
        return SolutionSummary(**cleaned)
    except Exception:
        pass
    try:
        overview = cleaned.get("overview")
        return SolutionSummary(overview=overview if isinstance(overview, str) else "")
    except Exception:
        return None


def _safe_event_metadata(raw) -> "EventMetadata | None":
    if not isinstance(raw, dict):
        return None
    try:
        return EventMetadata(**raw)
    except Exception:
        return None


def _safe_search_results(raw) -> list:
    from backend.domain.analyzer.schemas.analyze import SearchResult

    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            out.append(SearchResult(**item))
        except Exception:
            continue
    return out


@router.get("/catalog")
async def get_operational_catalog(
    response: Response,
    source_family: str | None = None,
):
    """Return public, versioned reference data; it contains no user incident history."""
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=600"
    from backend.domain.analyzer.services.operational_catalog import get_catalog
    entries = get_catalog(source_family)
    return {
        "classification": "OPERATIONAL_EVENT_CATALOG",
        "schema_version": 1,
        # Same loader as Analyzer matching: operational_event_catalog.json + diagnostic_knowledge_catalog.json.
        # Not the governed inventory (_catalog / eligibility 911) and not vendor_reference / unmapped candidates alone.
        "surface": "parser_linked_analyzer_catalog",
        "count": len(entries),
        "entries": entries,
    }


@router.get("/", response_model=list[HistoryResponse])
async def get_all_history(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
    asset_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(AnalysisHistory).where(AnalysisHistory.username == _user)
    if asset_id:
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
        stmt = stmt.filter(
            cast(AnalysisHistory.event_metadata, PGJSONB)["asset_id"].astext == asset_id
        )
    history_records = (
        await db.execute(
            stmt.order_by(AnalysisHistory.created_at.desc(), AnalysisHistory.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    results = []
    for record in history_records:
        solution = _safe_solution_summary(record.solution_summary)
        metadata = _safe_event_metadata(record.event_metadata)
        provenance = None
        if record.event_metadata:
            meta = record.event_metadata
            if meta.get("source_type") or meta.get("asset_id"):
                provenance = {
                    "source_type": meta.get("source_type"),
                    "source_subtype": meta.get("source_subtype"),
                    "asset_id": meta.get("asset_id"),
                    "event_source_id": meta.get("event_source_id"),
                    "channel": meta.get("channel"),
                    "provider": meta.get("provider"),
                    "record_id": meta.get("record_id"),
                    "occurrence_time": meta.get("occurrence_time"),
                }
        bundle = {}
        try:
            if isinstance(record.event_metadata, dict):
                attrs = record.event_metadata.get("attributes") or {}
                if isinstance(attrs, dict) and isinstance(attrs.get("bundle"), dict):
                    bundle = attrs["bundle"]
                elif isinstance(record.event_metadata.get("bundle"), dict):
                    # Backward compat: Phase-2 rows stored a top-level key.
                    bundle = record.event_metadata["bundle"]
        except Exception:
            bundle = {}
        results.append({
            "id": record.id,
            "eventId": record.event_id,
            "provider": record.provider,
            "parseMethod": record.parse_method,
            "description": record.description,
            "aiSummary": record.ai_summary,
            "solutionSummary": solution,
            "eventMetadata": metadata,
            "searchResults": _safe_search_results(record.search_results),
            "searchTimeMs": record.search_time_ms if record.search_time_ms is not None else 0.0,
            "created_at": record.created_at,
            "username": record.username,
            "feedback_by": record.feedback_by,
            "feedback_score": record.feedback_score,
            "provenance": provenance,
            "files": bundle.get("files") or [],
            "correlationConfidence": bundle.get("correlationConfidence"),
            "correlationReasons": bundle.get("correlationReasons") or [],
            "correlatedSources": bundle.get("correlatedSources") or [],
        })
    return results


@router.delete("/{history_id}")
async def delete_history(
    history_id: int,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    record = (await db.execute(select(AnalysisHistory).filter(
        AnalysisHistory.id == history_id, AnalysisHistory.username == _user,
    ))).scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="History record not found")

    linked_knowledge = (
        await db.execute(
            select(KnowledgeEntry.id).where(KnowledgeEntry.source_history_id == history_id)
        )
    ).scalar_one_or_none()
    if linked_knowledge is not None:
        raise HTTPException(
            status_code=409,
            detail="This incident is retained as knowledge provenance and cannot be deleted",
        )

    await db.delete(record)
    await db.commit()
    return {"message": "Record deleted successfully"}


@router.post("/{history_id}/feedback")
async def submit_feedback(
    history_id: int,
    score: Annotated[int, Query(description="1 for useful, -1 for not useful")],
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[str, Depends(get_current_user)],
):
    """Record usefulness feedback only; it never edits or publishes incident knowledge."""
    if score not in (-1, 1):
        raise HTTPException(status_code=422, detail="Feedback score must be 1 or -1")
    record = (await db.execute(select(AnalysisHistory).filter(
        AnalysisHistory.id == history_id, AnalysisHistory.username == user,
    ))).scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="History record not found")

    record.feedback_score = score
    record.feedback_by = user
    await db.commit()
    return {"message": "Feedback submitted successfully", "score": score}

@router.get("/stats")
async def get_history_stats(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    """Return per-user aggregates without materializing every incident row."""
    metadata = cast(AnalysisHistory.event_metadata, JSONB)
    critical_expr = metadata["isCritical"].astext == "true"
    source_family_expr = metadata["sourceFamily"].astext
    diagnostic_code_expr = metadata["diagnosticCode"].astext
    category_expr = metadata["category"].astext
    device_type_expr = metadata["attributes"]["deviceType"].astext

    metrics = (
        await db.execute(
            select(
                func.count(AnalysisHistory.id),
                func.coalesce(func.sum(case((critical_expr, 1), else_=0)), 0),
                # Average only real analyses: imported rows store 0 ms and must not drag the mean down.
                func.coalesce(func.avg(case((AnalysisHistory.search_time_ms > 0, AnalysisHistory.search_time_ms))), 0.0),
            ).where(AnalysisHistory.username == _user)
        )
    ).one()
    total_logs, critical_errors, average_search_ms = metrics

    provider_expr = func.coalesce(AnalysisHistory.provider, "Unknown")
    provider_rows = (
        await db.execute(
            select(provider_expr, func.count(AnalysisHistory.id))
            .where(AnalysisHistory.username == _user)
            .group_by(provider_expr)
            .order_by(func.count(AnalysisHistory.id).desc())
        )
    ).all()
    provider_stats = [{"name": name, "value": count} for name, count in provider_rows]

    category_rows = (
        await db.execute(
            select(
                AnalysisHistory.event_id,
                AnalysisHistory.provider,
                source_family_expr,
                diagnostic_code_expr,
                category_expr,
                device_type_expr,
                func.count(AnalysisHistory.id),
            )
            .where(AnalysisHistory.username == _user)
            .group_by(
                AnalysisHistory.event_id,
                AnalysisHistory.provider,
                source_family_expr,
                diagnostic_code_expr,
                category_expr,
                device_type_expr,
            )
        )
    ).all()

    from backend.domain.analyzer.services.operational_catalog import (
        entry_for_metadata,
        get_catalog_entry,
    )

    event_categories = {
        "4625": "Authentication",
        "4624": "Authentication",
        "1102": "Security",
        "4672": "Security",
        "4688": "Process & Execution",
        "1001": "Application",
        "1000": "Application",
        "7036": "System",
        "6008": "System",
        "41": "System",
        "2004": "Windows Update",
        "4720": "Account Management",
        "4740": "Account Management",
        "5152": "Firewall & Network Security",
        "1116": "Windows Defender",
        "4104": "PowerShell",
        "7045": "System",
    }
    category_counts: dict[str, int] = {}
    for event_id, provider, source_family, diagnostic_code, category_override, device_type, count in category_rows:
        eid = str(event_id or "").strip()
        prov = str(provider or "").strip()
        original_family = str(source_family or "")
        family = original_family
        if not family:
            family = "windows_event" if prov.lower() == "security" or any(
                word in prov.lower()
                for word in (
                    "windows", "grouppolicy", "kernel-power", "eventlog",
                    "distributedcom", "service control manager",
                )
            ) else "unknown_text"

        if eid.upper().startswith("AINC-") or "incident" in prov.lower():
            category = "Incident Investigation"
        elif category_override:
            category = str(category_override)
        elif family == "windows_event" and eid in event_categories:
            category = event_categories[eid]
        else:
            metadata_model = EventMetadata(
                eventId=eid or "Unknown",
                provider=prov or "Unknown",
                sourceFamily=original_family,
                diagnosticCode=str(diagnostic_code or eid),
                attributes={"deviceType": device_type} if device_type else {},
            )
            catalog_entry = (
                entry_for_metadata(metadata_model)
                if original_family
                else get_catalog_entry(eid, family)
            )
            if catalog_entry and catalog_entry.get("category"):
                raw_category = catalog_entry["category"]
                if "Audit" in raw_category:
                    category = "Security"
                elif "Services" in raw_category:
                    category = "System"
                else:
                    category = raw_category
            else:
                category = "System" if family == "windows_event" else "Unclassified"
        category_counts[category] = category_counts.get(category, 0) + int(count)

    category_stats = [
        {"name": name, "value": count}
        for name, count in sorted(category_counts.items(), key=lambda item: item[1], reverse=True)
    ]

    today = datetime.now(UTC).date()
    first_day = today - timedelta(days=6)
    day_expr = cast(AnalysisHistory.created_at, Date)
    daily_rows = (
        await db.execute(
            select(day_expr, func.count(AnalysisHistory.id))
            .where(
                AnalysisHistory.username == _user,
                day_expr.is_not(None),
                day_expr >= first_day,
            )
            .group_by(day_expr)
            .order_by(day_expr)
        )
    ).all()
    daily_counts = {
        day.strftime("%m/%d"): count
        for day, count in daily_rows
        if day is not None
    }
    last_7_days = [
        (today - timedelta(days=days)).strftime("%m/%d")
        for days in range(6, -1, -1)
    ]

    return {
        "totalLogs": int(total_logs or 0),
        "criticalErrors": int(critical_errors or 0),
        "avgSearchTimeSec": round(float(average_search_ms or 0.0) / 1000, 2),
        "dailyTrends": [
            {"date": day, "count": daily_counts.get(day, 0)}
            for day in last_7_days
        ],
        "categoryStats": category_stats,
        "providerStats": provider_stats,
    }
