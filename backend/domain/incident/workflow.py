"""Diagnosis, remediation and knowledge-proposal records for the existing Incident Core.

Boundaries (see docs/knowledge/ARCHITECTURE_ALIGNMENT_20261119.md):
* The canonical Diagnostic Knowledge Catalog stays the only reusable-knowledge store.
  Records here are case-specific. A diagnosis/remediation keeps a *snapshot* of the
  catalog record it referenced (classification, review state, content hash) so the
  incident stays interpretable if the catalog later changes.
* EIMS has no application login, so every record stores an explicit
  ``actor_assurance``. ``unattributed`` and ``shared-token`` actors may record
  hypotheses, reject/supersede hypotheses, propose and record remediation, and
  submit knowledge proposals for review. They can NEVER confirm a root cause, and
  nothing in this module verifies, resolves or closes an incident or approves knowledge.
* Authorisation for confirmation is enforced here (assurance AND reviewer capability),
  not only in the HTTP controller.
* Correlation confidence, hypothesis confidence and knowledge trust are separate facts.
* Writes and the append-only audit event share one transaction.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.analyzer.models.user import User
from backend.domain.incident.models import Incident, IncidentEvidence, IncidentVerification
from backend.domain.incident.service import (
    IncidentConflict,
    IncidentNotFound,
    IncidentPermissionError,
    IncidentTransitionRejected,
    IncidentValidationError,
)
from backend.domain.incident.workflow_models import (
    EXECUTION_OUTCOMES,
    STATED_CONFIDENCES,
    IncidentDiagnosis,
    IncidentKnowledgeProposal,
    IncidentNote,
    IncidentRemediation,
    IncidentWorkflowEvent,
)

UNATTRIBUTED = "unattributed"
SHARED_TOKEN = "shared-token"
VERIFIED = "verified-identity"
_TERMINAL = {"resolved", "closed"}
MAX_PAGE = 200


@dataclass(frozen=True)
class Actor:
    identifier: str
    assurance: str


def _digest(material: dict[str, Any]) -> str:
    blob = json.dumps(material, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _text(value: Any, name: str, *, required: bool, limit: int) -> str:
    text = (value or "").strip() if isinstance(value, str) or value is None else ""
    if required and not text:
        raise IncidentValidationError(f"{name} is required")
    if len(text) > limit:
        raise IncidentValidationError(f"{name} exceeds {limit} characters")
    return text


def _page(limit: int, offset: int) -> tuple[int, int]:
    return max(1, min(int(limit), MAX_PAGE)), max(0, int(offset))


class IncidentWorkflow:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ---------------------------------------------------------------- helpers
    async def _incident(self, incident_id: uuid.UUID) -> Incident:
        incident = (await self.db.execute(
            select(Incident).where(Incident.incident_id == incident_id).with_for_update()
        )).scalars().first()
        if incident is None:
            raise IncidentNotFound(f"incident {incident_id} not found")
        return incident

    @staticmethod
    def _require_open(incident: Incident) -> None:
        if incident.status in _TERMINAL:
            raise IncidentTransitionRejected(
                "Cannot add diagnosis or remediation records to a resolved or closed incident; "
                "reopen it into investigating first.")

    async def _require_reviewer(self, actor: Actor) -> None:
        """Domain-level authorisation: verified identity AND the reviewer capability."""
        if actor.assurance != VERIFIED:
            raise IncidentPermissionError(
                f"this action requires a verified-identity reviewer; this request is {actor.assurance}")
        user = (await self.db.execute(
            select(User).where(User.username == actor.identifier))).scalars().first()
        if user is None or not (user.role == "admin" or bool(user.knowledge_reviewer)):
            raise IncidentPermissionError("knowledge reviewer capability required")

    async def _evidence_ids(self, incident_id: uuid.UUID, ids: Sequence[uuid.UUID], name: str) -> list[str]:
        unique = list(dict.fromkeys(ids))
        if not unique:
            return []
        found = set((await self.db.execute(
            select(IncidentEvidence.evidence_id).where(
                IncidentEvidence.incident_id == incident_id,
                IncidentEvidence.evidence_id.in_(unique),
            )
        )).scalars().all())
        missing = [str(i) for i in unique if i not in found]
        if missing:
            raise IncidentValidationError(f"{name} reference evidence that does not belong to this incident")
        return [str(i) for i in unique]

    def _event(self, *, incident_id, record_type, record_id, action, actor: Actor, digest, detail=None) -> None:
        self.db.add(IncidentWorkflowEvent(
            incident_id=incident_id, record_type=record_type, record_id=record_id, action=action,
            actor=actor.identifier, actor_assurance=actor.assurance, record_digest=digest,
            detail=detail or {},
        ))

    async def _knowledge_snapshot(self, catalog_id: str | None, detected_version: str | None) -> dict | None:
        """Server-side snapshot of the canonical record's trust at this moment."""
        if not catalog_id:
            return None
        from backend.domain.knowledge.retrieval import retrieve
        from backend.domain.knowledge.service import _catalog, canonical_hash

        entry = _catalog().get(catalog_id)
        if entry is None:
            raise IncidentValidationError("catalog_id does not reference a known knowledge record")
        match = await retrieve(self.db, entry, detected_version=detected_version)
        return {
            "catalog_id": catalog_id,
            "classification": match["classification"],
            "lifecycle_status": match["lifecycleStatus"],
            "stale": match["stale"],
            "overlay_available": match["overlayAvailable"],
            "version_scope": match["versionScope"],
            "version_compatible": match["versionCompatible"],
            "content_hash": canonical_hash(entry),
            # Whether the canonical record itself carries remediation guidance. Today the
            # catalog schema has none, so this is False and any remediation is incident-specific.
            "canonical_remediation_available": bool(entry.get("remediation_guidance")),
            "captured_at": datetime.now(UTC).isoformat(),
        }

    async def _recompute_root_cause(self, incident: Incident) -> None:
        """root_cause_state reflects the *current cycle's* live diagnoses only."""
        live = list((await self.db.execute(
            select(IncidentDiagnosis.status).where(
                IncidentDiagnosis.incident_id == incident.incident_id,
                IncidentDiagnosis.remediation_cycle == incident.remediation_cycle,
                IncidentDiagnosis.status.in_(("hypothesis", "confirmed")),
            )
        )).scalars().all())
        incident.root_cause_state = ("confirmed" if "confirmed" in live
                                     else "hypothesis" if live else "unknown")

    # -------------------------------------------------------------- diagnosis
    async def propose_diagnosis(
        self, incident_id: uuid.UUID, *, actor: Actor, hypothesis: str, reasoning: str,
        stated_confidence: str, supporting_evidence_ids: Sequence[uuid.UUID],
        contradicting_evidence_ids: Sequence[uuid.UUID], catalog_id: str | None = None,
        analysis_history_id: int | None = None, detected_version: str | None = None,
    ) -> IncidentDiagnosis:
        hypothesis = _text(hypothesis, "hypothesis", required=True, limit=1000)
        reasoning = _text(reasoning, "reasoning", required=False, limit=8000)
        if stated_confidence not in STATED_CONFIDENCES:
            raise IncidentValidationError("stated_confidence must be low, medium or high")
        if set(supporting_evidence_ids) & set(contradicting_evidence_ids):
            raise IncidentValidationError("evidence cannot both support and contradict a hypothesis")
        incident = await self._incident(incident_id)
        self._require_open(incident)
        support = await self._evidence_ids(incident_id, supporting_evidence_ids, "supporting_evidence_ids")
        contra = await self._evidence_ids(incident_id, contradicting_evidence_ids, "contradicting_evidence_ids")
        knowledge = await self._knowledge_snapshot(catalog_id, detected_version)
        if analysis_history_id is not None:
            from backend.domain.analyzer.models.history import AnalysisHistory

            exists = (await self.db.execute(
                select(AnalysisHistory.id).where(AnalysisHistory.id == analysis_history_id)
            )).first()
            if exists is None:
                raise IncidentValidationError("analysis_history_id does not reference an existing analysis")

        content = {
            "incident_id": str(incident_id), "cycle": incident.remediation_cycle, "hypothesis": hypothesis,
            "reasoning": reasoning, "stated_confidence": stated_confidence, "supporting": support,
            "contradicting": contra, "knowledge": knowledge, "analysis_history_id": analysis_history_id,
            "proposed_by": actor.identifier, "proposed_assurance": actor.assurance,
        }
        row = IncidentDiagnosis(
            incident_id=incident_id, remediation_cycle=incident.remediation_cycle, hypothesis=hypothesis,
            reasoning=reasoning, stated_confidence=stated_confidence, status="hypothesis",
            supporting_evidence_ids=support, contradicting_evidence_ids=contra, knowledge=knowledge,
            analysis_history_id=analysis_history_id, proposed_by=actor.identifier,
            proposed_assurance=actor.assurance, record_digest=_digest(content),
        )
        self.db.add(row)
        await self.db.flush()
        await self._recompute_root_cause(incident)
        self._event(incident_id=incident_id, record_type="diagnosis", record_id=row.diagnosis_id,
                    action="proposed", actor=actor, digest=row.record_digest,
                    detail={"catalog_id": catalog_id, "stated_confidence": stated_confidence})
        await self.db.flush()
        return row

    async def _load_diagnosis(self, incident_id, diagnosis_id) -> IncidentDiagnosis:
        row = (await self.db.execute(
            select(IncidentDiagnosis).where(
                IncidentDiagnosis.diagnosis_id == diagnosis_id,
                IncidentDiagnosis.incident_id == incident_id,
            ).with_for_update()
        )).scalars().first()
        if row is None:
            raise IncidentNotFound("diagnosis not found for this incident")
        return row

    async def confirm_diagnosis(
        self, incident_id: uuid.UUID, diagnosis_id: uuid.UUID, *, actor: Actor, rationale: str,
    ) -> IncidentDiagnosis:
        await self._require_reviewer(actor)
        rationale = _text(rationale, "rationale", required=True, limit=4000)
        incident = await self._incident(incident_id)
        self._require_open(incident)
        row = await self._load_diagnosis(incident_id, diagnosis_id)
        if row.status != "hypothesis":
            raise IncidentConflict(f"diagnosis is {row.status} and cannot be confirmed")
        if row.remediation_cycle != incident.remediation_cycle:
            raise IncidentTransitionRejected("diagnosis belongs to an earlier remediation cycle")
        if not row.supporting_evidence_ids:
            raise IncidentValidationError("a diagnosis needs supporting evidence before it can be confirmed")
        if row.proposed_assurance == VERIFIED and row.proposed_by == actor.identifier:
            raise IncidentPermissionError("a diagnosis cannot be confirmed by the identity that proposed it")
        already = (await self.db.execute(
            select(IncidentDiagnosis.diagnosis_id).where(
                IncidentDiagnosis.incident_id == incident_id,
                IncidentDiagnosis.remediation_cycle == incident.remediation_cycle,
                IncidentDiagnosis.status == "confirmed",
            )
        )).first()
        if already is not None:
            raise IncidentConflict("another diagnosis is already confirmed in the current cycle")

        row.status = "confirmed"
        row.confirmed_by = actor.identifier
        row.confirmed_assurance = actor.assurance
        row.confirmed_at = datetime.now(UTC)
        await self.db.flush()
        await self._recompute_root_cause(incident)
        confirmation_digest = _digest({
            "diagnosis_digest": row.record_digest, "confirmed_by": actor.identifier,
            "confirmed_assurance": actor.assurance, "rationale": rationale,
            "confirmed_at": row.confirmed_at.isoformat(),
        })
        self._event(incident_id=incident_id, record_type="diagnosis", record_id=row.diagnosis_id,
                    action="confirmed", actor=actor, digest=confirmation_digest,
                    detail={"rationale": rationale})
        await self.db.flush()
        return row

    async def _close_hypothesis(
        self, incident_id, diagnosis_id, *, actor: Actor, reason: str, action: str,
        superseded_by_id: uuid.UUID | None = None,
    ) -> IncidentDiagnosis:
        reason = _text(reason, "reason", required=True, limit=4000)
        incident = await self._incident(incident_id)
        self._require_open(incident)
        row = await self._load_diagnosis(incident_id, diagnosis_id)
        if row.status != "hypothesis":
            raise IncidentConflict(f"only an open hypothesis can be {action}; this one is {row.status}")
        if row.remediation_cycle != incident.remediation_cycle:
            raise IncidentTransitionRejected("diagnosis belongs to an earlier remediation cycle")
        if action == "superseded":
            if superseded_by_id is None or superseded_by_id == diagnosis_id:
                raise IncidentValidationError("superseded_by_id must reference a different diagnosis")
            other = await self._load_diagnosis(incident_id, superseded_by_id)
            if other.status not in ("hypothesis", "confirmed") or \
                    other.remediation_cycle != incident.remediation_cycle:
                raise IncidentValidationError(
                    "the replacement must be a live diagnosis of the current cycle")
        row.status = action
        row.closed_by = actor.identifier
        row.closed_assurance = actor.assurance
        row.closed_at = datetime.now(UTC)
        row.closed_reason = reason
        row.superseded_by_id = superseded_by_id if action == "superseded" else None
        await self.db.flush()
        await self._recompute_root_cause(incident)
        digest = _digest({"diagnosis_digest": row.record_digest, "action": action, "reason": reason,
                          "by": actor.identifier, "assurance": actor.assurance,
                          "superseded_by": str(superseded_by_id) if superseded_by_id else None})
        self._event(incident_id=incident_id, record_type="diagnosis", record_id=row.diagnosis_id,
                    action=action, actor=actor, digest=digest,
                    detail={"reason": reason, "superseded_by": str(superseded_by_id) if superseded_by_id else None})
        await self.db.flush()
        return row

    async def reject_diagnosis(self, incident_id, diagnosis_id, *, actor: Actor, reason: str) -> IncidentDiagnosis:
        """History is kept: the row is not deleted, only closed with who/why/when."""
        return await self._close_hypothesis(incident_id, diagnosis_id, actor=actor, reason=reason,
                                            action="rejected")

    async def supersede_diagnosis(
        self, incident_id, diagnosis_id, *, actor: Actor, reason: str, superseded_by_id: uuid.UUID,
    ) -> IncidentDiagnosis:
        return await self._close_hypothesis(incident_id, diagnosis_id, actor=actor, reason=reason,
                                            action="superseded", superseded_by_id=superseded_by_id)

    async def add_note(self, incident_id: uuid.UUID, *, actor: Actor, text: str) -> IncidentNote:
        """Append an engineer observation. Notes carry no state: they cannot confirm, verify, resolve or close.

        Actor and assurance come from the server-side credential, never from the request body.
        """
        body = _text(text, "text", required=True, limit=4000)
        incident = await self._incident(incident_id)
        if incident.status == "closed":
            raise IncidentConflict("a closed incident does not accept new notes")
        content = {"incident_id": str(incident_id), "body": body, "actor": actor.identifier,
                   "assurance": actor.assurance}
        row = IncidentNote(incident_id=incident_id, body=body, actor=actor.identifier,
                           actor_assurance=actor.assurance, record_digest=_digest(content))
        self.db.add(row)
        await self.db.flush()
        self._event(incident_id=incident_id, record_type="note", record_id=row.note_id, action="noted",
                    actor=actor, digest=row.record_digest, detail={"length": len(body)})
        await self.db.flush()
        return row

    async def list_notes(self, incident_id: uuid.UUID, *, limit: int = 50, offset: int = 0
                         ) -> tuple[list[IncidentNote], int]:
        """Stable chronological order (oldest first; note_id breaks ties)."""
        await self._exists(incident_id)
        limit, offset = _page(limit, offset)
        total = (await self.db.execute(
            select(func.count()).select_from(IncidentNote).where(IncidentNote.incident_id == incident_id)
        )).scalar_one()
        rows = list((await self.db.execute(
            select(IncidentNote).where(IncidentNote.incident_id == incident_id)
            .order_by(IncidentNote.created_at, IncidentNote.note_id).limit(limit).offset(offset)
        )).scalars().all())
        return rows, int(total)

    async def list_diagnoses(self, incident_id: uuid.UUID, *, limit: int = 50, offset: int = 0
                             ) -> tuple[list[IncidentDiagnosis], int]:
        await self._exists(incident_id)
        limit, offset = _page(limit, offset)
        total = (await self.db.execute(
            select(func.count()).select_from(IncidentDiagnosis)
            .where(IncidentDiagnosis.incident_id == incident_id))).scalar_one()
        rows = list((await self.db.execute(
            select(IncidentDiagnosis).where(IncidentDiagnosis.incident_id == incident_id)
            .order_by(IncidentDiagnosis.created_at, IncidentDiagnosis.diagnosis_id)
            .limit(limit).offset(offset)
        )).scalars().all())
        return rows, int(total)

    # ------------------------------------------------------------ remediation
    async def propose_remediation(
        self, incident_id: uuid.UUID, *, actor: Actor, action: str, risk: str, rollback_plan: str,
        expected_verification_criteria: str, impact: str = "", expected_outcome: str = "",
        preconditions: Sequence[str] = (), affected_components: Sequence[str] = (),
        diagnosis_id: uuid.UUID | None = None, catalog_id: str | None = None,
        detected_version: str | None = None,
    ) -> IncidentRemediation:
        action = _text(action, "action", required=True, limit=1000)
        risk = _text(risk, "risk", required=True, limit=4000)
        rollback = _text(rollback_plan, "rollback_plan", required=True, limit=4000)
        criteria = _text(expected_verification_criteria, "expected_verification_criteria",
                         required=True, limit=4000)
        impact = _text(impact, "impact", required=False, limit=4000)
        outcome = _text(expected_outcome, "expected_outcome", required=False, limit=4000)
        incident = await self._incident(incident_id)
        self._require_open(incident)
        if diagnosis_id is not None:
            found = (await self.db.execute(
                select(IncidentDiagnosis.diagnosis_id).where(
                    IncidentDiagnosis.diagnosis_id == diagnosis_id,
                    IncidentDiagnosis.incident_id == incident_id)
            )).first()
            if found is None:
                raise IncidentValidationError("diagnosis_id does not belong to this incident")
        knowledge = await self._knowledge_snapshot(catalog_id, detected_version)
        pre = [str(p).strip() for p in preconditions if str(p).strip()][:20]
        comps = [str(c).strip() for c in affected_components if str(c).strip()][:50]
        content = {
            "incident_id": str(incident_id), "cycle": incident.remediation_cycle, "action": action,
            "risk": risk, "rollback_plan": rollback, "criteria": criteria, "impact": impact,
            "expected_outcome": outcome, "preconditions": pre, "components": comps,
            "diagnosis_id": str(diagnosis_id) if diagnosis_id else None, "knowledge": knowledge,
            "proposed_by": actor.identifier, "proposed_assurance": actor.assurance,
        }
        row = IncidentRemediation(
            incident_id=incident_id, diagnosis_id=diagnosis_id, remediation_cycle=incident.remediation_cycle,
            action=action, preconditions=pre, affected_components=comps, expected_outcome=outcome,
            risk=risk, impact=impact, rollback_plan=rollback, expected_verification_criteria=criteria,
            status="proposed", proposed_by=actor.identifier, proposed_assurance=actor.assurance,
            record_digest=_digest(content), catalog_id=catalog_id, knowledge=knowledge,
        )
        self.db.add(row)
        await self.db.flush()
        self._event(incident_id=incident_id, record_type="remediation", record_id=row.remediation_id,
                    action="proposed", actor=actor, digest=row.record_digest,
                    detail={"catalog_id": catalog_id})
        await self.db.flush()
        return row

    async def record_execution(
        self, incident_id: uuid.UUID, remediation_id: uuid.UUID, *, actor: Actor, actual_action: str,
        outcome: str, outcome_notes: str = "", evidence_ids: Sequence[uuid.UUID] = (),
    ) -> IncidentRemediation:
        actual = _text(actual_action, "actual_action", required=True, limit=4000)
        notes = _text(outcome_notes, "outcome_notes", required=False, limit=4000)
        if outcome not in EXECUTION_OUTCOMES:
            raise IncidentValidationError("outcome must be one of: " + ", ".join(EXECUTION_OUTCOMES))
        incident = await self._incident(incident_id)
        self._require_open(incident)
        row = (await self.db.execute(
            select(IncidentRemediation).where(
                IncidentRemediation.remediation_id == remediation_id,
                IncidentRemediation.incident_id == incident_id).with_for_update()
        )).scalars().first()
        if row is None:
            raise IncidentNotFound("remediation not found for this incident")
        if row.status != "proposed":
            raise IncidentConflict("remediation execution is already recorded")
        if row.remediation_cycle != incident.remediation_cycle:
            raise IncidentTransitionRejected("remediation belongs to an earlier remediation cycle")
        evidence = await self._evidence_ids(incident_id, evidence_ids, "evidence_ids")

        row.status = "executed"
        row.executed_by = actor.identifier
        row.executed_assurance = actor.assurance
        row.executed_at = datetime.now(UTC)
        row.actual_action = actual
        row.outcome = outcome
        row.outcome_notes = notes
        row.execution_evidence_ids = evidence
        digest = _digest({"remediation_digest": row.record_digest, "actual_action": actual,
                          "outcome": outcome, "notes": notes, "evidence": evidence,
                          "executed_by": actor.identifier, "executed_assurance": actor.assurance})
        self._event(incident_id=incident_id, record_type="remediation", record_id=row.remediation_id,
                    action="executed", actor=actor, digest=digest, detail={"outcome": outcome})
        await self.db.flush()
        return row

    async def list_remediations(self, incident_id: uuid.UUID, *, limit: int = 50, offset: int = 0
                                ) -> tuple[list[tuple[IncidentRemediation, str]], int]:
        """Rows with a *derived* verification state.

        'verified' only when an incident_verification record exists for the same
        remediation cycle, passed, and was recorded after a *succeeded* execution.
        It is an incident-level signal, not proof that this remediation caused recovery.
        """
        await self._exists(incident_id)
        limit, offset = _page(limit, offset)
        total = (await self.db.execute(
            select(func.count()).select_from(IncidentRemediation)
            .where(IncidentRemediation.incident_id == incident_id))).scalar_one()
        rows = list((await self.db.execute(
            select(IncidentRemediation).where(IncidentRemediation.incident_id == incident_id)
            .order_by(IncidentRemediation.created_at, IncidentRemediation.remediation_id)
            .limit(limit).offset(offset)
        )).scalars().all())
        verifications = list((await self.db.execute(
            select(IncidentVerification).where(
                IncidentVerification.incident_id == incident_id,
                IncidentVerification.outcome == "passed")
        )).scalars().all())
        out = []
        for row in rows:
            state = "unverified"
            if row.status == "executed" and row.outcome == "succeeded":
                if any(v.remediation_cycle == row.remediation_cycle and v.verified_at >= row.executed_at
                       for v in verifications):
                    state = "verified"
            out.append((row, state))
        return out, int(total)

    async def list_events(self, incident_id: uuid.UUID, *, limit: int = 100, offset: int = 0
                          ) -> tuple[list[IncidentWorkflowEvent], int]:
        await self._exists(incident_id)
        limit, offset = _page(limit, offset)
        total = (await self.db.execute(
            select(func.count()).select_from(IncidentWorkflowEvent)
            .where(IncidentWorkflowEvent.incident_id == incident_id))).scalar_one()
        rows = list((await self.db.execute(
            select(IncidentWorkflowEvent).where(IncidentWorkflowEvent.incident_id == incident_id)
            .order_by(IncidentWorkflowEvent.created_at, IncidentWorkflowEvent.event_id)
            .limit(limit).offset(offset)
        )).scalars().all())
        return rows, int(total)

    # ------------------------------------------------- knowledge proposal link
    async def propose_knowledge(
        self, incident_id: uuid.UUID, diagnosis_id: uuid.UUID, *, actor: Actor, proposal: Any,
        remediation_id: uuid.UUID | None = None, evidence_ids: Sequence[uuid.UUID] = (),
    ) -> tuple[IncidentKnowledgeProposal, Any]:
        """Submit a *proposal* into the existing Knowledge review lifecycle.

        The caller authors the proposal content; nothing is copied automatically from
        the incident and nothing is approved here. The originating incident, confirmed
        diagnosis, optional executed remediation and evidence are recorded in
        ``incident_knowledge_proposal``. Approval stays with the existing reviewer flow.
        """
        incident = await self._incident(incident_id)
        if incident.status not in _TERMINAL:
            raise IncidentTransitionRejected(
                "only a completed (resolved or closed) incident can propose knowledge")
        diagnosis = await self._load_diagnosis(incident_id, diagnosis_id)
        if diagnosis.status != "confirmed" or diagnosis.confirmed_assurance != VERIFIED:
            raise IncidentValidationError(
                "a knowledge proposal must originate from a root cause confirmed by a verified reviewer")
        if diagnosis.remediation_cycle != incident.remediation_cycle:
            raise IncidentTransitionRejected("the diagnosis belongs to an earlier remediation cycle")
        if diagnosis.analysis_history_id is None:
            raise IncidentValidationError(
                "the confirmed diagnosis has no analysis reference; the existing knowledge review "
                "flow requires the analysis it originated from")
        linked_remediation = None
        if remediation_id is not None:
            linked_remediation = (await self.db.execute(
                select(IncidentRemediation).where(
                    IncidentRemediation.remediation_id == remediation_id,
                    IncidentRemediation.incident_id == incident_id)
            )).scalars().first()
            if linked_remediation is None or linked_remediation.status != "executed":
                raise IncidentValidationError("remediation_id must reference an executed remediation of this incident")
        evidence = await self._evidence_ids(incident_id, evidence_ids, "evidence_ids")

        from backend.api.routers.analyzer.knowledge import KnowledgeProposalRequest, create_knowledge_proposal

        request = KnowledgeProposalRequest(history_id=diagnosis.analysis_history_id, **proposal.model_dump())
        from backend.domain.analyzer.auth import OPEN_ACCESS_IDENTITY

        # The analysis is bound to the incident through the confirmed diagnosis. It may be owned by
        # the proposer or by the shared open-access principal (history written without a login).
        entry = await create_knowledge_proposal(
            self.db, request, actor.identifier, commit=False,
            allowed_owners={actor.identifier, OPEN_ACCESS_IDENTITY})
        link = IncidentKnowledgeProposal(
            incident_id=incident_id, diagnosis_id=diagnosis_id, remediation_id=remediation_id,
            knowledge_entry_id=entry.id, remediation_cycle=incident.remediation_cycle, evidence_ids=evidence,
            proposed_by=actor.identifier, proposed_assurance=actor.assurance,
            diagnosis_digest=diagnosis.record_digest,
        )
        self.db.add(link)
        await self.db.flush()
        self._event(incident_id=incident_id, record_type="diagnosis", record_id=diagnosis_id,
                    action="knowledge_proposed", actor=actor,
                    digest=_digest({"diagnosis_digest": diagnosis.record_digest,
                                    "knowledge_entry_id": entry.id, "evidence": evidence}),
                    detail={"knowledge_entry_id": entry.id})
        await self.db.flush()
        return link, entry

    async def list_knowledge_proposals(self, incident_id: uuid.UUID) -> list[IncidentKnowledgeProposal]:
        await self._exists(incident_id)
        return list((await self.db.execute(
            select(IncidentKnowledgeProposal).where(IncidentKnowledgeProposal.incident_id == incident_id)
            .order_by(IncidentKnowledgeProposal.created_at, IncidentKnowledgeProposal.proposal_link_id)
            .limit(MAX_PAGE)
        )).scalars().all())

    async def _exists(self, incident_id: uuid.UUID) -> None:
        found = (await self.db.execute(
            select(Incident.incident_id).where(Incident.incident_id == incident_id))).first()
        if found is None:
            raise IncidentNotFound(f"incident {incident_id} not found")
