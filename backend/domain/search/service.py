"""
==============================================================================
EIMS Query Layer - Global Search Orchestrator Service (Sprint 10)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger import get_logger
from backend.domain.search.provider import SearchResult
from backend.domain.search.registry import SearchProviderRegistry

logger = get_logger("eims.query.search")


class GlobalSearchService:
    """
    Distributes every search request across all registered SearchProviders,
    merges normalized results, and applies a deterministic relevance-ranked
    ordering before slicing the page window.
    """
    def __init__(self, registry: SearchProviderRegistry) -> None:
        self._registry = registry

    async def global_search(
        self,
        db: AsyncSession,
        query: str,
        search_type: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[SearchResult], int]:
        """
        Executes bounded per-provider searches under an aggregated budget
        (`page * limit`) so deep pagination never explodes source queries,
        then returns the sorted page slice and the inspected hit count.
        """
        budget = page * limit
        providers = self._registry.find(search_type)

        collected: list[SearchResult] = []
        for provider in providers:
            try:
                collected.extend(await provider.search(db=db, query=query, limit=budget))
            except Exception as exc:  # Provider fault isolation
                logger.warning(f"Provider '{provider.name}' search fault suppressed: {exc}")
                continue

        collected.sort(key=lambda result: result.relevance, reverse=True)
        total_records = len(collected)
        start = (page - 1) * limit
        return collected[start:start + limit], total_records