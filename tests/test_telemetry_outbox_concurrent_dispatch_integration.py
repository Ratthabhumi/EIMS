"""Real PostgreSQL + Redis proof of at-least-once outbox dispatch under concurrency."""
import asyncio
import os
import re
import uuid
from datetime import UTC, datetime

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.domain.telemetry import worker as worker_module
from backend.domain.telemetry.models import TelemetryAlertOutbox
from backend.domain.telemetry.worker import TelemetryStreamConsumer
from backend.infrastructure.cache import cache_manager


SCHEMA_PATTERN = re.compile(r"eims_full_lineage_[0-9a-f]{32}")


@pytest.mark.asyncio
async def test_two_dispatchers_can_publish_same_alert_id_but_keep_one_outbox_row(monkeypatch):
    database_url = os.getenv("EIMS_TEST_DATABASE_URL")
    redis_url = os.getenv("EIMS_TEST_REDIS_URL")
    schema = os.getenv("EIMS_TEST_SCHEMA")
    if not all((database_url, redis_url, schema)):
        pytest.skip("Explicit disposable PostgreSQL, Redis and EIMS_TEST_SCHEMA settings are required")

    db_target = make_url(database_url)
    redis_target = make_url(redis_url)
    if (db_target.host not in ("127.0.0.1", "localhost")
            or db_target.port != 56441 or db_target.database != "eims_evtx_acceptance"):
        pytest.fail("Refusing outbox acceptance: PostgreSQL must be the disposable local DB on port 56441")
    if redis_target.host not in ("127.0.0.1", "localhost") or redis_target.port != 56379:
        pytest.fail("Refusing outbox acceptance: Redis must be the disposable local instance on port 56379")
    if not SCHEMA_PATTERN.fullmatch(schema):
        pytest.fail("EIMS_TEST_SCHEMA must identify a dedicated eims_full_lineage_<32 hex> rehearsal schema")

    engine = create_async_engine(
        database_url,
        poolclass=NullPool,
        connect_args={
            "prepared_statement_cache_size": 0,
            "server_settings": {"search_path": f"{schema},public"},
        },
    )
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis_client = Redis.from_url(redis_url, decode_responses=False)
    suffix = uuid.uuid4().hex
    alert_id = uuid.uuid4()
    stream_key = f"eims:telemetry:alerts:{suffix}"
    channel = f"eims:telemetry:alerts:live:{suffix}"
    release_xadd = asyncio.Event()
    first_xadd = asyncio.Event()
    both_xadds = asyncio.Event()
    xadd_calls = 0
    tasks = []

    try:
        async with engine.connect() as conn:
            version = await conn.scalar(text("SELECT version_num FROM alembic_version"))
        assert version == "a3d6f1e8c295"
        assert await redis_client.ping()

        async with session_maker() as session:
            async with session.begin():
                session.add(TelemetryAlertOutbox(
                    alert_id=alert_id,
                    payload={"event_type": "SYNTHETIC_OUTBOX_CONCURRENCY", "severity": "Low"},
                    created_at=datetime.now(UTC),
                ))

        monkeypatch.setattr(worker_module, "ALERT_STREAM_KEY", stream_key)
        monkeypatch.setattr(worker_module, "ALERT_CHANNEL", channel)
        monkeypatch.setattr(cache_manager, "_redis_client", redis_client)
        original_xadd = redis_client.xadd

        async def pause_until_both_dispatchers_selected(*args, **kwargs):
            nonlocal xadd_calls
            xadd_calls += 1
            if xadd_calls == 1:
                first_xadd.set()
            if xadd_calls == 2:
                both_xadds.set()
            await asyncio.wait_for(release_xadd.wait(), timeout=8)
            return await original_xadd(*args, **kwargs)

        monkeypatch.setattr(redis_client, "xadd", pause_until_both_dispatchers_selected)
        dispatcher_a = TelemetryStreamConsumer()
        dispatcher_b = TelemetryStreamConsumer()

        tasks.append(asyncio.create_task(dispatcher_a.dispatch_outbox(session_maker)))
        await asyncio.wait_for(first_xadd.wait(), timeout=5)
        # Dispatcher A has released its SELECT/FOR UPDATE transaction but has not XADD'd/stamped.
        tasks.append(asyncio.create_task(dispatcher_b.dispatch_outbox(session_maker)))
        await asyncio.wait_for(both_xadds.wait(), timeout=5)
        release_xadd.set()

        results = await asyncio.gather(*tasks)
        assert results == [1, 1]

        entries = await redis_client.xrange(stream_key)
        assert len(entries) == 2, "at-least-once dispatch may publish the same alert more than once"
        published_ids = []
        for _, fields in entries:
            value = fields.get(b"alert_id") or fields.get("alert_id")
            published_ids.append(value.decode() if isinstance(value, bytes) else str(value))
        assert published_ids == [str(alert_id), str(alert_id)]

        async with session_maker() as session:
            rows = list((await session.execute(
                select(TelemetryAlertOutbox).where(TelemetryAlertOutbox.alert_id == alert_id)
            )).scalars())
        assert len(rows) == 1
        assert rows[0].published_at is not None
    finally:
        release_xadd.set()
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        try:
            async with session_maker() as session:
                async with session.begin():
                    await session.execute(
                        delete(TelemetryAlertOutbox).where(TelemetryAlertOutbox.alert_id == alert_id)
                    )
        except Exception:
            pass
        await redis_client.delete(stream_key)
        await redis_client.aclose()
        await engine.dispose()
