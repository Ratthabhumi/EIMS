"""
==============================================================================
EIMS Query Layer - Telemetry Query API Controller (Sprint 10)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.analyzer.auth import get_current_user
from backend.domain.asset_registry.schemas import PaginationMetadata
from backend.domain.telemetry.models import TelemetryMetric, WindowsEventLog
from backend.domain.telemetry.schemas import (
    TelemetryMetricResponse,
    TelemetryMetricsListResponse,
    WinlogListResponse,
    WinlogResponse,
)
from backend.infrastructure.database import get_db_session

# Core Law 5 Section 5.2 strict adherence: No trailing slashes in route declarations
telemetry_query_router = APIRouter(prefix="/api/v1/telemetry", tags=["Telemetry Query Interfaces"])


@telemetry_query_router.get(
    "/metrics",
    response_model=TelemetryMetricsListResponse,
    status_code=200,
    summary="Query Historical Telemetry Metrics",
    description="Returns paginated telemetry metric history for a specific asset.",
)
async def list_telemetry_metrics(
    asset_id: UUID = Query(..., description="Filter by asset UUID."),
    from_dt: Optional[datetime] = Query(None, alias="from", description="Start date (ISO 8601)."),
    to_dt: Optional[datetime] = Query(None, alias="to", description="End date (ISO 8601)."),
    page: int = Query(1, ge=1, description="Requested page index offset."),
    limit: int = Query(50, ge=1, le=200, description="Max records per pagination slice."),
    db: AsyncSession = Depends(get_db_session),
    _user: str = Depends(get_current_user),
) -> TelemetryMetricsListResponse:
    stmt = select(TelemetryMetric).where(TelemetryMetric.asset_id == asset_id)
    if from_dt is not None:
        stmt = stmt.where(TelemetryMetric.event_time >= from_dt)
    if to_dt is not None:
        stmt = stmt.where(TelemetryMetric.event_time <= to_dt)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_records = (await db.execute(count_stmt)).scalar_one()

    skip = (page - 1) * limit
    stmt = stmt.order_by(TelemetryMetric.event_time.desc()).offset(skip).limit(limit)
    metrics = (await db.execute(stmt)).scalars().all()

    serialized_data = [TelemetryMetricResponse.model_validate(metric) for metric in metrics]
    pagination_block = PaginationMetadata(
        total_records=total_records,
        current_page=page,
        page_size=limit,
        next_page_cursor=None,
    )
    return TelemetryMetricsListResponse(status="success", data=serialized_data, pagination=pagination_block)


@telemetry_query_router.get(
    "/winlogs",
    response_model=WinlogListResponse,
    status_code=200,
    summary="Query Historical Windows Event Log Records",
    description="Returns paginated Windows Event Log history with asset/event/severity/date filtering.",
)
async def list_windows_event_logs(
    asset_id: Optional[UUID] = Query(None, description="Filter by asset UUID."),
    event_id: Optional[int] = Query(None, ge=0, description="Filter by Windows Event ID (exact match)."),
    severity: Optional[str] = Query(None, description="Filter by severity level."),
    from_dt: Optional[datetime] = Query(None, alias="from", description="Start date (ISO 8601)."),
    to_dt: Optional[datetime] = Query(None, alias="to", description="End date (ISO 8601)."),
    page: int = Query(1, ge=1, description="Requested page index offset."),
    limit: int = Query(50, ge=1, le=200, description="Max records per pagination slice."),
    db: AsyncSession = Depends(get_db_session),
    _user: str = Depends(get_current_user),
) -> WinlogListResponse:
    stmt = select(WindowsEventLog)
    if asset_id is not None:
        stmt = stmt.where(WindowsEventLog.asset_id == asset_id)
    if event_id is not None:
        stmt = stmt.where(WindowsEventLog.event_id == event_id)
    if severity is not None:
        stmt = stmt.where(WindowsEventLog.severity_level == severity)
    if from_dt is not None:
        stmt = stmt.where(WindowsEventLog.occurrence_time >= from_dt)
    if to_dt is not None:
        stmt = stmt.where(WindowsEventLog.occurrence_time <= to_dt)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_records = (await db.execute(count_stmt)).scalar_one()

    skip = (page - 1) * limit
    stmt = stmt.order_by(WindowsEventLog.occurrence_time.desc()).offset(skip).limit(limit)
    logs = (await db.execute(stmt)).scalars().all()

    serialized_data = [WinlogResponse.model_validate(log) for log in logs]
    pagination_block = PaginationMetadata(
        total_records=total_records,
        current_page=page,
        page_size=limit,
        next_page_cursor=None,
    )
    return WinlogListResponse(status="success", data=serialized_data, pagination=pagination_block)