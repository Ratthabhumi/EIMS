"""Read-only Knowledge Quality audit for delivery closure (no mutations)."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.domain.knowledge.catalog_adapter import classify, operational_problems, operational_view
from backend.domain.knowledge.service import _catalog, catalog_kind
from backend.domain.knowledge.unified_catalog import clear_caches, compute_totals, identity_evidence

VIEW_FIELDS = (
    "whatHappened",
    "why",
    "inspect",
    "recommendedAction",
    "risk",
    "rollback",
    "recoveryVerification",
)


def _field_ok(name: str, value) -> bool:
    if name == "whatHappened":
        return isinstance(value, str) and bool(value.strip())
    return isinstance(value, dict) and value.get("status") == "stated"


def main() -> None:
    clear_caches()
    identity = identity_evidence()
    totals = compute_totals()
    gov = _catalog()

    by_class_field = defaultdict(Counter)
    class_counts = Counter()
    problem_examples: list[dict] = []
    engineer_ready = 0  # what+inspect+action stated
    full_verify_chain = 0  # what+why+inspect+action+risk+verify stated
    asa = None

    for cid, entry in gov.items():
        kind = catalog_kind(cid)
        cls = classify(kind, entry)
        class_counts[cls] += 1
        view = operational_view(kind, entry)
        stated = {f: _field_ok(f, view.get(f)) for f in VIEW_FIELDS}
        for f, ok in stated.items():
            by_class_field[cls][f] += int(ok)
        problems = operational_problems(view)
        if len(problem_examples) < 25 and problems:
            problem_examples.append({"catalog_id": cid, "class": cls, "problems": problems})
        if stated["whatHappened"] and stated["inspect"] and stated["recommendedAction"]:
            engineer_ready += 1
        if all(stated[f] for f in ("whatHappened", "why", "inspect", "recommendedAction", "risk", "recoveryVerification")):
            full_verify_chain += 1
        if cid == "cisco_asa:official_message_id:113005":
            asa = {
                "catalog_id": cid,
                "class": cls,
                "stated": stated,
                "problems": problems,
                "eligibility_note": "ELIGIBLE for human-review registration; not human-approved",
            }

    out = {
        "identity": {
            "governed": identity["governed_count"],
            "analyzer_matchable": identity["analyzer_matchable_count"],
            "other_governed": identity["other_governed_count"],
            "strict_subset": identity["strict_subset"],
            "class_b": identity["cert_class_b_count"],
            "class_b_split": {
                "in_load_catalog": identity["cert_class_b_in_load_catalog"],
                "not_in_load_catalog": identity["cert_class_b_not_in_load_catalog"],
            },
            "eligible": totals["eligible"],
            "human_approved": totals["human_approved"],
            "family_sum_matchable": sum(totals["by_analyzer_source_family"].values()),
        },
        "class_counts": dict(class_counts),
        "stated_field_coverage_by_class": {
            cls: dict(fields) for cls, fields in sorted(by_class_field.items())
        },
        "class_denominators": dict(class_counts),
        "engineer_ready_partial": {
            "count": engineer_ready,
            "definition": "whatHappened + inspect + recommendedAction all status=stated",
            "of": len(gov),
        },
        "full_verify_chain": {
            "count": full_verify_chain,
            "definition": "what+why+inspect+action+risk+recoveryVerification all stated",
            "of": len(gov),
        },
        "asa_113005": asa,
        "problem_examples": problem_examples,
        "priority_gaps": [
            "Most Class A (Windows operational context) intentionally lack diagnostic remediation/verify — not engineer-ready diagnostics.",
            "Class C/F references are definition-only; must not be presented as remediation capabilities.",
            "Class B/E candidates often miss rollback/recoveryVerification — blocks eligibility or safe remediation.",
            "Human-approved remains 0; eligible=1 (ASA 113005) still needs human page review.",
            "Do not bulk-generate knowledge without source provenance.",
        ],
    }
    dest = Path("docs/acceptance/certification/final_delivery_2026-11-24/evidence/knowledge_quality_audit.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({
        "wrote": str(dest),
        "engineer_ready_partial": engineer_ready,
        "full_verify_chain": full_verify_chain,
        "of": len(gov),
        "asa": asa["stated"] if asa else None,
        "class_counts": dict(class_counts),
    }, indent=2))


if __name__ == "__main__":
    main()
