"""Event -> incident contract used by the Analyzer-embedded Incident Workspace (real PostgreSQL).

An analyzed event is bound to an incident through an evidence reference
(source_type='analysis', source_id=<analysis_history.id>). These tests pin what the UI relies on:
asking whether an event is already linked, creating without silent duplicates, linking more events
to one incident, and an explicit statement of what happened on create.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.incident.models import Incident, IncidentEvidence
from tests.incident_db_support import create_asset, session_factory
from tests.test_incident_workflow_records_pg import (  # noqa: F401  (fixture re-export)
    OPEN,
    TOKEN,
    _client,
    api,
    jwt_header,
)

NOW = datetime.now(UTC).isoformat()


async def _analysis(engine, event_id="1129", owner="demo") -> int:
    async with session_factory(engine)() as db:
        row = AnalysisHistory(event_id=event_id, provider="synthetic", username=owner, description="synthetic " + uuid.uuid4().hex,
                              solution_summary={}, event_metadata={"sourceFamily": "windows_event", "timestamp": NOW.replace("+00:00", "Z")},
                              search_results=[])
        db.add(row)
        await db.commit()
        return row.id


def _create_body(history_id, asset_id=None, key="1129", title="Incident from analysis"):
    body = {"title": title, "severity": "medium", "evidence": [
        {"source_type": "analysis", "source_id": str(history_id), "source_event_key": key, "observed_at": NOW}]}
    if asset_id:
        body["asset_id"] = str(asset_id)
    return body


def test_lookup_tells_whether_an_event_is_linked_and_is_not_shadowed_by_the_id_route(api):
    app, asset_id, engine = api

    async def scenario():
        hid = await _analysis(engine)
        async with _client(app) as client:
            url = "/api/v1/incidents/by-evidence"
            empty = await client.get(url, params={"source_type": "analysis", "source_id": str(hid)}, headers=OPEN)
            assert empty.status_code == 200 and empty.json() == []
            made = await client.post("/api/v1/incidents", json=_create_body(hid, asset_id), headers=OPEN)
            assert made.status_code == 201, made.text
            linked = (await client.get(url, params={"source_type": "analysis", "source_id": str(hid)}, headers=OPEN)).json()
            assert len(linked) == 1
            assert linked[0]["incident_id"] == made.json()["incident_id"]
            assert (linked[0]["status"], linked[0]["root_cause_state"]) == ("open", "unknown")
            assert (await client.get(url, params={"source_type": "bogus", "source_id": "1"}, headers=OPEN)).status_code == 422
            assert (await client.get(url, params={"source_type": "analysis"}, headers=OPEN)).status_code == 422

    asyncio.run(scenario())


def test_creating_twice_from_the_same_event_reuses_the_incident_and_says_so(api):
    app, asset_id, engine = api

    async def scenario():
        hid = await _analysis(engine)
        async with _client(app) as client:
            first = (await client.post("/api/v1/incidents", json=_create_body(hid, asset_id), headers=OPEN)).json()
            again = (await client.post("/api/v1/incidents", json=_create_body(hid, asset_id), headers=OPEN)).json()
            assert (first["created"], first["match"]) == (True, "created")
            assert (again["created"], again["match"]) == (False, "event_already_linked")
            assert again["incident_id"] == first["incident_id"]
            assert len(again["evidence"]) == 1
            # without the asset (as a UI that only knows the analysis id would send it) it is still idempotent
            nobody = (await client.post("/api/v1/incidents", json=_create_body(hid), headers=OPEN)).json()
            assert nobody["incident_id"] == first["incident_id"] and nobody["match"] == "event_already_linked"
        async with session_factory(engine)() as db:
            assert (await db.execute(select(func.count()).select_from(Incident))).scalar_one() == 1
            assert (await db.execute(select(func.count()).select_from(IncidentEvidence))).scalar_one() == 1

    asyncio.run(scenario())


def test_a_second_event_can_be_linked_to_the_same_incident_and_one_event_cannot_join_two(api):
    app, asset_id, engine = api

    async def scenario():
        h1, h2, h3 = await _analysis(engine), await _analysis(engine, "4625"), await _analysis(engine, "7036")
        other_asset = await create_asset(engine, "link-host-2")
        async with _client(app) as client:
            inc = (await client.post("/api/v1/incidents", json=_create_body(h1, asset_id), headers=OPEN)).json()
            iid = inc["incident_id"]
            attach = await client.post(f"/api/v1/incidents/{iid}/evidence", headers=OPEN, json={"evidence": [
                {"source_type": "analysis", "source_id": str(h2), "source_event_key": "4625", "observed_at": NOW}]})
            assert attach.status_code == 200, attach.text
            assert attach.json()["summary"]["evidence_added"] == 1
            assert sorted(e["source_id"] for e in attach.json()["evidence"]) == sorted([str(h1), str(h2)])
            # attaching the same event again adds nothing
            again = await client.post(f"/api/v1/incidents/{iid}/evidence", headers=OPEN, json={"evidence": [
                {"source_type": "analysis", "source_id": str(h2), "observed_at": NOW}]})
            assert again.status_code == 200 and again.json()["summary"]["evidence_added"] == 0
            # both events now resolve to the one incident
            for hid in (h1, h2):
                found = (await client.get("/api/v1/incidents/by-evidence", headers=OPEN,
                                          params={"source_type": "analysis", "source_id": str(hid)})).json()
                assert [f["incident_id"] for f in found] == [iid]
            # an event already bound to incident A cannot be attached to a different incident B
            other = (await client.post("/api/v1/incidents", json=_create_body(h3, other_asset, "7036"), headers=OPEN)).json()
            assert other["incident_id"] != iid and other["created"] is True
            clash = await client.post(f"/api/v1/incidents/{other['incident_id']}/evidence", headers=OPEN, json={"evidence": [
                {"source_type": "analysis", "source_id": str(h1), "observed_at": NOW}]})
            assert clash.status_code in (200, 409, 422), clash.text
            owner = (await client.get("/api/v1/incidents/by-evidence", headers=OPEN,
                                      params={"source_type": "analysis", "source_id": str(h1)})).json()
            assert [o["incident_id"] for o in owner] == [iid], "the event must remain bound to its original incident"

    asyncio.run(scenario())


def test_core_correlation_is_surfaced_and_events_without_asset_or_key_never_merge_silently(api):
    """Incident Core's existing rule (correlation.py), made visible to the caller.

    Same concrete asset AND same signature inside the window merges ('strong'); a different signature on the
    same asset is only a candidate ('ambiguous_not_merged', recorded for a human). Analysis events normally have no asset, and without a source_event_key each
    event is its own signature, so creating from such an event is always a new incident and linking
    is an explicit, separate action.
    """
    app, asset_id, engine = api

    async def scenario():
        h1, h2, h3 = await _analysis(engine), await _analysis(engine), await _analysis(engine, "9999")
        h4, h5 = await _analysis(engine, "2001"), await _analysis(engine, "2002")
        async with _client(app) as client:
            first = (await client.post("/api/v1/incidents", json=_create_body(h1, asset_id, "1129"), headers=OPEN)).json()
            second = (await client.post("/api/v1/incidents", json=_create_body(h2, asset_id, "1129"), headers=OPEN)).json()
            assert second["incident_id"] == first["incident_id"]
            assert (second["created"], second["match"]) == (False, "correlated_with_open_incident")
            assert len(second["evidence"]) == 2
            assert "same_asset_id" in second["summary"]["correlation"]["reasons"]
            third = (await client.post("/api/v1/incidents", json=_create_body(h3, asset_id, "9999"), headers=OPEN)).json()
            # Conservative policy: same asset + different signature is only a candidate, never an automatic merge.
            assert third["incident_id"] != first["incident_id"]
            assert (third["created"], third["match"]) == (True, "ambiguous_not_merged")
            candidates = third["summary"]["correlation"]["candidates"]
            assert [c["incident_id"] for c in candidates] == [first["incident_id"]]
            assert candidates[0]["confidence"] == "medium"

            def bare(hid):
                return {"title": "from event", "evidence": [
                    {"source_type": "analysis", "source_id": str(hid), "observed_at": NOW}]}

            a = (await client.post("/api/v1/incidents", json=bare(h4), headers=OPEN)).json()
            b = (await client.post("/api/v1/incidents", json=bare(h5), headers=OPEN)).json()
            assert (a["created"], b["created"]) == (True, True)
            assert a["incident_id"] != b["incident_id"], "no asset and no event key: nothing is merged implicitly"
            # linking them is then an explicit act
            link = await client.post(f"/api/v1/incidents/{a['incident_id']}/evidence", headers=OPEN, json={"evidence": [
                {"source_type": "analysis", "source_id": str(h5), "observed_at": NOW}]})
            assert link.status_code in (200, 409, 422)

    asyncio.run(scenario())


def test_creating_and_linking_do_not_widen_authority(api):
    """Open access may record the event link; it still cannot resolve or close (see workflow tests)."""
    app, asset_id, engine = api

    async def scenario():
        hid = await _analysis(engine)
        async with _client(app) as client:
            made = (await client.post("/api/v1/incidents", json=_create_body(hid, asset_id), headers=OPEN)).json()
            iid = made["incident_id"]
            row = made["evidence"][0]
            assert row["added_by"] == "demo"
            for target in ("resolved", "closed"):
                assert (await client.patch(f"/api/v1/incidents/{iid}/status", json={"status": target},
                                           headers=OPEN)).status_code == 403
            with_token = (await client.post("/api/v1/incidents", json=_create_body(await _analysis(engine, "5000"), None, "5000"),
                                            headers=TOKEN)).json()
            assert with_token["evidence"][0]["added_by"] == "admin"  # legacy attribution string, not an identity claim

    asyncio.run(scenario())
