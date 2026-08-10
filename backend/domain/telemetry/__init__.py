"""
==============================================================================
EIMS Telemetry Ingestion Modular Domain
Governed by EIMS Documentation System (EDS v1.0.0)
Source-Available All Rights Reserved Policy
==============================================================================
"""

from backend.domain.telemetry.broker import (
    MAX_STREAM_LENGTH,
    TELEMETRY_STREAM_KEY,
    AbstractTelemetryBroker,
    RedisTelemetryStreamBroker,
    StubTelemetryStreamBroker,
)
from backend.domain.telemetry.controller import get_telemetry_broker, telemetry_router
from backend.domain.telemetry.models import TelemetryMetric, WindowsEventLog
from backend.domain.telemetry.schemas import (
    AgentHeartbeatRequest,
    AgentWinlogRequest,
    HeartbeatMetrics,
    StreamIngestionResponse,
    WinlogMetadata,
)
from backend.domain.telemetry.security import verify_mtls_fingerprint
from backend.domain.telemetry.worker import TelemetryStreamConsumer

__all__ = [
    "MAX_STREAM_LENGTH",
    "TELEMETRY_STREAM_KEY",
    "AbstractTelemetryBroker",
    "AgentHeartbeatRequest",
    "AgentWinlogRequest",
    "HeartbeatMetrics",
    "RedisTelemetryStreamBroker",
    "StreamIngestionResponse",
    "StubTelemetryStreamBroker",
    "TelemetryMetric",
    "TelemetryStreamConsumer",
    "WindowsEventLog",
    "WinlogMetadata",
    "get_telemetry_broker",
    "telemetry_router",
    "verify_mtls_fingerprint",
]
