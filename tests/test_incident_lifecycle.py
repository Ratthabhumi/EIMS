"""Incident Core lifecycle matrix and reviewer-gated closure."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from backend.domain.asset_registry.models import AuditLog
from backend.domain.incident.service import (
    ACTION_INCIDENT_STATUS_CHANGED,
    LEGAL_TRANSITIONS,
    EvidenceInput,
    IncidentConflict,
    IncidentPermissionError,
    IncidentService,
    IncidentTransitionRejected,
    can_transition,
    validate_transition,
)
from tests.incident_db_support import (
    attach_analysis_evidence,
    create_asset,
    create_schema,
    create_user,
    require_database_url,
    session_factory,
)

BASE = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
STATUSES = ("open", "triage", "investigating", "resolved", "closed")
LEGAL_EDGES = {
    ("open", "triage"),
    ("triage", "investigating"),
    ("investigating", "resolved"),
    ("resolved", "closed"),
    ("resolved", "investigating"),
}


def _evidence(source_id="win-lifecycle", observed=BASE):
    return EvidenceInput(
        source_type="winlog", source_id=source_id, observed_at=observed, source_event_key="4625"
    )


async def _resolve(engine, incident_id, *, asset_id=None, verifier="reviewer"):
    """Resolve through the real invariant: fresh verification-grade evidence."""
    from backend.domain.incident.verification import VerificationRequest

    evidence_id = await attach_analysis_evidence(
        engine, incident_id, asset_id=asset_id
    )
    async with session_factory(engine)() as db:
        return await IncidentService(db).change_status(
            incident_id,
            "resolved",
            actor="engineer",
            verification=VerificationRequest(evidence_id=evidence_id),
            verifier=verifier,
        )


@pytest.fixture
def pg():
    url = require_database_url()
    _schema, engine = asyncio.run(create_schema(url))
    asyncio.run(create_user(engine, "reviewer", role="user", knowledge_reviewer=True))
    try:
        yield engine
    finally:
        asyncio.run(engine.dispose())


def test_transition_matrix_is_exactly_the_documented_edges():
    assert can_transition("open", "triage")
    assert can_transition("resolved", "investigating")  # explicit reopen only
    assert not can_transition("open", "investigating")
    assert not can_transition("closed", "investigating")
    assert LEGAL_TRANSITIONS["closed"] == frozenset()


@pytest.mark.parametrize("current", STATUSES)
@pytest.mark.parametrize("target", STATUSES)
def test_every_non_legal_edge_is_rejected(current, target):
    if (current, target) in LEGAL_EDGES:
        validate_transition(current, target)
        return
    with pytest.raises(IncidentTransitionRejected):
        validate_transition(current, target)


def test_full_legal_path_records_audit_and_never_asserts_root_cause(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        async with session_factory(pg)() as db:
            incident, _ = await IncidentService(db).create_from_evidence(
                [_evidence()], actor="engineer", asset_id=asset_id
            )
            incident_id = incident.incident_id
            assert incident.status == "open"
            assert incident.root_cause_state == "unknown"

        for target in ("triage", "investigating"):
            async with session_factory(pg)() as db:
                updated = await IncidentService(db).change_status(
                    incident_id, target, actor="engineer"
                )
                assert updated.status == target
                assert updated.root_cause_state == "unknown"

        resolved = await _resolve(pg, incident_id, asset_id=asset_id)
        assert resolved.status == "resolved"
        assert resolved.root_cause_state == "unknown"

        async with session_factory(pg)() as db:
            closed = await IncidentService(db).change_status(
                incident_id, "closed", actor="reviewer", reviewer_identity="reviewer"
            )
            assert closed.status == "closed"
            assert closed.owner == "reviewer"
            assert closed.root_cause_state == "unknown"

        async with session_factory(pg)() as db:
            rows = (
                await db.execute(
                    select(AuditLog)
                    .where(AuditLog.action_verb == ACTION_INCIDENT_STATUS_CHANGED)
                    .order_by(AuditLog.performed_at)
                )
            ).scalars().all()
            assert [row.immutable_payload["new_state"] for row in rows] == [
                "triage",
                "investigating",
                "resolved",
                "closed",
            ]
            assert rows[-1].immutable_payload["reviewer"] == "reviewer"
            assert all(row.immutable_payload["incident_id"] == str(incident_id) for row in rows)

    asyncio.run(scenario())


def test_illegal_transition_is_rejected_and_state_is_unchanged(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        async with session_factory(pg)() as db:
            incident, _ = await IncidentService(db).create_from_evidence(
                [_evidence("win-illegal")], actor="engineer", asset_id=asset_id
            )
            incident_id = incident.incident_id

        async with session_factory(pg)() as db:
            with pytest.raises(IncidentTransitionRejected):
                await IncidentService(db).change_status(
                    incident_id, "resolved", actor="engineer"
                )

        async with session_factory(pg)() as db:
            incident = await IncidentService(db).get_incident(incident_id)
            assert incident.status == "open"

    asyncio.run(scenario())


def test_reopen_from_resolved_is_allowed_and_close_stays_terminal(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        async with session_factory(pg)() as db:
            incident, _ = await IncidentService(db).create_from_evidence(
                [_evidence("win-reopen")], actor="engineer", asset_id=asset_id
            )
            incident_id = incident.incident_id

        for target in ("triage", "investigating"):
            async with session_factory(pg)() as db:
                await IncidentService(db).change_status(incident_id, target, actor="engineer")

        await _resolve(pg, incident_id, asset_id=asset_id)

        async with session_factory(pg)() as db:
            reopened = await IncidentService(db).change_status(
                incident_id, "investigating", actor="engineer"
            )
            assert reopened.status == "investigating"
            assert reopened.remediation_cycle == 1

        # Re-resolution requires evidence for the new cycle.
        again = await _resolve(pg, incident_id, asset_id=asset_id)
        assert again.status == "resolved"
        assert again.remediation_cycle == 1

        async with session_factory(pg)() as db:
            await IncidentService(db).change_status(
                incident_id, "closed", actor="reviewer", reviewer_identity="reviewer"
            )

        async with session_factory(pg)() as db:
            with pytest.raises(IncidentTransitionRejected):
                await IncidentService(db).change_status(
                    incident_id, "investigating", actor="reviewer", reviewer_identity="reviewer"
                )

    asyncio.run(scenario())


def test_close_without_reviewer_identity_is_denied_and_not_persisted(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        async with session_factory(pg)() as db:
            incident, _ = await IncidentService(db).create_from_evidence(
                [_evidence("win-close-guard")], actor="engineer", asset_id=asset_id
            )
            incident_id = incident.incident_id

        for target in ("triage", "investigating"):
            async with session_factory(pg)() as db:
                await IncidentService(db).change_status(incident_id, target, actor="engineer")

        await _resolve(pg, incident_id, asset_id=asset_id)

        async with session_factory(pg)() as db:
            with pytest.raises(IncidentPermissionError):
                await IncidentService(db).change_status(
                    incident_id, "closed", actor="engineer"
                )

        async with session_factory(pg)() as db:
            incident = await IncidentService(db).get_incident(incident_id)
            assert incident.status == "resolved"
            assert incident.owner is None

    asyncio.run(scenario())

def test_recurrence_after_closure_creates_new_open_incident(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        async with session_factory(pg)() as db:
            first, _ = await IncidentService(db).create_from_evidence(
                [_evidence("recur-1")], actor="engineer", asset_id=asset_id
            )
            first_id = first.incident_id

        for target in ("triage", "investigating"):
            async with session_factory(pg)() as db:
                await IncidentService(db).change_status(first_id, target, actor="engineer")
        await _resolve(pg, first_id, asset_id=asset_id)
        async with session_factory(pg)() as db:
            await IncidentService(db).change_status(
                first_id, "closed", actor="engineer", reviewer_identity="reviewer"
            )

        # A new occurrence of the same signature within the window must start a
        # new open incident, not merge into the closed row.
        async with session_factory(pg)() as db:
            second, created = await IncidentService(db).create_from_evidence(
                [_evidence("recur-2", observed=BASE + timedelta(seconds=60))],
                actor="engineer",
                asset_id=asset_id,
            )
            assert created is True
            assert second.incident_id != first_id
            assert second.status == "open"

        # Evidence may not be attached to a closed incident.
        async with session_factory(pg)() as db:
            with pytest.raises(IncidentConflict):
                await IncidentService(db).attach_evidence(
                    first_id, [_evidence("recur-3")], actor="engineer"
                )

        async with session_factory(pg)() as db:
            original = await IncidentService(db).get_incident(first_id)
            assert original.status == "closed"

    asyncio.run(scenario())
