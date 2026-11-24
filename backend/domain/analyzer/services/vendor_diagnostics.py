"""Diagnostic candidates whose input is not (yet) parsed by an EIMS parser.

Separate from OPERATIONAL_CATALOG (parser-reachable) and from the reference
inventory (definition tables). Each record carries symptom, causes, commands
with expected evidence, vendor-stated remediation, risk and verification, with
unsupported fields stated as "Not stated" rather than invented.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

DIAGNOSTIC_CATALOG_PATH = Path(__file__).with_name("vendor_diagnostic_catalog.json")
ALLOWED_MATURITY = {"candidate", "source_referenced"}
ALLOWED_PARSER_MAPPING = {"missing_parser", "existing_parser_missing_signature", "candidate_for_future_integration",
                          "parser_linked_by_sqlstate", "parser_linked_by_message", "parser_linked_by_fields",
                          "state_telemetry_evaluator"}
DETECTION_KINDS = {"log_or_symptom", "log_fields", "state_telemetry", "cli_state"}
STATE_KINDS = {"state_telemetry", "cli_state"}
_TEXT = ("candidate_id", "vendor", "product", "product_family", "version_scope", "problem_domain", "category",
         "symptom", "meaning", "operational_risk", "parser_mapping", "evidence_maturity", "knowledge_class",
         "lifecycle_status", "evidence_basis", "limitations")
_LISTS = ("signatures", "likely_causes", "alternative_causes", "diagnostic_steps", "remediation", "verification_steps")


def load_diagnostic_candidates(path=DIAGNOSTIC_CATALOG_PATH) -> list[dict]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("schema_version") != 1 or not isinstance(doc.get("records"), list):
        raise ValueError("Unsupported diagnostic candidate catalog")
    seen, out = set(), []
    for r in doc["records"]:
        if not isinstance(r, dict) or any(not isinstance(r.get(k), str) or not r[k].strip() for k in _TEXT):
            raise ValueError("Invalid diagnostic candidate")
        for k in _LISTS:
            if not isinstance(r.get(k), list) or not r[k] or any(not isinstance(v, str) or not v.strip() for v in r[k]):
                raise ValueError(f"Invalid list {k}: {r['candidate_id']}")
        cmds = r.get("diagnostic_commands")
        if not isinstance(cmds, list) or not cmds or any(
                not isinstance(c, dict) or not c.get("command") or not c.get("expected_evidence") for c in cmds):
            raise ValueError(f"Every command needs expected_evidence: {r['candidate_id']}")
        srcs = r.get("official_sources")
        if not isinstance(srcs, list) or not srcs or any(
                not str(s.get("url", "")).startswith("https://") or not all(s.get(k) for k in ("title", "scope", "retrieved", "page_date"))
                for s in srcs):
            raise ValueError(f"Incomplete official source: {r['candidate_id']}")
        if r["knowledge_class"] != "diagnostic_candidate" or r["lifecycle_status"] != "candidate":
            raise ValueError("Only diagnostic_candidate / candidate records are allowed")
        if r["evidence_maturity"] not in ALLOWED_MATURITY or r["parser_mapping"] not in ALLOWED_PARSER_MAPPING:
            raise ValueError(f"Overclaim in {r['candidate_id']}")
        if r["parser_mapping"] == "parser_linked_by_sqlstate":
            from backend.domain.analyzer.services.vendor_reference import REFERENCE_BY_ID

            codes = r.get("sqlstate_codes")
            if (not isinstance(codes, list) or not codes or not str(r.get("sqlstate_mapping_basis", "")).strip()
                    or any(f"postgresql:sqlstate:{c}" not in REFERENCE_BY_ID or str(c).startswith("00") for c in codes)):
                raise ValueError(f"sqlstate link needs documented, non-success codes and a basis: {r['candidate_id']}")
        kind = r.get("detection_kind", "log_or_symptom")
        if kind not in DETECTION_KINDS:
            raise ValueError(f"Unknown detection_kind: {r['candidate_id']}")
        if r.get("review_status", "PENDING_HUMAN_REVIEW") != "PENDING_HUMAN_REVIEW":
            raise ValueError(f"Only PENDING_HUMAN_REVIEW is allowed: {r['candidate_id']}")
        from backend.domain.knowledge.catalog_adapter import validate_operational_fields
        field_problems = validate_operational_fields(r.get("operational_fields"))
        if field_problems:
            raise ValueError(f"Invalid operational_fields for {r['candidate_id']}: {field_problems}")
        if kind in STATE_KINDS:
            sigs = r.get("detection_signals")
            if (not isinstance(sigs, list) or not sigs or any(not isinstance(s, dict) or not s.get("source") or not s.get("fields") for s in sigs)
                    or not isinstance(r.get("false_positive_risks"), list) or not r["false_positive_risks"]
                    or not str(r.get("validation_method", "")).strip() or "documented_thresholds" not in r):
                raise ValueError(f"State candidate needs detection_signals, false_positive_risks, validation_method and documented_thresholds: {r['candidate_id']}")
            if r["parser_mapping"] == "state_telemetry_evaluator":
                from backend.domain.analyzer.services import state_diagnostics

                if not callable(getattr(state_diagnostics, str(r.get("evaluator", "")), None)):
                    raise ValueError(f"Unknown evaluator: {r['candidate_id']}")
            if r["parser_mapping"] in ("parser_linked_by_sqlstate", "parser_linked_by_message", "parser_linked_by_fields"):
                raise ValueError(f"State candidates must not claim a log parser mapping: {r['candidate_id']}")
        if r["parser_mapping"] == "parser_linked_by_fields":
            cond = r.get("field_conditions")
            if (not isinstance(cond, dict) or not cond or not str(r.get("field_mapping_basis", "")).strip()
                    or any(not (isinstance(v, str) or (isinstance(v, list) and v and all(isinstance(i, str) for i in v))) for v in cond.values())):
                raise ValueError(f"field link needs field_conditions and a basis: {r['candidate_id']}")
        if r["parser_mapping"] == "parser_linked_by_message":
            from backend.domain.analyzer.services.parser import PG_DOCUMENTED_MESSAGE_KEYS

            keys = r.get("documented_messages")
            if (not isinstance(keys, list) or not keys or not str(r.get("message_mapping_basis", "")).strip()
                    or any(k not in PG_DOCUMENTED_MESSAGE_KEYS for k in keys)):
                raise ValueError(f"message link needs parser-known keys and a basis: {r['candidate_id']}")
        if r["candidate_id"] in seen:
            raise ValueError(f"Duplicate candidate {r['candidate_id']}")
        seen.add(r["candidate_id"])
        out.append(r)
    return out


DIAGNOSTIC_CANDIDATES = load_diagnostic_candidates()


def diagnostic_candidate_summary(records=None) -> dict:
    records = DIAGNOSTIC_CANDIDATES if records is None else records

    def by(key):
        return dict(sorted(Counter(r[key] for r in records).items()))

    return {"total_records": len(records), "by_vendor": by("vendor"), "by_product": by("product"),
            "by_problem_domain": by("problem_domain"), "by_parser_mapping": by("parser_mapping"),
            "by_evidence_maturity": by("evidence_maturity"),
            "unique_sources": len({s["url"] for r in records for s in r["official_sources"]}),
            "source_verified": 0, "validated": 0, "approved": 0}


def candidate_for_sqlstate(code: str) -> dict | None:
    """Diagnostic candidate linked to a PostgreSQL SQLSTATE (the parser supplies the code; nothing is inferred)."""
    for r in DIAGNOSTIC_CANDIDATES:
        if r["parser_mapping"] == "parser_linked_by_sqlstate" and str(code) in r.get("sqlstate_codes", []):
            return r
    return None


def candidate_for_message(key: str) -> dict | None:
    """Diagnostic candidate linked to a documented server message the parser recognised verbatim."""
    for r in DIAGNOSTIC_CANDIDATES:
        if r["parser_mapping"] == "parser_linked_by_message" and key in r.get("documented_messages", []):
            return r
    return None


def candidate_for_fields(attributes: dict) -> dict | None:
    """Candidate whose documented log-field conditions all hold for the parsed attributes (values compared case-insensitively)."""
    attrs = {str(k): str(v).strip().strip('"').lower() for k, v in (attributes or {}).items() if v is not None}
    for r in DIAGNOSTIC_CANDIDATES:
        if r["parser_mapping"] != "parser_linked_by_fields":
            continue
        ok = True
        for key, want in r["field_conditions"].items():
            allowed = [w.lower() for w in (want if isinstance(want, list) else [want])]
            if attrs.get(key) not in allowed:
                ok = False
                break
        if ok:
            return r
    return None
