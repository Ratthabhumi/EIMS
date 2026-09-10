"""
==============================================================================
EIMS Query Layer - Unified Timeline API Controller (Sprint 10)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.analyzer.auth import get_current_user
from backend.domain.asset_registry.schemas import PaginationMetadata
from backend.domain.timeline.schemas import TimelineResponse
from backend.domain.timeline.service import TimelineService
from backend.infrastructure.database import get_db_session

# Core Law 5 Section 5.2 strict adherence: No trailing slashes in route declarations
timeline_router = APIRouter(prefix="/api/v1", tags=["Unified Timeline"])

timeline_service = TimelineService()


async def get_timeline_service() -> TimelineService:
    """Dependency injection factory exposing the canonical unified Timeline service."""
    return timeline_service


@timeline_router.get(
    "/timeline",
    response_model=TimelineResponse,
    status_code=200,
    summary="Unified Cross-Source Timeline",
    description="Aggregates chronological events from audit_logs, telemetry_metrics, and windows_event_logs.",
)
async def query_timeline(
    entity_id: Optional[UUID] = Query(None, description="Filter by related asset/entity UUID."),
    event_type: Optional[Literal["audit", "telemetry", "winlog"]] = Query(
        None, alias="type", description="Filter by event source type."
    ),
    severity: Optional[str] = Query(None, description="Severity level (Critical, Warning, Information)."),
    from_dt: Optional[datetime] = Query(None, alias="from", description="Start date (ISO 8601)."),
    to_dt: Optional[datetime] = Query(None, alias="to", description="End date (ISO 8601)."),
    page: int = Query(1, ge=1, description="Requested page index offset."),
    limit: int = Query(50, ge=1, le=200, description="Max events per pagination slice."),
    db: AsyncSession = Depends(get_db_session),
    service: TimelineService = Depends(get_timeline_service),
    _user: str = Depends(get_current_user),
) -> TimelineResponse:
    """
    Returns chronologically ordered events (newest first) wrapped within the
    canonical Core Law 5 Section 6.1 collection wrapper.
    """
    events, total_records = await service.get_timeline(
        db=db,
        entity_id=entity_id,
        event_type=event_type,
        severity=severity,
        from_dt=from_dt,
        to_dt=to_dt,
        page=page,
        limit=limit,
    )
    pagination_block = PaginationMetadata(
        total_records=total_records,
        current_page=page,
        page_size=limit,
        next_page_cursor=None,
    )
    return TimelineResponse(status="success", data=events, pagination=pagination_block)