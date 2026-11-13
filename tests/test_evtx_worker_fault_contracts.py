"""Hermetic EVTX worker fault boundaries; no Redis, MinIO, or device sockets.

Two strict XFAILs describe destructive RPOP delivery loss. They are not a
recovery guarantee. The passing security contracts prohibit logging raw queue
payloads, which may contain attacker-controlled or sensitive strings.
"""
import io
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.domain.telemetry import evtx_worker as module


class FakeQueue:
    def __init__(self, *entries):
        self.entries = list(entries)

    async def rpop(self, key):
        assert key == "eims:jobs:evtx"
        return self.entries.pop() if self.entries else None


def _worker(monkeypatch, *entries):
    queue = FakeQueue(*entries)
    monkeypatch.setattr(module, "cache_manager", SimpleNamespace(redis=queue))

    class FakeStorage:
        def __init__(self):
            self.bucket = "synthetic-only"
            self.s3_client = SimpleNamespace(
                get_object=MagicMock(return_value={"Body": io.BytesIO(b"synthetic-evtx")})
            )

    storage = FakeStorage()
    monkeypatch.setattr(module, "MinIOStorageManager", FakeStorage)
    monkeypatch.setattr(module, "object_storage", storage)
    worker = module.EVTXBackgroundWorker()
    worker.broker.publish_winlog = AsyncMock()
    return worker, queue, storage


def _job():
    return json.dumps({
        "job_id": "synthetic-job-1",
        "minio_uri": "s3://synthetic-only/synthetic.evtx",
    })


@pytest.mark.asyncio
async def test_malformed_task_never_logs_untrusted_queue_bytes(monkeypatch, caplog):
    marker = "synthetic-secret-do-not-log-001"
    worker, queue, _ = _worker(monkeypatch, '{"private":"' + marker)
    with caplog.at_level("ERROR", logger="eims.worker.evtx"):
        await worker._process_pending_tasks()
    assert marker not in caplog.text
    worker.broker.publish_winlog.assert_not_awaited()
    assert queue.entries == []  # Current poison-message policy remains unresolved.


@pytest.mark.asyncio
async def test_missing_uri_never_logs_untrusted_task_fields(monkeypatch, caplog):
    marker = "synthetic-secret-do-not-log-002"
    worker, _, _ = _worker(monkeypatch, json.dumps({
        "job_id": "synthetic-job-2", "private": marker,
    }))
    with caplog.at_level("ERROR", logger="eims.worker.evtx"):
        await worker._process_pending_tasks()
    assert marker not in caplog.text
    worker.broker.publish_winlog.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_queue_does_not_contact_storage_or_publish(monkeypatch):
    worker, _, storage = _worker(monkeypatch)
    await worker._process_pending_tasks()
    storage.s3_client.get_object.assert_not_called()
    worker.broker.publish_winlog.assert_not_awaited()


@pytest.mark.xfail(strict=True, reason="Destructive RPOP loses job on MinIO read failure; no processing-list recovery")
@pytest.mark.asyncio
async def test_minio_outage_preserves_evtx_job_for_recovery(monkeypatch):
    raw = _job()
    worker, queue, storage = _worker(monkeypatch, raw)
    storage.s3_client.get_object.side_effect = OSError("synthetic-storage-outage")
    await worker._process_pending_tasks()
    assert raw in queue.entries


@pytest.mark.xfail(strict=True, reason="Destructive RPOP loses partially published job; replay/idempotency not implemented")
@pytest.mark.asyncio
async def test_partial_publish_preserves_job_for_recovery(monkeypatch):
    raw = _job()
    worker, queue, _ = _worker(monkeypatch, raw)
    records = [
        {
            "occurrence_time": "2026-10-29T00:00:00+00:00",
            "event_id": event_id,
            "severity": "Information",
            "event_channel": "System",
        }
        for event_id in (6005, 6006)
    ]
    monkeypatch.setattr(module, "parse_evtx_records", lambda _: records)
    worker.broker.publish_winlog.side_effect = [
        SimpleNamespace(status="accepted"),
        ConnectionError("synthetic-stream-publish-fault"),
    ]
    await worker._process_pending_tasks()
    assert worker.broker.publish_winlog.await_count == 2
    assert raw in queue.entries
