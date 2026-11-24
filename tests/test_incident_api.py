"""Incident Core API contract: authentication, Engineer writes, Reviewer close."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from fastapi import FastAPI

from backend.domain.analyzer import auth
from backend.domain.analyzer.services import session_security
from backend.domain.incident.controller import incident_router
from backend.infrastructure.database import get_db_session
from tests.incident_db_support import (
    attach_analysis_evidence,
    create_asset,
    create_schema,
    create_user,
    require_database_url,
    session_factory,
    session_id,
)

TEST_KEY = "synthetic-incident-signing-key-only-20261116"
BASE = datetime(2026, 11, 16, 11, 0, tzinfo=UTC)


def _bearer(username: str) -> dict[str, str]:
    payload = {
        "sub": username,
        "sid": session_id(username),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    return {"Authorization": "Bearer " + jwt.encode(payload, TEST_KEY, algorithm="HS256")}


def _body(asset_id, source_id: str = "win-api-1") -> dict:
    return {
        "title": "Synthetic incident",
        "severity": "high",
        "asset_id": str(asset_id),
        "evidence": [
            {
                "source_type": "winlog",
                "source_id": source_id,
                "source_event_key": "4625",
                "observed_at": BASE.isoformat(),
            }
        ],
    }


@pytest.fixture
def api(monkeypatch):
    url = require_database_url()
    _schema, engine = asyncio.run(create_schema(url))
    asyncio.run(create_user(engine, "engineer", role="user"))
    asyncio.run(create_user(engine, "reviewer", role="user", knowledge_reviewer=True))
    asset_id = asyncio.run(create_asset(engine))

    monkeypatch.setattr(auth.settings, "AUTH_MODE", "secure")
    monkeypatch.setattr(auth.settings, "ADMIN_TOKEN", "synthetic-incident-admin-token-only")
    monkeypatch.setattr(auth, "SECRET_KEY", TEST_KEY)
    monkeypatch.setattr(auth, "ALGORITHM", "HS256")
    monkeypatch.setattr(session_security, "THROTTLE_NAMESPACE", "pytest-incident")

    app = FastAPI()
    app.include_router(incident_router)

    async def db_override():
        async with session_factory(engine)() as db:
            yield db

    app.dependency_overrides[get_db_session] = db_override
    try:
        yield app, asset_id, engine
    finally:
        asyncio.run(engine.dispose())


def _client(app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://synthetic-incident"
    )


def test_open_access_may_record_but_never_resolve_or_close(api):
    """Replaces `test_unauthenticated_requests_are_rejected` (2026-11-19).

    That test asserted 401 for every unauthenticated call. The accepted product contract (see
    `get_current_user` in backend/domain/analyzer/auth.py: "EIMS has no application login") is that a
    missing credential resolves to the open-access principal, so reads and ordinary records are allowed.
    What must still hold is the security boundary the old test was protecting: an unattributed caller can
    never perform the privileged transitions. Those are asserted here; see also
    tests/test_incident_workflow_records_pg.py for confirmation and tests/test_incident_workflow_alignment_pg.py
    for the domain-service checks.
    """
    app, asset_id, _engine = api

    async def scenario():
        async with _client(app) as client:
            assert (await client.get("/api/v1/incidents")).status_code == 200
            created = await client.post("/api/v1/incidents", json=_body(asset_id))
            assert created.status_code == 201, created.text
            incident = created.json()
            assert incident["evidence"][0]["added_by"] == "demo"      # attributed to open access, nobody else
            iid = incident["incident_id"]
            base = f"/api/v1/incidents/{iid}/status"
            for step in ("triage", "investigating"):
                assert (await client.patch(base, json={"status": step})).status_code == 200
            for target in ("resolved", "closed"):
                denied = await client.patch(base, json={"status": target})
                assert denied.status_code == 403, (target, denied.text)
            # an unknown id is a 404, not an open door
            assert (await client.patch("/api/v1/incidents/11111111-1111-4111-8111-111111111111/status",
                                       json={"status": "triage"})).status_code == 404

    asyncio.run(scenario())


def test_engineer_creates_reads_and_attaches_evidence(api):
    app, asset_id, _engine = api

    async def scenario():
        async with _client(app) as client:
            engineer = _bearer("engineer")
            created = await client.post(
                "/api/v1/incidents", json=_body(asset_id), headers=engineer
            )
            assert created.status_code == 201, created.text
            payload = created.json()
            assert payload["status"] == "open"
            assert payload["confidence"] == "weak"
            assert payload["root_cause_state"] == "unknown"
            assert payload["asset_id"] == str(asset_id)
            assert len(payload["evidence"]) == 1
            incident_id = payload["incident_id"]

            listed = await client.get("/api/v1/incidents", headers=engineer)
            assert listed.status_code == 200
            assert listed.json()["pagination"]["total_records"] == 1
            assert listed.json()["data"][0]["incident_id"] == incident_id

            filtered = await client.get(
                "/api/v1/incidents", params={"status": "open", "severity": "high"}, headers=engineer
            )
            assert filtered.status_code == 200
            assert filtered.json()["pagination"]["total_records"] == 1
            empty = await client.get(
                "/api/v1/incidents", params={"status": "closed"}, headers=engineer
            )
            assert empty.json()["pagination"]["total_records"] == 0

            detail = await client.get(f"/api/v1/incidents/{incident_id}", headers=engineer)
            assert detail.status_code == 200
            assert detail.json()["incident_id"] == incident_id

            attached = await client.post(
                f"/api/v1/incidents/{incident_id}/evidence",
                json={
                    "evidence": [
                        {
                            "source_type": "telemetry",
                            "source_id": "metric-1",
                            "source_event_key": "cpu-saturation",
                            "observed_at": BASE.isoformat(),
                        }
                    ]
                },
                headers=engineer,
            )
            assert attached.status_code == 200, attached.text
            assert len(attached.json()["evidence"]) == 2

            evidence = await client.get(
                f"/api/v1/incidents/{incident_id}/evidence", headers=engineer
            )
            assert evidence.status_code == 200
            assert evidence.json()["pagination"]["total_records"] == 2

            duplicate = await client.post(
                f"/api/v1/incidents/{incident_id}/evidence",
                json={
                    "evidence": [
                        {
                            "source_type": "telemetry",
                            "source_id": "metric-1",
                            "observed_at": BASE.isoformat(),
                        }
                    ]
                },
                headers=engineer,
            )
            assert duplicate.status_code == 200
            assert len(duplicate.json()["evidence"]) == 2

            missing = await client.get(
                "/api/v1/incidents/22222222-2222-4222-8222-222222222222", headers=engineer
            )
            assert missing.status_code == 404

    asyncio.run(scenario())


def test_status_transitions_and_reviewer_only_closure(api):
    app, asset_id, engine = api

    async def scenario():
        async with _client(app) as client:
            engineer = _bearer("engineer")
            reviewer = _bearer("reviewer")
            created = await client.post(
                "/api/v1/incidents", json=_body(asset_id, "win-api-close"), headers=engineer
            )
            assert created.status_code == 201, created.text
            incident_id = created.json()["incident_id"]

            illegal = await client.patch(
                f"/api/v1/incidents/{incident_id}/status",
                json={"status": "resolved"},
                headers=engineer,
            )
            assert illegal.status_code == 409, illegal.text

            for target in ("triage", "investigating"):
                response = await client.patch(
                    f"/api/v1/incidents/{incident_id}/status",
                    json={"status": target},
                    headers=engineer,
                )
                assert response.status_code == 200, response.text
                assert response.json()["status"] == target

            # Resolution without verification is refused even for a reviewer.
            blocked = await client.patch(
                f"/api/v1/incidents/{incident_id}/status",
                json={"status": "resolved"},
                headers=reviewer,
            )
            assert blocked.status_code == 422, blocked.text
            assert "missing_verification" in blocked.text

            evidence_id = await attach_analysis_evidence(
                engine, incident_id, asset_id=asset_id
            )

            # An engineer may attach evidence but cannot authorise verification.
            denied_verify = await client.patch(
                f"/api/v1/incidents/{incident_id}/status",
                json={"status": "resolved", "verification": {"evidence_id": str(evidence_id)}},
                headers=engineer,
            )
            assert denied_verify.status_code == 403, denied_verify.text

            resolved = await client.patch(
                f"/api/v1/incidents/{incident_id}/status",
                json={"status": "resolved", "verification": {"evidence_id": str(evidence_id)}},
                headers=reviewer,
            )
            assert resolved.status_code == 200, resolved.text
            assert resolved.json()["status"] == "resolved"
            assert resolved.json()["verifications"][-1]["verifier_id"] == "reviewer"
            assert resolved.json()["verifications"][-1]["remediation_cycle"] == 0

            denied = await client.patch(
                f"/api/v1/incidents/{incident_id}/status",
                json={"status": "closed"},
                headers=engineer,
            )
            assert denied.status_code == 403, denied.text

            closed = await client.patch(
                f"/api/v1/incidents/{incident_id}/status",
                json={"status": "closed"},
                headers=reviewer,
            )
            assert closed.status_code == 200, closed.text
            assert closed.json()["status"] == "closed"
            assert closed.json()["owner"] == "reviewer"
            assert closed.json()["root_cause_state"] == "unknown"

            reopened = await client.patch(
                f"/api/v1/incidents/{incident_id}/status",
                json={"status": "investigating"},
                headers=reviewer,
            )
            assert reopened.status_code == 409, reopened.text

            invalid_literal = await client.patch(
                f"/api/v1/incidents/{incident_id}/status",
                json={"status": "archived"},
                headers=reviewer,
            )
            assert invalid_literal.status_code == 422, invalid_literal.text

    asyncio.run(scenario())
