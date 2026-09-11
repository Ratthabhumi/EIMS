"""
==============================================================================
EIMS Query Layer - Windows Event Log Search Provider
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from typing import Any
from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.asset_registry.models import InfrastructureAsset
from backend.domain.search.provider import SearchProvider, SearchResult
from backend.domain.telemetry.models import WindowsEventLog


class WindowsEventLogSearchProvider(SearchProvider):
    """
    Forensic security & diagnostic Windows Event Log search domain.
    Matches event IDs (e.g., 4625, 4624, 1102), severity levels, and
    extensible forensic parameters within `evtx_metadata`.
    """
    name = "winlog"

    async def search(self, db: AsyncSession, query: str, limit: int) -> list[SearchResult]:
        cleaned = query.strip()
        pattern = f"%{cleaned}%"

        conditions = [
            WindowsEventLog.severity_level.ilike(pattern),
            cast(WindowsEventLog.evtx_metadata, String).ilike(pattern),
        ]

        # Numeric query enables direct integer matching on canonical event_id
        if cleaned.isdigit():
            try:
                conditions.append(WindowsEventLog.event_id == int(cleaned))
            except ValueError:
                pass

        stmt = (
            select(WindowsEventLog, InfrastructureAsset.hostname)
            .outerjoin(InfrastructureAsset, WindowsEventLog.asset_id == InfrastructureAsset.asset_id)
            .where(or_(*conditions))
            .order_by(WindowsEventLog.occurrence_time.desc())
            .limit(limit)
        )

        rows = (await db.execute(stmt)).all()
        return [self._to_result(log, hostname, cleaned) for log, hostname in rows]

    @staticmethod
    def _to_result(log: WindowsEventLog, hostname: str | None, query: str) -> SearchResult:
        meta = log.evtx_metadata or {}
        user = meta.get("target_user_name") or meta.get("username")
        workstation = meta.get("workstation_name")
        src_ip = meta.get("source_network_ip")

        context_parts = []
        if hostname:
            context_parts.append(f"Host: {hostname}")
        elif workstation:
            context_parts.append(f"WS: {workstation}")
        if user:
            context_parts.append(f"User: {user}")
        if src_ip:
            context_parts.append(f"IP: {src_ip}")

        subtitle_prefix = " • ".join(context_parts) if context_parts else log.severity_level
        timestamp_str = log.occurrence_time.strftime("%Y-%m-%d %H:%M:%S") if log.occurrence_time else "n/a"

        event_name = _get_common_event_name(log.event_id)
        title = f"Windows Event {log.event_id} ({log.severity_level})"
        if event_name:
            title = f"Event {log.event_id} - {event_name}"

        return SearchResult(
            type="winlog",
            id=str(log.log_id),
            title=title,
            subtitle=f"{timestamp_str} • {subtitle_prefix}",
            url=f"/timeline?type=winlog&entity_id={log.asset_id}",
            timestamp=log.occurrence_time,
            relevance=WindowsEventLogSearchProvider._compute_relevance(log, query),
            result_kind="entity",
            metadata={
                "event_id": log.event_id,
                "severity": log.severity_level,
                "asset_id": str(log.asset_id),
                "hostname": hostname,
                "target_user_name": user,
                "source_network_ip": src_ip,
            },
        )

    @staticmethod
    def _compute_relevance(log: WindowsEventLog, query: str) -> float:
        lowered = query.lower()
        if query.isdigit() and int(query) == log.event_id:
            return 1.00
        if log.severity_level.lower() == lowered:
            return 0.90
        meta_str = str(log.evtx_metadata).lower()
        if lowered in meta_str:
            return 0.85
        return 0.75


def _get_common_event_name(event_id: int) -> str | None:
    common = {
        4624: "Successful Logon",
        4625: "Failed Logon (Security Alert)",
        4634: "Logoff",
        4648: "Explicit Credentials Logon",
        4672: "Special Privileges Assigned",
        4720: "User Account Created",
        1102: "Audit Log Cleared",
        7045: "New Service Installed",
    }
    return common.get(event_id)
