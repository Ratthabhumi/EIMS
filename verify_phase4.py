"""
==============================================================================
EIMS Automated API Controller & RFC 7807 Error Routing Verification Script
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
==============================================================================
"""

import sys
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from typing import Optional, List, Dict, Any

from backend.main import app
from backend.domain.asset_registry import (
    InfrastructureAsset,
    AssetRepository,
    get_asset_repository,
    AssetState,
)
from backend.core.exceptions import ResourceNotFoundException, AssetStateViolationException
from backend.domain.asset_registry.state_machine import AssetLifecycleStateMachine

# --- In-Memory Asynchronous Stub Repository for Zero-DB API Testing ---
class StubAssetRepository:
    def __init__(self):
        self.storage: Dict[uuid.UUID, InfrastructureAsset] = {}

    async def create_asset(self, hostname: str, canonical_ip: str, cryptographic_fingerprint: str, actor_id: Optional[uuid.UUID] = None) -> InfrastructureAsset:
        new_id = uuid.uuid4()
        asset = InfrastructureAsset(
            asset_id=new_id,
            hostname=hostname,
            canonical_ip=canonical_ip,
            cryptographic_fingerprint=cryptographic_fingerprint,
            lifecycle_state=AssetState.DISCOVERED.value,
            current_compliance_score=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.storage[new_id] = asset
        return asset

    async def get_asset_by_id(self, asset_id: uuid.UUID) -> Optional[InfrastructureAsset]:
        return self.storage.get(asset_id)

    async def list_assets(self, skip: int = 0, limit: int = 50, state: Optional[str] = None) -> List[InfrastructureAsset]:
        items = list(self.storage.values())
        if state:
            items = [i for i in items if i.lifecycle_state == state]
        return items[skip:skip+limit]

    async def transition_state(self, asset_id: uuid.UUID, target_state: str, actor_id: Optional[uuid.UUID] = None, reason: str = "") -> InfrastructureAsset:
        asset = self.storage.get(asset_id)
        if not asset:
            raise ResourceNotFoundException(resource_type="InfrastructureAsset", resource_id=str(asset_id))
        
        AssetLifecycleStateMachine.validate_transition(asset.lifecycle_state, target_state, str(asset_id))
        asset.lifecycle_state = target_state
        asset.updated_at = datetime.now(timezone.utc)
        return asset

# Override dependency to inject test stub repository
stub_repo_instance = StubAssetRepository()
app.dependency_overrides[get_asset_repository] = lambda: stub_repo_instance

client = TestClient(app)

def run_api_verification():
    print("=== [EIMS Automated API Verification: Testing REST Controllers & Error Routing] ===")
    
    # Test 1: Register Asset via POST /api/v1/assets
    print("\n1. Testing POST /api/v1/assets (Asset Enrollment)")
    enroll_payload = {
        "hostname": "srv-app-prod-01.eims.internal",
        "canonical_ip": "10.100.5.21",
        "cryptographic_fingerprint": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }
    resp_create = client.post("/api/v1/assets", json=enroll_payload)
    if resp_create.status_code != 201:
        print(f"ERROR: Expected status 201 on asset registration, got {resp_create.status_code}: {resp_create.text}")
        sys.exit(1)
    
    asset_data = resp_create.json()
    created_id = asset_data["asset_id"]
    print(f"SUCCESS: Enrolled Asset successfully -> ID='{created_id}' | State='{asset_data['lifecycle_state']}'")

    # Test 2: Enumerate via GET /api/v1/assets (Canonical Collection Wrapper verification)
    print("\n2. Testing GET /api/v1/assets (Canonical Collection Wrapper)")
    resp_list = client.get("/api/v1/assets?limit=10&page=1")
    if resp_list.status_code != 200:
        print(f"ERROR: Expected status 200 on list assets, got {resp_list.status_code}: {resp_list.text}")
        sys.exit(1)
    list_json = resp_list.json()
    if list_json.get("status") != "success" or "pagination" not in list_json:
        print("ERROR: Response fails to conform to Core Law 5 Section 6.1 Collection Wrapper schema!")
        sys.exit(1)
    print(f"SUCCESS: Verified Core Law 5 Collection Wrapper -> Total Records={list_json['pagination']['total_records']} | Page={list_json['pagination']['current_page']}")

    # Test 3: Retrieve single entity via GET /api/v1/assets/{id}
    print(f"\n3. Testing GET /api/v1/assets/{created_id} (Read-Through Lookup)")
    resp_get = client.get(f"/api/v1/assets/{created_id}")
    if resp_get.status_code != 200:
        print(f"ERROR: Expected status 200 on asset retrieval, got {resp_get.status_code}")
        sys.exit(1)
    print(f"SUCCESS: Retrieved asset entity -> Hostname='{resp_get.json()['hostname']}'")

    # Test 4: Execute Valid Transition via PATCH /api/v1/assets/{id} (Discovered -> PendingAudit)
    print("\n4. Testing PATCH /api/v1/assets/{id} (Valid State Transition)")
    patch_valid = {"lifecycle_state": "PendingAudit", "operator_rationale": "Initiated compliance test script"}
    resp_patch = client.patch(f"/api/v1/assets/{created_id}", json=patch_valid)
    if resp_patch.status_code != 200:
        print(f"ERROR: Expected status 200 on valid state transition, got {resp_patch.status_code}: {resp_patch.text}")
        sys.exit(1)
    print(f"SUCCESS: Authorized status transition via REST -> New State='{resp_patch.json()['lifecycle_state']}'")

    # Test 5: Verify RFC 7807 Problem Details on Illegal Transition (PendingAudit -> Decommissioned is forbidden!)
    print("\n5. Testing RFC 7807 Error Routing via PATCH /api/v1/assets/{id} (Prohibited Transition)")
    patch_prohibited = {"lifecycle_state": "Decommissioned", "operator_rationale": "Illegal jump bypassing rules"}
    resp_prohibited = client.patch(f"/api/v1/assets/{created_id}", json=patch_prohibited)
    
    if resp_prohibited.status_code != 409:
        print(f"ERROR: Expected HTTP 409 Conflict for state violation, got {resp_prohibited.status_code}!")
        sys.exit(1)
        
    content_type = resp_prohibited.headers.get("content-type", "")
    if "application/problem+json" not in content_type:
        print(f"ERROR: Expected RFC 7807 Content-Type 'application/problem+json', got '{content_type}'")
        sys.exit(1)
        
    problem_json = resp_prohibited.json()
    required_keys = ["type", "title", "status", "detail", "instance"]
    for k in required_keys:
        if k not in problem_json:
            print(f"ERROR: RFC 7807 response missing required attribute '{k}'! Got: {problem_json}")
            sys.exit(1)
            
    print(f"SUCCESS: Confirmed strict RFC 7807 Problem Details Response on illegal state jump:\n -> Status: {problem_json['status']}\n -> Title: {problem_json['title']}\n -> Detail: {problem_json['detail']}\n -> Instance Tracking UUID: {problem_json['instance']}")
    print("\n=== [ALL SPRINT 2 PHASE 4 API & ERROR ROUTING TESTS PASSED SUCCESSFULLY] ===")

if __name__ == "__main__":
    try:
        run_api_verification()
        sys.exit(0)
    except Exception as e:
        print(f"FATAL ERROR during Phase 4 validation: {e}")
        sys.exit(1)
