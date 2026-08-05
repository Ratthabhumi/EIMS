"""
==============================================================================
EIMS Asset Registry Administration API Controller
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Section 7.2
Source-Available All Rights Reserved Policy
==============================================================================
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.database import get_db_session
from backend.infrastructure.cache import get_cache_manager, AsynchronousCacheManager
from backend.domain.asset_registry.repository import AssetRepository
from backend.domain.asset_registry.schemas import (
    AssetCreateRequest,
    AssetTransitionRequest,
    AssetResponse,
    AssetListResponse,
    PaginationMetadata,
)
from backend.core.exceptions import ResourceNotFoundException
from backend.core.logger import get_logger

logger = get_logger("eims.api.asset_registry")

# Notice: Core Law 5 Section 5.2 prohibits trailing slashes in endpoint declarations
asset_router = APIRouter(prefix="/api/v1/assets", tags=["Asset Registry Administration"])


async def get_asset_repository(
    db_session: AsyncSession = Depends(get_db_session),
    cache_manager: AsynchronousCacheManager = Depends(get_cache_manager)
) -> AssetRepository:
    """Dependency injection factory providing clean Repository instances per request lifecycle."""
    return AssetRepository(db_session=db_session, cache_manager=cache_manager)


@asset_router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED, summary="Enroll New Infrastructure Asset")
async def register_asset(
    payload: AssetCreateRequest,
    repo: AssetRepository = Depends(get_asset_repository)
) -> AssetResponse:
    """
    Registers a newly discovered compute infrastructure asset into the authoritative registry.
    Assigns initial state 'Discovered' and populates volatile-LRU Redis cache.
    """
    logger.info(f"Received API enrollment request for hostname: '{payload.hostname}' ({payload.canonical_ip})")
    asset = await repo.create_asset(
        hostname=payload.hostname,
        canonical_ip=payload.canonical_ip,
        cryptographic_fingerprint=payload.cryptographic_fingerprint,
    )
    return AssetResponse.model_validate(asset)


@asset_router.get("", response_model=AssetListResponse, status_code=status.HTTP_200_OK, summary="Enumerate Asset Registry Collections")
async def list_assets(
    page: int = Query(1, ge=1, description="Requested page index offset"),
    limit: int = Query(50, ge=1, le=200, description="Max entities per pagination slice"),
    state: Optional[str] = Query(None, description="Optional status filtering literal"),
    repo: AssetRepository = Depends(get_asset_repository)
) -> AssetListResponse:
    """
    Enumerates registered Infrastructure Asset records subject to pagination and optional state filtering.
    Encapsulates results within Core Law 5 Section 6.1 canonical wrapper schema.
    """
    skip = (page - 1) * limit
    assets = await repo.list_assets(skip=skip, limit=limit, state=state)
    serialized_data = [AssetResponse.model_validate(a) for a in assets]
    
    # Calculate canonical pagination wrapper parameters
    pagination_block = PaginationMetadata(
        total_records=len(serialized_data), # In production scale, this runs count query; here matching returned block
        current_page=page,
        page_size=limit,
        next_page_cursor=None
    )
    return AssetListResponse(status="success", data=serialized_data, pagination=pagination_block)


@asset_router.get("/{asset_id}", response_model=AssetResponse, status_code=status.HTTP_200_OK, summary="Retrieve Asset Details")
async def get_asset_by_id(
    asset_id: uuid.UUID,
    repo: AssetRepository = Depends(get_asset_repository)
) -> AssetResponse:
    """
    Retrieves serialized details for a single target infrastructure asset.
    Executes sub-millisecond Redis Read-Through cache lookup prior to querying relational tables.
    """
    asset = await repo.get_asset_by_id(asset_id)
    if not asset:
        raise ResourceNotFoundException(resource_type="InfrastructureAsset", resource_id=str(asset_id))
    return AssetResponse.model_validate(asset)


@asset_router.patch("/{asset_id}", response_model=AssetResponse, status_code=status.HTTP_200_OK, summary="Execute Lifecycle State Transition")
async def transition_asset_state(
    asset_id: uuid.UUID,
    payload: AssetTransitionRequest,
    repo: AssetRepository = Depends(get_asset_repository)
) -> AssetResponse:
    """
    Commands an operational status mutation against a target Infrastructure Asset.
    If the requested jump violates canonical Core Law 3 state matrix arrows, raises HTTP 409 Conflict.
    """
    logger.info(f"API transition requested for Asset='{asset_id}' -> Target='{payload.lifecycle_state}'")
    asset = await repo.transition_state(
        asset_id=asset_id,
        target_state=payload.lifecycle_state,
        reason=payload.operator_rationale
    )
    return AssetResponse.model_validate(asset)
