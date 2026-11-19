"""
==============================================================================
EIMS Telemetry Ingestion API Controllers & Edge Routing
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Section 7.1
Source-Available All Rights Reserved Policy
==============================================================================
"""

import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status

from backend.core.logger import get_logger
from backend.domain.telemetry.broker import (
    AbstractTelemetryBroker,
    RedisTelemetryStreamBroker,
)
from backend.domain.telemetry.schemas import (
    AgentHeartbeatRequest,
    AgentWinlogRequest,
    StreamIngestionResponse,
)
from backend.domain.telemetry.security import verify_mtls_fingerprint
from backend.domain.telemetry.evtx_worker import EVTX_STREAM_KEY, MAX_EVTX_FILE_BYTES
from backend.infrastructure.cache import AsynchronousCacheManager, get_cache_manager
from backend.infrastructure.object_store import object_storage
from backend.domain.analyzer.auth import require_admin_or_token

logger = get_logger("eims.api.telemetry")
MAX_EVTX_UPLOAD_BYTES = MAX_EVTX_FILE_BYTES
EVTX_UPLOAD_READ_CHUNK_BYTES = 1024 * 1024


async def _enforce_evtx_upload_limit(file: UploadFile) -> int:
    """Count upload bytes with a hard cap, then rewind the spooled upload for MinIO."""
    total = 0
    while True:
        chunk = await file.read(min(EVTX_UPLOAD_READ_CHUNK_BYTES, MAX_EVTX_UPLOAD_BYTES - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_EVTX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="EVTX upload exceeds the 64 MiB limit.")
    await file.seek(0)
    return total


def _stable_ingestion_key(event_type: str, payload, cert_fingerprint: str) -> str:
    """Stable per-agent payload identity so HTTP retries do not duplicate telemetry rows."""
    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True,
                           separators=(",", ":"), ensure_ascii=False)
    material = "\x1f".join((event_type, cert_fingerprint.lower(), canonical))
    return "ingest:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


# Core Law 5 Section 5.2 strict adherence: No trailing slashes in route declarations
telemetry_router = APIRouter(prefix="/api/v1/telemetry", tags=["Telemetry Collector & Agent Ingestion"], dependencies=[Depends(require_admin_or_token)])


async def get_telemetry_broker(
    cache_manager: AsynchronousCacheManager = Depends(get_cache_manager)
) -> AbstractTelemetryBroker:
    """Dependency injection factory providing asynchronous Telemetry Broker instances."""
    return RedisTelemetryStreamBroker(cache_manager=cache_manager)


@telemetry_router.post(
    "/heartbeat",
    response_model=StreamIngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest Discovery Agent Heartbeat Metrics",
    description="Asynchronous edge route absorbing high-frequency diagnostic payloads under 15ms latency (REQ-DISC-03)."
)
async def ingest_agent_heartbeat(
    payload: AgentHeartbeatRequest,
    broker: AbstractTelemetryBroker = Depends(get_telemetry_broker),
    cert_fingerprint: str = Depends(verify_mtls_fingerprint)
) -> StreamIngestionResponse:
    """
    Validates physical metric constraints via Pydantic and asserts mTLS identity
    before enqueueing envelope directly into Redis Event Stream buffer.
    """
    logger.debug(f"Edge heartbeat received from agent '{payload.agent_version}' (SHA-256: {cert_fingerprint[:8]}...)")
    return await broker.publish_heartbeat(
        payload=payload, cert_fingerprint=cert_fingerprint,
        source_event_key=_stable_ingestion_key("heartbeat", payload, cert_fingerprint),
    )


@telemetry_router.post(
    "/winlog",
    response_model=StreamIngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest Diagnostic Windows Event Log Streams",
    description="Ingestion route receiving native .evtx strings and extensible forensic anomalies captured during Windows Log Analysis."
)
async def ingest_windows_event_log(
    payload: AgentWinlogRequest,
    broker: AbstractTelemetryBroker = Depends(get_telemetry_broker),
    cert_fingerprint: str = Depends(verify_mtls_fingerprint)
) -> StreamIngestionResponse:
    """
    Accepts extensible forensic diagnostic metadata and streams directly into Redis buffer for background workers.
    """
    logger.debug(f"Edge winlog received (Event ID: {payload.event_id}, Channel: {payload.event_channel})")
    return await broker.publish_winlog(
        payload=payload, cert_fingerprint=cert_fingerprint,
        source_event_key=_stable_ingestion_key("winlog", payload, cert_fingerprint),
    )


@telemetry_router.post(
    "/upload/evtx",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload Binary Windows Event Log (.evtx)",
    description="Ingest raw binary .evtx files for background parsing and IoC anomaly detection."
)
async def upload_windows_evtx(
    file: UploadFile = File(..., description="Raw binary .evtx file"),
    x_client_cert_fingerprint: str = Depends(verify_mtls_fingerprint),
    cache_manager: AsynchronousCacheManager = Depends(get_cache_manager)
) -> dict:
    """
    Stores the EVTX object and confirms a durable Redis Stream job before 202.
    """
    logger.info("Received EVTX upload request from Edge Agent: %s...", x_client_cert_fingerprint[:8])
    
    if not (file.filename or "").lower().endswith(".evtx") and file.content_type not in ["application/octet-stream", "application/x-winevt"]:
        raise HTTPException(status_code=415, detail="Unsupported Media Type. Must be a .evtx file.")
    await _enforce_evtx_upload_limit(file)

    job_id = uuid.uuid4().hex
    try:
        minio_uri = await object_storage.upload_file(file.file, file.filename, file.content_type or "application/octet-stream")
        logger.info(f"Successfully streamed file {file.filename} to {minio_uri}")
    except Exception as e:
        logger.error(f"MinIO streaming fault: {e!s}")
        raise HTTPException(status_code=502, detail="Storage Gateway Fault")
        
    # Redis Stream entries remain pending until the consumer commits all derived events.
    # The worker migrates any legacy list entries without destructive popping.
    try:
        stream_id = await cache_manager.xadd_queue(
            EVTX_STREAM_KEY, {"job_id": job_id, "minio_uri": minio_uri,
             "uploader_fingerprint": x_client_cert_fingerprint}
        )
        if not stream_id:
            raise RuntimeError("EVTX stream write was not confirmed")
    except Exception:
        # The MinIO object may now be orphaned. No automatic deletion is
        # attempted because queue-write outcome can be ambiguous.
        logger.error("EVTX queue publication unconfirmed after object upload")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="EVTX processing queue temporarily unavailable",
            headers={"Retry-After": "5"},
        ) from None

    return {
        "status": "processing",
        "message": "EVTX file accepted for asynchronous parsing",
        "task_id": job_id,
        "stream_id": stream_id,
        "minio_uri": minio_uri
    }
