"""Hermetic tests for the read-only MinIO health probe."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from backend.infrastructure import object_store
from backend.infrastructure.object_store import MinIOStorageManager

_MANAGERS: list = []


@pytest.fixture(autouse=True)
def _reap_probe_executors():
    """Guarantee no minio-health worker outlives a test (tests release their blockers)."""
    yield
    while _MANAGERS:
        ex = _MANAGERS.pop()._ping_executor
        if ex is not None:
            ex.shutdown(wait=True, cancel_futures=True)


def _manager() -> MinIOStorageManager:
    mgr = MinIOStorageManager.__new__(MinIOStorageManager)
    _MANAGERS.append(mgr)
    mgr.bucket = "test-bucket"
    mgr._endpoint = "http://minio.invalid:9000"
    mgr._health_client = None
    mgr.s3_client = MagicMock(name="regular_client")
    return mgr


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "secret-detail"}}, "HeadBucket")


def test_ping_404_does_not_create_bucket():
    mgr = _manager()
    health = MagicMock(name="health_client")
    health.head_bucket.side_effect = _client_error("404")
    mgr._health_client = health
    mgr._ensure_bucket_exists = MagicMock(name="ensure")

    assert asyncio.run(mgr.ping()) is False

    health.head_bucket.assert_called_once_with(Bucket="test-bucket")
    health.create_bucket.assert_not_called()
    mgr.s3_client.create_bucket.assert_not_called()
    mgr.s3_client.head_bucket.assert_not_called()
    mgr._ensure_bucket_exists.assert_not_called()


def test_ping_success_returns_true():
    mgr = _manager()
    mgr._health_client = MagicMock()
    assert asyncio.run(mgr.ping()) is True


def test_health_client_is_dedicated_and_bounded():
    mgr = _manager()
    with patch.object(object_store.boto3, "client") as mock_client:
        mock_client.return_value = MagicMock()
        mgr._sync_ping()

    assert mock_client.call_count == 1
    args, kwargs = mock_client.call_args
    assert args == ("s3",)
    assert kwargs["endpoint_url"] == "http://minio.invalid:9000"
    cfg = kwargs["config"]
    assert cfg.connect_timeout == 2
    assert cfg.read_timeout == 2
    assert cfg.retries["total_max_attempts"] == 1
    assert mgr._health_client is mock_client.return_value
    assert mgr.s3_client is not mgr._health_client


def test_ping_failure_logs_class_only(caplog):
    mgr = _manager()
    health = MagicMock()
    health.head_bucket.side_effect = _client_error("403")
    mgr._health_client = health

    with caplog.at_level("ERROR", logger="eims.infrastructure.object_store"):
        assert asyncio.run(mgr.ping()) is False

    text = caplog.text
    assert "phase=head_bucket" in text
    assert "ClientError" in text
    assert "secret-detail" not in text


# --- Phase diagnostics (measurement-only; explicit probe budgets) ----------------------

import threading
import time

import anyio.to_thread
import pytest
from fastapi.concurrency import run_in_threadpool


def test_await_timeout_fits_dashboard_health_budget():
    assert object_store._PING_AWAIT_TIMEOUT == 3.0


def _fast_timeout(monkeypatch, value=0.2):
    # Test-only shortening so hermetic tests stay fast; production value asserted above.
    monkeypatch.setattr(object_store, "_PING_AWAIT_TIMEOUT", value)


def _minio_threads():
    return [t for t in threading.enumerate() if t.name.startswith("minio-health") and t.is_alive()]


def _assert_no_minio_threads(timeout=2.0):
    deadline = time.monotonic() + timeout
    while _minio_threads() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert _minio_threads() == []


def test_saturated_anyio_threadpool_does_not_block_probe(monkeypatch):
    """The probe uses its own executor, so a starved shared AnyIO pool cannot delay it."""
    mgr = _manager()
    health = MagicMock()
    mgr._health_client = health
    release = threading.Event()

    async def scenario():
        limiter = anyio.to_thread.current_default_thread_limiter()
        original = limiter.total_tokens
        limiter.total_tokens = 1
        holder = asyncio.create_task(run_in_threadpool(release.wait))
        await asyncio.sleep(0.05)  # holder owns the only shared-pool token
        try:
            return await asyncio.wait_for(mgr.ping(), timeout=1.0)
        finally:
            release.set()
            await holder
            limiter.total_tokens = original
            await mgr.close()

    assert asyncio.run(scenario()) is True
    health.head_bucket.assert_called_once_with(Bucket="test-bucket")


def test_probe_thread_is_not_from_shared_pool():
    mgr = _manager()
    seen = []
    health = MagicMock()
    health.head_bucket.side_effect = lambda **_: seen.append(threading.current_thread().name)
    mgr._health_client = health

    async def scenario():
        assert await mgr.ping() is True
        await mgr.close()

    asyncio.run(scenario())
    assert seen and seen[0].startswith("minio-health")


def test_concurrent_probes_coalesce_into_single_job():
    mgr = _manager()
    release = threading.Event()
    started = threading.Event()
    health = MagicMock()

    def slow_head(**_):
        started.set()
        release.wait(5)

    health.head_bucket.side_effect = slow_head
    mgr._health_client = health

    async def scenario():
        tasks = [asyncio.create_task(mgr.ping()) for _ in range(10)]
        while not started.is_set():
            await asyncio.sleep(0.005)
        assert len(_minio_threads()) == 1
        assert mgr._ping_executor._max_workers == 1
        assert mgr._ping_executor._work_queue.qsize() == 0  # nothing queued behind it
        release.set()
        results = await asyncio.gather(*tasks)
        await mgr.close()
        return results

    assert asyncio.run(scenario()) == [True] * 10
    assert health.head_bucket.call_count == 1  # coalesced: one head_bucket for 10 callers
    _assert_no_minio_threads()


def test_timeout_does_not_spawn_second_worker_until_prior_completes(monkeypatch):
    _fast_timeout(monkeypatch, 0.1)
    mgr = _manager()
    release = threading.Event()
    started = threading.Event()
    calls = []
    health = MagicMock()

    def head(**_):
        calls.append(1)
        started.set()
        if len(calls) == 1:
            release.wait(5)

    health.head_bucket.side_effect = head
    mgr._health_client = health

    async def scenario():
        assert await mgr.ping() is False  # times out; first thread still blocked
        first_future = mgr._ping_inflight[0]
        assert not first_future.done()
        assert await mgr.ping() is False  # joins the same in-flight probe
        assert mgr._ping_inflight[0] is first_future
        assert len(calls) == 1
        assert len(_minio_threads()) == 1
        release.set()
        await asyncio.wrap_future(first_future)
        assert await mgr.ping() is True  # prior finished: a new probe is allowed
        assert len(calls) == 2
        assert len(_minio_threads()) == 1  # same single worker thread reused
        await mgr.close()

    asyncio.run(scenario())
    _assert_no_minio_threads()


def test_close_releases_executor_and_thread():
    mgr = _manager()
    mgr._health_client = MagicMock()

    async def scenario():
        assert await mgr.ping() is True
        assert len(_minio_threads()) == 1
        await mgr.close()
        await mgr.close()  # idempotent
        assert mgr._ping_executor is None and mgr._ping_inflight is None

    asyncio.run(scenario())
    deadline = time.monotonic() + 2
    while _minio_threads() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert _minio_threads() == []


def test_close_waits_for_running_probe_then_thread_exits():
    mgr = _manager()
    release = threading.Event()
    started = threading.Event()
    health = MagicMock()
    health.head_bucket.side_effect = lambda **_: (started.set(), release.wait(5))
    mgr._health_client = health

    async def scenario():
        task = asyncio.create_task(mgr.ping())
        while not started.is_set():
            await asyncio.sleep(0.005)
        threading.Timer(0.05, release.set).start()
        await mgr.close()
        assert await task is True

    asyncio.run(scenario())
    deadline = time.monotonic() + 2
    while _minio_threads() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert _minio_threads() == []


def test_diag_slow_head_bucket_reports_minio_request(monkeypatch, caplog):
    _fast_timeout(monkeypatch)
    mgr = _manager()
    release = threading.Event()
    health = MagicMock()
    health.head_bucket.side_effect = lambda **_: release.wait(5)
    mgr._health_client = health

    async def scenario():
        try:
            return await mgr.ping()
        finally:
            release.set()

    with caplog.at_level("ERROR", logger="eims.infrastructure.object_store"):
        assert asyncio.run(scenario()) is False

    assert "suspect=minio_request" in caplog.text
    assert "http://" not in caplog.text and "minio.invalid" not in caplog.text
    assert "test-bucket" not in caplog.text


def test_diag_finished_work_but_late_await_reports_event_loop():
    mgr = _manager()
    timing = {"worker_start": 1.01, "head_start": 1.011, "head_end": 1.02}
    import logging

    records = []
    handler = logging.Handler()
    handler.emit = records.append
    object_store.logger.addHandler(handler)
    try:
        mgr._log_ping_timeout(timing, 1.0, 0.5, 3.5, "TimeoutError")
    finally:
        object_store.logger.removeHandler(handler)
    msg = records[0].getMessage()
    assert "suspect=event_loop_or_wakeup" in msg
    assert "submit_loop_lag_ms=500.0" in msg


def test_sync_ping_records_phase_timestamps():
    mgr = _manager()
    mgr._health_client = MagicMock()
    timing: dict = {}
    assert mgr._sync_ping(timing) is True
    assert timing["worker_start"] <= timing["head_start"] <= timing["head_end"]


def test_cancelled_ping_stays_read_only_and_single_call(monkeypatch):
    mgr = _manager()
    release = threading.Event()
    started = threading.Event()
    health = MagicMock()

    def slow_head(**_):
        started.set()
        release.wait(5)

    health.head_bucket.side_effect = slow_head
    mgr._health_client = health
    mgr._ensure_bucket_exists = MagicMock()

    async def scenario():
        task = asyncio.create_task(mgr.ping())
        while not started.is_set():
            await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        release.set()
        await asyncio.sleep(0.05)

    asyncio.run(scenario())

    health.head_bucket.assert_called_once_with(Bucket="test-bucket")
    health.create_bucket.assert_not_called()
    mgr.s3_client.create_bucket.assert_not_called()
    mgr._ensure_bucket_exists.assert_not_called()


def test_probe_completed_within_deadline_survives_late_event_loop_wakeup(monkeypatch, caplog):
    _fast_timeout(monkeypatch, 0.1)
    mgr = _manager()
    mgr._health_client = MagicMock()
    original_wait_for = asyncio.wait_for

    async def late_awaiter(_awaitable, timeout):
        assert timeout == 0.1
        # The dedicated worker finishes well inside 100ms; simulate the loop only
        # resuming after its deadline callback has already fired.
        await asyncio.sleep(0.15)
        raise asyncio.TimeoutError()

    async def scenario():
        monkeypatch.setattr(object_store.asyncio, "wait_for", late_awaiter)
        try:
            result = await mgr.ping()
            assert mgr._ping_inflight[0].done()
            return result
        finally:
            monkeypatch.setattr(object_store.asyncio, "wait_for", original_wait_for)
            await mgr.close()

    with caplog.at_level("WARNING", logger="eims.infrastructure.object_store"):
        assert asyncio.run(scenario()) is True
    assert "Completed Within Deadline" in caplog.text
