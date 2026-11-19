import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.analyzer.auth import get_current_user, require_knowledge_reviewer
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.models.knowledge import (
    KnowledgeEntry,
    KnowledgeLifecycleEvent,
    KnowledgeUsage,
    KnowledgeSourceCandidate,
    KnowledgeSourceEvent,
)
from backend.domain.analyzer.services.vector_db import redact_for_embedding
from backend.infrastructure.database import get_db_session as get_db

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
AuthenticatedUser = Annotated[str, Depends(get_current_user)]
KnowledgeReviewer = Annotated[str, Depends(require_knowledge_reviewer)]
KnowledgeLimit = Annotated[int, Query(ge=1, le=100)]
KnowledgeOffset = Annotated[int, Query(ge=0, le=10000)]
SourceFamilyFilter = Annotated[str | None, Query(min_length=1, max_length=64)]
DiagnosticIdentityFilter = Annotated[str | None, Query(min_length=1, max_length=256)]
KnowledgeSearchQuery = Annotated[str | None, Query(min_length=2, max_length=160)]

StepText = Annotated[str, Field(min_length=3, max_length=1200)]
EvidenceText = Annotated[str, Field(min_length=3, max_length=1000)]
KNOWN_SOURCE_FAMILIES = {
    "windows_event", "veeam_vbr", "vmware", "fortinet", "cisco_asa",
    "palo_alto", "linux_syslog", "json", "unknown_text",
}


class KnowledgeProposalRequest(BaseModel):
    history_id: int = Field(gt=0)
    title: str = Field(min_length=3, max_length=200)
    resolution_status: Literal["resolved", "partially_resolved", "unresolved"]
    root_cause: str = Field(min_length=3, max_length=4000)
    solution_steps: list[StepText] = Field(min_length=1, max_length=12)
    impact: str = Field(default="", max_length=2000)
    prevention: str = Field(default="", max_length=2000)
    product_name: str | None = Field(default=None, max_length=128)
    product_version: str | None = Field(default=None, max_length=64)
    environment: str | None = Field(default=None, max_length=64)
    prerequisites: list[StepText] = Field(default_factory=list, max_length=8)
    risk_level: Literal["low", "medium", "high", "critical"] = "medium"
    validation_steps: list[StepText] = Field(default_factory=list, max_length=8)
    rollback_steps: list[StepText] = Field(default_factory=list, max_length=8)
    evidence_notes: list[EvidenceText] = Field(min_length=1, max_length=10)
    references: list[HttpUrl] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def high_risk_requires_validation_and_rollback(self):
        if self.risk_level in {"high", "critical"} and (not self.validation_steps or not self.rollback_steps):
            raise ValueError("High/Critical risk knowledge requires validation and rollback steps")
        return self

    @field_validator("references")
    @classmethod
    def https_references_only(cls, values):
        if any(url.scheme != "https" or url.username or url.password for url in values):
            raise ValueError("Knowledge references must use HTTPS without embedded credentials")
        return values


class KnowledgeReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    note: str = Field(default="", min_length=5, max_length=2000)


class KnowledgeUsageRequest(BaseModel):
    history_id: int = Field(gt=0)
    outcome: Literal["resolved", "partially_resolved", "not_resolved", "not_attempted"]
    notes: str = Field(default="", max_length=2000)


class KnowledgeLifecycleRequest(BaseModel):
    action: Literal["require_review", "revalidate", "supersede", "withdraw"]
    note: str = Field(min_length=5, max_length=2000)
    reason: str = Field(min_length=3, max_length=1000)
    superseded_by_id: int | None = Field(default=None, gt=0)


def _clean(value: str) -> str:
    return redact_for_embedding(value.strip())


def _source_history_hash(history: AnalysisHistory) -> str:
    source_material = json.dumps(
        {
            "event_id": history.event_id,
            "provider": history.provider,
            "description": history.description,
            "event_metadata": history.event_metadata,
            "solution_summary": history.solution_summary,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(source_material.encode("utf-8")).hexdigest()


def _serialize(entry: KnowledgeEntry, *, private: bool = False) -> dict:
    result = {
        "id": entry.id,
        "title": entry.title,
        "sourceFamily": entry.source_family,
        "diagnosticIdentity": entry.diagnostic_identity,
        "resolutionStatus": entry.resolution_status,
        "rootCause": entry.root_cause,
        "solutionSteps": list(entry.solution_steps or []),
        "impact": entry.impact,
        "prevention": entry.prevention,
        "productName": entry.product_name,
        "productVersion": entry.product_version,
        "environment": entry.environment,
        "prerequisites": list(entry.prerequisites or []),
        "riskLevel": entry.risk_level,
        "validationSteps": list(entry.validation_steps or []),
        "rollbackSteps": list(entry.rollback_steps or []),
        "evidenceNotes": list(entry.evidence_notes or []),
        "references": list(entry.references or []),
        "status": entry.status,
        "sourceHistoryHash": entry.source_history_hash,
        "proposedBy": entry.proposed_by,
        "createdAt": entry.created_at.isoformat() if entry.created_at else None,
        "reviewedBy": entry.reviewed_by,
        "reviewedAt": entry.reviewed_at.isoformat() if entry.reviewed_at else None,
        "reviewNote": entry.review_note,
        "lifecycleState": entry.lifecycle_state,
        "lifecycleReason": entry.lifecycle_reason,
        "lifecycleUpdatedAt": entry.lifecycle_updated_at.isoformat() if entry.lifecycle_updated_at else None,
        "supersededById": entry.superseded_by_id,
    }
    if private:
        result["sourceHistoryId"] = entry.source_history_id
    return result


@router.post("/proposals", status_code=201)
async def propose_knowledge(
    request: KnowledgeProposalRequest,
    db: DbSession,
    user: AuthenticatedUser,
):
    history = (
        await db.execute(
            select(AnalysisHistory).where(
                AnalysisHistory.id == request.history_id,
                AnalysisHistory.username == user,
            )
        )
    ).scalars().first()
    if history is None:
        raise HTTPException(status_code=404, detail="History record not found")

    existing = (
        await db.execute(
            select(KnowledgeEntry.id).where(
                KnowledgeEntry.source_history_id == history.id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="This incident already has a knowledge proposal")

    metadata = history.event_metadata if isinstance(history.event_metadata, dict) else {}
    source_family = str(metadata.get("sourceFamily") or "unknown_text").strip().lower()[:64]
    if source_family not in KNOWN_SOURCE_FAMILIES:
        source_family = "unknown_text"
    diagnostic_identity = str(
        metadata.get("diagnosticCode") or history.event_id or "Unknown"
    ).strip()[:256]
    source_history_hash = _source_history_hash(history)
    clean_title = _clean(request.title)
    clean_root_cause = _clean(request.root_cause)
    clean_steps = [_clean(step) for step in request.solution_steps]
    clean_prerequisites = [_clean(step) for step in request.prerequisites]
    clean_validation = [_clean(step) for step in request.validation_steps]
    clean_rollback = [_clean(step) for step in request.rollback_steps]
    clean_evidence = [_clean(note) for note in request.evidence_notes]
    if len(clean_title) < 3 or len(clean_root_cause) < 3:
        raise HTTPException(status_code=422, detail="Title and root cause must remain meaningful after sensitive-data redaction")
    if not clean_steps or any(len(step) < 3 for step in clean_steps):
        raise HTTPException(status_code=422, detail="At least one non-empty resolution step is required")
    if not clean_evidence or any(len(note) < 3 for note in clean_evidence):
        raise HTTPException(status_code=422, detail="At least one non-empty evidence note is required")
    if any(len(step) < 3 for step in (*clean_prerequisites, *clean_validation, *clean_rollback)):
        raise HTTPException(status_code=422, detail="Applicability and safety steps must remain meaningful after sensitive-data redaction")
    if request.risk_level in {"high", "critical"} and (not clean_validation or not clean_rollback):
        raise HTTPException(status_code=422, detail="High/Critical risk knowledge requires non-empty validation and rollback steps")

    entry = KnowledgeEntry(
        source_history_id=history.id,
        source_history_hash=source_history_hash,
        source_family=source_family,
        diagnostic_identity=diagnostic_identity,
        title=clean_title,
        resolution_status=request.resolution_status,
        root_cause=clean_root_cause,
        solution_steps=clean_steps,
        impact=_clean(request.impact),
        prevention=_clean(request.prevention),
        product_name=_clean(request.product_name) if request.product_name else None,
        product_version=_clean(request.product_version) if request.product_version else None,
        environment=_clean(request.environment) if request.environment else None,
        prerequisites=clean_prerequisites,
        risk_level=request.risk_level,
        validation_steps=clean_validation,
        rollback_steps=clean_rollback,
        evidence_notes=clean_evidence,
        references=[str(url) for url in request.references],
        status="pending",
        proposed_by=user,
    )
    db.add(entry)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This incident already has a knowledge proposal") from exc
    return _serialize(entry, private=True)


@router.get("/proposals/mine")
async def my_proposals(
    db: DbSession,
    user: AuthenticatedUser,
    limit: KnowledgeLimit = 50,
    offset: KnowledgeOffset = 0,
):
    rows = (
        await db.execute(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.proposed_by == user)
            .order_by(KnowledgeEntry.created_at.desc(), KnowledgeEntry.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return {"items": [_serialize(row, private=True) for row in rows], "limit": limit, "offset": offset}


@router.get("/review-queue")
async def review_queue(
    db: DbSession,
    _reviewer: KnowledgeReviewer,
    limit: KnowledgeLimit = 50,
    offset: KnowledgeOffset = 0,
):
    rows = (
        await db.execute(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.status == "pending")
            .order_by(KnowledgeEntry.created_at.asc(), KnowledgeEntry.id.asc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return {"items": [_serialize(row, private=True) for row in rows], "limit": limit, "offset": offset}


@router.post("/{knowledge_id}/review")
async def review_knowledge(
    knowledge_id: int,
    request: KnowledgeReviewRequest,
    db: DbSession,
    reviewer: KnowledgeReviewer,
):
    entry = (
        await db.execute(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.id == knowledge_id)
            .with_for_update()
        )
    ).scalars().first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Knowledge proposal not found")
    if entry.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending knowledge can be reviewed")
    if entry.proposed_by == reviewer:
        raise HTTPException(status_code=409, detail="A proposer cannot approve or reject their own knowledge")
    if len(request.note.strip()) < 5:
        raise HTTPException(status_code=422, detail="A review note of at least five characters is required")

    if request.decision == "approve":
        if entry.resolution_status == "unresolved":
            raise HTTPException(status_code=422, detail="Unresolved incidents cannot be published as reusable fixes")
        if entry.risk_level in {"high", "critical"} and (not entry.validation_steps or not entry.rollback_steps):
            raise HTTPException(status_code=422, detail="High/Critical risk knowledge requires validation and rollback steps")
        if entry.source_family not in KNOWN_SOURCE_FAMILIES - {"unknown_text"} or entry.diagnostic_identity == "Unknown":
            raise HTTPException(status_code=422, detail="A known source family and diagnostic identity are required")
        if (
            not entry.root_cause.strip()
            or not any(str(step).strip() for step in (entry.solution_steps or []))
            or not any(str(note).strip() for note in (entry.evidence_notes or []))
        ):
            raise HTTPException(status_code=422, detail="Root cause, solution steps and evidence are required")
        source_history = await db.get(AnalysisHistory, entry.source_history_id)
        if source_history is None or not hmac.compare_digest(
            _source_history_hash(source_history), entry.source_history_hash
        ):
            raise HTTPException(status_code=409, detail="Source incident evidence changed after proposal; review is blocked")

    entry.status = "approved" if request.decision == "approve" else "rejected"
    entry.reviewed_by = reviewer
    entry.reviewed_at = datetime.now(UTC)
    entry.review_note = _clean(request.note)
    await db.commit()
    return _serialize(entry, private=True)


@router.post("/{knowledge_id}/lifecycle")
async def change_knowledge_lifecycle(
    knowledge_id: int,
    request: KnowledgeLifecycleRequest,
    db: DbSession,
    reviewer: KnowledgeReviewer,
):
    """Apply an independently reviewed lifecycle transition without editing source knowledge."""
    entry = await db.scalar(
        select(KnowledgeEntry)
        .where(KnowledgeEntry.id == knowledge_id)
        .with_for_update()
    )
    if entry is None or entry.status != "approved":
        raise HTTPException(status_code=404, detail="Approved knowledge not found")
    if entry.proposed_by == reviewer:
        raise HTTPException(status_code=409, detail="A proposer cannot review their own knowledge lifecycle")

    note = _clean(request.note)
    reason = _clean(request.reason)
    if len(note) < 5 or len(reason) < 3:
        raise HTTPException(status_code=422, detail="Lifecycle reason and note must remain meaningful after redaction")

    previous = entry.lifecycle_state
    superseded_by_id = None
    if request.action == "require_review":
        if previous != "active" or request.superseded_by_id is not None:
            raise HTTPException(status_code=409, detail="Only active knowledge can be marked for revalidation")
        target = "revalidation_required"
    elif request.action == "revalidate":
        if previous != "revalidation_required" or request.superseded_by_id is not None:
            raise HTTPException(status_code=409, detail="Only knowledge requiring revalidation can be reactivated")
        target = "active"
    elif request.action == "supersede":
        if previous not in {"active", "revalidation_required"} or request.superseded_by_id is None:
            raise HTTPException(status_code=422, detail="Superseding requires a replacement approved knowledge ID")
        replacement = await db.scalar(
            select(KnowledgeEntry).where(
                KnowledgeEntry.id == request.superseded_by_id,
                KnowledgeEntry.status == "approved",
                KnowledgeEntry.lifecycle_state == "active",
            )
        )
        if (
            replacement is None
            or replacement.id == entry.id
            or replacement.source_family != entry.source_family
            or replacement.diagnostic_identity != entry.diagnostic_identity
        ):
            raise HTTPException(status_code=422, detail="Replacement must be different active approved knowledge with the same diagnostic identity")
        target = "superseded"
        superseded_by_id = replacement.id
    else:
        if previous not in {"active", "revalidation_required"} or request.superseded_by_id is not None:
            raise HTTPException(status_code=409, detail="Only active or review-required knowledge can be withdrawn")
        target = "withdrawn"

    entry.lifecycle_state = target
    entry.lifecycle_reason = reason
    entry.lifecycle_updated_at = datetime.now(UTC)
    entry.superseded_by_id = superseded_by_id
    db.add(
        KnowledgeLifecycleEvent(
            knowledge_entry_id=entry.id,
            from_state=previous,
            to_state=target,
            action=request.action,
            reason=reason,
            note=note,
            changed_by=reviewer,
        )
    )
    await db.commit()
    return _serialize(entry, private=True)


@router.get("/lifecycle/review-queue")
async def knowledge_lifecycle_review_queue(
    db: DbSession,
    _reviewer: KnowledgeReviewer,
    limit: KnowledgeLimit = 50,
    offset: KnowledgeOffset = 0,
):
    rows = (
        await db.execute(
            select(KnowledgeEntry)
            .where(
                KnowledgeEntry.status == "approved",
                KnowledgeEntry.lifecycle_state == "revalidation_required",
            )
            .order_by(KnowledgeEntry.lifecycle_updated_at.asc(), KnowledgeEntry.id.asc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return {"items": [_serialize(row, private=True) for row in rows], "limit": limit, "offset": offset}


@router.get("/{knowledge_id}/lifecycle/events")
async def knowledge_lifecycle_events(
    knowledge_id: int,
    db: DbSession,
    _user: AuthenticatedUser,
):
    entry = await db.scalar(select(KnowledgeEntry.id).where(KnowledgeEntry.id == knowledge_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    rows = (
        await db.execute(
            select(KnowledgeLifecycleEvent)
            .where(KnowledgeLifecycleEvent.knowledge_entry_id == knowledge_id)
            .order_by(KnowledgeLifecycleEvent.created_at.asc(), KnowledgeLifecycleEvent.id.asc())
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": row.id,
                "fromState": row.from_state,
                "toState": row.to_state,
                "action": row.action,
                "reason": row.reason,
                "note": row.note,
                "changedBy": row.changed_by,
                "createdAt": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }


@router.post("/{knowledge_id}/usage", status_code=201)
async def record_knowledge_usage(
    knowledge_id: int,
    request: KnowledgeUsageRequest,
    db: DbSession,
    user: AuthenticatedUser,
):
    entry = await db.scalar(
        select(KnowledgeEntry).where(
            KnowledgeEntry.id == knowledge_id,
            KnowledgeEntry.status == "approved",
            KnowledgeEntry.lifecycle_state == "active",
        )
    )
    history = await db.scalar(
        select(AnalysisHistory).where(
            AnalysisHistory.id == request.history_id,
            AnalysisHistory.username == user,
        )
    )
    if entry is None or history is None:
        raise HTTPException(status_code=404, detail="Approved knowledge or owned history not found")

    usage = KnowledgeUsage(
        knowledge_entry_id=entry.id,
        history_id=history.id,
        history_hash=_source_history_hash(history),
        outcome=request.outcome,
        notes=_clean(request.notes),
        reported_by=user,
    )
    db.add(usage)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="An outcome was already recorded for this knowledge and history") from exc
    return {
        "id": usage.id,
        "knowledgeId": entry.id,
        "historyId": history.id,
        "outcome": usage.outcome,
        "historyHash": usage.history_hash,
        "reportedBy": user,
        "createdAt": usage.created_at.isoformat() if usage.created_at else None,
    }


@router.get("/{knowledge_id}/usage-summary")
async def knowledge_usage_summary(
    knowledge_id: int,
    db: DbSession,
    _user: AuthenticatedUser,
):
    entry = await db.scalar(
        select(KnowledgeEntry.id).where(
            KnowledgeEntry.id == knowledge_id,
            KnowledgeEntry.status == "approved",
        )
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Approved knowledge not found")
    rows = (
        await db.execute(
            select(KnowledgeUsage.outcome, func.count())
            .where(KnowledgeUsage.knowledge_entry_id == knowledge_id)
            .group_by(KnowledgeUsage.outcome)
        )
    ).all()
    counts = {"resolved": 0, "partially_resolved": 0, "not_resolved": 0, "not_attempted": 0}
    for outcome, count in rows:
        counts[outcome] = count
    return {"knowledgeId": knowledge_id, "total": sum(counts.values()), "outcomes": counts}


@router.get("")
@router.get("/")
async def list_approved_knowledge(
    db: DbSession,
    _user: AuthenticatedUser,
    source_family: SourceFamilyFilter = None,
    diagnostic_identity: DiagnosticIdentityFilter = None,
    q: KnowledgeSearchQuery = None,
    limit: KnowledgeLimit = 50,
    offset: KnowledgeOffset = 0,
):
    filters = [
        KnowledgeEntry.status == "approved",
        KnowledgeEntry.lifecycle_state == "active",
    ]
    if source_family:
        filters.append(KnowledgeEntry.source_family == source_family.strip().lower())
    if diagnostic_identity:
        filters.append(KnowledgeEntry.diagnostic_identity == diagnostic_identity.strip())
    if q:
        # Literal substring search: escape LIKE metacharacters and keep the
        # query parameterized. Search approved knowledge only; never surface
        # pending/rejected proposals through discovery.
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{term}%"
        searchable = (
            KnowledgeEntry.title,
            KnowledgeEntry.source_family,
            KnowledgeEntry.diagnostic_identity,
            KnowledgeEntry.root_cause,
            cast(KnowledgeEntry.solution_steps, Text),
            KnowledgeEntry.impact,
            KnowledgeEntry.prevention,
            KnowledgeEntry.product_name,
            KnowledgeEntry.product_version,
            KnowledgeEntry.environment,
            cast(KnowledgeEntry.prerequisites, Text),
            cast(KnowledgeEntry.validation_steps, Text),
            cast(KnowledgeEntry.rollback_steps, Text),
            cast(KnowledgeEntry.evidence_notes, Text),
            cast(KnowledgeEntry.references, Text),
        )
        filters.append(or_(*(field.ilike(pattern, escape="\\") for field in searchable)))
    rows = (
        await db.execute(
            select(KnowledgeEntry)
            .where(*filters)
            .order_by(KnowledgeEntry.reviewed_at.desc(), KnowledgeEntry.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return {"items": [_serialize(row) for row in rows], "limit": limit, "offset": offset}


class KnowledgeSourceReviewRequest(BaseModel):
    decision: Literal["verify_reference", "reject", "require_revalidation", "withdraw"]
    note: str = Field(min_length=10, max_length=2000)


def _serialize_source_candidate(candidate: KnowledgeSourceCandidate) -> dict:
    return {
        "id": candidate.id,
        "sourceKey": candidate.source_key,
        "vendor": candidate.vendor,
        "product": candidate.product,
        "versionScope": candidate.version_scope,
        "domain": candidate.domain,
        "identity": candidate.identity,
        "title": candidate.title,
        "url": candidate.source_url,
        "applicability": candidate.applicability,
        "prerequisites": list(candidate.prerequisites or []),
        "evidence": list(candidate.evidence or []),
        "limitations": list(candidate.limitations or []),
        "nextChecks": list(candidate.next_checks or []),
        "validation": list(candidate.validation or []),
        "rollback": list(candidate.rollback or []),
        "riskLevel": candidate.risk_level,
        "evidenceStatus": candidate.evidence_status,
        "reviewState": candidate.review_state,
        "catalogSchemaVersion": candidate.catalog_schema_version,
        "catalogueRecordHash": candidate.source_hash,
        "importedAt": candidate.imported_at.isoformat() if candidate.imported_at else None,
        "reviewedBy": candidate.reviewed_by,
        "reviewedAt": candidate.reviewed_at.isoformat() if candidate.reviewed_at else None,
        "reviewNote": candidate.review_note,
        "updatedAt": candidate.updated_at.isoformat() if candidate.updated_at else None,
    }


@router.get("/sources")
async def list_knowledge_source_candidates(
    db: DbSession,
    _user: AuthenticatedUser,
    vendor: str | None = Query(default=None, min_length=1, max_length=128),
    review_state: str | None = Query(default=None, min_length=1, max_length=32),
    q: str | None = Query(default=None, min_length=2, max_length=160),
    limit: KnowledgeLimit = 50,
    offset: KnowledgeOffset = 0,
):
    filters = []
    if vendor:
        filters.append(KnowledgeSourceCandidate.vendor.ilike(vendor.strip()))
    if review_state:
        allowed = {
            "pending_domain_review", "verified_reference", "rejected",
            "revalidation_required", "withdrawn",
        }
        if review_state not in allowed:
            raise HTTPException(status_code=422, detail="Unknown source review state")
        filters.append(KnowledgeSourceCandidate.review_state == review_state)
    if q:
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{term}%"
        filters.append(or_(
            KnowledgeSourceCandidate.vendor.ilike(pattern, escape="\\"),
            KnowledgeSourceCandidate.product.ilike(pattern, escape="\\"),
            KnowledgeSourceCandidate.identity.ilike(pattern, escape="\\"),
            KnowledgeSourceCandidate.title.ilike(pattern, escape="\\"),
            KnowledgeSourceCandidate.applicability.ilike(pattern, escape="\\"),
        ))
    rows = (await db.execute(
        select(KnowledgeSourceCandidate)
        .where(*filters)
        .order_by(KnowledgeSourceCandidate.vendor, KnowledgeSourceCandidate.product,
                  KnowledgeSourceCandidate.source_key)
        .limit(limit).offset(offset)
    )).scalars().all()
    total = await db.scalar(
        select(func.count()).select_from(KnowledgeSourceCandidate).where(*filters)
    )
    return {
        "items": [_serialize_source_candidate(row) for row in rows],
        "total": int(total or 0), "limit": limit, "offset": offset,
    }


@router.post("/sources/{source_id}/review")
async def review_knowledge_source_candidate(
    source_id: int,
    request: KnowledgeSourceReviewRequest,
    db: DbSession,
    reviewer: KnowledgeReviewer,
):
    candidate = await db.scalar(
        select(KnowledgeSourceCandidate)
        .where(KnowledgeSourceCandidate.id == source_id)
        .with_for_update()
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Source candidate not found")

    previous = candidate.review_state
    if request.decision == "verify_reference":
        if previous not in {"pending_domain_review", "revalidation_required"}:
            raise HTTPException(status_code=409, detail="Only pending or revalidation-required sources can be verified")
        target = "verified_reference"
    elif request.decision == "reject":
        if previous not in {"pending_domain_review", "revalidation_required"}:
            raise HTTPException(status_code=409, detail="Only pending or revalidation-required sources can be rejected")
        target = "rejected"
    elif request.decision == "require_revalidation":
        if previous != "verified_reference":
            raise HTTPException(status_code=409, detail="Only verified references can require revalidation")
        target = "revalidation_required"
    else:
        if previous == "withdrawn":
            raise HTTPException(status_code=409, detail="Source candidate is already withdrawn")
        target = "withdrawn"

    note = _clean(request.note)
    if len(note) < 10:
        raise HTTPException(status_code=422, detail="Review note must remain meaningful after redaction")
    candidate.review_state = target
    candidate.reviewed_by = reviewer
    candidate.reviewed_at = datetime.now(UTC)
    candidate.review_note = note
    candidate.updated_at = datetime.now(UTC)
    db.add(KnowledgeSourceEvent(
        source_candidate_id=candidate.id,
        action=request.decision,
        from_state=previous,
        to_state=target,
        source_hash=candidate.source_hash,
        note=note,
        changed_by=reviewer,
    ))
    await db.commit()
    return _serialize_source_candidate(candidate)


@router.get("/sources/{source_id}/events")
async def knowledge_source_candidate_events(
    source_id: int,
    db: DbSession,
    _user: AuthenticatedUser,
):
    candidate = await db.scalar(
        select(KnowledgeSourceCandidate.id).where(KnowledgeSourceCandidate.id == source_id)
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Source candidate not found")
    rows = (await db.execute(
        select(KnowledgeSourceEvent)
        .where(KnowledgeSourceEvent.source_candidate_id == source_id)
        .order_by(KnowledgeSourceEvent.created_at.asc(), KnowledgeSourceEvent.id.asc())
    )).scalars().all()
    return {"items": [{
        "id": row.id,
        "action": row.action,
        "fromState": row.from_state,
        "toState": row.to_state,
        "catalogueRecordHash": row.source_hash,
        "note": row.note,
        "changedBy": row.changed_by,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    } for row in rows]}
