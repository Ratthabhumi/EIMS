import json
from tests import catalog_expectations as X
import pytest

from backend.domain.analyzer.services import vendor_reference as vr
from backend.domain.analyzer.services.operational_catalog import OPERATIONAL_CATALOG

REC = vr.REFERENCE_CATALOG


def test_inventory_is_separate_from_diagnostic_catalog():
    assert len(OPERATIONAL_CATALOG) == X.TOTAL
    ids = {e["catalog_id"] for e in OPERATIONAL_CATALOG}
    assert not ids & {r["reference_id"] for r in REC}
    assert all(r["knowledge_class"] == "reference_knowledge" for r in REC)


def test_ids_unique_and_stable_shape():
    ids = [r["reference_id"] for r in REC]
    assert len(ids) == len(set(ids)) and len(ids) >= 300
    assert all(r["reference_id"].endswith(":" + r["code"]) and r["reference_id"].count(":") >= 2 for r in REC)


def test_no_promotion_and_no_remediation():
    s = vr.reference_inventory_summary()
    assert s["source_verified"] == s["validated"] == s["approved"] == 0
    assert {r["lifecycle_status"] for r in REC} == {"candidate"}
    assert {r["evidence_maturity"] for r in REC} <= vr.ALLOWED_MATURITY
    assert all(r["remediation"] is None and r["limitations"].startswith("Definition only") for r in REC)


def test_every_record_has_https_source_and_missing_parser_stated():
    assert all(r["source"]["url"].startswith("https://") and r["source"]["method"] for r in REC)
    mapped = {r["product"] for r in REC if r["parser_mapping"] == "parser_mapped"}
    assert mapped == {"PostgreSQL", "systemd"}  # only these have a real parser path (see test_reference_parser_mapping)
    assert all(r.get("parser_mapping_note") for r in REC if r["parser_mapping"] == "parser_mapped")
    assert {r["parser_mapping"] for r in REC if r["product"] not in mapped} == {"missing_parser"}


@pytest.mark.parametrize("code,name", [("23505", "unique_violation"), ("40P01", "deadlock_detected"),
                                       ("53100", "disk_full"), ("57P01", "admin_shutdown"),
                                       ("28P01", "invalid_password"), ("57014", "query_canceled")])
def test_postgres_known_codes_match_documented_names(code, name):
    rec = {r["code"]: r for r in REC if r["product"] == "PostgreSQL"}[code]
    assert rec["name"] == name and name in rec["description"]


@pytest.mark.parametrize("code,name", [("203", "EXIT_EXEC"), ("217", "EXIT_USER"), ("1", "EXIT_FAILURE")])
def test_systemd_known_codes(code, name):
    rec = {r["code"]: r for r in REC if r["product"] == "systemd"}[code]
    assert rec["name"] == name


def test_loader_rejects_overclaim_and_missing_source(tmp_path):
    base = dict(REC[0])
    for patch in ({"evidence_maturity": "validated"}, {"knowledge_class": "diagnostic_candidate"}, {"parser_mapping": "parser_mapped", "parser_mapping_note": ""},
                  {"remediation": "restart it"}, {"parser_mapping": "existing_parser_existing_signature"},
                  {"source": {"url": "http://x", "title": "t", "retrieved": "d", "method": "m"}}):
        p = tmp_path / "c.json"
        p.write_text(json.dumps({"schema_version": 1, "records": [dict(base, **patch)]}), encoding="utf-8")
        with pytest.raises(ValueError):
            vr.load_reference_catalog(p)
    dup = tmp_path / "d.json"
    dup.write_text(json.dumps({"schema_version": 1, "records": [base, base]}), encoding="utf-8")
    with pytest.raises(ValueError):
        vr.load_reference_catalog(dup)


def test_summary_counts_add_up():
    s = vr.reference_inventory_summary()
    assert sum(s["by_product"].values()) == s["total_records"] == len(REC)
    assert s["unique_sources"] == 6


def _by(product):
    return {(r["code_type"], r["code"]): r for r in REC if r["product"] == product}


def test_kafka_codes_copied_from_protocol_table():
    k = _by("Apache Kafka")
    assert k[("protocol_error_code", "1")]["name"] == "OFFSET_OUT_OF_RANGE"
    assert k[("protocol_error_code", "-1")]["name"] == "UNKNOWN_SERVER_ERROR"
    assert "retriable: True" in k[("protocol_error_code", "2")]["description"]
    assert ("protocol_error_code", "0") not in k  # NONE carries no definition


def test_http_registry_excludes_unassigned_and_keeps_reference():
    h = _by("HTTP status code registry")
    assert h[("http_status", "503")]["name"].startswith("Service Unavailable")
    assert all("nassigned" not in r["name"] for r in h.values())


def test_linux_errno_and_haproxy_flags():
    e = _by("Linux errno(3)")
    assert "Permission denied" in e[("errno_name", "EACCES")]["description"]
    assert "No space left on device" in e[("errno_name", "ENOSPC")]["description"]
    f = _by("HAProxy")
    assert "client-side timeout" in f[("termination_state_first_character", "c")]["description"]
    assert "QUEUE" in f[("termination_state_second_character", "Q")]["description"]
    assert "INVALID cookie" in f[("termination_state_third_character", "I")]["description"]


def test_reference_inventory_breadth_is_reported_by_domain():
    s = vr.reference_inventory_summary()
    assert {"database", "linux_service", "linux_os", "messaging", "web_middleware"} <= set(s["by_domain"])
    assert len(s["by_product"]) == 6
