"""Human decision API and catalog registration against a disposable PostgreSQL (real authentication dependencies, no overrides).

Every scenario runs in its own unique schema. Users are synthetic. The shared admin token, anonymous callers and non-reviewer accounts
must be refused; the decider's identity and kind come from the server only.
"""
import asyncio
import copy
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from fastapi import FastAPI
from sqlalchemy import select, text

from backend.api.routers.analyzer import knowledge
from backend.domain.analyzer import auth
from backend.domain.analyzer.models.session import AnalyzerSession
from backend.domain.analyzer.models.user import User
from backend.domain.analyzer.services import session_security
from backend.domain.knowledge import service
from backend.domain.knowledge.models import KnowledgeReview, KnowledgeReviewEvent
from tests.incident_db_support import create_schema, require_database_url, session_factory
from tests.test_knowledge_service import SOURCE, VALID, _trigger_ddl
from tools import catalog_import

TEST_KEY = "synthetic-governance-signing-key-only-20261122"
ADMIN_TOKEN = "synthetic-governance-admin-token-only"
PASSWORD = "synthetic-test-password-only"
USERS = [("rev-one", "user", True), ("rev-two", "user", True), ("rev-three", "user", True), ("plain-user", "user", False), ("admin-user", "admin", False)]
ELIGIBLE_ID = "cisco_asa:official_message_id:113005"
INCOMPLETE_CANDIDATE = "candidate:postgresql:locks:deadlock-detected"
REFERENCE = "reference:postgresql:sqlstate:40P01"
WINDOWS = "windows_event:official_event_id:4624"
TABLES = [User.__table__, AnalyzerSession.__table__, KnowledgeReview.__table__, KnowledgeReviewEvent.__table__]


def bearer(name, **claims):
    payload = {"sub": name, "sid": "synthetic-session-" + name, "exp": datetime.now(UTC) + timedelta(minutes=5), **claims}
    return {"Authorization": "Bearer " + jwt.encode(payload, TEST_KEY, algorithm="HS256")}


def _source():
    return {k: v for k, v in SOURCE.items() if k != "verifier"}  # the decider is never client-supplied


@pytest.fixture()
def api(monkeypatch):
    url = require_database_url()
    monkeypatch.setattr(auth.settings, "AUTH_MODE", "secure")
    monkeypatch.setattr(auth.settings, "ADMIN_TOKEN", ADMIN_TOKEN)
    monkeypatch.setattr(auth, "SECRET_KEY", TEST_KEY)
    monkeypatch.setattr(auth, "ALGORITHM", "HS256")
    monkeypatch.setattr(session_security, "THROTTLE_NAMESPACE", "pytest-governance")

    async def run(check):
        _schema, engine = await create_schema(url, tables=TABLES)
        mod = _trigger_ddl()
        async with engine.begin() as conn:
            for ddl in (mod.APPEND_ONLY_FUNCTION_DDL, mod.APPEND_ONLY_TRIGGER_DDL, mod.APPEND_ONLY_TRUNCATE_DDL):
                await conn.execute(text(ddl))
        try:
            async with session_factory(engine)() as session:
                for name, role, reviewer in USERS:
                    account = User(username=name, role=role, knowledge_reviewer=reviewer, password=auth.hash_password(PASSWORD))
                    session.add(account)
                    await session.flush()
                    now = datetime.now(UTC)
                    session.add(AnalyzerSession(id=session_security.digest("synthetic-session-" + name), user_id=account.id, username=name,
                                                credential_version=session_security.digest(account.password), created_at=now, last_seen=now,
                                                expires_at=now + timedelta(minutes=10)))
                await session.commit()
                app = FastAPI()
                app.include_router(knowledge.router, prefix="/knowledge")

                async def db():
                    yield session
                app.dependency_overrides[knowledge.get_db] = db  # same function the auth dependencies use; authentication itself is NOT overridden
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://synthetic-test") as client:
                    await check(client, session)
        finally:
            await engine.dispose()
    return lambda check: asyncio.run(run(check))


def body(catalog_id, target, **kw):
    entry = service._catalog()[catalog_id]
    data = {"catalog_id": catalog_id, "target": target, "content_hash": service.canonical_hash(entry), "rationale": "synthetic decision for the test"}
    data.update(kw)
    return data


async def post(client, payload, who=None, headers=None):
    return await client.post("/knowledge/governance/decisions", json=payload, headers=headers if headers is not None else (bearer(who) if who else {}))


# --- who may decide -------------------------------------------------------------------------------------------------------------
def test_unauthenticated_and_shared_secret_callers_cannot_record_decisions(api):
    async def check(client, session):
        payload = body(ELIGIBLE_ID, "source_verified", review=_source())
        assert (await post(client, payload)).status_code == 401                                              # anonymous -> open-access identity
        assert (await post(client, payload, headers={"Authorization": "Bearer " + ADMIN_TOKEN})).status_code == 403   # shared admin token is a shared secret
        forged = jwt.encode({"sub": "rev-one", "sid": "synthetic-session-rev-one", "exp": datetime.now(UTC) + timedelta(minutes=5)}, "wrong-key", algorithm="HS256")
        assert (await post(client, payload, headers={"Authorization": "Bearer " + forged})).status_code == 401      # bad signature
        assert (await post(client, payload, headers=bearer("no-such-user"))).status_code == 401
        assert (await post(client, payload, "plain-user")).status_code == 403                                  # human without reviewer authority
        assert (await session.execute(select(KnowledgeReviewEvent))).scalars().first() is None                  # nothing was written
    api(check)


def test_reviewer_decision_takes_actor_from_authentication_and_records_kind_hash_and_evidence(api):
    async def check(client, session):
        r = await post(client, body(ELIGIBLE_ID, "source_verified", review=_source(), evidence_refs=["https://vendor.example/evidence/1"]), "rev-one")
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["actor"] == "rev-one" and data["actorKind"] == "human" and data["status"] == "source_verified"
        event = (await session.execute(select(KnowledgeReviewEvent))).scalars().all()[-1]
        assert event.actor == "rev-one" and event.evidence["actor_kind"] == "human" and event.evidence["verifier"] == "rev-one"
        assert event.source_hash == service.canonical_hash(service._catalog()[ELIGIBLE_ID])
        assert event.evidence["evidence_refs"] == ["https://vendor.example/evidence/1"]
        admin = await post(client, body(ELIGIBLE_ID, "rejected", review={}), "admin-user")  # a real admin account may also decide
        assert admin.status_code == 201 and admin.json()["actor"] == "admin-user"
    api(check)


@pytest.mark.parametrize("extra", [{"actor": "someone-else"}, {"actor_kind": "human"}, {"reviewer": "x"}, {"actorKind": "human"}])
def test_clients_cannot_name_the_decider_or_its_kind(api, extra):
    async def check(client, session):
        payload = {**body(ELIGIBLE_ID, "source_verified", review=_source()), **extra}
        assert (await post(client, payload, "rev-one")).status_code == 422
        nested = body(ELIGIBLE_ID, "source_verified", review={**_source(), "verifier": "rev-two"})
        assert (await post(client, nested, "rev-one")).status_code == 422
        assert (await session.execute(select(KnowledgeReviewEvent))).scalars().first() is None
    api(check)


# --- what a decision is bound to --------------------------------------------------------------------------------------------------
def test_stale_content_hash_is_refused_with_the_current_hash(api):
    async def check(client, session):
        payload = body(ELIGIBLE_ID, "source_verified", review=_source())
        payload["content_hash"] = "0" * 64
        r = await post(client, payload, "rev-one")
        assert r.status_code == 409 and r.json()["detail"]["code"] == "stale_content_hash"
        assert r.json()["detail"]["currentContentHash"] == service.canonical_hash(service._catalog()[ELIGIBLE_ID])
    api(check)


def test_a_decision_made_before_a_content_change_cannot_carry_forward(api, monkeypatch):
    async def check(client, session):
        assert (await post(client, body(ELIGIBLE_ID, "source_verified", review=_source()), "rev-one")).status_code == 201
        original = service._catalog

        def changed():
            catalog = original()
            catalog[ELIGIBLE_ID] = dict(catalog[ELIGIBLE_ID], limitations=catalog[ELIGIBLE_ID]["limitations"] + " (edited after review)")
            return catalog
        monkeypatch.setattr(service, "_catalog", changed)
        r = await post(client, body(ELIGIBLE_ID, "validated", review=VALID), "rev-two")
        assert r.status_code == 422 and "revision" in r.text   # the earlier source_verified belongs to the previous content
    api(check)


def test_approval_scope_follows_the_record_class_and_windows_context_has_no_approval(api):
    async def check(client, session):
        wrong = await post(client, body(ELIGIBLE_ID, "approved", approval_scope="approved_as_reference"), "rev-one")
        assert wrong.status_code == 422 and wrong.json()["detail"]["code"] == "wrong_approval_scope"
        assert (await post(client, body(WINDOWS, "approved", approval_scope="approved_as_context"), "rev-one")).status_code == 422  # not a valid scope value at all
        win = await post(client, body(WINDOWS, "approved", approval_scope="approved_as_reference"), "rev-one")
        assert win.status_code == 422 and win.json()["detail"]["code"] == "class_not_approvable"
        incomplete = await post(client, body(INCOMPLETE_CANDIDATE, "approved", approval_scope="approved_as_diagnostic"), "rev-one")
        assert incomplete.status_code == 422 and "recovery_verification" in incomplete.json()["detail"]["missing"]
        assert (await post(client, body(ELIGIBLE_ID, "source_verified", approval_scope="approved_as_diagnostic", review=_source()), "rev-one")).status_code == 422
        assert (await session.execute(select(KnowledgeReviewEvent))).scalars().first() is None
    api(check)


# --- full human path, independence, history, supersession ----------------------------------------------------------------------------
def test_full_human_path_requires_three_independent_humans_and_is_auditable(api):
    async def check(client, session):
        assert (await post(client, body(ELIGIBLE_ID, "source_verified", review=_source()), "rev-one")).status_code == 201
        assert (await post(client, body(ELIGIBLE_ID, "validated", review=VALID), "rev-two")).status_code == 201
        for who in ("rev-one", "rev-two"):   # verifier and validator cannot approve
            denied = await post(client, body(ELIGIBLE_ID, "approved", approval_scope="approved_as_diagnostic"), who)
            assert denied.status_code == 403, who
        ok = await post(client, body(ELIGIBLE_ID, "approved", approval_scope="approved_as_diagnostic", evidence_refs=["https://vendor.example/approval"]), "rev-three")
        assert ok.status_code == 201 and ok.json()["approvalScope"] == "approved_as_diagnostic"
        history = (await client.get("/knowledge/governance/history", params={"catalog_id": ELIGIBLE_ID}, headers=bearer("rev-one"))).json()
        assert [e["to_status"] for e in history["events"]] == ["source_verified", "validated", "approved"]
        assert [e["actor"] for e in history["events"]] == ["rev-one", "rev-two", "rev-three"]
        assert all(e["evidence"]["actor_kind"] == "human" for e in history["events"]) and history["events"][-1]["evidence"]["approval_scope"] == "approved_as_diagnostic"
        assert history["status"] == "approved" and history["stale"] is False and history["currentContentHash"] == ok.json()["contentHash"]
        assert (await client.get("/knowledge/governance/history", params={"catalog_id": "nope:nope:nope"}, headers=bearer("rev-one"))).status_code == 404
    api(check)


def test_supersession_records_the_replacement_and_keeps_the_history(api):
    async def check(client, session):
        assert (await post(client, body(ELIGIBLE_ID, "source_verified", review=_source()), "rev-one")).status_code == 201
        assert (await post(client, body(ELIGIBLE_ID, "validated", review=VALID), "rev-two")).status_code == 201
        assert (await post(client, body(ELIGIBLE_ID, "approved", approval_scope="approved_as_diagnostic"), "rev-three")).status_code == 201
        self_ref = await post(client, body(ELIGIBLE_ID, "superseded", review={"replacement_catalog_id": ELIGIBLE_ID}), "rev-one")
        assert self_ref.status_code == 422                                   # a record cannot supersede itself
        other = "cisco_asa:official_message_id:106024"
        ok = await post(client, body(ELIGIBLE_ID, "superseded", review={"replacement_catalog_id": other}), "rev-one")
        assert ok.status_code == 201 and ok.json()["status"] == "superseded"
        events = [e["to_status"] for e in (await client.get("/knowledge/governance/history", params={"catalog_id": ELIGIBLE_ID}, headers=bearer("rev-one"))).json()["events"]]
        assert events == ["source_verified", "validated", "approved", "superseded"]
    api(check)


# --- catalog registration (import) -------------------------------------------------------------------------------------------------
def test_registration_is_idempotent_audited_automation_and_never_a_decision(api):
    async def check(client, session):
        rows = catalog_import.build_evaluations()
        eligible = [r for r in rows if r["status"] == "ELIGIBLE"]
        first = await service.register_catalog_records(session, eligible)
        await session.commit()
        assert sorted(first["created"]) == sorted(r["catalog_id"] for r in eligible) and not first["refused"]
        second = await service.register_catalog_records(session, eligible)
        assert second["created"] == [] and sorted(second["already_registered"]) == sorted(first["created"])
        events = (await session.execute(select(KnowledgeReviewEvent))).scalars().all()
        assert len(events) == len(eligible) and all(e.event_type == "catalog_import" and e.evidence["actor_kind"] == "automation" for e in events)
        assert all(r.lifecycle_status == "candidate" for r in (await session.execute(select(KnowledgeReview))).scalars().all())
        # not eligible / unknown / stale evaluations are refused
        blocked = next(r for r in rows if r["status"] == "BLOCKED")
        stale = dict(eligible[0], content_hash="0" * 64)
        refused = await service.register_catalog_records(session, [blocked, stale, {"catalog_id": "x:y:z", "status": "ELIGIBLE", "content_hash": "0" * 64}])
        assert len(refused["refused"]) == 3 and refused["created"] == []
        # imported rows can then be decided by humans, and automation can never take that decision
        assert (await post(client, body(ELIGIBLE_ID, "source_verified", review=_source()), "rev-one")).status_code == 201
        with pytest.raises(service.KnowledgePermissionError):
            await service.promote(session, "cisco_asa:official_message_id:106024", "source_verified", actor="catalog-import", actor_kind="automation",
                                  rationale="automation tries", review=copy.deepcopy(SOURCE))
        await session.rollback()
    api(check)


def test_a_changed_record_is_reported_stale_by_the_adapter_after_registration(api):
    async def check(client, session):
        eligible = [r for r in catalog_import.build_evaluations() if r["status"] == "ELIGIBLE"]
        await service.register_catalog_records(session, eligible)
        await session.commit()
        registered = {r.catalog_id: r.content_hash for r in (await session.execute(select(KnowledgeReview))).scalars().all()}
        assert {r["catalog_id"]: r["status"] for r in catalog_import.build_evaluations(registered) if r["catalog_id"] in registered} == {c: "ALREADY_IMPORTED" for c in registered}
        tampered = {c: "f" * 64 for c in registered}
        assert {r["status"] for r in catalog_import.build_evaluations(tampered) if r["catalog_id"] in registered} == {"STALE_SOURCE"}
    api(check)
