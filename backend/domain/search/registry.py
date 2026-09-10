"""
==============================================================================
EIMS Query Layer - Search Provider Registry (Sprint 10)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from typing import List, Optional

from backend.domain.search.provider import SearchProvider


class SearchProviderRegistry:
    """
    Aggregation container mapping canonical provider names to concrete
    SearchProvider instances, enabling filterable dispatch by entity type.
    """
    def __init__(self) -> None:
        self._providers: dict[str, SearchProvider] = {}

    def register(self, provider: SearchProvider) -> None:
        """Registers a provider under its canonical `name` key."""
        if not provider.name:
            raise ValueError("SearchProvider must declare a non-empty provider name.")
        self._providers[provider.name] = provider

    def get(self, name: str) -> Optional[SearchProvider]:
        """Returns the provider registered under `name` or None."""
        return self._providers.get(name)

    def find(self, search_type: Optional[str]) -> List[SearchProvider]:
        """
        Returns all registered providers when `search_type` is None, otherwise the
        single provider matching the requested entity type filter.
        """
        if search_type is None:
            return list(self._providers.values())
        provider = self._providers.get(search_type)
        return [provider] if provider is not None else []

    def __iter__(self):
        return iter(self._providers.values())