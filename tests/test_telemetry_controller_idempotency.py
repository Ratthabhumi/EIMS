"""Controller idempotency contracts; no Redis or database sockets."""
from datetime import UTC, datetime

import pytest
from unittest.mock import AsyncMock

from backend.domain.telemetry.controller import (
    _stable_ingestion_key,
    ingest_agent_heartbeat,
    ingest_windows_event_log,
)
from backend.domain.telemetry.schemas import (
    AgentHeartbeatRequest,
    AgentWinlogRequest,
    HeartbeatMetrics,
)


@pytest.mark.parametrize("endpoint,event_type,payload", [
    (
        ingest_windows_event_log,
        "winlog",
        AgentWinlogRequest(
            occurrence_time=datetime(2026, 11, 14, 10, 0, tzinfo=UTC),
            event_id=4625,
            severity="Warning",
            event_channel="Security",
            metadata={"source_network_ip": "192.0.2.10", "evtx_event_record_id": "123"},
        ),
    ),
    (
        ingest_agent_heartbeat,
        "heartbeat",
        AgentHeartbeatRequest(
            agent_version="synthetic",
            timestamp=datetime(2026, 11, 14, 10, 0, tzinfo=UTC),
            metrics=HeartbeatMetrics(
                cpu_utilization=10, ram_used_mb=100, ram_total_mb=1000, disk_iops=1
            ),
        ),
    ),
])
@pytest.mark.asyncio
async def test_ingestion_endpoint_retries_reuse_stable_idempotency_key(endpoint, event_type, payload):
    broker = type("Broker", (), {})()
    publish = AsyncMock(return_value=type("Result", (), {"status": "accepted"})())
    setattr(broker, f"publish_{event_type}", publish)

    await endpoint(payload=payload, broker=broker, cert_fingerprint="a" * 64)
    first = publish.await_args.kwargs["source_event_key"]
    await endpoint(payload=payload, broker=broker, cert_fingerprint="a" * 64)
    second = publish.await_args.kwargs["source_event_key"]

    assert first == second
    assert first.startswith("ingest:")
    assert len(first) == 71
    assert _stable_ingestion_key(event_type, payload, "b" * 64) != first


@pytest.mark.asyncio
async def test_evtx_upload_size_limit_rejects_before_minio_or_queue(monkeypatch):
    from io import BytesIO
    from types import SimpleNamespace
    from fastapi import HTTPException
    from backend.domain.telemetry import controller

    monkeypatch.setattr(controller, "MAX_EVTX_UPLOAD_BYTES", 4)
    monkeypatch.setattr(controller, "EVTX_UPLOAD_READ_CHUNK_BYTES", 2)
    upload_bytes = BytesIO(b"123456789")

    async def read(size=-1):
        return upload_bytes.read(size)

    async def seek(position):
        upload_bytes.seek(position)

    upload = SimpleNamespace(
        filename="synthetic.evtx",
        content_type="application/octet-stream",
        file=upload_bytes,
        read=read,
        seek=seek,
    )
    storage = SimpleNamespace(upload_file=AsyncMock())
    monkeypatch.setattr(controller, "object_storage", storage)
    cache = SimpleNamespace(xadd_queue=AsyncMock())

    with pytest.raises(HTTPException) as exc:
        await controller.upload_windows_evtx(
            upload,
            x_client_cert_fingerprint="c" * 64,
            cache_manager=cache,
        )
    assert exc.value.status_code == 413
    storage.upload_file.assert_not_awaited()
    cache.xadd_queue.assert_not_awaited()
