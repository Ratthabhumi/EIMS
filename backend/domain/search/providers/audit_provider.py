"""
==============================================================================
EIMS Query Layer - Audit Log Search Provider (Sprint 10)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.asset_registry.models import AuditLog
from backend.domain.search.provider import SearchProvider, SearchResult


class AuditLogSearchProvider(SearchProvider):
    """
    Primary Global Search domain. Matches `action_verb` with partial/substring
    semantics and ranks exact matches ahead of prefix and substring hits.
    Results are ordered by the immutable execution timestamp.
    """
    name = "audit"

    async def search(self, db: AsyncSession, query: str, limit: int) -> list[SearchResult]:
        pattern = f"%{query}%"
        stmt = (
            select(AuditLog)
            .where(AuditLog.action_verb.ilike(pattern))
            .order_by(AuditLog.performed_at.desc())
            .limit(limit)
        )
        logs = (await db.execute(stmt)).scalars().all()
        return [self._to_result(log, query) for log in logs]

    @staticmethod
    def _to_result(log: AuditLog, query: str) -> SearchResult:
        lowered = query.lower()
        verb_lower = log.action_verb.lower()
        if verb_lower == lowered:
            relevance = 1.00
        elif verb_lower.startswith(lowered):
            relevance = 0.90
        else:
            relevance = 0.80

        return SearchResult(
            type="audit",
            id=str(log.log_id),
            title=log.action_verb,
            subtitle=f"Performed at {log.performed_at.isoformat() if log.performed_at else 'n/a'}",
            url="/timeline",
            timestamp=log.performed_at,
            relevance=relevance,
            metadata={
                "actor_id": str(log.actor_id) if log.actor_id else None,
                "asset_id": str(log.asset_id) if log.asset_id else None,
            },
        )