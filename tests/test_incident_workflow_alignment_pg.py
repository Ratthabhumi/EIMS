"""Architecture alignment: hypothesis rejection/supersession, bounded pagination, service-level
authorisation, snapshot-vs-current knowledge, remediation catalog link and incident-originated
Knowledge proposals (real PostgreSQL, real routes).
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select, text

from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.models.knowledge import KnowledgeEntry
from backend.domain.incident.models import IncidentEvidence
from backend.domain.incident.service import IncidentPermissionError, IncidentService
from backend.domain.incident.workflow import Actor, IncidentWorkflow
from backend.domain.incident.workflow_models import IncidentKnowledgeProposal, IncidentWorkflowEvent
from tests.incident_db_support import attach_analysis_evidence, create_asset, session_factory
from tests.test_incident_workflow_records_pg import (  # noqa: F401  (fixture re-export)
    CAND,
    OPEN,
    TOKEN,
    _client,
    _diag,
    _incident,
    _remediation,
    api,
    jwt_header,
)


async def _open_incident(client, asset_id, source="win-al-1"):
    iid, ev = await _incident(client, asset_id, source)
    for target in ("triage", "investigating"):
        r = await client.patch(f"/api/v1/incidents/{iid}/status", json={"status": target},
                               headers=jwt_header("engineer"))
        assert r.status_code == 200, r.text
    return iid, ev


def test_reject_keeps_history_and_is_open_to_all_tiers_but_not_to_confirmed_rows(api):
    app, asset_id, engine = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            base = f"/api/v1/incidents/{iid}/diagnoses"
            first = (await client.post(base, json=_diag(ev), headers=OPEN)).json()
            assert (await client.get(f"/api/v1/incidents/{iid}", headers=OPEN)).json()["root_cause_state"] == "hypothesis"
            blank = await client.post(f"{base}/{first['diagnosis_id']}/reject", json={"reason": "  "}, headers=OPEN)
            assert blank.status_code == 422
            rej = await client.post(f"{base}/{first['diagnosis_id']}/reject",
                                    json={"reason": "DC reachable, ruled out"}, headers=TOKEN)
            assert rej.status_code == 200, rej.text
            body = rej.json()
            assert (body["status"], body["closed_by"], body["closed_assurance"]) == (
                "rejected", "shared-admin-token", "shared-token")
            assert body["closed_reason"] == "DC reachable, ruled out"
            # nothing deleted; no live hypothesis -> state returns to unknown
            listed = (await client.get(base, headers=OPEN)).json()
            assert [d["status"] for d in listed] == ["rejected"]
            assert (await client.get(f"/api/v1/incidents/{iid}", headers=OPEN)).json()["root_cause_state"] == "unknown"
            # a rejected hypothesis cannot be confirmed, rejected again, or superseded
            for path, payload in (("confirm", {"rationale": "x"}), ("reject", {"reason": "x"})):
                r = await client.post(f"{base}/{first['diagnosis_id']}/{path}", json=payload,
                                      headers=jwt_header("reviewer"))
                assert r.status_code == 409, (path, r.text)
            # a confirmed hypothesis cannot be rejected
            live = (await client.post(base, json=_diag(ev), headers=OPEN)).json()
            assert (await client.post(f"{base}/{live['diagnosis_id']}/confirm", json={"rationale": "lab"},
                                      headers=jwt_header("reviewer"))).status_code == 200
            r = await client.post(f"{base}/{live['diagnosis_id']}/reject", json={"reason": "no"}, headers=OPEN)
            assert r.status_code == 409
            events = (await client.get(f"/api/v1/incidents/{iid}/workflow-events", headers=OPEN)).json()
            assert [(e["action"], e["actor_assurance"]) for e in events if e["action"] == "rejected"] == [
                ("rejected", "shared-token")]

    asyncio.run(scenario())


def test_supersede_requires_a_different_live_diagnosis_and_keeps_both_rows(api):
    app, asset_id, _ = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            base = f"/api/v1/incidents/{iid}/diagnoses"
            old = (await client.post(base, json=_diag(ev), headers=OPEN)).json()["diagnosis_id"]
            new = (await client.post(base, json=_diag(ev, hypothesis="Different cause"), headers=OPEN)).json()["diagnosis_id"]
            url = f"{base}/{old}/supersede"
            assert (await client.post(url, json={"reason": "r", "superseded_by_id": old}, headers=OPEN)).status_code == 422
            assert (await client.post(url, json={"reason": "r", "superseded_by_id": str(uuid.uuid4())},
                                      headers=OPEN)).status_code == 404
            ok = await client.post(url, json={"reason": "better explained by new", "superseded_by_id": new}, headers=OPEN)
            assert ok.status_code == 200, ok.text
            assert (ok.json()["status"], ok.json()["superseded_by_id"]) == ("superseded", new)
            statuses = {d["diagnosis_id"]: d["status"] for d in (await client.get(base, headers=OPEN)).json()}
            assert statuses == {old: "superseded", new: "hypothesis"}
            assert (await client.get(f"/api/v1/incidents/{iid}", headers=OPEN)).json()["root_cause_state"] == "hypothesis"
            # a replacement that is itself closed is refused
            third = (await client.post(base, json=_diag(ev, hypothesis="Third"), headers=OPEN)).json()["diagnosis_id"]
            await client.post(f"{base}/{third}/reject", json={"reason": "x"}, headers=OPEN)
            fourth = (await client.post(base, json=_diag(ev, hypothesis="Fourth"), headers=OPEN)).json()["diagnosis_id"]
            r = await client.post(f"{base}/{fourth}/supersede", json={"reason": "r", "superseded_by_id": third}, headers=OPEN)
            assert r.status_code == 422

    asyncio.run(scenario())


def test_database_rejects_inconsistent_closure_rows(api):
    app, asset_id, engine = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            first = (await client.post(f"/api/v1/incidents/{iid}/diagnoses", json=_diag(ev), headers=OPEN)).json()["diagnosis_id"]
            second = (await client.post(f"/api/v1/incidents/{iid}/diagnoses", json=_diag(ev), headers=OPEN)).json()["diagnosis_id"]

        async def attempt(sql, **params):
            async with engine.begin() as conn:
                with pytest.raises(Exception, match="violates|constraint"):
                    await conn.execute(text(sql), params)

        await attempt("UPDATE incident_diagnosis SET status='rejected' WHERE diagnosis_id=:i", i=first)  # no who/why
        await attempt("UPDATE incident_diagnosis SET status='superseded', closed_by='x', closed_at=now(), "
                      "closed_reason='r', closed_assurance='unattributed' WHERE diagnosis_id=:i", i=first)  # no link
        await attempt("UPDATE incident_diagnosis SET status='superseded', closed_by='x', closed_at=now(), "
                      "closed_reason='r', closed_assurance='unattributed', superseded_by_id=diagnosis_id "
                      "WHERE diagnosis_id=:i", i=first)  # self
        await attempt("UPDATE incident_diagnosis SET status='hypothesis', closed_by='x' WHERE diagnosis_id=:i", i=second)
        await attempt("UPDATE incident_diagnosis SET status='rejected', closed_by='x', closed_at=now(), "
                      "closed_reason='r', closed_assurance='root' WHERE diagnosis_id=:i", i=second)

    asyncio.run(scenario())


def test_lists_are_bounded_ordered_and_report_totals(api):
    app, asset_id, _ = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            base = f"/api/v1/incidents/{iid}/diagnoses"
            ids = []
            for n in range(5):
                ids.append((await client.post(base, json=_diag(ev, hypothesis=f"H{n}"), headers=OPEN)).json()["diagnosis_id"])
            page = await client.get(base, params={"limit": 2, "offset": 2}, headers=OPEN)
            assert page.status_code == 200
            assert page.headers["x-total-count"] == "5"
            assert [d["diagnosis_id"] for d in page.json()] == ids[2:4]
            assert (await client.get(base, params={"limit": 201}, headers=OPEN)).status_code == 422
            assert (await client.get(base, params={"limit": 0}, headers=OPEN)).status_code == 422
            assert (await client.get(base, params={"offset": -1}, headers=OPEN)).status_code == 422
            events = await client.get(f"/api/v1/incidents/{iid}/workflow-events", params={"limit": 3}, headers=OPEN)
            assert events.headers["x-total-count"] == "5" and len(events.json()) == 3
            rems = await client.get(f"/api/v1/incidents/{iid}/remediations", params={"limit": 1}, headers=OPEN)
            assert rems.headers["x-total-count"] == "0" and rems.json() == []

    asyncio.run(scenario())


def test_confirmation_is_authorised_in_the_domain_service_not_only_the_controller(api):
    app, asset_id, engine = api

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            diag = (await client.post(f"/api/v1/incidents/{iid}/diagnoses", json=_diag(ev), headers=OPEN)).json()
        for actor in (Actor("demo", "unattributed"), Actor("shared-admin-token", "shared-token"),
                      Actor("engineer", "verified-identity"),   # real user, no reviewer capability
                      Actor("ghost", "verified-identity")):      # no such account
            async with session_factory(engine)() as db:
                with pytest.raises(IncidentPermissionError):
                    await IncidentWorkflow(db).confirm_diagnosis(
                        uuid.UUID(iid), uuid.UUID(diag["diagnosis_id"]), actor=actor, rationale="x")
                await db.rollback()
        async with session_factory(engine)() as db:
            done = await IncidentWorkflow(db).confirm_diagnosis(
                uuid.UUID(iid), uuid.UUID(diag["diagnosis_id"]), actor=Actor("reviewer", "verified-identity"),
                rationale="lab")
            await db.commit()
            assert done.status == "confirmed"

    asyncio.run(scenario())


def test_remediation_keeps_a_catalog_snapshot_and_never_claims_canonical_guidance(api):
    app, asset_id, _ = api

    async def scenario():
        async with _client(app) as client:
            iid, _ev = await _incident(client, asset_id)
            url = f"/api/v1/incidents/{iid}/remediations"
            bad = await client.post(url, json=_remediation(catalog_id="nope:nope:nope"), headers=OPEN)
            assert bad.status_code == 422
            ok = await client.post(url, json=_remediation(catalog_id=CAND), headers=OPEN)
            assert ok.status_code == 201, ok.text
            row = ok.json()
            assert row["catalog_id"] == CAND
            assert row["knowledge"]["classification"] == "diagnostic_candidate_match"
            # the catalog schema has no remediation guidance, so the action is incident-specific
            assert row["knowledge"]["canonical_remediation_available"] is False
            plain = (await client.post(url, json=_remediation(), headers=OPEN)).json()
            assert plain["catalog_id"] is None and plain["knowledge"] is None

    asyncio.run(scenario())


def test_incident_snapshot_is_historical_and_current_record_is_inspectable_separately(api, monkeypatch):
    from backend.api.routers.analyzer.catalog import catalog_router
    from backend.domain.knowledge import service as ks
    from backend.infrastructure.database import get_db_session

    app, asset_id, engine = api
    app.include_router(catalog_router)

    async def scenario():
        async with _client(app) as client:
            iid, ev = await _incident(client, asset_id)
            diag = (await client.post(f"/api/v1/incidents/{iid}/diagnoses",
                                      json=_diag(ev, catalog_id=CAND), headers=OPEN)).json()
            snap_hash = diag["knowledge"]["content_hash"]
            current = await client.get("/api/v1/analyzer/catalog/record", params={"catalog_id": CAND}, headers=OPEN)
            assert current.status_code == 200, current.text
            record = current.json()
            assert record["content_hash"] == snap_hash
            assert record["classification"]["classification"] in ("diagnostic_candidate_match", "no_verified_match")
            assert record["remediation_guidance"] == [] and record["verification_criteria"] == []
            assert (await client.get("/api/v1/analyzer/catalog/record", params={"catalog_id": "nope:nope:nope"},
                                     headers=OPEN)).status_code == 404

            # the canonical record changes later: the incident keeps its original snapshot
            original = ks._catalog

            def changed():
                data = dict(original())
                data[CAND] = {**data[CAND], "description": "REVISED canonical wording"}
                return data

            monkeypatch.setattr(ks, "_catalog", changed)
            again = (await client.get("/api/v1/analyzer/catalog/record", params={"catalog_id": CAND},
                                      headers=OPEN)).json()
            assert again["content_hash"] != snap_hash
            stored = (await client.get(f"/api/v1/incidents/{iid}/diagnoses", headers=OPEN)).json()[0]
            assert stored["knowledge"]["content_hash"] == snap_hash, "historical snapshot must not be rewritten"

    asyncio.run(scenario())


async def _completed_incident(client, engine, asset_id, *, with_analysis=True, source="win-kp-1", history_owner="demo"):
    """investigating -> confirmed diagnosis -> verified resolution. Returns ids."""
    iid, ev = await _open_incident(client, asset_id, source)
    hid = None
    if with_analysis:
        async with session_factory(engine)() as db:
            row = AnalysisHistory(event_id="1129", provider="synthetic", username=history_owner,
                                  description="synthetic", solution_summary={}, event_metadata={
                                      "sourceFamily": "windows_event", "diagnosticCode": "1129"},
                                  search_results=[])
            db.add(row)
            await db.commit()
            hid = row.id
    diag = (await client.post(f"/api/v1/incidents/{iid}/diagnoses",
                              json=_diag(ev, **({"analysis_history_id": hid} if hid else {})), headers=OPEN)).json()
    assert (await client.post(f"/api/v1/incidents/{iid}/diagnoses/{diag['diagnosis_id']}/confirm",
                              json={"rationale": "lab"}, headers=jwt_header("reviewer"))).status_code == 200
    rem = (await client.post(f"/api/v1/incidents/{iid}/remediations", json=_remediation(), headers=OPEN)).json()
    assert (await client.post(f"/api/v1/incidents/{iid}/remediations/{rem['remediation_id']}/execution",
                              json={"actual_action": "done", "outcome": "succeeded", "evidence_ids": ev[:1]},
                              headers=OPEN)).status_code == 200
    proof = await attach_analysis_evidence(engine, uuid.UUID(iid), asset_id=asset_id)
    resolved = await client.patch(f"/api/v1/incidents/{iid}/status",
                                  json={"status": "resolved", "verification": {"evidence_id": str(proof)}},
                                  headers=jwt_header("reviewer"))
    assert resolved.status_code == 200, resolved.text
    return iid, ev, diag["diagnosis_id"], rem["remediation_id"], hid


PROPOSAL = {
    "title": "Group Policy fails without DC connectivity", "resolution_status": "resolved",
    "root_cause": "Domain controller unreachable from the client network segment",
    "solution_steps": ["Restore routing to the domain controller subnet"],
    "evidence_notes": ["Event 1129 repeated until routing was restored"],
    "validation_steps": ["gpupdate /force completes without event 1129"],
    "rollback_steps": ["Revert the routing change"], "risk_level": "medium",
}


def test_completed_incident_proposes_knowledge_into_the_existing_review_lifecycle(api):
    app, asset_id, engine = api

    async def scenario():
        async with _client(app) as client:
            iid, ev, did, rid, hid = await _completed_incident(client, engine, asset_id)
            url = f"/api/v1/incidents/{iid}/knowledge-proposals"
            body = {"diagnosis_id": did, "remediation_id": rid, "evidence_ids": ev[:1], "proposal": PROPOSAL}
            # a forged approval / status at the top level is rejected outright
            assert (await client.post(url, json={**body, "status": "approved"}, headers=OPEN)).status_code == 422
            made = await client.post(url, json=body, headers=OPEN)
            assert made.status_code == 201, made.text
            link = made.json()
            assert link["proposed_assurance"] == "unattributed" and link["knowledge_status"] == "pending"
            assert link["evidence_ids"] == ev[:1] and link["diagnosis_id"] == did
            async with session_factory(engine)() as db:
                entry = (await db.execute(select(KnowledgeEntry).where(
                    KnowledgeEntry.id == link["knowledge_entry_id"]))).scalars().one()
                # in the existing lifecycle: pending, not approved, not published
                assert entry.status == "pending" and entry.reviewed_by is None
                assert entry.source_history_id == hid
                links = (await db.execute(select(IncidentKnowledgeProposal))).scalars().all()
                assert len(links) == 1 and str(links[0].incident_id) == iid
            listed = (await client.get(url, headers=OPEN)).json()
            assert [x["knowledge_entry_id"] for x in listed] == [link["knowledge_entry_id"]]
            # duplicate proposal for the same analysis is refused by the existing rule
            assert (await client.post(url, json=body, headers=OPEN)).status_code == 409

    asyncio.run(scenario())


def test_knowledge_proposal_preconditions_are_enforced(api):
    app, asset_id, engine = api

    async def scenario():
        async with _client(app) as client:
            # open (not completed) incident
            iid, ev = await _open_incident(client, asset_id, "win-kp-open")
            diag = (await client.post(f"/api/v1/incidents/{iid}/diagnoses", json=_diag(ev), headers=OPEN)).json()
            url = f"/api/v1/incidents/{iid}/knowledge-proposals"
            body = {"diagnosis_id": diag["diagnosis_id"], "evidence_ids": [], "proposal": PROPOSAL}
            assert (await client.post(url, json=body, headers=OPEN)).status_code == 409

        other_asset = await create_asset(engine, "kp-host-2")
        async with _client(app) as client:
            # completed, but the diagnosis has no analysis reference
            iid2, ev2, did2, rid2, _ = await _completed_incident(client, engine, other_asset, with_analysis=False,
                                                                 source="win-kp-noanalysis")
            url2 = f"/api/v1/incidents/{iid2}/knowledge-proposals"
            assert (await client.post(url2, json={"diagnosis_id": did2, "proposal": PROPOSAL},
                                      headers=OPEN)).status_code == 422
        third = await create_asset(engine, "kp-host-3")
        async with _client(app) as client:
            iid3, ev3, did3, rid3, _ = await _completed_incident(client, engine, third, source="win-kp-pre")
            url3 = f"/api/v1/incidents/{iid3}/knowledge-proposals"
            other_ev = (await _incident(client, await create_asset(engine, "kp-host-4"), "win-kp-x"))[1]
            assert (await client.post(url3, json={"diagnosis_id": did3, "evidence_ids": other_ev,
                                                  "proposal": PROPOSAL}, headers=OPEN)).status_code == 422
            weak = {k: v for k, v in PROPOSAL.items() if k != "root_cause"}
            assert (await client.post(url3, json={"diagnosis_id": did3, "proposal": weak},
                                      headers=OPEN)).status_code == 422
            unknown = await client.post(url3, json={"diagnosis_id": str(uuid.uuid4()), "proposal": PROPOSAL}, headers=OPEN)
            assert unknown.status_code == 404

    asyncio.run(scenario())


def test_latest_migration_is_reversible_and_additive():
    """the head (c9f4a7b0d826, notes) and d4f7b0a2c503 downgrade cleanly to c3e6a9d1f402 and upgrades again."""
    from alembic import command
    from alembic.config import Config

    from tests.incident_db_support import require_database_url
    from tests.test_knowledge_overlay_pg import _create_schema, _migrate

    url = require_database_url()

    async def scenario():
        schema, engine = _create_schema(url)
        try:
            await _migrate(engine, schema)

            def run(direction: str, target: str):
                def go(connection):
                    cfg = Config()
                    cfg.set_main_option("script_location", "migrations")
                    cfg.attributes.update(connection=connection, version_table_schema=schema)
                    (command.downgrade if direction == "down" else command.upgrade)(cfg, target)
                return go

            async def state(conn):
                await conn.execute(text(f'SET search_path TO "{schema}", public'))
                tables = set((await conn.execute(text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = :s"), {"s": schema})).scalars())
                cols = set((await conn.execute(text(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema = :s "
                    "AND table_name = 'incident_diagnosis'"), {"s": schema})).scalars())
                version = await conn.scalar(text(f'SELECT version_num FROM "{schema}".alembic_version'))
                return tables, cols, version

            async with engine.connect() as conn:
                await conn.execute(text(f'SET search_path TO "{schema}", public'))
                tables, cols, version = await state(conn)
                assert version == "c9f4a7b0d826" and "incident_knowledge_proposal" in tables and "incident_note" in tables
                assert {"closed_by", "superseded_by_id"} <= cols
                await conn.rollback()
            async with engine.connect() as conn:
                await conn.execute(text(f'SET search_path TO "{schema}", public'))
                await conn.commit()
                await conn.run_sync(run("down", "c3e6a9d1f402"))
                await conn.commit()
                tables, cols, version = await state(conn)
                assert version == "c3e6a9d1f402"
                assert "incident_knowledge_proposal" not in tables and "incident_note" not in tables
                assert "incident_diagnosis" in tables and "closed_by" not in cols
                await conn.rollback()
            async with engine.connect() as conn:
                await conn.execute(text(f'SET search_path TO "{schema}", public'))
                await conn.commit()
                await conn.run_sync(run("up", "head"))
                await conn.commit()
                tables, cols, version = await state(conn)
                assert version == "c9f4a7b0d826" and "incident_note" in tables and "incident_knowledge_proposal" in tables
                await conn.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def _with_knowledge_router(app):
    from backend.api.routers.analyzer import knowledge as knowledge_api

    if not any(getattr(r, "path", "").startswith("/knowledge") for r in app.router.routes):
        app.include_router(knowledge_api.router, prefix="/knowledge")


def test_shared_token_cannot_approve_knowledge_it_caused_to_be_proposed(api):
    """A shared-token caller may propose, but must not be able to approve (even as the literal 'admin')."""
    app, asset_id, engine = api
    _with_knowledge_router(app)

    async def scenario():
        async with _client(app) as client:
            iid, ev, did, rid, hid = await _completed_incident(client, engine, asset_id)
            made = await client.post(
                f"/api/v1/incidents/{iid}/knowledge-proposals",
                json={"diagnosis_id": did, "proposal": PROPOSAL}, headers=TOKEN)
            assert made.status_code == 201, made.text
            link = made.json()
            assert (link["proposed_by"], link["proposed_assurance"]) == ("shared-admin-token", "shared-token")
            entry_id = link["knowledge_entry_id"]
            review = {"decision": "approve", "note": "looks right to me"}
            # the shared token (which resolves to the seeded 'admin' user) cannot review
            denied = await client.post(f"/knowledge/{entry_id}/review", json=review, headers=TOKEN)
            assert denied.status_code == 403, denied.text
            assert "shared admin token" in denied.text
            # a verified user without the reviewer capability cannot either; open access is rejected
            assert (await client.post(f"/knowledge/{entry_id}/review", json=review,
                                      headers=jwt_header("engineer"))).status_code == 403
            assert (await client.post(f"/knowledge/{entry_id}/review", json=review, headers=OPEN)).status_code == 401
            async with session_factory(engine)() as db:
                entry = (await db.execute(select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id))).scalars().one()
                assert entry.status == "pending" and entry.reviewed_by is None
            # an independent verified reviewer still can (the existing lifecycle is intact)
            ok = await client.post(f"/knowledge/{entry_id}/review", json=review, headers=jwt_header("reviewer"))
            assert ok.status_code == 200, ok.text

    asyncio.run(scenario())


def test_proposers_of_every_tier_work_but_only_for_analyses_they_may_use(api):
    app, asset_id, engine = api

    async def scenario():
        async with _client(app) as client:
            for index, (headers, who, assurance) in enumerate((
                    (TOKEN, "shared-admin-token", "shared-token"),
                    (jwt_header("engineer"), "engineer", "verified-identity"))):
                host = await create_asset(engine, f"tier-host-{index}")
                iid, ev, did, rid, hid = await _completed_incident(client, engine, host, source=f"win-tier-{index}")
                made = await client.post(f"/api/v1/incidents/{iid}/knowledge-proposals",
                                         json={"diagnosis_id": did, "proposal": PROPOSAL}, headers=headers)
                assert made.status_code == 201, (who, made.text)
                assert (made.json()["proposed_by"], made.json()["proposed_assurance"]) == (who, assurance)

            # analysis owned by a different account is not usable
            foreign_host = await create_asset(engine, "tier-host-foreign")
            iid, ev, did, rid, hid = await _completed_incident(client, engine, foreign_host,
                                                               source="win-tier-foreign", history_owner="bob")
            denied = await client.post(f"/api/v1/incidents/{iid}/knowledge-proposals",
                                       json={"diagnosis_id": did, "proposal": PROPOSAL}, headers=jwt_header("engineer"))
            assert denied.status_code == 404, denied.text
            async with session_factory(engine)() as db:
                links = (await db.execute(select(IncidentKnowledgeProposal).where(
                    IncidentKnowledgeProposal.incident_id == uuid.UUID(iid)))).scalars().all()
                events = (await db.execute(select(IncidentWorkflowEvent).where(
                    IncidentWorkflowEvent.incident_id == uuid.UUID(iid),
                    IncidentWorkflowEvent.action == "knowledge_proposed"))).scalars().all()
                entries = (await db.execute(select(KnowledgeEntry).where(KnowledgeEntry.source_history_id == hid))).scalars().all()
                assert links == [] and events == [] and entries == [], "a refused proposal must leave nothing behind"

    asyncio.run(scenario())


def test_duplicate_proposal_is_refused_without_extra_rows(api):
    app, asset_id, engine = api

    async def scenario():
        async with _client(app) as client:
            iid, ev, did, rid, hid = await _completed_incident(client, engine, asset_id)
            url = f"/api/v1/incidents/{iid}/knowledge-proposals"
            body = {"diagnosis_id": did, "proposal": PROPOSAL}
            assert (await client.post(url, json=body, headers=OPEN)).status_code == 201
            assert (await client.post(url, json=body, headers=OPEN)).status_code == 409
            async with session_factory(engine)() as db:
                assert len((await db.execute(select(IncidentKnowledgeProposal))).scalars().all()) == 1
                assert len((await db.execute(select(KnowledgeEntry))).scalars().all()) == 1
                proposed = (await db.execute(select(IncidentWorkflowEvent).where(
                    IncidentWorkflowEvent.action == "knowledge_proposed"))).scalars().all()
                assert len(proposed) == 1

    asyncio.run(scenario())


def test_status_service_rejects_non_verified_assurance_for_resolve_and_close(api):
    app, asset_id, engine = api

    async def scenario():
        for target in ("resolved", "closed"):
            for assurance in ("unattributed", "shared-token"):
                async with session_factory(engine)() as db:
                    with pytest.raises(IncidentPermissionError):
                        await IncidentService(db).change_status(
                            uuid.uuid4(), target, actor="reviewer", reviewer_identity="reviewer",
                            verifier="reviewer", assurance=assurance)

    asyncio.run(scenario())


def test_migrated_schema_has_the_named_unique_and_foreign_key_for_proposals():
    from tests.incident_db_support import require_database_url
    from tests.test_knowledge_overlay_pg import _create_schema, _migrate

    url = require_database_url()

    async def scenario():
        schema, engine = _create_schema(url)
        try:
            await _migrate(engine, schema)
            async with engine.connect() as conn:
                names = set((await conn.execute(text(
                    "SELECT c.conname FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
                    "JOIN pg_namespace n ON n.oid = t.relnamespace "
                    "WHERE n.nspname = :s AND t.relname = 'incident_knowledge_proposal'"), {"s": schema})).scalars())
                assert {"uq_incident_knowledge_proposal_entry", "fk_incident_knowledge_proposal_entry",
                        "pk_incident_knowledge_proposal"} <= names
                await conn.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())
