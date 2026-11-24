"""Knowledge governance service: sparse overlay over the canonical catalogs.

JSON owns content; this service owns effective state, transitions and history.
No canonical content is copied into PostgreSQL.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.analyzer.services.operational_catalog import load_catalog
from backend.domain.knowledge.gates import evaluate_gate
from backend.domain.knowledge.models import KnowledgeReview, KnowledgeReviewEvent

# candidate -> allowed next states
TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"source_verified", "rejected"}),
    "source_verified": frozenset({"validated", "rejected"}),
    "validated": frozenset({"approved", "rejected"}),
    "approved": frozenset({"deprecated", "superseded"}),
    "rejected": frozenset({"candidate"}),
    "deprecated": frozenset(),
    "superseded": frozenset(),
}

OPERATIONAL = "operational_context"
DIAGNOSTIC = "diagnostic_candidate"


class KnowledgeError(Exception):
    """Base error for knowledge governance."""


class KnowledgeNotFound(KnowledgeError):
    pass


class KnowledgeTransitionRejected(KnowledgeError):
    pass


class KnowledgePermissionError(KnowledgeError):
    pass


@dataclass(frozen=True)
class EffectiveState:
    catalog_id: str
    knowledge_class: str
    lifecycle_status: str
    content_hash: str
    review_required: bool
    revision: int


def canonical_hash(entry: dict) -> str:
    """Deterministic SHA-256 over the canonical record (key order independent)."""
    material = json.dumps({k: v for k, v in entry.items() if k != "catalog_id"}, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _catalog() -> dict[str, dict]:
    """Every governable catalog record: Windows/legacy (loader ids), vendor candidates (``candidate:<id>``) and references
    (``reference:<id>``). Added entries carry ``catalog_id`` but it is excluded from the content hash, so a record's hash is the same
    whether it is read raw (certification register) or through this catalogue."""
    from backend.domain.analyzer.services.vendor_diagnostics import DIAGNOSTIC_CANDIDATES
    from backend.domain.analyzer.services.vendor_reference import REFERENCE_CATALOG
    out = {entry["catalog_id"]: entry for entry in load_catalog()}
    for rec in DIAGNOSTIC_CANDIDATES:
        out[f"candidate:{rec['candidate_id']}"] = dict(rec, catalog_id=f"candidate:{rec['candidate_id']}")
    for rec in REFERENCE_CATALOG:
        out[f"reference:{rec['reference_id']}"] = dict(rec, catalog_id=f"reference:{rec['reference_id']}")
    return out


def catalog_kind(catalog_id: str) -> str:
    """windows | legacy | candidate | reference (the adapter's record kinds)."""
    if catalog_id.startswith("candidate:"):
        return "candidate"
    if catalog_id.startswith("reference:"):
        return "reference"
    return "windows" if catalog_id.startswith("windows_event:") else "legacy"


def _catalog_source(catalog_id: str, entry: dict) -> str:
    kind = catalog_kind(catalog_id)
    if kind in ("candidate", "reference"):
        return "vendor_" + kind
    return "operational" if entry.get("knowledge_class") == OPERATIONAL else "diagnostic"


def default_lifecycle(knowledge_class: str) -> str:
    return "not_applicable" if knowledge_class == OPERATIONAL else "candidate"


def resolve_catalog() -> list[dict]:
    """All canonical records with the class/lifecycle contract attached."""
    out = []
    for entry in load_catalog():
        out.append({
            "catalog_id": entry["catalog_id"],
            "knowledge_class": entry.get("knowledge_class", DIAGNOSTIC),
            "default_lifecycle": default_lifecycle(entry.get("knowledge_class", DIAGNOSTIC)),
            "content_hash": canonical_hash(entry),
            "product": entry.get("product"),
            "vendor": entry.get("vendor"),
            "diagnostic_code": entry.get("diagnostic_code"),
            "has_investigation": bool(entry.get("investigation_steps")),
            "has_references": bool(entry.get("official_references")),
            "has_limitations": bool(entry.get("limitations")),
            "has_remediation": bool(entry.get("remediation_guidance")),
            "has_verification": bool(entry.get("verification_criteria")),
        })
    return out


async def _rows(db: AsyncSession) -> dict[str, KnowledgeReview]:
    rows = (await db.execute(select(KnowledgeReview))).scalars().all()
    return {row.catalog_id: row for row in rows}


def effective_state(catalog_entry: dict, row: Optional[KnowledgeReview]) -> EffectiveState:
    knowledge_class = catalog_entry.get("knowledge_class", DIAGNOSTIC)
    if row is None:
        return EffectiveState(
            catalog_id=catalog_entry["catalog_id"],
            knowledge_class=knowledge_class,
            lifecycle_status=default_lifecycle(knowledge_class),
            content_hash=canonical_hash(catalog_entry),
            review_required=False,
            revision=0,
        )
    return EffectiveState(
        catalog_id=row.catalog_id,
        knowledge_class=knowledge_class,
        lifecycle_status=row.lifecycle_status,
        content_hash=row.content_hash,
        review_required=row.review_required,
        revision=row.revision,
    )


async def sync(db: AsyncSession, *, actor: str = "system") -> dict:
    """Detect canonical content changes for records that already have overlay state.

    Sparse by design: no row is created for a catalog record that has never been
    reviewed. Idempotent: one ``review_required`` event per changed revision.
    """
    catalog = _catalog()
    rows = await _rows(db)
    changed: list[str] = []
    for catalog_id, row in rows.items():
        entry = catalog.get(catalog_id)
        if entry is None:
            continue
        current = canonical_hash(entry)
        if current == row.content_hash:
            continue
        # already flagged for this new hash -> do not duplicate the event
        if row.review_required and row.content_hash == current:
            continue
        db.add(KnowledgeReviewEvent(
            catalog_id=catalog_id,
            event_type="review_required",
            from_status=row.lifecycle_status,
            to_status=row.lifecycle_status,
            actor=actor,
            rationale="canonical content changed since review",
            source_hash=current,
            revision=row.revision,
        ))
        row.content_hash = current
        row.review_required = True
        row.concurrency_version = int(row.concurrency_version or 1) + 1
        changed.append(catalog_id)
    await db.flush()
    return {"inspected": len(catalog), "overlay_rows": len(rows), "changed": changed}


async def promote(
    db: AsyncSession,
    catalog_id: str,
    target: str,
    *,
    actor: str,
    rationale: str,
    evidence: str | None = None,
    contributor: str | None = None,
    product_version_scope: str | None = None,
    review: dict | None = None,
    actor_kind: str | None = None,
) -> KnowledgeReview:
    """Move one record to ``target`` after the destination-state gate passes.

    All validation happens before any mutation; the state change and the
    append-only event are written in the caller's single transaction, so either
    both persist or neither does.
    """
    entry = _catalog().get(catalog_id)
    if entry is None:
        raise KnowledgeNotFound(f"unknown catalog id {catalog_id}")
    if entry.get("knowledge_class") == OPERATIONAL and target != "candidate":
        raise KnowledgeTransitionRejected(
            "operational_context may only be promoted to diagnostic candidate")
    if not actor or not actor.strip():
        raise KnowledgePermissionError("an authenticated actor is required")

    row = (await db.execute(
        select(KnowledgeReview).where(KnowledgeReview.catalog_id == catalog_id).with_for_update()
    )).scalars().first()
    current = row.lifecycle_status if row else default_lifecycle(
        entry.get("knowledge_class", DIAGNOSTIC))
    if target not in TRANSITIONS.get(current, frozenset()):
        raise KnowledgeTransitionRejected(f"illegal transition {current!r} -> {target!r}")
    if row is not None and row.review_required:
        raise KnowledgeTransitionRejected(
            "record requires renewed review after a content change")

    content_hash = canonical_hash(entry)
    events = [
        {"to_status": e["to_status"], "actor": e["actor"], "source_hash": e["source_hash"],
         "evidence": e.get("evidence") or {}}
        for e in await history(db, catalog_id)
        if e["event_type"] not in ("draft_saved", "draft_submitted", "draft_withdrawn")  # proposals are not decisions
    ]
    # Only decisions since the last reset (rejection / reopen) can support a new promotion.
    for index in range(len(events) - 1, -1, -1):
        if events[index]["to_status"] in {"candidate", "rejected"}:
            events = events[index + 1:]
            break
    problems, permission = evaluate_gate(
        dict(entry, catalog_id=catalog_id), current, target,
        actor=actor, rationale=rationale, review=review or {}, events=events,
        content_hash=content_hash,
        review_required=bool(row is not None and row.review_required),
        contributor=contributor, known_ids=set(_catalog()), actor_kind=actor_kind,
    )
    if permission:
        raise KnowledgePermissionError("; ".join(permission))
    if problems:
        raise KnowledgeTransitionRejected(
            f"{target} gate failed: " + "; ".join(problems))

    created = row is None
    if row is None:
        row = KnowledgeReview(
            catalog_id=catalog_id,
            catalog_source=_catalog_source(catalog_id, entry),
            content_hash=content_hash,
            lifecycle_status=current,
            revision=1,
        )
        db.add(row)
        await db.flush()

    row.lifecycle_status = target
    row.review_required = False
    row.revision = 1 if created else int(row.revision or 1) + 1
    row.concurrency_version = int(row.concurrency_version or 1) + 1
    if product_version_scope:
        row.product_version_scope = product_version_scope
    db.add(KnowledgeReviewEvent(
        catalog_id=catalog_id,
        event_type="transition",
        from_status=current,
        to_status=target,
        actor=actor.strip(),
        rationale=rationale,
        source_hash=content_hash,
        revision=row.revision,
        correlation_id=(evidence[:64] if evidence else None),
        evidence=dict(review or {}, actor_kind=actor_kind or "unspecified"),
    ))
    await db.flush()
    return row


async def history(db: AsyncSession, catalog_id: str) -> list[dict]:
    rows = (await db.execute(
        select(KnowledgeReviewEvent)
        .where(KnowledgeReviewEvent.catalog_id == catalog_id)
        .order_by(KnowledgeReviewEvent.created_at, KnowledgeReviewEvent.event_id)
    )).scalars().all()
    return [
        {
            "event_id": str(r.event_id),
            "event_type": r.event_type,
            "from_status": r.from_status,
            "to_status": r.to_status,
            "actor": r.actor,
            "rationale": r.rationale,
            "source_hash": r.source_hash,
            "revision": r.revision,
            "evidence": r.evidence,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def summary(db: AsyncSession) -> dict:
    """Counts from the catalog merged with *current* (non-stale) overlay state."""
    catalog = resolve_catalog()
    rows = await _rows(db)
    lifecycle = {state: 0 for state in
                 ("candidate", "source_verified", "validated", "approved",
                  "rejected", "deprecated", "superseded")}
    stale = 0
    for item in catalog:
        if item["knowledge_class"] == OPERATIONAL:
            continue
        row = rows.get(item["catalog_id"])
        state = row.lifecycle_status if row else "candidate"
        if row is not None and row.review_required:
            stale += 1
            continue  # stale decisions are not current
        lifecycle[state] = lifecycle.get(state, 0) + 1

    products: dict[str, int] = {}
    for item in catalog:
        products[item["product"] or "unknown"] = products.get(item["product"] or "unknown", 0) + 1

    return {
        "total_records": len(catalog),
        "counts": {
            "operational_context": sum(1 for i in catalog if i["knowledge_class"] == OPERATIONAL),
            "diagnostic_candidates": sum(1 for i in catalog if i["knowledge_class"] == DIAGNOSTIC),
            **lifecycle,
            "review_required": sum(1 for r in rows.values() if r.review_required),
            "stale_review": stale,
            "overlay_rows": len(rows),
        },
        "products": products,
        "coverage": {
            "investigation": sum(1 for i in catalog if i["has_investigation"]),
            "references": sum(1 for i in catalog if i["has_references"]),
            "limitations": sum(1 for i in catalog if i["has_limitations"]),
            "remediation": sum(1 for i in catalog if i["has_remediation"]),
            "verification": sum(1 for i in catalog if i["has_verification"]),
        },
    }


async def current_record(db: AsyncSession, catalog_id: str) -> dict:
    """The *current* canonical record plus its current trust classification.

    Read-only. Incidents keep their own historical snapshot; comparing the snapshot's
    ``content_hash`` with this record's ``content_hash`` shows whether the canonical
    content changed after the incident used it.
    """
    from backend.domain.knowledge.retrieval import retrieve

    entry = _catalog().get(catalog_id)
    if entry is None:
        raise KnowledgeNotFound(f"unknown catalog id {catalog_id}")
    match = await retrieve(db, entry)
    return {
        "catalog_id": catalog_id,
        "knowledge_class": entry.get("knowledge_class", DIAGNOSTIC),
        "content_hash": canonical_hash(entry),
        "classification": match,
        "title": entry.get("title"),
        "vendor": entry.get("vendor"),
        "product": entry.get("product"),
        "diagnostic_code": entry.get("diagnostic_code"),
        "severity": entry.get("severity"),
        "description": entry.get("description"),
        "compatibility_scope": entry.get("compatibility_scope"),
        "investigation_steps": list(entry.get("investigation_steps") or []),
        "limitations": entry.get("limitations") or "",
        "official_references": list(entry.get("official_references") or []),
        # The catalog schema has no remediation/verification fields yet; reported, not invented.
        "remediation_guidance": list(entry.get("remediation_guidance") or []),
        "verification_criteria": list(entry.get("verification_criteria") or []),
    }


async def register_catalog_records(db: AsyncSession, evaluations: list[dict], *, actor: str = "catalog-import") -> dict:
    """Register ELIGIBLE catalog records in the governance overlay as ``candidate`` with an audit event. Idempotent.

    Only records whose adapter status is ELIGIBLE are written; the recorded hash must equal the current canonical hash (a stale
    evaluation is refused). The event is attributed to automation: it can never count as a human decision, and nothing is
    verified, validated or approved by this call.
    """
    catalog = _catalog()
    rows = await _rows(db)
    created, already, refused = [], [], []
    for item in evaluations:
        catalog_id = item["catalog_id"]
        entry = catalog.get(catalog_id)
        if entry is None or item.get("status") != "ELIGIBLE":
            refused.append({"catalog_id": catalog_id, "reason": "not ELIGIBLE or unknown record"})
            continue
        current = canonical_hash(entry)
        if item.get("content_hash") != current:
            refused.append({"catalog_id": catalog_id, "reason": "evaluation is stale (content hash changed)"})
            continue
        if catalog_id in rows:
            already.append(catalog_id)
            continue
        row = KnowledgeReview(catalog_id=catalog_id, catalog_source=_catalog_source(catalog_id, entry), content_hash=current,
                              lifecycle_status="candidate", revision=1)
        db.add(row)
        await db.flush()
        db.add(KnowledgeReviewEvent(
            catalog_id=catalog_id, event_type="catalog_import", from_status=None, to_status="candidate", actor=actor,
            rationale="registered for human review by the catalog adapter (eligibility verified); not verified, validated or approved",
            source_hash=current, revision=1,
            evidence={"actor_kind": "automation", "eligibility": {k: item.get(k) for k in ("status", "class", "reasons", "approval_scope_if_approved")}},
        ))
        created.append(catalog_id)
    await db.flush()
    return {"created": created, "already_registered": already, "refused": refused}
