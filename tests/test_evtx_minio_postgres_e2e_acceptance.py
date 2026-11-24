"""Real MinIO + Redis + PostgreSQL EVTX ingestion and replay acceptance.

This test is deliberately opt-in and refuses non-local/non-disposable endpoints.
"""
import io
import os
import re
import uuid
from urllib.parse import unquote, urlparse

import pytest
from botocore.exceptions import ClientError
from fastapi import UploadFile
from redis.asyncio import Redis
from sqlalchemy import delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.core.config import settings
from backend.domain.asset_registry.models import InfrastructureAsset
from backend.domain.telemetry import broker as broker_module
from backend.domain.telemetry import controller as controller_module
from backend.domain.telemetry import evtx_worker as evtx_module
from backend.domain.telemetry import worker as telemetry_worker_module
from backend.domain.telemetry.evtx_worker import EVTXBackgroundWorker
from backend.domain.telemetry.models import WindowsEventLog
from backend.domain.telemetry.worker import TelemetryStreamConsumer
from backend.infrastructure.cache import AsynchronousCacheManager
from backend.infrastructure.object_store import MinIOStorageManager


FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "evtx", "system.evtx")
FIXTURE_SHA256 = "ccb83cfefc9038017224cd97b800b66e248fe14529649ddf47907e5a2021449e"
SCHEMA_PATTERN = re.compile(r"eims_full_lineage_[0-9a-f]{32}")


@pytest.mark.asyncio
async def test_real_evtx_upload_minio_redis_workers_postgres_and_ack_replay(monkeypatch):
    database_url = os.getenv("EIMS_TEST_DATABASE_URL")
    redis_url = os.getenv("EIMS_TEST_REDIS_URL")
    minio_endpoint = os.getenv("EIMS_TEST_MINIO_ENDPOINT")
    minio_access_key = os.getenv("EIMS_TEST_MINIO_ACCESS_KEY")
    minio_secret_key = os.getenv("EIMS_TEST_MINIO_SECRET_KEY")
    schema = os.getenv("EIMS_TEST_SCHEMA")
    if not all((database_url, redis_url, minio_endpoint, minio_access_key, minio_secret_key, schema)):
        pytest.skip("Explicit disposable PostgreSQL, Redis, MinIO and EIMS_TEST_SCHEMA settings are required")

    db_target = make_url(database_url)
    redis_target = make_url(redis_url)
    if (db_target.host not in ("127.0.0.1", "localhost")
            or db_target.port != 56441 or db_target.database != "eims_evtx_acceptance"):
        pytest.fail("Refusing EVTX acceptance: PostgreSQL must be the disposable local eims_evtx_acceptance DB on port 56441")
    if redis_target.host not in ("127.0.0.1", "localhost") or redis_target.port != 56379:
        pytest.fail("Refusing EVTX acceptance: Redis must be the disposable local instance on port 56379")
    if minio_endpoint not in ("127.0.0.1:59000", "localhost:59000"):
        pytest.fail("Refusing EVTX acceptance: MinIO must be the disposable local instance on port 59000")
    if not SCHEMA_PATTERN.fullmatch(schema):
        pytest.fail("EIMS_TEST_SCHEMA must identify a dedicated eims_full_lineage_<32 hex> rehearsal schema")

    fixture_bytes = open(FIXTURE, "rb").read()
    import hashlib
    assert hashlib.sha256(fixture_bytes).hexdigest() == FIXTURE_SHA256

    engine = create_async_engine(
        database_url,
        poolclass=NullPool,
        connect_args={
            "prepared_statement_cache_size": 0,
            "server_settings": {"search_path": f"{schema},public"},
        },
    )
    redis_client = Redis.from_url(redis_url, decode_responses=False)
    cache = AsynchronousCacheManager()
    cache._redis_client = redis_client
    storage = None
    object_key = None
    asset_id = uuid.uuid4()
    fingerprint = uuid.uuid4().hex + uuid.uuid4().hex
    suffix = uuid.uuid4().hex
    evtx_stream = f"eims:jobs:evtx:stream:{suffix}"
    evtx_dlq = f"eims:jobs:evtx:dead-letter:{suffix}"
    legacy_stream = f"eims:jobs:evtx:{suffix}"
    telemetry_stream = f"eims:telemetry:ingestion:{suffix}"
    telemetry_dlq = f"eims:telemetry:dead-letter:{suffix}"
    group_name = f"eims-test-telemetry-{suffix}"
    bucket = os.getenv("EIMS_TEST_MINIO_BUCKET", "eims-evtx-e2e")
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with engine.connect() as conn:
            version = await conn.scalar(text("SELECT version_num FROM alembic_version"))
            indexes = set((await conn.execute(text(
                "SELECT indexname FROM pg_indexes WHERE schemaname=:schema AND indexname IN "
                "('uq_windows_event_logs_source_event_key','idx_winlog_4625_src_ip_time')"
            ), {"schema": schema})).scalars())
        assert version == "a3d6f1e8c295"
        assert indexes == {"uq_windows_event_logs_source_event_key", "idx_winlog_4625_src_ip_time"}
        assert await redis_client.ping()

        monkeypatch.setattr(settings, "MINIO_ENDPOINT", minio_endpoint)
        monkeypatch.setattr(settings, "MINIO_ACCESS_KEY", minio_access_key)
        monkeypatch.setattr(settings, "MINIO_SECRET_KEY", minio_secret_key)
        monkeypatch.setattr(settings, "MINIO_BUCKET_NAME", bucket)
        monkeypatch.setattr(settings, "MINIO_SECURE", False)
        storage = MinIOStorageManager()
        try:
            storage.s3_client.head_bucket(Bucket=bucket)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code not in ("404", "NoSuchBucket", "NotFound"):
                raise
            storage.s3_client.create_bucket(Bucket=bucket)

        monkeypatch.setattr(controller_module, "object_storage", storage)
        monkeypatch.setattr(evtx_module, "object_storage", storage)
        monkeypatch.setattr(controller_module, "EVTX_STREAM_KEY", evtx_stream)
        monkeypatch.setattr(evtx_module, "EVTX_STREAM_KEY", evtx_stream)
        monkeypatch.setattr(evtx_module, "EVTX_CONSUMER_GROUP", f"eims-test-evtx-{suffix}")
        monkeypatch.setattr(evtx_module, "EVTX_DEAD_LETTER_STREAM_KEY", evtx_dlq)
        monkeypatch.setattr(evtx_module, "LEGACY_EVTX_LIST_KEY", legacy_stream)
        monkeypatch.setattr(broker_module, "TELEMETRY_STREAM_KEY", telemetry_stream)
        monkeypatch.setattr(telemetry_worker_module, "TELEMETRY_STREAM_KEY", telemetry_stream)
        monkeypatch.setattr(broker_module, "TELEMETRY_DEAD_LETTER_STREAM_KEY", telemetry_dlq)
        monkeypatch.setattr(telemetry_worker_module.database_engine, "get_session_maker", lambda: session_maker)

        async with session_maker() as session:
            async with session.begin():
                session.add(InfrastructureAsset(
                    asset_id=asset_id,
                    hostname=f"eims-evtx-e2e-{suffix[:12]}",
                    canonical_ip="192.0.2.10",
                    cryptographic_fingerprint=fingerprint,
                ))

        upload = UploadFile(file=io.BytesIO(fixture_bytes), filename="system.evtx")
        accepted = await controller_module.upload_windows_evtx(upload, fingerprint, cache)
        assert accepted["status"] == "processing"
        assert accepted["task_id"]
        parsed_uri = urlparse(accepted["minio_uri"])
        assert parsed_uri.scheme == "s3" and parsed_uri.netloc == bucket
        object_key = unquote(parsed_uri.path.lstrip("/"))
        stored = storage.s3_client.head_object(Bucket=bucket, Key=object_key)
        assert stored["ContentLength"] == len(fixture_bytes)
        assert await redis_client.xlen(evtx_stream) == 1

        broker = broker_module.RedisTelemetryStreamBroker(
            cache, consumer_name=f"telemetry-{suffix[:10]}",
            group_name=group_name, reclaim_idle_ms=0,
        )
        evtx_worker = EVTXBackgroundWorker(
            redis_client=redis_client, broker=broker,
            consumer_name=f"evtx-{suffix[:10]}", reclaim_idle_ms=0,
        )
        consumer = TelemetryStreamConsumer(broker=broker)
        consumer.register_agent_mapping(fingerprint, asset_id)

        original_ack = evtx_worker._ack_job
        ack_calls = 0

        async def fail_first_post_publish_ack(client, message_id):
            nonlocal ack_calls
            ack_calls += 1
            if ack_calls == 1:
                raise ConnectionError("synthetic post-publish EVTX ACK failure")
            await original_ack(client, message_id)

        evtx_worker._ack_job = fail_first_post_publish_ack
        with pytest.raises(ConnectionError, match="post-publish EVTX ACK failure"):
            await evtx_worker._process_pending_tasks()

        assert (await redis_client.xpending(evtx_stream, evtx_module.EVTX_CONSUMER_GROUP))["pending"] == 1
        first_messages = await redis_client.xrange(telemetry_stream)
        first_keys = {
            (fields.get(b"source_event_key") or fields.get("source_event_key")).decode()
            if isinstance(fields.get(b"source_event_key") or fields.get("source_event_key"), bytes)
            else (fields.get(b"source_event_key") or fields.get("source_event_key"))
            for _, fields in first_messages
        }
        assert len(first_messages) == 1601
        assert len(first_keys) == 1601

        first_processed = await consumer.process_batch(batch_size=2000)
        assert first_processed == 1601
        assert await redis_client.xlen(telemetry_stream) == 0
        assert (await redis_client.xpending(telemetry_stream, group_name))["pending"] == 0

        async with session_maker() as session:
            persisted_keys = set((await session.execute(
                select(WindowsEventLog.source_event_key).where(WindowsEventLog.asset_id == asset_id)
            )).scalars())
        assert persisted_keys == first_keys
        assert len(persisted_keys) == 1601

        # Replay the EVTX job after its publish succeeded but its ACK failed.
        evtx_worker._ack_job = original_ack
        await evtx_worker._process_pending_tasks()
        replay_messages = await redis_client.xrange(telemetry_stream)
        replay_keys = {
            (fields.get(b"source_event_key") or fields.get("source_event_key")).decode()
            if isinstance(fields.get(b"source_event_key") or fields.get("source_event_key"), bytes)
            else (fields.get(b"source_event_key") or fields.get("source_event_key"))
            for _, fields in replay_messages
        }
        assert len(replay_messages) == 1601
        assert replay_keys == first_keys

        replay_processed = await consumer.process_batch(batch_size=2000)
        assert replay_processed == 1601
        assert await redis_client.xlen(telemetry_stream) == 0
        assert await redis_client.xlen(evtx_stream) == 0
        assert (await redis_client.xpending(evtx_stream, evtx_module.EVTX_CONSUMER_GROUP))["pending"] == 0

        async with session_maker() as session:
            final_count = await session.scalar(
                select(func.count()).select_from(WindowsEventLog).where(WindowsEventLog.asset_id == asset_id)
            )
        assert final_count == 1601
    finally:
        if object_key and storage is not None:
            try:
                storage.s3_client.delete_object(Bucket=bucket, Key=object_key)
            except Exception:
                pass
        try:
            async with session_maker() as session:
                async with session.begin():
                    await session.execute(delete(WindowsEventLog).where(WindowsEventLog.asset_id == asset_id))
                    await session.execute(delete(InfrastructureAsset).where(InfrastructureAsset.asset_id == asset_id))
        except Exception:
            pass
        try:
            await redis_client.delete(evtx_stream, evtx_dlq, legacy_stream, telemetry_stream, telemetry_dlq)
            await redis_client.aclose()
        finally:
            await engine.dispose()
            if storage is not None:
                await storage.close()
