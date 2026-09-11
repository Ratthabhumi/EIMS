"""
==============================================================================
EIMS Query Layer - Audit Log Search Provider (Sprint 10)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.asset_registry.models import AuditLog
from backend.domain.search.provider import SearchProvider, SearchResult


class AuditLogSearchProvider(SearchProvider):
    """
    Primary Global Search domain. Matches `action_verb` and forensic `immutable_payload`
    with partial/substring semantics and ranks exact matches ahead of prefix and substring hits.
    Results are ordered by the immutable execution timestamp.
    """
    name = "audit"

    async def search(self, db: AsyncSession, query: str, limit: int) -> list[SearchResult]:
        cleaned = query.strip()
        pattern = f"%{cleaned}%"
        stmt = (
            select(AuditLog)
            .where(
                or_(
                    AuditLog.action_verb.ilike(pattern),
                    cast(AuditLog.immutable_payload, String).ilike(pattern),
                )
            )
            .order_by(AuditLog.performed_at.desc())
            .limit(limit)
        )
        logs = (await db.execute(stmt)).scalars().all()
        return [self._to_result(log, cleaned) for log in logs]

    @staticmethod
    def _to_result(log: AuditLog, query: str) -> SearchResult:
        lowered = query.lower()
        verb_lower = log.action_verb.lower()
        payload = log.immutable_payload or {}

        if verb_lower == lowered:
            relevance = 1.00
        elif verb_lower.startswith(lowered):
            relevance = 0.90
        elif lowered in str(payload).lower():
            relevance = 0.85
        else:
            relevance = 0.80

        event_detail = payload.get("event") or payload.get("reason")
        time_str = log.performed_at.strftime("%Y-%m-%d %H:%M:%S") if log.performed_at else "n/a"
        subtitle = f"{time_str} • {event_detail}" if event_detail else f"Performed at {time_str}"

        dest_url = f"/timeline?type=audit&entity_id={log.asset_id}" if log.asset_id else "/timeline?type=audit"

        return SearchResult(
            type="audit",
            id=str(log.log_id),
            title=log.action_verb,
            subtitle=subtitle,
            url=dest_url,
            timestamp=log.performed_at,
            relevance=relevance,
            result_kind="entity",
            metadata={
                "actor_id": str(log.actor_id) if log.actor_id else None,
                "asset_id": str(log.asset_id) if log.asset_id else None,
                "detail": event_detail,
            },
        )