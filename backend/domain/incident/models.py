"""
==============================================================================
EIMS Incident Core Domain ORM Models (v1)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 4 Compliance
Source-Available All Rights Reserved Policy
==============================================================================

Additive incident correlation surface. The incident record stores only
identity, correlation confidence and a bounded summary. Raw source payloads
(analysis text, EVTX XML, telemetry diagnostics) are never copied here; each
piece of evidence is referenced by (source_type, source_id) plus a digest.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, List, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infrastructure.database import Base


def _utcnow() -> datetime:
    """Returns an accurate timezone-aware UTC timestamp."""
    return datetime.now(UTC)


INCIDENT_STATUSES = ("open", "triage", "investigating", "resolved", "closed")
INCIDENT_SEVERITIES = ("info", "low", "medium", "high", "critical")
INCIDENT_CONFIDENCES = ("strong", "medium", "weak", "none")
INCIDENT_ROOT_CAUSE_STATES = ("unknown", "hypothesis", "confirmed")
INCIDENT_SOURCE_TYPES = ("analysis", "winlog", "telemetry", "audit")
VERIFICATION_OUTCOMES = ("passed", "failed")


def _sql_in_list(values: tuple[str, ...]) -> str:
    """Builds a deterministic SQL IN literal for CheckConstraints."""
    return ", ".join(f"'{value}'" for value in values)


class Incident(Base):
    """Correlated operational incident derived from bounded evidence references.

    Confidence describes correlation strength only. It is never a claim of
    causality: `root_cause_state` stays 'unknown' until a human or an explicit
    authorised API action records a hypothesis or confirmation.
    """
    __tablename__ = "incidents"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Universally unique incident identifier.",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable incident title (no raw evidence payload).",
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="open",
        doc="Lifecycle state: open, triage, investigating, resolved, closed.",
    )
    severity: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="medium",
        doc="Operational severity: info, low, medium, high, critical.",
    )
    confidence: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="none",
        doc="Correlation confidence: strong, medium, weak, none. Not causality.",
    )
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("infrastructure_assets.asset_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        doc="Resolved infrastructure asset, or NULL while asset identity is unresolved.",
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        doc="Earliest observed evidence timestamp (UTC).",
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        doc="Latest observed evidence timestamp (UTC).",
    )
    dedupe_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        doc="Deterministic SHA-256 of asset-or-unresolved, signature and window bucket.",
    )
    root_cause_state: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="unknown",
        doc="unknown, hypothesis or confirmed. Never set automatically to causality.",
    )
    owner: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Accountable operator username, if assigned.",
    )
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Bounded correlation summary {confidence, reasons, sources}; no raw evidence.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        doc="Record creation timestamp (UTC).",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        doc="Most recent mutation timestamp (UTC).",
    )
    remediation_cycle: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc=(
            "Monotonic remediation cycle. Incremented exactly once when a resolved "
            "incident is reopened into investigating; verification evidence and "
            "verification records are bound to this number."
        ),
    )
    remediation_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("now()"),
        doc=(
            "Start of the current remediation cycle (UTC). Evidence attached before "
            "this instant cannot verify the current cycle."
        ),
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_sql_in_list(INCIDENT_STATUSES)})",
            name="ck_incident_status_valid",
        ),
        CheckConstraint(
            f"severity IN ({_sql_in_list(INCIDENT_SEVERITIES)})",
            name="ck_incident_severity_valid",
        ),
        CheckConstraint(
            f"confidence IN ({_sql_in_list(INCIDENT_CONFIDENCES)})",
            name="ck_incident_confidence_valid",
        ),
        CheckConstraint(
            f"root_cause_state IN ({_sql_in_list(INCIDENT_ROOT_CAUSE_STATES)})",
            name="ck_incident_root_cause_state_valid",
        ),
        CheckConstraint(
            "last_seen >= first_seen",
            name="ck_incident_seen_window_ordered",
        ),
        Index("ix_incidents_status_last_seen", "status", "last_seen"),
        Index("ix_incidents_severity_last_seen", "severity", "last_seen"),
        {"comment": "Correlated incidents; evidence is referenced, not copied."},
    )

    evidence: Mapped[List["IncidentEvidence"]] = relationship(
        "IncidentEvidence",
        back_populates="incident",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class IncidentEvidence(Base):
    """Reference-only binding between an incident and one source record.

    The unique (source_type, source_id) pair makes evidence attachment
    idempotent and prevents the same source event from being counted twice.
    """
    __tablename__ = "incident_evidence"

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Universally unique evidence binding identifier.",
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Parent incident owning this evidence reference.",
    )
    source_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        doc="Evidence origin: analysis, winlog, telemetry, audit.",
    )
    source_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Source record identifier (e.g. analysis_history.id or winlog log_id).",
    )
    source_event_key: Mapped[Optional[str]] = mapped_column(
        String(160),
        nullable=True,
        doc="Optional upstream event key used for signature derivation.",
    )
    evidence_digest: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="SHA-256 digest of the source identity; never the payload itself.",
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="Timestamp at which the referenced source event was observed (UTC).",
    )
    added_by: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Authenticated username that attached this evidence reference.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        doc="Evidence binding creation timestamp (UTC).",
    )

    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_id",
            name="uq_incident_evidence_source",
        ),
        CheckConstraint(
            f"source_type IN ({_sql_in_list(INCIDENT_SOURCE_TYPES)})",
            name="ck_incident_evidence_source_type_valid",
        ),
        Index("ix_incident_evidence_observed_at", "observed_at"),
        {"comment": "Reference-only incident evidence; no copied source payloads."},
    )

    incident: Mapped["Incident"] = relationship("Incident", back_populates="evidence")


class IncidentVerification(Base):
    """Append-only proof that a remediation cycle was verified from evidence.

    A row is written only after the server has revalidated the referenced
    evidence against trusted persistence for the incident's *current*
    remediation cycle. The caller cannot submit an outcome or a verifier id:
    those are derived from the authenticated principal and the server-side
    evaluation. History is never deleted; reopening starts a new cycle and the
    old rows simply stop matching ``incidents.remediation_cycle``.
    """
    __tablename__ = "incident_verification"

    verification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Universally unique verification record identifier.",
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Incident this verification belongs to. RESTRICT preserves history.",
    )
    remediation_cycle: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Remediation cycle of the incident at verification time.",
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incident_evidence.evidence_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Persisted evidence reference that was verified.",
    )
    evidence_digest: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Digest recomputed server-side from the trusted evidence row.",
    )
    outcome: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        doc="Verification outcome: passed or failed.",
    )
    verifier_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Authenticated principal that authorised the verification.",
    )
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        doc="Verification timestamp (UTC).",
    )

    __table_args__ = (
        UniqueConstraint(
            "incident_id",
            "remediation_cycle",
            "evidence_id",
            name="uq_incident_verification_cycle_evidence",
        ),
        CheckConstraint(
            f"outcome IN ({_sql_in_list(VERIFICATION_OUTCOMES)})",
            name="ck_incident_verification_outcome_valid",
        ),
        CheckConstraint(
            "remediation_cycle >= 0",
            name="ck_incident_verification_cycle_non_negative",
        ),
        Index(
            "ix_incident_verification_incident_cycle",
            "incident_id",
            "remediation_cycle",
        ),
        {"comment": "Append-only verified-remediation records bound to one cycle."},
    )
