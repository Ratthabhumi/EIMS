from sqlalchemy import Column, Integer, String, JSON
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class VectorKnowledge(Base):
    __tablename__ = "ai_knowledge"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, index=True)
    description = Column(String)
    embedding = Column(Vector(768)) # Gemini embeddings are 768 dimensions
    solution_json = Column(JSON)
    feedback_score = Column(Integer, default=0)
