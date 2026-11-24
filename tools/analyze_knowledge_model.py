"""Measure how the current catalogs map onto the operational knowledge model (symptom -> applicability -> diagnosis ->
investigation -> remediation -> recovery verification -> provenance) and where the model has no field at all.

Everything is computed from the catalogs and the certification register; nothing is hand-typed. "Stated" means a field is
present and does not merely say the vendor gave no information ("Not stated...", "None", empty).
Output: docs/acceptance/certification/knowledge_model_mapping.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SERVICES = ROOT / "backend" / "domain" / "analyzer" / "services"
CERT = ROOT / "docs" / "acceptance" / "certification"
NOT_STATED = re.compile(r"^\s*(?:not stated|not documented|none stated|none\b|n/a|unknown)", re.I)

SECTIONS = {
    "A_symptom": "Symptom / observation: what was seen, identity (event id, signature, error code), source system, severity, detection conditions",
    "B_applicability": "Applicability: product, OS/version/build, provider/component, prerequisites, unsupported conditions",
    "C_diagnosis": "Diagnosis: likely cause, alternative causes, evidence per cause, confidence and limitations, false positives",
    "D_investigation": "Investigation: what to inspect, commands/queries, expected and abnormal output, evidence collection",
    "E_remediation": "Remediation: action, preconditions, permission, operational impact, destructive risk, downtime risk, backup/rollback, human approval",
    "F_recovery": "Recovery verification: post-checks, expected healthy state, recovery evidence, resolved criteria, escalation conditions",
    "G_provenance": "Provenance and governance: official source, source version, content hash, technical evidence, human review, approval scope, history",
}
# catalog field -> canonical section (what exists today)
MAPPING = {
    "windows_event (class A)": {
        "A_symptom": ["event_id", "title", "category", "severity", "description", "keywords"],
        "B_applicability": ["provider", "provider_names", "applicability (statement, kind, event_versions, publication)"],
        "C_diagnosis": ["operator_context (free text)"], "D_investigation": ["related_events", "diagnostic_guidance (some records)"],
        "E_remediation": [], "F_recovery": [], "G_provenance": ["official_references", "applicability.source_url", "register: content_hash, readiness"]},
    "legacy diagnostic (class B, 28)": {
        "A_symptom": ["observed_signatures", "relevant_log_fields", "title", "severity", "category", "code_type/diagnostic_code"],
        "B_applicability": ["compatibility_scope", "product"], "C_diagnosis": ["description", "limitations"],
        "D_investigation": ["investigation_steps", "diagnostic_guidance.expected_findings"],
        "E_remediation": ["diagnostic_guidance.safe_remediation", "diagnostic_guidance.risk", "diagnostic_guidance.rollback"],
        "F_recovery": ["diagnostic_guidance.verification_criteria"],
        "G_provenance": ["official_references", "verification_status (legacy label)", "diagnostic_guidance.evidence_basis"]},
    "vendor candidate (classes B/D/E, 72)": {
        "A_symptom": ["symptom", "signatures", "detection_signals", "field_conditions", "sqlstate_codes", "documented_messages"],
        "B_applicability": ["version_scope", "product_family", "problem_domain"],
        "C_diagnosis": ["meaning", "likely_causes", "alternative_causes", "false_positive_risks", "limitations"],
        "D_investigation": ["diagnostic_steps", "diagnostic_commands[].command", "diagnostic_commands[].expected_evidence"],
        "E_remediation": ["remediation", "operational_risk (free text: risk and impact together)"],
        "F_recovery": ["verification_steps"],
        "G_provenance": ["official_sources", "evidence_basis", "evidence_maturity", "review_status", "parser_mapping", "validation_method"]},
    "vendor reference (classes C/F, 658)": {
        "A_symptom": ["code", "name", "code_type"], "B_applicability": ["version_scope", "product"], "C_diagnosis": ["description"],
        "D_investigation": [], "E_remediation": [], "F_recovery": [], "G_provenance": ["source", "parser_mapping"]},
}
# fields the operational model needs that no catalog has as a dedicated field
STRUCTURAL_GAPS = [
    {"section": "E_remediation", "missing_field": "rollback_steps", "today": "free text inside operational_risk (candidates) or diagnostic_guidance.rollback (14 of 28 legacy)"},
    {"section": "E_remediation", "missing_field": "required_permission", "today": "not modelled"},
    {"section": "E_remediation", "missing_field": "operational_impact / downtime_risk", "today": "mixed into operational_risk free text"},
    {"section": "E_remediation", "missing_field": "human_approval_required", "today": "not modelled"},
    {"section": "E_remediation", "missing_field": "preconditions", "today": "not modelled (some appear in prose)"},
    {"section": "F_recovery", "missing_field": "expected_healthy_state", "today": "not modelled"},
    {"section": "F_recovery", "missing_field": "escalation_conditions", "today": "not modelled"},
    {"section": "D_investigation", "missing_field": "abnormal_output (structured)", "today": "expected_evidence prose only"},
    {"section": "C_diagnosis", "missing_field": "evidence_per_cause", "today": "causes are a flat list without a link to evidence"},
    {"section": "B_applicability", "missing_field": "os_build_range / unsupported_conditions (Windows)", "today": "only the new applicability block; 0 records state a build"},
    {"section": "G_provenance", "missing_field": "review history on the catalog record", "today": "governance tables cover 181 loaded records only (Round 1 finding P1)"},
]


def stated(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and not NOT_STATED.match(value)
    if isinstance(value, (list, tuple)):
        return any(stated(v) for v in value)
    if isinstance(value, dict):
        return any(stated(v) for v in value.values())
    return True


def _indicators(kind: str, rec: dict) -> dict[str, bool]:
    if kind == "legacy":
        g = rec.get("diagnostic_guidance") or {}
        return {"symptom": stated(rec.get("observed_signatures")), "applicability": stated(rec.get("compatibility_scope")),
                "cause_listed": stated(rec.get("description")), "alternative_causes": False, "false_positive_risks": False,
                "investigation": stated(rec.get("investigation_steps")), "commands_with_expected_output": False,
                "remediation": stated(g.get("safe_remediation")), "risk_stated": stated(g.get("risk")), "rollback_stated": stated(g.get("rollback")),
                "recovery_verification": stated(g.get("verification_criteria")), "limitations": stated(rec.get("limitations")),
                "source": stated(rec.get("official_references"))}
    if kind == "candidate":
        cmds = rec.get("diagnostic_commands") or []
        return {"symptom": stated(rec.get("symptom")), "applicability": stated(rec.get("version_scope")),
                "cause_listed": stated(rec.get("likely_causes")), "alternative_causes": stated(rec.get("alternative_causes")),
                "false_positive_risks": stated(rec.get("false_positive_risks")),
                "investigation": stated(rec.get("diagnostic_steps")), "commands_with_expected_output": any(stated(c.get("command")) and stated(c.get("expected_evidence")) for c in cmds),
                "remediation": stated(rec.get("remediation")), "risk_stated": stated(rec.get("operational_risk")), "rollback_stated": False,
                "recovery_verification": stated(rec.get("verification_steps")), "limitations": stated(rec.get("limitations")),
                "source": stated(rec.get("official_sources"))}
    if kind == "windows":
        return {"symptom": stated(rec.get("description")), "applicability": isinstance(rec.get("applicability"), dict),
                "cause_listed": stated(rec.get("operator_context")), "alternative_causes": False, "false_positive_risks": False,
                "investigation": stated(rec.get("diagnostic_guidance")), "commands_with_expected_output": False, "remediation": False,
                "risk_stated": False, "rollback_stated": False, "recovery_verification": False, "limitations": False,
                "source": stated(rec.get("official_references"))}
    return {"symptom": stated(rec.get("name") or rec.get("code")), "applicability": stated(rec.get("version_scope")), "cause_listed": stated(rec.get("description")),
            "alternative_causes": False, "false_positive_risks": False, "investigation": False, "commands_with_expected_output": False,
            "remediation": False, "risk_stated": False, "rollback_stated": False, "recovery_verification": False, "limitations": False,
            "source": stated(rec.get("source"))}


def to_knowledge_content(kind: str, rec: dict) -> dict:
    """Map a catalog record onto the engineer-facing ``KnowledgeProposalContent`` (the contract of the existing KnowledgeEntry workflow).
    Nothing is invented: ``risk_level`` is only 'high' when the remediation names a state-changing action (the strictest reading) and
    'medium' otherwise; ``product_version`` is left empty because the contract allows 64 characters and catalog scopes are longer."""
    from backend.domain.knowledge.remediation_safety import destructive_actions
    if kind == "legacy":
        g = rec.get("diagnostic_guidance") or {}
        steps = [x for x in (g.get("safe_remediation") or []) if stated(x)] or [x for x in rec.get("investigation_steps", []) if stated(x)]
        remediation = [x for x in (g.get("safe_remediation") or []) if stated(x)]
        data = {"title": rec["title"], "root_cause": rec["description"], "solution_steps": steps, "impact": str(g.get("risk") or "")[:2000],
                "product_name": rec.get("product"), "validation_steps": [x for x in (g.get("verification_criteria") or []) if stated(x)],
                "rollback_steps": [str(g["rollback"])] if stated(g.get("rollback")) else [],
                "evidence_notes": [str(g.get("evidence_basis") or rec.get("limitations") or "")],
                "references": [r["url"] for r in rec.get("official_references", [])][:10]}
    else:
        remediation = [x for x in rec.get("remediation", []) if stated(x)]
        steps = remediation or [x for x in rec.get("diagnostic_steps", []) if stated(x)]
        data = {"title": rec["candidate_id"], "root_cause": rec["meaning"], "solution_steps": steps, "impact": rec.get("operational_risk", "")[:2000] if stated(rec.get("operational_risk")) else "",
                "product_name": rec.get("product"), "validation_steps": [x for x in rec.get("verification_steps", []) if stated(x)], "rollback_steps": [],
                "evidence_notes": [rec.get("evidence_basis", "")], "references": [s_["url"] for s_ in rec.get("official_sources", [])][:10]}
    data["resolution_status"] = "unresolved"  # a catalog entry is guidance, not a resolved case
    data["risk_level"] = "high" if destructive_actions(remediation) else "medium"
    data["evidence_notes"] = [x[:1000] for x in data["evidence_notes"] if x and x.strip()]
    return data


def contract_check(kind: str, rec: dict) -> list[str]:
    """Reasons the record cannot yet enter the engineer-facing KnowledgeEntry contract (empty list = it validates)."""
    from pydantic import ValidationError
    from backend.api.routers.analyzer.knowledge import KnowledgeProposalContent
    try:
        KnowledgeProposalContent(**to_knowledge_content(kind, rec))
    except ValidationError as exc:
        return sorted({f"{'.'.join(str(x) for x in e['loc'])}: {e['msg'][:80]}" for e in exc.errors()})
    return []


def analyze() -> dict:
    register = json.loads((CERT / "register.json").read_text(encoding="utf-8"))
    cls = {r["record_key"]: r["cert_class"] for r in register["records"]}
    sources = {
        "windows": json.loads((SERVICES / "operational_event_catalog.json").read_text(encoding="utf-8")),
        "legacy": json.loads((SERVICES / "diagnostic_knowledge_catalog.json").read_text(encoding="utf-8"))["entries"],
        "candidate": json.loads((SERVICES / "vendor_diagnostic_catalog.json").read_text(encoding="utf-8"))["records"],
        "reference": json.loads((SERVICES / "vendor_reference_catalog.json").read_text(encoding="utf-8"))["records"],
    }
    from tools.build_certification_register import _identity
    catalog_name = {"windows": "operational", "legacy": "diagnostic_legacy", "candidate": "candidate", "reference": "reference"}
    per_class: dict[str, Counter] = defaultdict(Counter)
    complete: list[dict] = []
    contract: dict[str, dict] = defaultdict(lambda: {"records": 0, "validates": 0, "reasons": Counter()})
    for kind, rows in sources.items():
        for rec in rows:
            key = f"{catalog_name[kind]}:{_identity(rec, catalog_name[kind])}"
            c = cls[key]
            ind = _indicators(kind, rec)
            per_class[c]["records"] += 1
            for name, ok in ind.items():
                per_class[c][name] += bool(ok)
            if c in ("B", "D", "E"):
                reasons = contract_check(kind, rec)
                contract[c]["records"] += 1
                contract[c]["validates"] += not reasons
                contract[c]["reasons"].update(reasons)
                core = ["symptom", "applicability", "cause_listed", "investigation", "remediation", "risk_stated", "recovery_verification", "source"]
                complete.append({"record_key": key, "class": c, "present": [n for n in core if ind[n]], "missing_or_not_stated": [n for n in core if not ind[n]],
                                 "rollback_stated": ind["rollback_stated"], "complete_for_engineer_use": all(ind[n] for n in core) and not reasons,  # destructive remediation also needs rollback + validation
                                 "knowledge_entry_contract_blockers": reasons})
    summary = {c: dict(v) for c, v in sorted(per_class.items())}
    by_class_complete = {c: {"records": sum(1 for r in complete if r["class"] == c), "complete_for_engineer_use": sum(r["complete_for_engineer_use"] for r in complete if r["class"] == c)}
                         for c in ("B", "D", "E")}
    return {"schema_version": 1, "note": "Computed from the catalogs. 'Stated' excludes 'Not stated' placeholders. Not a certification.",
            "sections": SECTIONS, "current_mapping": MAPPING, "structural_gaps": STRUCTURAL_GAPS, "coverage_by_class": summary,
            "engineer_use_completeness": by_class_complete,
            "knowledge_entry_contract": {c: {"records": v["records"], "validates_unchanged": v["validates"], "blockers": dict(v["reasons"].most_common())} for c, v in sorted(contract.items())},
            "records_b_d_e": sorted(complete, key=lambda r: r["record_key"])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=CERT / "knowledge_model_mapping.json")
    args = parser.parse_args(argv)
    result = analyze()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"engineer_use_completeness": result["engineer_use_completeness"], "knowledge_entry_contract": result["knowledge_entry_contract"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
