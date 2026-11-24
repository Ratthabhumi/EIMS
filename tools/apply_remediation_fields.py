"""Write curated operational fields into vendor_diagnostic_catalog.json after re-verifying every 'stated' quote on the live official page.

Dry-run by default (``--apply`` writes). For each record the tool refuses to proceed if
  * a quote is not found verbatim (whitespace-normalised) in the page text fetched now,
  * the fields fail ``validate_operational_fields``,
  * the record is not a candidate with review_status PENDING_HUMAN_REVIEW.
Idempotent: a record that already carries identical fields is left alone. The catalog is re-serialised with indent=2, which reproduces the
file byte for byte when nothing changes. Content hashes of changed records change (evidence bound to them becomes stale until re-run).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CATALOG = ROOT / "backend" / "domain" / "analyzer" / "services" / "vendor_diagnostic_catalog.json"
CURATED = ROOT / "docs" / "acceptance" / "certification" / "remediation_fields_curated.json"
UA = {"User-Agent": "EIMS-source-readcheck/1.0"}


def page_text(url: str, cache: Path) -> str:
    f = cache / (hashlib.sha1(url.encode()).hexdigest() + ".html")
    if not f.exists():
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45).read())
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", f.read_text(encoding="utf-8", errors="replace"), flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def check(curated: dict, cache: Path) -> list[str]:
    from backend.domain.knowledge.catalog_adapter import validate_operational_fields
    problems: list[str] = []
    for key, block in curated["records"].items():
        problems += [f"{key}: {p}" for p in validate_operational_fields(block)]
        for name, entry in block.items():
            if entry.get("state") == "stated":
                src = entry["source"]
                if norm(src["quote"]) not in page_text(src["url"], cache):
                    problems.append(f"{key}.{name}: quote not found verbatim on {src['url']}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    args.cache.mkdir(parents=True, exist_ok=True)
    curated = json.loads(CURATED.read_text(encoding="utf-8"))
    problems = check(curated, args.cache)
    if problems:
        print(json.dumps({"ok": False, "problems": problems}, indent=1))
        return 1
    doc = json.loads(CATALOG.read_text(encoding="utf-8", newline=None))
    by_id = {f"candidate:{r['candidate_id']}": r for r in doc["records"]}
    changed = []
    for key, block in curated["records"].items():
        rec = by_id[key]
        if rec.get("review_status") != "PENDING_HUMAN_REVIEW":
            print(f"refusing {key}: not PENDING_HUMAN_REVIEW")
            return 1
        if rec.get("operational_fields") != block:
            rec["operational_fields"] = block
            changed.append(key)
    print(json.dumps({"ok": True, "records_changed": changed, "mode": "apply" if args.apply else "dry-run"}, indent=1))
    if args.apply and changed:
        CATALOG.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
