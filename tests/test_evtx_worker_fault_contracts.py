import asyncio
"""Hermetic EVTX consumer-group fault tests; no Redis, MinIO, or device sockets."""
import base64
import io
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.domain.telemetry import evtx_worker as module
from backend.domain.telemetry.evtx_worker import EVTX_STREAM_KEY


class FakeStreamRedis:
    def __init__(self, *entries):
        self.entries = [(f"1000-{i}", {"payload": raw}) for i, raw in enumerate(entries, 1)]
        self.pending = {}
        self.deliveries = {}
        self.acked = set()
        self.dead_letters = []
        self.legacy = []
        self.groups = set()
        self.next_id = 2000

    async def xgroup_create(self, name, groupname, id="0-0", mkstream=True):
        self.groups.add((name, groupname))
        return True

    async def eval(self, script, numkeys, legacy_key, stream_key):
        if not self.legacy:
            return None
        raw = self.legacy[-1]
        self.next_id += 1
        message_id = f"{self.next_id}-0"
        self.entries.append((message_id, {"payload": raw}))
        self.legacy.pop()
        return message_id

    async def xautoclaim(self, name, groupname, consumername, min_idle_time, start_id="0-0", count=1):
        if not self.pending:
            return "0-0", [], []
        message_id = next(iter(self.pending))
        self.deliveries[message_id] += 1
        return "0-0", [(message_id, self.pending[message_id])], []

    async def xreadgroup(self, groupname, consumername, streams, count=1, block=10):
        for message_id, fields in self.entries:
            if message_id not in self.pending and message_id not in self.acked:
                self.pending[message_id] = fields
                self.deliveries[message_id] = 1
                return [[EVTX_STREAM_KEY, [(message_id, fields)]]]
        return []

    async def xpending_range(self, name, groupname, min, max, count):
        if min in self.pending:
            return [{"message_id": min, "times_delivered": self.deliveries[min]}]
        return []

    async def xack(self, name, groupname, *message_ids):
        count = 0
        for message_id in message_ids:
            if message_id in self.pending:
                del self.pending[message_id]
                self.acked.add(message_id)
                count += 1
        return count

    async def xdel(self, name, *message_ids):
        before = len(self.entries)
        ids = set(message_ids)
        self.entries[:] = [(mid, fields) for mid, fields in self.entries if mid not in ids]
        return before - len(self.entries)

    async def xadd(self, name, fields):
        self.dead_letters.append((name, fields))
        return f"{self.next_id + 1}-0"


def _worker(monkeypatch, *entries, redis_client=None):
    queue = redis_client or FakeStreamRedis(*entries)
    monkeypatch.setattr(module, "cache_manager", SimpleNamespace(redis=queue))

    class FakeStorage:
        def __init__(self):
            self.bucket = "synthetic-only"
            self.s3_client = SimpleNamespace(
                get_object=MagicMock(side_effect=lambda *args, **kwargs: {"Body": io.BytesIO(b"synthetic-evtx")})
            )

    storage = FakeStorage()
    monkeypatch.setattr(module, "MinIOStorageManager", FakeStorage)
    monkeypatch.setattr(module, "object_storage", storage)
    worker = module.EVTXBackgroundWorker(redis_client=queue, reclaim_idle_ms=0, max_delivery_attempts=3)
    worker.broker.publish_winlog = AsyncMock(return_value=SimpleNamespace(status="accepted"))
    return worker, queue, storage


UPLOADER_FP = "b" * 64


def _job(**overrides):
    body = {"job_id": "synthetic-job-1", "minio_uri": "s3://synthetic-only/synthetic.evtx",
            "uploader_fingerprint": UPLOADER_FP}
    body.update(overrides)
    return json.dumps({k: v for k, v in body.items() if v is not None})


@pytest.mark.asyncio
async def test_malformed_task_never_logs_untrusted_queue_bytes(monkeypatch, caplog):
    marker = "synthetic-secret-do-not-log-001"
    worker, queue, _ = _worker(monkeypatch, '{"private":"' + marker)
    with caplog.at_level("ERROR", logger="eims.worker.evtx"):
        await worker._process_pending_tasks()
    assert marker not in caplog.text
    worker.broker.publish_winlog.assert_not_awaited()
    assert queue.entries == []
    assert len(queue.dead_letters) == 1


@pytest.mark.asyncio
async def test_missing_uri_never_logs_untrusted_task_fields(monkeypatch, caplog):
    marker = "synthetic-secret-do-not-log-002"
    worker, queue, _ = _worker(monkeypatch, json.dumps({"job_id": "synthetic-job-2", "private": marker}))
    with caplog.at_level("ERROR", logger="eims.worker.evtx"):
        await worker._process_pending_tasks()
    assert marker not in caplog.text
    worker.broker.publish_winlog.assert_not_awaited()
    assert queue.entries == []
    assert len(queue.dead_letters) == 1


@pytest.mark.asyncio
async def test_empty_queue_does_not_contact_storage_or_publish(monkeypatch):
    worker, _, storage = _worker(monkeypatch)
    await worker._process_pending_tasks()
    storage.s3_client.get_object.assert_not_called()
    worker.broker.publish_winlog.assert_not_awaited()


@pytest.mark.asyncio
async def test_minio_outage_preserves_evtx_job_for_recovery(monkeypatch):
    raw = _job()
    worker, queue, storage = _worker(monkeypatch, raw)
    storage.s3_client.get_object.side_effect = OSError("synthetic-storage-outage")
    with pytest.raises(OSError):
        await worker._process_pending_tasks()
    assert len(queue.pending) == 1
    assert len(queue.entries) == 1
    assert not queue.acked


@pytest.mark.asyncio
async def test_partial_publish_preserves_job_and_replays_stable_event_keys(monkeypatch):
    raw = _job()
    worker, queue, _ = _worker(monkeypatch, raw)
    records = [
        {"occurrence_time": "2026-10-29T00:00:00+00:00", "event_id": event_id,
         "severity": "Information", "event_channel": "System"}
        for event_id in (6005, 6006)
    ]
    monkeypatch.setattr(module, "parse_evtx_records", lambda _: records)
    worker.broker.publish_winlog.side_effect = [
        SimpleNamespace(status="accepted"), ConnectionError("synthetic-stream-publish-fault")]
    with pytest.raises(ConnectionError):
        await worker._process_pending_tasks()
    assert len(queue.pending) == 1
    first_keys = [call.kwargs["source_event_key"] for call in worker.broker.publish_winlog.await_args_list]
    assert first_keys == ["evtx:synthetic-job-1:0", "evtx:synthetic-job-1:1"]

    restarted, _, _ = _worker(monkeypatch, redis_client=queue)
    restarted.broker.publish_winlog = AsyncMock(return_value=SimpleNamespace(status="accepted"))
    await restarted._process_pending_tasks()
    retry_keys = [call.kwargs["source_event_key"] for call in restarted.broker.publish_winlog.await_args_list]
    assert retry_keys == first_keys
    assert queue.entries == []
    assert not queue.pending
    assert queue.acked


@pytest.mark.asyncio
async def test_invalid_records_are_dead_lettered_individually_and_valid_ones_publish(monkeypatch, caplog):
    worker, queue, _ = _worker(monkeypatch, _job())
    marker = "synthetic-secret-do-not-log-003"
    valid = {"occurrence_time": "2026-10-29T00:00:00+00:00", "event_id": 4625,
             "severity": "LogAlways", "event_channel": "Security"}
    records = [valid, {**valid, "occurrence_time": "", "metadata": {"x": marker}},
               {"parse_error": "xml-parse-error"}, {**valid, "event_id": 4624}]
    monkeypatch.setattr(module, "parse_evtx_records", lambda _: records)
    with caplog.at_level("INFO", logger="eims.worker.evtx"):
        await worker._process_pending_tasks()

    keys = [c.kwargs["source_event_key"] for c in worker.broker.publish_winlog.await_args_list]
    assert keys == ["evtx:synthetic-job-1:0", "evtx:synthetic-job-1:3"]
    dlq = [fields for _, fields in queue.dead_letters]
    assert [(f["record_index"], f["source_event_key"], f["reason"]) for f in dlq] == [
        ("1", "evtx:synthetic-job-1:1", "invalid-record:occurrence_time"),
        ("2", "evtx:synthetic-job-1:2", "xml-parse-error")]
    assert json.loads(dlq[0]["payload"])["occurrence_time"] == ""  # no fabricated timestamp
    assert queue.entries == [] and not queue.pending and queue.acked
    assert marker not in caplog.text


@pytest.mark.asyncio
async def test_record_dlq_is_not_written_or_acked_before_valid_publishes_succeed(monkeypatch):
    worker, queue, _ = _worker(monkeypatch, _job())
    valid = {"occurrence_time": "2026-10-29T00:00:00+00:00", "event_id": 4625,
             "severity": "Information", "event_channel": "Security"}
    monkeypatch.setattr(module, "parse_evtx_records", lambda _: [{"parse_error": "missing-system"}, valid])
    worker.broker.publish_winlog.side_effect = ConnectionError("synthetic-stream-publish-fault")
    with pytest.raises(ConnectionError):
        await worker._process_pending_tasks()
    assert queue.dead_letters == []
    assert len(queue.pending) == 1 and not queue.acked


@pytest.mark.asyncio
async def test_legacy_list_jobs_are_atomically_migrated_to_stream(monkeypatch):
    queue = FakeStreamRedis()
    queue.legacy.append(_job())
    worker, _, _ = _worker(monkeypatch, redis_client=queue)
    monkeypatch.setattr(module, "parse_evtx_records", lambda _: [])
    await worker._process_pending_tasks()
    assert queue.legacy == []
    assert queue.entries == []  # migrated, processed and ACKed
    assert queue.acked


@pytest.mark.asyncio
async def test_uploader_fingerprint_is_preserved_into_publish_winlog(monkeypatch):
    worker, queue, _ = _worker(monkeypatch, _job())
    records = [{"occurrence_time": "2026-10-29T00:00:00+00:00", "event_id": event_id,
                "severity": "Information", "event_channel": "System"} for event_id in (6005, 6006)]
    monkeypatch.setattr(module, "parse_evtx_records", lambda _: records)
    await worker._process_pending_tasks()
    fingerprints = [c.kwargs["cert_fingerprint"] for c in worker.broker.publish_winlog.await_args_list]
    assert fingerprints == [UPLOADER_FP, UPLOADER_FP]
    assert "eims-evtx-upload-system" not in fingerprints
    assert queue.entries == [] and queue.acked


@pytest.mark.asyncio
async def test_upload_envelope_flows_through_worker_with_verified_identity(monkeypatch):
    """Controller envelope -> Redis job -> worker -> publish_winlog keeps the same identity."""
    from backend.domain.telemetry import controller

    captured = {}

    async def xadd_queue(key, payload):
        captured["payload"] = payload
        return "1-0"

    monkeypatch.setattr(controller, "object_storage", SimpleNamespace(
        upload_file=AsyncMock(return_value="s3://synthetic-only/synthetic.evtx")))
    upload_bytes = io.BytesIO(b"x")
    async def upload_read(size=-1):
        return upload_bytes.read(size)
    async def upload_seek(position):
        upload_bytes.seek(position)
    upload = SimpleNamespace(
        filename="x.evtx", content_type="application/octet-stream", file=upload_bytes,
        read=upload_read, seek=upload_seek,
    )
    await controller.upload_windows_evtx(
        upload, x_client_cert_fingerprint="c" * 64, cache_manager=SimpleNamespace(xadd_queue=xadd_queue))

    worker, _, _ = _worker(monkeypatch, json.dumps(captured["payload"]))
    monkeypatch.setattr(module, "parse_evtx_records", lambda _: [
        {"occurrence_time": "2026-10-29T00:00:00+00:00", "event_id": 6005,
         "severity": "Information", "event_channel": "System"}])
    await worker._process_pending_tasks()
    assert worker.broker.publish_winlog.await_args.kwargs["cert_fingerprint"] == "c" * 64


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [None, "", "not-a-sha256", "eims-evtx-upload-system", "g" * 64, "a" * 63, 123])
async def test_missing_or_invalid_uploader_fingerprint_is_dead_lettered_with_stable_reason(monkeypatch, bad):
    worker, queue, storage = _worker(monkeypatch, _job(uploader_fingerprint=bad))
    await worker._process_pending_tasks()
    worker.broker.publish_winlog.assert_not_awaited()
    storage.s3_client.get_object.assert_not_called()
    assert queue.entries == []
    assert len(queue.dead_letters) == 1
    assert queue.dead_letters[0][1]["reason"] == module.INVALID_UPLOADER_REASON
    assert module.INVALID_UPLOADER_REASON == "missing-or-invalid-uploader-fingerprint"


def test_decode_fields_never_raises_on_malformed_utf8_and_preserves_bytes():
    entry, undecodable = module.EVTXBackgroundWorker._decode_fields_checked(
        {b"payload": b"\xff\xfe{", "ok": b"fine", b"bad\xc3": "v"})
    assert entry["payload"] == "base64:" + base64.b64encode(b"\xff\xfe{").decode()
    assert entry["ok"] == "fine"
    assert entry["base64:" + base64.b64encode(b"bad\xc3").decode()] == "v"
    assert sorted(undecodable) == sorted(["payload", "base64:" + base64.b64encode(b"bad\xc3").decode()])
    assert module.EVTXBackgroundWorker._decode_fields({b"x": b"\xff"})["x"].startswith("base64:")


@pytest.mark.asyncio
@pytest.mark.parametrize("fields", [
    {b"payload": b"\xff\xfe{not-utf8"},
    {b"payload": _job().encode(), b"extra": b"\xc3\x28"},
    {b"payload": _job().encode(), b"bad\xff": b"v"},
])
async def test_malformed_utf8_queue_fields_reach_dlq_once_and_are_not_reclaimed(monkeypatch, fields):
    worker, queue, storage = _worker(monkeypatch)
    queue.entries.append(("1000-1", fields))

    await worker._process_pending_tasks()  # must not raise UnicodeDecodeError

    assert len(queue.dead_letters) == 1
    name, dlq = queue.dead_letters[0]
    assert name == module.EVTX_DEAD_LETTER_STREAM_KEY
    assert dlq["reason"] == "undecodable-queue-field"
    assert dlq["source_stream_id"] == "1000-1"
    payload = json.loads(dlq["payload"])
    assert payload["undecodable_fields"]
    raw_bad = [b for b in (*fields.keys(), *fields.values()) if isinstance(b, bytes) and not _is_utf8(b)]
    expected = {"base64:" + base64.b64encode(b).decode() for b in raw_bad}
    assert expected and expected <= (set(payload) | set(payload.values()))  # raw bytes preserved
    assert queue.entries == [] and not queue.pending and queue.acked
    worker.broker.publish_winlog.assert_not_awaited()
    storage.s3_client.get_object.assert_not_called()

    await worker._process_pending_tasks()  # nothing left to reclaim: bounded
    assert len(queue.dead_letters) == 1


def _is_utf8(raw: bytes) -> bool:
    try:
        raw.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


@pytest.mark.asyncio
async def test_pre_existing_queued_envelope_without_fingerprint_fails_closed(monkeypatch):
    legacy = json.dumps({"job_id": "old-job", "minio_uri": "s3://synthetic-only/old.evtx"})
    worker, queue, _ = _worker(monkeypatch, legacy)
    await worker._process_pending_tasks()
    worker.broker.publish_winlog.assert_not_awaited()
    assert queue.dead_letters[0][1]["reason"] == module.INVALID_UPLOADER_REASON


def test_source_event_key_is_stable_across_reuploads_and_always_bounded():
    record = {
        "event_id": 4625, "event_channel": "Security", "occurrence_time": "2026-11-14T10:00:00Z",
        "metadata": {"evtx_event_record_id": "12345", "evtx_provider_name": "Microsoft-Windows-Security-Auditing",
                    "evtx_computer": "EIMS-SYNTHETIC"},
    }
    first = module.EVTXBackgroundWorker._source_event_key("job-a", 0, "ab" * 32, record)
    second = module.EVTXBackgroundWorker._source_event_key("job-b", 99, "AB" * 32, record)
    assert first == second and len(first) <= 160
    fallback = module.EVTXBackgroundWorker._source_event_key("j" * 300, 123, "ab" * 32, {"metadata": {}})
    assert fallback.startswith("evtx:") and len(fallback) <= 160


@pytest.mark.asyncio
async def test_long_job_claim_refresh_uses_justid_without_delivery_increment():
    calls = []

    class Client:
        async def xclaim(self, **kwargs):
            calls.append(kwargs)
            return ["1000-1"]

    worker = module.EVTXBackgroundWorker(consumer_name="synthetic-worker", reclaim_idle_ms=0)
    task = asyncio.create_task(worker._refresh_claim_loop(Client(), "1000-1"))
    await asyncio.sleep(1.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls and calls[0]["justid"] is True
    assert calls[0]["idle"] == 0 and calls[0]["min_idle_time"] == 0


@pytest.mark.asyncio
async def test_oversized_evtx_object_is_bounded_and_dead_lettered(monkeypatch):
    worker, queue, storage = _worker(monkeypatch, _job())
    monkeypatch.setattr(module, "MAX_EVTX_FILE_BYTES", 4)
    storage.s3_client.get_object.side_effect = None
    storage.s3_client.get_object.return_value = {"Body": io.BytesIO(b"123456789")}
    await worker._process_pending_tasks()
    storage.s3_client.get_object.assert_called_once()
    assert queue.dead_letters[0][1]["reason"] == "evtx-file-size-limit-exceeded"
    assert queue.entries == [] and not queue.pending and queue.acked
    worker.broker.publish_winlog.assert_not_awaited()


@pytest.mark.asyncio
async def test_evtx_record_limit_is_checked_before_any_event_publish(monkeypatch):
    worker, queue, _ = _worker(monkeypatch, _job())
    monkeypatch.setattr(module, "MAX_EVTX_RECORDS_PER_FILE", 2)
    record = {
        "occurrence_time": "2026-10-29T00:00:00+00:00",
        "event_id": 4625,
        "severity": "Warning",
        "event_channel": "Security",
    }
    monkeypatch.setattr(module, "parse_evtx_records", lambda _: iter([record, record, record]))
    await worker._process_pending_tasks()
    worker.broker.publish_winlog.assert_not_awaited()
    assert queue.dead_letters[0][1]["reason"] == "evtx-record-limit-exceeded"
    assert queue.entries == [] and not queue.pending and queue.acked
