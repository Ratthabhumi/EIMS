from sqlalchemy.future import select
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from backend.domain.analyzer.auth import get_current_user

from backend.infrastructure.database import get_db_session as get_db
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.schemas.history import HistoryResponse
from backend.domain.analyzer.schemas.analyze import SolutionSummary, EventMetadata

router = APIRouter()


@router.get("/", response_model=List[HistoryResponse])
async def get_all_history(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    history_records = (await db.execute(select(AnalysisHistory).order_by(AnalysisHistory.created_at.desc()))).scalars().all()
    results = []
    for record in history_records:
        solution = SolutionSummary(**record.solution_summary) if record.solution_summary else None
        metadata = EventMetadata(**record.event_metadata) if record.event_metadata else None
        results.append({
            "id": record.id,
            "eventId": record.event_id,
            "provider": record.provider,
            "parseMethod": record.parse_method,
            "description": record.description,
            "aiSummary": record.ai_summary,
            "solutionSummary": solution,
            "eventMetadata": metadata,
            "searchResults": record.search_results,
            "searchTimeMs": record.search_time_ms,
            "created_at": record.created_at,
            "username": record.username,
            "feedback_by": record.feedback_by,
            "feedback_score": record.feedback_score,
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
    daily_counts = {}
    
    import datetime
    
    for record in history_records:
        # Critical Errors
        if record.event_metadata and record.event_metadata.get("isCritical", False):
            critical_errors += 1
            
        # Search Time
        total_search_time += (record.search_time_ms or 0)
        
        # Provider Stats
        provider = record.provider or "Unknown"
        provider_counts[provider] = provider_counts.get(provider, 0) + 1
        
        # Daily Trends
        if record.created_at:
            day_str = record.created_at.strftime("%m/%d")
            daily_counts[day_str] = daily_counts.get(day_str, 0) + 1
            
    avg_search_time = (total_search_time / total_logs / 1000) if total_logs > 0 else 0
    
    provider_stats = [{"name": k, "value": v} for k, v in provider_counts.items()]
    daily_trends = [{"date": k, "count": v} for k, v in daily_counts.items()]
    
    # Fill missing days for the last 7 days
    today = datetime.datetime.now()
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        d_str = d.strftime("%m/%d")
        if not any(t["date"] == d_str for t in daily_trends):
            daily_trends.append({"date": d_str, "count": 0})
    
    daily_trends.sort(key=lambda x: x["date"])
    
    return {
        "totalLogs": total_logs,
        "criticalErrors": critical_errors,
        "avgSearchTimeSec": round(avg_search_time, 2),
        "dailyTrends": daily_trends,
        "providerStats": provider_stats
    }
