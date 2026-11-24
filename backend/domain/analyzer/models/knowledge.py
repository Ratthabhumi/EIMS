from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
    text,
)

from backend.infrastructure.database import Base


class KnowledgeEntry(Base):
    """Curated incident knowledge with explicit human approval before shared reuse."""

    __tablename__ = "knowledge_entries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_knowledge_entries_status",
        ),
        CheckConstraint(
            "resolution_status IN ('resolved', 'partially_resolved', 'unresolved')",
            name="ck_knowledge_entries_resolution_status",
        ),
        CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_knowledge_entries_risk_level",
        ),
        CheckConstraint(
            "lifecycle_state IN ('active', 'revalidation_required', 'superseded', 'withdrawn')",
            name="ck_knowledge_entries_lifecycle_state",
        ),
        CheckConstraint(
            "provider_scope IN ('provider_specific', 'vendor_product', 'generic', 'unknown', 'unverified')",
            name="ck_knowledge_entries_provider_scope",
        ),
        CheckConstraint(
            "provider_scope <> 'provider_specific' OR (provider IS NOT NULL AND length(btrim(provider)) > 0)",
            name="ck_knowledge_entries_provider_specific_needs_provider",
        ),
        Index(
            "ix_knowledge_entries_status_family_identity_reviewed",
            "status",
            "source_family",
            "diagnostic_identity",
            desc("reviewed_at"),
        ),
        UniqueConstraint(
            "source_history_id",
            name="uq_knowledge_entries_source_history_id",
        ),
    )

    id = Column(Integer, primary_key=True)
    source_history_id = Column(
        Integer,
        ForeignKey("analysis_history.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_history_hash = Column(String(64), nullable=False)
    source_family = Column(String(64), nullable=False)
    diagnostic_identity = Column(String(256), nullable=False)
    # Provider scope: legacy rows are 'unknown' and never an exact provider match (see verified_knowledge).
    provider = Column(String(160), nullable=True)
    provider_scope = Column(String(24), nullable=False, default="unknown", server_default="unknown")
    title = Column(String(200), nullable=False)
    resolution_status = Column(String(32), nullable=False)
    root_cause = Column(Text, nullable=False)
    solution_steps = Column(JSON, nullable=False)
    impact = Column(Text, nullable=False, default="", server_default="")
    prevention = Column(Text, nullable=False, default="", server_default="")
    product_name = Column(String(128), nullable=True)
    product_version = Column(String(64), nullable=True)
    environment = Column(String(64), nullable=True)
    prerequisites = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    risk_level = Column(String(16), nullable=False, default="medium", server_default="medium")
    validation_steps = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    rollback_steps = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    evidence_notes = Column(JSON, nullable=False)
    references = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    status = Column(String(16), nullable=False, default="pending", server_default="pending", index=True)
    proposed_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), server_default=func.now())
    reviewed_by = Column(String(128), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_note = Column(Text, nullable=False, default="", server_default="")
    lifecycle_state = Column(String(24), nullable=False, default="active", server_default="active")
    lifecycle_reason = Column(Text, nullable=False, default="", server_default="")
    lifecycle_updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), server_default=func.now())
    superseded_by_id = Column(
        Integer,
        ForeignKey("knowledge_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )


class KnowledgeLifecycleEvent(Base):
    """Append-only audit trail for Knowledge revalidation and retirement decisions."""

    __tablename__ = "knowledge_lifecycle_events"
    __table_args__ = (
        CheckConstraint(
            "to_state IN ('active', 'revalidation_required', 'superseded', 'withdrawn')",
            name="ck_knowledge_lifecycle_events_to_state",
        ),
        Index(
            "ix_knowledge_lifecycle_events_entry_created",
            "knowledge_entry_id",
            desc("created_at"),
        ),
    )

    id = Column(Integer, primary_key=True)
    knowledge_entry_id = Column(
        Integer,
        ForeignKey("knowledge_entries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_state = Column(String(24), nullable=True)
    to_state = Column(String(24), nullable=False)
    action = Column(String(24), nullable=False)
    reason = Column(Text, nullable=False)
    note = Column(Text, nullable=False, default="", server_default="")
    changed_by = Column(String(128), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class KnowledgeUsage(Base):
    """Append-only outcome feedback linking approved knowledge to an owned follow-up incident."""

    __tablename__ = "knowledge_usage"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('resolved', 'partially_resolved', 'not_resolved', 'not_attempted')",
            name="ck_knowledge_usage_outcome",
        ),
        UniqueConstraint(
            "knowledge_entry_id",
            "history_id",
            "reported_by",
            name="uq_knowledge_usage_entry_history_reporter",
        ),
        Index(
            "ix_knowledge_usage_entry_created",
            "knowledge_entry_id",
            desc("created_at"),
        ),
    )

    id = Column(Integer, primary_key=True)
    knowledge_entry_id = Column(
        Integer,
        ForeignKey("knowledge_entries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    history_id = Column(
        Integer,
        ForeignKey("analysis_history.id", ondelete="RESTRICT"),
        nullable=False,
    )
    history_hash = Column(String(64), nullable=False)
    outcome = Column(String(24), nullable=False)
    notes = Column(Text, nullable=False, default="", server_default="")
    reported_by = Column(String(128), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

class KnowledgeSourceCandidate(Base):
    """Vendor/source references awaiting independent domain review; never reusable Knowledge."""

    __tablename__ = "knowledge_source_candidates"
    __table_args__ = (
        CheckConstraint(
            "review_state IN ('pending_domain_review', 'verified_reference', 'rejected', 'revalidation_required', 'withdrawn')",
            name="ck_knowledge_source_candidates_review_state",
        ),
        CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_knowledge_source_candidates_risk_level",
        ),
        UniqueConstraint("source_key", name="uq_knowledge_source_candidates_source_key"),
        Index(
            "ix_knowledge_source_candidates_vendor_state",
            "vendor", "review_state", "product",
        ),
        Index(
            "ix_knowledge_source_candidates_identity",
            "identity", "vendor",
        ),
    )

    id = Column(Integer, primary_key=True)
    source_key = Column(String(128), nullable=False)
    vendor = Column(String(128), nullable=False)
    product = Column(String(200), nullable=False)
    version_scope = Column(String(600), nullable=False)
    domain = Column(String(160), nullable=False)
    identity = Column(String(256), nullable=False)
    title = Column(String(300), nullable=False)
    source_url = Column(String(2048), nullable=False)
    applicability = Column(Text, nullable=False)
    prerequisites = Column(JSON, nullable=False)
    evidence = Column(JSON, nullable=False)
    limitations = Column(JSON, nullable=False)
    next_checks = Column(JSON, nullable=False)
    validation = Column(JSON, nullable=False)
    rollback = Column(JSON, nullable=False)
    risk_level = Column(String(16), nullable=False)
    evidence_status = Column(String(64), nullable=False)
    review_state = Column(String(32), nullable=False, default="pending_domain_review", server_default="pending_domain_review")
    catalog_schema_version = Column(String(32), nullable=False)
    source_hash = Column(String(64), nullable=False)
    source_payload = Column(JSON, nullable=False)
    imported_by = Column(String(128), nullable=False, default="catalogue-import", server_default="catalogue-import")
    imported_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), server_default=func.now())
    reviewed_by = Column(String(128), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_note = Column(Text, nullable=False, default="", server_default="")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), server_default=func.now())


class KnowledgeSourceEvent(Base):
    """Append-only audit history for source import, revision and domain review."""

    __tablename__ = "knowledge_source_events"
    __table_args__ = (
        Index(
            "ix_knowledge_source_events_candidate_created",
            "source_candidate_id", desc("created_at"),
        ),
    )

    id = Column(Integer, primary_key=True)
    source_candidate_id = Column(
        Integer,
        ForeignKey("knowledge_source_candidates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action = Column(String(32), nullable=False)
    from_state = Column(String(32), nullable=True)
    to_state = Column(String(32), nullable=True)
    source_hash = Column(String(64), nullable=False)
    note = Column(Text, nullable=False, default="", server_default="")
    changed_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), server_default=func.now())
