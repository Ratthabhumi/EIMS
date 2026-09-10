"""
==============================================================================
EIMS Query Layer - Search Provider Abstraction (Sprint 10)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class SearchResult:
    """
    Normalized cross-domain search result contract (Architecture §6.5).
    Every candidate returned by any SearchProvider must conform to this
    canonical shape so orchestrators can merge heterogeneous sources safely.
    """
    type: str
    id: str
    title: str
    subtitle: str
    url: str
    timestamp: Optional[datetime]
    relevance: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SearchProvider(ABC):
    """
    Abstract contract every EIMS searchable domain implements to integrate with
    the Global Search orchestrator without altering core orchestration logic.
    """

    name: str = ""

    @abstractmethod
    async def search(self, db: AsyncSession, query: str, limit: int) -> list[SearchResult]:
        """
        Executes domain-specific matching against the supplied query string and
        returns up to `limit` results ordered by descending relevance.
        """