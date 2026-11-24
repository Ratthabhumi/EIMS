"""Unified Knowledge Catalog projection and API contract."""
from collections import Counter

from fastapi import Response

from backend.api.routers.analyzer import unified_catalog as api
from backend.domain.analyzer.services.operational_catalog import load_catalog
from backend.domain.knowledge.service import _catalog
from backend.domain.knowledge.unified_catalog import (
    clear_caches,
    compute_totals,
    identity_evidence,
    list_catalog,
)
import asyncio


def setup_function():
    clear_caches()


def test_identity_claims_machine_verifiable():
    ev = identity_evidence()
    linked = {e["catalog_id"] for e in load_catalog()}
    gov = set(_catalog().keys())
    assert ev["governed_count"] == 911 == len(gov)
    assert ev["unique_catalog_id_count"] == 911
    assert ev["duplicate_catalog_ids"] == []
    assert ev["analyzer_matchable_count"] == 181 == len(linked)
    assert ev["intersection_count"] == 181
    assert ev["only_in_analyzer_loader"] == []
    assert ev["other_governed_count"] == 730
    assert ev["strict_subset"] is True
    assert ev["difference_equals_other"] is True
    assert ev["unique_content_hashes"] == 911
    assert ev["content_hash_collisions"] == 0
    assert ev["cert_class_b_count"] == 39
    assert ev["cert_class_b_in_load_catalog"] == 28
    assert ev["cert_class_b_not_in_load_catalog"] == 11
    assert ev["b_membership_identity"] is True
    assert ev["cert_class_b_in_load_catalog"] + ev["cert_class_b_not_in_load_catalog"] == 39
    # Independent dimensions: Class B is not equal to Analyzer-matchable
    assert ev["cert_class_b_count"] != ev["analyzer_matchable_count"]
    totals = ev["totals"]
    assert totals["governed_records"] == 911
    assert totals["analyzer_matchable"] == 181
    assert totals["other_governed"] == 730
    assert totals["eligible"] == 1
    assert totals["blocked"] == 42
    assert totals["ineligible"] == 868
    assert totals["human_approved"] == 0


def test_list_filters_reconcile_to_rows():
    body = list_catalog(analyzer_availability="matchable", limit=200, offset=0)
    assert body["filtered_count"] == 181
    assert len(body["records"]) == 181
    assert all(r["analyzer_availability"] == "matchable" for r in body["records"])
    assert body["totals"]["analyzer_matchable"] == 181
    assert body["totals"]["governed_records"] == 911

    b_only = list_catalog(cert_class="B", limit=200)
    assert b_only["filtered_count"] == 39
    assert Counter(r["analyzer_availability"] for r in b_only["records"]) == {
        "matchable": 28,
        "not_matchable": 11,
    }

    eligible = list_catalog(eligibility="ELIGIBLE", limit=10)
    assert eligible["filtered_count"] == 1
    assert eligible["records"][0]["catalog_id"] == "cisco_asa:official_message_id:113005"
    assert eligible["records"][0]["analyzer_availability"] == "matchable"
    assert eligible["records"][0]["human_approval"] in (None, "NOT_APPROVED")


def test_api_endpoints():
    body = asyncio.run(api.get_unified_catalog(Response(), limit=5, offset=0))
    assert body["surface"] == "unified_governed_catalog"
    assert body["totals"]["governed_records"] == 911
    assert len(body["records"]) == 5
    ev = asyncio.run(api.get_catalog_identity_evidence())
    assert ev["strict_subset"] is True
    assert compute_totals()["other_governed"] == 730


def test_analyzer_product_family_distribution_is_matchable_subset_only():
    totals = compute_totals()
    families = totals["by_analyzer_source_family"]
    assert sum(families.values()) == totals["analyzer_matchable"] == 181
    assert families.get("windows_event") == 153
    assert families.get("cisco_asa") == 12
    assert families.get("json", 0) == 0  # parser-only family; not Analyzer-matchable rows
    assert totals["governed_records"] == 911
    assert totals["other_governed"] == 730
    # Must not equal governed inventory — product families describe the 181 surface only.
    assert sum(families.values()) != totals["governed_records"]
