"""
==============================================================================
EIMS Asset Registry Domain Pydantic Schemas
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AssetCreateRequest(BaseModel):
    """Payload parameter schema required for initiating asset enrollment."""
    hostname: str = Field(..., max_length=255, description="Registered OS networking hostname.")
    canonical_ip: str = Field(..., max_length=45, description="Primary IPv4/IPv6 networking address.")
    cryptographic_fingerprint: str = Field(
        ..., min_length=64, max_length=64, description="SHA-256 derivation of immutable hardware serial strings."
    )


class AssetTransitionRequest(BaseModel):
    """Payload parameters commanding an administrative state mutation."""
    lifecycle_state: str = Field(..., description="Target state machine literal (e.g., Quarantined, Decommissioned).")
    operator_rationale: str = Field(
        "Automated API state transition execution",
        description="Justification string recorded inside immutable audit trails."
    )


class AssetResponse(BaseModel):
    """Authoritative API serialization representation of an Infrastructure Asset entity."""
    model_config = ConfigDict(from_attributes=True)

    asset_id: uuid.UUID = Field(..., description="Universally unique canonical EIMS asset identifier.")
    hostname: str = Field(..., description="Registered operating system networking hostname.")
    canonical_ip: str = Field(..., description="Primary networking IP address associated with the asset.")
    cryptographic_fingerprint: str = Field(..., description="SHA-256 derived hardware unique signature.")
    lifecycle_state: str = Field(..., description="Active state machine literal.")
    current_compliance_score: int = Field(..., ge=0, le=100, description="Computed structural hardening score.")
    created_at: Optional[datetime] = Field(None, description="Record initial ingestion timestamp (UTC).")
    updated_at: Optional[datetime] = Field(None, description="Timestamp of most recent attribute mutation.")
    offline_report_data: Optional[dict] = Field(None, description="Full raw JSON report uploaded from offline Auditor tools.")


class PaginationMetadata(BaseModel):
    """Canonical Core Law 5 Section 6.1 pagination descriptor block."""
    total_records: int = Field(..., description="Aggregate record count matching query parameters.")
    current_page: int = Field(..., description="Active enumeration offset index.")
    page_size: int = Field(..., description="Maximum entities allocated per page slice.")
    next_page_cursor: Optional[str] = Field(None, description="Cryptographic string encoded for cursor resumption.")


class AssetListResponse(BaseModel):
    """Canonical collection wrapper schema protecting memory buffer throughput during lists."""
    status: str = Field("success", description="Standard API status response flag.")
    data: List[AssetResponse] = Field(..., description="Array of serialized Infrastructure Asset representations.")
    pagination: PaginationMetadata = Field(..., description="Accurate collection slice tracking metrics.")
