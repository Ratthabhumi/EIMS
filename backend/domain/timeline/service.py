"""
==============================================================================
EIMS Query Layer - Unified Timeline Aggregation Service (Sprint 10)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

import uuid
from typing import Optional

from sqlalchemy import String, cast, func, literal, null, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger import get_logger
from backend.domain.asset_registry.models import AuditLog
from backend.domain.telemetry.models import TelemetryMetric, WindowsEventLog
from backend.domain.timeline.schemas import TimelineEvent

logger = get_logger("eims.query.timeline")

ENTITY_TYPE = "asset"
SEVERITY_INFORMATION = "Information"


class TimelineService:
    """
    Aggregates chronological events across `audit_logs`, `telemetry_metrics`, and
    `windows_event_logs` via a single UNION ALL query — no new event table is
    introduced (Architecture §6.5 design decision).
    """
    async def get_timeline(
        self,
        db: AsyncSession,
        entity_id: Optional[uuid.UUID] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        from_dt=None,
        to_dt=None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[TimelineEvent], int]:
        """
        Builds and executes the unified source query, computing an accurate
        total record count, then slicing the requested chronological page.
        """
        union_subq = union_all(*self._build_source_selects(entity_id=entity_id, event_type=event_type)).subquery()

        conditions = []
        if severity:
            conditions.append(union_subq.c.severity == severity)
        if from_dt is not None:
            conditions.append(union_subq.c.timestamp >= from_dt)
        if to_dt is not None:
            conditions.append(union_subq.c.timestamp <= to_dt)

        count_stmt = select(func.count()).select_from(union_subq).where(*conditions)
        total = (await db.execute(count_stmt)).scalar_one()

        skip = (page - 1) * limit
        page_stmt = (
            select(union_subq)
            .where(*conditions)
            .order_by(union_subq.c.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        rows = (await db.execute(page_stmt)).all()
        return [self._build_event(row) for row in rows], total

    def _build_source_selects(self, entity_id, event_type) -> list:
        selects = []
        if event_type is None or event_type == "audit":
            selects.append(self._audit_select(entity_id))
        if event_type is None or event_type == "telemetry":
            selects.append(self._telemetry_select(entity_id))
        if event_type is None or event_type == "winlog":
            selects.append(self._winlog_select(entity_id))
        if not selects:
            raise ValueError(f"Unsupported timeline event type filter: '{event_type}'")
        return selects

    def _audit_select(self, entity_id):
        stmt = select(
            cast(AuditLog.log_id, String).label("id"),
            literal("audit").label("type"),
            literal(SEVERITY_INFORMATION).label("severity"),
            AuditLog.performed_at.label("timestamp"),
            cast(AuditLog.asset_id, String).label("entity_id"),
            cast(AuditLog.actor_id, String).label("actor_id"),
            AuditLog.action_verb.label("title"),
            literal("").label("description"),
            AuditLog.immutable_payload.label("metadata"),
        )
        if entity_id is not None:
            stmt = stmt.where(AuditLog.asset_id == entity_id)
        return stmt

    def _telemetry_select(self, entity_id):
        stmt = select(
            cast(TelemetryMetric.metric_id, String).label("id"),
            literal("telemetry").label("type"),
            literal(SEVERITY_INFORMATION).label("severity"),
            TelemetryMetric.event_time.label("timestamp"),
            cast(TelemetryMetric.asset_id, String).label("entity_id"),
            null().cast(String).label("actor_id"),
            func.concat("CPU Utilization ", cast(TelemetryMetric.cpu_utilization, String), "%").label("title"),
            literal("").label("description"),
            TelemetryMetric.diagnostic_payload.label("metadata"),
        )
        if entity_id is not None:
            stmt = stmt.where(TelemetryMetric.asset_id == entity_id)
        return stmt

    def _winlog_select(self, entity_id):
        stmt = select(
            cast(WindowsEventLog.log_id, String).label("id"),
            literal("winlog").label("type"),
            WindowsEventLog.severity_level.label("severity"),
            WindowsEventLog.occurrence_time.label("timestamp"),
            cast(WindowsEventLog.asset_id, String).label("entity_id"),
            null().cast(String).label("actor_id"),
            func.concat("Windows Event ", cast(WindowsEventLog.event_id, String)).label("title"),
            literal("").label("description"),
            WindowsEventLog.evtx_metadata.label("metadata"),
        )
        if entity_id is not None:
            stmt = stmt.where(WindowsEventLog.asset_id == entity_id)
        return stmt

    @staticmethod
    def _build_event(row) -> TimelineEvent:
        metadata = row.metadata or {}
        description = row.description or ""
        if row.type == "audit" and isinstance(metadata, dict):
            previous_state = metadata.get("previous_state")
            new_state = metadata.get("new_state")
            if previous_state and new_state:
                description = f"Asset state transitioned from {previous_state} to {new_state}"

        return TimelineEvent(
            id=str(row.id),
            type=row.type,
            title=row.title,
            description=description,
            severity=row.severity or SEVERITY_INFORMATION,
            timestamp=row.timestamp,
            actor_id=uuid.UUID(row.actor_id) if row.actor_id else None,
            entity_id=uuid.UUID(row.entity_id) if row.entity_id else None,
            entity_type=ENTITY_TYPE,
            metadata=metadata,
        )