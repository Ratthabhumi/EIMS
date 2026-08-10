from sqlalchemy import Column, Integer, String, DateTime, JSON, Float
from app.core.database import Base
from datetime import datetime

class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, index=True)
    provider = Column(String, index=True)
    parse_method = Column(String)
    description = Column(String)
    ai_summary = Column(String)
    solution_summary = Column(JSON, nullable=True)
    event_metadata = Column(JSON, nullable=True)
    search_results = Column(JSON)
    search_time_ms = Column(Float, default=0.0)
    feedback_score = Column(Integer, default=0)
    username = Column(String, default="admin")
    feedback_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
