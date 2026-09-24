from sqlalchemy.future import select
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from backend.domain.analyzer.auth import get_current_user

from backend.infrastructure.database import get_db_session as get_db
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.schemas.history import HistoryResponse
from backend.domain.analyzer.schemas.analyze import SolutionSummary, EventMetadata

router = APIRouter()


@router.get("/catalog")
async def get_operational_catalog(
    _user: str = Depends(get_current_user),
):
    """Return the static Operational Event Catalog (knowledge, not analyzed logs)."""
    from backend.domain.analyzer.services.operational_catalog import get_catalog
    return {
        "classification": "OPERATIONAL_EVENT_CATALOG",
        "count": len(get_catalog()),
        "entries": get_catalog(),
    }


@router.get("/", response_model=List[HistoryResponse])
async def get_all_history(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
    asset_id: Optional[str] = None,
):
    stmt = select(AnalysisHistory)
    if asset_id:
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
        stmt = stmt.filter(
            cast(AnalysisHistory.event_metadata, PGJSONB)["asset_id"].astext == asset_id
        )
    history_records = (await db.execute(stmt.order_by(AnalysisHistory.created_at.desc()))).scalars().all()
    results = []
    for record in history_records:
        solution = SolutionSummary(**record.solution_summary) if record.solution_summary else None
        metadata = EventMetadata(**record.event_metadata) if record.event_metadata else None
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
        results.append({
            "id": record.id,
            "eventId": record.event_id,
            "provider": record.provider,
            "parseMethod": record.parse_method,
            "description": record.description,
            "aiSummary": record.ai_summary,
            "solutionSummary": solution,
            "eventMetadata": metadata,
            "searchResults": record.search_results or [],
            "searchTimeMs": record.search_time_ms if record.search_time_ms is not None else 0.0,
            "created_at": record.created_at,
            "username": record.username,
            "feedback_by": record.feedback_by,
            "feedback_score": record.feedback_score,
            "provenance": provenance,
        })
    return results


@router.delete("/{history_id}")
async def delete_history(
    history_id: int,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    record = (await db.execute(select(AnalysisHistory).filter(AnalysisHistory.id == history_id))).scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="History record not found")
        
    await db.delete(record)
    await db.commit()
    return {"message": "Record deleted successfully"}


@router.post("/{history_id}/feedback")
async def submit_feedback(
    history_id: int,
    score: int, # 1 for Thumbs Up, -1 for Thumbs Down
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Update feedback score in history and synchronizes score in Vector Knowledge DB."""
    record = (await db.execute(select(AnalysisHistory).filter(AnalysisHistory.id == history_id))).scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="History record not found")
        
    record.feedback_score = score
    record.feedback_by = user
    await db.commit()

    # Sync with Vector DB if available
    try:
        from backend.domain.analyzer.services.vector_db import add_solution
        await add_solution(
            db=db,
            event_id=record.event_id,
            description=record.description,
            solution_summary=record.solution_summary,
            feedback_score=score,
        )
    except Exception as e:
        print(f"Failed to update Vector DB feedback: {e}")

    return {"message": "Feedback submitted successfully", "score": score}

@router.get("/stats")
async def get_history_stats(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    history_records = (await db.execute(select(AnalysisHistory).order_by(AnalysisHistory.created_at.asc()))).scalars().all()
    
    total_logs = len(history_records)
    critical_errors = 0
    total_search_time = 0
    
    provider_counts = {}
    category_counts = {}
    daily_counts = {}
    
    import datetime
    from backend.domain.analyzer.services.operational_catalog import get_catalog_entry

    EVENT_CATEGORIES = {
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
    
    for record in history_records:
        # Critical Errors
        if record.event_metadata and record.event_metadata.get("isCritical", False):
            critical_errors += 1
            
        # Search Time
        total_search_time += (record.search_time_ms or 0)
        
        # Provider Stats
        provider = record.provider or "Unknown"
        provider_counts[provider] = provider_counts.get(provider, 0) + 1
        
        # Category Classification (derive from real records and event semantics)
        eid = str(record.event_id or "").strip()
        prov = str(record.provider or "").strip()
        if eid.upper().startswith("AINC-") or "incident" in prov.lower():
            cat = "Incident Investigation"
        elif record.event_metadata and record.event_metadata.get("category"):
            cat = record.event_metadata["category"]
        elif eid in EVENT_CATEGORIES:
            cat = EVENT_CATEGORIES[eid]
        else:
            cat_entry = get_catalog_entry(eid)
            if cat_entry and cat_entry.get("category"):
                cat_raw = cat_entry["category"]
                if "Audit" in cat_raw:
                    cat = "Security"
                elif "Services" in cat_raw:
                    cat = "System"
                else:
                    cat = cat_raw
            else:
                cat = "System"
        category_counts[cat] = category_counts.get(cat, 0) + 1

        # Daily Trends
        if record.created_at:
            day_str = record.created_at.strftime("%m/%d")
            daily_counts[day_str] = daily_counts.get(day_str, 0) + 1
            
    avg_search_time = (total_search_time / total_logs / 1000) if total_logs > 0 else 0
    
    provider_stats = [{"name": k, "value": v} for k, v in provider_counts.items()]
    category_stats = [{"name": k, "value": v} for k, v in category_counts.items()]
    category_stats.sort(key=lambda x: x["value"], reverse=True)
    
    # Exactly last 7 calendar days (ending today)
    today = datetime.datetime.now()
    last_7_days = [(today - datetime.timedelta(days=i)).strftime("%m/%d") for i in range(6, -1, -1)]
    daily_trends = [{"date": d_str, "count": daily_counts.get(d_str, 0)} for d_str in last_7_days]
    
    return {
        "totalLogs": total_logs,
        "criticalErrors": critical_errors,
        "avgSearchTimeSec": round(avg_search_time, 2),
        "dailyTrends": daily_trends,
        "categoryStats": category_stats,
        "providerStats": provider_stats
    }
