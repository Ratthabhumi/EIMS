"""Opt-in restart acceptance for the dedicated disposable Redis and MinIO containers."""
import asyncio
import io
import os
import subprocess
import uuid
from urllib.parse import unquote, urlparse

import pytest
from botocore.exceptions import ClientError
from redis.asyncio import Redis
from sqlalchemy.engine import make_url

from backend.core.config import settings
from backend.domain.telemetry.broker import RedisTelemetryStreamBroker
from backend.infrastructure.cache import AsynchronousCacheManager
from backend.infrastructure.object_store import MinIOStorageManager


REDIS_CONTAINER_PREFIX = "eims-evtx-e2e-redis-"
MINIO_CONTAINER_PREFIX = "eims-evtx-e2e-minio-"


def _docker(*args):
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=30, check=False
    )
    if result.returncode:
        raise RuntimeError(f"docker {' '.join(args[:2])} failed with exit {result.returncode}")
    return result.stdout.strip()


def _verify_disposable_container(name, expected_prefix, expected_image):
    if not name.startswith(expected_prefix):
        pytest.fail(f"Refusing to restart container outside the dedicated EIMS acceptance namespace: {name}")
    details = _docker("inspect", "--format", "{{.Config.Image}}|{{.State.Running}}", name)
    image, running = details.split("|", 1)
    if expected_image not in image.lower() or running.lower() != "true":
        pytest.fail(f"Refusing to restart non-running or unexpected container: {name}")


@pytest.mark.asyncio
async def test_redis_and_minio_restart_recover_without_losing_test_data(monkeypatch):
    if os.getenv("EIMS_TEST_RESTART_CONTAINERS") != "1":
        pytest.skip("Set EIMS_TEST_RESTART_CONTAINERS=1 to permit restart of disposable EIMS acceptance containers")

    redis_url = os.getenv("EIMS_TEST_REDIS_URL")
    redis_container = os.getenv("EIMS_TEST_REDIS_CONTAINER", "")
    minio_endpoint = os.getenv("EIMS_TEST_MINIO_ENDPOINT")
    minio_container = os.getenv("EIMS_TEST_MINIO_CONTAINER", "")
    minio_access_key = os.getenv("EIMS_TEST_MINIO_ACCESS_KEY")
    minio_secret_key = os.getenv("EIMS_TEST_MINIO_SECRET_KEY")
    bucket = os.getenv("EIMS_TEST_MINIO_BUCKET", "eims-evtx-restart-e2e")
    if not all((redis_url, redis_container, minio_endpoint, minio_container,
                minio_access_key, minio_secret_key)):
        pytest.skip("Explicit disposable Redis/MinIO endpoints, container names and credentials are required")

    redis_target = make_url(redis_url)
    if redis_target.host not in ("127.0.0.1", "localhost") or redis_target.port != 56379:
        pytest.fail("Refusing restart acceptance: Redis must be the disposable local instance on port 56379")
    if minio_endpoint not in ("127.0.0.1:59000", "localhost:59000"):
        pytest.fail("Refusing restart acceptance: MinIO must be the disposable local instance on port 59000")
    _verify_disposable_container(redis_container, REDIS_CONTAINER_PREFIX, "redis")
    _verify_disposable_container(minio_container, MINIO_CONTAINER_PREFIX, "minio")

    redis_client = Redis.from_url(
        redis_url, decode_responses=False, socket_connect_timeout=1, socket_timeout=1
    )
    cache = AsynchronousCacheManager()
    cache._redis_client = redis_client
    suffix = uuid.uuid4().hex
    stream_key = f"eims:telemetry:ingestion:restart:{suffix}"
    group_name = f"eims-test-restart-{suffix}"
    broker1 = RedisTelemetryStreamBroker(
        cache, consumer_name=f"before-restart-{suffix[:8]}",
        group_name=group_name, reclaim_idle_ms=0,
    )
    manager = None
    minio_objects = []
    redis_stopped = False
    minio_stopped = False

    try:
        # Redis: persist a pending entry, lose the service, then reclaim the same entry.
        await redis_client.xadd(stream_key, {
            "event_type": "heartbeat",
            "source_event_key": f"restart:{suffix}",
            "payload": "{\"synthetic\":true}",
        })
        claimed, _, error_signal = await broker1.fetch_stream_batch(stream_key, "0-0", 10)
        assert error_signal is None and len(claimed) == 1
        message_id = claimed[0][0]
        _docker("exec", redis_container, "redis-cli", "SAVE")
        _docker("stop", redis_container)
        redis_stopped = True

        unavailable, _, error_signal = await broker1.fetch_stream_batch(stream_key, "0-0", 10)
        assert unavailable == [] and error_signal == "stream-read-error"

        _docker("start", redis_container)
        redis_stopped = False
        for _ in range(30):
            try:
                if await redis_client.ping():
                    break
            except Exception:
                pass
            await asyncio.sleep(0.5)
        else:
            pytest.fail("Disposable Redis did not recover within 15 seconds")

        broker2 = RedisTelemetryStreamBroker(
            cache, consumer_name=f"after-restart-{suffix[:8]}",
            group_name=group_name, reclaim_idle_ms=0,
        )
        reclaimed, _, error_signal = await broker2.fetch_stream_batch(stream_key, "0-0", 10)
        assert error_signal is None and len(reclaimed) == 1
        assert reclaimed[0][0] == message_id
        recovered_key = reclaimed[0][1].get(b"source_event_key") or reclaimed[0][1].get("source_event_key")
        if isinstance(recovered_key, bytes):
            recovered_key = recovered_key.decode()
        assert recovered_key == f"restart:{suffix}"
        await broker2.ack_stream_messages(stream_key, [message_id])
        assert await redis_client.xlen(stream_key) == 0
        assert (await redis_client.xpending(stream_key, group_name))["pending"] == 0

        # MinIO: verify a stored object survives service stop/start and uploads resume.
        monkeypatch.setattr(settings, "MINIO_ENDPOINT", minio_endpoint)
        monkeypatch.setattr(settings, "MINIO_ACCESS_KEY", minio_access_key)
        monkeypatch.setattr(settings, "MINIO_SECRET_KEY", minio_secret_key)
        monkeypatch.setattr(settings, "MINIO_BUCKET_NAME", bucket)
        monkeypatch.setattr(settings, "MINIO_SECURE", False)
        manager = MinIOStorageManager()
        try:
            manager.s3_client.head_bucket(Bucket=bucket)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code not in ("404", "NoSuchBucket", "NotFound"):
                raise
            manager.s3_client.create_bucket(Bucket=bucket)

        first_uri = await manager.upload_file(io.BytesIO(b"synthetic-minio-restart-proof"),
                                              "restart-proof.txt", "text/plain")
        first_key = unquote(urlparse(first_uri).path.lstrip("/"))
        minio_objects.append(first_key)
        assert manager.s3_client.head_object(Bucket=bucket, Key=first_key)["ContentLength"] == 29

        _docker("stop", minio_container)
        minio_stopped = True
        assert await manager.ping() is False

        _docker("start", minio_container)
        minio_stopped = False
        for _ in range(30):
            if await manager.ping():
                break
            await asyncio.sleep(0.5)
        else:
            pytest.fail("Disposable MinIO did not recover within 15 seconds")

        response = manager.s3_client.get_object(Bucket=bucket, Key=first_key)
        try:
            assert response["Body"].read() == b"synthetic-minio-restart-proof"
        finally:
            response["Body"].close()

        second_uri = await manager.upload_file(io.BytesIO(b"synthetic-upload-after-restart"),
                                               "after-restart.txt", "text/plain")
        second_key = unquote(urlparse(second_uri).path.lstrip("/"))
        minio_objects.append(second_key)
        assert manager.s3_client.head_object(Bucket=bucket, Key=second_key)["ContentLength"] == 30
    finally:
        if redis_stopped:
            try:
                _docker("start", redis_container)
            except Exception:
                pass
        if minio_stopped:
            try:
                _docker("start", minio_container)
            except Exception:
                pass
        if manager is not None:
            for key in minio_objects:
                try:
                    manager.s3_client.delete_object(Bucket=bucket, Key=key)
                except Exception:
                    pass
            await manager.close()
        try:
            await redis_client.delete(stream_key)
        except Exception:
            pass
        await redis_client.aclose()
