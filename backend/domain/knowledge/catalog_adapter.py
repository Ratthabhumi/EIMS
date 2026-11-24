"""Catalog -> operational knowledge adapter.

Two jobs, both read-only with respect to the catalogs:

1. ``operational_view``: the engineer-facing answer for one catalog record - what happened, why, what to inspect, what to do,
   risk, rollback, how to prove recovery, evidence and limitations. Every item states whether the catalog actually *states*
   it ("stated") or not ("not_stated"); nothing is invented to fill a gap.
2. ``evaluate``: the import eligibility of a record, per certification class. Eligible only means "may be registered for human
   review"; nothing here approves, verifies or validates anything.

Why not ``KnowledgeEntry``: that table stores knowledge derived from one analysed case (``source_history_id`` is a NOT NULL
foreign key to ``analysis_history``). Importing a catalog row would need a fabricated case. The catalogs are canonical content;
lifecycle lives in the governance overlay (``knowledge_review``) which the Analyzer already consults. "Import" therefore means
registering the record in that overlay with an audit event.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from backend.domain.knowledge.remediation_safety import DESTRUCTIVE_ACTION_POLICY, destructive_actions

STATUSES = ("ELIGIBLE", "INELIGIBLE", "BLOCKED", "NEEDS_HUMAN_REVIEW", "ALREADY_IMPORTED", "STALE_SOURCE")
CLASSES = {"A": "windows operational context", "B": "parser-linked diagnostic candidate", "C": "parser-mapped technical reference",
           "D": "state/telemetry reference", "E": "unmapped diagnostic candidate", "F": "reference-only"}
APPROVAL_SCOPES = {"B": "approved_as_diagnostic", "C": "approved_as_reference", "D": "approved_as_state_reference",
                   "E": "approved_as_reference", "F": "approved_as_reference"}
_NOT_STATED = re.compile(r"^\s*(?:not stated|not documented|none stated|none\b|n/a|unknown)", re.I)


def stated(value: Any) -> bool:
    """A field counts only when it carries content, not a 'Not stated' placeholder."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and not _NOT_STATED.match(value)
    if isinstance(value, (list, tuple)):
        return any(stated(v) for v in value)
    if isinstance(value, dict):
        return any(stated(v) for v in value.values())
    return True


def classify(kind: str, raw: dict) -> str:
    """Certification class A-F (mirrors the certification register; a test keeps the two in step)."""
    if kind == "windows":
        return "A"
    if kind == "legacy":
        return "B"
    if kind == "reference":
        return "C" if raw.get("parser_mapping") == "parser_mapped" else "F"
    if raw.get("detection_kind") in ("state_telemetry", "cli_state"):
        return "D"
    return "B" if str(raw.get("parser_mapping", "")).startswith("parser_linked_") else "E"


# ---- optional structured operational fields (candidate records and draft/approved supplements) -------------------------------------
FIELD_NAMES = ("required_permission", "human_approval_required", "rollback_steps", "verification_steps", "recovery_evidence",
               "recovery_success_criteria", "operational_impact", "destructive_risk")
FIELD_STATES = ("stated", "not_stated", "unverified")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def validate_operational_fields(block: Any) -> list[str]:
    """Problems in an ``operational_fields`` block (empty list = valid). Rules:

    * ``stated``: non-empty ``items`` AND a source with an https ``url``, a verbatim ``quote`` and a ``retrieved`` date - the statement must
      be traceable to an official page;
    * ``unverified``: non-empty ``items`` and a ``basis`` explaining where it comes from (never presented as confirmed);
    * ``not_stated``: no items and a ``reason`` (what was searched). Empty strings or generic placeholders are not evidence.
    """
    if block is None:
        return []
    if not isinstance(block, dict):
        return ["operational_fields must be an object"]
    problems: list[str] = []
    for name, entry in block.items():
        if name not in FIELD_NAMES:
            problems.append(f"{name}: unknown field")
            continue
        if not isinstance(entry, dict) or entry.get("state") not in FIELD_STATES:
            problems.append(f"{name}: state must be one of {FIELD_STATES}")
            continue
        state, items = entry["state"], entry.get("items", [])
        if state == "not_stated":
            if items:
                problems.append(f"{name}: not_stated must have no items")
            if not str(entry.get("reason", "")).strip():
                problems.append(f"{name}: not_stated needs a reason (what was searched)")
            continue
        if not isinstance(items, list) or not items or not all(isinstance(i, str) and len(i.strip()) >= 3 and not _NOT_STATED.match(i) for i in items):
            problems.append(f"{name}: {state} needs non-empty, non-placeholder items")
        if state == "unverified" and not str(entry.get("basis", "")).strip():
            problems.append(f"{name}: unverified needs a basis")
        if state == "stated":
            src = entry.get("source") or {}
            if not (isinstance(src.get("url"), str) and src["url"].startswith("https://")):
                problems.append(f"{name}: stated needs an https source url")
            if not str(src.get("quote", "")).strip():
                problems.append(f"{name}: stated needs a verbatim source quote")
            if not _ISO_DATE.match(str(src.get("retrieved", ""))):
                problems.append(f"{name}: stated needs a retrieved date (YYYY-MM-DD)")
    return problems


def _from_block(block: dict | None, name: str) -> dict | None:
    entry = (block or {}).get(name)
    if not isinstance(entry, dict) or entry.get("state") not in ("stated", "unverified"):
        return None
    out = {"status": entry["state"], "items": [str(i) for i in entry.get("items", [])]}
    src = entry.get("source") or {}
    if src.get("url"):
        out["source"] = src["url"]
    if entry.get("state") == "unverified":
        out["basis"] = entry.get("basis", "")
    return out


def _pick(block: dict | None, name: str, fallback: dict) -> dict:
    """Structured block first (it carries provenance); the legacy top-level field is the fallback. Unverified never counts as stated."""
    structured = _from_block(block, name)
    if structured and (structured["status"] == "stated" or fallback["status"] != "stated"):
        return structured
    return fallback


def _item(values: Any, source: str = "") -> dict:
    items = [v for v in (values if isinstance(values, (list, tuple)) else [values]) if stated(v)]
    return {"status": "stated" if items else "not_stated", "items": [str(v) for v in items], **({"source": source} if source and items else {})}


def operational_view(kind: str, raw: dict) -> dict:
    """Seven-section engineer view of a catalog record (candidates, legacy diagnostics, references, Windows context)."""
    if kind == "legacy":
        g = raw.get("diagnostic_guidance") or {}
        what = raw.get("title", "") + (": " + raw["description"] if raw.get("description") else "")
        why = _item(raw.get("description"))
        inspect = _item(list(raw.get("investigation_steps", [])) + list(g.get("expected_findings") or []))
        action = _item(g.get("safe_remediation"))
        risk, rollback = _item(g.get("risk")), _item(g.get("rollback"))
        recovery = _item(g.get("verification_criteria"))
        sources = [{"title": r.get("title", r["url"]), "url": r["url"], "scope": r.get("scope", "")} for r in raw.get("official_references", [])]
        limits = [raw.get("limitations", "")]
        version = raw.get("compatibility_scope", "")
        maturity = raw.get("support_level", "")
    elif kind == "candidate":
        what = raw.get("symptom", "")
        why = _item(list(raw.get("likely_causes", [])) + ["Alternative: " + a for a in raw.get("alternative_causes", []) if stated(a)])
        inspect = _item(list(raw.get("diagnostic_steps", [])) + [f"{c['command']} -> {c['expected_evidence']}" for c in raw.get("diagnostic_commands", [])])
        block = raw.get("operational_fields")
        action = _item(raw.get("remediation"))
        risk = _item(raw.get("operational_risk"))
        rollback = _pick(block, "rollback_steps", _item(raw.get("rollback_steps")))
        recovery = _pick(block, "verification_steps", _item(raw.get("verification_steps")))
        extras = {k: _pick(block, k, _item(None)) for k in ("required_permission", "human_approval_required", "recovery_evidence",
                                                              "recovery_success_criteria", "operational_impact", "destructive_risk")}
        sources = [{"title": s["title"], "url": s["url"], "scope": s.get("scope", "")} for s in raw.get("official_sources", [])]
        limits = [raw.get("limitations", "")] + list(raw.get("false_positive_risks", []))
        version = raw.get("version_scope", "")
        maturity = raw.get("evidence_maturity", "")
    elif kind == "reference":
        src = raw.get("source") or {}
        what = f"{raw.get('code', '')} {raw.get('name', '')}".strip()
        why, inspect, action = _item(raw.get("description")), _item(None), _item(None)
        risk, rollback, recovery = _item(None), _item(None), _item(None)
        sources = [{"title": src.get("title", ""), "url": src.get("url", ""), "scope": ""}] if src.get("url") else []
        limits, version, maturity = [raw.get("limitations", "")], raw.get("version_scope", ""), raw.get("evidence_maturity", "")
    else:  # windows operational context
        what = raw.get("title", "") + (": " + raw["description"] if raw.get("description") else "")
        why, inspect, action = _item(raw.get("operator_context")), _item(raw.get("related_events")), _item(None)
        risk, rollback, recovery = _item(None), _item(None), _item(None)
        sources = [{"title": r.get("title", r["url"]), "url": r["url"], "scope": r.get("scope", "")} for r in raw.get("official_references", [])]
        limits = []
        version = (raw.get("applicability") or {}).get("statement", "")
        maturity = ""
    actions = destructive_actions(action["items"])
    if kind != "candidate":
        extras = {k: _item(None) for k in ("required_permission", "human_approval_required", "recovery_evidence",
                                           "recovery_success_criteria", "operational_impact", "destructive_risk")}
    if actions and extras["human_approval_required"]["status"] != "stated":
        extras = dict(extras, human_approval_required={"status": "stated", "items": [DESTRUCTIVE_ACTION_POLICY],
                                                        "source": "EIMS policy (remediation_safety.DESTRUCTIVE_ACTION_POLICY)", "origin": "eims_policy"})
    return {
        "whatHappened": what,
        "why": why, "inspect": inspect, "recommendedAction": action, "risk": risk, "rollback": rollback, "recoveryVerification": recovery,
        "requiredPermission": extras["required_permission"], "humanApproval": extras["human_approval_required"],
        "recoveryEvidence": extras["recovery_evidence"], "recoverySuccessCriteria": extras["recovery_success_criteria"],
        "operationalImpact": extras["operational_impact"], "destructiveRisk": extras["destructive_risk"],
        "evidenceAndSource": sources, "versionScope": version,
        "confidenceLimitations": {"maturity": maturity, "limitations": [x for x in limits if stated(x)]},
        "destructiveActions": actions,
    }


def operational_problems(view: dict) -> list[str]:
    """What an engineer still lacks before this record can be used (empty list = every required item is stated)."""
    problems = []
    if not view["whatHappened"].strip():
        problems.append("what_happened")
    if not view["versionScope"].strip():
        problems.append("version_scope")
    if not view["evidenceAndSource"]:
        problems.append("source")
    for key, label in (("inspect", "investigation"), ("recommendedAction", "recommended_action"), ("risk", "risk"), ("recoveryVerification", "recovery_verification")):
        if view[key]["status"] != "stated":
            problems.append(label)
    if view["destructiveActions"]:
        if view["rollback"]["status"] != "stated":
            problems.append("rollback_for_destructive_action")
        if view["requiredPermission"]["status"] != "stated":
            problems.append("required_permission_for_destructive_action")
        if view["humanApproval"]["status"] != "stated":
            problems.append("human_approval_requirement_for_destructive_action")
    return problems


_VIEW_KEYS = {"required_permission": "requiredPermission", "human_approval_required": "humanApproval", "rollback_steps": "rollback",
              "verification_steps": "recoveryVerification", "recovery_evidence": "recoveryEvidence",
              "recovery_success_criteria": "recoverySuccessCriteria", "operational_impact": "operationalImpact", "destructive_risk": "destructiveRisk"}


def supplement_view_fields(supplement: dict) -> dict[str, dict]:
    """Stated, source-backed fields of an approved supplement keyed by view key (unverified fields are never merged into active guidance)."""
    out = {}
    for name, key in _VIEW_KEYS.items():
        entry = (supplement or {}).get(name)
        if isinstance(entry, dict) and entry.get("state") == "stated" and not validate_operational_fields({name: entry}):
            out[key] = {"status": "stated", "items": [str(i) for i in entry["items"]], "source": entry["source"]["url"], "origin": "approved_supplement"}
    return out


def merge_supplement(view: dict, supplement: dict) -> dict:
    """Overlay the stated fields of a human-approved supplement on a catalog view; catalog statements are never replaced by it."""
    merged = dict(view)
    for key, value in supplement_view_fields(supplement).items():
        if view.get(key, {}).get("status") != "stated":
            merged[key] = value
    merged["destructiveActions"] = view["destructiveActions"]
    return merged


@dataclass
class ImportContext:
    """Facts the caller knows and the pure adapter cannot (kept outside backend code: certification evidence lives in docs/)."""
    evidence_current: bool | None = None          # bound positive+negative evidence exists and matches the current content hash
    open_findings: tuple[str, ...] = field(default_factory=tuple)   # validator finding codes that need a human decision
    overlay_hash: str | None = None               # content hash recorded in the governance overlay, if the record was imported


def evaluate(kind: str, raw: dict, content_hash: str, ctx: ImportContext) -> dict:
    cls = classify(kind, raw)
    view = operational_view(kind, raw)
    out = {"class": cls, "class_name": CLASSES[cls], "content_hash": content_hash, "approval_scope_if_approved": APPROVAL_SCOPES.get(cls),
           "status": "", "reasons": [], "missing": []}
    if ctx.overlay_hash is not None:
        out["status"] = "ALREADY_IMPORTED" if ctx.overlay_hash == content_hash else "STALE_SOURCE"
        out["reasons"] = ["registered in the governance overlay with the same content hash"] if out["status"] == "ALREADY_IMPORTED" else [
            "the catalog content changed after registration; run sync and re-review before anything else"]
        return out
    if cls == "A":
        out.update(status="INELIGIBLE", reasons=["Windows operational context is not diagnostic knowledge; governance allows it to reach 'candidate' only"])
    elif cls in ("C", "F"):
        out.update(status="INELIGIBLE", reasons=["reference-only definition: it must not be presented as a diagnostic capability"])
    elif cls == "E":
        out.update(status="INELIGIBLE", reasons=["unmapped candidate: no parser or evaluator exists, so it cannot be a diagnostic capability"])
    elif cls == "D":
        out.update(status="BLOCKED", reasons=["state/telemetry reference: no live collector or API supplies the input"], missing=["live_collector"])
        if ctx.evidence_current is not True:
            out["missing"].append("real_source_technical_evidence")
    else:  # B
        missing = operational_problems(view)
        if ctx.evidence_current is not True:
            missing.append("current_bound_technical_evidence")
        if missing:
            out.update(status="BLOCKED", reasons=["required operational or evidence items are missing"], missing=missing)
        elif ctx.open_findings:
            out.update(status="NEEDS_HUMAN_REVIEW", reasons=["open validator findings need a human decision: " + ", ".join(sorted(set(ctx.open_findings)))])
        else:
            out.update(status="ELIGIBLE", reasons=["every required item is stated and technical evidence is current; eligible to be registered for human review (not approved)"])
    return out
