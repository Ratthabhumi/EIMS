"""Incident Core idempotency and transactional safety on disposable PostgreSQL."""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.domain.asset_registry.models import AuditLog
from backend.domain.incident.models import Incident, IncidentEvidence
from backend.domain.incident.service import (
    ACTION_INCIDENT_CREATED,
    ACTION_INCIDENT_EVIDENCE_ADDED,
    EvidenceInput,
    IncidentService,
)
from tests.incident_db_support import (
    create_asset,
    create_schema,
    require_database_url,
    session_factory,
)

BASE = datetime(2026, 11, 16, 9, 30, tzinfo=UTC)


@pytest.fixture
def pg():
    url = require_database_url()
    _schema, engine = asyncio.run(create_schema(url))
    try:
        yield engine
    finally:
        asyncio.run(engine.dispose())


def _evidence(source_id="win-1", *, event_key="4625", at=None, source_type="winlog"):
    return EvidenceInput(
        source_type=source_type,
        source_id=source_id,
        observed_at=at or BASE,
        source_event_key=event_key,
    )


async def _count(db, model, *conditions) -> int:
    stmt = select(func.count()).select_from(model)
    if conditions:
        stmt = stmt.where(*conditions)
    return int((await db.execute(stmt)).scalar_one())


def test_same_evidence_twice_yields_one_incident_and_one_evidence_row(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        item = _evidence()

        async with session_factory(pg)() as db:
            first, created = await IncidentService(db).create_from_evidence(
                [item], actor="engineer", asset_id=asset_id
            )
            assert created is True
            first_id = first.incident_id
            assert first.root_cause_state == "unknown"
            correlation = first.summary["correlation"]
            assert correlation["confidence"] == "weak"
            assert "single_source_evidence" in correlation["reasons"]
            assert str(asset_id) in correlation["sources"] or any(
                "winlog:win-1" in source for source in correlation["sources"]
            )

        async with session_factory(pg)() as db:
            second, created_again = await IncidentService(db).create_from_evidence(
                [item], actor="engineer", asset_id=asset_id
            )
            assert created_again is False
            assert second.incident_id == first_id

        async with session_factory(pg)() as db:
            assert await _count(db, Incident) == 1
            assert await _count(db, IncidentEvidence) == 1
            assert (
                await _count(db, AuditLog, AuditLog.action_verb == ACTION_INCIDENT_CREATED)
                == 1
            )
            assert (
                await _count(db, AuditLog, AuditLog.action_verb == ACTION_INCIDENT_EVIDENCE_ADDED)
                == 0
            )

    asyncio.run(scenario())


def test_duplicate_source_identity_is_rejected_by_unique_constraint(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        async with session_factory(pg)() as db:
            incident, _ = await IncidentService(db).create_from_evidence(
                [_evidence()], actor="engineer", asset_id=asset_id
            )
            incident_id = incident.incident_id

        async with session_factory(pg)() as db:
            db.add(
                IncidentEvidence(
                    incident_id=incident_id,
                    source_type="winlog",
                    source_id="win-1",
                    evidence_digest="a" * 64,
                    observed_at=BASE,
                    added_by="engineer",
                )
            )
            with pytest.raises(IntegrityError):
                await db.commit()

        async with session_factory(pg)() as db:
            assert await _count(db, IncidentEvidence) == 1

    asyncio.run(scenario())


def test_attach_evidence_is_idempotent(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        async with session_factory(pg)() as db:
            incident, _ = await IncidentService(db).create_from_evidence(
                [_evidence("win-1")], actor="engineer", asset_id=asset_id
            )
            incident_id = incident.incident_id

        async with session_factory(pg)() as db:
            incident, added = await IncidentService(db).attach_evidence(
                incident_id, [_evidence("win-2", event_key="4624")], actor="engineer"
            )
            assert added == 1
            assert incident.incident_id == incident_id

        async with session_factory(pg)() as db:
            _incident, added_again = await IncidentService(db).attach_evidence(
                incident_id, [_evidence("win-2", event_key="4624")], actor="engineer"
            )
            assert added_again == 0

        async with session_factory(pg)() as db:
            assert await _count(db, Incident) == 1
            assert await _count(db, IncidentEvidence) == 2
            assert (
                await _count(db, AuditLog, AuditLog.action_verb == ACTION_INCIDENT_EVIDENCE_ADDED)
                == 1
            )

    asyncio.run(scenario())


def test_concurrent_create_resolves_to_one_incident(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        item = _evidence("win-concurrent")

        async def attempt():
            async with session_factory(pg)() as db:
                incident, _created = await IncidentService(db).create_from_evidence(
                    [item], actor="engineer", asset_id=asset_id
                )
                return incident.incident_id

        first_id, second_id = await asyncio.gather(attempt(), attempt())
        assert first_id == second_id

        async with session_factory(pg)() as db:
            assert await _count(db, Incident) == 1
            assert await _count(db, IncidentEvidence) == 1
            assert (
                await _count(db, AuditLog, AuditLog.action_verb == ACTION_INCIDENT_CREATED)
                == 1
            )

    asyncio.run(scenario())


def test_injected_failure_rolls_back_incident_evidence_and_audit(pg, monkeypatch):
    def boom(self, incident):  # noqa: ANN001 - test seam signature
        raise RuntimeError("injected persistence failure")

    monkeypatch.setattr(IncidentService, "_post_persist", boom)

    async def scenario():
        asset_id = await create_asset(pg)
        async with session_factory(pg)() as db:
            with pytest.raises(RuntimeError):
                await IncidentService(db).create_from_evidence(
                    [_evidence("win-rollback")], actor="engineer", asset_id=asset_id
                )

        async with session_factory(pg)() as db:
            assert await _count(db, Incident) == 0
            assert await _count(db, IncidentEvidence) == 0
            assert await _count(db, AuditLog) == 0

    asyncio.run(scenario())


def test_unregistered_asset_is_rejected_without_partial_rows(pg):
    async def scenario():
        async with session_factory(pg)() as db:
            with pytest.raises(Exception) as exc:
                await IncidentService(db).create_from_evidence(
                    [_evidence("win-bad-asset")],
                    actor="engineer",
                    asset_id=uuid.uuid4(),
                )
            assert "not registered" in str(exc.value)

        async with session_factory(pg)() as db:
            assert await _count(db, Incident) == 0
            assert await _count(db, IncidentEvidence) == 0

    asyncio.run(scenario())
