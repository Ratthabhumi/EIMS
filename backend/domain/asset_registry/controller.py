"""
==============================================================================
EIMS Asset Registry Administration API Controller
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Section 7.2
Source-Available All Rights Reserved Policy
==============================================================================
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status, UploadFile, File, Header, HTTPException, Form
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
from backend.domain.asset_registry.models import OCRRegistrationRecord
from backend.infrastructure.object_store import object_storage

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


@asset_router.post("/ocr-upload", status_code=status.HTTP_202_ACCEPTED, summary="Upload Image for OCR Asset Registration")
async def upload_ocr_image(
    file: UploadFile = File(..., description="Multipart image payload (e.g. Server Invoice, BIOS Sticker)"),
    serial_number: Optional[str] = Form(None, description="Pre-extracted Serial Number"),
    device_id: Optional[str] = Form(None, description="Pre-extracted Device ID"),
    error_message: Optional[str] = Form(None, description="Error message from desktop client"),
    x_client_cert_fingerprint: str = Header(..., description="mTLS Client Certificate SHA-256 Fingerprint"),
    repo: AssetRepository = Depends(get_asset_repository)
) -> dict:
    """
    Core Law 4 Section 6.2 Multipart Ingestion.
    Accepts physical asset image, streams to MinIO, and uses client-provided OCR or creates async task.
    """
    logger.info(f"Received OCR upload request from Edge Agent: {x_client_cert_fingerprint}")
    
    # 1. Validate MIME type
    if file.content_type not in ["image/jpeg", "image/png", "application/pdf"]:
        raise HTTPException(status_code=415, detail="Unsupported Media Type. Must be JPEG, PNG, or PDF.")
        
    # 2. Stream to MinIO Storage Backend
    try:
        minio_uri = await object_storage.upload_file(file.file, file.filename, file.content_type)
        logger.info(f"Successfully streamed file {file.filename} to {minio_uri}")
    except Exception as e:
        logger.error(f"MinIO streaming fault: {str(e)}")
        raise HTTPException(status_code=502, detail="Storage Gateway Fault")
        
    # 3. Create Async OCR Workflow Record via Repository
    if error_message:
        from backend.domain.asset_registry.models import OCRRegistrationRecord
        tracking_record = OCRRegistrationRecord(
            minio_object_uri=minio_uri,
            extraction_status="Failed",
            parsed_raw_text={"error": error_message}
        )
        repo.db_session.add(tracking_record)
        await repo.db_session.commit()
        await repo.db_session.refresh(tracking_record)
    elif serial_number and device_id:
        import hashlib
        from backend.domain.asset_registry.models import OCRRegistrationRecord
        fingerprint = hashlib.sha256(serial_number.encode()).hexdigest()
        existing = await repo.get_asset_by_fingerprint(fingerprint)
        if not existing:
            asset = await repo.create_asset(
                hostname=f"hw-{serial_number.lower()}",
                canonical_ip="0.0.0.0",
                cryptographic_fingerprint=fingerprint
            )
        else:
            asset = existing
            
        tracking_record = OCRRegistrationRecord(
            minio_object_uri=minio_uri,
            extraction_status="Completed",
            parsed_raw_text={"extracted_sn": serial_number, "extracted_did": device_id},
            asset_id=asset.asset_id
        )
        repo.db_session.add(tracking_record)
        await repo.db_session.commit()
        await repo.db_session.refresh(tracking_record)
    else:
        tracking_record = await repo.create_ocr_registration(minio_uri=minio_uri)
    
    return {
        "status": "success",
        "message": "Image accepted",
        "task_id": str(tracking_record.record_id),
        "minio_uri": minio_uri,
        "extraction_status": tracking_record.extraction_status
    }


from backend.domain.asset_registry.schemas import OCRRegistrationListResponse, OCRRegistrationRecordResponse

@asset_router.get("/ocr-history", response_model=OCRRegistrationListResponse, status_code=status.HTTP_200_OK, summary="Retrieve OCR Upload History")
async def list_ocr_history(
    page: int = Query(1, ge=1, description="Requested page index offset"),
    limit: int = Query(50, ge=1, le=200, description="Max entities per pagination slice"),
    repo: AssetRepository = Depends(get_asset_repository)
) -> OCRRegistrationListResponse:
    """
    Retrieves the history of Sticker OCR scans uploaded to the backend.
    """
    skip = (page - 1) * limit
    records = await repo.list_ocr_records(skip=skip, limit=limit)
    serialized_data = [OCRRegistrationRecordResponse.model_validate(r) for r in records]
    
    pagination_block = PaginationMetadata(
        total_records=len(serialized_data),
        current_page=page,
        page_size=limit,
        next_page_cursor=None
    )
    return OCRRegistrationListResponse(status="success", data=serialized_data, pagination=pagination_block)

@asset_router.delete("/ocr-history", status_code=status.HTTP_200_OK, summary="Clear OCR Upload History")
async def clear_ocr_history(
    repo: AssetRepository = Depends(get_asset_repository)
) -> dict:
    """Clears all history of Sticker OCR scans uploaded to the backend."""
    await repo.clear_ocr_records()
    return {"status": "success", "message": "OCR history cleared"}


from fastapi.responses import Response

@asset_router.get("/ocr-history/image", summary="Stream OCR Scan Image")
async def stream_ocr_image(uri: str = Query(..., description="MinIO S3 Object URI")):
    """
    Streams the raw image bytes from MinIO for frontend visualization.
    """
    if not uri.startswith("s3://"):
        raise HTTPException(status_code=400, detail="Invalid object URI format.")
        
    try:
        file_data = await object_storage.download_file(uri)
        return Response(content=file_data["body"], media_type=file_data["content_type"])
    except Exception as e:
        logger.error(f"Failed to stream image {uri}: {str(e)}")
        raise HTTPException(status_code=404, detail="Image not found or inaccessible")

@asset_router.post("/import-report", response_model=AssetResponse, status_code=status.HTTP_200_OK, summary="Import Offline USB Auditor Report")
async def import_offline_report(
    file: UploadFile = File(..., description="JSON Report from USB Auditor"),
    repo: AssetRepository = Depends(get_asset_repository)
) -> AssetResponse:
    """
    Ingests an offline JSON report generated by the USB Auditor agent.
    Creates or updates the asset record and sets its compliance score.
    """
    import json
    try:
        content = await file.read()
        report_data = json.loads(content)
    except Exception as e:
        logger.error(f"Failed to parse offline report: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid JSON format")

    try:
        asset = await repo.upsert_offline_report(report_data)
        logger.info(f"Successfully imported offline report for {asset.hostname}")
        return AssetResponse.model_validate(asset)
    except Exception as e:
        logger.error(f"Failed to upsert offline report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
