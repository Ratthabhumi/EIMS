"""Request/response models for incident diagnosis and remediation.

Requests forbid unknown fields: a client can never supply an actor, an
assurance level, a knowledge classification, a verification state or a digest.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from backend.api.routers.analyzer.knowledge import KnowledgeProposalContent


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DiagnosisCreateRequest(_Request):
    hypothesis: str = Field(..., min_length=1, max_length=1000)
    reasoning: str = Field("", max_length=8000)
    stated_confidence: Literal["low", "medium", "high"] = "low"
    supporting_evidence_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    contradicting_evidence_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    catalog_id: Optional[str] = Field(None, max_length=200)
    analysis_history_id: Optional[int] = Field(None, ge=1)
    detected_version: Optional[str] = Field(None, max_length=64)


class DiagnosisConfirmRequest(_Request):
    rationale: str = Field(..., min_length=1, max_length=4000)


class DiagnosisCloseRequest(_Request):
    reason: str = Field(..., min_length=1, max_length=4000)


class DiagnosisSupersedeRequest(_Request):
    reason: str = Field(..., min_length=1, max_length=4000)
    superseded_by_id: uuid.UUID


class IncidentKnowledgeProposalRequest(_Request):
    """Caller-authored proposal content; nothing is copied automatically from the incident."""
    diagnosis_id: uuid.UUID
    remediation_id: Optional[uuid.UUID] = None
    evidence_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    proposal: KnowledgeProposalContent


class RemediationCreateRequest(_Request):
    action: str = Field(..., min_length=1, max_length=1000)
    risk: str = Field(..., min_length=1, max_length=4000)
    rollback_plan: str = Field(..., min_length=1, max_length=4000)
    expected_verification_criteria: str = Field(..., min_length=1, max_length=4000)
    impact: str = Field("", max_length=4000)
    expected_outcome: str = Field("", max_length=4000)
    preconditions: list[Annotated[str, StringConstraints(max_length=500)]] = Field(
        default_factory=list, max_length=20)
    affected_components: list[Annotated[str, StringConstraints(max_length=500)]] = Field(
        default_factory=list, max_length=50)
    diagnosis_id: Optional[uuid.UUID] = None
    catalog_id: Optional[str] = Field(None, max_length=200)
    detected_version: Optional[str] = Field(None, max_length=64)


class RemediationExecutionRequest(_Request):
    actual_action: str = Field(..., min_length=1, max_length=4000)
    outcome: Literal["succeeded", "failed", "partial", "rolled_back"]
    outcome_notes: str = Field("", max_length=4000)
    evidence_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class DiagnosisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    diagnosis_id: uuid.UUID
    incident_id: uuid.UUID
    remediation_cycle: int
    hypothesis: str
    reasoning: str
    stated_confidence: str
    status: str
    supporting_evidence_ids: list[Any]
    contradicting_evidence_ids: list[Any]
    knowledge: Optional[dict[str, Any]]
    analysis_history_id: Optional[int]
    proposed_by: str
    proposed_assurance: str
    record_digest: str
    confirmed_by: Optional[str]
    confirmed_assurance: Optional[str]
    confirmed_at: Optional[datetime]
    closed_by: Optional[str] = None
    closed_assurance: Optional[str] = None
    closed_at: Optional[datetime] = None
    closed_reason: Optional[str] = None
    superseded_by_id: Optional[uuid.UUID] = None
    created_at: datetime


class RemediationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    remediation_id: uuid.UUID
    incident_id: uuid.UUID
    diagnosis_id: Optional[uuid.UUID]
    remediation_cycle: int
    action: str
    preconditions: list[Any]
    affected_components: list[Any]
    expected_outcome: str
    risk: str
    impact: str
    rollback_plan: str
    expected_verification_criteria: str
    status: str
    proposed_by: str
    proposed_assurance: str
    record_digest: str
    executed_by: Optional[str]
    executed_assurance: Optional[str]
    executed_at: Optional[datetime]
    actual_action: Optional[str]
    outcome: Optional[str]
    outcome_notes: Optional[str]
    execution_evidence_ids: list[Any]
    catalog_id: Optional[str] = None
    knowledge: Optional[dict[str, Any]] = None
    created_at: datetime
    # Derived server-side from incident_verification; never writable here.
    verification_state: str = "unverified"


class WorkflowEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    incident_id: uuid.UUID
    record_type: str
    record_id: uuid.UUID
    action: str
    actor: str
    actor_assurance: str
    record_digest: str
    detail: dict[str, Any]
    created_at: datetime


class KnowledgeProposalLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    proposal_link_id: uuid.UUID
    incident_id: uuid.UUID
    diagnosis_id: uuid.UUID
    remediation_id: Optional[uuid.UUID]
    knowledge_entry_id: int
    remediation_cycle: int
    evidence_ids: list[Any]
    proposed_by: str
    proposed_assurance: str
    diagnosis_digest: str
    created_at: datetime
    # Review state lives in the existing Knowledge lifecycle; set only at creation (always pending).
    knowledge_status: Optional[str] = None


class NoteCreateRequest(BaseModel):
    """Only the text is accepted. Actor, assurance and timestamps are derived server-side; any other field
    (confirmation, verification, status, actor...) is rejected instead of ignored."""
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, max_length=4000)


class NoteResponse(BaseModel):
    """A note is an observation: it has no diagnosis, verification or lifecycle fields."""
    model_config = ConfigDict(from_attributes=True)

    note_id: uuid.UUID
    incident_id: uuid.UUID
    text: str = Field(validation_alias="body")
    actor: str
    actor_assurance: str
    created_at: datetime
