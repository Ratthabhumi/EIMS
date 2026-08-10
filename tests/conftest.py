"""
==============================================================================
EIMS Pytest Configuration & Asynchronous Dependency Injection Fixtures
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 3 & 5 Compliance
==============================================================================
"""

import uuid
import pytest
from datetime import datetime, timezone
from typing import Optional, List, Dict
from fastapi.testclient import TestClient

from backend.main import app
from backend.domain.asset_registry import (
    InfrastructureAsset,
    get_asset_repository,
    AssetState,
)
from backend.domain.asset_registry.state_machine import AssetLifecycleStateMachine
from backend.domain.asset_registry.models import OCRRegistrationRecord
from backend.domain.telemetry import get_telemetry_broker, StubTelemetryStreamBroker
from backend.core.exceptions import ResourceNotFoundException


class StubAssetRepository:
    """
    Hermetic asynchronous repository stub enabling instantaneous API contract testing
    without requiring active network DB socket connections to Docker containers.
    """
    def __init__(self):
        self.storage: Dict[uuid.UUID, InfrastructureAsset] = {}
        self.ocr_storage: Dict[uuid.UUID, OCRRegistrationRecord] = {}

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

    async def create_ocr_registration(self, minio_uri: str) -> OCRRegistrationRecord:
        new_id = uuid.uuid4()
        record = OCRRegistrationRecord(
            record_id=new_id,
            minio_object_uri=minio_uri,
            extraction_status="Pending",
            parsed_raw_text={}
        )
        self.ocr_storage[new_id] = record
        return record


@pytest.fixture
def stub_repo() -> StubAssetRepository:
    """Provides isolated repository memory space per test case."""
    return StubAssetRepository()


@pytest.fixture
def stub_broker() -> StubTelemetryStreamBroker:
    """Provides hermetic stream broker buffer per test case."""
    return StubTelemetryStreamBroker()


@pytest.fixture
def client(stub_repo: StubAssetRepository, stub_broker: StubTelemetryStreamBroker) -> TestClient:
    """Injects hermetic storage overrides and generates synchronous TestClient bridge."""
    app.dependency_overrides[get_asset_repository] = lambda: stub_repo
    app.dependency_overrides[get_telemetry_broker] = lambda: stub_broker
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
