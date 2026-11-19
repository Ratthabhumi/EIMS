"""ORM model for the Incident Core v1.1 ingestion outbox (additive; must match migration c4e8a1f7b932)."""
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database import Base

OUTBOX_SOURCE_TYPES = ("analysis", "winlog")
MAX_PROVENANCE_BYTES = 1024


def _utcnow() -> datetime:
    return datetime.now(UTC)


class IncidentIngestOutbox(Base):
    """Transactional outbox: written in the caller's source transaction when the insert succeeds.

    Reference-only. It carries the durable source identity, never raw log text. If the outbox
    insert fails for a reason other than a missing table, the source transaction is failed so
    evidence and intent retry together; a missing table keeps the pre-v1.1 behaviour (source
    evidence commits, the lost intent is logged and counted). Never a cross-transaction
    atomicity claim between source persistence and incident creation.
    """
    __tablename__ = "incident_ingest_outbox"

    outbox_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_event_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("infrastructure_assets.asset_id", ondelete="RESTRICT"),
        nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=text("now()"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("source_type IN ('analysis', 'winlog')", name="ck_incident_ingest_outbox_source_type"),
        CheckConstraint(f"octet_length(provenance::text) <= {MAX_PROVENANCE_BYTES}",
                        name="ck_incident_ingest_outbox_provenance_bounded"),
        UniqueConstraint("source_type", "source_id", name="uq_incident_ingest_outbox_source"),
        Index("idx_incident_ingest_outbox_pending", "created_at",
              postgresql_where=text("published_at IS NULL")),
        {"comment": "Reference-only transactional outbox feeding Incident Core ingestion."},
    )
