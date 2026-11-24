"""Idempotently import the versioned vendor-source catalogue into KnowledgeSourceCandidate.

Dry-run is the default. Applying requires an explicit database-name allowlist:
EIMS_SOURCE_CATALOGUE_IMPORT_ALLOWED_DATABASES=synthetic_db --apply
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from backend.domain.analyzer.models.knowledge import (  # noqa: E402
    KnowledgeSourceCandidate,
    KnowledgeSourceEvent,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "docs" / "knowledge-source-candidates" / "official-vendor-candidates.v1.json"
REQUIRED = {
    "id", "vendor", "product", "version_scope", "domain", "identity", "title",
    "url", "applicability", "prerequisites", "evidence", "limitations",
    "next_checks", "validation", "rollback", "risk", "review_state", "evidence_status",
}


def load_catalogue() -> tuple[dict, list[dict]]:
    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    if data.get("corpus_type") != "official_vendor_source_candidates":
        raise ValueError("Unexpected catalogue type")
    if data.get("approval_state") != "candidate_only_not_approved_knowledge":
        raise ValueError("Catalogue must remain candidate-only")
    if data.get("policy", {}).get("production_knowledge_import_enabled") is not False:
        raise ValueError("Catalogue policy must prohibit production Knowledge import")
    records = data.get("candidates")
    if not isinstance(records, list) or not records:
        raise ValueError("Catalogue candidates must be a non-empty list")
    seen: set[str] = set()
    for item in records:
        missing = REQUIRED - set(item)
        if missing:
            raise ValueError(f"{item.get('id', '<unknown>')} missing fields: {sorted(missing)}")
        if item["id"] in seen:
            raise ValueError(f"Duplicate source candidate key: {item['id']}")
        seen.add(item["id"])
        if item["review_state"] != "pending_domain_review":
            raise ValueError(f"{item['id']} must remain pending domain review")
        if item["risk"] not in {"low", "medium", "high", "critical"}:
            raise ValueError(f"{item['id']} has invalid risk level")
        if not item["url"].startswith("https://"):
            raise ValueError(f"{item['id']} has a non-HTTPS source URL")
        for field in ("prerequisites", "evidence", "limitations", "next_checks", "validation", "rollback"):
            if not isinstance(item[field], list) or not item[field]:
                raise ValueError(f"{item['id']} requires non-empty {field}")
    return data, records


def canonical_hash(item: dict) -> str:
    raw = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def import_catalogue(apply: bool) -> dict:
    data, records = load_catalogue()
    if not apply:
        return {"mode": "dry-run", "records": len(records), "vendors": sorted({x["vendor"] for x in records})}

    allowed = {x.strip() for x in os.getenv("EIMS_SOURCE_CATALOGUE_IMPORT_ALLOWED_DATABASES", "").split(",") if x.strip()}
    database_url = os.getenv("EIMS_SOURCE_CATALOGUE_DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("Set EIMS_SOURCE_CATALOGUE_DATABASE_URL explicitly; application DATABASE_URL is never used.")
    parsed = make_url(database_url)
    if (
        parsed.drivername != "postgresql+asyncpg"
        or parsed.host not in {"127.0.0.1", "localhost"}
        or parsed.username != "eims_test"
        or parsed.port in {None, 5432, 6432}
        or not parsed.database
        or parsed.database not in allowed
    ):
        raise RuntimeError(
            "Refusing import: require loopback postgresql+asyncpg, eims_test user, non-operational port, "
            "and an exact database name in EIMS_SOURCE_CATALOGUE_IMPORT_ALLOWED_DATABASES."
        )
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:

        created = updated = unchanged = 0
        async with AsyncSession(engine, expire_on_commit=False) as db:
            for item in records:
                source_hash = canonical_hash(item)
                row = await db.scalar(
                    select(KnowledgeSourceCandidate)
                    .where(KnowledgeSourceCandidate.source_key == item["id"])
                    .with_for_update()
                )
                if row is None:
                    row = KnowledgeSourceCandidate(
                        source_key=item["id"],
                        vendor=item["vendor"],
                        product=item["product"],
                        version_scope=item["version_scope"],
                        domain=item["domain"],
                        identity=item["identity"],
                        title=item["title"],
                        source_url=item["url"],
                        applicability=item["applicability"],
                        prerequisites=item["prerequisites"],
                        evidence=item["evidence"],
                        limitations=item["limitations"],
                        next_checks=item["next_checks"],
                        validation=item["validation"],
                        rollback=item["rollback"],
                        risk_level=item["risk"],
                        evidence_status=item["evidence_status"],
                        review_state="pending_domain_review",
                        catalog_schema_version=str(data.get("schema_version", "unknown")),
                        source_hash=source_hash,
                        source_payload=item,
                        imported_by="catalogue-import",
                    )
                    db.add(row)
                    await db.flush()
                    db.add(KnowledgeSourceEvent(
                        source_candidate_id=row.id,
                        action="catalogue_imported",
                        from_state=None,
                        to_state="pending_domain_review",
                        source_hash=source_hash,
                        note="Imported from version-controlled official vendor source catalogue; not approved Knowledge.",
                        changed_by="catalogue-sync",
                    ))
                    created += 1
                    continue

                if row.source_hash == source_hash:
                    unchanged += 1
                    continue

                previous_state = row.review_state
                previous_hash = row.source_hash
                row.vendor = item["vendor"]
                row.product = item["product"]
                row.version_scope = item["version_scope"]
                row.domain = item["domain"]
                row.identity = item["identity"]
                row.title = item["title"]
                row.source_url = item["url"]
                row.applicability = item["applicability"]
                row.prerequisites = item["prerequisites"]
                row.evidence = item["evidence"]
                row.limitations = item["limitations"]
                row.next_checks = item["next_checks"]
                row.validation = item["validation"]
                row.rollback = item["rollback"]
                row.risk_level = item["risk"]
                row.evidence_status = item["evidence_status"]
                row.catalog_schema_version = str(data.get("schema_version", "unknown"))
                row.source_hash = source_hash
                row.source_payload = item
                row.review_state = (
                    "pending_domain_review" if previous_state == "pending_domain_review"
                    else "revalidation_required"
                )
                row.updated_at = datetime.now(UTC)
                db.add(KnowledgeSourceEvent(
                    source_candidate_id=row.id,
                    action="catalogue_source_changed",
                    from_state=previous_state,
                    to_state=row.review_state,
                    source_hash=source_hash,
                    note=f"Catalogue content changed; prior source hash {previous_hash}. Independent review required.",
                    changed_by="catalogue-sync",
                ))
                updated += 1
            await db.commit()
        return {"mode": "applied", "created": created, "updated": updated, "unchanged": unchanged}
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Persist candidates; dry-run is default")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(import_catalogue(args.apply)), indent=2))


if __name__ == "__main__":
    main()
