"""Catalog adapter, eligibility, operational guidance and the Analyzer diagnostic-result contract (no database)."""
import json
from urllib.parse import urlparse
from pathlib import Path

import pytest

from backend.domain.analyzer.schemas.analyze import SolutionSummary
from backend.domain.analyzer.services import catalog_diagnostics as cd
from backend.domain.knowledge import catalog_adapter as ca
from backend.domain.knowledge.remediation_safety import destructive_actions, destructive_verbs_in, is_prohibition
from backend.domain.knowledge.service import _catalog, canonical_hash, catalog_kind
from tests.certification_fixtures import ASA_POSITIVE, VEEAM_REPLICA, pg_json
from tools import catalog_import

CERT = Path(__file__).resolve().parents[1] / "docs" / "acceptance" / "certification"


def _register():
    return {r["record_key"]: r for r in json.loads((CERT / "register.json").read_text(encoding="utf-8"))["records"]}


def _key(catalog_id):
    kind = catalog_kind(catalog_id)
    return catalog_id if kind in ("candidate", "reference") else ("operational:" if kind == "windows" else "diagnostic_legacy:") + catalog_id


# --- governance catalogue covers every record and agrees with the certification register ------------------------------------
def test_governance_catalogue_covers_all_911_records_with_register_hashes_and_classes():
    catalog, register = _catalog(), _register()
    assert len(catalog) == len(register) == 911
    for cid, entry in catalog.items():
        row = register[_key(cid)]
        assert canonical_hash(entry) == row["content_hash"], cid
        assert ca.classify(catalog_kind(cid), entry) == row["cert_class"], cid


def test_hash_ignores_only_the_catalog_id_key():
    entry = {"a": 1, "catalog_id": "x"}
    assert canonical_hash(entry) == canonical_hash({"a": 1, "catalog_id": "y"}) == canonical_hash({"a": 1})
    assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})


# --- negation-aware destructive detection --------------------------------------------------------------------------------------
@pytest.mark.parametrize("text,destructive", [
    ("Do not delete separate backup files manually.", False),
    ("It is not necessary or desirable to stop the postmaster.", False),
    ("No remediation: this is a requested action.", False),
    ("Never restart the node during resync.", False),
    ("Delete the problematic VM definition in Hyper-V Manager.", True),
    ("Restart the service. Do not use VACUUM FULL.", True),
    ("Drop old replication slots; avoid dropping active ones.", True),
    ("Start the server again; restart sessions.", True),
])
def test_prohibitions_are_not_destructive_instructions(text, destructive):
    assert bool(destructive_actions([text])) is destructive


def test_prohibition_requires_the_negation_before_the_verb():
    assert is_prohibition("Do not delete it.") and not is_prohibition("Delete it, do not wait.")
    assert destructive_verbs_in(["Delete the file. Do not reset the counter."]) == ["delete"]


# --- stated vs not stated -------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("value,expected", [(None, False), ("", False), ("Not stated by the page.", False), ("None", False), ([], False), (["Not stated."], False),
                                            ("Verify the replica is healthy.", True), (["a"], True), ({"k": "Not stated"}, False)])
def test_stated_semantics(value, expected):
    assert ca.stated(value) is expected


# --- eligibility per class --------------------------------------------------------------------------------------------------
def test_only_class_b_records_can_ever_be_eligible_and_every_status_has_a_reason():
    rows = catalog_import.build_evaluations()
    assert {r["status"] for r in rows} <= set(ca.STATUSES)
    for r in rows:
        assert r["reasons"]
        if r["class"] in ("A", "C", "E", "F"):
            assert r["status"] == "INELIGIBLE"  # context, references and unmapped candidates are never diagnostic capabilities
        if r["class"] == "D":
            assert r["status"] == "BLOCKED" and "live_collector" in r["missing"]
        assert r["class"] == r["register_class"]


def test_eligible_records_have_every_operational_item_stated_and_current_evidence():
    rows = [r for r in catalog_import.build_evaluations() if r["status"] == "ELIGIBLE"]
    assert rows and all(r["class"] == "B" and r["missing"] == [] for r in rows)
    entries = _catalog()
    for r in rows:
        view = ca.operational_view(r["kind"], entries[r["catalog_id"]])
        assert ca.operational_problems(view) == []
        if view["destructiveActions"]:
            assert view["rollback"]["status"] == "stated"


def test_committed_eligibility_artifact_is_the_current_computation():
    committed = json.loads((CERT / "catalog_import_eligibility.json").read_text(encoding="utf-8"))
    fresh = catalog_import.build_evaluations()
    assert committed["summary"] == catalog_import.summarize(fresh)
    assert [(r["catalog_id"], r["status"], r["content_hash"]) for r in committed["records"]] == [(r["catalog_id"], r["status"], r["content_hash"]) for r in fresh]


def test_stale_evidence_blocks_and_overlay_state_is_reported():
    entries = _catalog()
    cid = next(r["catalog_id"] for r in catalog_import.build_evaluations() if r["status"] == "ELIGIBLE")
    entry, kind = entries[cid], catalog_kind(cid)
    h = canonical_hash(entry)
    assert ca.evaluate(kind, entry, h, ca.ImportContext(evidence_current=True))["status"] == "ELIGIBLE"
    stale = ca.evaluate(kind, entry, h, ca.ImportContext(evidence_current=False))
    assert stale["status"] == "BLOCKED" and "current_bound_technical_evidence" in stale["missing"]
    assert ca.evaluate(kind, entry, h, ca.ImportContext(evidence_current=True, overlay_hash=h))["status"] == "ALREADY_IMPORTED"
    assert ca.evaluate(kind, entry, h, ca.ImportContext(evidence_current=True, overlay_hash="0" * 64))["status"] == "STALE_SOURCE"
    review = ca.evaluate(kind, entry, h, ca.ImportContext(evidence_current=True, open_findings=("unqualified_always_never",)))
    assert review["status"] == "NEEDS_HUMAN_REVIEW"


def test_destructive_remediation_without_rollback_blocks_a_class_b_candidate():
    base = next(c for c in _catalog().values() if c.get("candidate_id") == "postgresql:locks:deadlock-detected")
    rec = dict(base, remediation=["Drop the replication slot and restart the server."], verification_steps=["Confirm replication resumes."], operational_risk="Replicas may need a rebuild.")
    result = ca.evaluate("candidate", rec, "h", ca.ImportContext(evidence_current=True))
    assert result["status"] == "BLOCKED" and "rollback_for_destructive_action" in result["missing"]
    with_rollback = dict(rec, rollback_steps=["Recreate the slot and re-seed the replica."])
    assert "rollback_for_destructive_action" not in ca.evaluate("candidate", with_rollback, "h", ca.ImportContext(evidence_current=True))["missing"]


# --- Analyzer diagnostic-result contract (what the engineer receives) -------------------------------------------------------------
GUIDANCE_KEYS = {"whatHappened", "why", "inspect", "recommendedAction", "risk", "rollback", "recoveryVerification", "requiredPermission", "humanApproval",
                 "recoveryEvidence", "recoverySuccessCriteria", "operationalImpact", "destructiveRisk", "evidenceAndSource", "versionScope",
                 "confidenceLimitations", "destructiveActions", "reviewState", "catalogId", "contentHash", "missing"}


def test_solution_summary_keeps_every_existing_field_and_adds_optional_guidance():
    names = set(SolutionSummary.model_fields)
    assert {"overview", "causes", "steps", "evidence", "confidence", "limitations", "nextEvidence", "incident", "evidenceItems", "knowledgeMatch", "operationalGuidance"} <= names
    old = SolutionSummary(overview="x")
    assert old.operationalGuidance is None  # older records and unmatched inputs are unchanged


def test_eligible_record_returns_a_complete_guidance_through_the_real_analyzer_path():
    eligible = {r["catalog_id"] for r in catalog_import.build_evaluations() if r["status"] == "ELIGIBLE"}
    assert eligible == {"cisco_asa:official_message_id:113005"}  # the only record whose every required item is stated by its sources
    guidance = cd.catalog_summary("cisco_asa", ASA_POSITIVE["113005"], "en").operationalGuidance
    assert guidance is not None and set(guidance.model_dump()) == GUIDANCE_KEYS and guidance.missing == []
    record = _catalog()["cisco_asa:official_message_id:113005"]["diagnostic_guidance"]
    assert guidance.recoveryVerification.items == [x for x in record["verification_criteria"] if ca.stated(x)]
    assert guidance.reviewState.startswith("PENDING_HUMAN_REVIEW")  # nothing is presented as approved
    assert guidance.evidenceAndSource and guidance.versionScope and guidance.catalogId == "cisco_asa:official_message_id:113005"


def test_veeam_diagnostics_return_guidance_through_build_summary_with_missing_items_listed():
    import asyncio
    from backend.domain.analyzer.services import summary as summary_service
    guidance = asyncio.run(summary_service.build_summary("", "Veeam", "", [], language="en", source_family="veeam_vbr",
                                                         diagnostic_code="VEEAM-REPLICA-SNAPSHOT-CHAIN", evidence_text=VEEAM_REPLICA)).operationalGuidance
    assert guidance is not None and guidance.recoveryVerification.status == "stated" and guidance.rollback.status == "stated"
    assert "required_permission_for_destructive_action" in guidance.missing  # the destructive step has no stated permission, so it is not eligible
    assert guidance.humanApproval.origin == "eims_policy"


def test_missing_operational_items_are_reported_as_not_stated_never_invented():
    guidance = cd.catalog_summary("json", pg_json("40P01"), "en").operationalGuidance
    assert guidance.recoveryVerification.status == "not_stated" and guidance.recoveryVerification.items == []
    assert "recovery_verification" in guidance.missing and guidance.reviewState == "PENDING_HUMAN_REVIEW"
    assert guidance.rollback.status == "not_stated"  # candidates have no rollback field at all today
    assert guidance.recommendedAction.status == "stated" and guidance.evidenceAndSource


def test_reference_only_lookups_do_not_return_diagnostic_guidance():
    # SQLSTATE 23505 is a documented reference without a linked candidate: definition only, no operational guidance
    summary = cd.catalog_summary("json", pg_json("23505"), "en")
    assert summary is not None and summary.operationalGuidance is None


def test_no_guidance_is_ever_labelled_approved():
    for text in (ASA_POSITIVE["106024"], ASA_POSITIVE["113005"]):
        guidance = cd.catalog_summary("cisco_asa", text, "en").operationalGuidance
        assert "APPROVED" not in guidance.reviewState.upper() and guidance.reviewState.startswith("PENDING_HUMAN_REVIEW")


def test_knowledge_entry_contract_and_columns_are_unchanged():
    from backend.api.routers.analyzer.knowledge import KnowledgeProposalContent
    from backend.domain.analyzer.models.knowledge import KnowledgeEntry
    cols = {c.name for c in KnowledgeEntry.__table__.columns}
    assert {"source_history_id", "solution_steps", "validation_steps", "rollback_steps", "risk_level", "status"} <= cols and len(cols) == 32  # the model was not changed by the adapter work
    ok = KnowledgeProposalContent(title="t t", resolution_status="resolved", root_cause="cause", solution_steps=["do it now"], evidence_notes=["e e"],
                                  risk_level="high", validation_steps=["check it"], rollback_steps=["undo it"])
    assert ok.risk_level == "high"


def test_source_history_requirement_is_why_catalog_rows_are_not_copied_into_knowledge_entry():
    from backend.domain.analyzer.models.knowledge import KnowledgeEntry
    col = KnowledgeEntry.__table__.c.source_history_id
    assert col.nullable is False and list(col.foreign_keys)[0].target_fullname == "analysis_history.id"


# --- structured operational fields (schema) ---------------------------------------------------------------------------------------
STATED = {"state": "stated", "items": ["Run the documented check."], "source": {"url": "https://example.org/doc", "quote": "verbatim sentence", "retrieved": "2026-11-22"}}


@pytest.mark.parametrize("block,fragment", [
    ({"rollback_steps": {"state": "stated", "items": ["x"], "source": {"url": "http://insecure", "quote": "q", "retrieved": "2026-11-22"}}}, "https source url"),
    ({"rollback_steps": {"state": "stated", "items": ["do it"], "source": {"url": "https://a.b", "quote": "", "retrieved": "2026-11-22"}}}, "verbatim source quote"),
    ({"rollback_steps": {"state": "stated", "items": ["do it"], "source": {"url": "https://a.b", "quote": "q", "retrieved": "yesterday"}}}, "retrieved date"),
    ({"rollback_steps": {"state": "stated", "items": ["Not stated"], "source": {"url": "https://a.b", "quote": "q", "retrieved": "2026-11-22"}}}, "placeholder"),
    ({"rollback_steps": {"state": "unverified", "items": ["maybe"]}}, "basis"),
    ({"rollback_steps": {"state": "not_stated", "items": [], "reason": ""}}, "reason"),
    ({"rollback_steps": {"state": "not_stated", "items": ["invented"], "reason": "searched"}}, "no items"),
    ({"made_up": STATED}, "unknown field"),
    ({"rollback_steps": {"state": "guess", "items": ["x"]}}, "state must be"),
])
def test_operational_fields_reject_untraceable_or_placeholder_content(block, fragment):
    assert any(fragment in p for p in ca.validate_operational_fields(block)), ca.validate_operational_fields(block)


def test_valid_operational_fields_and_unverified_never_count_as_stated():
    assert ca.validate_operational_fields({"rollback_steps": STATED, "required_permission": {"state": "not_stated", "items": [], "reason": "searched the page"},
                                           "verification_steps": {"state": "unverified", "items": ["Re-run the check."], "basis": "composed"}}) == []
    base = next(c for c in _catalog().values() if c.get("candidate_id") == "postgresql:locks:deadlock-detected")
    rec = dict(base, operational_fields={"verification_steps": {"state": "unverified", "items": ["Re-run the check."], "basis": "composed"}})
    view = ca.operational_view("candidate", rec)
    assert view["recoveryVerification"]["status"] == "unverified" and "recovery_verification" in ca.operational_problems(view)
    rec = dict(base, operational_fields={"verification_steps": STATED})
    assert ca.operational_problems(ca.operational_view("candidate", rec)) == []


def test_loader_rejects_invalid_operational_fields(tmp_path):
    from backend.domain.analyzer.services import vendor_diagnostics as vd
    rec = json.loads(json.dumps(next(c for c in vd.DIAGNOSTIC_CANDIDATES if c["candidate_id"] == "postgresql:locks:deadlock-detected")))
    rec["operational_fields"] = {"rollback_steps": {"state": "stated", "items": ["x y z"]}}
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"schema_version": 1, "records": [rec]}), encoding="utf-8")
    with pytest.raises(ValueError, match="operational_fields"):
        vd.load_diagnostic_candidates(path)


def test_supplement_never_replaces_a_catalog_statement_and_only_stated_fields_merge():
    entry = _catalog()["cisco_asa:official_message_id:113005"]
    view = ca.operational_view("legacy", entry)
    merged = ca.merge_supplement(view, {"verification_steps": dict(STATED, items=["A different check."]), "rollback_steps": {"state": "unverified", "items": ["x y"], "basis": "b"}})
    assert merged["recoveryVerification"] == view["recoveryVerification"]          # the catalog's own statement wins
    assert merged["rollback"]["status"] == view["rollback"]["status"]                # unverified is not merged


def test_human_approval_policy_is_labelled_eims_policy_and_only_for_destructive_actions():
    base = next(c for c in _catalog().values() if c.get("candidate_id") == "postgresql:locks:deadlock-detected")
    destructive = ca.operational_view("candidate", dict(base, remediation=["Drop the replication slot."]))
    assert destructive["humanApproval"]["origin"] == "eims_policy" and destructive["humanApproval"]["status"] == "stated"
    plain = ca.operational_view("candidate", dict(base, remediation=["Review the application lock order."]))
    assert plain["humanApproval"]["status"] == "not_stated"


def test_curated_remediation_fields_are_valid_traceable_and_applied_to_the_catalog():
    curated = json.loads((CERT / "remediation_fields_curated.json").read_text(encoding="utf-8"))["records"]
    catalog = _catalog()
    for key, block in curated.items():
        assert ca.validate_operational_fields(block) == []
        assert catalog[key]["operational_fields"] == block and catalog[key]["review_status"] == "PENDING_HUMAN_REVIEW"
        for name, entry in block.items():
            if entry["state"] == "stated":
                assert entry["source"]["url"].startswith("https://") and urlparse(entry["source"]["url"]).hostname in {urlparse(x["url"]).hostname for x in catalog[key]["official_sources"]}   # quoted from the vendor host the record cites
