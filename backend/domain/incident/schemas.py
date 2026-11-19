"""
==============================================================================
EIMS Incident Core Pydantic v2 Contracts
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

import uuid
from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.domain.asset_registry.schemas import PaginationMetadata

IncidentStatusLiteral = Literal["open", "triage", "investigating", "resolved", "closed"]
IncidentSeverityLiteral = Literal["info", "low", "medium", "high", "critical"]
IncidentSourceTypeLiteral = Literal["analysis", "winlog", "telemetry", "audit"]


class IncidentEvidenceCreate(BaseModel):
    """Reference to one source record. Payloads are never accepted here."""
    source_type: IncidentSourceTypeLiteral = Field(
        ..., description="Evidence origin domain: analysis, winlog, telemetry or audit."
    )
    source_id: str = Field(
        ..., min_length=1, max_length=64,
        description="Identifier of the source record (for example analysis_history.id).",
    )
    source_event_key: Optional[str] = Field(
        None, max_length=160,
        description="Optional upstream event key used to derive the correlation signature.",
    )
    evidence_digest: Optional[str] = Field(
        None, min_length=64, max_length=64, pattern="^[0-9a-f]{64}$",
        description="SHA-256 of the source identity. Computed deterministically when omitted.",
    )
    observed_at: datetime = Field(
        ..., description="Observation timestamp of the referenced source event (UTC)."
    )


class IncidentCreateRequest(BaseModel):
    """Creates one incident from one or more evidence references."""
    title: Optional[str] = Field(
        None, max_length=255, description="Optional title; derived from the signature when omitted."
    )
    severity: Optional[IncidentSeverityLiteral] = Field(
        None, description="Optional severity; defaults to 'medium'."
    )
    asset_id: Optional[uuid.UUID] = Field(
        None, description="Resolved asset identity, or null when identity is unresolved."
    )
    evidence: List[IncidentEvidenceCreate] = Field(
        ..., min_length=1, max_length=200,
        description="Bounded evidence references; raw log payloads are not accepted.",
    )
    window_seconds: Optional[int] = Field(
        None, ge=1, le=86400,
        description="Correlation window in seconds; defaults to 900 for Incident Core v1.",
    )


class IncidentEvidenceAttachRequest(BaseModel):
    """Attaches one or more evidence references to an existing incident."""
    evidence: List[IncidentEvidenceCreate] = Field(
        ..., min_length=1, max_length=200,
        description="Bounded evidence references; duplicate (source_type, source_id) pairs are ignored.",
    )
    window_seconds: Optional[int] = Field(
        None, ge=1, le=86400,
        description="Correlation window used to annotate the merge confidence.",
    )


class IncidentVerificationRequest(BaseModel):
    """Caller input for resolution verification: one persisted evidence id."""
    model_config = ConfigDict(extra="forbid")

    evidence_id: uuid.UUID = Field(
        ..., description="incident_evidence.evidence_id proving the remediation outcome."
    )


class IncidentStatusUpdateRequest(BaseModel):
    """Commands a legal incident lifecycle transition.

    ``resolved`` is only accepted together with ``verification`` — a persisted
    evidence reference that the service revalidates against the current
    remediation cycle. ``outcome`` and ``verifier_id`` are deliberately not
    accepted here: they are derived server-side from the authenticated
    principal and the trusted evidence row.
    """
    model_config = ConfigDict(extra="forbid")

    status: IncidentStatusLiteral = Field(
        ..., description="Target lifecycle state: triage, investigating, resolved or closed."
    )
    verification: Optional[IncidentVerificationRequest] = Field(
        None,
        description=(
            "Required when status='resolved'. Must reference persisted incident "
            "evidence attached during the current remediation cycle."
        ),
    )


class IncidentResponse(BaseModel):
    """Serialised incident record; summary carries bounded correlation metadata."""
    model_config = ConfigDict(from_attributes=True)

    incident_id: uuid.UUID
    title: str
    status: str
    severity: str
    confidence: str
    asset_id: Optional[uuid.UUID]
    first_seen: datetime
    last_seen: datetime
    dedupe_key: str
    root_cause_state: str
    owner: Optional[str]
    summary: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    remediation_cycle: int = 0


class IncidentEvidenceResponse(BaseModel):
    """Serialised evidence reference; no source payload is exposed."""
    model_config = ConfigDict(from_attributes=True)

    evidence_id: uuid.UUID
    incident_id: uuid.UUID
    source_type: str
    source_id: str
    source_event_key: Optional[str]
    evidence_digest: str
    observed_at: datetime
    added_by: str
    created_at: datetime


class IncidentVerificationResponse(BaseModel):
    """One append-only verification record (who verified what, and when)."""
    model_config = ConfigDict(from_attributes=True)

    verification_id: uuid.UUID
    incident_id: uuid.UUID
    remediation_cycle: int
    evidence_id: uuid.UUID
    evidence_digest: str
    outcome: str
    verifier_id: str
    verified_at: datetime


class IncidentDetailResponse(IncidentResponse):
    """Incident record with its current evidence references."""
    evidence: List[IncidentEvidenceResponse] = Field(
        default_factory=list, description="Evidence references currently bound to the incident."
    )
    verifications: List[IncidentVerificationResponse] = Field(
        default_factory=list,
        description="Append-only verification history across remediation cycles.",
    )


class IncidentVerificationResponse(BaseModel):
    """One append-only verification record (who verified what, and when)."""
    model_config = ConfigDict(from_attributes=True)

    verification_id: uuid.UUID
    incident_id: uuid.UUID
    remediation_cycle: int
    evidence_id: uuid.UUID
    evidence_digest: str
    outcome: str
    verifier_id: str
    verified_at: datetime


class IncidentListResponse(BaseModel):
    """Canonical Core Law 5 Section 6.1 collection wrapper."""
    status: str = "success"
    data: List[IncidentResponse]
    pagination: PaginationMetadata


class IncidentEvidenceListResponse(BaseModel):
    """Collection wrapper for an incident's evidence references."""
    status: str = "success"
    data: List[IncidentEvidenceResponse]
    pagination: PaginationMetadata
