"""
==============================================================================
EIMS Automated Test Suite — Telemetry Collector API Controllers & Edge Routing
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Section 7.1
==============================================================================
"""

import pytest
import json
from fastapi.testclient import TestClient


@pytest.fixture
def valid_mtls_headers():
    return {"X-Client-Cert-Fingerprint": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}


def test_post_heartbeat_success(client: TestClient, stub_broker, valid_mtls_headers):
    """Verifies edge ingestion route returns HTTP 202 Accepted and pushes to stream buffer."""
    payload = {
        "agent_version": "v1.2.4",
        "timestamp": "2026-08-05T08:14:55Z",
        "metrics": {
            "cpu_utilization": 45.2,
            "ram_used_mb": 8420,
            "ram_total_mb": 16384,
            "disk_iops": 312
        }
    }
    resp = client.post("/api/v1/telemetry/heartbeat", json=payload, headers=valid_mtls_headers)
    assert resp.status_code == 202, f"Expected 202 Accepted, got {resp.status_code}: {resp.text}"
    
    data = resp.json()
    assert data["status"] == "accepted"
    assert "stub-" in data["stream_job_id"]
    assert len(data["queued_at"]) > 0
    
    # Verify exact delivery into our hermetic stub broker queue
    assert len(stub_broker.stream_buffer) == 1
    entry = stub_broker.stream_buffer[0]
    assert entry["event_type"] == "heartbeat"
    assert json.loads(entry["payload"])["metrics"]["cpu_utilization"] == 45.2


def test_post_winlog_success_with_extensible_forensics(client: TestClient, stub_broker, valid_mtls_headers):
    """Verifies Windows Event Log route returns HTTP 202 and captures custom forensic tags."""
    payload = {
        "occurrence_time": "2026-08-05T08:15:01Z",
        "event_id": 4625,
        "severity": "Critical",
        "event_channel": "Security",
        "metadata": {
            "target_user_name": "Administrator",
            "workstation_name": "WORKSTATION-X",
            "source_network_ip": "192.168.1.104",
            "addon_name": "DiskDeleter",
            "hook_status": "Active"
        }
    }
    resp = client.post("/api/v1/telemetry/winlog", json=payload, headers=valid_mtls_headers)
    assert resp.status_code == 202
    
    data = resp.json()
    assert data["status"] == "accepted"
    assert len(stub_broker.stream_buffer) == 1
    
    buffered_payload = json.loads(stub_broker.stream_buffer[0]["payload"])
    assert buffered_payload["metadata"]["addon_name"] == "DiskDeleter"
    assert buffered_payload["metadata"]["hook_status"] == "Active"


def test_heartbeat_rejected_on_missing_mtls_header(client: TestClient):
    """Proves omitting X-Client-Cert-Fingerprint throws RFC 7807 HTTP 401 Unauthorized."""
    payload = {
        "agent_version": "v1.0.0",
        "metrics": {"cpu_utilization": 20.0, "ram_used_mb": 1024, "ram_total_mb": 4096, "disk_iops": 50}
    }
    # No headers passed
    resp = client.post("/api/v1/telemetry/heartbeat", json=payload)
    assert resp.status_code == 401
    assert "application/problem+json" in resp.headers.get("content-type", "")
    
    err = resp.json()
    assert err["status"] == 401
    assert err["title"] == "mTLS Client Authentication Required"


def test_heartbeat_rejected_on_impossible_metric_bounds(client: TestClient, valid_mtls_headers):
    """
    Proves Core Law 5 Section 6.2 validation interception:
    Submitting cpu_utilization=145.2 via REST controller must be rejected with HTTP 422.
    """
    payload = {
        "agent_version": "v1.2.4",
        "metrics": {
            "cpu_utilization": 145.2,  # Illegal physical value > 100
            "ram_used_mb": 8420,
            "ram_total_mb": 16384,
            "disk_iops": 312
        }
    }
    resp = client.post("/api/v1/telemetry/heartbeat", json=payload, headers=valid_mtls_headers)
    assert resp.status_code == 422
    assert "application/problem+json" in resp.headers.get("content-type", "")
    assert resp.json()["title"] == "Schema Validation Fault"
