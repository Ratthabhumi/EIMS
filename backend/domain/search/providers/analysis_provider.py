"""
==============================================================================
EIMS Query Layer - Analysis History Search Provider (Sprint 10)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.search.provider import SearchProvider, SearchResult


class AnalysisSearchProvider(SearchProvider):
    """
    Secondary Global Search domain. Executes PostgreSQL full-text matching over
    the generated `search_vector` column when the Sprint 10 index migration has
    been applied; gracefully falls back to ILIKE matching across `event_id`,
    `description`, and `ai_summary` on un-migrated databases.
    """
    name = "analysis"

    async def search(self, db: AsyncSession, query: str, limit: int) -> list[SearchResult]:
        try:
            return await self._search_vector(db, query, limit)
        except Exception:
            return await self._fallback_ilike(db, query, limit)

    async def _search_vector(self, db: AsyncSession, query: str, limit: int) -> list[SearchResult]:
        stmt = text(
            """
            SELECT
                id, event_id, provider, parse_method, description, ai_summary, created_at,
                ts_rank(search_vector, plainto_tsquery('english', :q)) AS rank
            FROM analysis_history
            WHERE search_vector @@ plainto_tsquery('english', :q)
            ORDER BY rank DESC
            LIMIT :limit
            """
        )
        rows = (await db.execute(stmt, {"q": query, "limit": limit})).mappings().all()
        return [self._to_result(row, relevance=max(0.0, min(float(row["rank"] or 0.0), 1.0))) for row in rows]

    async def _fallback_ilike(self, db: AsyncSession, query: str, limit: int) -> list[SearchResult]:
        pattern = f"%{query}%"
        stmt = (
            select(AnalysisHistory)
            .where(
                or_(
                    AnalysisHistory.event_id == query,
                    AnalysisHistory.description.ilike(pattern),
                    AnalysisHistory.ai_summary.ilike(pattern),
                )
            )
            .order_by(AnalysisHistory.created_at.desc())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return [self._to_result(row, relevance=self._fallback_relevance(row, query)) for row in rows]

    @staticmethod
    def _to_result(row, relevance: float) -> SearchResult:
        title = row.description or f"Analysis #{row.id}"
        provider = getattr(row, "provider", None)
        return SearchResult(
            type="analysis",
            id=str(row.id),
            title=title,
            subtitle=provider or f"Analyzed at {row.created_at.isoformat() if row.created_at else 'n/a'}",
            url="/analyzer",
            timestamp=row.created_at,
            relevance=relevance,
            metadata={
                "event_id": row.event_id,
                "provider": provider,
                "parse_method": getattr(row, "parse_method", None),
            },
        )

    @staticmethod
    def _fallback_relevance(row, query: str) -> float:
        lowered = query.lower()
        if row.event_id and row.event_id == query:
            return 1.00
        text_hits = 0
        if row.description and lowered in row.description.lower():
            text_hits += 1
        if row.ai_summary and lowered in row.ai_summary.lower():
            text_hits += 1
        if text_hits >= 2:
            return 0.90
        if text_hits == 1:
            return 0.80
        return 0.60