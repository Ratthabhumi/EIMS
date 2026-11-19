"""
==============================================================================
EIMS Incident Core Service (v1)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 4 & 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================

Transactional, idempotent incident creation and lifecycle management.

Design boundaries:
- Incident + evidence + audit rows commit in ONE transaction.
- Evidence is reference-only: (source_type, source_id) plus a digest; payloads
  are never copied into the incident domain.
- Correlation is deterministic (see correlation.py). Root cause is never
  inferred: `root_cause_state` remains 'unknown' unless a human/API records
  hypothesis or confirmation explicitly.
- No automatic closure and no automatic remediation.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger import get_logger
from backend.domain.asset_registry.models import AuditLog, InfrastructureAsset
from backend.domain.incident.correlation import (
    CONFIDENCE_NONE,
    CONFIDENCE_RANK,
    CONFIDENCE_WEAK,
    DEFAULT_WINDOW_SECONDS,
    CorrelationAssessment,
    CorrelationInput,
    build_dedupe_key,
    build_evidence_digest,
    classify,
    normalize_observed_at,
    normalize_signature,
    window_bucket,
)
from backend.domain.incident.models import (
    INCIDENT_SEVERITIES,
    Incident,
    IncidentEvidence,
    IncidentVerification,
)
from backend.domain.incident.verification import (
    VerificationRejected,
    VerificationRequest,
    build_record,
    evaluate as evaluate_verification,
)

logger = get_logger("eims.incident.service")

ACTION_INCIDENT_CREATED = "INCIDENT_CREATED"
ACTION_INCIDENT_STATUS_CHANGED = "INCIDENT_STATUS_CHANGED"
ACTION_INCIDENT_EVIDENCE_ADDED = "INCIDENT_EVIDENCE_ADDED"

DEFAULT_SEVERITY = "medium"
MAX_CORRELATION_REASONS = 40
MAX_CORRELATION_SOURCES = 200
CANDIDATE_LIMIT = 100

# open -> triage -> investigating -> resolved -> closed, plus one reopen edge.
LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "open": frozenset({"triage"}),
    "triage": frozenset({"investigating"}),
    "investigating": frozenset({"resolved"}),
    "resolved": frozenset({"closed", "investigating"}),
    "closed": frozenset(),
}


def can_transition(current: str, target: str) -> bool:
    """True when the requested lifecycle edge is legal from the current state."""
    return target in LEGAL_TRANSITIONS.get((current or "").strip().lower(), frozenset())


def validate_transition(current: str, target: str) -> None:
    if not can_transition(current, target):
        raise IncidentTransitionRejected(
            f"Illegal incident transition: {current!r} -> {target!r}")


def _stronger_confidence(left: str, right: str) -> str:
    """The higher of two confidence labels, using the shared ranking."""
    return left if CONFIDENCE_RANK.get(left, 0) >= CONFIDENCE_RANK.get(right, 0) else right


def _dedupe_in_order(values, limit: int) -> list:
    """Stable de-duplication with a hard bound (summary lists must stay bounded)."""
    seen = set()
    out = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
        if len(out) >= limit:
            break
    return out


def _is_duplicate_evidence(exc: IntegrityError) -> bool:
    """True only for the expected duplicate-evidence unique violation.

    asyncpg exposes ``sqlstate`` directly; the constraint name is also checked so
    an unrelated unique violation on the same table cannot be misread as an
    idempotent duplicate.
    """
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None)
    text_ = str(orig or exc)
    return sqlstate == "23505" and "uq_incident_evidence_source" in text_



class IncidentError(Exception):
    """Base error for incident domain operations."""


class IncidentValidationError(IncidentError):
    """The supplied incident data or transition target is not valid."""


class IncidentConflict(IncidentError):
    """A concurrent or conflicting lifecycle/identity operation was rejected."""


class IncidentNotFound(IncidentError):
    """The incident does not exist."""


class IncidentPermissionError(IncidentError):
    """The actor lacks the capability required for this operation."""


class IncidentTransitionRejected(IncidentValidationError):
    """The requested lifecycle edge is not legal from the current state."""


@dataclass(frozen=True)
class EvidenceInput:  # noqa: F811 - reconstructed definition
    """One piece of source evidence, identified durably.

    ``digest`` defaults to a hash of the source identity and observation time;
    callers may supply an explicit digest. ``signature`` is what correlation
    compares, so the original source identity is preserved.
    """
    source_type: str
    source_id: str
    observed_at: datetime
    source_event_key: str | None = None
    evidence_digest: str | None = None

    @property
    def signature(self) -> str:
        return normalize_signature(self.source_type, self.source_event_key or self.source_id)

    def correlation_input(self, asset_id: uuid.UUID | None) -> CorrelationInput:
        """Identity handed to the correlation classifier (contract from correlation.py)."""
        return CorrelationInput(
            asset_id=asset_id,
            source_type=self.source_type,
            source_id=self.source_id,
            signature=self.signature,
            observed_at=self.observed_at,
        )

    @property
    def digest(self) -> str:
        if self.evidence_digest:
            return self.evidence_digest
        material = f"{self.source_type}:{self.source_id}:{normalize_observed_at(self.observed_at).isoformat()}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


class IncidentService:
    """Incident lifecycle, deterministic correlation and evidence binding."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
    # ------------------------------------------------------------------
    # Test seam: a single hook after ORM rows are flushed but before commit.
    # Production leaves it as a no-op; tests use it to prove rollback safety.
    # ------------------------------------------------------------------
    def _post_persist(self, incident: Incident) -> None:
        return None

    # ------------------------------------------------------------------
    # Evidence normalisation
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_evidence(evidence: list[EvidenceInput]) -> list[EvidenceInput]:
        if not evidence:
            raise IncidentValidationError("At least one evidence item is required.")
        normalized: dict[tuple[str, str], EvidenceInput] = {}
        for item in evidence:
            source_type = (item.source_type or "").strip().lower()
            source_id = (item.source_id or "").strip()
            if not source_type or not source_id:
                raise IncidentValidationError("Evidence source_type and source_id are required.")
            if len(source_id) > 64:
                raise IncidentValidationError("Evidence source_id must be at most 64 characters.")
            observed = normalize_observed_at(item.observed_at)
            key = (source_type, source_id)
            candidate = EvidenceInput(
                source_type=source_type,
                source_id=source_id,
                observed_at=observed,
                source_event_key=item.source_event_key,
                evidence_digest=item.evidence_digest,
            )
            # Deterministic conflict resolution: earliest observation wins.
            if key not in normalized or observed < normalized[key].observed_at:
                normalized[key] = candidate
        return sorted(
            normalized.values(),
            key=lambda e: (e.observed_at, e.source_type, e.source_id),
        )

    @staticmethod
    def _validate_severity(severity: str | None) -> str:
        value = (severity or DEFAULT_SEVERITY).strip().lower()
        if value not in INCIDENT_SEVERITIES:
            raise IncidentValidationError(f"Unsupported incident severity: {severity}")
        return value

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------
    async def get_incident(self, incident_id: uuid.UUID) -> Incident:
        incident = await self.db.get(Incident, incident_id)
        if incident is None:
            raise IncidentNotFound(f"Incident {incident_id} does not exist.")
        return incident

    @staticmethod
    def _is_terminal(incident: Incident) -> bool:
        return incident.status in {"resolved", "closed"}

    async def _by_dedupe_key(self, dedupe_key: str) -> Incident | None:
        stmt = select(Incident).where(Incident.dedupe_key == dedupe_key)
        return (await self.db.execute(stmt)).scalars().first()

    async def _evidence_lookup(self, source_type: str, source_id: str) -> IncidentEvidence | None:
        stmt = select(IncidentEvidence).where(
            IncidentEvidence.source_type == source_type,
            IncidentEvidence.source_id == source_id,
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def _candidate_incidents(
        self, primary: EvidenceInput, asset_id: uuid.UUID | None, window_seconds: int
    ) -> list[Incident]:
        expanded = timedelta(seconds=window_seconds * 2)
        observed = normalize_observed_at(primary.observed_at)
        conditions = [
            Incident.last_seen >= observed - expanded,
            Incident.first_seen <= observed + expanded,
            # A recurrence of a resolved/closed incident must start a new
            # incident; merging it back would hide the recurrence.
            Incident.status.notin_(("resolved", "closed")),
        ]
        # Different concrete asset ids must never be considered for merging.
        if asset_id is None:
            conditions.append(Incident.asset_id.is_(None))
        else:
            conditions.append(
                or_(Incident.asset_id.is_(None), Incident.asset_id == asset_id)
            )
        stmt = (
            select(Incident)
            .where(*conditions)
            .order_by(Incident.last_seen.desc())
            .limit(CANDIDATE_LIMIT)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    @staticmethod
    def _incident_correlation_input(incident: Incident) -> CorrelationInput | None:
        summary = incident.summary if isinstance(incident.summary, dict) else {}
        correlation = summary.get("correlation") if isinstance(summary, dict) else None
        signature = correlation.get("signature") if isinstance(correlation, dict) else None
        if not isinstance(signature, str) or not signature:
            return None
        return CorrelationInput(
            asset_id=incident.asset_id,
            source_type="incident",
            source_id=str(incident.incident_id),
            signature=signature,
            observed_at=normalize_observed_at(incident.last_seen),
        )

    async def _best_candidate(
        self, primary: EvidenceInput, asset_id: uuid.UUID | None, window_seconds: int
    ) -> tuple[Incident, CorrelationAssessment] | None:
        best: tuple[Incident, CorrelationAssessment] | None = None
        for incident in await self._candidate_incidents(primary, asset_id, window_seconds):
            existing = self._incident_correlation_input(incident)
            if existing is None:
                continue
            assessment = classify(
                primary.correlation_input(asset_id),
                existing,
                window_seconds=window_seconds,
            )
            if not assessment.mergeable:
                continue
            if best is None or CONFIDENCE_RANK[assessment.confidence] > CONFIDENCE_RANK[best[1].confidence]:
                best = (incident, assessment)
        return best

    # ------------------------------------------------------------------
    # Evidence attachment (inside the caller's transaction)
    # ------------------------------------------------------------------
    async def _attach_items(
        self, incident: Incident, items: list[EvidenceInput], actor: str
    ) -> list[IncidentEvidence]:
        added: list[IncidentEvidence] = []
        for item in items:
            if await self._evidence_lookup(item.source_type, item.source_id) is not None:
                continue
            row = IncidentEvidence(
                incident_id=incident.incident_id,
                source_type=item.source_type,
                source_id=item.source_id,
                source_event_key=item.source_event_key,
                evidence_digest=item.digest,
                observed_at=normalize_observed_at(item.observed_at),
                added_by=actor,
            )
            self.db.add(row)
            added.append(row)
        return added

    @staticmethod
    def _extend_seen_window(incident: Incident, items: list[EvidenceInput]) -> None:
        first = min(normalize_observed_at(i.observed_at) for i in items)
        last = max(normalize_observed_at(i.observed_at) for i in items)
        if incident.first_seen is None or first < incident.first_seen:
            incident.first_seen = first
        if incident.last_seen is None or last > incident.last_seen:
            incident.last_seen = last

    @staticmethod
    def _merge_summary(incident: Incident, assessment: CorrelationAssessment, signature: str) -> None:
        summary = dict(incident.summary or {})
        correlation = dict(summary.get("correlation") or {})
        reasons = list(correlation.get("reasons") or []) + list(assessment.reasons)
        sources = list(correlation.get("sources") or []) + list(assessment.sources)
        merged_signatures = list(correlation.get("merged_signatures") or [])
        if signature != correlation.get("signature") and signature not in merged_signatures:
            merged_signatures.append(signature)
        correlation.update(
            {
                "confidence": _stronger_confidence(
                    str(correlation.get("confidence") or CONFIDENCE_NONE),
                    assessment.confidence,
                ),
                "reasons": _dedupe_in_order(reasons, MAX_CORRELATION_REASONS),
                "sources": _dedupe_in_order(sources, MAX_CORRELATION_SOURCES),
                "window_seconds": assessment.window_seconds,
                "asset_state": "resolved" if incident.asset_id is not None else "unresolved",
            }
        )
        if merged_signatures:
            correlation["merged_signatures"] = merged_signatures[:MAX_CORRELATION_SOURCES]
        summary["correlation"] = correlation
        incident.summary = summary

    def _audit(
        self,
        *,
        incident: Incident,
        action_verb: str,
        actor: str,
        previous_state: str | None,
        new_state: str | None,
        confidence: str | None,
        evidence_digest: str | None,
        reviewer: str | None = None,
        extra: dict | None = None,
    ) -> None:
        """Queues an audit row in the same transaction as the mutation."""
        payload: dict = {
            "incident_id": str(incident.incident_id),
            "previous_state": previous_state,
            "new_state": new_state,
            "actor": actor,
            "confidence": confidence,
            "evidence_digest": evidence_digest,
        }
        if reviewer is not None:
            payload["reviewer"] = reviewer
        if extra:
            payload.update(extra)
        self.db.add(
            AuditLog(
                actor_id=None,
                asset_id=incident.asset_id,
                action_verb=action_verb,
                immutable_payload=payload,
            )
        )

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    async def create_from_evidence(
        self,
        evidence: list[EvidenceInput],
        *,
        actor: str,
        asset_id: uuid.UUID | None = None,
        title: str | None = None,
        severity: str | None = None,
        window_seconds: int | None = None,
    ) -> tuple[Incident, bool]:
        """Creates or reuses an incident. Returns (incident, created)."""
        items = self._normalize_evidence(evidence)
        if not actor:
            raise IncidentValidationError("An authenticated actor is required.")
        window = int(window_seconds or DEFAULT_WINDOW_SECONDS)
        if window <= 0:
            raise IncidentValidationError("window_seconds must be positive.")
        normalized_severity = self._validate_severity(severity)

        if asset_id is not None:
            asset_exists = await self.db.scalar(
                select(InfrastructureAsset.asset_id).where(
                    InfrastructureAsset.asset_id == asset_id
                )
            )
            if asset_exists is None:
                raise IncidentValidationError(f"Asset {asset_id} is not registered.")

        primary = items[0]
        signature = primary.signature
        dedupe_key = build_dedupe_key(asset_id, signature, primary.observed_at, window)

        existing = await self._by_dedupe_key(dedupe_key)
        if existing is not None and self._is_terminal(existing):
            # Same signature/window after closure is a recurrence, not the same
            # incident. Use a deterministic per-bucket recurrence key so retries
            # are still idempotent without reopening or merging into the closed row.
            bucket = int(normalize_observed_at(primary.observed_at).timestamp()) // window
            dedupe_key = f"{dedupe_key}:r{bucket}"
            existing = await self._by_dedupe_key(dedupe_key)
        if existing is not None:
            return await self._reuse_incident(
                existing, items, actor=actor, window_seconds=window, asset_id=asset_id
            )

        # Idempotency across window buckets: the same source row always wins.
        for item in items:
            bound = await self._evidence_lookup(item.source_type, item.source_id)
            if bound is not None:
                incident = await self.get_incident(bound.incident_id)
                if self._is_terminal(incident):
                    # The exact same source event is already recorded; that is
                    # idempotency, not a new occurrence.
                    return incident, False
                return await self._reuse_incident(
                    incident, items, actor=actor, window_seconds=window,
                    asset_id=asset_id or incident.asset_id,
                )

        best = await self._best_candidate(primary, asset_id, window)
        if best is not None:
            incident, _assessment = best
            return await self._reuse_incident(
                incident, items, actor=actor, window_seconds=window, asset_id=asset_id
            )

        # Intra-request correlation for a brand-new incident (single source = weak).
        if len(items) == 1:
            correlation = _single_item_assessment(primary, asset_id, window)
        else:
            correlation = _multi_item_assessment(primary, items, asset_id, window)

        incident = Incident(
            title=(title or f"{primary.source_type} incident: {primary.source_id}")[:255],
            status="open",
            severity=normalized_severity,
            confidence=correlation.confidence,
            asset_id=asset_id,
            first_seen=min(normalize_observed_at(i.observed_at) for i in items),
            last_seen=max(normalize_observed_at(i.observed_at) for i in items),
            dedupe_key=dedupe_key,
            root_cause_state="unknown",
            owner=None,
            summary={"correlation": correlation.as_summary(signature, asset_id)},
        )

        try:
            async with self.db.begin_nested():
                self.db.add(incident)
                await self.db.flush()
                await self._attach_items(incident, items, actor)
                self._audit(
                    incident=incident,
                    action_verb=ACTION_INCIDENT_CREATED,
                    actor=actor,
                    previous_state=None,
                    new_state="open",
                    confidence=correlation.confidence,
                    evidence_digest=primary.digest,
                )
                await self.db.flush()
                self._post_persist(incident)
            await self.db.commit()
            logger.info(
                "Incident created incident_id=%s confidence=%s sources=%s",
                incident.incident_id, correlation.confidence, len(items),
            )
            return incident, True
        except IntegrityError:
            # A concurrent writer won the dedupe/evidence race.
            await self.db.rollback()
            recovered = await self._recover_after_conflict(dedupe_key, items, actor, window)
            if recovered is None:
                raise IncidentConflict(
                    "Concurrent incident creation could not be resolved deterministically."
                ) from None
            return recovered
        except Exception:
            await self.db.rollback()
            raise

    async def _recover_after_conflict(
        self,
        dedupe_key: str,
        items: list[EvidenceInput],
        actor: str,
        window_seconds: int,
    ) -> tuple[Incident, bool] | None:
        incident = await self._by_dedupe_key(dedupe_key)
        if incident is None:
            for item in items:
                bound = await self._evidence_lookup(item.source_type, item.source_id)
                if bound is not None:
                    incident = await self.get_incident(bound.incident_id)
                    break
        if incident is None:
            return None
        if self._is_terminal(incident):
            # Same source event already bound to a closed incident: idempotent.
            return incident, False
        try:
            return await self._reuse_incident(
                incident, items, actor=actor, window_seconds=window_seconds,
                asset_id=incident.asset_id,
            )
        except IntegrityError:
            await self.db.rollback()
            incident = await self._by_dedupe_key(dedupe_key)
            if incident is None:
                return None
            return incident, False

    async def _reuse_incident(
        self,
        incident: Incident,
        items: list[EvidenceInput],
        *,
        actor: str,
        window_seconds: int,
        asset_id: uuid.UUID | None,
    ) -> tuple[Incident, bool]:
        """Attaches any unseen evidence to an already-resolved incident."""
        if self._is_terminal(incident):
            raise IncidentConflict(
                "Cannot merge evidence into a resolved or closed incident; "
                "create a recurrence instead."
            )
        primary = items[0]
        existing_input = self._incident_correlation_input(incident)
        assessment = (
            classify(
                primary.correlation_input(asset_id),
                existing_input,
                window_seconds=window_seconds,
            )
            if existing_input is not None
            else _single_item_assessment(primary, asset_id, window_seconds)
        )
        try:
            async with self.db.begin_nested():
                added = await self._attach_items(incident, items, actor)
                if added:
                    self._extend_seen_window(incident, items)
                    # Explicit evidence may resolve an unresolved incident asset,
                    # but an existing concrete asset is never replaced or guessed.
                    if incident.asset_id is None and asset_id is not None:
                        incident.asset_id = asset_id
                    self._merge_summary(incident, assessment, primary.signature)
                    incident.confidence = _stronger_confidence(
                        incident.confidence, assessment.confidence
                    )
                    self._audit(
                        incident=incident,
                        action_verb=ACTION_INCIDENT_EVIDENCE_ADDED,
                        actor=actor,
                        previous_state=incident.status,
                        new_state=incident.status,
                        confidence=assessment.confidence,
                        evidence_digest=primary.digest,
                    )
                    await self.db.flush()
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            incident = await self.get_incident(incident.incident_id)
            return incident, False
        return incident, False

    # ------------------------------------------------------------------
    # Explicit evidence attachment
    # ------------------------------------------------------------------
    async def attach_evidence(
        self,
        incident_id: uuid.UUID,
        evidence: list[EvidenceInput],
        *,
        actor: str,
        window_seconds: int | None = None,
    ) -> tuple[Incident, int]:
        """Idempotently attaches evidence references. Returns (incident, added_count)."""
        items = self._normalize_evidence(evidence)
        if not actor:
            raise IncidentValidationError("An authenticated actor is required.")
        window = int(window_seconds or DEFAULT_WINDOW_SECONDS)

        incident = await self.get_incident(incident_id)
        if self._is_terminal(incident):
            raise IncidentConflict(
                "Cannot attach evidence to a resolved or closed incident; "
                "create a recurrence instead."
            )
        primary = items[0]
        existing_input = self._incident_correlation_input(incident)
        assessment = (
            classify(
                primary.correlation_input(incident.asset_id),
                existing_input,
                window_seconds=window,
            )
            if existing_input is not None
            else _single_item_assessment(primary, incident.asset_id, window)
        )
        try:
            async with self.db.begin_nested():
                added = await self._attach_items(incident, items, actor)
                if added:
                    self._extend_seen_window(incident, items)
                    self._merge_summary(incident, assessment, primary.signature)
                    incident.confidence = _stronger_confidence(
                        incident.confidence, assessment.confidence
                    )
                    self._audit(
                        incident=incident,
                        action_verb=ACTION_INCIDENT_EVIDENCE_ADDED,
                        actor=actor,
                        previous_state=incident.status,
                        new_state=incident.status,
                        confidence=assessment.confidence,
                        evidence_digest=primary.digest,
                    )
                    await self.db.flush()
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            # Idempotency expects exactly one failure: the unique
            # (source_type, source_id) guard when a concurrent writer attached
            # the same evidence first. Any other integrity failure is a real
            # persistence defect and must not be reported as success.
            if not _is_duplicate_evidence(exc):
                raise
            incident = await self.get_incident(incident_id)
            return incident, 0
        return incident, len(added)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def change_status(
        self,
        incident_id: uuid.UUID,
        target_status: str,
        *,
        actor: str,
        reviewer_identity: str | None = None,
        verification: VerificationRequest | None = None,
        verifier: str | None = None,
    ) -> Incident:
        """Applies one legal lifecycle edge inside a single locked transaction.

        Transaction ownership: this method owns the transaction it starts and
        commits exactly once. Pass a dedicated session; do not share it.

        Resolving requires ``verification`` (a persisted evidence reference) and
        an authorised ``verifier``. The evidence is revalidated here, under
        ``SELECT ... FOR UPDATE`` on the incident row, in the same transaction
        as the status change, so a controller cannot bypass the invariant.
        """
        if not actor:
            raise IncidentValidationError("An authenticated actor is required.")
        target = (target_status or "").strip().lower()
        try:
            incident = (
                await self.db.execute(
                    select(Incident)
                    .where(Incident.incident_id == incident_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalars().first()
            if incident is None:
                raise IncidentNotFound(f"Incident {incident_id} does not exist.")
            previous = incident.status
            validate_transition(previous, target)

            if target == "closed" and not reviewer_identity:
                raise IncidentPermissionError(
                    "Closing an incident requires the Knowledge Reviewer capability."
                )

            extra: dict | None = None
            if target == "resolved":
                if verification is None:
                    raise IncidentValidationError(
                        "resolution_blocked:missing_verification: resolving an incident "
                        "requires verification.evidence_id"
                    )
                decision = await evaluate_verification(
                    self.db, incident, verification, verifier
                )
                record = build_record(incident, decision)
                self.db.add(record)
                await self.db.flush()
                extra = {
                    "verification_id": str(record.verification_id),
                    "remediation_cycle": record.remediation_cycle,
                    "verifier": record.verifier_id,
                    "verified_evidence_id": str(record.evidence_id),
                }

            if target == "investigating" and previous == "resolved":
                # A genuine reopen starts a new remediation cycle exactly once in
                # this transaction. Existing verification rows stay historical
                # and no longer match the incident's cycle.
                incident.remediation_cycle = int(incident.remediation_cycle or 0) + 1
                incident.remediation_started_at = datetime.now(UTC)
                extra = {**(extra or {}), "remediation_cycle": incident.remediation_cycle}

            incident.status = target
            if target == "closed":
                # Record the accountable reviewer on the incident and in the audit payload.
                incident.owner = reviewer_identity

            self._audit(
                incident=incident,
                action_verb=ACTION_INCIDENT_STATUS_CHANGED,
                actor=actor,
                previous_state=previous,
                new_state=target,
                confidence=incident.confidence,
                evidence_digest=None,
                reviewer=reviewer_identity,
                extra=extra,
            )
            await self.db.flush()
            await self.db.commit()
        except VerificationRejected as exc:
            await self.db.rollback()
            if exc.code.startswith("verifier_"):
                raise IncidentPermissionError(str(exc)) from exc
            raise IncidentValidationError(
                f"resolution_blocked:{exc.code}: {exc.detail}") from exc
        except Exception:
            await self.db.rollback()
            raise
        logger.info(
            "Incident status changed incident_id=%s %s -> %s actor=%s",
            incident.incident_id, previous, target, actor,
        )
        return incident

    async def list_verifications(
        self, incident_id: uuid.UUID, *, limit: int = 100
    ) -> list[IncidentVerification]:
        """Returns the append-only verification history, newest last."""
        rows = (
            await self.db.execute(
                select(IncidentVerification)
                .where(IncidentVerification.incident_id == incident_id)
                .order_by(IncidentVerification.verified_at)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    async def list_incidents(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        asset_id: uuid.UUID | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[Incident], int]:
        conditions = []
        if status:
            conditions.append(Incident.status == status.strip().lower())
        if severity:
            conditions.append(Incident.severity == severity.strip().lower())
        if asset_id is not None:
            conditions.append(Incident.asset_id == asset_id)

        base = select(Incident).where(*conditions)
        total = (
            await self.db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        page = max(int(page), 1)
        limit = max(min(int(limit), 200), 1)
        stmt = (
            base.order_by(Incident.last_seen.desc(), Incident.incident_id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        return rows, int(total)

    async def list_evidence(
        self,
        incident_id: uuid.UUID,
        *,
        page: int = 1,
        limit: int = 100,
    ) -> tuple[list[IncidentEvidence], int]:
        await self.get_incident(incident_id)
        base = select(IncidentEvidence).where(IncidentEvidence.incident_id == incident_id)
        total = (
            await self.db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        page = max(int(page), 1)
        limit = max(min(int(limit), 500), 1)
        stmt = (
            base.order_by(IncidentEvidence.observed_at.asc(), IncidentEvidence.evidence_id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        return rows, int(total)


def _single_item_assessment(
    item: EvidenceInput, asset_id: uuid.UUID | None, window_seconds: int
) -> CorrelationAssessment:
    """A lone evidence reference is explicitly weak, not causal."""
    normalized = normalize_observed_at(item.observed_at)
    return CorrelationAssessment(
        confidence=CONFIDENCE_WEAK,
        reasons=("single_source_evidence",),
        sources=(item.correlation_input(asset_id).source_label,),
        window_seconds=int(window_seconds),
        window_bucket=window_bucket(normalized, window_seconds),
        dedupe_key=build_dedupe_key(asset_id, item.signature, normalized, window_seconds),
        asset_key=str(asset_id) if asset_id is not None else "unresolved",
    )


def _multi_item_assessment(
    primary: EvidenceInput,
    items: list[EvidenceInput],
    asset_id: uuid.UUID | None,
    window_seconds: int,
) -> CorrelationAssessment:
    """Best deterministic pairwise correlation among a multi-evidence request."""
    best: CorrelationAssessment | None = None
    for other in items[1:]:
        assessment = classify(
            primary.correlation_input(asset_id),
            other.correlation_input(asset_id),
            window_seconds=window_seconds,
        )
        if best is None or CONFIDENCE_RANK[assessment.confidence] > CONFIDENCE_RANK[best.confidence]:
            best = assessment
    if best is not None and best.confidence != CONFIDENCE_NONE:
        return best
    fallback = _single_item_assessment(primary, asset_id, window_seconds)
    return replace(
        fallback,
        reasons=("multi_source_no_positive_correlation",),
        sources=tuple(i.correlation_input(asset_id).source_label for i in items[:MAX_CORRELATION_SOURCES]),
    )
