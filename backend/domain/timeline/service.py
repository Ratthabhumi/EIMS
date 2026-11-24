"""
==============================================================================
EIMS Query Layer - Unified Timeline Aggregation Service (Sprint 10 + Portal Correction)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

import uuid
from typing import Optional

from sqlalchemy import String, cast, func, literal, null, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger import get_logger
from backend.domain.asset_registry.models import AuditLog
from backend.domain.incident.models import Incident, IncidentEvidence, IncidentVerification
from backend.domain.incident.service import ACTION_INCIDENT_EVIDENCE_ADDED
from backend.domain.telemetry.models import TelemetryMetric, WindowsEventLog
from backend.domain.timeline.schemas import TimelineEvent

logger = get_logger("eims.query.timeline")

ENTITY_TYPE = "asset"
SEVERITY_INFORMATION = "Information"

# Audit verbs that are already represented by incident_evidence rows.
_AUDIT_VERBS_COVERED_BY_EVIDENCE = frozenset({ACTION_INCIDENT_EVIDENCE_ADDED})

_ACTION_DESCRIPTIONS: dict[str, str] = {
    "IMPORT_REPORT": "Imported an offline USB Auditor report and enrolled the asset.",
    "UPDATE_FROM_REPORT": "Updated the asset from an offline USB Auditor report.",
    "ENROLL_ASSET": "Enrolled a new infrastructure asset.",
    "TRANSITION_STATE": "Changed the asset lifecycle state.",
    "INCIDENT_CREATED": "Created a correlated incident from evidence.",
    "INCIDENT_STATUS_CHANGED": "Changed the incident lifecycle status.",
    "INCIDENT_EVIDENCE_ADDED": "Attached evidence to an incident.",
}


def describe_audit_action(action_verb: str, metadata: dict | None) -> str:
    """Maps technical audit verbs to engineer-facing text without dropping the verb."""
    payload = metadata if isinstance(metadata, dict) else {}
    base = _ACTION_DESCRIPTIONS.get(action_verb, f"Recorded action {action_verb}.")
    previous_state = payload.get("previous_state")
    new_state = payload.get("new_state")
    if previous_state and new_state:
        return f"{base} ({previous_state} → {new_state}). Original verb: {action_verb}."
    event = payload.get("event")
    if isinstance(event, str) and event.strip():
        return f"{base} {event.strip()} Original verb: {action_verb}."
    return f"{base} Original verb: {action_verb}."


class TimelineService:
    """
    Aggregates chronological events across audit, incident evidence, incident
    verification, and the legacy telemetry/winlog sources via UNION ALL.
    """

    async def get_timeline(
        self,
        db: AsyncSession,
        entity_id: Optional[uuid.UUID] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        from_dt=None,
        to_dt=None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[TimelineEvent], int]:
        union_subq = union_all(*self._build_source_selects(entity_id=entity_id, event_type=event_type)).subquery()

        conditions = []
        if severity:
            conditions.append(union_subq.c.severity == severity)
        if from_dt is not None:
            conditions.append(union_subq.c.timestamp >= from_dt)
        if to_dt is not None:
            conditions.append(union_subq.c.timestamp <= to_dt)

        count_stmt = select(func.count()).select_from(union_subq).where(*conditions)
        total = (await db.execute(count_stmt)).scalar_one()

        skip = (page - 1) * limit
        page_stmt = (
            select(union_subq)
            .where(*conditions)
            # Deterministic page boundaries when timestamps collide.
            .order_by(union_subq.c.timestamp.desc(), union_subq.c.type.asc(), union_subq.c.id.asc())
            .offset(skip)
            .limit(limit)
        )
        rows = (await db.execute(page_stmt)).all()
        return [self._build_event(row) for row in rows], total

    def _build_source_selects(self, entity_id, event_type) -> list:
        selects = []
        if event_type is None or event_type == "audit":
            selects.append(self._audit_select(entity_id, transition_only=False))
        if event_type == "incident_transition":
            selects.append(self._audit_select(entity_id, transition_only=True))
        if event_type is None or event_type == "evidence":
            selects.append(self._evidence_select(entity_id))
        if event_type is None or event_type == "verification":
            selects.append(self._verification_select(entity_id))
        if event_type is None or event_type == "telemetry":
            selects.append(self._telemetry_select(entity_id))
        if event_type is None or event_type == "winlog":
            selects.append(self._winlog_select(entity_id))
        if not selects:
            raise ValueError(f"Unsupported timeline event type filter: '{event_type}'")
        return selects

    def _audit_select(self, entity_id, *, transition_only: bool):
        stmt = select(
            cast(AuditLog.log_id, String).label("id"),
            literal("incident_transition" if transition_only else "audit").label("type"),
            literal(SEVERITY_INFORMATION).label("severity"),
            AuditLog.performed_at.label("timestamp"),
            cast(AuditLog.asset_id, String).label("entity_id"),
            cast(AuditLog.actor_id, String).label("actor_id"),
            AuditLog.action_verb.label("title"),
            literal("").label("description"),
            AuditLog.immutable_payload.label("metadata"),
        )
        # Evidence attachment is emitted from incident_evidence to avoid duplicates.
        stmt = stmt.where(AuditLog.action_verb.notin_(list(_AUDIT_VERBS_COVERED_BY_EVIDENCE)))
        if transition_only:
            stmt = stmt.where(AuditLog.action_verb == "INCIDENT_STATUS_CHANGED")
        if entity_id is not None:
            stmt = stmt.where(AuditLog.asset_id == entity_id)
        return stmt

    def _evidence_select(self, entity_id):
        stmt = (
            select(
                cast(IncidentEvidence.evidence_id, String).label("id"),
                literal("evidence").label("type"),
                literal(SEVERITY_INFORMATION).label("severity"),
                IncidentEvidence.created_at.label("timestamp"),
                cast(Incident.asset_id, String).label("entity_id"),
                null().cast(String).label("actor_id"),
                func.concat(
                    "Evidence attached (",
                    IncidentEvidence.source_type,
                    "/",
                    IncidentEvidence.source_id,
                    ")",
                ).label("title"),
                literal("").label("description"),
                func.jsonb_build_object(
                    "incident_id", cast(IncidentEvidence.incident_id, String),
                    "actor", IncidentEvidence.added_by,
                    "source_type", IncidentEvidence.source_type,
                    "source_id", IncidentEvidence.source_id,
                    "evidence_digest", IncidentEvidence.evidence_digest,
                    "observed_at", cast(IncidentEvidence.observed_at, String),
                    "correlation_id", null().cast(String),
                ).label("metadata"),
            )
            .select_from(IncidentEvidence)
            .join(Incident, Incident.incident_id == IncidentEvidence.incident_id)
        )
        if entity_id is not None:
            stmt = stmt.where(Incident.asset_id == entity_id)
        return stmt

    def _verification_select(self, entity_id):
        stmt = (
            select(
                cast(IncidentVerification.verification_id, String).label("id"),
                literal("verification").label("type"),
                literal(SEVERITY_INFORMATION).label("severity"),
                IncidentVerification.verified_at.label("timestamp"),
                cast(Incident.asset_id, String).label("entity_id"),
                null().cast(String).label("actor_id"),
                func.concat(
                    "Verification ",
                    IncidentVerification.outcome,
                    " (cycle ",
                    cast(IncidentVerification.remediation_cycle, String),
                    ")",
                ).label("title"),
                literal("").label("description"),
                func.jsonb_build_object(
                    "incident_id", cast(IncidentVerification.incident_id, String),
                    "actor", IncidentVerification.verifier_id,
                    "outcome", IncidentVerification.outcome,
                    "remediation_cycle", IncidentVerification.remediation_cycle,
                    "evidence_id", cast(IncidentVerification.evidence_id, String),
                    "evidence_digest", IncidentVerification.evidence_digest,
                    "correlation_id", null().cast(String),
                ).label("metadata"),
            )
            .select_from(IncidentVerification)
            .join(Incident, Incident.incident_id == IncidentVerification.incident_id)
        )
        if entity_id is not None:
            stmt = stmt.where(Incident.asset_id == entity_id)
        return stmt

    def _telemetry_select(self, entity_id):
        stmt = select(
            cast(TelemetryMetric.metric_id, String).label("id"),
            literal("telemetry").label("type"),
            literal(SEVERITY_INFORMATION).label("severity"),
            TelemetryMetric.event_time.label("timestamp"),
            cast(TelemetryMetric.asset_id, String).label("entity_id"),
            null().cast(String).label("actor_id"),
            func.concat("CPU Utilization ", cast(TelemetryMetric.cpu_utilization, String), "%").label("title"),
            literal("").label("description"),
            TelemetryMetric.diagnostic_payload.label("metadata"),
        )
        if entity_id is not None:
            stmt = stmt.where(TelemetryMetric.asset_id == entity_id)
        return stmt

    def _winlog_select(self, entity_id):
        stmt = select(
            cast(WindowsEventLog.log_id, String).label("id"),
            literal("winlog").label("type"),
            WindowsEventLog.severity_level.label("severity"),
            WindowsEventLog.occurrence_time.label("timestamp"),
            cast(WindowsEventLog.asset_id, String).label("entity_id"),
            null().cast(String).label("actor_id"),
            func.concat("Windows Event ", cast(WindowsEventLog.event_id, String)).label("title"),
            literal("").label("description"),
            WindowsEventLog.evtx_metadata.label("metadata"),
        )
        if entity_id is not None:
            stmt = stmt.where(WindowsEventLog.asset_id == entity_id)
        return stmt

    @staticmethod
    def _build_event(row) -> TimelineEvent:
        metadata = dict(row.metadata or {}) if isinstance(row.metadata, dict) else {}
        description = row.description or ""
        if row.type in {"audit", "incident_transition"}:
            description = describe_audit_action(row.title, metadata)
        elif row.type == "evidence":
            actor = metadata.get("actor") or "unavailable"
            incident = metadata.get("incident_id") or "unavailable"
            description = (
                f"Evidence reference attached by {actor} to incident {incident}. "
                f"Source {metadata.get('source_type', 'unavailable')}/"
                f"{metadata.get('source_id', 'unavailable')}."
            )
        elif row.type == "verification":
            actor = metadata.get("actor") or "unavailable"
            incident = metadata.get("incident_id") or "unavailable"
            outcome = metadata.get("outcome") or "unavailable"
            cycle = metadata.get("remediation_cycle")
            cycle_text = str(cycle) if cycle is not None else "unavailable"
            description = (
                f"Remediation cycle {cycle_text} verification {outcome} by {actor} "
                f"for incident {incident}."
            )

        # Never invent missing relationships — surface honest placeholders in metadata.
        if "correlation_id" not in metadata or not metadata.get("correlation_id"):
            metadata["correlation_id"] = None
        if row.type in {"audit", "incident_transition"} and not metadata.get("actor") and row.actor_id:
            metadata["actor"] = str(row.actor_id)
            metadata.setdefault("assurance", "verified_identity")
        # Preserve explicit unattributed / shared-token / historical-missing markers.
        if not metadata.get("assurance"):
            if metadata.get("actor") or row.actor_id:
                metadata["assurance"] = "verified_identity"
            elif row.type in {"audit", "incident_transition"}:
                # Historical USB imports often omit actor_id — do not invent one.
                metadata["assurance"] = "historical_unavailable"
            else:
                metadata["assurance"] = "unattributed"

        return TimelineEvent(
            id=str(row.id),
            type=row.type,
            title=row.title,
            description=description,
            severity=row.severity or SEVERITY_INFORMATION,
            timestamp=row.timestamp,
            actor_id=uuid.UUID(row.actor_id) if row.actor_id else None,
            entity_id=uuid.UUID(row.entity_id) if row.entity_id else None,
            entity_type=ENTITY_TYPE,
            metadata=metadata,
        )
