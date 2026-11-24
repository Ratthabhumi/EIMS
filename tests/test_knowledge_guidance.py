"""Structured diagnostic_guidance: validation, baseline preservation, and the .NET Runtime 1026 correction."""
from tests import catalog_expectations as X
import copy
import json
from pathlib import Path

import pytest

from backend.domain.analyzer.services.operational_catalog import (
    CATALOG_PATH, VENDOR_CATALOG_PATH, get_catalog_entry, load_catalog,
)


def _write(tmp_path, windows, vendor):
    w, v = tmp_path / "w.json", tmp_path / "v.json"
    w.write_text(json.dumps(windows), encoding="utf-8")
    v.write_text(json.dumps(vendor), encoding="utf-8")
    return w, v


def _base():
    return (json.loads(CATALOG_PATH.read_text(encoding="utf-8")),
            json.loads(VENDOR_CATALOG_PATH.read_text(encoding="utf-8")))


BASELINE = Path(__file__).with_name("data") / "knowledge_baseline_ids_20261119.json"


def test_baseline_163_stable_ids_preserved_and_classes_unchanged():
    baseline = set(json.loads(BASELINE.read_text(encoding="utf-8"))["ids"])
    catalog = load_catalog()
    current = {e["catalog_id"] for e in catalog}
    assert len(baseline) == 163
    assert baseline <= current, f"baseline IDs lost: {sorted(baseline - current)}"
    assert len(current) == len(catalog)
    by_id = {e["catalog_id"]: e for e in catalog}
    assert sum(by_id[i]["knowledge_class"] == "diagnostic_candidate" for i in baseline) == 22
    assert all(e["lifecycle_status"] in ("operational_context", "candidate") for e in catalog)


def test_migrated_records_use_qualified_ids_only_where_the_plain_id_is_taken():
    baseline = set(json.loads(BASELINE.read_text(encoding="utf-8"))["ids"])
    new = {e["catalog_id"] for e in load_catalog()} - baseline
    migrated = {i for i in new if i.startswith("windows_event")}
    assert len(migrated) == 12  # the 12 records migrated from event_knowledge.json (Windows set is otherwise unchanged)
    assert new - migrated <= {f"{e['source_family']}:{e['code_type']}:{e['diagnostic_code']}" for e in X.VENDOR}
    assert {f"cisco_asa:official_message_id:{c}" for c in ("411001", "411002", "105005", "106001", "106015", "106100")} <= new
    assert {"windows_event:official_event_id:5011:Microsoft-Windows-WAS",
            "windows_event:official_event_id:1001:Microsoft-Windows-WER-SystemErrorReporting"} <= new


def test_guidance_never_changes_lifecycle_or_identity():
    entry = get_catalog_entry("106024", "cisco_asa", "official_message_id")
    assert entry["lifecycle_status"] == "candidate"
    assert entry["catalog_id"] == "cisco_asa:official_message_id:106024"
    guidance = entry["diagnostic_guidance"]
    assert guidance["evidence_basis"] and guidance["rollback"] and guidance["verification_criteria"]


@pytest.mark.parametrize("bad", [
    {"expected_findings": ["x"]},                                    # evidence_basis missing
    {"evidence_basis": "s", "unknown_key": "x"},                     # unknown key
    {"evidence_basis": "s", "expected_findings": "not a list"},
    {"evidence_basis": "s", "safe_remediation": [""]},
    {"evidence_basis": "s", "risk": 5},
    "string",
])
def test_invalid_guidance_fails_closed(tmp_path, bad):
    windows, vendor = _base()
    vendor = copy.deepcopy(vendor)
    vendor["entries"][0]["diagnostic_guidance"] = bad
    w, v = _write(tmp_path, windows, vendor)
    with pytest.raises(ValueError):
        load_catalog(w, v)


def test_windows_reference_must_be_https(tmp_path):
    windows, vendor = _base()
    windows = copy.deepcopy(windows)
    windows[0]["official_references"] = [{"title": "t", "url": "http://x", "scope": "s"}]
    w, v = _write(tmp_path, windows, vendor)
    with pytest.raises(ValueError):
        load_catalog(w, v)


def test_net_runtime_1026_is_a_symptom_not_a_root_cause():
    entry = get_catalog_entry("1026")
    assert entry["provider"] == ".NET Runtime"
    assert entry["lifecycle_status"] == "operational_context"   # not promoted by this correction
    assert "symptom" in entry["operator_context"].lower()
    for speculative in ("csp issues", "hard-coded"):
        assert speculative not in entry["operator_context"].lower()
    assert "1000" in entry["related_events"] and "1001" in entry["related_events"]
    assert "no official microsoft event-definition page" in entry["diagnostic_guidance"]["evidence_basis"].lower()
