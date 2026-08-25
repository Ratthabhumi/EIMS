from sqlalchemy.future import select
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel

from backend.infrastructure.database import get_db_session as get_db
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.services.vector_db import add_solution

from backend.domain.analyzer.auth import get_current_user

router = APIRouter()

class FeedbackRequest(BaseModel):
    history_id: int
    score: int  # 1 for thumb up, -1 for thumb down
    corrected_solution: Optional[dict] = None

@router.post("/feedback")
async def submit_feedback(
    req: FeedbackRequest, 
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
    x_gemini_api_key: Optional[str] = Header(None)
):
    history_item = (await db.execute(select(AnalysisHistory).filter(AnalysisHistory.id == req.history_id))).scalars().first()
    if not history_item:
        raise HTTPException(status_code=404, detail="History not found")
        
    history_item.feedback_score = req.score
    history_item.feedback_by = _user
    
    # If the user provides a corrected solution, overwrite it
    if req.corrected_solution:
        history_item.solution_summary = req.corrected_solution
        
    await db.commit()
    
    # Add to RAG vector DB if positive
    if req.score > 0 and history_item.solution_summary:
        try:
            add_solution(
                db=db,
                event_id=history_item.event_id,
                description=history_item.description,
                solution_summary=history_item.solution_summary,
                feedback_score=req.score,
                api_key=x_gemini_api_key
            )
        except Exception as e:
            print(f"Failed to add to vector DB: {e}")
            
    return {"status": "success", "message": "Feedback recorded."}
