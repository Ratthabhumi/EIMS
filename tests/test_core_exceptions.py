"""
==============================================================================
EIMS Automated Test Suite — RFC 7807 Problem Details Exception Architecture
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Section 6.2
==============================================================================
"""

import uuid
import pytest
from backend.core.exceptions import EIMSProblemException, AssetStateViolationException, ResourceNotFoundException


def test_eims_problem_exception_base():
    """Verifies foundational RFC 7807 attribute structure on custom exceptions."""
    exc = EIMSProblemException(
        status=400,
        title="Invalid Configuration Payload",
        detail="The provided subnet mask fails routing evaluations.",
        type_uri="https://errors.eims.platform/v1/invalid-subnet",
        subnet="255.255.255.999"
    )
    assert exc.status == 400
    assert exc.title == "Invalid Configuration Payload"
    assert exc.type_uri == "https://errors.eims.platform/v1/invalid-subnet"
    assert exc.extra_metrics["subnet"] == "255.255.255.999"


def test_asset_state_violation_status_and_formatting():
    """Confirms AssetStateViolationException adheres strictly to HTTP 409 Conflict per Core Law 3."""
    dummy_id = str(uuid.uuid4())
    exc = AssetStateViolationException(current_state="Discovered", attempted_state="Decommissioned", asset_id=dummy_id)
    assert exc.status == 409
    assert exc.title == "Asset Lifecycle State Machine Violation"
    assert "Discovered" in exc.detail and "Decommissioned" in exc.detail
    assert exc.extra_metrics["asset_id"] == dummy_id


def test_resource_not_found_formatting():
    """Confirms ResourceNotFoundException assigns HTTP 404 and canonical detail messages."""
    missing_id = str(uuid.uuid4())
    exc = ResourceNotFoundException(resource_type="InfrastructureAsset", resource_id=missing_id)
    assert exc.status == 404
    assert exc.title == "Requested Infrastructure Resource Missing"
    assert exc.extra_metrics["resource_id"] == missing_id
    assert "InfrastructureAsset" in exc.detail
