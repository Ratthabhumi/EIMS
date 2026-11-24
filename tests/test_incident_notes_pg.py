"""Engineer Notes API (real PostgreSQL, disposable database).

A note is an observation. It is append-only, carries server-derived actor + assurance, appears in the audit timeline,
and has no way to confirm a diagnosis, verify a remediation or change an incident's status.
"""
from __future__ import annotations

import asyncio
import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from backend.domain.analyzer.models.history import AnalysisHistory  # noqa: F401
from backend.domain.incident.workflow_models import IncidentNote
from tests.incident_db_support import session_factory
from tests.test_incident_workflow_records_pg import OPEN, TOKEN, _client, api, jwt_header  # noqa: F401

NOW = datetime.now(UTC).isoformat()


def _migration():
    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "a7d2c5e8f604_add_incident_note.py"
    spec = importlib.util.spec_from_file_location("_note_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _incident(client, asset_id, source_id="9001"):
    payload = {"title": "notes host",
               "evidence": [{"source_type": "winlog", "source_id": source_id, "observed_at": NOW}]}
    if asset_id is not None:
        payload["asset_id"] = str(asset_id)
    made = await client.post("/api/v1/incidents", headers=OPEN, json=payload)
    assert made.status_code == 201, made.text
    return made.json()["incident_id"]


def test_notes_are_listed_oldest_first_with_total_and_pagination(api):
    app, asset_id, engine = api

    async def run():
        async with _client(app) as c:
            iid = await _incident(c, asset_id)
            for n in range(5):
                r = await c.post(f"/api/v1/incidents/{iid}/notes", json={"text": f"observation {n}"}, headers=OPEN)
                assert r.status_code == 201, r.text
            page1 = await c.get(f"/api/v1/incidents/{iid}/notes", params={"limit": 2}, headers=OPEN)
            page2 = await c.get(f"/api/v1/incidents/{iid}/notes", params={"limit": 2, "offset": 2}, headers=OPEN)
            everything = (await c.get(f"/api/v1/incidents/{iid}/notes", headers=OPEN)).json()
        assert page1.headers["X-Total-Count"] == "5"
        assert [n["text"] for n in everything] == [f"observation {n}" for n in range(5)]
        assert [n["text"] for n in page1.json() + page2.json()] == [n["text"] for n in everything[:4]]
        assert {"note_id", "incident_id", "text", "actor", "actor_assurance", "created_at"} == set(everything[0])

    asyncio.run(run())


def test_actor_and_assurance_are_derived_from_the_credential_never_from_the_body(api):
    app, asset_id, engine = api

    async def run():
        async with _client(app) as c:
            iid = await _incident(c, asset_id)
            url = f"/api/v1/incidents/{iid}/notes"
            anonymous = (await c.post(url, json={"text": "open access note"}, headers=OPEN)).json()
            shared = (await c.post(url, json={"text": "shared token note"}, headers=TOKEN)).json()
            person = (await c.post(url, json={"text": "named person note"}, headers=jwt_header("engineer"))).json()
            assert (anonymous["actor"], anonymous["actor_assurance"]) == ("demo", "unattributed")
            assert (shared["actor"], shared["actor_assurance"]) == ("shared-admin-token", "shared-token")
            assert (person["actor"], person["actor_assurance"]) == ("engineer", "verified-identity")
            for forged in ({"text": "x", "actor": "alice"}, {"text": "x", "actor_assurance": "verified-identity"},
                           {"text": "x", "root_cause_state": "confirmed"}, {"text": "x", "status": "resolved"},
                           {"text": "x", "verified": True}, {"text": "x", "created_at": NOW}):
                assert (await c.post(url, json=forged, headers=OPEN)).status_code == 422, forged

    asyncio.run(run())


def test_a_note_never_confirms_a_cause_verifies_or_changes_status(api):
    app, asset_id, engine = api

    async def run():
        async with _client(app) as c:
            iid = await _incident(c, asset_id)
            before = (await c.get(f"/api/v1/incidents/{iid}", headers=OPEN)).json()
            for body in ("Root cause confirmed: DC02 routing", "VERIFIED and RESOLVED", "status: closed"):
                assert (await c.post(f"/api/v1/incidents/{iid}/notes", json={"text": body}, headers=jwt_header("engineer"))
                        ).status_code == 201
            after = (await c.get(f"/api/v1/incidents/{iid}", headers=OPEN)).json()
            diagnoses = (await c.get(f"/api/v1/incidents/{iid}/diagnoses", headers=OPEN)).json()
        assert (after["status"], after["root_cause_state"]) == (before["status"], before["root_cause_state"]) == ("open", "unknown")
        assert diagnoses == []
        assert not after.get("verifications")

    asyncio.run(run())


def test_validation_and_unknown_incident(api):
    app, asset_id, engine = api

    async def run():
        async with _client(app) as c:
            iid = await _incident(c, asset_id)
            url = f"/api/v1/incidents/{iid}/notes"
            for bad in ({"text": ""}, {"text": "   "}, {"text": "x" * 4001}, {}):
                assert (await c.post(url, json=bad, headers=OPEN)).status_code == 422, bad
            assert (await c.post(url, json={"text": "x" * 4000}, headers=OPEN)).status_code == 201
            missing = "00000000-0000-4000-8000-000000000000"
            assert (await c.post(f"/api/v1/incidents/{missing}/notes", json={"text": "x"}, headers=OPEN)).status_code == 404
            assert (await c.get(f"/api/v1/incidents/{missing}/notes", headers=OPEN)).status_code == 404

    asyncio.run(run())


def test_notes_belong_to_their_incident_and_persist_in_the_database(api):
    app, asset_id, engine = api

    async def run():
        async with _client(app) as c:
            a = await _incident(c, asset_id, "9001")
            b = await _incident(c, None, "9002")
            await c.post(f"/api/v1/incidents/{a}/notes", json={"text": "only on A"}, headers=OPEN)
            await c.post(f"/api/v1/incidents/{b}/notes", json={"text": "only on B"}, headers=OPEN)
            assert [n["text"] for n in (await c.get(f"/api/v1/incidents/{a}/notes", headers=OPEN)).json()] == ["only on A"]
            assert [n["text"] for n in (await c.get(f"/api/v1/incidents/{b}/notes", headers=OPEN)).json()] == ["only on B"]
        # a brand-new session (nothing cached) still reads them: the rows are durable
        async with session_factory(engine)() as db:
            rows = (await db.execute(select(IncidentNote).order_by(IncidentNote.created_at))).scalars().all()
        assert [(r.body, r.actor, r.actor_assurance) for r in rows] == [
            ("only on A", "demo", "unattributed"), ("only on B", "demo", "unattributed")]
        assert all(len(r.record_digest) == 64 for r in rows)

    asyncio.run(run())


def test_every_note_is_written_to_the_append_only_audit_timeline(api):
    app, asset_id, engine = api

    async def run():
        async with _client(app) as c:
            iid = await _incident(c, asset_id)
            created = (await c.post(f"/api/v1/incidents/{iid}/notes", json={"text": "DC02 remains responsive"},
                                    headers=jwt_header("engineer"))).json()
            events = (await c.get(f"/api/v1/incidents/{iid}/workflow-events", headers=OPEN)).json()
        noted = [e for e in events if e["record_type"] == "note"]
        assert len(noted) == 1
        assert (noted[0]["action"], noted[0]["actor"], noted[0]["actor_assurance"]) == ("noted", "engineer", "verified-identity")
        assert noted[0]["record_id"] == created["note_id"]
        assert "DC02" not in str(noted[0])  # the audit event records that a note exists, not a second copy of its text

    asyncio.run(run())


def test_notes_are_append_only_in_the_database(api):
    app, asset_id, engine = api
    migration = _migration()

    async def run():
        async with engine.begin() as conn:
            await conn.execute(text(migration.FUNCTION_DDL))
            await conn.execute(text("DROP TRIGGER IF EXISTS trg_incident_note_append_only ON incident_note"))
            await conn.execute(text("DROP TRIGGER IF EXISTS trg_incident_note_append_only_truncate ON incident_note"))
            await conn.execute(text(migration.ROW_TRIGGER_DDL))
            await conn.execute(text(migration.TRUNCATE_TRIGGER_DDL))
        async with _client(app) as c:
            iid = await _incident(c, asset_id)
            await c.post(f"/api/v1/incidents/{iid}/notes", json={"text": "immutable"}, headers=OPEN)
        for statement in ("UPDATE incident_note SET body='tampered'", "DELETE FROM incident_note",
                          "TRUNCATE incident_note"):
            with pytest.raises(DBAPIError):
                async with engine.begin() as conn:
                    await conn.execute(text(statement))
        async with session_factory(engine)() as db:
            assert (await db.execute(select(IncidentNote.body))).scalars().all() == ["immutable"]

    asyncio.run(run())


def test_migration_declares_the_same_constraints_as_the_model():
    migration = _migration()
    assert migration.down_revision == "d4f7b0a2c503"
    assert {c.name for c in IncidentNote.__table__.constraints if c.name} >= {
        "ck_incident_note_body_length", "ck_incident_note_assurance"}
