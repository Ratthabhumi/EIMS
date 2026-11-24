"""Run the synthetic certification fixtures through the real parser / Analyzer path and record the actual results.

Output (``technical_evidence_matching.json``) is *run-bound evidence*: each case stores the input, the expectation, the
actual outcome, the repository HEAD, a UTC timestamp and the content hash of the record it was run against. A later
content change makes that hash stale (the register builder then reports the evidence as stale, not as current).
This is automated technical evidence only; it is never a certification or a review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_OUT = ROOT / "docs" / "acceptance" / "certification" / "technical_evidence_matching.json"


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:  # noqa: BLE001 - evidence metadata only
        return ""


def _legacy(text: str, expect: list[str]) -> dict:
    from backend.domain.analyzer.services.operational_catalog import entry_for_metadata
    from backend.domain.analyzer.services.parser import parse_event_metadata
    meta = parse_event_metadata(text)
    entry = entry_for_metadata(meta)
    actual = [entry["source_family"], entry["code_type"], entry["diagnostic_code"]] if entry else None
    return {"actual": actual, "matched": actual == expect}


def _summary(text: str, family: str, candidate_id: str) -> dict:
    from backend.domain.analyzer.services import catalog_diagnostics as cd
    solution = cd.catalog_summary(family, text, "en")
    blob = solution.model_dump_json() if solution is not None else ""
    return {"actual": candidate_id if candidate_id in blob else None, "matched": candidate_id in blob}


def _evaluate(fn_name: str, case: dict) -> dict:
    from backend.domain.analyzer.services import state_diagnostics as sd
    fn = getattr(sd, fn_name)
    if "line" in case:
        result = fn(case["line"])
    elif "thresholds" in case:
        result = fn(case["row"], thresholds=case["thresholds"])
    else:
        result = fn(case["row"])
    expect = case["expect"]
    actual = {k: result.get(k) for k in expect}
    return {"actual": actual, "matched": actual == expect}


def _run_one(fx: dict, case: dict, positive: bool) -> dict:
    resolver = fx["resolver"]
    if resolver == "legacy":
        out = _legacy(case["text"] if isinstance(case, dict) else case, fx["expect"])
        expected = fx["expect"] if positive else None
        passed = out["matched"] if positive else (out["actual"] != fx["expect"])
        return {"expected": expected if positive else f"must not resolve to {fx['expect']}", "actual": out["actual"], "passed": passed}
    if resolver == "summary":
        out = _summary(case["text"] if isinstance(case, dict) else case, fx["family"], fx["candidate_id"])
        passed = out["matched"] if positive else not out["matched"]
        return {"expected": fx["candidate_id"] if positive else f"must not reach {fx['candidate_id']}", "actual": out["actual"], "passed": passed}
    if resolver == "evaluator":
        out = _evaluate(fx["function"], case)
        return {"expected": case["expect"], "actual": out["actual"], "passed": out["matched"]}
    raise ValueError(f"unknown resolver {resolver}")


def run(register_hashes: dict[str, str]) -> dict:
    from tests.certification_fixtures import build_fixtures
    head = _git_head()
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    cases = []
    for fx in build_fixtures():
        key = fx["record_key"]
        pos_case = fx["positive"] if isinstance(fx["positive"], dict) else {"text": fx["positive"]}
        entries = [("positive", pos_case, True)] + [("negative", n, False) for n in fx["negatives"]]
        kind = fx.get("evidence_kind", "analyzer_path")
        for label, case, is_pos in entries:
            try:
                outcome = _run_one(fx, case, is_pos)
            except Exception as exc:  # noqa: BLE001 - a crash is a failed case, recorded as such
                outcome = {"expected": "no exception", "actual": f"{type(exc).__name__}: {exc}", "passed": False}
            text = case.get("text") if isinstance(case, dict) and "text" in case else json.dumps(case, sort_keys=True, default=str)
            cases.append({
                "record_key": key, "kind": kind, "polarity": label,
                "why": case.get("why", "documented positive example") if isinstance(case, dict) else "",
                "input_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "input_preview": text[:160], **outcome,
            })
    return {
        "schema_version": 1, "generated_at": stamp, "git_head": head, "python": platform.python_version(),
        "note": "Automated technical evidence from synthetic fixtures; not a certification or a human review.",
        "record_hashes": {k: register_hashes.get(k, "") for k in sorted({c["record_key"] for c in cases})},
        "cases": cases,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    from tools.build_certification_register import build_register
    hashes = {row["record_key"]: row["content_hash"] for row in build_register()["records"]}
    result = run(hashes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failed = [c for c in result["cases"] if not c["passed"]]
    print(json.dumps({"cases": len(result["cases"]), "records": len(result["record_hashes"]), "failed": len(failed)}))
    for case in failed:
        print("FAILED", case["record_key"], case["polarity"], "|", case["why"], "|", case["expected"], "|", case["actual"])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
