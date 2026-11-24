import json
from collections import Counter
from pathlib import Path

m = json.loads(Path("evaluation/analyzer/gold/manifest.v1.json").read_text(encoding="utf-8"))
rows = []
for c in m["cases"]:
    cid = c["case_id"]
    files = c.get("files") or {}
    truth = c.get("truth") or {}
    present = {}
    missing = []
    for role, rel in files.items() if isinstance(files, dict) else []:
        candidates = [
            Path("evaluation/analyzer/gold") / rel,
            Path(rel),
            Path("evaluation/analyzer/gold/cases") / cid / Path(rel).name,
        ]
        hit = next((cand for cand in candidates if cand.exists()), None)
        present[role] = str(hit) if hit else None
        if hit is None:
            missing.append(role)
    case_dir = Path("evaluation/analyzer/gold/cases") / cid
    input_files = [p for p in case_dir.rglob("*") if p.is_file()] if case_dir.exists() else []

    def count_nonempty(o):
        if isinstance(o, dict):
            return sum(count_nonempty(v) for v in o.values())
        if isinstance(o, list):
            return sum(count_nonempty(v) for v in o)
        return 1 if o not in (None, "") else 0

    truth_fields = {}
    if isinstance(truth, dict):
        for k, v in truth.items():
            if isinstance(v, dict):
                truth_fields[k] = sorted(v.keys())
            elif isinstance(v, list):
                truth_fields[k] = f"list[{len(v)}]"
            else:
                truth_fields[k] = type(v).__name__

    # decision criteria proxies in truth
    criteria_keys = [
        "diagnostic_code",
        "source_family",
        "claims",
        "evidence_spans",
        "resolution",
        "abstain",
        "kb_ids",
        "correlation",
        "expected",
    ]
    present_criteria = [
        k for k in criteria_keys if isinstance(truth, dict) and k in truth and truth[k] not in (None, "", [], {})
    ]

    rows.append(
        {
            "case_id": cid,
            "split": c.get("split"),
            "review_status": c.get("review_status"),
            "origin": c.get("origin"),
            "scenario_group": c.get("scenario_group"),
            "annotator_id": c.get("annotator_id"),
            "files_map": files,
            "missing_file_roles": missing,
            "case_dir_exists": case_dir.exists(),
            "input_file_count": len(input_files),
            "input_names": [p.name for p in input_files],
            "truth_keys": sorted(truth.keys()) if isinstance(truth, dict) else [],
            "truth_fields": truth_fields,
            "truth_nonempty_leaves": count_nonempty(truth) if isinstance(truth, dict) else 0,
            "criteria_present": present_criteria,
        }
    )

print("TOTAL", len(rows))
print("split", dict(Counter(r["split"] for r in rows)))
print("review", dict(Counter(r["review_status"] for r in rows)))
print("case_dir_ok", sum(r["case_dir_exists"] for r in rows))
print("has_input_files", sum(r["input_file_count"] > 0 for r in rows))
print("truth_nonempty>0", sum(r["truth_nonempty_leaves"] > 0 for r in rows))
print("missing any file role", sum(1 for r in rows if r["missing_file_roles"]))
print("annotators", dict(Counter(r["annotator_id"] for r in rows)))
print("origins", dict(Counter(r["origin"] for r in rows)))

# coverage matrix style summary
print("\nCASE COVERAGE")
for r in rows:
    print(
        f"{r['case_id']:28} {r['split']:7} "
        f"input={'Y' if r['input_file_count'] else 'N'} "
        f"truth={'Y' if r['truth_nonempty_leaves'] else 'N'} "
        f"criteria={','.join(r['criteria_present']) or '-'} "
        f"files={r['files_map']} missing={r['missing_file_roles']}"
    )

print("\nTRUTH SAMPLE case0")
print(json.dumps(m["cases"][0]["truth"], indent=2)[:1500])
print("\nFILES SAMPLE case0", m["cases"][0]["files"])

# criteria frequency
crit_c = Counter()
for r in rows:
    for k in r["criteria_present"]:
        crit_c[k] += 1
print("\nCRITERIA FREQ", dict(crit_c))

# human review packages summary
print("\n=== HUMAN REVIEW PACKAGES ===")
asa = Path("docs/acceptance/certification/asa_113005_review_package.md")
print("ASA package exists", asa.exists(), "bytes", asa.stat().st_size if asa.exists() else 0)
cb = json.loads(Path("docs/acceptance/certification/class_b_human_review_package.json").read_text(encoding="utf-8"))
print("Class B records", len(cb.get("records", [])))
# peek first record keys
if cb.get("records"):
    print("Class B record keys", sorted(cb["records"][0].keys())[:30])
hr = Path("docs/acceptance/2026-11-20-human-review-package.md")
print("Nov20 package exists", hr.exists(), "bytes", hr.stat().st_size if hr.exists() else 0)
# count PENDING markers roughly
text = hr.read_text(encoding="utf-8") if hr.exists() else ""
print("Nov20 PENDING_HUMAN_REVIEW count", text.count("PENDING_HUMAN_REVIEW"))
print("Nov20 blank reviewer rows approx", text.count("|  |  |  |"))
