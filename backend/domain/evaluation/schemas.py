from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
import uuid

class RatingScore(BaseModel):
    question_id: str
    score: int = Field(..., ge=1, le=5)

class ServiceSessionCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    customer_name: Optional[str] = Field(None, max_length=255)
    engineer_name: Optional[str] = Field(None, max_length=255)
    evaluation_questions: Optional[List[dict]] = Field(None, description="Array of questions for this session")

class ServiceSessionResponse(BaseModel):
    session_id: uuid.UUID
    title: str
    description: Optional[str]
    customer_name: Optional[str]
    engineer_name: Optional[str]
    evaluation_questions: Optional[List[dict]]
    created_at: datetime
    completed_at: Optional[datetime]
    
    # We will compute the evaluation link on the fly, but for now just returning the raw data
    model_config = ConfigDict(from_attributes=True)

class ServiceEvaluationSubmit(BaseModel):
    responder_name: Optional[str] = Field(None, max_length=255, description="Name of the person submitting the evaluation")
    department: Optional[str] = Field(None, max_length=255, description="Department of the person submitting")
    rating_scores: List[RatingScore] = Field(..., description="Array of answers, e.g. [{'question_id': 'q1', 'score': 5}]")
    feedback_comments: Optional[str] = Field(None, description="Optional text feedback from the customer")

class ServiceEvaluationResponse(BaseModel):
    evaluation_id: uuid.UUID
    session_id: uuid.UUID
    responder_name: Optional[str]
    department: Optional[str]
    rating_scores: Optional[List[dict]]
    average_score: Optional[float]
    feedback_comments: Optional[str]
    submitted_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
