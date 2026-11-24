"""Draft proposals for catalog candidates - a human-editable, hash-bound layer that is separate from active knowledge.

Why this shape (checked against the schema): ``KnowledgeEntry`` needs a real ``analysis_history`` row; catalog candidates have none and
a fabricated history is forbidden. The governance overlay already has an append-only event store keyed by ``catalog_id`` with a
JSONB evidence column, so a proposal is a sequence of events - no new table, no migration:

    CANDIDATE --draft_saved--> DRAFT --draft_submitted--> HUMAN_REVIEW --decision API (approved)--> APPROVED
        any open state becomes STALE when the catalog content changes; a rejected lifecycle shows REJECTED;
        BLOCKED/INELIGIBLE is the adapter's eligibility (reported next to the status, never stored).

* Draft content is a set of operational fields (``operational_fields`` shape) that a human supplies with sources. It is **never**
  read by the Analyzer: only an *approved* decision stores the supplement that the Analyzer may merge (see ``approved_supplement``).
* Every event records author, actor kind, base content hash, content digest, revision and time (the append-only table timestamps it).
* Saving identical content for the same base hash is idempotent (no duplicate event). Editing a submitted draft returns it to DRAFT.
* A draft prepared by AI or automation can be saved, but only a human may submit it, and the author of a draft cannot approve it.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.knowledge import service
from backend.domain.knowledge.catalog_adapter import (
    classify, evaluate, ImportContext, merge_supplement, operational_problems, operational_view, validate_operational_fields,
)
from backend.domain.knowledge.models import KnowledgeReviewEvent

DRAFT_EVENT_TYPES = ("draft_saved", "draft_submitted", "draft_withdrawn")
PROPOSAL_CLASSES = ("B", "D", "E")
ACTOR_KINDS = ("human", "ai_assist", "automation")


def digest(content: dict) -> str:
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def derive(entry: dict, events: list[dict], row) -> dict:
    """Current proposal state from the event history (pure)."""
    current = service.canonical_hash(entry)
    drafts = [e for e in events if e["event_type"] in DRAFT_EVENT_TYPES]
    last = drafts[-1] if drafts else None
    status = "CANDIDATE"
    if last and last["event_type"] == "draft_saved":
        status = "DRAFT"
    elif last and last["event_type"] == "draft_submitted":
        status = "HUMAN_REVIEW"
    stale = bool(last and last["event_type"] != "draft_withdrawn" and last["source_hash"] != current)
    if stale:
        status = "STALE"
    saved = next((e for e in reversed(drafts) if e["event_type"] == "draft_saved"), None)
    if row is not None and row.lifecycle_status == "approved" and row.content_hash == current:
        status = "APPROVED"
    elif row is not None and row.lifecycle_status == "rejected":
        status = "REJECTED"
    return {"status": status, "stale": stale, "currentContentHash": current, "baseContentHash": last["source_hash"] if last else None,
            "revisions": len([e for e in drafts if e["event_type"] == "draft_saved"]),
            "draft": (saved["evidence"] or {}).get("draft") if saved and last and last["event_type"] != "draft_withdrawn" else None,
            "draftAuthor": saved["actor"] if saved else None, "draftAuthorKind": (saved["evidence"] or {}).get("actor_kind") if saved else None,
            "draftDigest": (saved["evidence"] or {}).get("draft_digest") if saved else None,
            "history": [{"type": e["event_type"], "actor": e["actor"], "actorKind": (e["evidence"] or {}).get("actor_kind"), "revision": e["revision"],
                         "sourceHash": e["source_hash"], "at": e["created_at"], "note": e["rationale"]} for e in drafts]}


def preview(entry: dict, catalog_id: str, content: dict | None) -> dict:
    """Dry run: validation problems and what the record would lack with this draft applied. Writes nothing."""
    kind = service.catalog_kind(catalog_id)
    problems = validate_operational_fields(content) if content is not None else []
    view = operational_view(kind, entry)
    base_missing = operational_problems(view)
    would = operational_problems(merge_supplement(view, content or {})) if not problems else base_missing
    stated_only = sorted((content or {}).keys())
    unverified = sorted(k for k, v in (content or {}).items() if isinstance(v, dict) and v.get("state") == "unverified")
    return {"class": classify(kind, entry), "validationProblems": problems, "missingNow": base_missing, "missingWithDraft": would,
            "fieldsInDraft": stated_only, "unverifiedFields": unverified,
            "note": "unverified and not_stated fields never count as stated; only stated, source-backed fields can complete a record"}


async def get(db: AsyncSession, catalog_id: str) -> dict:
    entry = service._catalog().get(catalog_id)
    if entry is None:
        raise service.KnowledgeNotFound(f"unknown catalog id {catalog_id}")
    events = await service.history(db, catalog_id)
    row = (await service._rows(db)).get(catalog_id)
    kind = service.catalog_kind(catalog_id)
    out = derive(entry, events, row)
    # Technical-evidence freshness is an offline certification artifact; report operational completeness only.
    ctx = ImportContext(evidence_current=True, overlay_hash=None)
    out["eligibility"] = {k: v for k, v in evaluate(kind, entry, out["currentContentHash"], ctx).items() if k in ("class", "status", "reasons", "missing")}
    out["eligibility"]["basis"] = "operational completeness only; technical-evidence freshness is checked offline by tools/catalog_import.py"
    view = operational_view(kind, entry)
    out["view"] = view
    out["missing"] = operational_problems(view)
    out["class"] = classify(kind, entry)
    out["catalogId"] = catalog_id
    return out


def _guard(catalog_id: str, base_hash: str) -> tuple[dict, str]:
    entry = service._catalog().get(catalog_id)
    if entry is None:
        raise service.KnowledgeNotFound(f"unknown catalog id {catalog_id}")
    cls = classify(service.catalog_kind(catalog_id), entry)
    if cls not in PROPOSAL_CLASSES:
        raise service.KnowledgeTransitionRejected(f"class {cls} (context or reference) has no proposal path")
    current = service.canonical_hash(entry)
    if base_hash != current:
        raise service.KnowledgeTransitionRejected("the record changed since this draft was based on it (stale base hash)")
    return entry, current


def _event(catalog_id: str, kind: str, row, entry: dict, current: str, actor: str, actor_kind: str, note: str, revision: int, extra: dict) -> KnowledgeReviewEvent:
    status = row.lifecycle_status if row is not None else service.default_lifecycle(entry.get("knowledge_class", service.DIAGNOSTIC))
    return KnowledgeReviewEvent(catalog_id=catalog_id, event_type=kind, from_status=status, to_status=status, actor=actor, rationale=note,
                                source_hash=current, revision=revision, evidence={"actor_kind": actor_kind, **extra})


async def save_draft(db: AsyncSession, catalog_id: str, *, actor: str, actor_kind: str, content: dict, base_hash: str, note: str) -> dict:
    if actor_kind not in ACTOR_KINDS or not actor.strip():
        raise service.KnowledgePermissionError("an identified actor with a known actor kind is required")
    entry, current = _guard(catalog_id, base_hash)
    problems = validate_operational_fields(content)
    if problems or not content:
        raise service.KnowledgeTransitionRejected("invalid draft: " + ("; ".join(problems) if problems else "no fields"))
    events = await service.history(db, catalog_id)
    row = (await service._rows(db)).get(catalog_id)
    state = derive(entry, events, row)
    if state["status"] in ("APPROVED", "REJECTED"):
        raise service.KnowledgeTransitionRejected(f"a {state['status']} record cannot be edited; withdraw or supersede through the decision API")
    d = digest(content)
    if state["status"] in ("DRAFT", "HUMAN_REVIEW") and state["draftDigest"] == d:
        return {"created": False, **state}   # idempotent: identical content for the same base hash
    db.add(_event(catalog_id, "draft_saved", row, entry, current, actor.strip(), actor_kind, note, state["revisions"] + 1,
                  {"draft": content, "draft_digest": d}))
    await db.flush()
    return {"created": True, **derive(entry, await service.history(db, catalog_id), row)}


async def submit_draft(db: AsyncSession, catalog_id: str, *, actor: str, actor_kind: str, base_hash: str, note: str) -> dict:
    if actor_kind != "human":
        raise service.KnowledgePermissionError("only a human may submit a draft for review")
    entry, current = _guard(catalog_id, base_hash)
    events = await service.history(db, catalog_id)
    row = (await service._rows(db)).get(catalog_id)
    state = derive(entry, events, row)
    if state["status"] != "DRAFT":
        raise service.KnowledgeTransitionRejected(f"only a DRAFT can be submitted (status is {state['status']})")
    db.add(_event(catalog_id, "draft_submitted", row, entry, current, actor.strip(), actor_kind, note, state["revisions"],
                  {"draft_digest": state["draftDigest"], "prepared_by": state["draftAuthor"], "prepared_by_kind": state["draftAuthorKind"]}))
    await db.flush()
    return derive(entry, await service.history(db, catalog_id), row)


async def withdraw_draft(db: AsyncSession, catalog_id: str, *, actor: str, actor_kind: str, base_hash: str, note: str) -> dict:
    if actor_kind != "human":
        raise service.KnowledgePermissionError("only a human may withdraw a draft")
    entry = service._catalog().get(catalog_id)
    if entry is None:
        raise service.KnowledgeNotFound(f"unknown catalog id {catalog_id}")
    current = service.canonical_hash(entry)
    events = await service.history(db, catalog_id)
    row = (await service._rows(db)).get(catalog_id)
    state = derive(entry, events, row)
    if state["status"] not in ("DRAFT", "HUMAN_REVIEW", "STALE"):
        raise service.KnowledgeTransitionRejected(f"nothing to withdraw (status is {state['status']})")
    db.add(_event(catalog_id, "draft_withdrawn", row, entry, current, actor.strip(), actor_kind, note, state["revisions"], {}))
    await db.flush()
    return derive(entry, await service.history(db, catalog_id), row)


async def approved_supplement(db: AsyncSession, catalog_id: str) -> dict | None:
    """The human-approved supplement for the record's *current* content, or None. Drafts are never returned."""
    entry = service._catalog().get(catalog_id)
    row = (await service._rows(db)).get(catalog_id)
    if entry is None or row is None or row.lifecycle_status != "approved" or row.content_hash != service.canonical_hash(entry) or row.review_required:
        return None
    for event in reversed(await service.history(db, catalog_id)):
        if event["event_type"] == "transition" and event["to_status"] == "approved":
            sup = (event["evidence"] or {}).get("supplement")
            return sup if isinstance(sup, dict) and not validate_operational_fields(sup) else None
    return None


def merged_view(catalog_id: str, supplement: dict | None) -> dict:
    entry = service._catalog()[catalog_id]
    view = operational_view(service.catalog_kind(catalog_id), entry)
    return merge_supplement(view, supplement) if supplement else view


def public(state: dict[str, Any]) -> dict[str, Any]:
    return state


def _event_dict(r: KnowledgeReviewEvent) -> dict:
    return {"event_type": r.event_type, "actor": r.actor, "source_hash": r.source_hash, "revision": r.revision, "rationale": r.rationale,
            "evidence": r.evidence, "created_at": r.created_at.isoformat() if r.created_at else None, "to_status": r.to_status}


_PRIORITY = {"HUMAN_REVIEW": 0, "DRAFT": 1, "STALE": 2, "CANDIDATE": 3, "APPROVED": 4, "REJECTED": 5}


async def queue(db: AsyncSession) -> list[dict]:
    """Reviewer queue: every class B/D/E candidate with its proposal status and what an engineer still lacks. Read-only."""
    catalog = service._catalog()
    rows = await service._rows(db)
    events: dict[str, list[dict]] = {}
    result = await db.execute(select(KnowledgeReviewEvent).where(KnowledgeReviewEvent.event_type.in_(DRAFT_EVENT_TYPES))
                              .order_by(KnowledgeReviewEvent.created_at, KnowledgeReviewEvent.event_id))
    for r in result.scalars().all():
        events.setdefault(r.catalog_id, []).append(_event_dict(r))
    items = []
    for catalog_id, entry in catalog.items():
        kind = service.catalog_kind(catalog_id)
        cls = classify(kind, entry)
        if cls not in PROPOSAL_CLASSES:
            continue
        state = derive(entry, events.get(catalog_id, []), rows.get(catalog_id))
        view = operational_view(kind, entry)
        missing = operational_problems(view)
        row = rows.get(catalog_id)
        items.append({"catalogId": catalog_id, "class": cls, "title": view["whatHappened"][:140], "contentHash": state["currentContentHash"],
                      "proposalStatus": state["status"], "lifecycle": row.lifecycle_status if row else "candidate", "missing": missing,
                      "operationallyComplete": not missing, "sources": len(view["evidenceAndSource"]), "revisions": state["revisions"],
                      "draftAuthor": state["draftAuthor"]})
    items.sort(key=lambda i: (_PRIORITY.get(i["proposalStatus"], 9), i["class"], len(i["missing"]), i["catalogId"]))
    return items
