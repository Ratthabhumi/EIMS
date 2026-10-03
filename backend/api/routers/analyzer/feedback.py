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
            from backend.domain.analyzer.services.bundle import derive_bundle_semantic_document_from_metadata
            desc_to_sync = history_item.description
            em = history_item.event_metadata if isinstance(history_item.event_metadata, dict) else {}
            attrs = em.get("attributes") if isinstance(em.get("attributes"), dict) else {}
            if "bundle" in attrs or (history_item.parse_method and "bundle" in str(history_item.parse_method).lower()):
                desc_to_sync = derive_bundle_semantic_document_from_metadata(em, history_item.solution_summary or {})

            source_fam = em.get("sourceFamily")
            diag_id = em.get("diagnosticCode") or history_item.event_id
            await add_solution(
                db=db,
                event_id=history_item.event_id,
                description=desc_to_sync,
                solution_summary=history_item.solution_summary,
                feedback_score=req.score,
                api_key=x_gemini_api_key,
                source_family=source_fam,
                diagnostic_identity=diag_id,
            )
        except Exception as e:
            print(f"Failed to add to vector DB: {e}")
            
    return {"status": "success", "message": "Feedback recorded."}
