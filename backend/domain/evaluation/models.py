import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from backend.infrastructure.database import Base

class ServiceSession(Base):
    """
    Represents an IT or Customer Service session that has occurred,
    which is eligible for a post-service evaluation (Cisco-style survey).
    """
    __tablename__ = "service_sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=True)
    engineer_name: Mapped[str] = mapped_column(String(255), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    
    evaluation_questions: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    
    # 1-to-N relationship to Evaluations
    evaluations: Mapped[list["ServiceEvaluation"]] = relationship(
        "ServiceEvaluation",
        back_populates="session",
        cascade="all, delete-orphan"
    )

class ServiceEvaluation(Base):
    """
    Represents the customer feedback / survey result submitted via QR Code link.
    """
    __tablename__ = "service_evaluations"

    evaluation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("service_sessions.session_id", ondelete="CASCADE"), nullable=False)
    
    responder_name: Mapped[str] = mapped_column(String(255), nullable=True)
    department: Mapped[str] = mapped_column(String(255), nullable=True)
    
    rating_scores: Mapped[list[dict]] = mapped_column(JSONB, nullable=True) # e.g. [{"question_id": "q1", "score": 5}]
    average_score: Mapped[float] = mapped_column(Float, nullable=True)
    
    feedback_comments: Mapped[str] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    session: Mapped["ServiceSession"] = relationship("ServiceSession", back_populates="evaluations")
