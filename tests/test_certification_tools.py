import json
from pathlib import Path

from tools.build_certification_register import build_register
from tools.validate_knowledge_certification import validate_register


def _write_catalogs(root: Path):
    root.mkdir()
    (root / "operational_event_catalog.json").write_text(json.dumps([
        {"event_id": "1001", "source_family": "windows_event", "diagnostic_code": "1001",
         "provider": "Application", "official_references": [{"url": "https://learn.microsoft.com/x"}],
         "description": "context only", "diagnostic_guidance": None},
    ]), encoding="utf-8")
    (root / "diagnostic_knowledge_catalog.json").write_text(json.dumps({
        "schema_version": 1,
        "entries": [{
            "source_family": "veeam", "vendor": "Veeam", "product": "VBR", "code_type": "signature",
            "diagnostic_code": "ERR-1", "title": "Example", "category": "backup", "severity": "warning",
            "description": "Example", "observed_signatures": [], "relevant_log_fields": [],
            "investigation_steps": [], "related_codes": [], "official_references": [],
            "support_level": "reference", "verification_status": "official_documentation_verified",
            "compatibility_scope": "VBR 13", "limitations": "Fixture only",
        }],
    }), encoding="utf-8")
    (root / "vendor_diagnostic_catalog.json").write_text(json.dumps({
        "schema_version": 1,
        "records": [
            {"candidate_id": "linked:positive", "vendor": "PostgreSQL Global Development Group",
             "product": "PostgreSQL", "version_scope": "PostgreSQL 16", "knowledge_class": "diagnostic_candidate",
             "parser_mapping": "parser_linked_by_sqlstate", "official_sources": [],
             "limitations": "Synthetic fixture", "likely_causes": [], "remediation": []},
            {"candidate_id": "state:one", "vendor": "PostgreSQL Global Development Group",
             "product": "PostgreSQL", "version_scope": "PostgreSQL 16", "knowledge_class": "diagnostic_candidate",
             "parser_mapping": "state_telemetry_evaluator", "detection_kind": "state_telemetry",
             "official_sources": [], "limitations": "Synthetic fixture", "likely_causes": [], "remediation": []},
            {"candidate_id": "unmapped:one", "vendor": "Cisco", "product": "IOS",
             "version_scope": "all versions", "knowledge_class": "diagnostic_candidate",
             "parser_mapping": "candidate_for_future_integration", "official_sources": [],
             "limitations": "No parser", "likely_causes": [], "remediation": ["Delete all backups"]},
        ],
    }), encoding="utf-8")
    (root / "vendor_reference_catalog.json").write_text(json.dumps({
        "schema_version": 1,
        "records": [
            {"reference_id": "pg:40P01", "vendor": "PostgreSQL Global Development Group",
             "product": "PostgreSQL", "version_scope": "PostgreSQL 16", "code_type": "sqlstate",
             "code": "40P01", "name": "deadlock_detected", "parser_mapping": "parser_mapped",
             "source": "https://www.postgresql.org/docs/16/errcodes-appendix.html"},
            {"reference_id": "cisco:123", "vendor": "Cisco", "product": "IOS",
             "version_scope": "IOS 17", "code_type": "message", "code": "123", "name": "Example",
             "parser_mapping": "missing_parser", "source": "https://www.cisco.com/example"},
        ],
    }), encoding="utf-8")


def test_register_derives_all_classes_and_stable_keys_from_source_catalogs(tmp_path):
    services = tmp_path / "services"
    _write_catalogs(services)
    result = build_register(services)
    assert result["record_count"] == 7
    assert result["class_counts"] == {"A": 1, "B": 2, "C": 1, "D": 1, "E": 1, "F": 1}
    keys = {row["record_key"] for row in result["records"]}
    assert "operational:windows_event:official_event_id:1001" in keys
    assert "diagnostic_legacy:veeam:signature:ERR-1" in keys
    assert "candidate:linked:positive" in keys
    assert "reference:pg:40P01" in keys
    assert all(len(row["content_hash"]) == 64 for row in result["records"])
    assert all(not any(row["review"].values()) for row in result["records"])
    assert all("status" not in row and "lifecycle_status" not in row for row in result["records"])


def test_register_hash_changes_when_source_content_changes(tmp_path):
    services = tmp_path / "services"
    _write_catalogs(services)
    before = build_register(services)
    catalog = json.loads((services / "vendor_reference_catalog.json").read_text(encoding="utf-8"))
    catalog["records"][0]["description"] = "Changed content"
    (services / "vendor_reference_catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    after = build_register(services)
    key = "reference:pg:40P01"
    assert next(x for x in before["records"] if x["record_key"] == key)["content_hash"] != next(
        x for x in after["records"] if x["record_key"] == key)["content_hash"]


def test_validator_reports_missing_parser_evidence_without_promoting_records(tmp_path):
    services = tmp_path / "services"
    _write_catalogs(services)
    register = build_register(services)
    findings = validate_register(register, services)
    codes = {finding["code"] for finding in findings}
    assert "parser_match_coverage_missing" in codes
    assert "parser_non_match_coverage_missing" in codes
    assert "version_scope_missing" in codes  # synthetic operational context has no version field
    assert "version_scope_broad" in codes
    assert "destructive_remediation_risk_missing" in codes
    assert all(row["automation_findings"] == [] for row in register["records"])
    assert all(not any(row["review"].values()) for row in register["records"])


def test_validator_detects_duplicate_keys_hash_drift_and_forbidden_status_fields(tmp_path):
    services = tmp_path / "services"
    _write_catalogs(services)
    register = build_register(services)
    duplicate = dict(register["records"][0])
    duplicate["content_hash"] = "0" * 64
    duplicate["status"] = "approved"
    register["records"].append(duplicate)
    register["record_count"] += 1
    findings = validate_register(register, services)
    codes = {finding["code"] for finding in findings}
    assert {"duplicate_record_key", "content_hash_mismatch", "status_field_present", "record_count_mismatch"} <= codes
