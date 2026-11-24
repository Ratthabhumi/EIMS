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


@pytest.mark.asyncio
async def test_restart_after_sql_commit_before_ack_does_not_duplicate(monkeypatch):
    """Expected contract; currently broken by replay of the same stream ID."""
    monkeypatch.setattr(database_engine, "get_session_maker", lambda: object())
    fingerprint, message = _message()
    broker = RedisTelemetryStreamBroker(AsynchronousCacheManager())
    persisted_by_key = {}

    async def persist(_session_maker, metrics, winlogs, *_unused):
        # Model the PostgreSQL unique source_event_key constraint used by _persist_batch.
        for metric in metrics:
            persisted_by_key.setdefault(metric.source_event_key, metric.metric_id)

    before_crash = _consumer(broker, fingerprint, message)
    before_crash._persist_batch = AsyncMock(side_effect=persist)
    before_crash._ack_and_trim = AsyncMock(
        side_effect=RuntimeError("synthetic crash after SQL commit")
    )
    with pytest.raises(RuntimeError, match="synthetic crash after SQL commit"):
        await before_crash.process_batch()
    assert len(persisted_by_key) == 1
    assert before_crash._last_id == "0-0"

    # Fresh worker has no durable cursor; same Redis entry is replayed.
    after_restart = _consumer(broker, fingerprint, message)
    after_restart._persist_batch = AsyncMock(side_effect=persist)
    assert await after_restart.process_batch() == 1

    assert len(persisted_by_key) == 1
    assert next(iter(persisted_by_key)) == after_restart.processed_metrics[0].source_event_key


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


@pytest.mark.asyncio
async def test_poison_telemetry_is_dead_lettered_before_ack():
    from backend.domain.telemetry.broker import StubTelemetryStreamBroker

    broker = StubTelemetryStreamBroker()
    broker.stream_buffer.append({
        "sequence_id": "stub-poison-1", "event_type": "unknown",
        "cert_fingerprint": "f" * 64, "payload": "not-json",
    })
    consumer = TelemetryStreamConsumer(broker=broker)

    assert await consumer.process_batch(batch_size=1) == 0
    assert broker.stream_buffer == []
    assert len(broker.dead_letter_buffer) == 1
    assert broker.dead_letter_buffer[0]["source_stream_id"] == "stub-poison-1"


@pytest.mark.asyncio
async def test_malformed_utf8_stream_fields_are_dead_lettered_without_decode_loss():
    from backend.domain.telemetry.broker import StubTelemetryStreamBroker

    broker = StubTelemetryStreamBroker()
    broker.stream_buffer.append({
        "sequence_id": "stub-poison-bytes-1",
        b"event_type": b"winlog",
        b"cert_fingerprint": b"f" * 64,
        b"payload": b"\xff\xfe{",
    })
    consumer = TelemetryStreamConsumer(broker=broker)

    assert await consumer.process_batch(batch_size=1) == 0
    assert broker.stream_buffer == []
    assert len(broker.dead_letter_buffer) == 1
    dead = broker.dead_letter_buffer[0]
    assert dead["reason"] == "undecodable-queue-field"
    assert dead["source_stream_id"] == "stub-poison-bytes-1"
    assert dead["entry"]["payload"].startswith("base64:")
    assert dead["entry"]["undecodable_fields"]
