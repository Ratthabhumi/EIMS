"""Incident diagnosis / remediation records (additive to the Incident Core).

Records carry an explicit ``actor_assurance`` so an audit reader can tell an
unproven open-access actor from a verified reviewer. Nothing here records
*verification*: that remains ``incident_verification`` and its guards.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database import Base

ACTOR_ASSURANCES = ("unattributed", "shared-token", "verified-identity")
DIAGNOSIS_STATES = ("hypothesis", "confirmed", "rejected", "superseded")
REMEDIATION_STATES = ("proposed", "executed")
EXECUTION_OUTCOMES = ("succeeded", "failed", "partial", "rolled_back")
STATED_CONFIDENCES = ("low", "medium", "high")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


class IncidentDiagnosis(Base):
    __tablename__ = "incident_diagnosis"

    diagnosis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="RESTRICT"), nullable=False)
    remediation_cycle: Mapped[int] = mapped_column(Integer, nullable=False)
    hypothesis: Mapped[str] = mapped_column(String(1000), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    stated_confidence: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="hypothesis", server_default="hypothesis")
    supporting_evidence_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    contradicting_evidence_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    knowledge: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    analysis_history_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    proposed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    proposed_assurance: Mapped[str] = mapped_column(String(24), nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    confirmed_assurance: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    closed_assurance: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    superseded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incident_diagnosis.diagnosis_id", ondelete="RESTRICT"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint(f"status IN ({_in(DIAGNOSIS_STATES)})", name="ck_incident_diagnosis_status"),
        CheckConstraint(f"stated_confidence IN ({_in(STATED_CONFIDENCES)})", name="ck_incident_diagnosis_confidence"),
        CheckConstraint(f"proposed_assurance IN ({_in(ACTOR_ASSURANCES)})",
                        name="ck_incident_diagnosis_proposed_assurance"),
        CheckConstraint("confirmed_assurance IS NULL OR confirmed_assurance = 'verified-identity'",
                        name="ck_incident_diagnosis_confirmed_assurance"),
        CheckConstraint(
            "(status = 'confirmed') = COALESCE(confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmed_assurance = 'verified-identity', false)",
            name="ck_incident_diagnosis_confirmation_consistent"),
        CheckConstraint("confirmed_by IS NULL OR confirmed_by <> proposed_by",
                        name="ck_incident_diagnosis_confirmer_not_proposer"),
        CheckConstraint(
            "(status IN ('rejected', 'superseded')) = COALESCE(closed_by IS NOT NULL AND closed_at IS NOT NULL "
            "AND closed_reason IS NOT NULL AND closed_assurance IS NOT NULL, false)",
            name="ck_incident_diagnosis_closure_consistent"),
        CheckConstraint(
            "status IN ('rejected', 'superseded') OR (closed_by IS NULL AND closed_at IS NULL AND closed_reason IS NULL AND closed_assurance IS NULL AND superseded_by_id IS NULL)",
            name="ck_incident_diagnosis_closed_fields_only_when_closed"),
        CheckConstraint(
            "status = 'confirmed' OR (confirmed_by IS NULL AND confirmed_at IS NULL AND confirmed_assurance IS NULL)",
            name="ck_incident_diagnosis_confirmed_fields_only_when_confirmed"),
        CheckConstraint(f"closed_assurance IS NULL OR closed_assurance IN ({_in(ACTOR_ASSURANCES)})",
                        name="ck_incident_diagnosis_closed_assurance"),
        CheckConstraint(
            "(status = 'superseded') = (superseded_by_id IS NOT NULL) AND superseded_by_id IS DISTINCT FROM diagnosis_id",
            name="ck_incident_diagnosis_superseded_link"),
        Index("ix_incident_diagnosis_incident", "incident_id", "created_at"),
        Index("uq_incident_diagnosis_one_confirmed_per_cycle", "incident_id", "remediation_cycle",
              unique=True, postgresql_where=text("status = 'confirmed'")),
        {"comment": "Root-cause hypotheses; 'confirmed' requires a verified-identity reviewer."},
    )


class IncidentRemediation(Base):
    __tablename__ = "incident_remediation"

    remediation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="RESTRICT"), nullable=False)
    diagnosis_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incident_diagnosis.diagnosis_id", ondelete="RESTRICT"), nullable=True)
    remediation_cycle: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(1000), nullable=False)
    preconditions: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    affected_components: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    expected_outcome: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    risk: Mapped[str] = mapped_column(Text, nullable=False)
    impact: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    rollback_plan: Mapped[str] = mapped_column(Text, nullable=False)
    expected_verification_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed", server_default="proposed")
    proposed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    proposed_assurance: Mapped[str] = mapped_column(String(24), nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    executed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    executed_assurance: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    outcome_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    catalog_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    knowledge: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    execution_evidence_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint(f"status IN ({_in(REMEDIATION_STATES)})", name="ck_incident_remediation_status"),
        CheckConstraint(f"proposed_assurance IN ({_in(ACTOR_ASSURANCES)})",
                        name="ck_incident_remediation_proposed_assurance"),
        CheckConstraint(f"executed_assurance IS NULL OR executed_assurance IN ({_in(ACTOR_ASSURANCES)})",
                        name="ck_incident_remediation_executed_assurance"),
        CheckConstraint(f"outcome IS NULL OR outcome IN ({_in(EXECUTION_OUTCOMES)})",
                        name="ck_incident_remediation_outcome"),
        CheckConstraint(
            "(status = 'executed') = (executed_by IS NOT NULL AND executed_at IS NOT NULL "
            "AND outcome IS NOT NULL AND executed_assurance IS NOT NULL)",
            name="ck_incident_remediation_execution_consistent"),
        Index("ix_incident_remediation_incident", "incident_id", "created_at"),
        {"comment": "Proposed vs executed remediation; never records verification."},
    )


class IncidentWorkflowEvent(Base):
    """Append-only audit (protected by a PostgreSQL trigger)."""
    __tablename__ = "incident_workflow_event"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="RESTRICT"), nullable=False)
    record_type: Mapped[str] = mapped_column(String(16), nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_assurance: Mapped[str] = mapped_column(String(24), nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("record_type IN ('diagnosis', 'remediation', 'note')", name="ck_incident_workflow_event_type"),
        CheckConstraint(f"actor_assurance IN ({_in(ACTOR_ASSURANCES)})", name="ck_incident_workflow_event_assurance"),
        Index("ix_incident_workflow_event_incident", "incident_id", "created_at"),
        Index("ix_incident_workflow_event_record", "record_id"),
        {"comment": "Append-only audit of diagnosis/remediation operations with actor assurance."},
    )


class IncidentNote(Base):
    """Engineer observation. Append-only (trigger); carries no state, so it can never confirm, verify or resolve."""
    __tablename__ = "incident_note"

    note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_assurance: Mapped[str] = mapped_column(String(24), nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("char_length(btrim(body)) BETWEEN 1 AND 4000", name="ck_incident_note_body_length"),
        CheckConstraint(f"actor_assurance IN ({_in(ACTOR_ASSURANCES)})", name="ck_incident_note_assurance"),
        Index("ix_incident_note_incident_created", "incident_id", "created_at", "note_id"),
        {"comment": "Append-only engineer observations; never a diagnosis, remediation, verification or status change."},
    )


class IncidentKnowledgeProposal(Base):
    """Which existing Knowledge review entry originated from which incident.

    No catalog content is copied here. The proposal itself lives in the existing
    knowledge_entries review lifecycle and is never promoted by this link.
    """
    __tablename__ = "incident_knowledge_proposal"

    proposal_link_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="RESTRICT"), nullable=False)
    diagnosis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incident_diagnosis.diagnosis_id", ondelete="RESTRICT"), nullable=False)
    remediation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incident_remediation.remediation_id", ondelete="RESTRICT"), nullable=True)
    knowledge_entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_entries.id", ondelete="RESTRICT"), nullable=False)
    remediation_cycle: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    proposed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    proposed_assurance: Mapped[str] = mapped_column(String(24), nullable=False)
    diagnosis_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("knowledge_entry_id", name="uq_incident_knowledge_proposal_entry"),
        CheckConstraint(f"proposed_assurance IN ({_in(ACTOR_ASSURANCES)})",
                        name="ck_incident_knowledge_proposal_assurance"),
        Index("ix_incident_knowledge_proposal_incident", "incident_id", "created_at"),
        {"comment": "Links an incident to the existing Knowledge review entry it originated; no content copy."},
    )
