"""Real Redis proof that a long telemetry batch keeps its consumer-group lease."""
import asyncio
import json
import os
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis
from sqlalchemy.engine import make_url

from backend.domain.telemetry import broker as broker_module
from backend.domain.telemetry import worker as worker_module
from backend.domain.telemetry.broker import RedisTelemetryStreamBroker
from backend.domain.telemetry.worker import TelemetryStreamConsumer
from backend.infrastructure.cache import AsynchronousCacheManager


@pytest.mark.asyncio
async def test_long_telemetry_batch_refreshes_lease_without_delivery_increment(monkeypatch):
    redis_url = os.getenv("EIMS_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("Explicit EIMS_TEST_REDIS_URL is required")
    target = make_url(redis_url)
    if target.host not in ("127.0.0.1", "localhost") or target.port != 56379:
        pytest.fail("Refusing lease acceptance: Redis must be the disposable local instance on port 56379")

    suffix = uuid.uuid4().hex
    stream_key = f"eims:telemetry:ingestion:{suffix}"
    dlq_key = f"eims:telemetry:dead-letter:{suffix}"
    group_name = f"eims-test-lease-{suffix}"
    fingerprint = uuid.uuid4().hex + uuid.uuid4().hex
    asset_id = uuid.uuid4()
    source_event_key = f"lease-test:{suffix}"
    redis1 = Redis.from_url(redis_url, decode_responses=False)
    redis2 = Redis.from_url(redis_url, decode_responses=False)
    cache1 = AsynchronousCacheManager()
    cache2 = AsynchronousCacheManager()
    cache1._redis_client = redis1
    cache2._redis_client = redis2
    task = None

    try:
        monkeypatch.setattr(worker_module, "TELEMETRY_STREAM_KEY", stream_key)
        monkeypatch.setattr(broker_module, "TELEMETRY_STREAM_KEY", stream_key)
        monkeypatch.setattr(broker_module, "TELEMETRY_DEAD_LETTER_STREAM_KEY", dlq_key)
        assert await redis1.ping()

        payload = {
            "agent_version": "v1.0.0",
            "timestamp": datetime.now(UTC).isoformat(),
            "metrics": {
                "cpu_utilization": 12.5,
                "ram_used_mb": 512,
                "ram_total_mb": 4096,
                "disk_iops": 50,
            },
        }
        await redis1.xadd(stream_key, {
            "event_type": "heartbeat",
            "cert_fingerprint": fingerprint,
            "source_event_key": source_event_key,
            "payload": json.dumps(payload),
        })

        broker1 = RedisTelemetryStreamBroker(
            cache1, consumer_name=f"lease-owner-{suffix[:8]}",
            group_name=group_name, reclaim_idle_ms=600,
        )
        broker2 = RedisTelemetryStreamBroker(
            cache2, consumer_name=f"lease-competitor-{suffix[:8]}",
            group_name=group_name, reclaim_idle_ms=600,
        )
        consumer = TelemetryStreamConsumer(broker=broker1)
        consumer.register_agent_mapping(fingerprint, asset_id)
        consumer._dispatch_outbox_safely = AsyncMock(return_value=0)
        monkeypatch.setattr(worker_module.database_engine, "get_session_maker", lambda: object())

        persist_entered = asyncio.Event()

        async def slow_persist(session_maker, records):
            persist_entered.set()
            await asyncio.sleep(1.8)
            return []

        consumer._persist_isolating = slow_persist
        task = asyncio.create_task(consumer.process_batch(batch_size=10))
        await asyncio.wait_for(persist_entered.wait(), timeout=5)

        # Without lease refresh, the 600ms idle threshold would expire during this delay.
        await asyncio.sleep(0.8)
        pending = await redis1.xpending_range(stream_key, group_name, "-", "+", 1)
        assert len(pending) == 1
        delivered = pending[0].get("times_delivered", pending[0].get(b"times_delivered"))
        idle_ms = pending[0].get("time_since_delivered", pending[0].get(b"time_since_delivered"))
        assert int(delivered) == 1, "XCLAIM JUSTID must not increment delivery count"
        assert int(idle_ms) < 600, "lease refresh must keep pending idle time below the reclaim threshold"

        competing_messages, _, error_signal = await broker2.fetch_stream_batch(stream_key, "0-0", 10)
        assert error_signal is None
        assert competing_messages == [], "a second consumer must not reclaim a live batch lease"

        assert await task == 1
        task = None
        assert await redis1.xlen(stream_key) == 0
        assert (await redis1.xpending(stream_key, group_name))["pending"] == 0
    finally:
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await redis1.delete(stream_key, dlq_key)
        await redis1.aclose()
        await redis2.aclose()
