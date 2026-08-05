"""
==============================================================================
EIMS Telemetry Ingestion Modular Domain
Governed by EIMS Documentation System (EDS v1.0.0)
Source-Available All Rights Reserved Policy
==============================================================================
"""

from backend.domain.telemetry.schemas import (
    HeartbeatMetrics,
    AgentHeartbeatRequest,
    WinlogMetadata,
    AgentWinlogRequest,
    StreamIngestionResponse,
)
from backend.domain.telemetry.security import verify_mtls_fingerprint
from backend.domain.telemetry.broker import (
    AbstractTelemetryBroker,
    RedisTelemetryStreamBroker,
    StubTelemetryStreamBroker,
    TELEMETRY_STREAM_KEY,
    MAX_STREAM_LENGTH,
)
from backend.domain.telemetry.controller import telemetry_router, get_telemetry_broker

__all__ = [
    "HeartbeatMetrics",
    "AgentHeartbeatRequest",
    "WinlogMetadata",
    "AgentWinlogRequest",
    "StreamIngestionResponse",
    "verify_mtls_fingerprint",
    "AbstractTelemetryBroker",
    "RedisTelemetryStreamBroker",
    "StubTelemetryStreamBroker",
    "TELEMETRY_STREAM_KEY",
    "MAX_STREAM_LENGTH",
    "telemetry_router",
    "get_telemetry_broker",
]
