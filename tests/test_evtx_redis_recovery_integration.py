"""Real Redis Streams EVTX restart/replay test with synthetic MinIO and parser."""
import io
import json
import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis

from backend.domain.telemetry import evtx_worker as module
from backend.domain.telemetry.evtx_worker import EVTXBackgroundWorker


@pytest.mark.asyncio
async def test_evtx_minio_and_partial_publish_failures_keep_pending_job(monkeypatch):
    redis_url = os.getenv("EIMS_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("Explicit EIMS_TEST_REDIS_URL is required")
    client = Redis.from_url(redis_url, decode_responses=True)
    suffix = uuid.uuid4().hex
    stream_key = f"eims:test:evtx:{suffix}"
    group_name = f"eims-test-evtx-workers-{suffix}"
    dlq_key = f"eims:test:evtx:dlq:{suffix}"
    legacy_key = f"eims:test:evtx:legacy:{suffix}"
    job_id = f"synthetic-{suffix}"
    monkeypatch.setattr(module, "EVTX_STREAM_KEY", stream_key)
    monkeypatch.setattr(module, "EVTX_CONSUMER_GROUP", group_name)
    monkeypatch.setattr(module, "EVTX_DEAD_LETTER_STREAM_KEY", dlq_key)
    monkeypatch.setattr(module, "LEGACY_EVTX_LIST_KEY", legacy_key)

    class FakeStorage:
        def __init__(self, fail=False):
            self.bucket = "synthetic-only"
            self.fail = fail
            self.s3_client = self
        def get_object(self, Bucket, Key):
            if self.fail:
                raise OSError("synthetic MinIO read fault")
            return {"Body": io.BytesIO(b"synthetic-evtx-binary")}

    records = [
        {"occurrence_time": "2026-11-13T10:00:00+00:00", "event_id": event_id,
         "severity": "Information", "event_channel": "System", "metadata": {}}
        for event_id in (6005, 6006)
    ]
    monkeypatch.setattr(module, "MinIOStorageManager", FakeStorage)
    monkeypatch.setattr(module, "parse_evtx_records", lambda _: records)

    try:
        await client.xadd(stream_key, {"payload": json.dumps({
            "job_id": job_id, "minio_uri": "s3://synthetic-only/synthetic.evtx",
            # Synthetic identity fixture only (valid 64-char hex); not a production identity.
            "uploader_fingerprint": "ab" * 32})})

        monkeypatch.setattr(module, "object_storage", FakeStorage(fail=True))
        first_broker = SimpleNamespace(publish_winlog=AsyncMock())
        first = EVTXBackgroundWorker(redis_client=client, broker=first_broker, reclaim_idle_ms=0)
        with pytest.raises(OSError, match="MinIO read fault"):
            await first._process_pending_tasks()
        assert (await client.xpending(stream_key, group_name))["pending"] == 1
        first_broker.publish_winlog.assert_not_awaited()

        monkeypatch.setattr(module, "object_storage", FakeStorage(fail=False))
        second_broker = SimpleNamespace(publish_winlog=AsyncMock(side_effect=[
            SimpleNamespace(status="accepted"), ConnectionError("synthetic telemetry publish fault")]))
        second = EVTXBackgroundWorker(redis_client=client, broker=second_broker, reclaim_idle_ms=0)
        with pytest.raises(ConnectionError, match="telemetry publish fault"):
            await second._process_pending_tasks()
        first_attempt_keys = [call.kwargs["source_event_key"] for call in second_broker.publish_winlog.await_args_list]
        assert first_attempt_keys == [f"evtx:{job_id}:0", f"evtx:{job_id}:1"]
        assert (await client.xpending(stream_key, group_name))["pending"] == 1

        third_broker = SimpleNamespace(publish_winlog=AsyncMock(return_value=SimpleNamespace(status="accepted")))
        third = EVTXBackgroundWorker(redis_client=client, broker=third_broker, reclaim_idle_ms=0)
        await third._process_pending_tasks()
        replay_keys = [call.kwargs["source_event_key"] for call in third_broker.publish_winlog.await_args_list]
        assert replay_keys == first_attempt_keys
        assert await client.xlen(stream_key) == 0
        assert (await client.xpending(stream_key, group_name))["pending"] == 0
    finally:
        await client.delete(stream_key, dlq_key, legacy_key)
        await client.aclose()
