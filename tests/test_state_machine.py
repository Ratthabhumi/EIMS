"""
==============================================================================
EIMS Automated Test Suite — Canonical Asset Lifecycle State Machine
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 3 Section 6.4
==============================================================================
"""

import uuid
import pytest
from backend.domain.asset_registry import AssetLifecycleStateMachine, AssetState
from backend.core.exceptions import AssetStateViolationException


def test_valid_positive_transitions():
    """Proves that sequential forward lifecycle progressions complete without interruption."""
    dummy_id = str(uuid.uuid4())
    valid_chain = [
        (AssetState.DISCOVERED.value, AssetState.PENDING_AUDIT.value),
        (AssetState.PENDING_AUDIT.value, AssetState.COMPLIANT.value),
        (AssetState.COMPLIANT.value, AssetState.QUARANTINED.value),
        (AssetState.QUARANTINED.value, AssetState.PENDING_AUDIT.value),
        (AssetState.PENDING_AUDIT.value, AssetState.NON_COMPLIANT.value),
        (AssetState.NON_COMPLIANT.value, AssetState.DECOMMISSIONED.value),
    ]
    for curr, tgt in valid_chain:
        # Should execute silently without throwing exception
        AssetLifecycleStateMachine.validate_transition(curr, tgt, dummy_id)


def test_prohibited_illegal_state_jumps():
    """Asserts that bypassing adjacent directional arrows throws AssetStateViolationException (HTTP 409)."""
    dummy_id = str(uuid.uuid4())
    prohibited_attempts = [
        (AssetState.DISCOVERED.value, AssetState.COMPLIANT.value),
        (AssetState.DISCOVERED.value, AssetState.DECOMMISSIONED.value),
        (AssetState.PENDING_AUDIT.value, AssetState.DISCOVERED.value),
        (AssetState.DECOMMISSIONED.value, AssetState.COMPLIANT.value),  # Decommissioned is terminal!
    ]
    for curr, tgt in prohibited_attempts:
        with pytest.raises(AssetStateViolationException) as exc_info:
            AssetLifecycleStateMachine.validate_transition(curr, tgt, dummy_id)
        assert exc_info.value.status == 409
        assert exc_info.value.title == "Asset Lifecycle State Machine Violation"


def test_invalid_state_literal_string():
    """Verifies unrecognized strings trigger state violation handling."""
    dummy_id = str(uuid.uuid4())
    with pytest.raises(AssetStateViolationException):
        AssetLifecycleStateMachine.validate_transition("Discovered", "NonExistentStateLiteral", dummy_id)
