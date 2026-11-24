"""End-to-end engineer workflow: evidence -> verification -> resolution -> reopen.

Exercises the same public service path the API uses. The persisted record is
read back from fresh sessions and must answer: what happened, which evidence
supports it, what remediation was verified, who verified it, when, for which
remediation cycle, and why resolution was allowed or blocked.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from backend.domain.asset_registry.models import AuditLog
from backend.domain.incident.models import IncidentEvidence, IncidentVerification
from backend.domain.incident.service import (
    EvidenceInput,
    IncidentPermissionError,
    IncidentService,
    IncidentValidationError,
)
from backend.domain.incident.verification import VerificationRequest
from tests.incident_db_support import (
    attach_analysis_evidence,
    create_asset,
    create_schema,
    create_user,
    require_database_url,
    session_factory,
)

BASE = datetime(2026, 11, 19, 8, 0, tzinfo=UTC)


@pytest.fixture
def pg():
    url = require_database_url()
    _schema, engine = asyncio.run(_bootstrap(url))
    try:
        yield engine
    finally:
        asyncio.run(engine.dispose())


async def _bootstrap(url: str):
    _schema, engine = await create_schema(url)
    await create_user(engine, "engineer", role="user")
    await create_user(engine, "reviewer", role="user", knowledge_reviewer=True)
    return _schema, engine


def test_engineer_end_to_end_verified_resolution_and_reopen(pg):
    async def scenario():
        asset = await create_asset(pg, hostname="synthetic-e2e-host")

        # 1-3. Detect, attach, correlate: two sources on the same asset merge.
        async with session_factory(pg)() as db:
            incident, created = await IncidentService(db).create_from_evidence(
                [EvidenceInput(
                    source_type="winlog", source_id="e2e-winlog-1",
                    source_event_key="4625", observed_at=BASE,
                )],
                actor="engineer",
                asset_id=asset,
                title="Synthetic repeated logon failure",
            )
            assert created is True
            incident_id = incident.incident_id
            assert incident.status == "open"

        async with session_factory(pg)() as db:
            merged, added = await IncidentService(db).attach_evidence(
                incident_id,
                [EvidenceInput(
                    source_type="winlog", source_id="e2e-winlog-2",
                    source_event_key="4625", observed_at=BASE + timedelta(seconds=30),
                )],
                actor="engineer",
            )
            assert merged.incident_id == incident_id
            assert added == 1

        # 4. Investigate.
        for target in ("triage", "investigating"):
            async with session_factory(pg)() as db:
                await IncidentService(db).change_status(
                    incident_id, target, actor="engineer"
                )

        # 5. Resolution without proof is blocked.
        async with session_factory(pg)() as db:
            with pytest.raises(IncidentValidationError) as exc:
                await IncidentService(db).change_status(
                    incident_id, "resolved", actor="reviewer", verifier="reviewer"
                )
        assert "missing_verification" in str(exc.value)

        async with session_factory(pg)() as db:
            current = await IncidentService(db).get_incident(incident_id)
            assert current.status == "investigating"
            assert current.remediation_cycle == 0

        # 6-10. Attach remediation observation, verify, resolve.
        evidence_id = await attach_analysis_evidence(pg, incident_id, asset_id=asset)
        async with session_factory(pg)() as db:
            resolved = await IncidentService(db).change_status(
                incident_id,
                "resolved",
                actor="reviewer",
                verification=VerificationRequest(evidence_id=evidence_id),
                verifier="reviewer",
            )
            assert resolved.status == "resolved"

        # 11. Read the complete record back from a fresh session.
        async with session_factory(pg)() as db:
            incident = await IncidentService(db).get_incident(incident_id)
            evidence = (
                await db.execute(
                    select(IncidentEvidence)
                    .where(IncidentEvidence.incident_id == incident_id)
                    .order_by(IncidentEvidence.created_at)
                )
            ).scalars().all()
            verifications = await IncidentService(db).list_verifications(incident_id)
            audits = (
                await db.execute(
                    select(AuditLog)
                    .where(AuditLog.action_verb == "INCIDENT_STATUS_CHANGED")
                    .order_by(AuditLog.performed_at)
                )
            ).scalars().all()

        assert incident.status == "resolved"
        assert [row.source_type for row in evidence] == ["winlog", "winlog", "analysis"]
        assert len(verifications) == 1
        verification = verifications[0]
        assert verification.outcome == "passed"
        assert verification.remediation_cycle == 0
        assert verification.verifier_id == "reviewer"
        assert verification.evidence_id == evidence_id
        assert verification.verified_at is not None
        assert [a.immutable_payload["new_state"] for a in audits] == [
            "triage", "investigating", "resolved",
        ]
        assert audits[-1].immutable_payload["verifier"] == "reviewer"
        assert audits[-1].immutable_payload["verification_id"] == str(
            verification.verification_id
        )

        # 12-14. Reopen and try to close again with the previous cycle's proof.
        async with session_factory(pg)() as db:
            reopened = await IncidentService(db).change_status(
                incident_id, "investigating", actor="engineer"
            )
            assert reopened.remediation_cycle == 1

        async with session_factory(pg)() as db:
            with pytest.raises(IncidentValidationError) as exc:
                await IncidentService(db).change_status(
                    incident_id,
                    "resolved",
                    actor="reviewer",
                    verification=VerificationRequest(evidence_id=evidence_id),
                    verifier="reviewer",
                )
        assert "evidence_stale" in str(exc.value)

        async with session_factory(pg)() as db:
            incident = await IncidentService(db).get_incident(incident_id)
            verifications = await IncidentService(db).list_verifications(incident_id)
        assert incident.status == "investigating"
        assert len(verifications) == 1, "no stale-cycle verification may be recorded"

        # 15-17. Fresh evidence for the new cycle, then resolve again.
        fresh = await attach_analysis_evidence(pg, incident_id, asset_id=asset)
        async with session_factory(pg)() as db:
            again = await IncidentService(db).change_status(
                incident_id,
                "resolved",
                actor="reviewer",
                verification=VerificationRequest(evidence_id=fresh),
                verifier="reviewer",
            )
            assert again.status == "resolved"
            assert again.remediation_cycle == 1

        # 18. Full history remains visible and ordered by cycle.
        async with session_factory(pg)() as db:
            verifications = await IncidentService(db).list_verifications(incident_id)
        assert [v.remediation_cycle for v in verifications] == [0, 1]
        assert all(v.outcome == "passed" and v.verifier_id == "reviewer"
                   for v in verifications)
        assert verifications[0].evidence_id != verifications[1].evidence_id

    asyncio.run(scenario())


def test_engineer_cannot_self_authorise_resolution(pg):
    """An engineer may gather evidence but not declare the fix verified."""

    async def scenario():
        asset = await create_asset(pg, hostname="synthetic-e2e-guard")
        async with session_factory(pg)() as db:
            incident, _ = await IncidentService(db).create_from_evidence(
                [EvidenceInput(
                    source_type="winlog", source_id="e2e-guard-1", observed_at=BASE,
                    source_event_key="4625",
                )],
                actor="engineer",
                asset_id=asset,
            )
            incident_id = incident.incident_id
        for target in ("triage", "investigating"):
            async with session_factory(pg)() as db:
                await IncidentService(db).change_status(incident_id, target, actor="engineer")
        evidence_id = await attach_analysis_evidence(pg, incident_id, asset_id=asset)
        async with session_factory(pg)() as db:
            with pytest.raises(IncidentPermissionError):
                await IncidentService(db).change_status(
                    incident_id,
                    "resolved",
                    actor="engineer",
                    verification=VerificationRequest(evidence_id=evidence_id),
                    verifier="engineer",
                )
        async with session_factory(pg)() as db:
            incident = await IncidentService(db).get_incident(incident_id)
            rows = (
                await db.execute(
                    select(IncidentVerification).where(
                        IncidentVerification.incident_id == incident_id
                    )
                )
            ).scalars().all()
        assert incident.status == "investigating"
        assert rows == []

    asyncio.run(scenario())
