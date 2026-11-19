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
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.analyzer.auth import get_current_user, require_knowledge_reviewer
from backend.domain.asset_registry.schemas import PaginationMetadata
from backend.domain.incident.schemas import (
    IncidentCreateRequest,
    IncidentDetailResponse,
    IncidentEvidenceAttachRequest,
    IncidentEvidenceCreate,
    IncidentEvidenceListResponse,
    IncidentEvidenceResponse,
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
from backend.infrastructure.database import get_db_session

incident_router = APIRouter(prefix="/api/v1/incidents", tags=["Incident Core"])


async def get_incident_service(
    db: AsyncSession = Depends(get_db_session),
) -> IncidentService:
    """Dependency factory binding the service to the request transaction."""
    return IncidentService(db)


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
        incident, _created = await service.create_from_evidence(
            _service_items(payload.evidence),
            actor=user,
            asset_id=payload.asset_id,
            title=payload.title,
            severity=payload.severity,
            window_seconds=payload.window_seconds,
        )
        return await _detail(service, incident)
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
        incident, added = await service.attach_evidence(
            incident_id,
            _service_items(payload.evidence),
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
) -> IncidentDetailResponse:
    reviewer_identity: str | None = None
    verification: VerificationRequest | None = None
    verifier: str | None = None
    if payload.status == "closed":
        # Enforces the same capability gate as Knowledge review; unauthenticated
        # callers are rejected by get_current_user before reaching this point.
        reviewer_identity = await require_knowledge_reviewer(username=user, db=db)
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
        )
        return await _detail(service, incident)
    except Exception as exc:  # noqa: BLE001
        _raise_for_service_error(exc)
