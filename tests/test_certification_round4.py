"""Round 4: Windows source research ledger, catalog applicability, Class B review package, risk evidence, knowledge model.

These tests check the tooling and the committed artifacts for consistency. They never certify a record.
"""
import json
import time
from pathlib import Path

import pytest

from tools import analyze_knowledge_model as akm
from tools import apply_windows_applicability as apply_app
from tools import build_windows_source_ledger as ledger_tool
from tools.build_certification_register import SERVICES, build_register

CERT = Path(__file__).resolve().parents[1] / "docs" / "acceptance" / "certification"


def _json(name):
    return json.loads((CERT / name).read_text(encoding="utf-8"))


def _catalog():
    return json.loads((SERVICES / "operational_event_catalog.json").read_text(encoding="utf-8"))


# --- extraction rules keep OS version, schema version, product-level scope and publication data apart ---------------------
AUDIT_TEXT = ('Version: Windows Server 2008, Windows Vista. Event Versions: 0 - Windows Server 2008, Windows Vista. 1 - Windows Server 2012, Windows 8. '
              'Added "Impersonation Level" field. Field Descriptions Subject: ...')


def test_audit_page_version_line_is_split_into_os_statement_and_event_schema_versions():
    out = ledger_tool.extract(AUDIT_TEXT, "4624")
    assert out["os_statement"] == "Windows Server 2008, Windows Vista"
    assert out["event_versions_statement"].startswith("0 - Windows Server 2008")
    assert out["applies_to_statement"] == "" and out["build_support_statement"] == ""


def test_a_version_field_that_names_no_windows_release_is_not_an_os_statement():
    out = ledger_tool.extract("Version: 6.1 Message: The system has rebooted without cleanly shutting down first.", "41")
    assert out["os_statement"] == "" and out["product_version_field"] == "6.1"
    out = ledger_tool.extract("Version: Definition version Engine Version: Antimalware Engine version Event ID 1007", "1007")
    assert out["os_statement"] == ""


def test_product_level_applies_to_is_kept_separate_from_os_versions():
    out = ledger_tool.extract("Applies to: Supported versions of Windows Client Feedback Summarize this article for me", "41")
    assert out["applies_to_statement"] == "Supported versions of Windows Client" and out["os_statement"] == ""


@pytest.mark.parametrize("text,eid,expected", [
    ("A service does not start, and events 7000 and 7011 are logged in Windows Server", "7011", True),
    ("Event ID 7011: A timeout was reached", "7011", True),
    ("7036: The service entered the running state", "7036", True),
    ("Port 70110 is used by the service", "7011", False),
    ("Windows Server 2019 supports many things", "7011", False),
])
def test_event_id_must_appear_in_an_event_like_context(text, eid, expected):
    assert ledger_tool.id_context(text, eid, [])[0] is expected


def test_event_id_matching_is_not_pathological_on_long_numeric_text():
    text = ("events " + "1, 2, 3, " * 4000 + "and more").strip()
    started = time.monotonic()
    ledger_tool.id_context(text, "7011", ["Service Control Manager"])
    assert time.monotonic() - started < 2.0


# --- committed ledger and catalog applicability ------------------------------------------------------------------------
def test_ledger_covers_every_windows_record_exactly_once_and_uses_only_official_hosts():
    ledger = _json("windows_source_research_ledger.json")
    catalog = _catalog()
    assert len(ledger["dispositions"]) == len(catalog) == ledger["summary"]["records"]
    assert len({d["record_key"] for d in ledger["dispositions"]}) == len(catalog)
    for row in ledger["rows"]:
        assert ledger_tool.urlparse_host(row["source_url"]) in ledger_tool.ALLOWED_HOSTS and "/answers/" not in row["source_url"]
        assert isinstance(row["pub_ms_date"], str)  # publication data is its own field, never mixed into the OS statement
    assert all(d["human_status"] in ("NEEDS_HUMAN_REVIEW", "UNVERIFIED") for d in ledger["dispositions"])  # nothing is verified


def test_every_catalog_applicability_block_matches_a_ledger_row_and_is_verbatim_official_text():
    ledger = _json("windows_source_research_ledger.json")
    rows = {(r["event_id"], r["provider"], r["source_url"]): r for r in ledger["rows"]}
    blocks = [(e, e["applicability"]) for e in _catalog() if "applicability" in e]
    assert len(blocks) == ledger["summary"]["by_disposition"]["EXPLICIT_OS_STATEMENT_FOUND"] + ledger["summary"]["by_disposition"]["PRODUCT_LEVEL_APPLICABILITY_ONLY"]
    for rec, block in blocks:
        row = rows[(rec["event_id"], rec["provider"], block["source_url"])]
        assert block["status"] == "official_text_extracted_human_reread_pending"
        if block["kind"] == "os_versions_as_stated_by_page":
            assert block["statement"] == row["os_statement"] and ledger_tool.OS_WORDS.search(block["statement"])
        else:
            assert block["kind"] == "product_level_statement_only" and block["statement"] == row["applies_to_statement"]
            assert not ledger_tool.OS_WORDS.search(block["statement"])  # a product-level scope must not be passed off as an OS range
        assert block["publication"]["ms_date"] == row["pub_ms_date"]


def test_register_never_uses_publication_dates_or_page_scope_as_an_os_version():
    register = {r["record_key"]: r for r in _json("register.json")["records"]}
    for rec in _catalog():
        block = rec.get("applicability")
        key = f"operational:windows_event:official_event_id:{rec.get('diagnostic_code', rec['event_id'])}"
        row = register[key]
        if block and block["kind"] == "os_versions_as_stated_by_page":
            assert row["version_scope_basis"] == "explicit_from_official_statement" and row["version_scope"] == block["statement"]
            assert block["publication"]["ms_date"] not in row["version_scope"]
            assert row["readiness"]["source_blockers"] == [] and row["readiness"]["source"] == "SOURCE_UNVERIFIED"
        elif block:
            assert row["version_scope_basis"] == "product_level_statement" and "version_scope_product_level_only" in row["readiness"]["source_blockers"]
        else:
            assert row["version_scope_basis"] != "explicit_from_official_statement"


def test_no_windows_record_states_build_support_and_build_mentions_never_reach_the_catalog():
    rows = _json("windows_source_research_ledger.json")["rows"]
    assert not [r for r in rows if r["build_support_statement"]]  # nothing in the sources states a supported build
    mentions = [r for r in rows if r["build_mention"]]
    assert mentions and all("Build" in r["build_mention"] for r in mentions)  # e.g. 'KB5044284 (OS Build 26100.2033)' for one update
    assert not [e for e in _catalog() if "applicability" in e and "Build" in json.dumps(e["applicability"])]


def test_applying_the_ledger_again_changes_nothing_and_preserves_line_endings():
    text = (SERVICES / "operational_event_catalog.json").open(encoding="utf-8", newline="").read()
    chosen = apply_app.plan(_json("windows_source_research_ledger.json"))
    again, count = apply_app.apply(text, chosen)
    assert count == 0 and again == text and "\r\n" in text


@pytest.mark.parametrize("nl", ["\r\n", "\n"])
def test_apply_preserves_the_files_own_line_endings_byte_for_byte(nl):
    body = nl.join(['[', '  {', '    "event_id": "1",', '    "provider": "P"', '  }', ']', ''])
    chosen = {("1", "P"): {"kind": "product_level_statement_only", "statement": "s", "event_versions": "", "source_url": "u", "source_title": "t",
                           "publication": {}, "retrieved": "d", "status": "x"}}
    out, count = apply_app.apply(body, chosen)
    assert count == 1 and json.loads(out)[0]["applicability"]["statement"] == "s"
    assert out.count("\r\n") == (out.count("\n") if nl == "\r\n" else 0)
    stripped = out.replace(f',{nl}    "applicability": ' + json.dumps(chosen[("1", "P")]), "")
    assert stripped == body


# --- the findings disposition now explains every Round 3 change -----------------------------------------------------
def test_round3_findings_are_all_accounted_for_in_the_current_dispositions():
    rows = _json("findings_disposition.json")["dispositions"]
    round3 = {(f["record_key"], f["code"]) for f in _json("baseline_round3_findings.json")["findings"] if f["severity"] != "evidence"}
    have = {(r["record_key"], r["finding_type"]) for r in rows}
    assert round3 <= have
    resolved = [r for r in rows if r.get("resolved_by") == "official_applicability_statement"]
    assert resolved and all(r["resolution_status"] == "RESOLVED_BY_EVIDENCE" for r in resolved)
    register = {r["record_key"]: r for r in _json("register.json")["records"]}
    assert all(register[r["record_key"]]["version_scope_basis"] == "explicit_from_official_statement" for r in resolved)


def test_unresolved_findings_are_counted_by_unique_records_too():
    summary = _json("findings_disposition.json")["summary"]
    open_records = {r["record_key"] for r in _json("findings_disposition.json")["dispositions"]
                    if r["resolution_status"].startswith("OPEN") and not r.get("superseded_by")}
    assert summary["unique_records_with_open_findings"] == len(open_records) > 0


# --- legacy label, risk evidence --------------------------------------------------------------------------------------
def test_legacy_verification_label_is_never_read_as_human_source_verification():
    rows = _json("register.json")["records"]
    legacy = [r for r in rows if r["catalog"] == "diagnostic_legacy"]
    assert len(legacy) == 28 and all(r["legacy_verification"] and r["legacy_verification"]["human_source_verified"] is False for r in legacy)
    assert all(r["legacy_verification"] is None for r in rows if r["catalog"] != "diagnostic_legacy")
    assert all(r["readiness"]["source"] == "SOURCE_UNVERIFIED" for r in legacy)
    assert any(r["legacy_verification"]["label"] == "official_documentation_verified" for r in legacy)  # the label is kept, not rewritten


def test_risk_evidence_covers_exactly_the_unresolved_risk_findings_and_stays_unverified():
    evidence = _json("risk_warning_evidence.json")["records"]
    open_keys = {f["record_key"] for f in _json("validator_report.json")["findings"] if f["code"] == "destructive_remediation_risk_unresolved"}
    assert {r["record_key"] for r in evidence} == open_keys and open_keys
    assert all(r["status"] == "RISK_UNVERIFIED_NEEDS_HUMAN_REVIEW" for r in evidence)
    assert all(r["fetched"] or r["conclusion"] == "NOT_RETRIEVED_AUTOMATICALLY" for r in evidence)


# --- Class B review package --------------------------------------------------------------------------------------------
def test_class_b_package_covers_every_class_b_record_with_blank_reviewer_fields_and_current_hashes():
    register = {r["record_key"]: r for r in _json("register.json")["records"] if r["cert_class"] == "B"}
    index = {r["record_key"]: r for r in _json("class_b_human_review_package.json")["records"]}
    text = (CERT / "class_b_human_review_package.md").read_text(encoding="utf-8")
    assert set(index) == set(register) and len(register) == 39
    assert all(index[k]["content_hash"] == register[k]["content_hash"] for k in register)  # not stale
    assert text.count("**14. Reviewer decision (blank") == 39 and text.count("|  |  |  |  |  |") == 39
    for forbidden in ("ACCEPT", "APPROVED by", "Reviewer: "):
        assert forbidden not in text
    for key in register:
        assert f"## {key}" in text


# --- knowledge model analysis ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("value,expected", [("Not stated by the vendor page.", False), ("none", False), ("", False), (None, False), ([], False),
                                            (["Not stated."], False), ("Dropping the slot may force a rebuild.", True), (["step"], True)])
def test_stated_ignores_not_stated_placeholders(value, expected):
    assert akm.stated(value) is expected


def test_knowledge_model_mapping_is_recomputed_and_consistent_with_the_register():
    mapping = _json("knowledge_model_mapping.json")
    fresh = akm.analyze()
    assert mapping["coverage_by_class"] == fresh["coverage_by_class"] and mapping["engineer_use_completeness"] == fresh["engineer_use_completeness"]
    register = _json("register.json")["records"]
    for cls, stats in mapping["coverage_by_class"].items():
        assert stats["records"] == sum(r["cert_class"] == cls for r in register)
    assert {g["missing_field"] for g in mapping["structural_gaps"]} >= {"rollback_steps", "required_permission", "expected_healthy_state", "escalation_conditions"}
    assert set(mapping["sections"]) == {"A_symptom", "B_applicability", "C_diagnosis", "D_investigation", "E_remediation", "F_recovery", "G_provenance"}


def test_complete_for_engineer_use_requires_every_operational_section_not_just_a_source():
    mapping = _json("knowledge_model_mapping.json")
    for rec in mapping["records_b_d_e"]:
        if rec["complete_for_engineer_use"]:
            assert rec["missing_or_not_stated"] == [] and rec["knowledge_entry_contract_blockers"] == []
        else:
            assert rec["missing_or_not_stated"] or rec["knowledge_entry_contract_blockers"]
    assert mapping["engineer_use_completeness"]["D"]["complete_for_engineer_use"] == 0  # no state record has risk + recovery + remediation stated


def test_register_is_still_deterministic_after_the_catalog_applicability_change():
    assert build_register(SERVICES, CERT)["records"] == build_register(SERVICES, CERT)["records"]


# --- end-to-end knowledge contract: catalog record -> engineer-facing KnowledgeEntry contract -------------------------------
def test_catalog_records_map_onto_the_existing_knowledge_entry_contract_without_invented_fields():
    mapping = _json("knowledge_model_mapping.json")
    contract = mapping["knowledge_entry_contract"]
    fresh = akm.analyze()["knowledge_entry_contract"]
    assert contract == fresh  # committed artifact is current
    for cls, stats in contract.items():
        # the only thing the existing contract rejects is the high/critical rule: destructive remediation without validation and rollback
        assert set(stats["blockers"]) <= {": Value error, High/Critical risk knowledge requires validation and rollback steps"}
        assert stats["validates_unchanged"] + sum(stats["blockers"].values()) == stats["records"]


def test_complete_records_validate_and_destructive_records_without_rollback_are_rejected_by_the_contract():
    from backend.api.routers.analyzer.knowledge import KnowledgeProposalContent
    from pydantic import ValidationError
    mapping = _json("knowledge_model_mapping.json")
    blocked = [r for r in mapping["records_b_d_e"] if r["knowledge_entry_contract_blockers"]]
    assert blocked and all(not r["complete_for_engineer_use"] for r in blocked)  # a rejected record is never "complete"
    sample = next(r for r in blocked)
    kinds = {"candidate": akm.__dict__["to_knowledge_content"]}
    cand = {f"candidate:{c['candidate_id']}": c for c in json.loads((SERVICES / "vendor_diagnostic_catalog.json").read_text(encoding="utf-8"))["records"]}
    legacy = {f"diagnostic_legacy:{e['source_family']}:{e['code_type']}:{e['diagnostic_code']}": e
              for e in json.loads((SERVICES / "diagnostic_knowledge_catalog.json").read_text(encoding="utf-8"))["entries"]}
    rec, kind = (cand[sample["record_key"]], "candidate") if sample["record_key"] in cand else (legacy[sample["record_key"]], "legacy")
    content = kinds["candidate"](kind, rec)
    assert content["risk_level"] == "high" and not (content["validation_steps"] and content["rollback_steps"])
    with pytest.raises(ValidationError):
        KnowledgeProposalContent(**content)
    complete = [r for r in mapping["records_b_d_e"] if r["complete_for_engineer_use"]]
    assert complete  # at least some records carry every operational section


def test_catalog_version_scopes_do_not_fit_the_contracts_product_version_field():
    # KnowledgeProposalContent.product_version allows 64 characters; truncating a version scope would change its meaning, so the mapping leaves it empty
    cands = json.loads((SERVICES / "vendor_diagnostic_catalog.json").read_text(encoding="utf-8"))["records"]
    assert sum(len(c["version_scope"]) > 64 for c in cands) > len(cands) // 2
    assert all(akm.to_knowledge_content("candidate", c).get("product_version") is None for c in cands[:5])


# --- artifact validity and referential integrity ---------------------------------------------------------------------------
def test_every_certification_json_parses_and_csv_files_match_their_json_row_counts():
    import csv
    for path in CERT.glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    pairs = {"findings_disposition": lambda d: d["dispositions"], "windows_source_research_ledger": lambda d: d["rows"], "register": lambda d: d["records"]}
    for name, rows in pairs.items():
        data = _json(f"{name}.json")
        with (CERT / f"{name}.csv").open(encoding="utf-8-sig", newline="") as fh:
            assert len(list(csv.DictReader(fh))) == len(rows(data)), name


def test_dispositions_and_ledger_reference_only_existing_register_records():
    keys = {r["record_key"] for r in _json("register.json")["records"]}
    assert {d["record_key"] for d in _json("windows_source_research_ledger.json")["dispositions"]} <= keys
    assert {r["record_key"] for r in _json("findings_disposition.json")["dispositions"] if r["record_key"] != "(register)"} <= keys
    assert {r["record_key"] for r in _json("risk_warning_evidence.json")["records"]} <= keys
