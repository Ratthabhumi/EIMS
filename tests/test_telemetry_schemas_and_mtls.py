"""
==============================================================================
EIMS Automated Test Suite — Telemetry Schemas & mTLS Security Gatekeeper
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Section 7.1
==============================================================================
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from fastapi import status
from unittest.mock import AsyncMock

from backend.domain.telemetry import (
    HeartbeatMetrics,
    AgentHeartbeatRequest,
    WinlogMetadata,
    AgentWinlogRequest,
    StreamIngestionResponse,
    verify_mtls_fingerprint,
)
from backend.core.exceptions import EIMSProblemException


def test_valid_heartbeat_payload_validation():
    """Verifies standard Discovery Agent heartbeat metrics pass schema inspection cleanly."""
    metrics = HeartbeatMetrics(cpu_utilization=42.5, ram_used_mb=8420, ram_total_mb=16384, disk_iops=312)
    payload = AgentHeartbeatRequest(agent_version="v1.2.4", metrics=metrics)
    assert payload.metrics.cpu_utilization == 42.5
    assert payload.agent_version == "v1.2.4"


def test_illegal_cpu_utilization_schema_rejection():
    """
    Proves adherence to Core Law 5 Section 6.2 example:
    Submitting cpu_utilization=145.2 must be rejected by Pydantic mathematical constraints.
    """
    with pytest.raises(ValidationError) as exc_info:
        HeartbeatMetrics(cpu_utilization=145.2, ram_used_mb=4000, ram_total_mb=8192, disk_iops=100)
    
    err_str = str(exc_info.value)
    assert "cpu_utilization" in err_str
    assert "less than or equal to 100" in err_str or "le" in err_str


def test_extensible_winlog_metadata_payload():
    """Verifies Windows Event Log telemetry permits standard AND custom forensic diagnostic attributes."""
    # Passing standard fields plus custom forensic tag from DiskDeleter/Hook extensions
    meta = WinlogMetadata(
        target_user_name="Administrator",
        workstation_name="WORKSTATION-SEC",
        source_network_ip="192.168.1.104",
        custom_hook_signature="DETOURS_INJECTED_V1",
        api_intercepted="DeleteFileW"
    )
    req = AgentWinlogRequest(
        occurrence_time=datetime.now(timezone.utc),
        event_id=4625,
        severity="Critical",
        event_channel="Security",
        metadata=meta
    )
    assert req.event_id == 4625
    assert req.metadata.target_user_name == "Administrator"
    # Verify extra attributes are preserved cleanly without validation crash
    assert getattr(req.metadata, "custom_hook_signature", None) == "DETOURS_INJECTED_V1"
    assert getattr(req.metadata, "api_intercepted", None) == "DeleteFileW"


def test_stream_ingestion_response_formatting():
    """Verifies HTTP 202 stream acceptance wrapper generates valid timestamps and job identifiers."""
    resp = StreamIngestionResponse()
    assert resp.status == "accepted"
    assert len(resp.stream_job_id) > 0 and "-" in resp.stream_job_id
    assert len(resp.queued_at) > 0


@pytest.mark.asyncio
async def test_mtls_fingerprint_gatekeeper_success():
    """Proves valid 64-char SHA-256 certificate hashes pass mTLS security validation."""
    valid_sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    result = await verify_mtls_fingerprint(x_client_cert_fingerprint=valid_sha256)
    assert result == valid_sha256


@pytest.mark.asyncio
async def test_mtls_fingerprint_gatekeeper_missing_header():
    """Asserts absence of X-Client-Cert-Fingerprint header triggers HTTP 401 Unauthorized Problem Details."""
    with pytest.raises(EIMSProblemException) as exc_info:
        await verify_mtls_fingerprint(x_client_cert_fingerprint=None)
    
    assert exc_info.value.status == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.title == "mTLS Client Authentication Required"


@pytest.mark.asyncio
async def test_mtls_fingerprint_gatekeeper_invalid_hash_length():
    """Asserts malformed short/non-hex strings in mTLS certificate header are rejected with HTTP 401."""
    malformed_str = "short-hash-string-not-sha256"
    with pytest.raises(EIMSProblemException) as exc_info:
        await verify_mtls_fingerprint(x_client_cert_fingerprint=malformed_str)
        
    assert exc_info.value.status == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.title == "Invalid mTLS Certificate Fingerprint"
    assert exc_info.value.extra_metrics["provided_fingerprint_length"] == len(malformed_str)
