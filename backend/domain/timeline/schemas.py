"""
==============================================================================
EIMS Query Layer - Unified Timeline API Schemas (Sprint 10)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from backend.domain.asset_registry.schemas import PaginationMetadata


class TimelineEvent(BaseModel):
    """Unified chronological event representation aggregated from domain tables."""
    id: str = Field(..., description="Source record identifier.")
    type: str = Field(..., description="Event source type literal (audit, telemetry, winlog).")
    title: str = Field(..., description="Primary display title.")
    description: str = Field(..., description="Human-readable event summary.")
    severity: str = Field(..., description="Severity classification literal.")
    timestamp: datetime = Field(..., description="Event occurrence timestamp (UTC).")
    actor_id: Optional[UUID] = Field(None, description="Operator or agent identifier responsible for the event.")
    entity_id: Optional[UUID] = Field(None, description="Related asset/entity identifier.")
    entity_type: str = Field("asset", description="Related entity classification.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extensible source-specific context.")


class TimelineResponse(BaseModel):
    """Canonical collection wrapper for unified Timeline responses (Core Law 5 §6.1)."""
    status: str = Field("success", description="Standard API status response flag.")
    data: list[TimelineEvent] = Field(..., description="Chronologically ordered event list.")
    pagination: PaginationMetadata = Field(..., description="Accurate collection slice tracking metrics.")