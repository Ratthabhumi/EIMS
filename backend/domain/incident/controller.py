"""
==============================================================================
EIMS Incident Core API Controller (v1)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================

Routes are registered under /api/v1/incidents. Reads require any authenticated
identity. Creating incidents and attaching evidence requires an authenticated
Engineer. Closing an incident additionally requires the Knowledge Reviewer
capability.
"""

import uuid
from typing import Literal, Optional

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.domain.analyzer.auth import (
    OPEN_ACCESS_IDENTITY,
    get_current_user,
    require_knowledge_reviewer,
    security,
)
from backend.domain.asset_registry.schemas import PaginationMetadata
from backend.domain.incident.schemas import (
    IncidentCreateRequest,
    IncidentDetailResponse,
    IncidentEvidenceAttachRequest,
    IncidentEvidenceCreate,
    IncidentEvidenceListResponse,
    IncidentEvidenceResponse,
    IncidentLinkResponse,
    IncidentListResponse,
    IncidentResponse,
    IncidentStatusUpdateRequest,
    IncidentVerificationResponse,
)
from backend.domain.incident.service import (
    EvidenceInput,
    IncidentConflict,
    IncidentNotFound,
    IncidentPermissionError,
    IncidentService,
    IncidentTransitionRejected,
    IncidentValidationError,
)
from backend.domain.incident.verification import VerificationRequest
from backend.domain.incident.workflow import (
    SHARED_TOKEN,
    UNATTRIBUTED,
    VERIFIED,
    Actor,
    IncidentWorkflow,
)
from backend.domain.incident.workflow_schemas import (
    DiagnosisCloseRequest,
    DiagnosisConfirmRequest,
    DiagnosisCreateRequest,
    DiagnosisResponse,
    DiagnosisSupersedeRequest,
    IncidentKnowledgeProposalRequest,
    KnowledgeProposalLinkResponse,
    NoteCreateRequest,
    NoteResponse,
    RemediationCreateRequest,
    RemediationExecutionRequest,
    RemediationResponse,
    WorkflowEventResponse,
)
from backend.infrastructure.database import get_db_session

incident_router = APIRouter(prefix="/api/v1/incidents", tags=["Incident Core"])


async def get_incident_service(
    db: AsyncSession = Depends(get_db_session),
) -> IncidentService:
    """Dependency factory binding the service to the request transaction."""
    return IncidentService(db)


async def get_actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    user: str = Depends(get_current_user),
) -> Actor:
    """Derives an honest actor + assurance level from the actual credential.

    * no usable credential            -> ``unattributed`` (open access)
    * the shared admin token          -> ``shared-token`` (a secret, not a person)
    * a valid session JWT for a user  -> ``verified-identity``
    The literal username "admin" returned for the shared token is NOT used as an
    identifier, so the shared secret is never mistaken for a named person.
    """
    token = credentials.credentials if credentials and credentials.credentials else ""
    if not token:
        return Actor(OPEN_ACCESS_IDENTITY, UNATTRIBUTED)
    if secrets.compare_digest(token, settings.ADMIN_TOKEN):
        return Actor("shared-admin-token", SHARED_TOKEN)
    # "demo" is the open-access principal and "shared-admin-token" is reserved for the
    # shared secret: a real user carrying either name must not impersonate them in the audit.
    if user in (OPEN_ACCESS_IDENTITY, "shared-admin-token"):
        return Actor(OPEN_ACCESS_IDENTITY, UNATTRIBUTED)
    return Actor(user, VERIFIED)


async def get_workflow(db: AsyncSession = Depends(get_db_session)) -> IncidentWorkflow:
    return IncidentWorkflow(db)


def _service_items(payload: list[IncidentEvidenceCreate]) -> list[EvidenceInput]:
    return [
        EvidenceInput(
            source_type=item.source_type,
            source_id=item.source_id,
            observed_at=item.observed_at,
            source_event_key=item.source_event_key,
            evidence_digest=item.evidence_digest,
        )
        for item in payload
    ]


def _raise_for_service_error(exc: Exception) -> None:
    """Maps domain failures onto explicit HTTP semantics."""
    if isinstance(exc, IncidentNotFound):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, IncidentPermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if isinstance(exc, IncidentTransitionRejected):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, IncidentValidationError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if isinstance(exc, IncidentConflict):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


async def _detail(service: IncidentService, incident) -> IncidentDetailResponse:
    evidence, _total = await service.list_evidence(incident.incident_id, page=1, limit=500)
    verifications = await service.list_verifications(incident.incident_id)
    # Validate through the flat response model first: Incident.evidence is a
    # lazy relationship and must not be touched outside an await context.
    base = IncidentResponse.model_validate(incident)
    return IncidentDetailResponse(
        **base.model_dump(),
        evidence=[IncidentEvidenceResponse.model_validate(row) for row in evidence],
        verifications=[
            IncidentVerificationResponse.model_validate(row) for row in verifications
        ],
    )


@incident_router.get(
    "",
    response_model=IncidentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List correlated incidents",
)
async def list_incidents(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by lifecycle status."),
    severity: Optional[str] = Query(None, description="Filter by severity."),
    asset_id: Optional[uuid.UUID] = Query(None, description="Filter by resolved asset UUID."),
    page: int = Query(1, ge=1, description="Requested page index offset."),
    limit: int = Query(50, ge=1, le=200, description="Max incidents per page."),
    service: IncidentService = Depends(get_incident_service),
    _user: str = Depends(get_current_user),
) -> IncidentListResponse:
    try:
        incidents, total = await service.list_incidents(
            status=status_filter, severity=severity, asset_id=asset_id, page=page, limit=limit
        )
    except Exception as exc:  # noqa: BLE001 - mapped domain/HTTP boundary
        _raise_for_service_error(exc)
    return IncidentListResponse(
        status="success",
        data=[IncidentResponse.model_validate(item) for item in incidents],
        pagination=PaginationMetadata(
            total_records=total, current_page=page, page_size=limit, next_page_cursor=None
        ),
    )


@incident_router.get(
    "/by-evidence",
    response_model=list[IncidentLinkResponse],
    status_code=status.HTTP_200_OK,
    summary="Which incident, if any, is a source event already linked to",
)
async def incident_for_evidence(
    source_type: Literal["analysis", "winlog", "telemetry", "audit"] = Query(...),
    source_id: str = Query(..., min_length=1, max_length=64),
    service: IncidentService = Depends(get_incident_service),
    _user: str = Depends(get_current_user),
) -> list[IncidentLinkResponse]:
    try:
        return [IncidentLinkResponse(**row) for row in await service.find_by_evidence(source_type, source_id)]
    except Exception as exc:  # noqa: BLE001
        _raise_for_service_error(exc)


@incident_router.get(
    "/{incident_id}",
    response_model=IncidentDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve one incident with evidence references",
)
async def get_incident(
    incident_id: uuid.UUID,
    service: IncidentService = Depends(get_incident_service),
    _user: str = Depends(get_current_user),
) -> IncidentDetailResponse:
    try:
        incident = await service.get_incident(incident_id)
        return await _detail(service, incident)
    except Exception as exc:  # noqa: BLE001
        _raise_for_service_error(exc)


@incident_router.post(
    "",
    response_model=IncidentDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an incident from evidence references",
)
async def create_incident(
    payload: IncidentCreateRequest,
    service: IncidentService = Depends(get_incident_service),
    user: str = Depends(get_current_user),
) -> IncidentDetailResponse:
    try:
        items = _service_items(payload.evidence)
        already_bound = any([await service.find_by_evidence(i.source_type, i.source_id) for i in items])
        items, asset_id = await service.enrich_evidence(items, payload.asset_id)
        already_bound = already_bound or any(
            [i.evidence_digest and await service.find_by_digest(i.evidence_digest) for i in items])
        incident, created = await service.create_from_evidence(
            items,
            actor=user,
            asset_id=asset_id,
            title=payload.title,
            severity=payload.severity,
            window_seconds=payload.window_seconds,
        )
        response = await _detail(service, incident)
        response.created = created
        correlation = (response.summary or {}).get("correlation") or {}
        response.match = (
            ("ambiguous_not_merged" if correlation.get("status") == "ambiguous" else "created") if created
            else "event_already_linked" if already_bound
            else "correlated_with_open_incident")
        return response
    except Exception as exc:  # noqa: BLE001
        _raise_for_service_error(exc)


@incident_router.post(
    "/{incident_id}/evidence",
    response_model=IncidentDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Attach evidence references to an incident",
)
async def attach_evidence(
    incident_id: uuid.UUID,
    payload: IncidentEvidenceAttachRequest,
    service: IncidentService = Depends(get_incident_service),
    user: str = Depends(get_current_user),
) -> IncidentDetailResponse:
    try:
        enriched, _asset = await service.enrich_evidence(_service_items(payload.evidence), None)
        incident, added = await service.attach_evidence(
            incident_id,
            enriched,
            actor=user,
            window_seconds=payload.window_seconds,
        )
        response = await _detail(service, incident)
        response.summary = {**(response.summary or {}), "evidence_added": added}
        return response
    except Exception as exc:  # noqa: BLE001
        _raise_for_service_error(exc)


@incident_router.get(
    "/{incident_id}/evidence",
    response_model=IncidentEvidenceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List evidence references for an incident",
)
async def list_evidence(
    incident_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    service: IncidentService = Depends(get_incident_service),
    _user: str = Depends(get_current_user),
) -> IncidentEvidenceListResponse:
    try:
        rows, total = await service.list_evidence(incident_id, page=page, limit=limit)
    except Exception as exc:  # noqa: BLE001
        _raise_for_service_error(exc)
    return IncidentEvidenceListResponse(
        status="success",
        data=[IncidentEvidenceResponse.model_validate(row) for row in rows],
        pagination=PaginationMetadata(
            total_records=total, current_page=page, page_size=limit, next_page_cursor=None
        ),
    )


@incident_router.patch(
    "/{incident_id}/status",
    response_model=IncidentDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Apply a legal incident lifecycle transition",
)
async def update_status(
    incident_id: uuid.UUID,
    payload: IncidentStatusUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    service: IncidentService = Depends(get_incident_service),
    user: str = Depends(get_current_user),
    actor: Actor = Depends(get_actor),
) -> IncidentDetailResponse:
    reviewer_identity: str | None = None
    verification: VerificationRequest | None = None
    verifier: str | None = None
    if payload.status in ("resolved", "closed") and actor.assurance != VERIFIED:
        # Open-access and shared-token callers are not a proven individual. They
        # must never verify, resolve or close an incident, even if the literal
        # name they resolve to matches a privileged account.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Resolving or closing an incident requires a verified-identity reviewer",
        )
    if payload.status == "closed":
        # Enforces the same capability gate as Knowledge review; unauthenticated
        # callers are rejected by get_current_user before reaching this point.
        reviewer_identity = await require_knowledge_reviewer(username=user, credentials=None, db=db)
    elif payload.status == "resolved":
        # The authenticated principal is the only verifier identity that exists;
        # the service checks its capability against trusted persistence. The
        # service also rejects a missing/invalid evidence reference, after the
        # lifecycle edge itself has been validated.
        verifier = user
        if payload.verification is not None:
            verification = VerificationRequest(
                evidence_id=payload.verification.evidence_id
            )
    try:
        incident = await service.change_status(
            incident_id,
            payload.status,
            actor=user,
            reviewer_identity=reviewer_identity,
            verification=verification,
            verifier=verifier,
            assurance=actor.assurance,
        )
        return await _detail(service, incident)
    except Exception as exc:  # noqa: BLE001
        _raise_for_service_error(exc)


# ---------------------------------------------------------------------------
# Diagnosis and remediation records (actor assurance is derived server-side)
# ---------------------------------------------------------------------------
def _total(response: Response, total: int) -> None:
    response.headers["X-Total-Count"] = str(total)


@incident_router.post(
    "/{incident_id}/diagnoses",
    response_model=DiagnosisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a root-cause hypothesis (never a confirmed cause)",
)
async def create_diagnosis(
    incident_id: uuid.UUID,
    payload: DiagnosisCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    workflow: IncidentWorkflow = Depends(get_workflow),
    actor: Actor = Depends(get_actor),
) -> DiagnosisResponse:
    try:
        row = await workflow.propose_diagnosis(
            incident_id, actor=actor, hypothesis=payload.hypothesis, reasoning=payload.reasoning,
            stated_confidence=payload.stated_confidence,
            supporting_evidence_ids=payload.supporting_evidence_ids,
            contradicting_evidence_ids=payload.contradicting_evidence_ids,
            catalog_id=payload.catalog_id, analysis_history_id=payload.analysis_history_id,
            detected_version=payload.detected_version,
        )
        response = DiagnosisResponse.model_validate(row)
        await db.commit()
        return response
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        _raise_for_service_error(exc)


@incident_router.post(
    "/{incident_id}/notes",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Append an engineer note (an observation; never a diagnosis, verification or status change)",
)
async def create_note(
    incident_id: uuid.UUID,
    payload: NoteCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    workflow: IncidentWorkflow = Depends(get_workflow),
    actor: Actor = Depends(get_actor),
) -> NoteResponse:
    try:
        row = await workflow.add_note(incident_id, actor=actor, text=payload.text)
        response = NoteResponse.model_validate(row)
        await db.commit()
        return response
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        _raise_for_service_error(exc)


@incident_router.get(
    "/{incident_id}/notes",
    response_model=list[NoteResponse],
    summary="List engineer notes, oldest first (bounded page; total in X-Total-Count)",
)
async def list_notes(
    incident_id: uuid.UUID,
    response: Response,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    workflow: IncidentWorkflow = Depends(get_workflow),
    _user: str = Depends(get_current_user),
) -> list[NoteResponse]:
    try:
        rows, total = await workflow.list_notes(incident_id, limit=limit, offset=offset)
        _total(response, total)
        return [NoteResponse.model_validate(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        _raise_for_service_error(exc)


@incident_router.get(
    "/{incident_id}/diagnoses",
    response_model=list[DiagnosisResponse],
    summary="List diagnosis records (bounded page; total in X-Total-Count)",
)
async def list_diagnoses(
    incident_id: uuid.UUID,
    response: Response,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    workflow: IncidentWorkflow = Depends(get_workflow),
    _user: str = Depends(get_current_user),
) -> list[DiagnosisResponse]:
    try:
        rows, total = await workflow.list_diagnoses(incident_id, limit=limit, offset=offset)
        _total(response, total)
        return [DiagnosisResponse.model_validate(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        _raise_for_service_error(exc)


@incident_router.post(
    "/{incident_id}/diagnoses/{diagnosis_id}/confirm",
    response_model=DiagnosisResponse,
    summary="Confirm a root cause (verified-identity reviewer only)",
)
async def confirm_diagnosis(
    incident_id: uuid.UUID,
    diagnosis_id: uuid.UUID,
    payload: DiagnosisConfirmRequest,
    db: AsyncSession = Depends(get_db_session),
    workflow: IncidentWorkflow = Depends(get_workflow),
    actor: Actor = Depends(get_actor),
) -> DiagnosisResponse:
    # Defence in depth: the service enforces the same rule independently of HTTP.
    if actor.assurance != VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Root cause can only be confirmed by a verified-identity reviewer",
        )
    await require_knowledge_reviewer(username=actor.identifier, credentials=None, db=db)
    try:
        row = await workflow.confirm_diagnosis(
            incident_id, diagnosis_id, actor=actor, rationale=payload.rationale)
        response = DiagnosisResponse.model_validate(row)
        await db.commit()
        return response
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        _raise_for_service_error(exc)


@incident_router.post(
    "/{incident_id}/diagnoses/{diagnosis_id}/reject",
    response_model=DiagnosisResponse,
    summary="Reject an open hypothesis; the row and its history are kept",
)
async def reject_diagnosis(
    incident_id: uuid.UUID,
    diagnosis_id: uuid.UUID,
    payload: DiagnosisCloseRequest,
    db: AsyncSession = Depends(get_db_session),
    workflow: IncidentWorkflow = Depends(get_workflow),
    actor: Actor = Depends(get_actor),
) -> DiagnosisResponse:
    try:
        row = await workflow.reject_diagnosis(incident_id, diagnosis_id, actor=actor, reason=payload.reason)
        response = DiagnosisResponse.model_validate(row)
        await db.commit()
        return response
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        _raise_for_service_error(exc)


@incident_router.post(
    "/{incident_id}/diagnoses/{diagnosis_id}/supersede",
    response_model=DiagnosisResponse,
    summary="Supersede an open hypothesis with another live diagnosis",
)
async def supersede_diagnosis(
    incident_id: uuid.UUID,
    diagnosis_id: uuid.UUID,
    payload: DiagnosisSupersedeRequest,
    db: AsyncSession = Depends(get_db_session),
    workflow: IncidentWorkflow = Depends(get_workflow),
    actor: Actor = Depends(get_actor),
) -> DiagnosisResponse:
    try:
        row = await workflow.supersede_diagnosis(
            incident_id, diagnosis_id, actor=actor, reason=payload.reason,
            superseded_by_id=payload.superseded_by_id)
        response = DiagnosisResponse.model_validate(row)
        await db.commit()
        return response
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        _raise_for_service_error(exc)


@incident_router.post(
    "/{incident_id}/remediations",
    response_model=RemediationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Propose a remediation (risk, rollback and verification criteria required)",
)
async def create_remediation(
    incident_id: uuid.UUID,
    payload: RemediationCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    workflow: IncidentWorkflow = Depends(get_workflow),
    actor: Actor = Depends(get_actor),
) -> RemediationResponse:
    try:
        row = await workflow.propose_remediation(
            incident_id, actor=actor, action=payload.action, risk=payload.risk,
            rollback_plan=payload.rollback_plan,
            expected_verification_criteria=payload.expected_verification_criteria,
            impact=payload.impact, expected_outcome=payload.expected_outcome,
            preconditions=payload.preconditions, affected_components=payload.affected_components,
            diagnosis_id=payload.diagnosis_id, catalog_id=payload.catalog_id,
            detected_version=payload.detected_version,
        )
        response = RemediationResponse.model_validate(row)
        await db.commit()
        return response
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        _raise_for_service_error(exc)


@incident_router.post(
    "/{incident_id}/remediations/{remediation_id}/execution",
    response_model=RemediationResponse,
    summary="Record what was actually done and its outcome (does not verify)",
)
async def record_remediation_execution(
    incident_id: uuid.UUID,
    remediation_id: uuid.UUID,
    payload: RemediationExecutionRequest,
    db: AsyncSession = Depends(get_db_session),
    workflow: IncidentWorkflow = Depends(get_workflow),
    actor: Actor = Depends(get_actor),
) -> RemediationResponse:
    try:
        row = await workflow.record_execution(
            incident_id, remediation_id, actor=actor, actual_action=payload.actual_action,
            outcome=payload.outcome, outcome_notes=payload.outcome_notes,
            evidence_ids=payload.evidence_ids,
        )
        response = RemediationResponse.model_validate(row)
        await db.commit()
        return response
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        _raise_for_service_error(exc)


@incident_router.get(
    "/{incident_id}/remediations",
    response_model=list[RemediationResponse],
    summary="List remediation records with derived verification state (bounded page)",
)
async def list_remediations(
    incident_id: uuid.UUID,
    response: Response,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    workflow: IncidentWorkflow = Depends(get_workflow),
    _user: str = Depends(get_current_user),
) -> list[RemediationResponse]:
    try:
        rows, total = await workflow.list_remediations(incident_id, limit=limit, offset=offset)
        _total(response, total)
        out = []
        for row, state in rows:
            item = RemediationResponse.model_validate(row)
            item.verification_state = state
            out.append(item)
        return out
    except Exception as exc:  # noqa: BLE001
        _raise_for_service_error(exc)


@incident_router.get(
    "/{incident_id}/workflow-events",
    response_model=list[WorkflowEventResponse],
    summary="Append-only diagnosis/remediation audit with actor assurance (bounded page)",
)
async def list_workflow_events(
    incident_id: uuid.UUID,
    response: Response,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    workflow: IncidentWorkflow = Depends(get_workflow),
    _user: str = Depends(get_current_user),
) -> list[WorkflowEventResponse]:
    try:
        rows, total = await workflow.list_events(incident_id, limit=limit, offset=offset)
        _total(response, total)
        return [WorkflowEventResponse.model_validate(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        _raise_for_service_error(exc)


@incident_router.post(
    "/{incident_id}/knowledge-proposals",
    response_model=KnowledgeProposalLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Propose knowledge from a completed incident into the existing review lifecycle",
)
async def create_knowledge_proposal_from_incident(
    incident_id: uuid.UUID,
    payload: IncidentKnowledgeProposalRequest,
    db: AsyncSession = Depends(get_db_session),
    workflow: IncidentWorkflow = Depends(get_workflow),
    actor: Actor = Depends(get_actor),
) -> KnowledgeProposalLinkResponse:
    try:
        link, entry = await workflow.propose_knowledge(
            incident_id, payload.diagnosis_id, actor=actor, proposal=payload.proposal,
            remediation_id=payload.remediation_id, evidence_ids=payload.evidence_ids)
        response = KnowledgeProposalLinkResponse.model_validate(link)
        response.knowledge_status = entry.status
        await db.commit()
        return response
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        _raise_for_service_error(exc)


@incident_router.get(
    "/{incident_id}/knowledge-proposals",
    response_model=list[KnowledgeProposalLinkResponse],
    summary="Knowledge proposals that originated from this incident (review state lives in Knowledge)",
)
async def list_knowledge_proposals(
    incident_id: uuid.UUID,
    workflow: IncidentWorkflow = Depends(get_workflow),
    _user: str = Depends(get_current_user),
) -> list[KnowledgeProposalLinkResponse]:
    try:
        return [KnowledgeProposalLinkResponse.model_validate(r)
                for r in await workflow.list_knowledge_proposals(incident_id)]
    except Exception as exc:  # noqa: BLE001
        _raise_for_service_error(exc)
