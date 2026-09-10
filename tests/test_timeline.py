"""
==============================================================================
EIMS Automated Test Suite — Sprint 10 Unified Timeline API
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
==============================================================================
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.domain.timeline.controller import get_timeline_service
from backend.domain.timeline.schemas import TimelineEvent
from backend.main import app

_ASSET_ID = "8f3b2d10-6c54-4a21-9e87-2b10a9c8e7f6"


def _make_event(event_type: str, timestamp: datetime, severity: str = "Information") -> TimelineEvent:
    return TimelineEvent(
        id=str(uuid.uuid4()),
        type=event_type,
        title="TRANSITION_STATE" if event_type == "audit" else "CPU Utilization 68.4%" if event_type == "telemetry" else "Windows Event 4625",
        description="Asset state transitioned from Discovered to Active",
        severity=severity,
        timestamp=timestamp,
        actor_id=None,
        entity_id=uuid.UUID(_ASSET_ID),
        entity_type="asset",
        metadata={},
    )


class StubTimelineService:
    """Hermetic unified Timeline service stub honoring the controller call contract."""

    def __init__(self, events):
        self.events = events

    async def get_timeline(self, db, entity_id=None, event_type=None, severity=None, from_dt=None, to_dt=None, page=1, limit=50):
        data = self.events
        if entity_id is not None:
            data = [e for e in data if e.entity_id == entity_id]
        if event_type is not None:
            data = [e for e in data if e.type == event_type]
        if severity is not None:
            data = [e for e in data if e.severity == severity]
        total = len(data)
        start = (page - 1) * limit
        return data[start:start + limit], total


@pytest.fixture
def timeline_overrides(client: TestClient):
    """Injects the hermetic unified Timeline service stub scoped for the request lifetime."""
    service = StubTimelineService([
        _make_event("audit", datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)),
        _make_event("telemetry", datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)),
        _make_event("winlog", datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc), severity="Critical"),
    ])
    app.dependency_overrides[get_timeline_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_timeline_service, None)


def test_timeline_returns_unified_events_ordered(timeline_overrides, client: TestClient):
    resp = client.get("/api/v1/timeline")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    assert len(body["data"]) == 3
    types = [item["type"] for item in body["data"]]
    assert types == ["audit", "telemetry", "winlog"]
    stamps = [item["timestamp"] for item in body["data"]]
    assert stamps == sorted(stamps, reverse=True)
    first = body["data"][0]
    assert first["entity_id"] == _ASSET_ID
    assert first["entity_type"] == "asset"
    assert "pagination" in body
    assert body["pagination"]["total_records"] == 3


def test_timeline_type_filter(timeline_overrides, client: TestClient):
    resp = client.get("/api/v1/timeline", params={"type": "winlog"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert all(item["type"] == "winlog" for item in body["data"])
    assert len(body["data"]) == 1


def test_timeline_severity_filter(timeline_overrides, client: TestClient):
    resp = client.get("/api/v1/timeline", params={"severity": "Critical"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["type"] == "winlog"


def test_timeline_entity_id_filter(timeline_overrides, client: TestClient):
    other = str(uuid.uuid4())
    resp = client.get("/api/v1/timeline", params={"entity_id": other})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == []


def test_timeline_works_for_guest_without_token(timeline_overrides, client: TestClient):
    resp = client.get("/api/v1/timeline")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


def test_timeline_rejects_unknown_type(timeline_overrides, client: TestClient):
    resp = client.get("/api/v1/timeline", params={"type": "analysis"})
    assert resp.status_code == 422


def test_timeline_rejects_invalid_entity_id(timeline_overrides, client: TestClient):
    resp = client.get("/api/v1/timeline", params={"entity_id": "not-a-uuid"})
    assert resp.status_code == 422


def test_timeline_from_to_alias_parameters(timeline_overrides, client: TestClient):
    resp = client.get(
        "/api/v1/timeline",
        params={"from": "2026-08-10T00:00:00Z", "to": "2026-08-31T00:00:00Z"},
    )
    assert resp.status_code == 200, resp.text