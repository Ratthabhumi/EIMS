import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Header
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
from backend.core.logger import get_logger

logger = get_logger("eims.evaluations")
router = APIRouter(prefix="/api/v1/evaluations", tags=["Evaluation System"])

async def verify_admin_token(authorization: str | None = Header(None)):
    """Simple authorization for Admin Panel actions"""
    if authorization != "Bearer EIMS-ADMIN-TOKEN":
        logger.warning("Unauthorized attempt to access Admin Evaluation API")
        raise HTTPException(status_code=401, detail="Unauthorized")
    return authorization

DEFAULT_QUESTIONS = [
    {"id": "q1", "label": "ความรวดเร็วในการแก้ไขปัญหา (Resolution Time & Efficiency)", "category": "Support", "orderIndex": 1},
    {"id": "q2", "label": "ความเป็นมืออาชีพและการให้บริการ (Professionalism & Service Quality)", "category": "Support", "orderIndex": 2},
    {"id": "q3", "label": "การแก้ไขปัญหาได้สำเร็จและครบถ้วน (Resolution Quality)", "category": "Support", "orderIndex": 3},
    {"id": "q4", "label": "ความตรงต่อเวลาในการส่งมอบงาน (Punctuality)", "category": "Implement", "orderIndex": 4},
    {"id": "q5", "label": "คุณภาพของการติดตั้งระบบ (Implementation Quality)", "category": "Implement", "orderIndex": 5},
    {"id": "q6", "label": "การถ่ายทอดความรู้และการสอนใช้งาน (Knowledge Transfer)", "category": "Implement", "orderIndex": 6},
    {"id": "q7", "label": "ความพึงพอใจโดยรวมต่อการให้บริการ (Overall Satisfaction)", "category": "General", "orderIndex": 7}
]

@router.post("/sessions", response_model=ServiceSessionResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin_token)])
async def create_service_session(
    session_data: ServiceSessionCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """Creates a new service session that a customer can evaluate later."""
    eval_qs = session_data.evaluation_questions if session_data.evaluation_questions is not None else DEFAULT_QUESTIONS
    
    new_session = ServiceSession(
        title=session_data.title,
        description=session_data.description,
        customer_name=session_data.customer_name,
        engineer_name=session_data.engineer_name,
        evaluation_questions=eval_qs
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return new_session

@router.get("/sessions", response_model=List[ServiceSessionResponse])
async def list_service_sessions(skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db_session)):
    """Returns a list of recent service sessions (used by Admin Dashboard)."""
    result = await db.execute(
        select(ServiceSession).order_by(ServiceSession.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()

@router.get("/sessions/{session_id}", response_model=ServiceSessionResponse)
async def get_service_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db_session)):
    """Retrieves the details of a specific service session (used by public form)."""
    result = await db.execute(select(ServiceSession).where(ServiceSession.session_id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Service session not found")
    return session

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
        
    # Calculate average score
    scores = [item.score for item in evaluation_data.rating_scores]
    avg_score = sum(scores) / len(scores) if len(scores) > 0 else 0.0

    new_evaluation = ServiceEvaluation(
        session_id=session_id,
        responder_name=evaluation_data.responder_name,
        department=evaluation_data.department,
        rating_scores=[item.model_dump() for item in evaluation_data.rating_scores],
        average_score=avg_score,
        feedback_comments=evaluation_data.feedback_comments
    )
    db.add(new_evaluation)
    await db.commit()
    await db.refresh(new_evaluation)
    return new_evaluation

@router.get("/sessions/{session_id}/responses", response_model=List[ServiceEvaluationResponse])
async def get_session_responses(session_id: uuid.UUID, db: AsyncSession = Depends(get_db_session)):
    """Retrieves all evaluations for a specific service session (1-to-N)."""
    result = await db.execute(
        select(ServiceEvaluation)
        .where(ServiceEvaluation.session_id == session_id)
        .order_by(ServiceEvaluation.submitted_at.desc())
    )
    return result.scalars().all()

@router.put("/sessions/{session_id}", response_model=ServiceSessionResponse, dependencies=[Depends(verify_admin_token)])
async def update_service_session(
    session_id: uuid.UUID,
    session_data: ServiceSessionCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """Updates an existing service session."""
    result = await db.execute(select(ServiceSession).where(ServiceSession.session_id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Service session not found")
        
    session.title = session_data.title
    session.description = session_data.description
    session.customer_name = session_data.customer_name
    session.engineer_name = session_data.engineer_name
    if session_data.evaluation_questions is not None:
        session.evaluation_questions = session_data.evaluation_questions
        
    await db.commit()
    await db.refresh(session)
    return session

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verify_admin_token)])
async def delete_service_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Deletes a service session."""
    result = await db.execute(select(ServiceSession).where(ServiceSession.session_id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Service session not found")
        
    await db.delete(session)
    await db.commit()
    return None

@router.delete("/responses/{evaluation_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verify_admin_token)])
async def delete_service_evaluation(
    evaluation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Deletes an individual service evaluation response."""
    result = await db.execute(select(ServiceEvaluation).where(ServiceEvaluation.evaluation_id == evaluation_id))
    evaluation = result.scalars().first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Service evaluation not found")
        
    await db.delete(evaluation)
    await db.commit()
    return None
