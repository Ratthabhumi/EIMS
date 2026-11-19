"""Trusted, persistence-backed verification for incident resolution.

Why this module exists
----------------------
Incident Core v1 (2026-11-16) deliberately had no remediation or closure
automation: an incident could move to ``resolved`` on a human command alone.
That is a product-correctness gap: a caller asserting "it is fixed" is not
evidence. This module is the smallest coherent extension that closes it.

Contract (new policy, documented in
``docs/INCIDENT_VERIFICATION_AND_RESOLUTION_POLICY.md``)
--------------------------------------------------------
* Resolution requires a persisted ``incident_verification`` row.
* A row is written only after the server revalidates, inside the caller's
  transaction and under a row lock on the incident:
    1. the verifier is an authenticated principal with review capability;
    2. the evidence row exists and belongs to *this* incident;
    3. the evidence source type can actually evidence a remediation outcome;
    4. the stored digest equals a server-side recomputation (no caller digest);
    5. the evidence was attached inside the current remediation cycle;
    6. the referenced source record exists in trusted persistence;
    7. the referenced record is not attributed to a different asset.
* The caller never supplies ``outcome`` or ``verifier_id``.

Honest limits
-------------
Evidence is reference-only: EIMS stores ``(source_type, source_id, digest)``
and never copies source payloads. The digest therefore proves *reference*
integrity (the row was not edited after attachment), not the bytes of an
external artifact. Only source types whose referenced record exists in EIMS
persistence are accepted; everything else fails closed.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.incident.correlation import normalize_observed_at
from backend.domain.incident.models import (
    Incident,
    IncidentEvidence,
    IncidentVerification,
)

OUTCOME_PASSED = "passed"
OUTCOME_FAILED = "failed"

# A winlog/telemetry/audit row is a metadata reference without a trusted
# outcome signal; accepting it would let a caller "prove" a fix with an event
# that only proves the problem occurred. Such evidence fails closed.
VERIFICATION_SOURCE_TYPES = frozenset({"analysis"})

# analysis_history.id is an integer; only its canonical decimal form is trusted.
_SOURCE_ID_RE = re.compile(r"[0-9]+")


class VerificationRejected(Exception):
    """The supplied verification cannot authorise resolution."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class VerificationRequest:
    """The only caller-supplied verification input: a persisted evidence ref."""
    evidence_id: uuid.UUID


@dataclass(frozen=True)
class VerificationDecision:
    """Server-derived verdict; ``outcome`` is never read from the request."""
    outcome: str
    evidence_id: uuid.UUID
    evidence_digest: str
    remediation_cycle: int
    verifier: str
    reason: str


def recompute_evidence_digest(row: IncidentEvidence) -> str:
    """Recompute the reference digest exactly as attachment computed it."""
    material = (
        f"{row.source_type}:{row.source_id}:"
        f"{normalize_observed_at(row.observed_at).isoformat()}"
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


async def _authorize_verifier(db: AsyncSession, verifier: str | None) -> str:
    """Resolve capability from trusted persistence, never from the request."""
    if not verifier or not verifier.strip():
        raise VerificationRejected(
            "verifier_required", "an authenticated verifier identity is required")
    username = verifier.strip()
    if username in {"guest", "demo"}:
        raise VerificationRejected(
            "verifier_unauthorized", "anonymous identities cannot verify remediation")
    # Imported here so the incident domain does not import the analyzer package
    # at module import time.
    from backend.domain.analyzer.models.user import User

    user = (
        await db.execute(select(User).where(User.username == username))
    ).scalars().first()
    if user is None:
        raise VerificationRejected(
            "verifier_unauthorized", f"unknown verifier principal {username!r}")
    if user.role != "admin" and not bool(user.knowledge_reviewer):
        raise VerificationRejected(
            "verifier_unauthorized", "verifier lacks the review capability")
    return username


async def _trusted_source_exists(
    db: AsyncSession, incident: Incident, row: IncidentEvidence
) -> None:
    """Prove the referenced source record exists and is not foreign."""
    if row.source_type == "analysis":
        from backend.domain.analyzer.models.history import AnalysisHistory

        raw_source_id = str(row.source_id)
        if not _SOURCE_ID_RE.fullmatch(raw_source_id):
            raise VerificationRejected(
                "evidence_source_malformed",
                "analysis evidence source_id must be a canonical integer analysis_history.id",
            )
        source_pk = int(raw_source_id)
        if str(source_pk) != raw_source_id or source_pk < 1 or source_pk > 2**31 - 1:
            raise VerificationRejected(
                "evidence_source_malformed",
                "analysis evidence source_id must be a canonical 32-bit integer id",
            )
        source = (
            await db.execute(select(AnalysisHistory).where(AnalysisHistory.id == source_pk))
        ).scalars().first()
        if source is None:
            raise VerificationRejected(
                "evidence_source_unknown",
                "referenced analysis record does not exist in trusted persistence",
            )
        if incident.asset_id is not None and source.asset_id != incident.asset_id:
            raise VerificationRejected(
                "evidence_asset_mismatch",
                "referenced observation is not attributed to the incident's asset",
            )
        return
    raise VerificationRejected(
        "evidence_type_not_verifiable",
        f"source_type {row.source_type!r} cannot prove a remediation outcome",
    )


async def evaluate(
    db: AsyncSession,
    incident: Incident,
    request: VerificationRequest,
    verifier: str | None,
) -> VerificationDecision:
    """Authoritative validation. Call only under the incident row lock.

    Must run inside the same transaction as the status transition so a stale
    read cannot authorise a resolution (TOCTOU).
    """
    verifier_name = await _authorize_verifier(db, verifier)

    evidence_id = request.evidence_id
    if not isinstance(evidence_id, uuid.UUID):
        try:
            evidence_id = uuid.UUID(str(evidence_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise VerificationRejected(
                "evidence_malformed",
                "verification.evidence_id must be a UUID",
            ) from exc

    row = (
        await db.execute(
            select(IncidentEvidence).where(IncidentEvidence.evidence_id == evidence_id)
        )
    ).scalars().first()
    if row is None:
        raise VerificationRejected(
            "evidence_unknown", f"evidence {evidence_id} does not exist")
    if row.incident_id != incident.incident_id:
        raise VerificationRejected(
            "evidence_foreign", "evidence belongs to another incident")
    if row.source_type not in VERIFICATION_SOURCE_TYPES:
        raise VerificationRejected(
            "evidence_type_not_verifiable",
            f"source_type {row.source_type!r} cannot prove a remediation outcome",
        )
    if row.added_by and row.added_by == verifier_name:
        raise VerificationRejected(
            "verifier_conflict",
            "the identity that attached the evidence cannot also verify it",
        )

    recomputed = recompute_evidence_digest(row)
    if recomputed != row.evidence_digest:
        raise VerificationRejected(
            "evidence_digest_mismatch",
            "stored evidence digest does not match its trusted recomputation",
        )

    started = getattr(incident, "remediation_started_at", None)
    if started is not None and (
        normalize_observed_at(row.created_at) < normalize_observed_at(started)
    ):
        raise VerificationRejected(
            "evidence_stale",
            "evidence predates the current remediation cycle",
        )

    await _trusted_source_exists(db, incident, row)

    return VerificationDecision(
        outcome=OUTCOME_PASSED,
        evidence_id=row.evidence_id,
        evidence_digest=recomputed,
        remediation_cycle=int(incident.remediation_cycle or 0),
        verifier=verifier_name,
        reason="evidence revalidated against trusted persistence",
    )


def build_record(
    incident: Incident, decision: VerificationDecision
) -> IncidentVerification:
    """Build the append-only verification row for the current cycle."""
    return IncidentVerification(
        incident_id=incident.incident_id,
        remediation_cycle=decision.remediation_cycle,
        evidence_id=decision.evidence_id,
        evidence_digest=decision.evidence_digest,
        outcome=decision.outcome,
        verifier_id=decision.verifier,
        verified_at=datetime.now(UTC),
    )
