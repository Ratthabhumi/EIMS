"""Every record that lacked an official Windows reference has an explicit, evidence-consistent disposition."""
import json
from collections import Counter
from pathlib import Path

import pytest

from tests.catalog_expectations import WINDOWS

DISP = json.loads((Path(__file__).resolve().parents[1] / "backend/domain/analyzer/services/windows_reference_dispositions.json").read_text(encoding="utf-8"))
ROWS = DISP["records"]
ALLOWED = {"EXACT_MATCH", "INDIRECT_AUTHORITATIVE_REFERENCE", "NO_AUTHORITATIVE_REFERENCE_FOUND", "AMBIGUOUS", "NEEDS_HUMAN_REVIEW"}
CAT = {(e["event_id"], e["provider"]): e for e in WINDOWS}


def test_all_54_records_have_exactly_one_disposition_and_pending_review():
    keys = [(r["event_id"], r["provider"]) for r in ROWS]
    assert len(ROWS) == 54 and len(set(keys)) == 54 and set(keys) <= set(CAT)
    assert {r["disposition"] for r in ROWS} <= ALLOWED
    assert all(r["review_status"] == "PENDING_HUMAN_REVIEW" for r in ROWS)


def test_dispositions_agree_with_the_catalog_references():
    for r in ROWS:
        rec = CAT[(r["event_id"], r["provider"])]
        refs = [x["url"] for x in rec.get("official_references", [])]
        if r["disposition"] == "EXACT_MATCH":
            assert refs and {x["url"] for x in r["references"]} == set(refs)
        else:
            assert not refs, (r["event_id"], r["provider"])  # indirect/none/review must not appear as official references
        if r["disposition"] in ("NO_AUTHORITATIVE_REFERENCE_FOUND", "NEEDS_HUMAN_REVIEW"):
            assert r["references"] == []
        if r["disposition"] == "INDIRECT_AUTHORITATIVE_REFERENCE":
            assert r["references"] and all(x["url"].startswith("https://learn.microsoft.com/") for x in r["references"])
            assert "Not an exact" in r["note"]


def test_counts_reconcile_with_the_catalog():
    c = Counter(r["disposition"] for r in ROWS)
    assert c["EXACT_MATCH"] == 12 and c["INDIRECT_AUTHORITATIVE_REFERENCE"] == 8
    assert c["NO_AUTHORITATIVE_REFERENCE_FOUND"] == 32 and c["NEEDS_HUMAN_REVIEW"] == 2 and c["AMBIGUOUS"] == 0
    assert sum(bool(e.get("official_references")) for e in WINDOWS) == 99 + c["EXACT_MATCH"]
    assert sum(not e.get("official_references") for e in WINDOWS) == 54 - c["EXACT_MATCH"]


@pytest.mark.parametrize("eid,provider,fragment", [("4199", "TCP/IP", "address conflict"), ("51", "Disk", "warning")])
def test_wording_conflicts_found_in_this_tranche_are_corrected_not_just_referenced(eid, provider, fragment):
    rec = CAT[(eid, provider)]
    assert fragment in (rec["description"] + rec["title"] + rec["severity"]).lower()


def test_exact_references_are_sample_scoped_where_the_page_is_one_scenario():
    for key in (("7023", "Service Control Manager"), ("7031", "Service Control Manager"), ("7034", "Service Control Manager")):
        scopes = " ".join(x["scope"] for x in CAT[key]["official_references"])
        assert "not a general definition" in scopes and scopes.rstrip().endswith("human re-read pending.")
