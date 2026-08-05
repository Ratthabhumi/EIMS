"""
==============================================================================
EIMS Automated Test Suite — Telemetry Redis Stream Event Broker
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 4 Section 7.3
==============================================================================
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from backend.domain.telemetry import (
    HeartbeatMetrics,
    AgentHeartbeatRequest,
    WinlogMetadata,
    AgentWinlogRequest,
    StubTelemetryStreamBroker,
    RedisTelemetryStreamBroker,
    TELEMETRY_STREAM_KEY,
    MAX_STREAM_LENGTH,
)
from backend.infrastructure.cache import AsynchronousCacheManager
from backend.core.config import settings


@pytest.fixture
def stub_broker():
    return StubTelemetryStreamBroker()


@pytest.fixture
def dummy_heartbeat():
    metrics = HeartbeatMetrics(cpu_utilization=25.0, ram_used_mb=4096, ram_total_mb=16384, disk_iops=150)
    return AgentHeartbeatRequest(agent_version="v1.2.4", metrics=metrics)


@pytest.fixture
def dummy_winlog():
    meta = WinlogMetadata(target_user_name="System", workstation_name="LAB-01", event_source="DiskDeleter")
    return AgentWinlogRequest(occurrence_time=datetime.now(timezone.utc), event_id=1001, severity="Information", event_channel="System", metadata=meta)


@pytest.mark.asyncio
async def test_stub_broker_heartbeat_ingestion(stub_broker, dummy_heartbeat):
    """Verifies instantaneous heartbeat queue processing and job sequence identifier formatting."""
    cert_hash = "a" * 64
    resp = await stub_broker.publish_heartbeat(dummy_heartbeat, cert_hash)
    
    assert resp.status == "accepted"
    assert "stub-" in resp.stream_job_id
    assert len(stub_broker.stream_buffer) == 1
    
    entry = stub_broker.stream_buffer[0]
    assert entry["event_type"] == "heartbeat"
    assert entry["cert_fingerprint"] == cert_hash
    
    # Assert JSON payload integrity
    payload_data = json.loads(entry["payload"])
    assert payload_data["metrics"]["cpu_utilization"] == 25.0


@pytest.mark.asyncio
async def test_stub_broker_winlog_ingestion_and_custom_metadata(stub_broker, dummy_winlog):
    """Verifies winlog streaming envelope captures extensible diagnostic metadata cleanly."""
    cert_hash = "b" * 64
    resp = await stub_broker.publish_winlog(dummy_winlog, cert_hash)
    
    assert resp.status == "accepted"
    assert len(stub_broker.stream_buffer) == 1
    entry = stub_broker.stream_buffer[0]
    assert entry["event_type"] == "winlog"
    
    data = json.loads(entry["payload"])
    assert data["event_id"] == 1001
    assert data["metadata"]["event_source"] == "DiskDeleter"


@pytest.mark.asyncio
async def test_redis_broker_xadd_execution():
    """Verifies RedisTelemetryStreamBroker calls XADD with strict maxlen=100k bound."""
    mock_redis = AsyncMock()
    mock_redis.xadd = AsyncMock(return_value="1722760000000-1")
    
    cache_mgr = AsynchronousCacheManager()
    cache_mgr._redis_client = mock_redis
    
    broker = RedisTelemetryStreamBroker(cache_mgr)
    metrics = HeartbeatMetrics(cpu_utilization=10.0, ram_used_mb=2048, ram_total_mb=8192, disk_iops=50)
    req = AgentHeartbeatRequest(agent_version="v1.0.0", metrics=metrics)
    
    cert_hash = "c" * 64
    resp = await broker.publish_heartbeat(req, cert_hash)
    
    assert resp.status == "accepted"
    assert resp.stream_job_id == "1722760000000-1"
    
    # Assert XADD was invoked with exact Core Law 4 specifications
    mock_redis.xadd.assert_called_once()
    call_kwargs = mock_redis.xadd.call_args.kwargs
    assert call_kwargs["name"] == TELEMETRY_STREAM_KEY
    assert call_kwargs["maxlen"] == MAX_STREAM_LENGTH
    assert call_kwargs["approximate"] is True
    assert call_kwargs["fields"]["event_type"] == "heartbeat"
    assert call_kwargs["fields"]["cert_fingerprint"] == cert_hash


def test_cache_namespace_validation_for_telemetry():
    """Verifies AsynchronousCacheManager._validate_namespace acknowledges eims:telemetry: as canonical."""
    cache_mgr = AsynchronousCacheManager()
    # Should execute cleanly without raising warnings or errors
    cache_mgr._validate_namespace("eims:telemetry:ingestion")
