from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.analyzer.auth import get_current_user
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.infrastructure.database import get_db_session as get_db

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]
AuthenticatedUser = Annotated[str, Depends(get_current_user)]


class FeedbackRequest(BaseModel):
    history_id: int
    score: Literal[-1, 1]


@router.post("/feedback")
async def submit_feedback(
    req: FeedbackRequest,
    db: DbSession,
    user: AuthenticatedUser,
):
    """Record usefulness feedback without rewriting or publishing incident knowledge."""
    history_item = (
        await db.execute(
            select(AnalysisHistory).where(
                AnalysisHistory.id == req.history_id,
                AnalysisHistory.username == user,
            )
        )
    ).scalars().first()
    if history_item is None:
        raise HTTPException(status_code=404, detail="History not found")

    history_item.feedback_score = req.score
    history_item.feedback_by = user
    await db.commit()
    return {"status": "success", "message": "Feedback recorded."}
