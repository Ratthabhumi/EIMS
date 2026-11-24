"""Knowledge governance persistence (sparse overlay + append-only history).

Canonical *content* stays in the JSON catalogs. This module stores only
governance state, keyed by the loader's stable ``catalog_id`` — no content copy.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database import Base

LIFECYCLE_STATES = (
    "candidate",
    "source_verified",
    "validated",
    "approved",
    "rejected",
    "deprecated",
    "superseded",
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _sql_in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


class KnowledgeReview(Base):
    """Latest effective governance state for one catalog record.

    Sparse: a row exists only when a record actually needs governance state.
    Records without a row fall back to their canonical classification
    (``operational_context`` -> not applicable, ``diagnostic_candidate`` ->
    candidate).
    """
    __tablename__ = "knowledge_review"

    catalog_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    catalog_source: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="candidate"
    )
    product_version_scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    concurrency_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_catalog_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            f"lifecycle_status IN ({_sql_in_list(LIFECYCLE_STATES)})",
            name="ck_knowledge_review_lifecycle_valid",
        ),
        CheckConstraint("revision >= 1", name="ck_knowledge_review_revision_positive"),
        Index("ix_knowledge_review_lifecycle", "lifecycle_status"),
        Index("ix_knowledge_review_review_required", "review_required"),
        {"comment": "Sparse governance state; content stays in the JSON catalogs."},
    )


class KnowledgeReviewEvent(Base):
    """Append-only decision history (protected by a PostgreSQL trigger)."""
    __tablename__ = "knowledge_review_event"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    catalog_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    evidence: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            f"to_status IN ({_sql_in_list(LIFECYCLE_STATES)})",
            name="ck_knowledge_review_event_to_status_valid",
        ),
        Index("ix_knowledge_review_event_catalog_time", "catalog_id", "created_at"),
        {"comment": "Append-only knowledge decisions; UPDATE/DELETE blocked."},
    )
