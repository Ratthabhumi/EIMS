"""
==============================================================================
EIMS Asset Registry Domain Module
Governed by EIMS Documentation System (EDS v1.0.0)
Source-Available All Rights Reserved Policy
==============================================================================
"""

from backend.domain.asset_registry.models import InfrastructureAsset, HardwareInventory, AuditLog
from backend.domain.asset_registry.state_machine import AssetState, AssetLifecycleStateMachine
from backend.domain.asset_registry.repository import AssetRepository, ASSET_CACHE_KEY_PREFIX, ASSET_CACHE_TTL_SECONDS
from backend.domain.asset_registry.schemas import (
    AssetCreateRequest,
    AssetTransitionRequest,
    AssetResponse,
    AssetListResponse,
    PaginationMetadata,
)
from backend.domain.asset_registry.controller import asset_router, get_asset_repository

__all__ = [
    "InfrastructureAsset",
    "HardwareInventory",
    "AuditLog",
    "AssetState",
    "AssetLifecycleStateMachine",
    "AssetRepository",
    "ASSET_CACHE_KEY_PREFIX",
    "ASSET_CACHE_TTL_SECONDS",
    "AssetCreateRequest",
    "AssetTransitionRequest",
    "AssetResponse",
    "AssetListResponse",
    "PaginationMetadata",
    "asset_router",
    "get_asset_repository",
]
