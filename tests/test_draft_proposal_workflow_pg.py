"""Draft proposal workflow end to end (disposable PostgreSQL, real authentication):

catalog -> adapter -> candidate -> draft proposal -> human review -> decision API -> governance overlay -> Analyzer guidance.
"""
import copy
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from backend.api.routers.analyzer import analyze as analyze_router
from backend.domain.analyzer.services import catalog_diagnostics as cd
from backend.domain.knowledge import proposals, service
from backend.domain.knowledge.models import KnowledgeReviewEvent
from tests.certification_fixtures import pg_json
from tests.test_knowledge_governance_api_pg import USERS, api, bearer, body, _source  # noqa: F401  (api is the fixture)
from tests.test_knowledge_service import VALID

CID = "candidate:postgresql:locks:deadlock-detected"       # class B, blocked only by missing recovery verification
REFERENCE = "reference:postgresql:sqlstate:40P01"
BLOCKED_OTHER = "candidate:postgresql:auth:password-authentication-failed"
STATED_VERIFY = {"verification_steps": {"state": "stated", "items": ["Confirm that the previously deadlocking transactions now complete without a deadlock error."],
                                        "source": {"url": "https://www.postgresql.org/docs/16/explicit-locking.html", "quote": "synthetic quote for the test",
                                                   "retrieved": "2026-11-22"}}}
UNVERIFIED_VERIFY = {"verification_steps": {"state": "unverified", "items": ["Re-run the workload and check the log."], "basis": "composed by a person"}}


def prop(catalog_id=CID, content=None, note="synthetic draft", **kw):
    entry = service._catalog()[catalog_id]
    return {"catalog_id": catalog_id, "base_hash": service.canonical_hash(entry), "content": STATED_VERIFY if content is None else content, "note": note, **kw}


async def post_to(client, path, payload, who=None, headers=None):
    return await client.post("/knowledge/governance" + path, json=payload, headers=headers if headers is not None else (bearer(who) if who else {}))


async def state(client, catalog_id=CID, who="rev-one"):
    return (await client.get("/knowledge/governance/proposals", params={"catalog_id": catalog_id}, headers=bearer(who))).json()


def guidance_for(catalog_id=CID):
    return cd.catalog_summary("json", pg_json("40P01"), "en")


# --- authorization and class rules --------------------------------------------------------------------------------------------------
def test_only_authenticated_human_reviewers_can_write_drafts_and_references_have_no_proposal_path(api):
    async def check(client, session):
        assert (await post_to(client, "/proposals", prop())).status_code == 401
        assert (await post_to(client, "/proposals", prop(), headers={"Authorization": "Bearer synthetic-governance-admin-token-only"})).status_code == 403
        assert (await post_to(client, "/proposals", prop(), "plain-user")).status_code == 403
        for extra in ({"actor": "x"}, {"actor_kind": "human"}):
            assert (await post_to(client, "/proposals", {**prop(), **extra}, "rev-one")).status_code == 422
        ref = await post_to(client, "/proposals", prop(REFERENCE), "rev-one")
        assert ref.status_code == 422 and "no proposal path" in ref.text                  # reference-only
        win = await post_to(client, "/proposals", prop("windows_event:official_event_id:4624"), "rev-one")
        assert win.status_code == 422                                                      # Windows context
        assert (await post_to(client, "/proposals", {**prop(), "catalog_id": "nope:nope:nope"}, "rev-one")).status_code == 404
        assert (await session.execute(select(KnowledgeReviewEvent))).scalars().first() is None
    api(check)


def test_invalid_drafts_are_rejected_and_unverified_fields_never_complete_a_record(api):
    async def check(client, session):
        bad = {"verification_steps": {"state": "stated", "items": ["x y z"], "source": {"url": "http://insecure", "quote": "", "retrieved": "soon"}}}
        assert (await post_to(client, "/proposals", prop(content=bad), "rev-one")).status_code == 422
        assert (await post_to(client, "/proposals", prop(content={}), "rev-one")).status_code == 422
        assert (await post_to(client, "/proposals", prop(content={"invented_field": {"state": "stated"}}), "rev-one")).status_code == 422
        pv = (await post_to(client, "/proposals/preview", {"catalog_id": CID, "content": UNVERIFIED_VERIFY}, "rev-one")).json()
        assert "recovery_verification" in pv["missingWithDraft"] and pv["unverifiedFields"] == ["verification_steps"]   # still missing
        pv = (await post_to(client, "/proposals/preview", {"catalog_id": CID, "content": STATED_VERIFY}, "rev-one")).json()
        assert pv["missingNow"] == ["recovery_verification"] and pv["missingWithDraft"] == [] and pv["validationProblems"] == []
        assert (await session.execute(select(KnowledgeReviewEvent))).scalars().first() is None   # preview writes nothing
    api(check)


# --- draft lifecycle ------------------------------------------------------------------------------------------------------------------
def test_draft_save_is_idempotent_editable_recorded_and_never_active_guidance(api):
    async def check(client, session):
        first = await post_to(client, "/proposals", prop(), "rev-one")
        assert first.status_code == 201 and first.json()["status"] == "DRAFT" and first.json()["created"] is True
        again = await post_to(client, "/proposals", prop(), "rev-one")
        assert again.json()["created"] is False and again.json()["revisions"] == 1       # identical content: no duplicate
        edited = await post_to(client, "/proposals", prop(content={**STATED_VERIFY, **{"operational_impact": {"state": "not_stated", "items": [], "reason": "searched the page"}}}), "rev-two")
        assert edited.json()["revisions"] == 2 and edited.json()["draftAuthor"] == "rev-two"   # a different reviewer may edit; both recorded
        s = await state(client)
        assert [h["actor"] for h in s["history"]] == ["rev-one", "rev-two"] and all(h["actorKind"] == "human" for h in s["history"])
        assert s["eligibility"]["status"] == "BLOCKED"                                    # eligibility is the adapter's, not the draft's
        # a DRAFT is invisible to the Analyzer: no supplement, guidance still lacks recovery verification
        assert await proposals.approved_supplement(session, CID) is None
        g = guidance_for().operationalGuidance
        await analyze_router._apply_approved_supplement(session, guidance_for())
        assert g.recoveryVerification.status == "not_stated" and "recovery_verification" in g.missing
        # draft changes never touch lifecycle or decision prerequisites
        assert (await session.execute(select(service.KnowledgeReview))).scalars().first() is None
    api(check)


def test_submission_withdrawal_and_editing_after_submission(api):
    async def check(client, session):
        await post_to(client, "/proposals", prop(), "rev-one")
        sub = await post_to(client, "/proposals/submit", prop(), "rev-two")
        assert sub.json()["status"] == "HUMAN_REVIEW"
        edit = await post_to(client, "/proposals", prop(content={**STATED_VERIFY, **UNVERIFIED_VERIFY}), "rev-one")
        assert edit.json()["status"] == "DRAFT"                                          # editing a submitted draft returns it to DRAFT
        assert (await post_to(client, "/proposals/submit", prop(), "rev-one")).json()["status"] == "HUMAN_REVIEW"
        wd = await post_to(client, "/proposals/withdraw", prop(), "rev-one")
        assert wd.json()["status"] == "CANDIDATE" and wd.json()["draft"] is None
        assert (await post_to(client, "/proposals/submit", prop(), "rev-one")).status_code == 422   # nothing left to submit
    api(check)


def test_changed_source_makes_the_draft_stale_and_blocks_further_use(api, monkeypatch):
    async def check(client, session):
        payload = prop()
        await post_to(client, "/proposals", payload, "rev-one")
        original = service._catalog

        def changed():
            catalog = original()
            catalog[CID] = dict(catalog[CID], limitations=catalog[CID]["limitations"] + " (edited upstream)")
            return catalog
        monkeypatch.setattr(service, "_catalog", changed)
        s = await state(client)
        assert s["status"] == "STALE" and s["stale"] is True and s["baseContentHash"] == payload["base_hash"] != s["currentContentHash"]
        assert (await post_to(client, "/proposals", payload, "rev-one")).status_code == 422          # old base hash refused
        assert (await post_to(client, "/proposals/submit", payload, "rev-one")).status_code == 422
        fresh = dict(payload, base_hash=s["currentContentHash"])
        assert (await post_to(client, "/proposals", fresh, "rev-one")).json()["status"] == "DRAFT"   # re-based draft
    api(check)


def test_ai_prepared_drafts_need_a_human_to_submit_and_cannot_approve(api):
    async def check(client, session):
        entry = service._catalog()[CID]
        base = service.canonical_hash(entry)
        saved = await proposals.save_draft(session, CID, actor="draft-bot", actor_kind="ai_assist", content=STATED_VERIFY, base_hash=base, note="prepared by an assistant")
        await session.commit()
        assert saved["status"] == "DRAFT" and saved["draftAuthorKind"] == "ai_assist"
        with pytest.raises(service.KnowledgePermissionError):
            await proposals.submit_draft(session, CID, actor="draft-bot", actor_kind="ai_assist", base_hash=base, note="self submit")
        with pytest.raises(service.KnowledgePermissionError):
            await proposals.submit_draft(session, CID, actor="batch", actor_kind="automation", base_hash=base, note="auto submit")
        await session.rollback()
        sub = await post_to(client, "/proposals/submit", prop(), "rev-one")
        assert sub.json()["status"] == "HUMAN_REVIEW"
        events = (await session.execute(select(KnowledgeReviewEvent).order_by(KnowledgeReviewEvent.created_at))).scalars().all()
        assert events[-1].evidence["prepared_by_kind"] == "ai_assist" and events[-1].evidence["actor_kind"] == "human"
    api(check)


# --- decision API, supplement and Analyzer ---------------------------------------------------------------------------------------------
async def verify_and_validate(client):
    assert (await post(client, body(CID, "source_verified", review=_source()), "rev-one")).status_code == 201
    assert (await post(client, body(CID, "validated", review=VALID), "rev-two")).status_code == 201


async def post(client, payload, who):
    return await client.post("/knowledge/governance/decisions", json=payload, headers=bearer(who))


def test_blocked_record_becomes_active_guidance_only_after_a_human_approves_the_reviewed_supplement(api):
    async def check(client, session):
        # without a supplement the diagnostic approval is refused: recovery verification is not stated
        await verify_and_validate(client)
        refused = await post(client, body(CID, "approved", approval_scope="approved_as_diagnostic"), "rev-three")
        assert refused.status_code == 422 and "recovery_verification" in refused.json()["detail"]["missing"]
        # draft prepared and submitted by rev-three; the author may not approve it
        await post_to(client, "/proposals", prop(), "rev-three")
        await post_to(client, "/proposals/submit", prop(), "rev-three")
        before = guidance_for()
        await analyze_router._apply_approved_supplement(session, before)
        assert before.operationalGuidance.recoveryVerification.status == "not_stated"      # HUMAN_REVIEW is still not active
        author = await post(client, body(CID, "approved", approval_scope="approved_as_diagnostic"), "rev-three")
        assert author.status_code == 403 and author.json()["detail"]["code"] == "author_cannot_approve"
        # an independent reviewer who did not author the draft approves (rev-one verified, rev-two validated, so use the admin account)
        ok = await post(client, body(CID, "approved", approval_scope="approved_as_diagnostic"), "admin-user")
        assert ok.status_code == 201 and ok.json()["status"] == "approved"
        event = (await session.execute(select(KnowledgeReviewEvent).where(KnowledgeReviewEvent.to_status == "approved"))).scalars().one()
        assert event.evidence["supplement"] == STATED_VERIFY and event.evidence["supplement_digest"] == proposals.digest(STATED_VERIFY)
        assert (await state(client))["status"] == "APPROVED"
        # now the Analyzer merges the stated, approved field
        after = guidance_for()
        await analyze_router._apply_approved_supplement(session, after)
        g = after.operationalGuidance
        assert g.recoveryVerification.status == "stated" and g.recoveryVerification.origin == "approved_supplement" and g.missing == []
        assert g.reviewState.startswith("APPROVED_SUPPLEMENT")
    api(check)


def test_unverified_supplement_content_is_never_merged_and_a_changed_record_loses_its_approval(api, monkeypatch):
    async def check(client, session):
        await verify_and_validate(client)
        mixed = {**STATED_VERIFY, "recovery_evidence": {"state": "unverified", "items": ["Check the server log for deadlock messages."], "basis": "composed"}}
        await post_to(client, "/proposals", prop(content=mixed), "rev-three")
        await post_to(client, "/proposals/submit", prop(content=mixed), "rev-three")
        assert (await post(client, body(CID, "approved", approval_scope="approved_as_diagnostic"), "admin-user")).status_code == 201
        merged = guidance_for()
        await analyze_router._apply_approved_supplement(session, merged)
        g = merged.operationalGuidance
        assert g.recoveryVerification.status == "stated" and g.recoveryEvidence.status == "not_stated"   # unverified part stays out
        original = service._catalog

        def changed():
            catalog = original()
            catalog[CID] = dict(catalog[CID], limitations=catalog[CID]["limitations"] + " (edited after approval)")
            return catalog
        monkeypatch.setattr(service, "_catalog", changed)
        assert await proposals.approved_supplement(session, CID) is None                 # stale approval is not active
        stale = guidance_for()
        await analyze_router._apply_approved_supplement(session, stale)
        assert stale.operationalGuidance.recoveryVerification.status == "not_stated"
    api(check)


def test_unrelated_blocked_candidates_and_references_stay_untouched(api):
    async def check(client, session):
        s = await state(client, BLOCKED_OTHER)
        assert s["status"] == "CANDIDATE" and s["eligibility"]["status"] == "BLOCKED" and s["draft"] is None
        assert await proposals.approved_supplement(session, BLOCKED_OTHER) is None and await proposals.approved_supplement(session, REFERENCE) is None
        assert cd.catalog_summary("json", pg_json("23505"), "en").operationalGuidance is None     # reference-only: no guidance at all
        copy.deepcopy(USERS)
    api(check)


def test_reads_follow_open_access_but_every_write_requires_the_reviewer_capability(api):
    async def check(client, session):
        for path, params in (("/queue", {}), ("/proposals", {"catalog_id": CID}), ("/history", {"catalog_id": CID})):
            url = "/knowledge/governance" + path
            assert (await client.get(url, params=params)).status_code == 200                                    # open access, no login
            assert (await client.get(url, params=params, headers=bearer("plain-user"))).status_code == 200
        # nothing in the read payloads lets a client act: writes stay protected
        for path, payload in (("/proposals", prop()), ("/proposals/submit", {"catalog_id": CID, "base_hash": "0" * 64}),
                              ("/proposals/withdraw", {"catalog_id": CID, "base_hash": "0" * 64}), ("/decisions", {"catalog_id": CID, "target": "source_verified"})):
            assert (await post_to(client, path, payload)).status_code == 401                                    # anonymous
            assert (await post_to(client, path, payload, "plain-user")).status_code == 403                      # authenticated non-reviewer
            assert (await post_to(client, path, payload, headers={"Authorization": "Bearer synthetic-governance-admin-token-only"})).status_code == 403   # shared token
            assert (await post_to(client, path, payload, headers=bearer("rev-one", exp=datetime.now(UTC) - timedelta(minutes=1)))).status_code == 401  # expired
            assert (await post_to(client, path, payload, headers=bearer("no-such-user"))).status_code == 401    # unknown identity
    api(check)
