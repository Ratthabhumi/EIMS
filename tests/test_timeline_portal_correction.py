"""Focused Portal Correction tests for Timeline description mapping and filters."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.domain.timeline.controller import get_timeline_service
from backend.domain.timeline.schemas import TimelineEvent
from backend.domain.timeline.service import TimelineService, describe_audit_action
from backend.main import app


def test_describe_import_and_update_verbs_keep_original():
    import_text = describe_audit_action("IMPORT_REPORT", {"event": "Offline USB Auditor Import"})
    assert "Imported an offline USB Auditor report" in import_text
    assert "IMPORT_REPORT" in import_text

    update_text = describe_audit_action(
        "UPDATE_FROM_REPORT",
        {"event": "Offline USB Auditor Update", "new_score": 88},
    )
    assert "Updated the asset from an offline USB Auditor report" in update_text
    assert "UPDATE_FROM_REPORT" in update_text


def test_describe_incident_status_transition():
    text = describe_audit_action(
        "INCIDENT_STATUS_CHANGED",
        {"previous_state": "investigating", "new_state": "resolved", "incident_id": str(uuid4())},
    )
    assert "Changed the incident lifecycle status" in text
    assert "investigating → resolved" in text
    assert "INCIDENT_STATUS_CHANGED" in text


def test_describe_unknown_verb_is_honest():
    text = describe_audit_action("CUSTOM_VERB", {})
    assert "CUSTOM_VERB" in text


def test_build_event_marks_missing_correlation_unavailable_fields():
    row = SimpleNamespace(
        id=str(uuid4()),
        type="audit",
        title="IMPORT_REPORT",
        description="",
        severity="Information",
        timestamp=datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc),
        actor_id=None,
        entity_id=str(uuid4()),
        metadata={"event": "Offline USB Auditor Import"},
    )
    event = TimelineService._build_event(row)
    assert event.metadata.get("correlation_id") is None
    assert event.metadata.get("assurance") == "historical_unavailable"
    assert "IMPORT_REPORT" in event.description
    assert event.actor_id is None
    assert event.entity_id is not None


def test_build_event_preserves_unattributed_assurance():
    row = SimpleNamespace(
        id=str(uuid4()),
        type="audit",
        title="UPDATE_FROM_REPORT",
        description="",
        severity="Information",
        timestamp=datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc),
        actor_id=None,
        entity_id=str(uuid4()),
        metadata={
            "event": "Offline USB Auditor Update",
            "assurance": "unattributed",
            "principal": "open_access",
        },
    )
    event = TimelineService._build_event(row)
    assert event.metadata.get("assurance") == "unattributed"
    assert event.metadata.get("principal") == "open_access"


class StubTimelineService:
    def __init__(self, events):
        self.events = events
        self.calls = []

    async def get_timeline(self, db, entity_id=None, event_type=None, severity=None, from_dt=None, to_dt=None, page=1, limit=50):
        self.calls.append({"event_type": event_type, "page": page, "limit": limit})
        data = self.events
        if event_type is not None:
            data = [e for e in data if e.type == event_type]
        total = len(data)
        start = (page - 1) * limit
        return data[start:start + limit], total


def _event(event_type: str, stamp: datetime) -> TimelineEvent:
    return TimelineEvent(
        id=str(uuid4()),
        type=event_type,
        title=event_type,
        description=f"{event_type} event",
        severity="Information",
        timestamp=stamp,
        actor_id=None,
        entity_id=None,
        entity_type="asset",
        metadata={"incident_id": str(uuid4())} if event_type != "audit" else {},
    )


@pytest.fixture
def portal_timeline_overrides():
    events = [
        _event("verification", datetime(2026, 11, 19, 15, 0, tzinfo=timezone.utc)),
        _event("evidence", datetime(2026, 11, 19, 14, 0, tzinfo=timezone.utc)),
        _event("incident_transition", datetime(2026, 11, 19, 13, 0, tzinfo=timezone.utc)),
        _event("audit", datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)),
    ]
    service = StubTimelineService(events)
    app.dependency_overrides[get_timeline_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_timeline_service, None)


def test_timeline_accepts_new_engineering_type_filters(portal_timeline_overrides, client: TestClient):
    for event_type in ("audit", "incident_transition", "evidence", "verification"):
        resp = client.get("/api/v1/timeline", params={"type": event_type})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "success"
        assert all(item["type"] == event_type for item in body["data"])


def test_timeline_pagination_is_server_side(portal_timeline_overrides, client: TestClient):
    resp = client.get("/api/v1/timeline", params={"page": 1, "limit": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["pagination"]["total_records"] == 4
    assert body["pagination"]["page_size"] == 2
    assert portal_timeline_overrides.calls[-1]["page"] == 1
    assert portal_timeline_overrides.calls[-1]["limit"] == 2


def test_timeline_rejects_unknown_engineering_type(client: TestClient):
    resp = client.get("/api/v1/timeline", params={"type": "fabricated"})
    assert resp.status_code == 422
