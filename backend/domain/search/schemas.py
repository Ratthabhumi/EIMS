"""
==============================================================================
EIMS Query Layer - Global Search API Schemas (Sprint 10)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.domain.asset_registry.schemas import PaginationMetadata


class SearchResultSchema(BaseModel):
    """Canonical serialization representation of a normalized search result."""
    type: str = Field(..., description="Entity type identifier (asset, audit, analysis).")
    id: str = Field(..., description="UUID (or integer) of the matched entity.")
    title: str = Field(..., description="Primary display name.")
    subtitle: str = Field(..., description="Secondary information (state, date, severity).")
    url: str = Field(..., description="Canonical frontend route for navigation.")
    timestamp: Optional[datetime] = Field(None, description="When the entity was created or updated (UTC).")
    relevance: float = Field(default=0.0, ge=0.0, le=1.0, description="0.0-1.0 relevance score.")
    result_kind: str = Field(default="entity", description="Result category: navigation or entity.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional flexible context.")


class SearchResponse(BaseModel):
    """Canonical collection wrapper for Global Search responses (Core Law 5 §6.1)."""
    status: str = Field("success", description="Standard API status response flag.")
    data: List[SearchResultSchema] = Field(..., description="Normalized search results.")
    pagination: PaginationMetadata = Field(..., description="Accurate collection slice tracking metrics.")