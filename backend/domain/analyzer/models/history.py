from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Index, Integer, String, desc
from sqlalchemy.dialects.postgresql import UUID

from backend.infrastructure.database import Base


class AnalysisHistory(Base):
    __tablename__ = "analysis_history"
    __table_args__ = (
        Index("ix_analysis_history_username_created_at_id", "username", desc("created_at"), desc("id")),
    )

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
    # Optional, additive identity link to the asset registry. Never backfilled
    # from computer-name heuristics: unresolved stays NULL until evidence
    # explicitly supplies a resolved asset_id.
    asset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("infrastructure_assets.asset_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    # Legacy column is TIMESTAMP WITHOUT TIME ZONE; persist UTC-naive values explicitly.
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
