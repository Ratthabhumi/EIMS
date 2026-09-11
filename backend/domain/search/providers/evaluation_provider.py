"""
==============================================================================
EIMS Query Layer - Service Evaluation Search Provider
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.evaluation.models import ServiceSession
from backend.domain.search.provider import SearchProvider, SearchResult


class EvaluationSearchProvider(SearchProvider):
    """
    Business evaluation search provider indexing service sessions, customer names,
    assigned engineers, and operational service descriptions.
    """
    name = "evaluation"

    async def search(self, db: AsyncSession, query: str, limit: int) -> list[SearchResult]:
        cleaned = query.strip()
        pattern = f"%{cleaned}%"

        stmt = (
            select(ServiceSession)
            .where(
                or_(
                    ServiceSession.title.ilike(pattern),
                    ServiceSession.customer_name.ilike(pattern),
                    ServiceSession.engineer_name.ilike(pattern),
                    ServiceSession.description.ilike(pattern),
                )
            )
            .order_by(ServiceSession.created_at.desc())
            .limit(limit)
        )

        sessions = (await db.execute(stmt)).scalars().all()
        return [self._to_result(sess, cleaned) for sess in sessions]

    @staticmethod
    def _to_result(sess: ServiceSession, query: str) -> SearchResult:
        subtitle_parts = []
        if sess.customer_name:
            subtitle_parts.append(f"Client: {sess.customer_name}")
        if sess.engineer_name:
            subtitle_parts.append(f"Eng: {sess.engineer_name}")
        if not subtitle_parts and sess.description:
            subtitle_parts.append(sess.description[:60])

        relevance = EvaluationSearchProvider._compute_relevance(sess, query)

        return SearchResult(
            type="evaluation",
            id=str(sess.session_id),
            title=f"Evaluation: {sess.title}",
            subtitle=" • ".join(subtitle_parts) if subtitle_parts else "Service Session",
            url=f"/evaluations/admin/{sess.session_id}",
            timestamp=sess.created_at,
            relevance=relevance,
            result_kind="entity",
            metadata={
                "session_id": str(sess.session_id),
                "customer": sess.customer_name,
                "engineer": sess.engineer_name,
            },
        )

    @staticmethod
    def _compute_relevance(sess: ServiceSession, query: str) -> float:
        lowered = query.lower()
        if sess.title.lower() == lowered:
            return 1.00
        if sess.title.lower().startswith(lowered):
            return 0.92
        if sess.customer_name and lowered in sess.customer_name.lower():
            return 0.88
        if sess.engineer_name and lowered in sess.engineer_name.lower():
            return 0.85
        return 0.75
