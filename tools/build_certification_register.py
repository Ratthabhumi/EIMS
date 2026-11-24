"""Build a read-only, evidence-only certification register from the four canonical catalogs.

This tool never writes to a source catalog or governance database. Generated rows carry
classification and evidence pointers only; no lifecycle or certification status is emitted.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SERVICES = ROOT / "backend" / "domain" / "analyzer" / "services"
DEFAULT_OUTPUT = ROOT / "docs" / "acceptance" / "certification"
SOURCE_FILES = {
    "operational": "operational_event_catalog.json",
    "diagnostic_legacy": "diagnostic_knowledge_catalog.json",
    "candidate": "vendor_diagnostic_catalog.json",
    "reference": "vendor_reference_catalog.json",
}
from backend.domain.knowledge.remediation_safety import DESTRUCTIVE_RE, DESTRUCTIVE_VERBS, destructive_verbs_in  # noqa: E402,F401  single source of truth


def _read_catalogs(services: Path) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for name, filename in SOURCE_FILES.items():
        data = json.loads((services / filename).read_text(encoding="utf-8"))
        if name == "operational":
            rows = data
        elif name == "diagnostic_legacy":
            rows = data.get("entries")
        else:
            rows = data.get("records")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"Unexpected catalog shape: {filename}")
        result[name] = rows
    return result


def _identity(record: dict[str, Any], catalog: str) -> str:
    if catalog == "operational":
        # Mirrors operational_catalog.load_catalog's stable identity components.
        code = record.get("diagnostic_code", record.get("event_id"))
        return ":".join((str(record.get("source_family", "windows_event")),
                         str(record.get("code_type", "official_event_id")), str(code)))
    if catalog == "diagnostic_legacy":
        return ":".join(str(record.get(k, "")) for k in
                        ("source_family", "code_type", "diagnostic_code"))
    if catalog == "candidate":
        return str(record.get("candidate_id", ""))
    return str(record.get("reference_id", ""))


def _catalog_hash(record: dict[str, Any], catalog: str, loaded_entries: dict[str, dict[str, Any]]) -> tuple[str, str]:
    # The 181-record overlay hashes the loaded canonical row, including loader-supplied identity
    # fields, exactly as knowledge.service.canonical_hash does.
    if catalog in ("operational", "diagnostic_legacy"):
        identity = _identity(record, catalog)
        entry = loaded_entries.get(identity)
        if entry is not None:
            from backend.domain.knowledge.service import canonical_hash
            return canonical_hash(entry), "knowledge.service canonical loaded record"
    material = json.dumps(record, sort_keys=True, default=str, separators=(",", ":"))
    import hashlib
    return hashlib.sha256(material.encode("utf-8")).hexdigest(), "canonical source record"


def _loaded_entries() -> dict[str, dict[str, Any]]:
    try:
        from backend.domain.analyzer.services.operational_catalog import load_catalog
        from backend.domain.knowledge.service import canonical_hash
        del canonical_hash
        return {str(row["catalog_id"]): row for row in load_catalog()}
    except (ImportError, KeyError, ValueError):
        return {}


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_strings(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_strings(item))
        return out
    return []


def _urls(record: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for key in ("official_references", "official_sources"):
        values = record.get(key) or []
        if isinstance(values, list):
            for item in values:
                if isinstance(item, dict) and isinstance(item.get("url"), str):
                    found.append(item["url"])
    source = record.get("source")
    if isinstance(source, str) and source.startswith(("http://", "https://")):
        found.append(source)
    elif isinstance(source, dict) and isinstance(source.get("url"), str):
        found.append(source["url"])
    return list(dict.fromkeys(found))


def _classify(catalog: str, record: dict[str, Any]) -> str:
    if catalog == "operational":
        return "A"
    if catalog == "diagnostic_legacy":
        return "B"
    if catalog == "reference":
        return "C" if record.get("parser_mapping") == "parser_mapped" else "F"
    kind = record.get("detection_kind")
    if kind in ("state_telemetry", "cli_state"):
        return "D"
    return "B" if str(record.get("parser_mapping", "")).startswith("parser_linked_") else "E"


def _applicability(record: dict[str, Any]) -> dict[str, Any] | None:
    block = record.get("applicability")
    return block if isinstance(block, dict) and isinstance(block.get("statement"), str) and block["statement"].strip() else None


def _version_scope(record: dict[str, Any]) -> str:
    block = _applicability(record)
    if block:
        return block["statement"].strip()
    explicit = record.get("version_scope") or record.get("compatibility_scope")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    references = record.get("official_references") or record.get("official_sources") or []
    scopes = list(dict.fromkeys(
        item["scope"].strip() for item in references
        if isinstance(item, dict) and isinstance(item.get("scope"), str) and item["scope"].strip()
    )) if isinstance(references, list) else []
    return " | ".join(scopes)


def _version_basis(record: dict[str, Any]) -> str:
    """'explicit' when the record states a version/compatibility scope itself; 'derived_from_source_scope' when the value is
    only the free-text scope of a cited page (which describes what the page covers, not a product version range)."""
    block = _applicability(record)
    if block:  # verbatim official statement copied by tools/apply_windows_applicability.py
        return "explicit_from_official_statement" if block.get("kind") == "os_versions_as_stated_by_page" else "product_level_statement"
    explicit = record.get("version_scope") or record.get("compatibility_scope")
    if isinstance(explicit, str) and explicit.strip():
        return "explicit"
    return "derived_from_source_scope" if _version_scope(record) else ""


def _legacy_verification(record: dict[str, Any], catalog: str) -> dict[str, Any] | None:
    """Backward-compatible reading of the legacy catalog label ``verification_status`` on the 28 legacy diagnostic entries. The
    label was set by earlier tooling; no human reviewer or review record exists for it, so it must never be read as SOURCE_VERIFIED."""
    if catalog != "diagnostic_legacy":
        return None
    return {"label": record.get("verification_status", ""), "human_source_verified": False,
            "interpretation": "legacy catalog label (the UI shows it as 'Documented reference'); no human reviewer or review record exists; not equivalent to SOURCE_VERIFIED"}


def _parser(record: dict[str, Any], catalog: str = "") -> dict[str, Any] | None:
    if catalog == "diagnostic_legacy" and not record.get("parser_mapping"):
        return {"mapping": "existing_parser_existing_signature",
                "symbol": f"{record.get('source_family', '')}:{record.get('code_type', '')}"}
    mapping = record.get("parser_mapping")
    if not mapping:
        mapping = record.get("detection_kind")
    if not mapping:
        return None
    return {"mapping": mapping, "symbol": record.get("parser_symbol") or record.get("evaluator")
            or record.get("evaluator_symbol") or ""}


def _risk(record: dict[str, Any]) -> list[str]:
    keys = ("operational_risk", "risk", "rollback", "remediation_risk")
    risks = []
    for key in keys:
        risks.extend(_strings(record.get(key)))
    guidance = record.get("diagnostic_guidance")
    if isinstance(guidance, dict):
        risks.extend(_strings(guidance.get("risk")))
        risks.extend(_strings(guidance.get("rollback")))
    return list(dict.fromkeys(risks))


def _limitations(record: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(_strings(record.get("limitations"))))


def _remediation(record: dict[str, Any]) -> list[str]:
    out = []
    for key in ("remediation", "remediation_guidance", "safe_remediation"):
        out.extend(_strings(record.get(key)))
    guidance = record.get("diagnostic_guidance")
    if isinstance(guidance, dict):
        out.extend(_strings(guidance.get("safe_remediation")))
    return out


EVIDENCE_KINDS = {
    ("analyzer_path", "positive"): "parser_match",
    ("analyzer_path", "negative"): "parser_non_match",
    ("evaluator_synthetic_row", "positive"): "evaluator_synthetic_positive",
    ("evaluator_synthetic_row", "negative"): "evaluator_synthetic_negative",
    ("evaluator_real_state", "positive"): "evaluator_real_state_positive",
    ("evaluator_real_state", "negative"): "evaluator_real_state_negative",
}


def _load_evidence(evidence_dir: Path | None) -> dict[str, list[dict[str, Any]]]:
    """Group run-bound evidence files (technical_evidence_*.json) by record key. Only explicit bindings are used."""
    grouped: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = {}
    meta: dict[str, dict[str, Any]] = {}
    if evidence_dir is None or not evidence_dir.is_dir():
        return {}
    for path in sorted(evidence_dir.glob("technical_evidence_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for case in data.get("cases", []):
            kind = EVIDENCE_KINDS.get((case.get("kind"), case.get("polarity")))
            if not kind:
                continue
            key = case["record_key"]
            grouped.setdefault(key, {}).setdefault((kind, path.name), []).append(case)
            meta[(key, path.name)] = {"hash": (data.get("record_hashes") or {}).get(key, ""),
                                      "run_at": data.get("generated_at", ""), "git_head": data.get("git_head", "")}
    out: dict[str, list[dict[str, Any]]] = {}
    for key, kinds in grouped.items():
        for (kind, filename), cases in sorted(kinds.items()):
            m = meta[(key, filename)]
            out.setdefault(key, []).append({
                "kind": kind, "evidence_file": filename, "cases": len(cases),
                "all_passed": all(c.get("passed") is True for c in cases),
                "run_at": m["run_at"], "git_head": m["git_head"], "bound_content_hash": m["hash"],
            })
    return out


def _test_evidence(record_key: str, content_hash: str, evidence: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Attach only evidence explicitly bound to this record key; mark it stale if the content hash has since changed."""
    return [dict(item, current=item["bound_content_hash"] == content_hash) for item in evidence.get(record_key, [])]


def build_register(services: Path = SERVICES, evidence_dir: Path | None = None) -> dict[str, Any]:
    if evidence_dir is None and services == SERVICES:
        evidence_dir = DEFAULT_OUTPUT
    evidence = _load_evidence(evidence_dir)
    catalogs = _read_catalogs(services)
    loaded = _loaded_entries()
    records: list[dict[str, Any]] = []
    for catalog, rows in catalogs.items():
        for raw in rows:
            identity = _identity(raw, catalog)
            if not identity:
                raise ValueError(f"Missing stable identity in {catalog}: {raw!r}")
            cert_class = _classify(catalog, raw)
            content_hash, hash_basis = _catalog_hash(raw, catalog, loaded)
            remediation = _remediation(raw)
            text_to_scan = "\n".join(remediation)
            records.append({
                "record_key": f"{catalog}:{identity}",
                "catalog": catalog,
                "catalog_id": identity,
                "cert_class": cert_class,
                "content_hash": content_hash,
                "hash_basis": hash_basis,
                "record_type": raw.get("knowledge_class") or raw.get("source_family") or raw.get("code_type") or "",
                "vendor": raw.get("vendor") or raw.get("provider") or "",
                "product": raw.get("product") or "",
                "version_scope": _version_scope(raw),
                "version_scope_basis": _version_basis(raw),
                "source_urls": _urls(raw),
                "quoted_claims": [],
                "legacy_verification": _legacy_verification(raw, catalog),
                "parser_or_evaluator": _parser(raw, catalog),
                "test_evidence": _test_evidence(f"{catalog}:{identity}", content_hash, evidence),
                "limitations": _limitations(raw),
                "risks": _risk(raw),
                "destructive_verbs": destructive_verbs_in(remediation),  # negation-aware: prohibitions are not instructions
                "automation_findings": [],
                "review": {
                    "reviewer_id": "", "reviewer_kind": "", "decision": "",
                    "decided_at": "", "rationale": "",
                },
            })
    return {
        "schema_version": 1,
        "source_catalogs": dict(SOURCE_FILES),
        "record_count": len(records),
        "class_counts": dict(sorted(Counter(row["cert_class"] for row in records).items())),
        "records": sorted(records, key=lambda row: row["record_key"]),
    }


def write_register(register: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "register.json"
    csv_path = output_dir / "register.csv"
    json_path.write_text(json.dumps(register, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    columns = [
        "record_key", "catalog", "catalog_id", "cert_class", "content_hash", "hash_basis",
        "record_type", "vendor", "product", "version_scope", "version_scope_basis", "source_urls", "quoted_claims",
        "parser_or_evaluator", "test_evidence", "limitations", "risks", "destructive_verbs",
        "automation_findings", "legacy_verification", "readiness", "review",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in register["records"]:
            writer.writerow({key: json.dumps(row[key], ensure_ascii=False) if isinstance(row[key], (list, dict)) else row[key]
                             for key in columns})


TECHNICAL_REQUIRED = {  # automated checks that must have executed, per class, for TECHNICALLY_VALIDATED (evidence only)
    "A": {"identity_resolution"},
    "B": {"parser_positive_negative"},
    "C": set(),  # one of the reference-parser checks, see apply_readiness
    "D": {"evaluator_real_state"},
    "E": {"schema_complete"},
    "F": {"schema_complete"},
}
TECHNICAL_BLOCKING_CODES = {
    "parser_match_coverage_missing", "parser_non_match_coverage_missing", "evaluator_not_mapped",
    "state_real_evidence_positive_missing", "state_real_evidence_negative_missing", "evidence_stale", "evidence_failed",
    "reference_parser_mismatch", "reference_parser_check_error", "identity_resolution_failed", "schema_incomplete",
}
SOURCE_BLOCKING_CODES = {"source_url_missing", "version_scope_missing", "version_scope_broad", "version_scope_not_explicit", "version_scope_product_level_only"}


def apply_readiness(register: dict[str, Any], findings: list[dict[str, Any]], checks: dict[str, set[str]]) -> None:
    """Derive per-record readiness from evidence. Human fields stay blank, so source verification, independent review and
    approval can never be derived here: those states are reserved for recorded human governance decisions. Source
    blockers (missing URL, missing/non-explicit version scope) and technical blockers are kept apart."""
    by_key: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        if finding.get("record_key") and finding["severity"] != "evidence":
            by_key.setdefault(finding["record_key"], []).append(finding)
    for row in register["records"]:
        key, cls = row["record_key"], row["cert_class"]
        mine = by_key.get(key, [])
        technical_blockers = sorted({f["code"] for f in mine if f["code"] in TECHNICAL_BLOCKING_CODES})
        source_blockers = sorted({f["code"] for f in mine if f["code"] in SOURCE_BLOCKING_CODES})
        done = checks.get(key, set())
        need_ok = bool(done & {"reference_parser_positive", "reference_parser_expected_non_emission"}) if cls == "C" else True
        technical = ("TECHNICALLY_VALIDATED" if (TECHNICAL_REQUIRED[cls] <= done and need_ok and not technical_blockers)
                     else "TECHNICAL_UNVALIDATED")
        row["readiness"] = {
            "basis": "automated evidence only; not a certification, review or approval",
            "source": "SOURCE_UNVERIFIED",
            "technical": technical,
            "independent_review": "INDEPENDENT_REVIEW_PENDING",
            "approval": "NOT_APPROVED",
            "blocked": bool(technical_blockers or source_blockers),
            "blockers": technical_blockers,
            "source_blockers": source_blockers,
            "checks_run": sorted(done),
            "review_attention": sorted({f["code"] for f in mine if f["code"] not in TECHNICAL_BLOCKING_CODES | SOURCE_BLOCKING_CODES}),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--services-dir", type=Path, default=SERVICES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evidence-dir", type=Path, default=None, help="directory with technical_evidence_*.json (default: output dir)")
    args = parser.parse_args(argv)
    register = build_register(args.services_dir, args.evidence_dir or args.output_dir)
    from tools.validate_knowledge_certification import validate_register_detailed
    findings, checks = validate_register_detailed(register, args.services_dir)
    by_key: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        if finding.get("record_key"):
            by_key.setdefault(finding["record_key"], []).append(finding)
    for row in register["records"]:
        row["automation_findings"] = by_key.get(row["record_key"], [])
    apply_readiness(register, findings, checks)
    write_register(register, args.output_dir)
    print(json.dumps({"record_count": register["record_count"], "class_counts": register["class_counts"],
                      "json": str(args.output_dir / "register.json"), "csv": str(args.output_dir / "register.csv")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
