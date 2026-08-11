import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.infrastructure.database import get_db_session
from backend.domain.evaluation.models import ServiceSession, ServiceEvaluation
from backend.domain.evaluation.schemas import (
    ServiceSessionCreate,
    ServiceSessionResponse,
    ServiceEvaluationSubmit,
    ServiceEvaluationResponse
)

router = APIRouter(prefix="/api/v1/evaluations", tags=["Evaluation System"])

@router.post("/sessions", response_model=ServiceSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_service_session(
    session_data: ServiceSessionCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """Creates a new service session that a customer can evaluate later."""
    new_session = ServiceSession(
        title=session_data.title,
        description=session_data.description,
        customer_name=session_data.customer_name,
        engineer_name=session_data.engineer_name
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return new_session

@router.get("/sessions", response_model=List[ServiceSessionResponse])
async def list_service_sessions(db: AsyncSession = Depends(get_db_session), limit: int = 50):
    """Returns a list of recent service sessions (used by Admin Dashboard)."""
    result = await db.execute(
        select(ServiceSession).order_by(ServiceSession.created_at.desc()).limit(limit)
    )
    return result.scalars().all()

@router.post("/sessions/{session_id}/evaluate", response_model=ServiceEvaluationResponse, status_code=status.HTTP_201_CREATED)
async def submit_evaluation(
    session_id: uuid.UUID,
    evaluation_data: ServiceEvaluationSubmit,
    db: AsyncSession = Depends(get_db_session)
):
    """Submits a customer evaluation (star rating and feedback) for a given service session."""
    # Check if session exists
    result = await db.execute(select(ServiceSession).where(ServiceSession.session_id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Service session not found")
        
    # Check if already evaluated
    eval_result = await db.execute(select(ServiceEvaluation).where(ServiceEvaluation.session_id == session_id))
    if eval_result.scalars().first():
        raise HTTPException(status_code=400, detail="This service session has already been evaluated")
        
    new_evaluation = ServiceEvaluation(
        session_id=session_id,
        rating_score=evaluation_data.rating_score,
        feedback_comments=evaluation_data.feedback_comments
    )
    db.add(new_evaluation)
    await db.commit()
    await db.refresh(new_evaluation)
    return new_evaluation

@router.get("/sessions/{session_id}/evaluation", response_model=ServiceEvaluationResponse)
async def get_evaluation(session_id: uuid.UUID, db: AsyncSession = Depends(get_db_session)):
    """Retrieves the evaluation for a specific service session, if any."""
    result = await db.execute(select(ServiceEvaluation).where(ServiceEvaluation.session_id == session_id))
    evaluation = result.scalars().first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found for this session")
    return evaluation
