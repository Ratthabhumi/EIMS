from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
import uuid

class ServiceSessionCreate(BaseModel):
    title: str = Field(..., max_length=255, description="Brief title of the service provided")
    description: Optional[str] = Field(None, description="Detailed description of the service")
    customer_name: Optional[str] = Field(None, max_length=255, description="Name of the customer/employee receiving service")
    engineer_name: Optional[str] = Field(None, max_length=255, description="Name of the IT engineer who provided the service")

class ServiceSessionResponse(BaseModel):
    session_id: uuid.UUID
    title: str
    description: Optional[str]
    customer_name: Optional[str]
    engineer_name: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    
    # We will compute the evaluation link on the fly, but for now just returning the raw data
    model_config = ConfigDict(from_attributes=True)

class ServiceEvaluationSubmit(BaseModel):
    rating_score: int = Field(..., ge=1, le=5, description="Star rating from 1 to 5")
    feedback_comments: Optional[str] = Field(None, description="Optional text feedback from the customer")

class ServiceEvaluationResponse(BaseModel):
    evaluation_id: uuid.UUID
    session_id: uuid.UUID
    rating_score: int
    feedback_comments: Optional[str]
    submitted_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
