"""Destination-state quality gates for knowledge lifecycle transitions (pure, no DB)."""
from __future__ import annotations

import pytest

from backend.domain.knowledge.gates import evaluate_gate

HASH = "a" * 64
OLD_HASH = "b" * 64

ENTRY = {
    "catalog_id": "veeam_vbr:eims_diagnostic:X",
    "knowledge_class": "diagnostic_candidate",
    "limitations": "Reference knowledge is not proof of root cause.",
    "investigation_steps": ["collect job log"],
}

SOURCE = {
    "source_title": "Veeam KB1234",
    "source_url": "https://www.veeam.com/kb1234",
    "supporting_section": "Cause",
    "claim_evidence": "States CTK deletion can fail when the file is locked.",
    "verified_at": "2026-11-19T10:00:00+00:00",
    "verifier": "alice",
    "vendor_product_scope": "Veeam B&R 12",
}
VALID = {
    "product_version_scope": "Veeam B&R 12.x",
    "applicability": "VMware backup jobs using CBT",
    "validation_basis": "Reproduced lock in lab run 7",
    "verification_criteria": ["next job completes without CTK error"],
}


def ev(to_status, actor, source_hash=HASH, evidence=None):
    return {"to_status": to_status, "actor": actor, "source_hash": source_hash,
            "evidence": dict(evidence or {}, actor_kind="human")}


def gate(target, current, *, actor="alice", rationale="because", review=None, events=(),
         contributor=None, stale=False, content_hash=HASH, known=(), actor_kind="human"):
    return evaluate_gate(
        ENTRY, current, target, actor=actor, rationale=rationale, review=review or {},
        events=list(events), content_hash=content_hash, review_required=stale,
        contributor=contributor, known_ids=set(known), actor_kind=actor_kind,
    )


def test_candidate_needs_nothing_beyond_actor_and_rationale():
    problems, permission = gate("candidate", "rejected")
    assert problems == [] and permission == []


def test_source_verified_requires_every_source_field():
    problems, _ = gate("source_verified", "candidate", review={})
    for field in SOURCE:
        assert any(field in p for p in problems), field
    assert gate("source_verified", "candidate", review=SOURCE) == ([], [])


@pytest.mark.parametrize("url", ["", "http://insecure.example", "not a url", "javascript:alert(1)"])
def test_source_url_must_be_https(url):
    problems, _ = gate("source_verified", "candidate", review={**SOURCE, "source_url": url})
    assert any("source_url" in p for p in problems)


def test_verifier_must_be_the_authenticated_actor():
    problems, permission = gate("source_verified", "candidate", actor="mallory", review=SOURCE)
    assert problems or permission


def test_validated_requires_fields_and_prior_source_provenance():
    problems, _ = gate("validated", "source_verified", actor="bob", review={}, events=[])
    for field in VALID:
        assert any(field in p for p in problems), field
    assert any("source_verified" in p for p in problems)
    ok = gate("validated", "source_verified", actor="bob", review=VALID,
              events=[ev("source_verified", "alice", evidence=SOURCE)])
    assert ok == ([], [])


def test_validated_rejects_provenance_for_a_different_source_revision():
    problems, _ = gate("validated", "source_verified", actor="bob", review=VALID,
                       events=[ev("source_verified", "alice", source_hash=OLD_HASH, evidence=SOURCE)])
    assert any("revision" in p for p in problems)


def test_approved_requires_validation_current_revision_and_not_stale():
    base = [ev("source_verified", "alice", evidence=SOURCE), ev("validated", "bob", evidence=VALID)]
    assert gate("approved", "validated", actor="carol", events=base) == ([], [])
    problems, _ = gate("approved", "validated", actor="carol", events=base[:1])
    assert any("validated" in p for p in problems)
    stale_events = [ev("source_verified", "alice", evidence=SOURCE),
                    ev("validated", "bob", source_hash=OLD_HASH, evidence=VALID)]
    problems, _ = gate("approved", "validated", actor="carol", events=stale_events)
    assert any("revision" in p for p in problems)
    problems, _ = gate("approved", "validated", actor="carol", events=base, stale=True)
    assert any("stale" in p or "renewed" in p for p in problems)


@pytest.mark.parametrize("actor", ["alice", "bob"])
def test_approval_separation_of_duties(actor):
    base = [ev("source_verified", "alice", evidence=SOURCE), ev("validated", "bob", evidence=VALID)]
    _, permission = gate("approved", "validated", actor=actor, events=base)
    assert permission


def test_contributor_cannot_approve_own_work():
    base = [ev("source_verified", "alice", evidence=SOURCE), ev("validated", "bob", evidence=VALID)]
    _, permission = gate("approved", "validated", actor="carol", events=base, contributor="carol")
    assert permission


def test_blank_actor_or_rationale_is_rejected_everywhere():
    for target, current in (("rejected", "candidate"), ("deprecated", "approved")):
        p, perm = gate(target, current, actor=" ")
        assert perm
        p, perm = gate(target, current, rationale=" ")
        assert p


def test_superseded_requires_a_known_distinct_replacement():
    problems, _ = gate("superseded", "approved", review={})
    assert any("replacement" in p for p in problems)
    problems, _ = gate("superseded", "approved", review={"replacement_catalog_id": ENTRY["catalog_id"]},
                       known={ENTRY["catalog_id"], "other"})
    assert any("replacement" in p for p in problems)
    problems, _ = gate("superseded", "approved", review={"replacement_catalog_id": "missing"}, known={"other"})
    assert any("replacement" in p for p in problems)
    assert gate("superseded", "approved", review={"replacement_catalog_id": "other"},
                known={"other"}) == ([], [])


# --- human / AI / automation separation (Round 4) ------------------------------------------------------------------------
HUMAN_ONLY = ["source_verified", "validated", "approved", "deprecated", "superseded"]


@pytest.mark.parametrize("kind", ["ai_assist", "automation", "unspecified", "", None, "Human", "human "])
@pytest.mark.parametrize("target", HUMAN_ONLY)
def test_only_an_exact_human_actor_kind_can_take_a_decision(target, kind):
    base = [ev("source_verified", "alice", evidence=SOURCE), ev("validated", "bob", evidence=VALID)]
    review = dict(SOURCE, **VALID, replacement_catalog_id="x")
    _, permission = gate(target, "validated", actor="carol", review=review, events=base, actor_kind=kind, known={"x"})
    assert any("human decision" in p for p in permission)


@pytest.mark.parametrize("target", ["candidate", "rejected"])
def test_ai_or_automation_may_reopen_or_reject_but_that_is_all(target):
    for kind in ("ai_assist", "automation", None):
        problems, permission = gate(target, "validated", actor="bot", actor_kind=kind)
        assert permission == [] and problems == []


@pytest.mark.parametrize("prior_kind", ["ai_assist", "automation", None])
def test_prior_decisions_not_recorded_by_a_human_do_not_satisfy_prerequisites(prior_kind):
    def event(status, actor, evidence):
        e = {"to_status": status, "actor": actor, "source_hash": HASH, "evidence": dict(evidence)}
        if prior_kind:
            e["evidence"]["actor_kind"] = prior_kind
        return e
    problems, _ = gate("validated", "source_verified", actor="bob", review=VALID, events=[event("source_verified", "alice", SOURCE)])
    assert any("human actor" in p for p in problems)
    base = [event("source_verified", "alice", SOURCE), event("validated", "bob", VALID)]
    problems, _ = gate("approved", "validated", actor="carol", events=base)
    assert any("human actors" in p for p in problems)


def test_the_full_human_path_still_passes():
    base = [ev("source_verified", "alice", evidence=SOURCE), ev("validated", "bob", evidence=VALID)]
    assert gate("approved", "validated", actor="carol", events=base) == ([], [])


def test_a_free_text_reviewer_name_is_not_an_actor_kind():
    # verifier is a text field inside the review payload; it can never stand in for actor_kind
    _, permission = gate("source_verified", "candidate", actor="alice", review=dict(SOURCE, verifier="alice"), actor_kind=None)
    assert any("human decision" in p for p in permission)
