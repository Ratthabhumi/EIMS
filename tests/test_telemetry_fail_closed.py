"""Fail-closed contracts for production telemetry transport and persistence.

Synthetic and hermetic: no Docker, Redis, database, network, or real agent.
These tests deliberately use the non-stub broker to protect production paths.
"""
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend.domain.telemetry import AgentHeartbeatRequest, HeartbeatMetrics
from backend.domain.telemetry.broker import RedisTelemetryStreamBroker
from backend.domain.telemetry.worker import TelemetryStreamConsumer
from backend.infrastructure.cache import AsynchronousCacheManager
from backend.infrastructure.database import database_engine


def heartbeat():
    return AgentHeartbeatRequest(
        agent_version="test-agent",
        metrics=HeartbeatMetrics(
            cpu_utilization=12, ram_used_mb=1024, ram_total_mb=2048, disk_iops=3
        ),
    )


@pytest.mark.asyncio
async def test_production_broker_without_redis_must_not_claim_accepted():
    cache = AsynchronousCacheManager()
    broker = RedisTelemetryStreamBroker(cache)

    with pytest.raises(HTTPException) as error:
        await broker.publish_heartbeat(heartbeat(), "a" * 64)

    assert error.value.status_code == 503
    assert "temporarily unavailable" in str(error.value.detail).lower()


@pytest.mark.asyncio
async def test_production_broker_xadd_failure_must_not_claim_accepted():
    cache = AsynchronousCacheManager()
    cache._redis_client = AsyncMock()
    cache._redis_client.xadd.side_effect = ConnectionError("synthetic redis outage")
    broker = RedisTelemetryStreamBroker(cache)

    with pytest.raises(HTTPException) as error:
        await broker.publish_heartbeat(heartbeat(), "a" * 64)

    assert error.value.status_code == 503
    assert "synthetic redis outage" not in str(error.value.detail)


@pytest.mark.asyncio
async def test_successful_xadd_returns_real_stream_identifier():
    cache = AsynchronousCacheManager()
    cache._redis_client = AsyncMock()
    cache._redis_client.xadd.return_value = "1722760000000-1"
    broker = RedisTelemetryStreamBroker(cache)

    response = await broker.publish_heartbeat(heartbeat(), "a" * 64)

    assert response.status == "accepted"
    assert response.stream_job_id == "1722760000000-1"
    cache._redis_client.xadd.assert_awaited_once()


@pytest.mark.asyncio
async def test_non_stub_worker_must_not_ack_without_database(monkeypatch):
    """No database transaction means no successful ingestion; preserve cursor."""
    cache = AsynchronousCacheManager()
    broker = RedisTelemetryStreamBroker(cache)
    worker = TelemetryStreamConsumer(broker=broker)
    agent_fingerprint = "b" * 64
    worker.register_agent_mapping(agent_fingerprint, uuid.uuid4())
    worker._fetch_batch = AsyncMock(return_value=(
        [("1000-0", {
            "event_type": "heartbeat",
            "cert_fingerprint": agent_fingerprint,
            "payload": heartbeat().model_dump_json(),
        })],
        "eims:telemetry:ingestion",
        None,
    ))
    worker._ack_and_trim = AsyncMock()
    monkeypatch.setattr(database_engine, "get_session_maker", lambda: None)

    with pytest.raises(RuntimeError, match="[Dd]atabase.*unavailable"):
        await worker.process_batch(batch_size=1)

    worker._ack_and_trim.assert_not_awaited()
    assert worker._last_id == "0-0"
