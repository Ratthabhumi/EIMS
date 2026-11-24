"""Scan the cited vendor pages of candidates whose remediation names a state-changing action but whose risk field only says
"Not stated". Keyword scan, verbatim sentences only, no inference. A finding stays OPEN unless a human accepts a statement.

Output: docs/acceptance/certification/risk_warning_evidence.json. Pages that refuse automated fetching (HTTP 403) are
reported as such and are NOT fetched by other means.
"""
from __future__ import annotations

import argparse
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
OUT = ROOT / "docs" / "acceptance" / "certification" / "risk_warning_evidence.json"
RISK = re.compile(r"[^.]*\b(caution|warning|careful|impact|disrupt|downtime|outage|data loss|not recommended|should not|do not|don't|risk|vulnerab|"
                  r"reset|reboot|restart|interrupt)\b[^.]*\.", re.I)
BOILERPLATE = re.compile(r"(?i)upgrade to microsoft edge|e-mail with instructions|configure (?:security|network|repository)|contact veeam support|log in|buy online")


def scan(keys: list[str]) -> dict:
    cands = {f"candidate:{r['candidate_id']}": r for r in json.loads((SERVICES / "vendor_diagnostic_catalog.json").read_text(encoding="utf-8"))["records"]}
    cands = {f"candidate:{r['candidate_id']}": r for r in json.loads((SERVICES / "vendor_diagnostic_catalog.json").read_text(encoding="utf-8"))["records"]}
    out = []
    for key in keys:
        rec = cands[key]
        url = rec["official_sources"][0]["url"]
        item = {"record_key": key, "source_url": url, "risk_field_in_record": rec.get("operational_risk", "")[:300], "retrieved": datetime.now(UTC).strftime("%Y-%m-%d")}
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "EIMS-source-readcheck/1.0"}), timeout=45).read().decode("utf-8", "replace")
            text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S))))
            sentences = [m.group(0).strip() for m in RISK.finditer(text) if 40 < len(m.group(0)) < 420 and not BOILERPLATE.search(m.group(0))]
            item.update({"fetched": True, "page_chars": len(text), "keyword_sentences": sentences[:6],
                         "conclusion": "NO_RELEVANT_VENDOR_RISK_STATEMENT_IDENTIFIED" if not sentences else "SENTENCES_FOUND_NEED_HUMAN_RELEVANCE_CHECK"})
        except Exception as exc:  # noqa: BLE001 - recorded, never bypassed
            item.update({"fetched": False, "error": f"{type(exc).__name__}: {str(exc)[:80]}", "keyword_sentences": [], "conclusion": "NOT_RETRIEVED_AUTOMATICALLY"})
        item["status"] = "RISK_UNVERIFIED_NEEDS_HUMAN_REVIEW"
        out.append(item)
    return {"schema_version": 1, "note": "Keyword scan only; the absence of a sentence is not proof that the vendor gives no warning. Not a review.", "records": out}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validator-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args(argv)
    findings = json.loads(args.validator_report.read_text(encoding="utf-8"))["findings"]
    keys = sorted({f["record_key"] for f in findings if f["code"] == "destructive_remediation_risk_unresolved"})
    result = scan(keys)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(keys), "by_conclusion": {c: sum(r["conclusion"] == c for r in result["records"]) for c in {r["conclusion"] for r in result["records"]}}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
