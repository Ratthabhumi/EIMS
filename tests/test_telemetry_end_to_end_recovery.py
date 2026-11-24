"""Real Redis + PostgreSQL crash/restart acceptance; only runs with explicit test URLs."""
import json
import os
import re
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.domain.asset_registry.models import InfrastructureAsset
from backend.domain.telemetry import worker as worker_module
from backend.domain.telemetry.broker import RedisTelemetryStreamBroker
from backend.domain.telemetry.models import TelemetryMetric, WindowsEventLog
from backend.domain.telemetry.worker import TelemetryStreamConsumer
from backend.infrastructure.cache import AsynchronousCacheManager


@pytest.mark.asyncio
async def test_commit_then_ack_failure_replays_without_duplicate_rows(monkeypatch):
    database_url = os.getenv("EIMS_TEST_DATABASE_URL")
    redis_url = os.getenv("EIMS_TEST_REDIS_URL")
    schema = os.getenv("EIMS_TEST_SCHEMA")
    if not database_url or not redis_url:
        pytest.skip("Explicit EIMS_TEST_DATABASE_URL and EIMS_TEST_REDIS_URL are required")
    if not schema:
        pytest.fail("EIMS_TEST_SCHEMA must name a completed isolated migration rehearsal schema")
    if not re.fullmatch(r"eims_full_lineage_[0-9a-f]{32}", schema):
        pytest.fail("Refusing integration test: EIMS_TEST_SCHEMA must name an isolated full-lineage rehearsal schema")

    engine = create_async_engine(
        database_url, poolclass=NullPool,
        connect_args={"prepared_statement_cache_size": 0, "server_settings": {"search_path": schema}},
    )
    # Fail early if this schema is not the actual Alembic-head rehearsal.
    async with engine.connect() as conn:
        version = await conn.scalar(text("SELECT version_num FROM alembic_version"))
        indexes = set((await conn.execute(text(
            "SELECT indexname FROM pg_indexes WHERE schemaname=:schema "
            "AND indexname IN ('uq_telemetry_metrics_source_event_key', "
            "'uq_windows_event_logs_source_event_key', 'idx_winlog_4625_src_ip_time')"
        ), {"schema": schema})).scalars())
    if version != "a3d6f1e8c295" or len(indexes) != 3:
        await engine.dispose()
        pytest.fail(f"Isolated telemetry schema is not migration-complete: head={version}, required_indexes={sorted(indexes)}")

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis_client = Redis.from_url(redis_url, decode_responses=True)
    suffix = uuid.uuid4().hex
    asset_id = uuid.uuid4()
    fingerprint = suffix * 2
    metric_key = f"integration:heartbeat:{suffix}"
    winlog_key = f"integration:winlog:{suffix}"
    stream_key = f"eims:test:telemetry:{suffix}"
    group_name = f"eims-test-consumer-{suffix}"
    monkeypatch.setattr(worker_module, "TELEMETRY_STREAM_KEY", stream_key)
    monkeypatch.setattr(worker_module.database_engine, "get_session_maker", lambda: session_maker)

    try:
        async with session_maker() as session:
            async with session.begin():
                session.add(InfrastructureAsset(
                    asset_id=asset_id, hostname=f"eims-test-{suffix[:12]}",
                    canonical_ip="192.0.2.10", cryptographic_fingerprint=fingerprint,
                ))

        now = datetime.now(UTC).isoformat()
        heartbeat = {
            "agent_version": "v1.0.0", "timestamp": now,
            "metrics": {"cpu_utilization": 12.5, "ram_used_mb": 512,
                        "ram_total_mb": 4096, "disk_iops": 50},
        }
        winlog = {
            "occurrence_time": now, "event_id": 1129, "severity": "Warning",
            "event_channel": "System", "metadata": {"workstation_name": "EIMS-SYNTHETIC"},
        }
        await redis_client.xadd(stream_key, {
            "event_type": "heartbeat", "cert_fingerprint": fingerprint,
            "source_event_key": metric_key, "payload": json.dumps(heartbeat),
        })
        await redis_client.xadd(stream_key, {
            "event_type": "winlog", "cert_fingerprint": fingerprint,
            "source_event_key": winlog_key, "payload": json.dumps(winlog),
        })

        cache = AsynchronousCacheManager()
        cache._redis_client = redis_client
        first_broker = RedisTelemetryStreamBroker(
            cache, consumer_name=f"crashed-{suffix[:8]}", group_name=group_name, reclaim_idle_ms=0,
        )
        first = TelemetryStreamConsumer(broker=first_broker)
        first.register_agent_mapping(fingerprint, asset_id)
        first._ack_and_trim = AsyncMock(side_effect=ConnectionError("synthetic post-commit ACK failure"))

        with pytest.raises(ConnectionError, match="post-commit ACK failure"):
            await first.process_batch(batch_size=10)

        async with session_maker() as session:
            metric_count = await session.scalar(select(func.count()).select_from(TelemetryMetric).where(
                TelemetryMetric.source_event_key == metric_key))
            winlog_count = await session.scalar(select(func.count()).select_from(WindowsEventLog).where(
                WindowsEventLog.source_event_key == winlog_key))
        assert metric_count == 1 and winlog_count == 1
        pending_after_crash = await redis_client.xpending(stream_key, group_name)
        assert pending_after_crash["pending"] == 2

        restarted_broker = RedisTelemetryStreamBroker(
            cache, consumer_name=f"restarted-{suffix[:8]}", group_name=group_name, reclaim_idle_ms=0,
        )
        restarted = TelemetryStreamConsumer(broker=restarted_broker)
        restarted.register_agent_mapping(fingerprint, asset_id)
        assert await restarted.process_batch(batch_size=10) == 2

        async with session_maker() as session:
            metric_count = await session.scalar(select(func.count()).select_from(TelemetryMetric).where(
                TelemetryMetric.source_event_key == metric_key))
            winlog_count = await session.scalar(select(func.count()).select_from(WindowsEventLog).where(
                WindowsEventLog.source_event_key == winlog_key))
        assert metric_count == 1 and winlog_count == 1
        assert await redis_client.xlen(stream_key) == 0
        assert (await redis_client.xpending(stream_key, group_name))["pending"] == 0
    finally:
        try:
            async with session_maker() as session:
                async with session.begin():
                    await session.execute(delete(TelemetryMetric).where(TelemetryMetric.source_event_key == metric_key))
                    await session.execute(delete(WindowsEventLog).where(WindowsEventLog.source_event_key == winlog_key))
                    await session.execute(delete(InfrastructureAsset).where(InfrastructureAsset.asset_id == asset_id))
        finally:
            await redis_client.delete(stream_key)
            await redis_client.aclose()
            await engine.dispose()
