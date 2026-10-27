"""Synthetic worker crash/restart fault-injection contracts.

No Redis/SQL sockets. xfail(strict=True) tracks known delivery gaps instead
of misrepresenting them as implemented reliability guarantees.
"""
import uuid
from unittest.mock import AsyncMock

import pytest

from backend.domain.telemetry import AgentHeartbeatRequest, HeartbeatMetrics
from backend.domain.telemetry.broker import RedisTelemetryStreamBroker, TELEMETRY_STREAM_KEY
from backend.domain.telemetry.worker import TelemetryStreamConsumer
from backend.infrastructure.cache import AsynchronousCacheManager
from backend.infrastructure.database import database_engine


def _message():
    fingerprint = "d" * 64
    heartbeat = AgentHeartbeatRequest(
        agent_version="synthetic",
        metrics=HeartbeatMetrics(
            cpu_utilization=9, ram_used_mb=100, ram_total_mb=1000, disk_iops=1
        ),
    )
    return fingerprint, ("1000-0", {
        "event_type": "heartbeat",
        "cert_fingerprint": fingerprint,
        "payload": heartbeat.model_dump_json(),
    })


def _consumer(broker, fingerprint, message):
    consumer = TelemetryStreamConsumer(broker=broker)
    consumer.register_agent_mapping(fingerprint, uuid.UUID("00000000-0000-0000-0000-000000000001"))
    consumer._fetch_batch = AsyncMock(return_value=([message], TELEMETRY_STREAM_KEY, None))
    consumer._ack_and_trim = AsyncMock()
    return consumer


@pytest.mark.asyncio
async def test_crash_before_sql_commit_preserves_message_for_restart(monkeypatch):
    """A failed transaction must not advance the cursor or acknowledge an event."""
    monkeypatch.setattr(database_engine, "get_session_maker", lambda: object())
    fingerprint, message = _message()
    broker = RedisTelemetryStreamBroker(AsynchronousCacheManager())
    before_crash = _consumer(broker, fingerprint, message)
    before_crash._persist_batch = AsyncMock(side_effect=RuntimeError("synthetic rollback"))

    with pytest.raises(RuntimeError, match="synthetic rollback"):
        await before_crash.process_batch()
    assert before_crash._last_id == "0-0"
    before_crash._ack_and_trim.assert_not_awaited()

    after_restart = _consumer(broker, fingerprint, message)
    after_restart._persist_batch = AsyncMock()
    assert await after_restart.process_batch() == 1
    after_restart._persist_batch.assert_awaited_once()
    after_restart._ack_and_trim.assert_awaited_once()
    assert after_restart._last_id == "1000-0"


@pytest.mark.xfail(strict=True, reason="XREAD cursor is in-memory; no SQL stream-ID dedup on restart")
@pytest.mark.asyncio
async def test_restart_after_sql_commit_before_ack_does_not_duplicate(monkeypatch):
    """Expected contract; currently broken by replay of the same stream ID."""
    monkeypatch.setattr(database_engine, "get_session_maker", lambda: object())
    fingerprint, message = _message()
    broker = RedisTelemetryStreamBroker(AsynchronousCacheManager())
    persisted_ids = []

    async def persist(_session_maker, metrics, winlogs, anomalies):
        persisted_ids.extend(m.metric_id for m in metrics)

    before_crash = _consumer(broker, fingerprint, message)
    before_crash._persist_batch = AsyncMock(side_effect=persist)
    assert await before_crash.process_batch() == 1

    # Fresh worker has no durable cursor; same Redis entry is replayed.
    after_restart = _consumer(broker, fingerprint, message)
    after_restart._persist_batch = AsyncMock(side_effect=persist)
    assert await after_restart.process_batch() == 1

    assert len(persisted_ids) == 1


@pytest.mark.xfail(strict=True, reason="Current _ack_and_trim swallows broker ACK failures")
@pytest.mark.asyncio
async def test_ack_failure_prevents_worker_from_advancing_cursor(monkeypatch):
    """Expected contract; ACK errors must not be silently treated as success."""
    monkeypatch.setattr(database_engine, "get_session_maker", lambda: object())
    fingerprint, message = _message()
    broker = RedisTelemetryStreamBroker(AsynchronousCacheManager())
    broker.ack_stream_messages = AsyncMock(side_effect=ConnectionError("synthetic ACK fault"))
    consumer = _consumer(broker, fingerprint, message)
    consumer._persist_batch = AsyncMock()
    # Use the real ACK path, but no Redis instance or trim.
    del consumer._ack_and_trim
    consumer._ensure_redis = AsyncMock(return_value=None)

    with pytest.raises(ConnectionError, match="synthetic ACK fault"):
        await consumer.process_batch()
    assert consumer._last_id == "0-0"
