"""Recompute the Knowledge coverage matrix from the live catalogs (no hand-typed numbers)."""
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.domain.analyzer.services.operational_catalog import OPERATIONAL_CATALOG  # noqa: E402
from backend.domain.analyzer.services.vendor_reference import REFERENCE_CATALOG  # noqa: E402
from backend.domain.analyzer.services.vendor_diagnostics import DIAGNOSTIC_CANDIDATES  # noqa: E402

PARSED_FAMILIES = {"windows_event", "veeam_vbr", "vmware", "palo_alto", "fortinet", "cisco_asa", "linux_syslog"}


def urls(e):
    return {r["url"] for r in e.get("official_references", [])}


rows = defaultdict(lambda: dict(n=0, src=set(), refd=0, guid=0))
for e in OPERATIONAL_CATALOG:
    k = (e["vendor"], e["product"], e["knowledge_class"], "existing parser + existing signature"
         if e["source_family"] in PARSED_FAMILIES else "missing parser")
    r = rows[k]; r["n"] += 1; r["src"] |= urls(e); r["refd"] += bool(e.get("official_references")); r["guid"] += bool(e.get("diagnostic_guidance"))
for e in REFERENCE_CATALOG:
    k = (e["vendor"], e["product"] + " (" + e["version_scope"].split(";")[0] + ")", e["knowledge_class"], e["parser_mapping"])
    r = rows[k]; r["n"] += 1; r["src"].add(e["source"]["url"]); r["refd"] += 1

for e in DIAGNOSTIC_CANDIDATES:
    k = (e["vendor"], e["product"] + " (" + e["problem_domain"] + ")", e["knowledge_class"] + " (parser-unmapped)", e["parser_mapping"])
    r = rows[k]; r["n"] += 1; r["src"] |= {x["url"] for x in e["official_sources"]}; r["refd"] += 1; r["guid"] += 1

total = sum(r["n"] for r in rows.values())
allsrc = set().union(*(r["src"] for r in rows.values()))
print("| Vendor | Product (version scope) | Class | Parser / signature mapping | Records | With source | With guidance | Unique sources |")
print("|---|---|---|---|---:|---:|---:|---:|")
for (v, p, c, m), r in sorted(rows.items()):
    print(f"| {v} | {p} | {c} | {m} | {r['n']} | {r['refd']} | {r['guid']} | {len(r['src'])} |")
print(f"\nTotal records {total}; distinct source URLs across both catalogs {len(allsrc)}")
print("Vendors:", len({k[0] for k in rows}), "| products:", len({k[1].split(' (')[0] for k in rows}))
print("By class:", dict(Counter({k[2]: 0 for k in rows}) ), {c: sum(r['n'] for k, r in rows.items() if k[2] == c) for c in {k[2] for k in rows}})

print("\n### Problem-domain coverage (reference inventory) / category (diagnostic catalog)")
dom = Counter(r["domain"] for r in REFERENCE_CATALOG)
cat = Counter(e["category"] for e in OPERATIONAL_CATALOG)
print("| Domain | Reference records |\n|---|---:|")
for k, v in sorted(dom.items()): print(f"| {k} | {v} |")
print("\n| Diagnostic-catalog category | Records |\n|---|---:|")
for k, v in sorted(cat.items()): print(f"| {k} | {v} |")
print("\nDistinct vendors:", len({e['vendor'] for e in OPERATIONAL_CATALOG} | {r['vendor'] for r in REFERENCE_CATALOG}))
print("Distinct version scopes (reference):", len({r['version_scope'] for r in REFERENCE_CATALOG}))


# --- Tranche 18: separate, reconciled categories (never summed as equal capability) --------------------------------
import json as _json  # noqa: E402
from backend.domain.analyzer.services.vendor_diagnostics import STATE_KINDS  # noqa: E402

_disp = _json.loads((Path(__file__).resolve().parents[1] / "backend/domain/analyzer/services/windows_reference_dispositions.json").read_text(encoding="utf-8"))["records"]
_win = [e for e in OPERATIONAL_CATALOG if e["source_family"] == "windows_event"]
_legacy_diag = [e for e in OPERATIONAL_CATALOG if e["knowledge_class"] == "diagnostic_candidate"]
_state = [e for e in DIAGNOSTIC_CANDIDATES if e.get("detection_kind") in STATE_KINDS]
_logc = [e for e in DIAGNOSTIC_CANDIDATES if e.get("detection_kind") not in STATE_KINDS]
_linked = lambda e: e["parser_mapping"].startswith("parser_linked_by_")  # noqa: E731
_pg = lambda e: "postgres" in e["vendor"].lower()  # noqa: E731
_dc = Counter(r["disposition"] for r in _disp)
print("\n### Tranche 18 reconciliation (computed)")
rec = {
    "parser-linked diagnostic candidates (legacy catalog, existing parser+signature)": len(_legacy_diag),
    "parser-linked candidates outside legacy catalog (sqlstate/message/fields)": sum(_linked(e) for e in _logc),
    "parser-mapped references (reference catalog)": sum(e["parser_mapping"] == "parser_mapped" for e in REFERENCE_CATALOG),
    "state/metrics candidates (evaluator, not log-parsed)": len(_state),
    "supporting references not parser-mapped": sum(e["parser_mapping"] != "parser_mapped" for e in REFERENCE_CATALOG),
    "log-symptom candidates not yet parser-linked": sum(not _linked(e) for e in _logc),
    "PostgreSQL entries (reference + candidates)": sum(_pg(e) for e in REFERENCE_CATALOG) + sum(_pg(e) for e in DIAGNOSTIC_CANDIDATES),
    "total records (4 files)": len(OPERATIONAL_CATALOG) + len(REFERENCE_CATALOG) + len(DIAGNOSTIC_CANDIDATES),
    "Windows records": len(_win),
    "Windows exact-source records": sum(bool(e.get("official_references")) for e in _win),
    "Windows indirect-source only (disposition file, not official_references)": _dc["INDIRECT_AUTHORITATIVE_REFERENCE"],
    "Windows unresolved (no authoritative reference found)": _dc["NO_AUTHORITATIVE_REFERENCE_FOUND"] + _dc["AMBIGUOUS"],
    "Windows needing human review (dispositions)": _dc["NEEDS_HUMAN_REVIEW"],
    "records awaiting human review (candidates, PENDING_HUMAN_REVIEW)": sum(e.get("review_status") == "PENDING_HUMAN_REVIEW" for e in DIAGNOSTIC_CANDIDATES),
    "disposition rows awaiting human review": sum(r["review_status"] == "PENDING_HUMAN_REVIEW" for r in _disp),
    "human-reviewed (independent)": 0,
}
for k, v in rec.items():
    print(f"- {k}: {v}")
