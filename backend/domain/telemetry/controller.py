"""
==============================================================================
EIMS Telemetry Ingestion API Controllers & Edge Routing
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Section 7.1
Source-Available All Rights Reserved Policy
==============================================================================
"""

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
from backend.infrastructure.cache import AsynchronousCacheManager, get_cache_manager
from backend.infrastructure.object_store import object_storage

logger = get_logger("eims.api.telemetry")

# Core Law 5 Section 5.2 strict adherence: No trailing slashes in route declarations
telemetry_router = APIRouter(prefix="/api/v1/telemetry", tags=["Telemetry Collector & Agent Ingestion"])


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
    return await broker.publish_heartbeat(payload=payload, cert_fingerprint=cert_fingerprint)


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
    return await broker.publish_winlog(payload=payload, cert_fingerprint=cert_fingerprint)


@telemetry_router.post(
    "/upload/evtx",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload Binary Windows Event Log (.evtx)",
    description="Ingest raw binary .evtx files for background parsing and IoC anomaly detection."
)
async def upload_windows_evtx(
    file: UploadFile = File(..., description="Raw binary .evtx file"),
    x_client_cert_fingerprint: str = Header(..., description="mTLS Client Certificate SHA-256 Fingerprint"),
    broker: AbstractTelemetryBroker = Depends(get_telemetry_broker)
) -> dict:
    """
    Accepts raw binary .evtx file, streams to MinIO, and creates an asynchronous 'Pending' EVTX parsing task.
    """
    logger.info(f"Received EVTX upload request from Edge Agent: {x_client_cert_fingerprint}")
    
    if not file.filename.endswith(".evtx") and file.content_type not in ["application/octet-stream", "application/x-winevt"]:
        raise HTTPException(status_code=415, detail="Unsupported Media Type. Must be a .evtx file.")
        
    try:
        minio_uri = await object_storage.upload_file(file.file, file.filename, file.content_type or "application/octet-stream")
        logger.info(f"Successfully streamed file {file.filename} to {minio_uri}")
    except Exception as e:
        logger.error(f"MinIO streaming fault: {e!s}")
        raise HTTPException(status_code=502, detail="Storage Gateway Fault")
        
    job_id = uuid.uuid4().hex
    # Enqueue EVTX parsing job in Redis (list)
    await broker.cache_manager.redis.lpush("eims:jobs:evtx", minio_uri)
    
    return {
        "status": "processing",
        "message": "EVTX file accepted for asynchronous parsing",
        "task_id": job_id,
        "minio_uri": minio_uri
    }
