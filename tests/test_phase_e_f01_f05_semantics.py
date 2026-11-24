"""Focused Phase E checks for F01/F02/F04/F05. No held-out matcher tuning."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.domain.analyzer.services.operational_catalog import get_catalog_entry
from backend.domain.analyzer.services.parser import parse_event_metadata
from backend.domain.analyzer.services.vendor_parsers import resolve_vendor_diagnostic
from evaluation.analyzer.runner import annotation_digest, load_manifest, predict
from evaluation.analyzer.scoring import score

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "evaluation/analyzer/gold"
CASES = GOLD / "cases"


def _read(case_id: str) -> str:
    return (CASES / case_id / "input.txt").read_text(encoding="utf-8")


def test_f01_cross_vendor_relationship_is_dedicated_and_family_scoped():
    cat = json.loads((ROOT / "backend/domain/analyzer/services/diagnostic_knowledge_catalog.json").read_text(encoding="utf-8"))
    cbt = [e for e in cat["entries"] if e.get("diagnostic_code") == "VMWARE-CBT-DELETE-FAILED"]
    assert len(cbt) == 2
    families = {e["source_family"] for e in cbt}
    assert families == {"veeam_vbr", "vmware"}
    for e in cbt:
        rel = e["cross_vendor_relationship"]
        assert rel["kind"] == "eims_shared_diagnostic_concept"
        assert rel["lookup"] == "source_family_scoped_only"
        assert rel["not_vendor_native_id"] is True
        assert rel["does_not_imply_identical_root_cause"] is True
        assert e["related_codes"] == []
        peer = rel["peer"]
        assert peer["diagnostic_code"] == "VMWARE-CBT-DELETE-FAILED"
        assert peer["source_family"] != e["source_family"]
        assert peer["source_family"] in families
        # Contextual KB enrichment preserved
        assert any("322285" in r.get("url", "") for r in e["official_references"])
        assert e["verification_status"] == "code_supported_with_contextual_reference"

    veeam = get_catalog_entry("VMWARE-CBT-DELETE-FAILED", "veeam_vbr", "eims_diagnostic")
    vmware = get_catalog_entry("VMWARE-CBT-DELETE-FAILED", "vmware", "eims_diagnostic")
    assert veeam and vmware
    assert veeam["source_family"] == "veeam_vbr"
    assert vmware["source_family"] == "vmware"
    # Relationship metadata must not collapse the two identities.
    assert veeam["catalog_id"] != vmware["catalog_id"]
    assert get_catalog_entry("VMWARE-CBT-DELETE-FAILED", "fortinet", "eims_diagnostic") is None


def test_f01_positive_and_negative_signature_resolution():
    veeam = _read("veeam_tracker")
    esxi = _read("esxi_tracker")
    assert resolve_vendor_diagnostic(veeam, "veeam_vbr") == "VMWARE-CBT-DELETE-FAILED"
    assert resolve_vendor_diagnostic(esxi, "vmware") == "VMWARE-CBT-DELETE-FAILED"
    # Cross-family text does not change the requirement that callers pass the correct family.
    assert resolve_vendor_diagnostic(veeam, "vmware") == "VMWARE-CBT-DELETE-FAILED"  # same signature text
    # Unrelated signatures stay unresolved.
    assert resolve_vendor_diagnostic("Info Job Type: Backup completed successfully", "veeam_vbr") == ""
    assert resolve_vendor_diagnostic("Snapshot created successfully", "vmware") == ""
    # Catalog relationship object itself is not a matching input.
    rel = get_catalog_entry("VMWARE-CBT-DELETE-FAILED", "veeam_vbr", "eims_diagnostic")["cross_vendor_relationship"]
    assert resolve_vendor_diagnostic(json.dumps(rel), "veeam_vbr") == ""


def test_f02_fortinet_layers_separated_without_parser_change():
    accept = parse_event_metadata(_read("fort_accept"), "input.txt")
    deny = parse_event_metadata(_read("fort_deny_reserved"), "input.txt")
    assert accept.eventId == deny.eventId == "0000000013"
    assert accept.diagnosticCode == deny.diagnosticCode == "traffic/forward"
    assert accept.attributes["action"] == "accept"
    assert deny.attributes["action"] == "deny"
    # Missing / empty action
    bare = parse_event_metadata(
        'date=2026-10-20 time=09:30:00 logid="0000000013" type="traffic" subtype="forward" level="notice" srcip=1.1.1.1\n',
        "input.txt",
    )
    assert bare.eventId == "0000000013"
    assert bare.diagnosticCode == "traffic/forward"
    assert not (bare.attributes or {}).get("action")


def test_f02_f04_f05_manifest_schema_lock_and_predict_layers():
    doc, payloads = load_manifest(GOLD / "manifest.v1.json")
    by_id = {c["case_id"]: c for c in doc["cases"]}

    win = by_id["win_boot"]["truth"]
    assert win["informational_only"] is True
    assert win["event_identity"] == "6005"
    assert win["diagnostic_evidence"] == []
    assert win["identity_evidence"][0]["line"] == 3

    accept = by_id["fort_accept"]["truth"]
    assert accept["event_identity"] == "0000000013"
    assert accept["diagnostic_category"] == "traffic/forward"
    assert accept["outcome"] == "accept"
    assert accept["diagnostic_code"] == "traffic/forward"
    assert accept["diagnostic_evidence"] == []

    deny = by_id["fort_deny_reserved"]
    assert deny["split"] == "heldout"
    t = deny["truth"]
    assert t["outcome"] == "deny"
    assert t["diagnostic_evidence"][0]["line"] == 1
    assert t["evidence"][0]["line"] == 1

    lock = json.loads((GOLD / "heldout.v1.lock.json").read_text(encoding="utf-8"))
    for c in doc["cases"]:
        if c["split"] == "heldout":
            assert lock[c["case_id"]] == annotation_digest(c)

    # Development fixtures only for predict/score behavior (held-out not used to tune).
    cases = [by_id[cid] for cid in ("win_boot", "fort_accept", "fort_config")]
    predictions = [predict(c, payloads[c["case_id"]], "rule_only") for c in cases]
    metrics, per_case = score(cases, predictions)

    by_pred = {p["case_id"]: p for p in predictions}
    assert by_pred["fort_accept"]["event_identity"] == "0000000013"
    assert by_pred["fort_accept"]["diagnostic_category"] == "traffic/forward"
    assert by_pred["fort_accept"]["outcome"] == "accept"
    assert by_pred["fort_accept"]["diagnostic_code"] == "traffic/forward"
    assert by_pred["win_boot"]["event_identity"] == "6005"
    assert by_pred["win_boot"]["diagnostic_evidence"] == []
    assert by_pred["win_boot"]["identity_evidence"][0]["line"] == 3

    assert metrics["event_identity"]["accuracy"]["value"] == 1.0
    assert metrics["diagnostic_category"]["accuracy"]["value"] == 1.0
    assert metrics["outcome"]["accuracy"]["numerator"] >= 1
    # Informational cases must not inflate failure FP merely by lacking diagnostic evidence.
    assert metrics["false_positive_failure_rate"]["numerator"] == 0
    assert metrics["provenance"]["identity_citation_coverage"]["value"] == 1.0


def test_f02_outcome_scoring_distinguishes_accept_and_deny_on_dev_fixture():
    """Synthetic scoring pairs — development fixtures only, not held-out tuning."""
    cases = [
        {"case_id": "a", "truth": {"source_family": "fortinet", "diagnostic_code": "traffic/forward",
                                   "event_identity": "0000000013", "diagnostic_category": "traffic/forward",
                                   "outcome": "accept", "abstain_expected": False, "evidence": [],
                                   "correlation_pairs": [], "applicable_kb": [], "first_failure": None,
                                   "terminal_failure": None, "identity_evidence": [], "diagnostic_evidence": []}},
        {"case_id": "d", "truth": {"source_family": "fortinet", "diagnostic_code": "traffic/forward",
                                   "event_identity": "0000000013", "diagnostic_category": "traffic/forward",
                                   "outcome": "deny", "abstain_expected": False, "evidence": [],
                                   "correlation_pairs": [], "applicable_kb": [], "first_failure": None,
                                   "terminal_failure": None, "identity_evidence": [], "diagnostic_evidence": []}},
    ]
    predictions = [
        {"case_id": "a", "status": "OK", "source_family": "fortinet", "diagnostic_code": "traffic/forward",
         "event_identity": "0000000013", "diagnostic_category": "traffic/forward", "outcome": "accept",
         "identity_abstained": False, "first_failure": [], "terminal_failure": [], "evidence": [],
         "identity_evidence": [], "diagnostic_evidence": [], "correlation_pairs": []},
        {"case_id": "d", "status": "OK", "source_family": "fortinet", "diagnostic_code": "traffic/forward",
         "event_identity": "0000000013", "diagnostic_category": "traffic/forward", "outcome": "deny",
         "identity_abstained": False, "first_failure": [], "terminal_failure": [], "evidence": [],
         "identity_evidence": [], "diagnostic_evidence": [], "correlation_pairs": []},
    ]
    metrics, _ = score(cases, predictions)
    assert metrics["event_identity"]["accuracy"]["value"] == 1.0
    assert metrics["diagnostic_category"]["accuracy"]["value"] == 1.0
    assert metrics["outcome"]["accuracy"]["value"] == 1.0
    # Conflicting outcome is scored as wrong on that layer only.
    predictions[1]["outcome"] = "accept"
    metrics_bad, _ = score(cases, predictions)
    assert metrics_bad["outcome"]["accuracy"]["value"] == 0.5
    assert metrics_bad["event_identity"]["accuracy"]["value"] == 1.0


def test_f05_6005_operational_catalog_informational():
    ocat = json.loads((ROOT / "backend/domain/analyzer/services/operational_event_catalog.json").read_text(encoding="utf-8"))
    entry = next(e for e in ocat if str(e.get("event_id")) == "6005")
    blob = (entry.get("description", "") + " " + entry.get("operator_context", "")).upper()
    assert "INFORMATIONAL" in blob or "NOT A STANDALONE ROOT-CAUSE" in blob
    meta = parse_event_metadata(_read("win_boot"), "input.txt")
    assert meta.eventId == "6005"
    assert meta.diagnosticCode == ""
    assert meta.isCritical is False
    entry = get_catalog_entry("6005", "windows_event")
    assert entry is not None
    assert entry.get("knowledge_class") == "operational_context"
