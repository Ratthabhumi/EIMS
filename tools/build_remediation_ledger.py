"""Build remediation_research_ledger.json: the per-record outcome for the records the engineer-facing KnowledgeEntry contract rejected.

Inputs: knowledge_model_mapping.json (current contract blockers), remediation_research_candidates.json (raw verbatim keyword sentences
from the cited vendor pages, produced by tools/research_remediation_sources.py) and the curated notes below (sentences read by a person
or an AI assistant in the session; they are *noted*, not adopted: adoption needs a human review of the page).

Outcome vocabulary: RESOLVED_RULE_DEFECT (the record only prohibits an action), MANUAL_REVIEW_REQUIRED (the vendor page cannot be
fetched automatically and is not bypassed), BLOCKED (no explicit rollback/verification statement was found in the cited source).
No remediation, rollback or verification text was written from memory; nothing here changes a catalog record.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SERVICES = ROOT / "backend" / "domain" / "analyzer" / "services"
CERT = ROOT / "docs" / "acceptance" / "certification"

# Verbatim sentences read on the cited pages during this review. They are evidence leads for a human reviewer, not adopted content.
NOTES = {
    "candidate:microsoft-hyper-v:vm:fails-to-migrate-start-or-inaccessible": [
        {"category": "backup", "sentence": "Back up and, if needed, delete or rename the .vmcx and .vmrs files.",
         "note": "explicit vendor backup step before the destructive VM-definition removal; no rollback/restore procedure or post-check is stated on the page"}],
    "candidate:fortinet-fortios:ha:split-brain-or-formation-failure": [
        {"category": "verification-in-diagnosis", "sentence": "Verify that the HA configurations match between the HA members.",
         "note": "a diagnostic check, not a post-remediation recovery criterion; the page gives no expected healthy output"}],
    "candidate:postgresql:vacuum:xid-wraparound-warning-or-refusal": [
        {"category": "caution", "sentence": "Contrary to what the hint states, it is not necessary or desirable to stop the postmaster or enter single user-mode in order to restore normal operation.",
         "note": "a prohibition already reflected in the record; the page states no rollback for dropping slots or terminating sessions and no verification query"}],
    "candidate:postgresql:server:administrator-shutdown-or-terminate": [
        {"category": "caution", "sentence": "It is best not to use SIGKILL to shut down the server.",
         "note": "risk statement already in the record; no recovery verification on the page"}],
}


def build() -> dict:
    mapping = json.loads((CERT / "knowledge_model_mapping.json").read_text(encoding="utf-8"))["records_b_d_e"]
    raw = {r["record_key"]: r for r in json.loads((CERT / "remediation_research_candidates.json").read_text(encoding="utf-8"))["records"]}
    now_blocked = {r["record_key"]: r for r in mapping if r["knowledge_entry_contract_blockers"]}
    out = []
    curated = json.loads((CERT / "remediation_fields_curated.json").read_text(encoding="utf-8"))["records"] if (CERT / "remediation_fields_curated.json").exists() else {}
    elig = {r["record_key"]: r for r in json.loads((CERT / "catalog_import_eligibility.json").read_text(encoding="utf-8"))["records"]}
    for key, r in sorted(raw.items()):
        row = {"record_key": key, "class": r["class"], "official_source_urls": [p["url"] for p in r["pages"]],
               "remediation_in_record": r["remediation_in_record"], "vendor_statements_noted": NOTES.get(key, []),
               "candidate_sentence_counts": {k: len(v) for p in r["pages"] for k, v in p["statements"].items()},
               "evidence_reference": "remediation_research_candidates.json (raw keyword sentences, unreviewed)"}
        if key not in now_blocked:
            row.update(disposition="RESOLVED_RULE_DEFECT", missing=[], reason="the remediation text only prohibits the action ('Do not ...'); the earlier keyword rule counted the verb "
                       "as an instruction. The negation-aware rule (backend/domain/knowledge/remediation_safety.py) no longer flags it.", remaining_blocker="")
        elif r["disposition"] == "MANUAL_REVIEW_REQUIRED":
            row.update(disposition="MANUAL_REVIEW_REQUIRED", missing=["rollback", "post_action_verification", "expected_healthy_output"],
                       reason="the vendor page refuses automated retrieval (HTTP 403); it is not bypassed", remaining_blocker="a person must read the cited page and decide what it states")
        else:
            row.update(disposition="BLOCKED", missing=["rollback", "post_action_verification", "expected_healthy_output"],
                       reason="the cited source was fetched and scanned; it contains no explicit rollback or post-action verification statement for this remediation "
                              "(keyword hits are generic and unreviewed)", remaining_blocker="a vendor source that states rollback and verification, or a human decision to accept the record as reference-only")
        if key in curated:
            row["operational_fields_added"] = {name: entry["state"] for name, entry in curated[key].items()}
            row["fields_source"] = "remediation_fields_curated.json (stated fields re-verified verbatim against the live official page by tools/apply_remediation_fields.py)"
            if row["disposition"] == "BLOCKED":
                row["disposition"] = "PARTIAL_EVIDENCE_ADDED_STILL_BLOCKED"
        e = elig.get(key)
        if e:
            row["eligibility_status"] = e["status"]
            row["missing_after_research"] = e["missing"]
        out.append(row)
    return {"schema_version": 1, "note": "Nothing was written from memory and no catalog record was changed. Adoption of any noted sentence needs a human reading of the page.",
            "summary": {"records": len(out), "by_disposition": dict(sorted(Counter(r["disposition"] for r in out).items()))}, "records": out}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=CERT / "remediation_research_ledger.json")
    args = parser.parse_args(argv)
    ledger = build()
    args.output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(ledger["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
