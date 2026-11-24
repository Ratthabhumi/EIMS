"""Read-only inventory of the canonical Knowledge Catalog (no DB, no network).

Usage: python tools/knowledge_inventory.py [--md out.md]
Derives every figure from load_catalog(); nothing is hand-counted.
"""
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict

from backend.domain.analyzer.services.operational_catalog import load_catalog

WIN_DEPTH = ("description", "operator_context", "keywords", "related_events")
VENDOR_DEPTH = ("description", "observed_signatures", "relevant_log_fields", "investigation_steps",
                "official_references", "limitations")
GENERIC = re.compile(r"^(investigate|review|check|correlate|monitor)\b", re.I)


def completeness(e):
    keys = VENDOR_DEPTH if e["knowledge_class"] == "diagnostic_candidate" else WIN_DEPTH
    have = [k for k in keys if e.get(k)]
    return have, [k for k in keys if k not in have]


def row(e):
    have, missing = completeness(e)
    ctx = (e.get("operator_context") or e.get("limitations") or "")
    steps = e.get("investigation_steps") or []
    refs = e.get("official_references") or []
    digest = hashlib.sha256(json.dumps({k: v for k, v in e.items() if k != "catalog_id"}, sort_keys=True,
                                        ensure_ascii=False).encode()).hexdigest()[:12]
    if e["knowledge_class"] == "diagnostic_candidate":
        nxt = "verify refs against vendor docs; add expected findings, remediation, risk, rollback, verification"
        if not refs:
            nxt = "NO references: cannot be source-verified"
    else:
        nxt = "split context vs event-specific guidance; add references where evidence exists"
    return {
        "id": e["catalog_id"], "vendor": e["vendor"], "product": e["product"], "category": e["category"],
        "class": e["knowledge_class"], "lifecycle": e["lifecycle_status"], "refs": len(refs),
        "steps": len(steps), "keywords": len(e.get("keywords") or []), "ctx_chars": len(ctx),
        "has": len(have), "missing": ",".join(missing), "hash": digest, "next": nxt,
    }


def main():
    cat = load_catalog()
    rows = [row(e) for e in cat]
    by_title = defaultdict(list)
    for e in cat:
        by_title[re.sub(r"\W+", " ", e["title"].lower()).strip()].append(e["catalog_id"])
    dups = {t: ids for t, ids in by_title.items() if len(ids) > 1}
    cls = Counter(r["class"] for r in rows)
    vend = Counter(r["vendor"] for r in rows)
    out = [f"# Knowledge catalog inventory ({len(rows)} records)", "",
           f"- classes: {dict(cls)}", f"- vendors: {dict(vend)}",
           f"- records with official references: {sum(1 for r in rows if r['refs'])}",
           f"- records with investigation steps: {sum(1 for r in rows if r['steps'])}",
           f"- duplicate normalised titles: {dups or 'none'}", "",
           "| ID | vendor | category | class | lifecycle | refs | steps | missing | sha12 | next |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['id']} | {r['vendor']} | {r['category']} | {r['class']} | {r['lifecycle']} | {r['refs']} | "
                   f"{r['steps']} | {r['missing'] or '-'} | {r['hash']} | {r['next']} |")
    text = "\n".join(out)
    if "--md" in sys.argv:
        open(sys.argv[sys.argv.index("--md") + 1], "w", encoding="utf-8").write(text + "\n")
    print("\n".join(out[:8]))
    return rows


if __name__ == "__main__":
    main()
