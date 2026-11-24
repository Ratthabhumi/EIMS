"""Access policy (owner-confirmed): EIMS has no application login and Analyzer use is open access. The read endpoints (queue, record,
history) are informational catalog and review-status views and follow that policy; every write (draft save/submit/withdraw, decision) requires
the reviewer capability below. The decider is never taken from the client.

Human decision API for catalog knowledge (source_verified / validated / approved / deprecated / superseded / rejected).

Trust model - everything that identifies the decider comes from the server:
* the principal is the caller resolved by ``require_knowledge_reviewer`` (a database user with a valid session AND the reviewer
  capability; the shared admin token, guest/demo and open-access callers are refused there);
* ``actor`` and ``actor_kind`` are set by the server (``human``); the request body cannot carry them and unknown fields are
  rejected, so a client cannot choose its own reviewer identity or kind;
* every decision is bound to the record's current content hash (a stale hash is refused with 409) and to its evidence references.
Automation and AI have no path here: they are not reviewer accounts. (The system cannot prove that the person behind a reviewer
account is not delegating to a tool; that residual risk is stated in the security report.)
"""
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.analyzer.auth import get_current_user, require_knowledge_reviewer
from backend.domain.knowledge import proposals, service
from backend.domain.knowledge.catalog_adapter import APPROVAL_SCOPES, classify, merge_supplement, operational_problems, operational_view
from backend.infrastructure.database import get_db_session as get_db

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]
KnowledgeReviewer = Annotated[str, Depends(require_knowledge_reviewer)]
AuthenticatedUser = Annotated[str, Depends(get_current_user)]
FORBIDDEN_PAYLOAD_KEYS = {"actor", "actor_kind", "actorKind", "reviewer", "reviewer_id", "reviewedBy", "verifier", "approved_by"}
Target = Literal["candidate", "source_verified", "validated", "approved", "rejected", "deprecated", "superseded"]
Scope = Literal["approved_as_diagnostic", "approved_as_reference", "approved_as_state_reference"]


class GovernanceDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    catalog_id: str = Field(min_length=3, max_length=160)
    target: Target
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    rationale: str = Field(min_length=10, max_length=2000)
    review: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[HttpUrl] = Field(default_factory=list, max_length=10)
    approval_scope: Scope | None = None

    @field_validator("review")
    @classmethod
    def review_cannot_name_a_decider(cls, value):
        clash = FORBIDDEN_PAYLOAD_KEYS & set(value)
        if clash:
            raise ValueError(f"the decider is determined by the server; remove {sorted(clash)}")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def https_only(cls, values):
        if any(v.scheme != "https" or v.username or v.password for v in values):
            raise ValueError("evidence references must use HTTPS without embedded credentials")
        return values


def _problem(status: int, code: str, message: str, **extra):
    return HTTPException(status_code=status, detail={"code": code, "message": message, **extra})


@router.post("/decisions", status_code=201)
async def record_governance_decision(request: GovernanceDecisionRequest, db: DbSession, principal: KnowledgeReviewer):
    entry = service._catalog().get(request.catalog_id)
    if entry is None:
        raise _problem(404, "unknown_record", "catalog_id does not reference a known knowledge record")
    current = service.canonical_hash(entry)
    if request.content_hash != current:
        raise _problem(409, "stale_content_hash", "the record changed after the evidence was gathered; re-review the current version", currentContentHash=current)
    kind = service.catalog_kind(request.catalog_id)
    cls = classify(kind, entry)
    supplement = None
    if request.target == "approved":
        proposal = await proposals.get(db, request.catalog_id)
        if proposal["status"] == "HUMAN_REVIEW" and not proposal["stale"] and proposal["draft"]:
            if proposal["draftAuthor"] == principal:
                raise _problem(403, "author_cannot_approve", "the author of a draft cannot approve its supplement; another reviewer must decide")
            supplement = proposal["draft"]
    if request.target == "approved":
        expected = APPROVAL_SCOPES.get(cls)
        if expected is None:
            raise _problem(422, "class_not_approvable", "Windows operational context has no approval path; it can only be a candidate")
        if request.approval_scope != expected:
            raise _problem(422, "wrong_approval_scope", f"class {cls} may only be approved as {expected}", allowedScope=expected)
        if expected == "approved_as_diagnostic":
            view = operational_view(kind, entry)
            problems = operational_problems(merge_supplement(view, supplement) if supplement else view)
            if problems:
                raise _problem(422, "operational_contract_incomplete", "a diagnostic approval needs every operational section stated", missing=problems)
    elif request.approval_scope is not None:
        raise _problem(422, "scope_only_for_approval", "approval_scope is only valid for the approved decision")
    review = dict(request.review)
    review["verifier"] = principal  # server-set: the gate requires the verifier to be the authenticated actor
    review["evidence_refs"] = [str(u) for u in request.evidence_refs]
    if request.approval_scope:
        review["approval_scope"] = request.approval_scope
    review["record_class"] = cls
    if supplement:
        review["supplement"] = supplement
        review["supplement_digest"] = proposals.digest(supplement)
    try:
        row = await service.promote(db, request.catalog_id, request.target, actor=principal, actor_kind="human",
                                    rationale=request.rationale, review=review)
        await db.commit()
    except service.KnowledgePermissionError as exc:
        await db.rollback()
        raise _problem(403, "permission_denied", str(exc)) from exc
    except service.KnowledgeNotFound as exc:
        await db.rollback()
        raise _problem(404, "unknown_record", str(exc)) from exc
    except service.KnowledgeTransitionRejected as exc:
        await db.rollback()
        raise _problem(422, "transition_rejected", str(exc)) from exc
    return {"catalogId": request.catalog_id, "status": row.lifecycle_status, "revision": row.revision, "actor": principal, "actorKind": "human",
            "contentHash": current, "approvalScope": request.approval_scope, "recordClass": cls}


@router.get("/history")
async def governance_history(db: DbSession, _user: AuthenticatedUser, catalog_id: str = Query(min_length=3, max_length=160)):
    entry = service._catalog().get(catalog_id)
    if entry is None:
        raise _problem(404, "unknown_record", "catalog_id does not reference a known knowledge record")
    events = await service.history(db, catalog_id)
    rows = await service._rows(db)
    row = rows.get(catalog_id)
    current = service.canonical_hash(entry)
    return {"catalogId": catalog_id, "currentContentHash": current,
            "status": row.lifecycle_status if row else service.default_lifecycle(entry.get("knowledge_class", service.DIAGNOSTIC)),
            "stale": bool(row and (row.review_required or row.content_hash != current)), "events": events}


# ---- draft proposals (human-editable, hash-bound, separate from active guidance) ---------------------------------------------------
class ProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    catalog_id: str = Field(min_length=3, max_length=160)
    base_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    content: dict[str, Any] = Field(default_factory=dict)
    note: str = Field(default="", max_length=2000)


class ProposalPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    catalog_id: str = Field(min_length=3, max_length=160)
    content: dict[str, Any] = Field(default_factory=dict)


def _proposal_error(exc: Exception):
    if isinstance(exc, service.KnowledgePermissionError):
        return _problem(403, "permission_denied", str(exc))
    if isinstance(exc, service.KnowledgeNotFound):
        return _problem(404, "unknown_record", str(exc))
    return _problem(422, "proposal_rejected", str(exc))


@router.get("/queue")
async def reviewer_queue(db: DbSession, _user: AuthenticatedUser):
    items = await proposals.queue(db)
    return {"items": items, "total": len(items)}


@router.get("/proposals")
async def get_proposal(db: DbSession, _user: AuthenticatedUser, catalog_id: str = Query(min_length=3, max_length=160)):
    try:
        return await proposals.get(db, catalog_id)
    except service.KnowledgeNotFound as exc:
        raise _proposal_error(exc) from exc


@router.post("/proposals/preview")
async def preview_proposal(request: ProposalPreviewRequest, _principal: KnowledgeReviewer):
    entry = service._catalog().get(request.catalog_id)
    if entry is None:
        raise _problem(404, "unknown_record", "catalog_id does not reference a known knowledge record")
    return proposals.preview(entry, request.catalog_id, request.content)   # dry run: nothing is written


@router.post("/proposals", status_code=201)
async def save_proposal(request: ProposalRequest, db: DbSession, principal: KnowledgeReviewer):
    try:
        result = await proposals.save_draft(db, request.catalog_id, actor=principal, actor_kind="human", content=request.content,
                                            base_hash=request.base_hash, note=request.note)
        await db.commit()
    except (service.KnowledgeError,) as exc:
        await db.rollback()
        raise _proposal_error(exc) from exc
    return result


@router.post("/proposals/submit")
async def submit_proposal(request: ProposalRequest, db: DbSession, principal: KnowledgeReviewer):
    try:
        result = await proposals.submit_draft(db, request.catalog_id, actor=principal, actor_kind="human", base_hash=request.base_hash, note=request.note)
        await db.commit()
    except (service.KnowledgeError,) as exc:
        await db.rollback()
        raise _proposal_error(exc) from exc
    return result


@router.post("/proposals/withdraw")
async def withdraw_proposal(request: ProposalRequest, db: DbSession, principal: KnowledgeReviewer):
    try:
        result = await proposals.withdraw_draft(db, request.catalog_id, actor=principal, actor_kind="human", base_hash=request.base_hash, note=request.note)
        await db.commit()
    except (service.KnowledgeError,) as exc:
        await db.rollback()
        raise _proposal_error(exc) from exc
    return result
