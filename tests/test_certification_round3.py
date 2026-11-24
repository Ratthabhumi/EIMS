"""Certification program round 3: evidence binding, class-aware validation and register integrity.

Synthetic catalogs (tmp_path) test rule behaviour; the committed register/evidence files are checked for consistency
against the real catalogs. Passing here is evidence about the tooling only, never a certification of any record.
"""
import csv
import json
from collections import Counter
from pathlib import Path

import pytest

from tests.certification_fixtures import build_fixtures
from tools import run_certification_matching as matching
from tools import run_certification_pg_state as pg_state
from tools.build_certification_register import SERVICES, SOURCE_FILES, apply_readiness, build_register
from tools.build_findings_disposition import build as build_dispositions
from tools.validate_knowledge_certification import (
    reconcile_dispositions, validate_register, validate_register_detailed,
)

CERT = Path(__file__).resolve().parents[1] / "docs" / "acceptance" / "certification"


def _read(name):
    return json.loads((SERVICES / name).read_text(encoding="utf-8"))


def _synthetic(root: Path, *, remediation=None, operational_risk="", version="PostgreSQL 16", extra_record=None):
    root.mkdir(exist_ok=True)
    (root / "operational_event_catalog.json").write_text("[]", encoding="utf-8")
    (root / "diagnostic_knowledge_catalog.json").write_text(json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8")
    record = {"candidate_id": "synthetic:linked", "vendor": "PostgreSQL Global Development Group", "product": "PostgreSQL",
              "version_scope": version, "knowledge_class": "diagnostic_candidate", "parser_mapping": "parser_linked_by_sqlstate",
              "official_sources": [{"url": "https://www.postgresql.org/docs/16/x.html", "scope": "s"}], "limitations": "fixture",
              "likely_causes": [], "remediation": remediation or [], "operational_risk": operational_risk}
    record.update(extra_record or {})
    (root / "vendor_diagnostic_catalog.json").write_text(json.dumps({"schema_version": 1, "records": [record]}), encoding="utf-8")
    (root / "vendor_reference_catalog.json").write_text(json.dumps({"schema_version": 1, "records": []}), encoding="utf-8")
    return root


# --- 1-3: stable keys, hash integrity, completeness ------------------------------------------------------------------
def test_register_is_deterministic_across_builds():
    first, second = build_register(), build_register()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert [r["record_key"] for r in first["records"]] == sorted(r["record_key"] for r in first["records"])


def test_content_hash_changes_with_content_and_not_with_key_order(tmp_path):
    services = _synthetic(tmp_path / "s")
    before = build_register(services)["records"][0]["content_hash"]
    data = json.loads((services / "vendor_diagnostic_catalog.json").read_text(encoding="utf-8"))
    data["records"][0] = dict(reversed(list(data["records"][0].items())))
    (services / "vendor_diagnostic_catalog.json").write_text(json.dumps(data), encoding="utf-8")
    assert build_register(services)["records"][0]["content_hash"] == before  # key order independent
    data["records"][0]["symptom"] = "changed"
    (services / "vendor_diagnostic_catalog.json").write_text(json.dumps(data), encoding="utf-8")
    assert build_register(services)["records"][0]["content_hash"] != before


def test_register_covers_every_source_record_exactly_once():
    register = build_register()
    expected = (len(_read("operational_event_catalog.json")) + len(_read("diagnostic_knowledge_catalog.json")["entries"])
                + len(_read("vendor_diagnostic_catalog.json")["records"]) + len(_read("vendor_reference_catalog.json")["records"]))
    keys = [r["record_key"] for r in register["records"]]
    assert register["record_count"] == len(keys) == len(set(keys)) == expected
    assert set(SOURCE_FILES) == {k.split(":", 1)[0] for k in keys}


# --- 5: class assignment recomputed independently of the generator ----------------------------------------------------
def test_class_counts_match_an_independent_derivation_from_the_catalogs():
    cands = _read("vendor_diagnostic_catalog.json")["records"]
    refs = _read("vendor_reference_catalog.json")["records"]
    state = [c for c in cands if c.get("detection_kind") in ("state_telemetry", "cli_state")]
    linked = [c for c in cands if c not in state and str(c.get("parser_mapping", "")).startswith("parser_linked_")]
    expected = {
        "A": len(_read("operational_event_catalog.json")),
        "B": len(_read("diagnostic_knowledge_catalog.json")["entries"]) + len(linked),
        "C": sum(r.get("parser_mapping") == "parser_mapped" for r in refs),
        "D": len(state),
        "E": len(cands) - len(state) - len(linked),
        "F": sum(r.get("parser_mapping") != "parser_mapped" for r in refs),
    }
    assert build_register()["class_counts"] == expected


# --- 6-8: positive, negative and false-positive evidence through the real parser/Analyzer path ------------------------
@pytest.fixture(scope="module")
def evidence_run():
    hashes = {r["record_key"]: r["content_hash"] for r in build_register()["records"]}
    return matching.run(hashes)


def test_every_positive_fixture_matches_through_the_real_path(evidence_run):
    positives = [c for c in evidence_run["cases"] if c["polarity"] == "positive"]
    assert positives and all(c["passed"] for c in positives)
    assert all(c["actual"] is not None for c in positives)


def test_every_negative_fixture_is_rejected_and_none_is_vacuous(evidence_run):
    negatives = [c for c in evidence_run["cases"] if c["polarity"] == "negative"]
    assert negatives and all(c["passed"] for c in negatives)
    records = {c["record_key"] for c in evidence_run["cases"]}
    for key in records:  # each record has at least one positive AND one negative
        pols = {c["polarity"] for c in evidence_run["cases"] if c["record_key"] == key}
        assert pols == {"positive", "negative"}, key


def test_fixtures_cover_every_mapped_class_b_and_evaluator_record():
    register = build_register()
    fixture_keys = {f["record_key"] for f in build_fixtures()}
    for row in register["records"]:
        mapping = (row.get("parser_or_evaluator") or {}).get("mapping", "")
        if row["cert_class"] == "B" or mapping == "state_telemetry_evaluator":
            assert row["record_key"] in fixture_keys, row["record_key"]


def test_false_positive_rejection_cases():
    by_key = {f["record_key"]: f for f in build_fixtures()}
    asa = by_key["diagnostic_legacy:cisco_asa:official_message_id:106023"]
    assert any("999999" in n["text"] for n in asa["negatives"])  # unknown ID with the same shape
    pan = by_key["diagnostic_legacy:palo_alto:log_category:TRAFFIC"]
    out = matching._run_one(pan, pan["negatives"][0], False)
    assert out["passed"] and out["actual"] == ["palo_alto", "log_category", "THREAT"]  # resolved, but to the right other record
    pgm = by_key["candidate:postgresql:checkpoint:wal-size-triggered-too-frequently"]
    assert all(matching._run_one(pgm, n, False)["passed"] for n in pgm["negatives"])


def test_the_runner_can_fail_a_wrong_expectation_and_a_crash():
    fx = dict(next(f for f in build_fixtures() if f["record_key"].endswith("official_message_id:106023")))
    wrong = dict(fx, expect=["cisco_asa", "official_message_id", "302013"])
    assert matching._run_one(wrong, fx["positive"], True)["passed"] is False
    bad_eval = {"resolver": "evaluator", "function": "evaluate_replication_slot"}
    assert matching._run_one(bad_eval, {"row": {"wal_status": "lost"}, "expect": {"state": "reserved"}}, True)["passed"] is False


# --- 9-11: version scope, source traceability, destructive remediation -----------------------------------------------
def test_version_scope_missing_broad_and_derived_only_are_flagged(tmp_path):
    cases = (("", {"official_sources": []}, "version_scope_missing"),
             ("", {}, "version_scope_not_explicit"),  # only the cited page's scope sentence exists
             ("all versions", {}, "version_scope_broad"))
    for i, (version, extra, code) in enumerate(cases):
        services = _synthetic(tmp_path / f"s{i}", version=version, extra_record=extra)
        register = build_register(services)
        assert code in {f["code"] for f in validate_register(register, services)}, code
    explicit = _synthetic(tmp_path / "ok", version="PostgreSQL 16 only")
    assert not {f["code"] for f in validate_register(build_register(explicit), explicit)} & {
        "version_scope_missing", "version_scope_broad", "version_scope_not_explicit"}


def test_version_scope_is_present_for_every_non_windows_record_in_the_real_catalogs():
    register = build_register()
    findings = validate_register(register)
    missing = {f["record_key"] for f in findings if f["code"] == "version_scope_missing"}
    assert missing and all(k.startswith("operational:") for k in missing)  # the open ones are exactly the Windows records
    derived = {f["record_key"] for f in findings if f["code"] == "version_scope_not_explicit"}
    assert derived and all(k.startswith("operational:") for k in derived) and not derived & missing  # Windows records that only have a page-scope sentence


def test_every_source_url_is_https_and_records_without_a_source_are_exactly_the_open_windows_ones():
    register = build_register()
    no_source = {r["record_key"] for r in register["records"] if not r["source_urls"]}
    assert no_source and all(k.startswith("operational:") for k in no_source)
    assert all(u.startswith("https://") for r in register["records"] for u in r["source_urls"])
    assert no_source == {f["record_key"] for f in validate_register(register) if f["code"] == "source_url_missing"}


@pytest.mark.parametrize("risk,expected", [("", "destructive_remediation_risk_missing"),
                                            ("Not stated by the vendor.", "destructive_remediation_risk_unresolved"),
                                            ("Dropping the slot may force a replica rebuild. Rollback: recreate the replica.", None)])
def test_destructive_remediation_requires_a_stated_risk(tmp_path, risk, expected):
    services = _synthetic(tmp_path / "s", remediation=["Drop the replication slot."], operational_risk=risk)
    codes = {f["code"] for f in validate_register(build_register(services), services)}
    assert (expected in codes) if expected else not (codes & {"destructive_remediation_risk_missing", "destructive_remediation_risk_unresolved"})


@pytest.mark.parametrize("verb", ["rebuild", "restart", "reboot", "drop", "delete"])
def test_register_and_validator_share_one_destructive_verb_list(verb):
    from tools.build_certification_register import DESTRUCTIVE_RE
    assert DESTRUCTIVE_RE.search(f"you may {verb} the node")


# --- 12-13: human review fields blank, AI/automation cannot approve ----------------------------------------------------
def test_committed_register_has_blank_human_review_fields_and_no_approval_states():
    register = json.loads((CERT / "register.json").read_text(encoding="utf-8"))
    for row in register["records"]:
        assert not any(row["review"].values())
        ready = row["readiness"]
        assert ready["source"] == "SOURCE_UNVERIFIED" and ready["independent_review"] == "INDEPENDENT_REVIEW_PENDING"
        assert ready["approval"] == "NOT_APPROVED" and "lifecycle_status" not in row
    text = (CERT / "register.json").read_text(encoding="utf-8")
    for forbidden in ('"SOURCE_VERIFIED"', '"INDEPENDENTLY_REVIEWED"', '"APPROVED"'):
        assert forbidden not in text


def test_complete_automated_evidence_still_never_yields_source_verified_review_or_approval():
    register = build_register()
    findings, checks = validate_register_detailed(register)
    apply_readiness(register, findings, checks)
    technically = [r for r in register["records"] if r["readiness"]["technical"] == "TECHNICALLY_VALIDATED"]
    assert technically  # automation can validate technically ...
    assert all(r["readiness"]["source"] == "SOURCE_UNVERIFIED" and r["readiness"]["approval"] == "NOT_APPROVED" for r in technically)  # ... and nothing more


@pytest.mark.parametrize("kind", ["ai", "automation", "human"])
def test_a_filled_review_block_in_the_generated_register_is_an_error(tmp_path, kind):
    services = _synthetic(tmp_path / "s")
    register = build_register(services)
    register["records"][0]["review"] = {"reviewer_id": "x", "reviewer_kind": kind, "decision": "approved", "decided_at": "2026-01-01", "rationale": "r"}
    assert "review_field_not_blank" in {f["code"] for f in validate_register(register, services)}


# --- 14: content change invalidates prior evidence --------------------------------------------------------------------
def test_content_change_marks_bound_evidence_stale_and_reopens_the_coverage_finding(tmp_path):
    services = _synthetic(tmp_path / "s")
    evidence_dir = tmp_path / "ev"
    evidence_dir.mkdir()
    key = "candidate:synthetic:linked"
    h = build_register(services)["records"][0]["content_hash"]
    cases = [{"record_key": key, "kind": "analyzer_path", "polarity": p, "passed": True} for p in ("positive", "negative")]
    (evidence_dir / "technical_evidence_x.json").write_text(json.dumps({"generated_at": "t", "git_head": "g", "record_hashes": {key: h}, "cases": cases}), encoding="utf-8")
    fresh = build_register(services, evidence_dir)
    codes = {f["code"] for f in validate_register(fresh, services)}
    assert not codes & {"parser_match_coverage_missing", "parser_non_match_coverage_missing", "evidence_stale"}
    data = json.loads((services / "vendor_diagnostic_catalog.json").read_text(encoding="utf-8"))
    data["records"][0]["symptom"] = "edited after the evidence run"
    (services / "vendor_diagnostic_catalog.json").write_text(json.dumps(data), encoding="utf-8")
    stale = build_register(services, evidence_dir)
    assert all(e["current"] is False for e in stale["records"][0]["test_evidence"])
    codes = {f["code"] for f in validate_register(stale, services)}
    assert {"evidence_stale", "parser_match_coverage_missing", "parser_non_match_coverage_missing"} <= codes


def test_a_failing_evidence_case_is_an_error(tmp_path):
    services = _synthetic(tmp_path / "s")
    evidence_dir = tmp_path / "ev"
    evidence_dir.mkdir()
    key = "candidate:synthetic:linked"
    h = build_register(services)["records"][0]["content_hash"]
    cases = [{"record_key": key, "kind": "analyzer_path", "polarity": "positive", "passed": False}]
    (evidence_dir / "technical_evidence_x.json").write_text(json.dumps({"record_hashes": {key: h}, "cases": cases}), encoding="utf-8")
    assert "evidence_failed" in {f["code"] for f in validate_register(build_register(services, evidence_dir), services)}


# --- 15: NOT_APPLICABLE / BLOCKED handling and disposition reconciliation -----------------------------------------------
def test_every_actionable_finding_has_exactly_one_disposition_and_none_is_orphaned():
    register = json.loads((CERT / "register.json").read_text(encoding="utf-8"))
    rows = json.loads((CERT / "findings_disposition.json").read_text(encoding="utf-8"))["dispositions"]
    findings = validate_register(register)
    assert reconcile_dispositions(findings, rows) == []


def test_reconcile_flags_missing_and_duplicate_dispositions():
    findings = [{"code": "version_scope_missing", "severity": "warning", "record_key": "k", "message": "m"}]
    assert {p["code"] for p in reconcile_dispositions(findings, [])} == {"finding_without_disposition"}
    row = {"record_key": "k", "finding_type": "version_scope_missing", "resolution_status": "OPEN_BLOCKED"}
    assert {p["code"] for p in reconcile_dispositions(findings, [row, dict(row)])} == {"finding_with_duplicate_disposition"}
    assert {p["code"] for p in reconcile_dispositions([], [row])} == {"disposition_without_finding"}


def test_disposition_vocabulary_and_blocked_rows_state_a_blocker():
    out = json.loads((CERT / "findings_disposition.json").read_text(encoding="utf-8"))
    allowed = {"FIX_REQUIRED", "EVIDENCE_REQUIRED", "ACCEPTED_LIMITATION", "NOT_APPLICABLE", "BLOCKED", "NEEDS_HUMAN_REVIEW"}
    rows = out["dispositions"]
    assert {r["disposition"] for r in rows} <= allowed
    assert all(r["remaining_blocker"] for r in rows if r["disposition"] in ("BLOCKED", "NEEDS_HUMAN_REVIEW"))
    baseline = [r for r in rows if r["origin"] == "round2_baseline"]
    assert len(baseline) == out["summary"]["baseline_findings"] == json.loads((CERT / "baseline_round2_findings.json").read_text(encoding="utf-8"))["finding_count"]


def test_resolved_by_evidence_rows_point_at_real_current_evidence():
    register = {r["record_key"]: r for r in json.loads((CERT / "register.json").read_text(encoding="utf-8"))["records"]}
    for row in json.loads((CERT / "findings_disposition.json").read_text(encoding="utf-8"))["dispositions"]:
        if row["resolution_status"] != "RESOLVED_BY_EVIDENCE":
            continue
        rec = register[row["record_key"]]
        if row.get("resolved_by") == "official_applicability_statement":
            assert rec["version_scope_basis"] == "explicit_from_official_statement", row["record_key"]
        else:
            evidence = rec["test_evidence"]
            assert evidence and all(e["current"] and e["all_passed"] for e in evidence), row["record_key"]


def test_stale_disposition_for_a_class_b_record_is_not_silently_accepted():
    # a baseline finding whose evidence disappeared must be re-opened by the builder, not reported as resolved
    register = {"records": [{"record_key": "k", "cert_class": "B", "test_evidence": [], "content_hash": "h" * 64}]}
    baseline = [{"code": "parser_match_coverage_missing", "severity": "warning", "record_key": "k", "message": "m"}]
    current = [{"code": "parser_match_coverage_missing", "severity": "warning", "record_key": "k", "message": "m"}]
    rows = build_dispositions(baseline, current, register, {"k": ("candidate", {})})
    assert rows[0]["resolution_status"] != "RESOLVED_BY_EVIDENCE" and rows[0]["disposition"] == "BLOCKED"


# --- 16: JSON / CSV consistency and committed-artifact freshness -------------------------------------------------------
def test_register_csv_matches_json_row_for_row():
    register = json.loads((CERT / "register.json").read_text(encoding="utf-8"))
    with (CERT / "register.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == register["record_count"] == len(register["records"])
    assert [r["record_key"] for r in rows] == [r["record_key"] for r in register["records"]]
    assert [r["content_hash"] for r in rows] == [r["content_hash"] for r in register["records"]]
    assert all(json.loads(r["readiness"]) == j["readiness"] for r, j in zip(rows, register["records"]))


def test_committed_register_is_the_current_build_of_the_catalogs_and_evidence():
    committed = json.loads((CERT / "register.json").read_text(encoding="utf-8"))
    fresh = build_register(SERVICES, CERT)
    assert [(r["record_key"], r["content_hash"]) for r in committed["records"]] == [(r["record_key"], r["content_hash"]) for r in fresh["records"]]
    for old, new in zip(committed["records"], fresh["records"]):
        assert old["test_evidence"] == new["test_evidence"], old["record_key"]
    assert all(e["current"] for r in committed["records"] for e in r["test_evidence"])  # no stale evidence in the committed register


# --- class C: success-status references are intentionally not surfaced -----------------------------------------------
@pytest.mark.parametrize("key", ["reference:postgresql:sqlstate:00000", "reference:systemd:exit_status:0"])
def test_success_status_references_are_expected_non_emission_not_mismatch(key):
    register = build_register()
    findings, checks = validate_register_detailed(register)
    assert "reference_parser_expected_non_emission" in checks[key]
    assert not [f for f in findings if f["record_key"] == key and f["code"].startswith("reference_parser_mismatch")]


def test_every_other_parser_mapped_reference_resolves_through_the_parser():
    register = build_register()
    findings, checks = validate_register_detailed(register)
    mapped = [r["record_key"] for r in register["records"] if r["cert_class"] == "C"]
    assert not [f for f in findings if f["code"] in ("reference_parser_mismatch", "reference_parser_check_error")]
    positives = sum("reference_parser_positive" in checks[k] for k in mapped)
    non_emission = sum("reference_parser_expected_non_emission" in checks[k] for k in mapped)
    assert positives + non_emission == len(mapped) and non_emission == 2


# --- class D: real-source evidence, guards ---------------------------------------------------------------------------
def test_state_candidates_need_real_source_evidence_not_authored_rows():
    register = {r["record_key"]: r for r in json.loads((CERT / "register.json").read_text(encoding="utf-8"))["records"]}
    slot = register[pg_state.SLOT_KEY]
    kinds = {e["kind"] for e in slot["test_evidence"]}
    assert {"evaluator_real_state_positive", "evaluator_real_state_negative", "evaluator_synthetic_positive", "evaluator_synthetic_negative"} <= kinds
    ha = register["candidate:fortinet-fortios:ha:failover-reason-from-ha-status"]
    assert {e["kind"] for e in ha["test_evidence"]} <= {"evaluator_synthetic_positive", "evaluator_synthetic_negative"}
    assert ha["readiness"]["technical"] == "TECHNICAL_UNVALIDATED" and ha["readiness"]["blocked"]  # authored strings are not enough


def test_real_pg_evidence_file_records_actual_rows_from_a_postgresql_16_server():
    data = json.loads((CERT / "technical_evidence_pg_state.json").read_text(encoding="utf-8"))
    assert data["environment"]["server_version"].startswith("16.")
    cases = data["cases"]
    assert cases and all(c["kind"] == "evaluator_real_state" and c["passed"] and c["actual_row"] for c in cases)
    statuses = {c["actual_row"].get("wal_status") for c in cases if c["record_key"] == pg_state.SLOT_KEY}
    assert {"reserved", "extended", "lost"} <= statuses  # observed on the server, not authored
    assert "password" not in json.dumps(data).lower()


@pytest.mark.parametrize("dsn", ["postgresql://u:p@db.example.com:5432/eims_cert_state", "postgresql://u:p@127.0.0.1:5432/eims_registry",
                                 "postgresql://u:p@127.0.0.1:5432/postgres"])
def test_pg_runner_refuses_non_disposable_targets(dsn):
    with pytest.raises(SystemExit):
        pg_state._guard(dsn, "primary")


def test_unmapped_state_candidate_stays_blocked_with_no_invented_evidence():
    register = {r["record_key"]: r for r in json.loads((CERT / "register.json").read_text(encoding="utf-8"))["records"]}
    row = register["candidate:fortinet-fortios:ha:unexpected-failover-causes"]
    assert row["test_evidence"] == [] and "evaluator_not_mapped" in row["readiness"]["blockers"]


def test_evidence_counts_summary_matches_the_register():
    evidence = json.loads((CERT / "technical_evidence_matching.json").read_text(encoding="utf-8"))
    register = json.loads((CERT / "register.json").read_text(encoding="utf-8"))["records"]
    keys = {c["record_key"] for c in evidence["cases"]}
    with_evidence = {r["record_key"] for r in register if any(e["evidence_file"] == "technical_evidence_matching.json" for e in r["test_evidence"])}
    assert keys == with_evidence and Counter(c["passed"] for c in evidence["cases"]) == Counter({True: len(evidence["cases"])})


def test_source_blockers_and_technical_blockers_are_reported_separately():
    register = {r["record_key"]: r for r in json.loads((CERT / "register.json").read_text(encoding="utf-8"))["records"]}
    product_level = register["operational:windows_event:official_event_id:4199"]
    assert product_level["readiness"]["technical"] == "TECHNICALLY_VALIDATED" and product_level["readiness"]["blockers"] == []
    assert product_level["readiness"]["source_blockers"] == ["version_scope_product_level_only"] and product_level["readiness"]["blocked"]
    explicit = register["operational:windows_event:official_event_id:4624"]
    assert explicit["version_scope_basis"] == "explicit_from_official_statement" and explicit["readiness"]["source_blockers"] == []
    no_source = register["operational:windows_event:official_event_id:1054"]
    assert set(no_source["readiness"]["source_blockers"]) == {"source_url_missing", "version_scope_missing"}
    assert all(r["readiness"]["source"] == "SOURCE_UNVERIFIED" for r in register.values())
