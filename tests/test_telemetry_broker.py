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
    """Verifies RedisTelemetryStreamBroker never trims unacknowledged entries at publish time."""
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
    assert "maxlen" not in call_kwargs
    assert "approximate" not in call_kwargs
    assert call_kwargs["fields"]["event_type"] == "heartbeat"
    assert call_kwargs["fields"]["cert_fingerprint"] == cert_hash


def test_cache_namespace_validation_for_telemetry():
    """Verifies AsynchronousCacheManager._validate_namespace acknowledges eims:telemetry: as canonical."""
    cache_mgr = AsynchronousCacheManager()
    # Should execute cleanly without raising warnings or errors
    cache_mgr._validate_namespace("eims:telemetry:ingestion")


@pytest.mark.asyncio
async def test_redis_broker_reclaims_pending_before_reading_new_entries():
    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock()
    pending = ("1722760000000-1", {"event_type": "heartbeat", "payload": "{}"})
    mock_redis.xautoclaim = AsyncMock(return_value=("0-0", [pending], []))
    mock_redis.xreadgroup = AsyncMock(return_value=[])
    cache = AsynchronousCacheManager()
    cache._redis_client = mock_redis
    broker = RedisTelemetryStreamBroker(cache, consumer_name="restarted-worker", reclaim_idle_ms=0)

    messages, key, error = await broker.fetch_stream_batch(TELEMETRY_STREAM_KEY, "0-0", 10)

    assert error is None and key == TELEMETRY_STREAM_KEY
    assert messages == [pending]
    mock_redis.xgroup_create.assert_awaited_once()
    mock_redis.xautoclaim.assert_awaited_once()
    mock_redis.xreadgroup.assert_not_awaited()


@pytest.mark.asyncio
async def test_ack_failure_is_propagated_and_never_silently_accepted():
    mock_redis = AsyncMock()
    mock_redis.xack = AsyncMock(side_effect=ConnectionError("synthetic ACK fault"))
    cache = AsynchronousCacheManager()
    cache._redis_client = mock_redis
    broker = RedisTelemetryStreamBroker(cache)

    with pytest.raises(ConnectionError, match="synthetic ACK fault"):
        await broker.ack_stream_messages(TELEMETRY_STREAM_KEY, ["1722760000000-1"])
    mock_redis.xdel.assert_not_awaited()


@pytest.mark.asyncio
async def test_ack_deletes_only_after_confirmed_group_ack():
    mock_redis = AsyncMock()
    mock_redis.xack = AsyncMock(return_value=1)
    mock_redis.xdel = AsyncMock(return_value=1)
    cache = AsynchronousCacheManager()
    cache._redis_client = mock_redis
    broker = RedisTelemetryStreamBroker(cache)

    await broker.ack_stream_messages(TELEMETRY_STREAM_KEY, ["1722760000000-1"])

    mock_redis.xack.assert_awaited_once_with(TELEMETRY_STREAM_KEY, broker.group_name, "1722760000000-1")
    mock_redis.xdel.assert_awaited_once_with(TELEMETRY_STREAM_KEY, "1722760000000-1")


@pytest.mark.asyncio
async def test_cache_stream_client_preserves_raw_bytes_but_string_cache_reads_decode(monkeypatch):
    from backend.infrastructure import cache as cache_module

    redis_client = AsyncMock()
    redis_client.get = AsyncMock(return_value=b'{"ok":true}')
    factory = patch.object(cache_module.redis, "from_url", return_value=redis_client)
    with factory as from_url:
        cache = AsynchronousCacheManager()
        await cache.initialize()
        assert from_url.call_args.kwargs["decode_responses"] is False
        assert await cache.get_value("eims:asset:synthetic") == '{"ok":true}'


@pytest.mark.asyncio
async def test_redis_broker_preserves_raw_stream_field_bytes_for_dlq_decoding():
    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock()
    mock_redis.xautoclaim = AsyncMock(return_value=("0-0", [], []))
    mock_redis.xreadgroup = AsyncMock(return_value=[[
        TELEMETRY_STREAM_KEY, [(b"1722760000000-9", {b"payload": b"\\xff\\xfe{"})]
    ]])
    cache = AsynchronousCacheManager()
    cache._redis_client = mock_redis
    broker = RedisTelemetryStreamBroker(cache)

    messages, _, error = await broker.fetch_stream_batch(TELEMETRY_STREAM_KEY, "0-0", 1)

    assert error is None
    assert messages == [("1722760000000-9", {b"payload": b"\\xff\\xfe{"})]
