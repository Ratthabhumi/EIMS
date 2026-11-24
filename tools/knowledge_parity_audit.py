"""Field-level parity audit: event_knowledge.json (legacy, 39 records) vs the canonical operational catalog.

Writes docs/acceptance/evidence/knowledge_parity_matrix_<date>.json and prints a Markdown matrix. Classification per
field: exact | corrected (canonical text deliberately differs) | missing_in_canonical | missing_in_legacy |
not_applicable. Record-count equality is never used as proof.
"""
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from backend.domain.analyzer.services import event_knowledge as ek
from backend.domain.analyzer.services.operational_catalog import WINDOWS_BY_EVENT_ID, resolve_windows_entry

LEGACY = json.loads(Path("backend/domain/analyzer/services/event_knowledge.json").read_text(encoding="utf-8"))
NON_WINDOWS = {"KAVT0000", "KAVT0245-E"}
CORRECTED = {"5011", "109"}
LEGACY_FIELDS = ("overview", "causes", "steps")
CANONICAL_ONLY = ("risk", "rollback", "verification_criteria", "expected_findings", "diagnostic_checks")


def classify(eid):
    row = {"event_id": eid, "legacy_providers": LEGACY[eid].get("provider_names", []), "fields": {}}
    if eid in NON_WINDOWS:
        row.update(canonical_id=None, verdict="UNRESOLVED_EXCEPTION",
                   note="Hitachi JP1 message ID: vendor family/product/source not established; stays in the legacy "
                        "compatibility layer, not migrated, nothing fabricated.")
        return row
    entry = next((resolve_windows_entry(eid, p)["entry"] for p in LEGACY[eid]["provider_names"]
                  if resolve_windows_entry(eid, p)["basis"] == "provider_and_id"), None)
    if entry is None:
        row.update(canonical_id=None, verdict="MISSING_IN_CANONICAL")
        return row
    guidance = entry.get("diagnostic_guidance") or {}
    carried = guidance.get("localized_summary") or {}
    row["canonical_id"] = entry["catalog_id"]
    row["canonical_provider"] = entry.get("provider")
    row["canonical_provider_names"] = entry.get("provider_names")
    row["status"] = {"knowledge_class": entry.get("knowledge_class"), "lifecycle_status": entry.get("lifecycle_status"),
                     "verification_status": entry.get("verification_status")}
    row["official_references"] = len(entry.get("official_references") or [])
    row["evidence_basis"] = guidance.get("evidence_basis", "")[:160]
    for lang in ("th", "en"):
        for field in LEGACY_FIELDS:
            want, have = LEGACY[eid].get(lang, {}).get(field), (carried.get(lang) or {}).get(field)
            if have is None:
                verdict = "missing_in_canonical"
            elif eid in CORRECTED and field == "overview":
                verdict = "corrected"
            else:
                verdict = "exact" if have == (want if want is not None else ([] if field != "overview" else "")) else "conflicting"
            row["fields"][f"{lang}.{field}"] = verdict
    for field in CANONICAL_ONLY:
        row["fields"][field] = "missing_in_legacy"  # legacy never had these; canonical carries them only where sourced
    row["verdict"] = ("EQUIVALENT_WITH_CORRECTION" if eid in CORRECTED else
                      "EXACT" if all(v == "exact" for k, v in row["fields"].items() if k.split(".")[-1] in LEGACY_FIELDS) else "CONFLICT")
    # behaviour parity: provider matching must not be broader than the legacy rule
    wrong = ek.get_curated_summary(eid, "en", "Another Provider")
    row["foreign_provider_blocked"] = wrong is None
    row["unqualified_provider_behaviour_equal"] = (
        (ek.get_curated_summary(eid, "en", "") is None) == (ek._legacy_curated_summary(eid, "en", "") is None))
    return row


def main():
    rows = [classify(e) for e in sorted(LEGACY)]
    out = Path(f"docs/acceptance/evidence/knowledge_parity_matrix_{datetime.now(UTC):%Y%m%d}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"legacy_records": len(LEGACY), "canonical_windows_ids": len(WINDOWS_BY_EVENT_ID), "rows": rows},
                              indent=1, ensure_ascii=False), encoding="utf-8")
    summary = {}
    for row in rows:
        summary[row["verdict"]] = summary.get(row["verdict"], 0) + 1
    print("| Event ID | Canonical record | Providers | Verdict | Foreign provider blocked | Status |")
    print("|---|---|---|---|---|---|")
    for row in rows:
        print(f"| {row['event_id']} | {row.get('canonical_id') or '-'} | {', '.join(row['legacy_providers']) or '-'} | "
              f"{row['verdict']} | {row.get('foreign_provider_blocked', '-')} | "
              f"{(row.get('status') or {}).get('lifecycle_status', '-')} |")
    print("\nSUMMARY", json.dumps(summary), "->", out, file=sys.stderr)


if __name__ == "__main__":
    main()
