"""Catalog adapter CLI: eligibility preview for all catalog records and an idempotent, audited registration in the governance overlay.

Dry-run is the default and writes only the preview artifacts (catalog_import_eligibility.json/.csv). ``--apply`` additionally
registers ELIGIBLE records as lifecycle ``candidate`` with an automation-attributed audit event. It refuses any database that is
not on loopback, not on the explicit allowlist (EIMS_CATALOG_IMPORT_ALLOWED_DATABASES, comma separated) or on a standard
operational port (5432/6432). Nothing is verified, validated or approved by this tool.

Status per record: ELIGIBLE, INELIGIBLE, BLOCKED, NEEDS_HUMAN_REVIEW, ALREADY_IMPORTED, STALE_SOURCE.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CERT = ROOT / "docs" / "acceptance" / "certification"


def build_evaluations(overlay_hashes: dict[str, str] | None = None) -> list[dict]:
    from backend.domain.knowledge.catalog_adapter import ImportContext, evaluate
    from backend.domain.knowledge.service import _catalog, canonical_hash, catalog_kind
    register = {r["record_key"]: r for r in json.loads((CERT / "register.json").read_text(encoding="utf-8"))["records"]}
    findings = json.loads((CERT / "validator_report.json").read_text(encoding="utf-8"))["findings"]
    open_by_key: dict[str, list[str]] = {}
    for f in findings:
        if f["severity"] != "evidence" and f.get("record_key"):
            open_by_key.setdefault(f["record_key"], []).append(f["code"])
    out = []
    for catalog_id, entry in sorted(_catalog().items()):
        kind = catalog_kind(catalog_id)
        record_key = catalog_id if kind in ("candidate", "reference") else ("operational:" if kind == "windows" else "diagnostic_legacy:") + catalog_id
        row = register[record_key]
        kinds = {e["kind"] for e in row["test_evidence"] if e["current"] and e["all_passed"]}
        fresh = ({"parser_match", "parser_non_match"} <= kinds) or ({"evaluator_real_state_positive", "evaluator_real_state_negative"} <= kinds)
        ctx = ImportContext(evidence_current=fresh, open_findings=tuple(open_by_key.get(record_key, ())),
                            overlay_hash=(overlay_hashes or {}).get(catalog_id))
        result = evaluate(kind, entry, canonical_hash(entry), ctx)
        out.append({"catalog_id": catalog_id, "record_key": record_key, "kind": kind, "register_class": row["cert_class"],
                    "open_findings": sorted(set(open_by_key.get(record_key, []))), **result})
    return out


def summarize(rows: list[dict]) -> dict:
    by_class: dict[str, Counter] = {}
    for r in rows:
        by_class.setdefault(r["class"], Counter())[r["status"]] += 1
    return {"records": len(rows), "by_status": dict(sorted(Counter(r["status"] for r in rows).items())),
            "by_class": {c: dict(sorted(v.items())) for c, v in sorted(by_class.items())}}


def write_artifacts(rows: list[dict], out_dir: Path) -> None:
    payload = {"schema_version": 1, "note": ("Preview only. ELIGIBLE means a record may be registered for human review; it does not mean verified, validated or approved. "
               "Reference-only, unmapped and Windows-context records are never importable as diagnostic capabilities."),
               "summary": summarize(rows), "records": rows}
    (out_dir / "catalog_import_eligibility.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cols = ["catalog_id", "record_key", "class", "class_name", "status", "reasons", "missing", "open_findings", "approval_scope_if_approved", "content_hash"]
    with (out_dir / "catalog_import_eligibility.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(r[k], ensure_ascii=False) if isinstance(r[k], (list, dict)) else r[k]) for k in cols})


def guard_database(url_text: str) -> str:
    from sqlalchemy.engine import make_url
    url = make_url(url_text)
    allowed = {d.strip() for d in os.environ.get("EIMS_CATALOG_IMPORT_ALLOWED_DATABASES", "").split(",") if d.strip()}
    if url.drivername != "postgresql+asyncpg" or url.host not in ("127.0.0.1", "localhost") or url.port in (None, 5432, 6432) or url.database not in allowed:
        raise SystemExit("refusing: need a loopback postgresql+asyncpg URL on a non-standard port whose database is in EIMS_CATALOG_IMPORT_ALLOWED_DATABASES")
    return url_text


async def apply_import(database_url: str) -> dict:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from backend.domain.knowledge.models import KnowledgeReview
    from backend.domain.knowledge.service import register_catalog_records
    engine = create_async_engine(database_url)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            hashes = {r.catalog_id: r.content_hash for r in (await db.execute(select(KnowledgeReview))).scalars().all()}
            rows = build_evaluations(hashes)
            result = await register_catalog_records(db, [r for r in rows if r["status"] == "ELIGIBLE"])
            await db.commit()
            return {"summary_before_import": summarize(rows), **result}
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=CERT)
    parser.add_argument("--apply", action="store_true", help="register ELIGIBLE records in the governance overlay (disposable allowlisted database only)")
    parser.add_argument("--database-url", default=os.environ.get("EIMS_CATALOG_IMPORT_DATABASE_URL", ""))
    args = parser.parse_args(argv)
    rows = build_evaluations()
    write_artifacts(rows, args.output_dir)
    print(json.dumps({"mode": "dry-run", **summarize(rows)}, indent=1))
    if args.apply:
        if not args.database_url:
            raise SystemExit("--apply needs --database-url (or EIMS_CATALOG_IMPORT_DATABASE_URL)")
        print(json.dumps(asyncio.run(apply_import(guard_database(args.database_url))), indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
