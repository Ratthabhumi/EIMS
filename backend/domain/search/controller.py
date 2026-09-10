"""
==============================================================================
EIMS Query Layer - Global Search API Controller (Sprint 10)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from dataclasses import asdict
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.analyzer.auth import get_current_user
from backend.domain.asset_registry.schemas import PaginationMetadata
from backend.domain.search.providers import (
    AnalysisSearchProvider,
    AssetSearchProvider,
    AuditLogSearchProvider,
)
from backend.domain.search.registry import SearchProviderRegistry
from backend.domain.search.schemas import SearchResponse, SearchResultSchema
from backend.domain.search.service import GlobalSearchService
from backend.infrastructure.database import get_db_session

# Core Law 5 Section 5.2 strict adherence: No trailing slashes in route declarations
search_router = APIRouter(prefix="/api/v1", tags=["Global Search"])


def _build_default_registry() -> SearchProviderRegistry:
    """Constructs the canonical Sprint 10 SearchProvider registry (Asset, Audit, Analysis)."""
    registry = SearchProviderRegistry()
    registry.register(AssetSearchProvider())
    registry.register(AuditLogSearchProvider())
    registry.register(AnalysisSearchProvider())
    return registry


search_service = GlobalSearchService(_build_default_registry())


async def get_search_service() -> GlobalSearchService:
    """Dependency injection factory exposing the canonical Global Search orchestrator."""
    return search_service


@search_router.get(
    "/search",
    response_model=SearchResponse,
    status_code=200,
    summary="Cross-Domain Global Search",
    description="Returns normalized search results across Asset, AuditLog, and Analysis domains.",
)
async def global_search(
    q: str = Query(..., min_length=2, max_length=200, description="Search query string (minimum 2 characters)."),
    search_type: Optional[Literal["asset", "audit", "analysis"]] = Query(
        None, alias="type", description="Filter results by entity type."
    ),
    page: int = Query(1, ge=1, description="Requested page index offset."),
    limit: int = Query(20, ge=1, le=50, description="Max entities per pagination slice."),
    db: AsyncSession = Depends(get_db_session),
    service: GlobalSearchService = Depends(get_search_service),
    _user: str = Depends(get_current_user),
) -> SearchResponse:
    """
    Executes relevance-ranked cross-domain search and wraps the page slice
    within the canonical Core Law 5 Section 6.1 collection wrapper.
    """
    results, total_records = await service.global_search(
        db=db,
        query=q,
        search_type=search_type,
        page=page,
        limit=limit,
    )
    serialized_data = [SearchResultSchema(**asdict(result)) for result in results]
    pagination_block = PaginationMetadata(
        total_records=total_records,
        current_page=page,
        page_size=limit,
        next_page_cursor=None,
    )
    return SearchResponse(status="success", data=serialized_data, pagination=pagination_block)