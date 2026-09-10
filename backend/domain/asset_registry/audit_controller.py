"""
==============================================================================
EIMS Query Layer - Audit Log Query API Controller (Sprint 10)
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
from backend.domain.asset_registry.models import AuditLog
from backend.domain.asset_registry.schemas import AuditLogListResponse, AuditLogResponse, PaginationMetadata
from backend.infrastructure.database import get_db_session

# Core Law 5 Section 5.2 strict adherence: No trailing slashes in route declarations
audit_router = APIRouter(prefix="/api/v1", tags=["Compliance Auditing & Audit Log"])


@audit_router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    status_code=200,
    summary="Query Immutable Audit Log Records",
    description="Read-only forensic interface over the immutable audit journal with asset/action/date filtering.",
)
async def list_audit_logs(
    asset_id: Optional[UUID] = Query(None, description="Filter by target asset UUID."),
    action: Optional[str] = Query(None, description="Filter by action_verb (exact match)."),
    from_dt: Optional[datetime] = Query(None, alias="from", description="Start date (ISO 8601)."),
    to_dt: Optional[datetime] = Query(None, alias="to", description="End date (ISO 8601)."),
    page: int = Query(1, ge=1, description="Requested page index offset."),
    limit: int = Query(50, ge=1, le=200, description="Max records per pagination slice."),
    db: AsyncSession = Depends(get_db_session),
    _user: str = Depends(get_current_user),
) -> AuditLogListResponse:
    """
    Returns ordered historical execution records from the immutable PostgreSQL
    audit tables wrapped within the canonical Core Law 5 Section 6.1 wrapper.
    """
    stmt = select(AuditLog)
    if asset_id is not None:
        stmt = stmt.where(AuditLog.asset_id == asset_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action_verb == action)
    if from_dt is not None:
        stmt = stmt.where(AuditLog.performed_at >= from_dt)
    if to_dt is not None:
        stmt = stmt.where(AuditLog.performed_at <= to_dt)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_records = (await db.execute(count_stmt)).scalar_one()

    skip = (page - 1) * limit
    stmt = stmt.order_by(AuditLog.performed_at.desc()).offset(skip).limit(limit)
    logs = (await db.execute(stmt)).scalars().all()

    serialized_data = [AuditLogResponse.model_validate(log) for log in logs]
    pagination_block = PaginationMetadata(
        total_records=total_records,
        current_page=page,
        page_size=limit,
        next_page_cursor=None,
    )
    return AuditLogListResponse(status="success", data=serialized_data, pagination=pagination_block)