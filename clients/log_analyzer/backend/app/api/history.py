from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.auth import get_current_user

from app.core.database import get_db
from app.models.history import AnalysisHistory
from app.schemas.history import HistoryResponse
from app.schemas.analyze import SolutionSummary, EventMetadata

router = APIRouter()


@router.get("/", response_model=List[HistoryResponse])
def get_all_history(
    db: Session = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    history_records = db.query(AnalysisHistory).order_by(AnalysisHistory.created_at.desc()).all()
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
def delete_history(
    history_id: int,
    db: Session = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    record = db.query(AnalysisHistory).filter(AnalysisHistory.id == history_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="History not found")
    db.delete(record)
    db.commit()
    return {"message": "Deleted successfully"}
