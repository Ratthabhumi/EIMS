"""
==============================================================================
EIMS Telemetry Ingestion API Controllers & Edge Routing
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Section 7.1
Source-Available All Rights Reserved Policy
==============================================================================
"""

from fastapi import APIRouter, Depends, status
from backend.core.logger import get_logger
from backend.infrastructure.cache import get_cache_manager, AsynchronousCacheManager
from backend.domain.telemetry.schemas import (
    AgentHeartbeatRequest,
    AgentWinlogRequest,
    StreamIngestionResponse,
)
from backend.domain.telemetry.security import verify_mtls_fingerprint
from backend.domain.telemetry.broker import AbstractTelemetryBroker, RedisTelemetryStreamBroker

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
