"""Validate certification-register evidence without network or database access.

A PASS here means only that this automated check found no issue in its scope. It is
never a review, lifecycle transition, approval, or certification decision.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.build_certification_register import (
    SERVICES, SOURCE_FILES, _identity, _read_catalogs, build_register,
)
from backend.domain.knowledge.remediation_safety import destructive_actions  # noqa: E402

VENDOR_HOSTS = {
    "microsoft": ("microsoft.com",),
    "windows": ("microsoft.com",),
    "service control manager": ("microsoft.com",),
    "disk": ("microsoft.com",),
    "ntfs": ("microsoft.com",),
    "tcp/ip": ("microsoft.com",),
    "powershell": ("microsoft.com",),
    "cisco": ("cisco.com",),
    "fortinet": ("fortinet.com", "fortinetweb.s3.amazonaws.com"),
    "veeam": ("veeam.com", "knowledge.broadcom.com"),
    "openssh": ("openssh.com", "github.com"),
    "postgresql global development group": ("postgresql.org", "github.com"),
    "systemd project": ("freedesktop.org", "github.com"),
    "apache software foundation": ("apache.org",),
    "linux man-pages project": ("man7.org", "kernel.org"),
    "iana": ("iana.org",),
    "haproxy technologies": ("haproxy.com", "docs.haproxy.org"),
    "palo alto networks": ("paloaltonetworks.com",),
    "vmware / broadcom": ("vmware.com", "broadcom.com"),
}
VERSION_TOO_BROAD = re.compile(r"\b(?:all|any)\s+(?:versions?|releases?|platforms?)\b|\buniversal(?:ly)?\b", re.I)
UNQUALIFIED = re.compile(r"\b(?:always|never)\b", re.I)
CERTAIN_CAUSE = re.compile(r"\b(?:is|are|was|were) caused by\b|\bthe cause is\b", re.I)
# A "risk" field that merely says the vendor gave none is an unresolved risk, not a stated one.
RISK_UNRESOLVED = re.compile(r"^\s*(?:not stated|not documented|unknown|none stated|n/a)\b", re.I)
EVIDENCE_SEVERITY = "evidence"


def _vendor_hosts(vendor: str) -> tuple[str, ...]:
    normalized = vendor.casefold().strip()
    if normalized.startswith(("microsoft", "windows", "powershell", "service control", "disk", "ntfs", "tcp/ip", "remote desktop", "dhcp", "dns", "resource-exhaustion", ".net runtime", "vss")):
        return ("microsoft.com",)
    return VENDOR_HOSTS.get(normalized, ())


def _source_lookup(services: Path) -> dict[str, tuple[str, dict[str, Any]]]:
    catalogs = _read_catalogs(services)
    rows = {}
    for catalog, items in catalogs.items():
        for raw in items:
            key = f"{catalog}:{_identity(raw, catalog)}"
            rows[key] = (catalog, raw)
    return rows


def _finding(code: str, severity: str, record_key: str | None, message: str) -> dict[str, Any]:
    return {"code": code, "severity": severity, "record_key": record_key, "message": message}


def _parser_consistency(records: list[dict[str, Any]], services: Path, checks: dict[str, set[str]] | None = None) -> list[dict[str, Any]]:
    checks = checks if checks is not None else defaultdict(set)
    findings: list[dict[str, Any]] = []
    refs = [row for row in records if row["cert_class"] == "C"]
    try:
        from backend.domain.analyzer.services.parser import parse_event_metadata
        from backend.domain.analyzer.services.vendor_reference import reference_for_metadata
    except Exception as exc:
        return [_finding("reference_parser_unavailable", "error", None,
                         f"Could not load local parser/resolver for offline consistency checks: {type(exc).__name__}")]

    checked = 0
    expected_non_emission = 0
    source_rows = _source_lookup(services)
    for row in refs:
        catalog, raw = source_rows.get(row["record_key"], ("", {}))
        if not raw:
            findings.append(_finding("reference_source_missing", "error", row["record_key"], "Reference row is absent from source catalogs."))
            continue
        product = str(raw.get("product", "")).casefold()
        code = str(raw.get("code", ""))
        try:
            if product == "postgresql":
                text = json.dumps({
                    "timestamp": "2026-11-20 10:00:00.123 UTC", "user": "synthetic",
                    "dbname": "synthetic", "pid": 7, "session_id": "s.1", "line_num": 1,
                    "error_severity": "ERROR", "state_code": code, "message": "synthetic fixture",
                    "backend_type": "client backend",
                })
                metadata = parse_event_metadata(text)
                result = reference_for_metadata(metadata)
                # PostgreSQL's successful-completion class (00xxx) is deliberately not surfaced
                # by the Analyzer; the existing parser contract explicitly excludes it.
                if code.startswith("00") and result is None:
                    expected_non_emission += 1
                    checked += 1
                    checks[row["record_key"]].add("reference_parser_expected_non_emission")
                    continue
            elif product == "systemd":
                if code == "0":
                    expected_non_emission += 1
                    checked += 1
                    checks[row["record_key"]].add("reference_parser_expected_non_emission")
                    continue
                status_name = str(raw.get("name", "")).removeprefix("EXIT_")
                text = (f"Nov 20 10:00:00 host-synthetic systemd[1]: demo.service: "
                        f"Main process exited, code=exited, status={code}/{status_name}")
                metadata = parse_event_metadata(text)
                result = reference_for_metadata(metadata)
            else:
                findings.append(_finding("reference_parser_scope_unknown", "warning", row["record_key"],
                                         f"No offline positive fixture rule is defined for product {raw.get('product')!r}."))
                continue
            checked += 1
            if not result or result.get("reference_id") != raw.get("reference_id"):
                findings.append(_finding("reference_parser_mismatch", "error", row["record_key"],
                                         "Synthetic positive input did not resolve to this parser-mapped reference."))
            else:
                checks[row["record_key"]].add("reference_parser_positive")
        except Exception as exc:
            findings.append(_finding("reference_parser_check_error", "error", row["record_key"],
                                     f"Offline positive check raised {type(exc).__name__}."))
    findings.append(_finding("reference_parser_check_summary", "evidence", None,
                             f"Checked {checked} parser-mapped references; {expected_non_emission} success-status references (PostgreSQL class 00, systemd exit status 0) are intentionally not surfaced by the parser contract."))
    return findings


def validate_register(register: dict[str, Any], services: Path = SERVICES) -> list[dict[str, Any]]:
    return validate_register_detailed(register, services)[0]


def validate_register_detailed(register: dict[str, Any], services: Path = SERVICES) -> tuple[list[dict[str, Any]], dict[str, set[str]]]:
    """Return (findings, checks_run). ``checks_run[record_key]`` lists the automated checks that actually executed."""
    checks: dict[str, set[str]] = defaultdict(set)
    findings: list[dict[str, Any]] = []
    records = register.get("records", [])
    sources = _source_lookup(services)
    expected = build_register(services)
    expected_by_key = {row["record_key"]: row for row in expected["records"]}

    seen: set[str] = set()
    counts = Counter()
    for row in records:
        key = row.get("record_key", "")
        if key in seen:
            findings.append(_finding("duplicate_record_key", "error", key, "Register contains a duplicate stable record key."))
        seen.add(key)
        counts[row.get("cert_class", "")] += 1
        if key not in sources:
            findings.append(_finding("source_record_missing", "error", key or None, "Register key does not resolve to a canonical source record."))
            continue
        canonical = expected_by_key.get(key)
        if not canonical or row.get("content_hash") != canonical["content_hash"]:
            findings.append(_finding("content_hash_mismatch", "error", key, "Content hash differs from the canonical record hash."))
        if row.get("cert_class") != canonical["cert_class"]:
            findings.append(_finding("classification_mismatch", "error", key, "Class differs from the documented record-class rule."))
        if any(value for value in (row.get("review") or {}).values()):
            findings.append(_finding("review_field_not_blank", "error", key, "Generated human-review fields must remain blank."))
        if any(field in row for field in ("status", "lifecycle_status", "dimension_status")):
            findings.append(_finding("status_field_present", "error", key, "Register must not create lifecycle or certification statuses."))

        _, raw = sources[key]
        cls = row.get("cert_class")
        if not row.get("source_urls"):
            findings.append(_finding("source_url_missing", "warning", key,
                                     "No source URL is recorded; source verification cannot start for this record."))
        else:
            checks[key].add("source_present")
        evidence = [item for item in (row.get("test_evidence") or []) if isinstance(item, dict)]
        for item in evidence:
            if item.get("current") is not True:
                findings.append(_finding("evidence_stale", "warning", key,
                                         f"{item.get('kind')} evidence in {item.get('evidence_file')} was bound to a different content hash."))
            elif item.get("all_passed") is not True:
                findings.append(_finding("evidence_failed", "error", key,
                                         f"{item.get('kind')} evidence in {item.get('evidence_file')} contains a failing case."))

        def _has(kind: str) -> bool:
            return any(i.get("kind") == kind and i.get("current") is True and i.get("all_passed") is True for i in evidence)

        if cls == "B":
            if not _has("parser_match"):
                findings.append(_finding("parser_match_coverage_missing", "warning", key,
                                         "No current, passing per-record positive evidence from the real parser/Analyzer path."))
            if not _has("parser_non_match"):
                findings.append(_finding("parser_non_match_coverage_missing", "warning", key,
                                         "No current, passing per-record negative/non-match evidence from the real parser/Analyzer path."))
            if _has("parser_match") and _has("parser_non_match"):
                checks[key].add("parser_positive_negative")
        elif cls == "D":
            mapping = (row.get("parser_or_evaluator") or {}).get("mapping")
            if mapping != "state_telemetry_evaluator":
                findings.append(_finding("evaluator_not_mapped", "warning", key,
                                         "State/telemetry candidate has no evaluator mapped; matching evidence cannot exist yet."))
            else:
                if not _has("evaluator_real_state_positive"):
                    findings.append(_finding("state_real_evidence_positive_missing", "warning", key,
                                             "No current real-source (not authored-row) positive evidence for the evaluator."))
                if not _has("evaluator_real_state_negative"):
                    findings.append(_finding("state_real_evidence_negative_missing", "warning", key,
                                             "No current real-source (not authored-row) negative evidence for the evaluator."))
                if _has("evaluator_real_state_positive") and _has("evaluator_real_state_negative"):
                    checks[key].add("evaluator_real_state")

        scope = str(row.get("version_scope") or "").strip()
        if not scope:
            findings.append(_finding("version_scope_missing", "warning", key, "Version scope is empty."))
        elif row.get("version_scope_basis") == "product_level_statement":
            findings.append(_finding("version_scope_product_level_only", "warning", key,
                                     "The official page states a product-level applicability only (no OS version or build range)."))
        elif row.get("version_scope_basis") == "derived_from_source_scope":
            findings.append(_finding("version_scope_not_explicit", "warning", key,
                                     "The only 'scope' is free text copied from a cited page; no explicit product/version range is recorded."))
        elif VERSION_TOO_BROAD.search(scope):
            findings.append(_finding("version_scope_broad", "warning", key, "Version scope contains broad applicability language; human scope review is needed."))

        for url in row.get("source_urls") or []:
            parsed = urlparse(url)
            if parsed.scheme.lower() != "https" or not parsed.hostname:
                findings.append(_finding("source_url_invalid_or_not_https", "warning", key, "Source URL is malformed or does not use HTTPS."))
                continue
            allow = _vendor_hosts(str(row.get("vendor", "")))
            if not allow:
                findings.append(_finding("vendor_host_allowlist_missing", "warning", key,
                                         f"No static host allow-list is defined for vendor {row.get('vendor')!r}."))
            elif not any(parsed.hostname.casefold() == domain or parsed.hostname.casefold().endswith("." + domain)
                         for domain in allow):
                findings.append(_finding("source_host_not_allowlisted", "warning", key,
                                         f"Source hostname {parsed.hostname!r} is outside the static vendor allow-list."))

        remediations = []
        for field in ("remediation", "remediation_guidance", "safe_remediation"):
            value = raw.get(field)
            if isinstance(value, str):
                remediations.append(value)
            elif isinstance(value, list):
                remediations.extend(item for item in value if isinstance(item, str))
        guidance = raw.get("diagnostic_guidance")
        if isinstance(guidance, dict):
            safe = guidance.get("safe_remediation")
            if isinstance(safe, list):
                remediations.extend(item for item in safe if isinstance(item, str))
        risk_values = [str(raw.get(field, "")) for field in ("operational_risk", "risk", "rollback")]
        if isinstance(guidance, dict):
            risk_values.extend(str(guidance.get(field, "")) for field in ("risk", "rollback"))
        risk_text = " ".join(risk_values)
        if destructive_actions(remediations):  # negation-aware: 'Do not delete ...' is a prohibition, not an instruction
            if not risk_text.strip():
                findings.append(_finding("destructive_remediation_risk_missing", "warning", key,
                                         "Destructive remediation language has no stated risk/rollback field."))
            elif RISK_UNRESOLVED.match(risk_text.strip()) and not re.search(r"\brollback\b", risk_text, re.I):
                findings.append(_finding("destructive_remediation_risk_unresolved", "warning", key,
                                         "Destructive remediation language; the risk field only says the vendor gave no risk statement."))
            else:
                checks[key].add("destructive_risk_stated")
        all_claims = " ".join(str(raw.get(field, "")) for field in ("description", "meaning", "likely_causes", "causes", "remediation"))
        if UNQUALIFIED.search(all_claims):
            findings.append(_finding("unqualified_always_never", "warning", key,
                                     "Unqualified 'always' or 'never' language needs human evidence review."))
        causes = raw.get("likely_causes") or raw.get("causes") or []
        if isinstance(causes, str):
            causes = [causes]
        if isinstance(causes, list) and any(CERTAIN_CAUSE.search(str(item)) for item in causes):
            findings.append(_finding("certain_cause_wording", "warning", key,
                                     "Cause wording may assert certainty; human source and diagnostic review is needed."))

    missing_keys = set(expected_by_key) - seen
    extra_keys = seen - set(expected_by_key)
    for key in sorted(missing_keys):
        findings.append(_finding("register_record_missing", "error", key, "Canonical source record is absent from the register."))
    for key in sorted(extra_keys):
        findings.append(_finding("register_record_unexpected", "error", key, "Register contains a key absent from the four source catalogs."))

    if register.get("record_count") != len(expected["records"]) or len(records) != len(expected["records"]):
        findings.append(_finding("record_count_mismatch", "error", None,
                                 f"Register/source count mismatch: register={len(records)}, sources={len(expected['records'])}."))
    if dict(sorted(counts.items())) != expected["class_counts"]:
        findings.append(_finding("class_count_mismatch", "error", None,
                                 f"Class counts differ: register={dict(counts)}, expected={expected['class_counts']}."))

    # Diagnostic candidates without a parser are explicitly class E; their lack of parser
    # coverage is expected and they remain references only under the proposal.
    findings.extend(_parser_consistency(records, services, checks))
    _class_technical_checks(records, sources, findings, checks)
    return findings, checks


def _class_technical_checks(records, sources, findings, checks) -> None:
    """Technical checks for classes without parser evidence: identity resolution (A) and schema completeness (E, F)."""
    try:
        from backend.domain.analyzer.services.operational_catalog import resolve_windows_entry
    except Exception as exc:  # noqa: BLE001
        findings.append(_finding("identity_resolver_unavailable", "error", None, f"Could not load the Windows resolver: {type(exc).__name__}"))
        resolve_windows_entry = None
    for row in records:
        key = row.get("record_key", "")
        if key not in sources:
            continue
        _, raw = sources[key]
        cls = row.get("cert_class")
        if cls == "A" and resolve_windows_entry is not None:
            event_id, provider = raw.get("event_id"), raw.get("provider")
            result = resolve_windows_entry(event_id, provider)
            entry = result.get("entry") or {}
            if result.get("basis") == "provider_and_id" and entry.get("event_id") == str(event_id) and entry.get("provider") == provider:
                checks[key].add("identity_resolution")
            else:
                findings.append(_finding("identity_resolution_failed", "warning", key,
                                         f"Event ID {event_id} with provider {provider!r} did not resolve uniquely to this record (basis={result.get('basis')})."))
        elif cls == "E":
            missing = [f for f in ("candidate_id", "version_scope", "limitations", "official_sources", "parser_mapping") if not raw.get(f)]
            if missing:
                findings.append(_finding("schema_incomplete", "warning", key, f"Missing fields: {missing}"))
            else:
                checks[key].add("schema_complete")
        elif cls == "F":
            missing = [f for f in ("reference_id", "code", "version_scope", "source") if not raw.get(f)]
            if missing:
                findings.append(_finding("schema_incomplete", "warning", key, f"Missing fields: {missing}"))
            else:
                checks[key].add("schema_complete")


def reconcile_dispositions(findings: list[dict[str, Any]], dispositions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every actionable finding must have exactly one recorded disposition; nothing is silenced by omission."""
    problems: list[dict[str, Any]] = []
    actionable = [f for f in findings if f["severity"] != EVIDENCE_SEVERITY]
    have = Counter((d.get("record_key"), d.get("finding_type")) for d in dispositions)
    for f in actionable:
        k = (f.get("record_key"), f["code"])
        if have.get(k, 0) == 0:
            problems.append(_finding("finding_without_disposition", "error", f.get("record_key"), f"No disposition for {f['code']}."))
        elif have[k] > 1:
            problems.append(_finding("finding_with_duplicate_disposition", "error", f.get("record_key"), f"Several dispositions for {f['code']}."))
    wanted = {(f.get("record_key"), f["code"]) for f in actionable}
    for d in dispositions:
        if d.get("resolution_status") == "RESOLVED_BY_EVIDENCE" or d.get("record_key") == "(register)" or d.get("superseded_by"):
            continue  # resolved findings and the informational summary row legitimately no longer appear as findings
        if (d.get("record_key"), d.get("finding_type")) not in wanted:
            problems.append(_finding("disposition_without_finding", "warning", d.get("record_key"),
                                     f"Disposition for {d.get('finding_type')} no longer matches any finding (fixed or stale)."))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", type=Path, default=ROOT / "docs" / "acceptance" / "certification" / "register.json")
    parser.add_argument("--services-dir", type=Path, default=SERVICES)
    parser.add_argument("--output", type=Path, help="Optional JSON findings output; stdout is used otherwise.")
    parser.add_argument("--dispositions", type=Path, help="findings_disposition.json; every actionable finding must have a disposition.")
    args = parser.parse_args(argv)
    register = json.loads(args.register.read_text(encoding="utf-8"))
    findings = validate_register(register, args.services_dir)
    if args.dispositions:
        rows = json.loads(args.dispositions.read_text(encoding="utf-8")).get("dispositions", [])
        findings = findings + reconcile_dispositions(findings, rows)
    actionable = [item for item in findings if item["severity"] != EVIDENCE_SEVERITY]
    result = {
        "evidence_only": True,
        "certification_decision": None,
        "finding_count": len(actionable),
        "informational_evidence_rows": len(findings) - len(actionable),
        "counts_by_code": dict(sorted(Counter(item["code"] for item in actionable).items())),
        "findings": findings,
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 1 if any(item["severity"] == "error" for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
