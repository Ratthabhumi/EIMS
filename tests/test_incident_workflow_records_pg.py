"""Diagnosis / remediation records with honest actor assurance (real PostgreSQL).

EIMS has no application login. Assurance is derived server-side from the actual
credential: none -> unattributed, shared admin token -> shared-token, valid
session JWT for a user -> verified-identity. Only verified-identity reviewers
may confirm a root cause, and only they may resolve or close an incident.
"""
from __future__ import annotations

import asyncio
import importlib.util
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import jwt
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from backend.domain.analyzer import auth
from backend.domain.analyzer.services import session_security
from backend.domain.incident.controller import incident_router
from backend.domain.incident.models import IncidentVerification
from backend.domain.incident.workflow_models import (
    IncidentDiagnosis,
    IncidentRemediation,
    IncidentWorkflowEvent,
)
from backend.infrastructure.database import get_db_session
from tests.incident_db_support import (
    INCIDENT_TABLES,
    create_asset,
    create_schema,
    create_user,
    require_database_url,
    session_factory,
    session_id,
)

TEST_KEY = "synthetic-incident-signing-key-only-20261119"
ADMIN_TOKEN = "synthetic-incident-admin-token-only"
BASE = datetime(2026, 11, 19, 11, 0, tzinfo=UTC)
TABLES = list(INCIDENT_TABLES)  # includes the workflow tables
CAND = "veeam_vbr:eims_diagnostic:VMWARE-CBT-DELETE-FAILED"


def _migration():
    path = (Path(__file__).resolve().parents[1] / "migrations" / "versions"
            / "c3e6a9d1f402_add_incident_diagnosis_remediation.py")
    spec = importlib.util.spec_from_file_location("_workflow_migration", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def jwt_header(username: str) -> dict[str, str]:
    payload = {"sub": username, "sid": session_id(username),
               "exp": datetime.now(UTC) + timedelta(minutes=5)}
    return {"Authorization": "Bearer " + jwt.encode(payload, TEST_KEY, algorithm="HS256")}


TOKEN = {"Authorization": "Bearer " + ADMIN_TOKEN}
OPEN: dict[str, str] = {}


@pytest.fixture
def api(monkeypatch):
    url = require_database_url()
    _schema, engine = asyncio.run(create_schema(url, tables=TABLES))

    async def prepare():
        mod = _migration()
        async with engine.begin() as conn:
            for ddl in (mod.APPEND_ONLY_FUNCTION_DDL, mod.APPEND_ONLY_TRIGGER_DDL,
                        mod.APPEND_ONLY_TRUNCATE_DDL):
                await conn.execute(text(ddl))
        await create_user(engine, "engineer", role="user")
        await create_user(engine, "reviewer", role="user", knowledge_reviewer=True)
        await create_user(engine, "reviewer2", role="user", knowledge_reviewer=True)
        # A privileged account whose literal name equals what the shared token resolves to.
        await create_user(engine, "admin", role="admin")
        # Accounts whose names collide with the open-access / shared-token identifiers.
        await create_user(engine, "demo", role="admin", knowledge_reviewer=True)
        await create_user(engine, "shared-admin-token", role="admin", knowledge_reviewer=True)
        return await create_asset(engine)

    asset_id = asyncio.run(prepare())
    monkeypatch.setattr(auth.settings, "AUTH_MODE", "secure")
    monkeypatch.setattr(auth.settings, "ADMIN_TOKEN", ADMIN_TOKEN)
    monkeypatch.setattr(auth, "SECRET_KEY", TEST_KEY)
    monkeypatch.setattr(auth, "ALGORITHM", "HS256")
    monkeypatch.setattr(session_security, "THROTTLE_NAMESPACE", "pytest-incident-workflow")

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
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://synthetic-incident")


def _body(asset_id, source_id: str) -> dict:
    return {"title": "Synthetic incident", "severity": "high", "asset_id": str(asset_id),
            "evidence": [{"source_type": "winlog", "source_id": source_id,
                          "source_event_key": "4625", "observed_at": BASE.isoformat()}]}


async def _incident(client, asset_id, source_id="win-wf-1"):
    created = await client.post("/api/v1/incidents", json=_body(asset_id, source_id),
                                headers=jwt_header("engineer"))
    assert created.status_code == 201, created.text
    payload = created.json()
    return payload["incident_id"], [e["evidence_id"] for e in payload["evidence"]]


def _diag(evidence_ids=(), **extra) -> dict:
    return {"hypothesis": "CTK file locked by a stale snapshot", "reasoning": "log pattern",
            "stated_confidence": "medium", "supporting_evidence_ids": list(evidence_ids), **extra}


def _remediation(**extra) -> dict:
    return {"action": "Consolidate snapshots then reset CBT", "risk": "Next backup is a full backup",
            "rollback_plan": "Restore previous disk chain from backup",
            "expected_verification_criteria": "Next job completes without CTK error", **extra}


def test_assurance_comes_from_the_credential_never_from_the_body(api):
    app, asset_id, _ = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            url = f"/api/v1/incidents/{iid}/diagnoses"
            none = (await client.post(url, json=_diag(ev), headers=OPEN)).json()
            token = (await client.post(url, json=_diag(ev), headers=TOKEN)).json()
            person = (await client.post(url, json=_diag(ev), headers=jwt_header("engineer"))).json()
            assert (none["proposed_assurance"], none["proposed_by"]) == ("unattributed", "demo")
            assert (token["proposed_assurance"], token["proposed_by"]) == ("shared-token", "shared-admin-token")
            assert (person["proposed_assurance"], person["proposed_by"]) == ("verified-identity", "engineer")
            for forged in ({"actor": "reviewer"}, {"proposed_assurance": "verified-identity"},
                           {"proposed_by": "reviewer"}, {"record_digest": "0" * 64},
                           {"knowledge": {"classification": "approved_diagnostic_match"}},
                           {"status": "confirmed"}):
                r = await client.post(url, json=_diag(ev, **forged), headers=OPEN)
                assert r.status_code == 422, (forged, r.text)

    asyncio.run(scenario())


def test_hypothesis_moves_root_cause_to_hypothesis_but_never_to_confirmed(api):
    app, asset_id, _ = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            before = (await client.get(f"/api/v1/incidents/{iid}", headers=OPEN)).json()
            assert before["root_cause_state"] == "unknown"
            await client.post(f"/api/v1/incidents/{iid}/diagnoses", json=_diag(ev), headers=OPEN)
            after = (await client.get(f"/api/v1/incidents/{iid}", headers=OPEN)).json()
            assert after["root_cause_state"] == "hypothesis"

    asyncio.run(scenario())


def test_only_a_verified_reviewer_can_confirm_a_root_cause(api):
    app, asset_id, _ = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            diag = (await client.post(f"/api/v1/incidents/{iid}/diagnoses", json=_diag(ev),
                                      headers=OPEN)).json()
            url = f"/api/v1/incidents/{iid}/diagnoses/{diag['diagnosis_id']}/confirm"
            body = {"rationale": "reproduced in lab"}
            for who, headers in (("open", OPEN), ("shared token", TOKEN),
                                 ("verified non-reviewer", jwt_header("engineer"))):
                r = await client.post(url, json=body, headers=headers)
                assert r.status_code == 403, (who, r.text)
            state = (await client.get(f"/api/v1/incidents/{iid}", headers=OPEN)).json()
            assert state["root_cause_state"] == "hypothesis"

            ok = await client.post(url, json=body, headers=jwt_header("reviewer"))
            assert ok.status_code == 200, ok.text
            confirmed = ok.json()
            assert confirmed["status"] == "confirmed"
            assert (confirmed["confirmed_by"], confirmed["confirmed_assurance"]) == ("reviewer", "verified-identity")
            assert (await client.get(f"/api/v1/incidents/{iid}", headers=OPEN)).json()["root_cause_state"] == "confirmed"
            again = await client.post(url, json=body, headers=jwt_header("reviewer2"))
            assert again.status_code == 409

    asyncio.run(scenario())


def test_confirmation_needs_supporting_evidence_and_an_independent_confirmer(api):
    app, asset_id, _ = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            bare = (await client.post(f"/api/v1/incidents/{iid}/diagnoses", json=_diag(),
                                      headers=jwt_header("reviewer"))).json()
            r = await client.post(f"/api/v1/incidents/{iid}/diagnoses/{bare['diagnosis_id']}/confirm",
                                  json={"rationale": "x"}, headers=jwt_header("reviewer2"))
            assert r.status_code == 422, r.text

            own = (await client.post(f"/api/v1/incidents/{iid}/diagnoses", json=_diag(ev),
                                     headers=jwt_header("reviewer"))).json()
            url = f"/api/v1/incidents/{iid}/diagnoses/{own['diagnosis_id']}/confirm"
            assert (await client.post(url, json={"rationale": "x"},
                                      headers=jwt_header("reviewer"))).status_code == 403
            assert (await client.post(url, json={"rationale": "x"},
                                      headers=jwt_header("reviewer2"))).status_code == 200

    asyncio.run(scenario())


def test_evidence_links_must_belong_to_the_incident_and_not_overlap(api):
    app, asset_id, engine = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id, "win-wf-a")
            other_asset = await create_asset(engine, "other-host-b")
            _other, other_ev = await _incident(client, other_asset, "win-wf-b")
            url = f"/api/v1/incidents/{iid}/diagnoses"
            assert (await client.post(url, json=_diag(other_ev), headers=OPEN)).status_code == 422
            assert (await client.post(
                url, json=_diag(ev, contradicting_evidence_ids=ev), headers=OPEN)).status_code == 422
            ok = await client.post(url, json=_diag(ev, contradicting_evidence_ids=[]), headers=OPEN)
            assert ok.status_code == 201

    asyncio.run(scenario())


def test_knowledge_snapshot_is_computed_server_side(api):
    app, asset_id, _ = api

    async def scenario():
        from backend.domain.knowledge.service import _catalog, canonical_hash

        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            url = f"/api/v1/incidents/{iid}/diagnoses"
            r = await client.post(url, json=_diag(ev, catalog_id=CAND), headers=OPEN)
            assert r.status_code == 201, r.text
            snap = r.json()["knowledge"]
            # An unreviewed candidate (and no overlay table in this schema) can never be trusted.
            assert snap["classification"] == "diagnostic_candidate_match"
            assert snap["catalog_id"] == CAND
            assert snap["content_hash"] == canonical_hash(_catalog()[CAND])
            assert snap["overlay_available"] is False
            bad = await client.post(url, json=_diag(ev, catalog_id="nope:nope:nope"), headers=OPEN)
            assert bad.status_code == 422
            assert (await client.post(url, json=_diag(ev), headers=OPEN)).json()["knowledge"] is None

    asyncio.run(scenario())


def test_remediation_proposal_requires_risk_rollback_and_criteria(api):
    app, asset_id, _ = api

    async def scenario():
        async with _client(app) as client:
            iid, _ev = await _incident(client, asset_id)
            url = f"/api/v1/incidents/{iid}/remediations"
            for missing in ("risk", "rollback_plan", "expected_verification_criteria", "action"):
                body = _remediation()
                body.pop(missing)
                assert (await client.post(url, json=body, headers=OPEN)).status_code == 422, missing
                blank = {**_remediation(), missing: "   "}
                assert (await client.post(url, json=blank, headers=OPEN)).status_code in (422,), missing
            for forged in ({"verification_state": "verified"}, {"status": "executed"},
                           {"executed_by": "reviewer"}):
                assert (await client.post(url, json=_remediation(**forged), headers=OPEN)).status_code == 422
            ok = await client.post(url, json=_remediation(), headers=OPEN)
            assert ok.status_code == 201, ok.text
            row = ok.json()
            assert (row["status"], row["proposed_assurance"], row["verification_state"]) == (
                "proposed", "unattributed", "unverified")

    asyncio.run(scenario())


def test_execution_is_recorded_once_with_assurance_and_never_verifies(api):
    app, asset_id, engine = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            diag = (await client.post(f"/api/v1/incidents/{iid}/diagnoses", json=_diag(ev),
                                      headers=OPEN)).json()
            rem = (await client.post(f"/api/v1/incidents/{iid}/remediations",
                                     json=_remediation(diagnosis_id=diag["diagnosis_id"]),
                                     headers=OPEN)).json()
            url = f"/api/v1/incidents/{iid}/remediations/{rem['remediation_id']}/execution"
            payload = {"actual_action": "Consolidated snapshots, reset CBT", "outcome": "succeeded",
                       "outcome_notes": "job re-run pending", "evidence_ids": ev}
            for forged in ({"verification_state": "verified"}, {"executed_by": "reviewer"}):
                assert (await client.post(url, json={**payload, **forged}, headers=OPEN)).status_code == 422
            other_asset = await create_asset(engine, "other-host-x")
            _o, other_ev = await _incident(client, other_asset, "win-wf-x")
            assert (await client.post(url, json={**payload, "evidence_ids": other_ev},
                                      headers=OPEN)).status_code == 422
            done = await client.post(url, json=payload, headers=TOKEN)
            assert done.status_code == 200, done.text
            body = done.json()
            assert (body["status"], body["outcome"]) == ("executed", "succeeded")
            assert (body["executed_by"], body["executed_assurance"]) == ("shared-admin-token", "shared-token")
            assert (await client.post(url, json=payload, headers=OPEN)).status_code == 409
            listed = (await client.get(f"/api/v1/incidents/{iid}/remediations", headers=OPEN)).json()
            assert listed[0]["verification_state"] == "unverified"
            wrong_diag = await client.post(
                f"/api/v1/incidents/{iid}/remediations",
                json=_remediation(diagnosis_id=str(uuid.uuid4())), headers=OPEN)
            assert wrong_diag.status_code == 422

    asyncio.run(scenario())


def test_verification_state_is_derived_from_incident_verification_only(api):
    app, asset_id, engine = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            rem = (await client.post(f"/api/v1/incidents/{iid}/remediations", json=_remediation(),
                                     headers=OPEN)).json()
            await client.post(
                f"/api/v1/incidents/{iid}/remediations/{rem['remediation_id']}/execution",
                json={"actual_action": "done", "outcome": "succeeded", "evidence_ids": []}, headers=OPEN)
            state = lambda: client.get(f"/api/v1/incidents/{iid}/remediations", headers=OPEN)  # noqa: E731
            assert (await state()).json()[0]["verification_state"] == "unverified"

            async with session_factory(engine)() as db:
                db.add(IncidentVerification(
                    incident_id=uuid.UUID(iid), remediation_cycle=99, evidence_id=uuid.UUID(ev[0]),
                    evidence_digest="0" * 64, outcome="passed", verifier_id="reviewer"))
                await db.commit()
            assert (await state()).json()[0]["verification_state"] == "unverified"  # wrong cycle

            async with session_factory(engine)() as db:
                db.add(IncidentVerification(
                    incident_id=uuid.UUID(iid), remediation_cycle=0, evidence_id=uuid.UUID(ev[0]),
                    evidence_digest="0" * 64, outcome="passed", verifier_id="reviewer"))
                await db.commit()
            assert (await state()).json()[0]["verification_state"] == "verified"

    asyncio.run(scenario())


@pytest.mark.parametrize("target", ["resolved", "closed"])
def test_open_access_and_shared_token_can_never_resolve_or_close(api, target):
    app, asset_id, _ = api

    async def scenario():
        async with _client(app) as client:
            iid, _ev = await _incident(client, asset_id)
            url = f"/api/v1/incidents/{iid}/status"
            body = {"status": target}
            for headers in (OPEN, TOKEN):
                r = await client.patch(url, json=body, headers=headers)
                assert r.status_code == 403, (target, headers, r.text)
            state = (await client.get(f"/api/v1/incidents/{iid}", headers=OPEN)).json()
            assert state["status"] == "open"

    asyncio.run(scenario())


def test_workflow_events_record_assurance_and_are_append_only(api):
    app, asset_id, engine = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            diag = (await client.post(f"/api/v1/incidents/{iid}/diagnoses", json=_diag(ev),
                                      headers=OPEN)).json()
            await client.post(f"/api/v1/incidents/{iid}/diagnoses/{diag['diagnosis_id']}/confirm",
                              json={"rationale": "lab"}, headers=jwt_header("reviewer"))
            events = (await client.get(f"/api/v1/incidents/{iid}/workflow-events", headers=OPEN)).json()
            assert [(e["record_type"], e["action"], e["actor_assurance"]) for e in events] == [
                ("diagnosis", "proposed", "unattributed"),
                ("diagnosis", "confirmed", "verified-identity"),
            ]
            assert all(len(e["record_digest"]) == 64 for e in events)

        async with engine.begin() as conn:
            for statement in ("UPDATE incident_workflow_event SET actor = 'x'",
                              "DELETE FROM incident_workflow_event",
                              "TRUNCATE incident_workflow_event"):
                with pytest.raises(Exception, match="append-only"):
                    async with conn.begin_nested():
                        await conn.execute(text(statement))

    asyncio.run(scenario())


def test_existing_incident_invariants_still_hold_for_a_reviewer(api):
    """The reviewer path is unchanged: a verified reviewer can still be authorised to close."""
    app, asset_id, _ = api

    async def scenario():
        async with _client(app) as client:
            iid, _ev = await _incident(client, asset_id)
            r = await client.patch(f"/api/v1/incidents/{iid}/status", json={"status": "triage"},
                                   headers=jwt_header("engineer"))
            assert r.status_code == 200, r.text
            # resolving still demands verification evidence, even for a verified reviewer
            r = await client.patch(f"/api/v1/incidents/{iid}/status", json={"status": "investigating"},
                                   headers=jwt_header("engineer"))
            assert r.status_code == 200, r.text
            # Legal edge (investigating -> resolved). Open-access and shared-token callers are
            # blocked by the assurance guard itself, not merely by an illegal transition.
            for headers in (OPEN, TOKEN):
                blocked = await client.patch(f"/api/v1/incidents/{iid}/status",
                                             json={"status": "resolved"}, headers=headers)
                assert blocked.status_code == 403, blocked.text
                assert "verified-identity" in blocked.text
            # A verified reviewer passes the guard and then meets the verification requirement.
            r = await client.patch(f"/api/v1/incidents/{iid}/status", json={"status": "resolved"},
                                   headers=jwt_header("reviewer"))
            assert r.status_code == 422, r.text
            assert "missing_verification" in r.text

    asyncio.run(scenario())


def test_usernames_colliding_with_reserved_identifiers_cannot_masquerade(api):
    app, asset_id, _ = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            url = f"/api/v1/incidents/{iid}/diagnoses"
            for name in ("demo", "shared-admin-token"):
                row = (await client.post(url, json=_diag(ev), headers=jwt_header(name))).json()
                assert (row["proposed_by"], row["proposed_assurance"]) == ("demo", "unattributed"), name
                denied = await client.post(f"{url}/{row['diagnosis_id']}/confirm",
                                           json={"rationale": "x"}, headers=jwt_header(name))
                assert denied.status_code == 403, name
                status = await client.patch(f"/api/v1/incidents/{iid}/status",
                                            json={"status": "closed"}, headers=jwt_header(name))
                assert status.status_code == 403, name
            # A genuine session for the seeded "admin" user is a verified identity.
            diag = (await client.post(url, json=_diag(ev), headers=jwt_header("engineer"))).json()
            ok = await client.post(f"{url}/{diag['diagnosis_id']}/confirm",
                                   json={"rationale": "lab"}, headers=jwt_header("admin"))
            assert ok.status_code == 200, ok.text
            assert ok.json()["confirmed_by"] == "admin"

    asyncio.run(scenario())


def test_database_constraints_enforce_confirmation_rules_independently_of_the_app(api):
    app, asset_id, engine = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            url = f"/api/v1/incidents/{iid}/diagnoses"
            first = (await client.post(url, json=_diag(ev), headers=OPEN)).json()["diagnosis_id"]
            second = (await client.post(url, json=_diag(ev), headers=OPEN)).json()["diagnosis_id"]

        async def attempt(sql: str, **params):
            async with engine.begin() as conn:
                with pytest.raises(Exception, match="violates|constraint"):
                    await conn.execute(text(sql), params)

        confirm = ("UPDATE incident_diagnosis SET status='confirmed', confirmed_by=:by, "
                   "confirmed_at=now(), confirmed_assurance=:assurance WHERE diagnosis_id=:id")
        await attempt(confirm, by="x", assurance=None, id=first)               # no assurance
        await attempt(confirm, by="x", assurance="shared-token", id=first)     # not verified
        await attempt(confirm, by="demo", assurance="verified-identity", id=first)  # == proposer
        async with engine.begin() as conn:
            await conn.execute(text(confirm), {"by": "reviewer", "assurance": "verified-identity", "id": first})
        await attempt(confirm, by="reviewer2", assurance="verified-identity", id=second)  # 2nd in cycle

    asyncio.run(scenario())


def test_reopen_resets_root_cause_state_and_old_cycle_diagnoses_cannot_be_reconfirmed(api):
    from tests.incident_db_support import attach_analysis_evidence

    app, asset_id, engine = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            eng = jwt_header("engineer")
            base = f"/api/v1/incidents/{iid}"
            for target in ("triage", "investigating"):
                assert (await client.patch(f"{base}/status", json={"status": target}, headers=eng)).status_code == 200
            diag = (await client.post(f"{base}/diagnoses", json=_diag(ev), headers=OPEN)).json()
            confirm = f"{base}/diagnoses/{diag['diagnosis_id']}/confirm"
            assert (await client.post(confirm, json={"rationale": "lab"},
                                      headers=jwt_header("reviewer"))).status_code == 200
            assert (await client.get(base, headers=OPEN)).json()["root_cause_state"] == "confirmed"

            proof = await attach_analysis_evidence(engine, uuid.UUID(iid), asset_id=asset_id)
            resolved = await client.patch(
                f"{base}/status", json={"status": "resolved", "verification": {"evidence_id": str(proof)}},
                headers=jwt_header("reviewer"))
            assert resolved.status_code == 200, resolved.text
            # records cannot be added to a resolved incident
            rejected = await client.post(f"{base}/diagnoses", json=_diag(ev), headers=OPEN)
            assert rejected.status_code == 409, rejected.text

            reopened = await client.patch(f"{base}/status", json={"status": "investigating"}, headers=eng)
            assert reopened.status_code == 200, reopened.text
            state = reopened.json()
            assert state["remediation_cycle"] == 1
            assert state["root_cause_state"] == "unknown", "a new cycle has no live diagnosis"
            stale = await client.post(confirm, json={"rationale": "again"}, headers=jwt_header("reviewer2"))
            assert stale.status_code in (409,), stale.text
            fresh = (await client.post(f"{base}/diagnoses", json=_diag(ev), headers=OPEN)).json()
            ok = await client.post(f"{base}/diagnoses/{fresh['diagnosis_id']}/confirm",
                                   json={"rationale": "new cycle"}, headers=jwt_header("reviewer2"))
            assert ok.status_code == 200, ok.text

    asyncio.run(scenario())


def test_dangling_analysis_reference_is_rejected(api):
    app, asset_id, _ = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            r = await client.post(f"/api/v1/incidents/{iid}/diagnoses",
                                  json=_diag(ev, analysis_history_id=987654), headers=OPEN)
            assert r.status_code == 422, r.text

    asyncio.run(scenario())


def test_failed_execution_is_never_reported_as_verified_even_with_a_passed_verification(api):
    app, asset_id, engine = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            rem = (await client.post(f"/api/v1/incidents/{iid}/remediations", json=_remediation(),
                                     headers=OPEN)).json()
            await client.post(
                f"/api/v1/incidents/{iid}/remediations/{rem['remediation_id']}/execution",
                json={"actual_action": "tried", "outcome": "failed"}, headers=OPEN)
            async with session_factory(engine)() as db:
                db.add(IncidentVerification(
                    incident_id=uuid.UUID(iid), remediation_cycle=0, evidence_id=uuid.UUID(ev[0]),
                    evidence_digest="0" * 64, outcome="passed", verifier_id="reviewer"))
                await db.commit()
            listed = (await client.get(f"/api/v1/incidents/{iid}/remediations", headers=OPEN)).json()
            assert listed[0]["verification_state"] == "unverified"

    asyncio.run(scenario())


def test_real_alembic_chain_creates_workflow_tables_with_append_only_audit():
    """The shipped migration (not create_all) builds the tables and the protection."""
    from tests.test_knowledge_overlay_pg import _create_schema, _migrate

    url = require_database_url()

    async def scenario():
        schema, bootstrap = _create_schema(url)
        try:
            await _migrate(bootstrap, schema)
            async with bootstrap.connect() as conn:
                await conn.execute(text(f'SET search_path TO "{schema}", public'))
                tables = set((await conn.execute(text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = :s"), {"s": schema})).scalars())
                assert {"incident_diagnosis", "incident_remediation", "incident_workflow_event"} <= tables
                triggers = set((await conn.execute(text(
                    "SELECT tgname FROM pg_trigger WHERE tgrelid = "
                    f"'\"{schema}\".incident_workflow_event'::regclass AND NOT tgisinternal"))).scalars())
                assert triggers == {"trg_incident_workflow_event_append_only",
                                    "trg_incident_workflow_event_append_only_truncate"}
                head = await conn.scalar(text(f'SELECT version_num FROM "{schema}".alembic_version'))
                assert head == "c9f4a7b0d826"
                await conn.rollback()
        finally:
            await bootstrap.dispose()

    asyncio.run(scenario())
