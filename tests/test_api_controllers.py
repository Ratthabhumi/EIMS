"""
==============================================================================
EIMS Automated Test Suite — Asset Registry REST API Controllers & Error Routing
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
==============================================================================
"""

import uuid
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@patch("backend.main.database_engine.ping", new_callable=AsyncMock, return_value=True)
@patch("backend.main.cache_manager.ping", new_callable=AsyncMock, return_value=True)
def test_health_check_endpoint_healthy(mock_cache_ping, mock_db_ping, client: TestClient):
    """Verifies operational observability endpoint returns HTTP 200 when storage tiers respond."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    assert data["components"]["postgresql_pgbouncer_tier"] == "UP"
    assert data["components"]["redis_volatile_lru_tier"] == "UP"
    assert data["licensing_model"] == "Source-Available (All Rights Reserved)"


@patch("backend.main.database_engine.ping", new_callable=AsyncMock, return_value=False)
@patch("backend.main.cache_manager.ping", new_callable=AsyncMock, return_value=False)
def test_health_check_endpoint_degraded(mock_cache_ping, mock_db_ping, client: TestClient):
    """Verifies health endpoint reports DEGRADED status (HTTP 503) if connection pipelines fail."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "DEGRADED"
    assert data["components"]["postgresql_pgbouncer_tier"] == "DOWN"


def test_asset_enrollment_and_canonical_wrapper(client: TestClient):
    """Executes full-cycle asset enrollment via POST and verifies Section 6.1 collection wrappers via GET."""
    payload = {
        "hostname": "srv-prod-cluster-01.internal",
        "canonical_ip": "10.240.16.15",
        "cryptographic_fingerprint": "a" * 64
    }
    # Create Asset
    post_resp = client.post("/api/v1/assets", json=payload)
    assert post_resp.status_code == 201, f"Expected 201 Created, got {post_resp.status_code}: {post_resp.text}"
    created_asset = post_resp.json()
    asset_id = created_asset["asset_id"]
    assert created_asset["lifecycle_state"] == "Discovered"
    assert created_asset["hostname"] == payload["hostname"]

    # Retrieve via Read-Through GET by ID
    get_resp = client.get(f"/api/v1/assets/{asset_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["canonical_ip"] == payload["canonical_ip"]

    # Enumerate collections via GET /api/v1/assets (Canonical Collection Wrapper check)
    list_resp = client.get("/api/v1/assets?limit=25&page=1")
    assert list_resp.status_code == 200
    list_json = list_resp.json()
    assert list_json["status"] == "success"
    assert "data" in list_json and "pagination" in list_json
    assert list_json["pagination"]["total_records"] >= 1
    assert list_json["pagination"]["current_page"] == 1


def test_asset_state_transitions_via_patch(client: TestClient):
    """Tests authorized REST state mutations and verifies strict RFC 7807 error responses on illegal hops."""
    payload = {
        "hostname": "srv-db-analytics.internal",
        "canonical_ip": "192.168.100.5",
        "cryptographic_fingerprint": "b" * 64
    }
    post_resp = client.post("/api/v1/assets", json=payload)
    asset_id = post_resp.json()["asset_id"]

    # Valid Transition 1: Discovered -> PendingAudit
    patch_resp1 = client.patch(f"/api/v1/assets/{asset_id}", json={"lifecycle_state": "PendingAudit", "operator_rationale": "Unit test audit initiation"})
    assert patch_resp1.status_code == 200
    assert patch_resp1.json()["lifecycle_state"] == "PendingAudit"

    # Valid Transition 2: PendingAudit -> Compliant
    patch_resp2 = client.patch(f"/api/v1/assets/{asset_id}", json={"lifecycle_state": "Compliant", "operator_rationale": "Passed hardening checks"})
    assert patch_resp2.status_code == 200
    assert patch_resp2.json()["lifecycle_state"] == "Compliant"

    # Prohibited Transition: Compliant directly to Discovered (Must raise HTTP 409 Conflict with RFC 7807 JSON)
    prohibited_resp = client.patch(f"/api/v1/assets/{asset_id}", json={"lifecycle_state": "Discovered", "operator_rationale": "Illegal reset attempt"})
    assert prohibited_resp.status_code == 409, f"Expected HTTP 409 Conflict, got {prohibited_resp.status_code}"
    assert "application/problem+json" in prohibited_resp.headers.get("content-type", "")
    
    problem_payload = prohibited_resp.json()
    assert problem_payload["status"] == 409
    assert problem_payload["title"] == "Asset Lifecycle State Machine Violation"
    assert "Compliant" in problem_payload["detail"] and "Discovered" in problem_payload["detail"]


def test_resource_not_found_via_get(client: TestClient):
    """Verifies that requesting non-existent asset UUIDs returns RFC 7807 404 error payloads."""
    fake_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/assets/{fake_id}")
    assert resp.status_code == 404
    assert "application/problem+json" in resp.headers.get("content-type", "")
    assert resp.json()["status"] == 404
    assert resp.json()["title"] == "Requested Infrastructure Resource Missing"
