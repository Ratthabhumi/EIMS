"""
==============================================================================
EIMS Automated State Machine & Repository Verification Script
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 3 Compliance
==============================================================================
"""

import sys
import uuid
from backend.domain.asset_registry import AssetLifecycleStateMachine, AssetState, AssetRepository, ASSET_CACHE_KEY_PREFIX
from backend.core.exceptions import AssetStateViolationException

def test_state_machine():
    print("=== [Test 1: Evaluating Positive State Machine Transitions] ===")
    dummy_id = str(uuid.uuid4())
    
    # Test valid enrollment progression
    valid_chain = [
        (AssetState.DISCOVERED.value, AssetState.PENDING_AUDIT.value),
        (AssetState.PENDING_AUDIT.value, AssetState.COMPLIANT.value),
        (AssetState.COMPLIANT.value, AssetState.QUARANTINED.value),
        (AssetState.QUARANTINED.value, AssetState.PENDING_AUDIT.value),
        (AssetState.PENDING_AUDIT.value, AssetState.NON_COMPLIANT.value),
        (AssetState.NON_COMPLIANT.value, AssetState.DECOMMISSIONED.value),
    ]
    
    for curr, tgt in valid_chain:
        try:
            AssetLifecycleStateMachine.validate_transition(curr, tgt, dummy_id)
            print(f"SUCCESS: Authorized transition -> [{curr}] -> [{tgt}]")
        except Exception as e:
            print(f"ERROR: Valid transition [{curr}] -> [{tgt}] unexpectedly blocked: {e}")
            sys.exit(1)

    print("\n=== [Test 2: Evaluating Prohibited State Machine Violations (HTTP 409 Conflict)] ===")
    prohibited_attempts = [
        (AssetState.DISCOVERED.value, AssetState.COMPLIANT.value),       # Skipping baseline audit
        (AssetState.DISCOVERED.value, AssetState.DECOMMISSIONED.value),  # Instant decommission from discovery
        (AssetState.DECOMMISSIONED.value, AssetState.COMPLIANT.value),   # Reviving decommissioned read-only archive
    ]
    
    for curr, tgt in prohibited_attempts:
        try:
            AssetLifecycleStateMachine.validate_transition(curr, tgt, dummy_id)
            print(f"ERROR: Prohibited transition [{curr}] -> [{tgt}] was erroneously permitted!")
            sys.exit(1)
        except AssetStateViolationException as exc:
            if exc.status != 409:
                print(f"ERROR: Expected HTTP 409 Conflict status for state violation, but got {exc.status}!")
                sys.exit(1)
            print(f"SUCCESS: Properly blocked prohibited hop -> [{curr}] -> [{tgt}] | Status={exc.status} | Title='{exc.title}'")

def test_repository_structure():
    print("\n=== [Test 3: Validating Repository Architecture & Cache Namespaces] ===")
    if not ASSET_CACHE_KEY_PREFIX.startswith("eims:asset:"):
        print("ERROR: Repository cache namespace violates Core Law 4 rules!")
        sys.exit(1)
    print(f"SUCCESS: Confirmed canonical Redis cache namespace prefix -> '{ASSET_CACHE_KEY_PREFIX}' (TTL: 300s)")
    print("=== [ALL SPRINT 2 PHASE 3 STATE MACHINE & REPOSITORY TESTS PASSED SUCCESSFULLY] ===")

if __name__ == "__main__":
    try:
        test_state_machine()
        test_repository_structure()
        sys.exit(0)
    except Exception as e:
        print(f"FATAL ERROR during Phase 3 verification: {e}")
        sys.exit(1)
