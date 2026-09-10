"""
==============================================================================
EIMS Query Layer - Global Search Modular Domain (Sprint 10)
Governed by EIMS Documentation System (EDS v1.0.0)
Source-Available All Rights Reserved Policy
==============================================================================
"""

from backend.domain.search.registry import SearchProviderRegistry
from backend.domain.search.provider import SearchProvider, SearchResult
from backend.domain.search.service import GlobalSearchService
from backend.domain.search.schemas import SearchResponse, SearchResultSchema
from backend.domain.search.controller import get_search_service, search_router

__all__ = [
    "SearchProvider",
    "SearchProviderRegistry",
    "SearchResult",
    "GlobalSearchService",
    "SearchResponse",
    "SearchResultSchema",
    "get_search_service",
    "search_router",
]