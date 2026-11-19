"""
==============================================================================
EIMS Incident Core Domain Module
Governed by EIMS Documentation System (EDS v1.0.0)
Source-Available All Rights Reserved Policy
==============================================================================
"""

from backend.domain.incident.correlation import (
    DEFAULT_WINDOW_SECONDS,
    CorrelationAssessment,
    CorrelationInput,
    build_dedupe_key,
    classify,
)
from backend.domain.incident.controller import incident_router
from backend.domain.incident.models import Incident, IncidentEvidence
from backend.domain.incident.schemas import (
    IncidentCreateRequest,
    IncidentEvidenceAttachRequest,
    IncidentEvidenceCreate,
    IncidentStatusUpdateRequest,
)
from backend.domain.incident.service import (
    LEGAL_TRANSITIONS,
    EvidenceInput,
    IncidentService,
    can_transition,
    validate_transition,
)

__all__ = [
    "DEFAULT_WINDOW_SECONDS",
    "CorrelationAssessment",
    "CorrelationInput",
    "build_dedupe_key",
    "classify",
    "Incident",
    "IncidentEvidence",
    "IncidentCreateRequest",
    "IncidentEvidenceAttachRequest",
    "IncidentEvidenceCreate",
    "IncidentStatusUpdateRequest",
    "LEGAL_TRANSITIONS",
    "EvidenceInput",
    "IncidentService",
    "can_transition",
    "validate_transition",
    "incident_router",
]
