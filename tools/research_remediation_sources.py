"""Collect verbatim vendor statements about preconditions, impact, backup/rollback and post-action verification for the 28 records
that the engineer-facing KnowledgeEntry contract rejects (destructive remediation without rollback/verification).

Only sentences published on the cited official pages are kept, with their category; nothing is written from memory. Pages that refuse
automated fetching (HTTP 403, e.g. cisco.com) are recorded as MANUAL_REVIEW_REQUIRED and are never fetched by other means.
The ledger lists candidate sentences; adopting one into the overlay is a separate, curated step (remediation_overlay.json).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SERVICES = ROOT / "backend" / "domain" / "analyzer" / "services"
CERT = ROOT / "docs" / "acceptance" / "certification"
UA = {"User-Agent": "EIMS-source-readcheck/1.0"}
CATEGORIES = {
    "precondition": re.compile(r"\b(before you|prerequisite|make sure|ensure|must be|only if|requires?|prior to)\b", re.I),
    "impact_risk": re.compile(r"\b(will (?:be )?(?:lost|deleted|removed|disconnected|restart|reset|fail)|data loss|downtime|outage|disrupt|irreversible|cannot be undone|not recommended|caution|warning|important)\b", re.I),
    "backup_rollback": re.compile(r"\b(back ?up|backup|roll ?back|revert|restore|undo|snapshot before|previous (?:setting|configuration))\b", re.I),
    "verification": re.compile(r"\b(verify|confirm|to check|check that|you can check|should (?:now )?(?:show|display|return|be)|expected output|make sure that)\b", re.I),
}


def _clean(raw: str) -> str:
    raw = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def fetch(url: str, cache: Path) -> tuple[str, str]:
    f = cache / (hashlib.sha1(url.encode()).hexdigest() + ".html")
    if f.exists():
        return "ok", f.read_text(encoding="utf-8", errors="replace")
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45).read()
    except urllib.error.HTTPError as exc:  # noqa: PERF203
        return ("MANUAL_REVIEW_REQUIRED" if exc.code in (401, 403) else f"HTTP_{exc.code}"), ""
    except Exception as exc:  # noqa: BLE001
        return f"FETCH_FAILED_{type(exc).__name__}", ""
    f.write_bytes(raw)
    return "ok", raw.decode("utf-8", "replace")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", text) if 40 <= len(s.strip()) <= 380]


def build(cache: Path) -> dict:
    cache.mkdir(parents=True, exist_ok=True)
    mapping = json.loads((CERT / "knowledge_model_mapping.json").read_text(encoding="utf-8"))["records_b_d_e"]
    keys = [r["record_key"] for r in mapping if r["knowledge_entry_contract_blockers"]]
    cands = {f"candidate:{c['candidate_id']}": c for c in json.loads((SERVICES / "vendor_diagnostic_catalog.json").read_text(encoding="utf-8"))["records"]}
    legacy = {f"diagnostic_legacy:{e['source_family']}:{e['code_type']}:{e['diagnostic_code']}": e
              for e in json.loads((SERVICES / "diagnostic_knowledge_catalog.json").read_text(encoding="utf-8"))["entries"]}
    out = []
    for key in keys:
        rec = cands.get(key) or legacy[key]
        urls = [s["url"] for s in rec.get("official_sources", [])] or [r["url"] for r in rec.get("official_references", [])]
        pages = []
        for url in urls:
            status, raw = fetch(url, cache)
            item = {"url": url, "fetch_status": status, "retrieved": datetime.now(UTC).strftime("%Y-%m-%d"), "statements": {}}
            if status == "ok":
                sents = sentences(_clean(raw))
                for cat, pat in CATEGORIES.items():
                    item["statements"][cat] = [s for s in sents if pat.search(s)][:6]
            pages.append(item)
        out.append({"record_key": key, "class": next(r["class"] for r in mapping if r["record_key"] == key),
                    "remediation_in_record": [x[:200] for x in (rec.get("remediation") or [])][:4],
                    "contract_blockers": next(r["knowledge_entry_contract_blockers"] for r in mapping if r["record_key"] == key),
                    "pages": pages,
                    "disposition": "MANUAL_REVIEW_REQUIRED" if any(p["fetch_status"] == "MANUAL_REVIEW_REQUIRED" for p in pages) else "CANDIDATE_STATEMENTS_COLLECTED_UNREVIEWED"})
    return {"schema_version": 1, "note": "Candidate verbatim sentences only; nothing is adopted until curated into remediation_overlay.json. Not a review.", "records": out}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=CERT / "remediation_research_candidates.json")
    args = parser.parse_args(argv)
    result = build(args.cache)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from collections import Counter
    print(json.dumps({"records": len(result["records"]), "by_disposition": dict(Counter(r["disposition"] for r in result["records"]))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
