"""Hermetic EVTX upload acceptance contracts: no real Redis, MinIO, or devices.

A 202 response must mean that the EVTX job was confirmed on the Redis list.
This does NOT prove worker crash recovery, object cleanup, or exactly-once delivery.
"""
import io
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, UploadFile

from backend.domain.telemetry import controller


def _file():
    return UploadFile(
        file=io.BytesIO(b"synthetic-test-only-evtx-bytes"),
        filename="synthetic.evtx",
        headers={"content-type": "application/octet-stream"},
    )


def _storage(monkeypatch, *, error=None):
    upload = AsyncMock(return_value="s3://synthetic-only/object.evtx")
    if error is not None:
        upload.side_effect = error
    monkeypatch.setattr(controller, "object_storage", SimpleNamespace(upload_file=upload))
    return upload


@pytest.mark.asyncio
async def test_evtx_202_only_after_confirmed_queue_write(monkeypatch):
    upload = _storage(monkeypatch)
    cache = SimpleNamespace(lpush_queue=AsyncMock(return_value=1))
    response = await controller.upload_windows_evtx(
        _file(), x_client_cert_fingerprint="a" * 64, cache_manager=cache
    )
    assert response["status"] == "processing"
    assert response["task_id"]
    assert response["minio_uri"] == "s3://synthetic-only/object.evtx"
    upload.assert_awaited_once()
    cache.lpush_queue.assert_awaited_once()
    key, payload = cache.lpush_queue.await_args.args
    assert key == "eims:jobs:evtx"
    assert json.loads(json.dumps(payload)) == {
        "job_id": response["task_id"],
        "minio_uri": response["minio_uri"],
    }


@pytest.mark.asyncio
async def test_evtx_queue_failure_after_storage_does_not_claim_202(monkeypatch):
    upload = _storage(monkeypatch)
    cache = SimpleNamespace(lpush_queue=AsyncMock(
        side_effect=ConnectionError("synthetic-redis-disconnect")
    ))
    with pytest.raises(HTTPException) as failure:
        await controller.upload_windows_evtx(
            _file(), x_client_cert_fingerprint="a" * 64, cache_manager=cache
        )
    assert failure.value.status_code == 503
    assert "synthetic-redis-disconnect" not in str(failure.value.detail)
    assert failure.value.headers["Retry-After"] == "5"
    upload.assert_awaited_once()  # Orphan risk remains: no silent cleanup claim.


@pytest.mark.asyncio
@pytest.mark.parametrize("queue_depth", [0, None])
async def test_evtx_unconfirmed_queue_result_is_not_accepted(monkeypatch, queue_depth):
    _storage(monkeypatch)
    cache = SimpleNamespace(lpush_queue=AsyncMock(return_value=queue_depth))
    with pytest.raises(HTTPException) as failure:
        await controller.upload_windows_evtx(
            _file(), x_client_cert_fingerprint="a" * 64, cache_manager=cache
        )
    assert failure.value.status_code == 503


@pytest.mark.asyncio
async def test_evtx_storage_failure_never_attempts_queue(monkeypatch):
    _storage(monkeypatch, error=RuntimeError("synthetic-storage-unavailable"))
    cache = SimpleNamespace(lpush_queue=AsyncMock())
    with pytest.raises(HTTPException) as failure:
        await controller.upload_windows_evtx(
            _file(), x_client_cert_fingerprint="a" * 64, cache_manager=cache
        )
    assert failure.value.status_code == 502
    cache.lpush_queue.assert_not_awaited()
