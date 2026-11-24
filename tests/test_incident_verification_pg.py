"""Verification-before-resolution: the resolution invariant on PostgreSQL.

Every denial asserts persisted state from a fresh session (status, cycle,
verification rows) rather than only the raised exception. All tests run against
the allowlisted disposable PostgreSQL role/database.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from backend.domain.incident.models import IncidentEvidence, IncidentVerification
from backend.domain.incident.schemas import IncidentStatusUpdateRequest
from backend.domain.incident.service import (
    EvidenceInput,
    IncidentPermissionError,
    IncidentService,
    IncidentTransitionRejected,
    IncidentValidationError,
)
from backend.domain.incident.verification import VerificationRequest
from tests.incident_db_support import (
    attach_analysis_evidence,
    create_analysis_observation,
    create_asset,
    create_schema,
    create_user,
    install_verification_append_only,
    require_database_url,
    session_factory,
)

BASE = datetime(2026, 11, 19, 9, 0, tzinfo=UTC)


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
    await install_verification_append_only(engine)
    await create_user(engine, "engineer", role="user")
    await create_user(engine, "reviewer", role="user", knowledge_reviewer=True)
    await create_user(engine, "admin", role="admin")
    await create_user(engine, "outsider", role="user", knowledge_reviewer=False)
    return _schema, engine


async def _ready_incident(engine, asset_id, source_id: str) -> uuid.UUID:
    async with session_factory(engine)() as db:
        incident, _ = await IncidentService(db).create_from_evidence(
            [EvidenceInput(
                source_type="winlog", source_id=source_id, observed_at=BASE,
                source_event_key="4625",
            )],
            actor="engineer",
            asset_id=asset_id,
        )
        incident_id = incident.incident_id
    for target in ("triage", "investigating"):
        async with session_factory(engine)() as db:
            await IncidentService(db).change_status(incident_id, target, actor="engineer")
    return incident_id


async def _attach(engine, incident_id, *, source_type="winlog", source_id=None,
                  observed=BASE) -> uuid.UUID:
    source_id = source_id or f"src-{uuid.uuid4().hex[:12]}"
    async with session_factory(engine)() as db:
        await IncidentService(db).attach_evidence(
            incident_id,
            [EvidenceInput(source_type=source_type, source_id=source_id, observed_at=observed)],
            actor="engineer",
        )
    async with session_factory(engine)() as db:
        row = (
            await db.execute(
                select(IncidentEvidence).where(IncidentEvidence.source_id == source_id)
            )
        ).scalars().first()
        return row.evidence_id


async def _resolve(engine, incident_id, evidence_id, *, verifier="reviewer", actor="engineer"):
    async with session_factory(engine)() as db:
        return await IncidentService(db).change_status(
            incident_id,
            "resolved",
            actor=actor,
            verification=VerificationRequest(evidence_id=evidence_id),
            verifier=verifier,
        )


async def _attempt(engine, incident_id, evidence_id, *, verifier="reviewer"):
    """Run a resolution attempt and return the raised error (or None on success)."""
    try:
        await _resolve(engine, incident_id, evidence_id, verifier=verifier)
        return None
    except Exception as exc:  # noqa: BLE001 - the error is the assertion target
        return exc


async def _state(engine, incident_id):
    async with session_factory(engine)() as db:
        incident = await IncidentService(db).get_incident(incident_id)
        return incident.status, int(incident.remediation_cycle)


async def _verification_count(engine, incident_id, cycle=None) -> int:
    async with session_factory(engine)() as db:
        stmt = select(func.count()).select_from(IncidentVerification).where(
            IncidentVerification.incident_id == incident_id
        )
        if cycle is not None:
            stmt = stmt.where(IncidentVerification.remediation_cycle == cycle)
        return (await db.execute(stmt)).scalar()


def _assert_blocked(error, code: str):
    assert isinstance(error, IncidentValidationError), repr(error)
    assert code in str(error), str(error)


# ---------------------------------------------------------------------------
# 1. no verification at all
# ---------------------------------------------------------------------------
def test_resolve_without_verification_is_rejected_and_not_persisted(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-noverify")
        async with session_factory(pg)() as db:
            with pytest.raises(IncidentValidationError) as exc:
                await IncidentService(db).change_status(
                    incident_id, "resolved", actor="engineer", verifier="reviewer"
                )
        _assert_blocked(exc.value, "missing_verification")
        assert await _state(pg, incident_id) == ("investigating", 0)
        assert await _verification_count(pg, incident_id) == 0

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 2/3. unknown and malformed references
# ---------------------------------------------------------------------------
def test_unknown_evidence_reference_is_rejected(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-unknown")
        error = await _attempt(pg, incident_id, uuid.uuid4())
        _assert_blocked(error, "evidence_unknown")
        assert await _state(pg, incident_id) == ("investigating", 0)
        assert await _verification_count(pg, incident_id) == 0

    asyncio.run(scenario())


def test_malformed_evidence_reference_is_rejected(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-malformed")
        error = await _attempt(pg, incident_id, "not-a-uuid")
        _assert_blocked(error, "evidence_malformed")
        assert await _state(pg, incident_id) == ("investigating", 0)
        assert await _verification_count(pg, incident_id) == 0

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 4. wrong evidence type
# ---------------------------------------------------------------------------
def test_evidence_type_that_cannot_prove_outcome_is_rejected(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-type")
        winlog_evidence = await _attach(pg, incident_id, source_type="winlog",
                                        source_id="winlog-verify-attempt")
        error = await _attempt(pg, incident_id, winlog_evidence)
        _assert_blocked(error, "evidence_type_not_verifiable")
        assert await _state(pg, incident_id) == ("investigating", 0)
        assert await _verification_count(pg, incident_id) == 0

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 5. evidence from another incident
# ---------------------------------------------------------------------------
def test_evidence_belonging_to_another_incident_is_rejected(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        other_asset = await create_asset(pg, hostname="synthetic-other-host")
        first = await _ready_incident(pg, asset_id, "win-owner-1")
        second = await _ready_incident(pg, other_asset, "win-owner-2")
        second_evidence = await attach_analysis_evidence(pg, second, asset_id=other_asset)
        error = await _attempt(pg, first, second_evidence)
        _assert_blocked(error, "evidence_foreign")
        assert await _state(pg, first) == ("investigating", 0)
        assert await _verification_count(pg, first) == 0

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 6. corrupted digest
# ---------------------------------------------------------------------------
def test_corrupted_evidence_digest_is_rejected(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-digest")
        evidence_id = await attach_analysis_evidence(pg, incident_id, asset_id=asset_id)
        async with session_factory(pg)() as db:
            await db.execute(
                text("UPDATE incident_evidence SET evidence_digest = :d WHERE evidence_id = :e"),
                {"d": "f" * 64, "e": evidence_id},
            )
            await db.commit()
        error = await _attempt(pg, incident_id, evidence_id)
        _assert_blocked(error, "evidence_digest_mismatch")
        assert await _state(pg, incident_id) == ("investigating", 0)
        assert await _verification_count(pg, incident_id) == 0

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 7/17. stale evidence from an earlier cycle, and fresh evidence afterwards
# ---------------------------------------------------------------------------
def test_evidence_from_earlier_cycle_is_rejected_and_fresh_evidence_allowed(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-cycle")
        old_evidence = await attach_analysis_evidence(pg, incident_id, asset_id=asset_id)
        resolved = await _resolve(pg, incident_id, old_evidence)
        assert resolved.status == "resolved"
        assert resolved.remediation_cycle == 0
        assert await _verification_count(pg, incident_id, 0) == 1

        async with session_factory(pg)() as db:
            reopened = await IncidentService(db).change_status(
                incident_id, "investigating", actor="engineer"
            )
            assert reopened.remediation_cycle == 1

        # The previous cycle's evidence cannot authorise the new cycle.
        error = await _attempt(pg, incident_id, old_evidence)
        _assert_blocked(error, "evidence_stale")
        assert await _state(pg, incident_id) == ("investigating", 1)
        assert await _verification_count(pg, incident_id, 1) == 0

        fresh = await attach_analysis_evidence(pg, incident_id, asset_id=asset_id)
        again = await _resolve(pg, incident_id, fresh)
        assert again.status == "resolved"
        assert again.remediation_cycle == 1
        assert await _verification_count(pg, incident_id, 1) == 1
        # History is preserved, not replaced.
        assert await _verification_count(pg, incident_id) == 2

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 8. evidence whose trusted source does not exist
# ---------------------------------------------------------------------------
def test_evidence_without_persisted_source_is_rejected(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-source")
        evidence_id = await attach_analysis_evidence(pg, incident_id, asset_id=asset_id)
        async with session_factory(pg)() as db:
            source_id = (await db.execute(
                text("SELECT source_id FROM incident_evidence WHERE evidence_id = :e"),
                {"e": evidence_id},
            )).scalar()
            await db.execute(text("DELETE FROM analysis_history WHERE id = :i"),
                             {"i": int(source_id)})
            await db.commit()
        error = await _attempt(pg, incident_id, evidence_id)
        _assert_blocked(error, "evidence_source_unknown")
        assert await _state(pg, incident_id) == ("investigating", 0)
        assert await _verification_count(pg, incident_id) == 0

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 9/10. verifier authorization
# ---------------------------------------------------------------------------
def test_unauthorized_verifier_is_rejected(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-unauth")
        evidence_id = await attach_analysis_evidence(pg, incident_id, asset_id=asset_id)
        error = await _attempt(pg, incident_id, evidence_id, verifier="outsider")
        assert isinstance(error, IncidentPermissionError), repr(error)
        assert "verifier_unauthorized" in str(error), str(error)
        assert await _state(pg, incident_id) == ("investigating", 0)
        assert await _verification_count(pg, incident_id) == 0

    asyncio.run(scenario())


def test_unknown_or_anonymous_verifier_is_rejected(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-ghost")
        evidence_id = await attach_analysis_evidence(pg, incident_id, asset_id=asset_id)
        for verifier in ("ghost-user", "demo", "guest", None):
            error = await _attempt(pg, incident_id, evidence_id, verifier=verifier)
            assert error is not None, verifier
            assert isinstance(error, IncidentPermissionError), repr(error)
            assert "verifier_" in str(error), str(error)
        assert await _state(pg, incident_id) == ("investigating", 0)
        assert await _verification_count(pg, incident_id) == 0

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 11. valid verification
# ---------------------------------------------------------------------------
def test_valid_current_cycle_evidence_with_authorized_verifier_resolves(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-valid")
        evidence_id = await attach_analysis_evidence(pg, incident_id, asset_id=asset_id)
        resolved = await _resolve(pg, incident_id, evidence_id, verifier="admin")
        assert resolved.status == "resolved"

        async with session_factory(pg)() as db:
            rows = (await db.execute(
                select(IncidentVerification).where(
                    IncidentVerification.incident_id == incident_id
                )
            )).scalars().all()
            assert len(rows) == 1
            row = rows[0]
            assert row.outcome == "passed"
            assert row.verifier_id == "admin"
            assert row.remediation_cycle == 0
            assert row.evidence_id == evidence_id
            assert len(row.evidence_digest) == 64

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 12. duplicate submission
# ---------------------------------------------------------------------------
def test_duplicate_resolution_is_rejected_without_extra_verification(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-dup")
        evidence_id = await attach_analysis_evidence(pg, incident_id, asset_id=asset_id)
        await _resolve(pg, incident_id, evidence_id)
        error = await _attempt(pg, incident_id, evidence_id)
        assert isinstance(error, IncidentTransitionRejected), repr(error)
        assert await _state(pg, incident_id) == ("resolved", 0)
        assert await _verification_count(pg, incident_id) == 1

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 13. concurrent resolve
# ---------------------------------------------------------------------------
def test_concurrent_resolution_produces_one_authoritative_verification(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-race")
        evidence_id = await attach_analysis_evidence(pg, incident_id, asset_id=asset_id)
        barrier = asyncio.Event()

        async def attempt():
            await barrier.wait()
            return await _attempt(pg, incident_id, evidence_id)

        tasks = [asyncio.create_task(attempt()) for _ in range(2)]
        await asyncio.sleep(0)
        barrier.set()
        results = await asyncio.gather(*tasks)

        successes = [r for r in results if r is None]
        failures = [r for r in results if r is not None]
        assert len(successes) == 1, results
        assert len(failures) == 1, results
        assert isinstance(failures[0], (IncidentTransitionRejected, IntegrityError)), failures[0]
        assert await _state(pg, incident_id) == ("resolved", 0)
        assert await _verification_count(pg, incident_id) == 1

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 14. resolve racing with reopen
# ---------------------------------------------------------------------------
def test_resolve_racing_with_reopen_cannot_reuse_stale_verification(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-reopen-race")
        old_evidence = await attach_analysis_evidence(pg, incident_id, asset_id=asset_id)
        await _resolve(pg, incident_id, old_evidence)

        barrier = asyncio.Event()

        async def reopen():
            await barrier.wait()
            async with session_factory(pg)() as db:
                try:
                    return await IncidentService(db).change_status(
                        incident_id, "investigating", actor="engineer"
                    )
                except Exception as exc:  # noqa: BLE001
                    return exc

        async def stale_resolve():
            await barrier.wait()
            return await _attempt(pg, incident_id, old_evidence)

        tasks = [asyncio.create_task(reopen()), asyncio.create_task(stale_resolve())]
        await asyncio.sleep(0)
        barrier.set()
        await asyncio.gather(*tasks)

        status, cycle = await _state(pg, incident_id)
        assert (status, cycle) == ("investigating", 1), (status, cycle)
        # No verification row may exist for the new cycle.
        assert await _verification_count(pg, incident_id, 1) == 0
        assert await _verification_count(pg, incident_id, 0) == 1

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 15. persistence failure rolls back the transition
# ---------------------------------------------------------------------------
def test_verification_persistence_failure_rolls_back_resolution(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-persist")
        evidence_id = await attach_analysis_evidence(pg, incident_id, asset_id=asset_id)

        # Pre-existing authoritative row for this (incident, cycle, evidence).
        async with session_factory(pg)() as db:
            await db.execute(
                text(
                    "INSERT INTO incident_verification "
                    "(verification_id, incident_id, remediation_cycle, evidence_id, "
                    " evidence_digest, outcome, verifier_id, verified_at) "
                    "VALUES (:v,:i,0,:e,:d,'passed','reviewer',now())"
                ),
                {"v": uuid.uuid4(), "i": incident_id, "e": evidence_id, "d": "a" * 64},
            )
            await db.commit()

        async with session_factory(pg)() as db:
            with pytest.raises(IntegrityError):
                await IncidentService(db).change_status(
                    incident_id,
                    "resolved",
                    actor="engineer",
                    verification=VerificationRequest(evidence_id=evidence_id),
                    verifier="reviewer",
                )

        assert await _state(pg, incident_id) == ("investigating", 0)
        assert await _verification_count(pg, incident_id) == 1

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 16. history/audit consistency
# ---------------------------------------------------------------------------
def test_resolution_records_verification_and_audit_together(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-audit")
        evidence_id = await attach_analysis_evidence(pg, incident_id, asset_id=asset_id)
        await _resolve(pg, incident_id, evidence_id)

        async with session_factory(pg)() as db:
            payload = (await db.execute(
                text(
                    "SELECT immutable_payload FROM audit_logs "
                    "WHERE action_verb = 'INCIDENT_STATUS_CHANGED' "
                    "AND immutable_payload ->> 'new_state' = 'resolved'"
                )
            )).scalar()
            verification_id = (await db.execute(
                select(IncidentVerification.verification_id).where(
                    IncidentVerification.incident_id == incident_id
                )
            )).scalar()
        assert payload is not None
        assert payload["verification_id"] == str(verification_id)
        assert payload["verifier"] == "reviewer"
        assert payload["remediation_cycle"] == 0
        assert payload["verified_evidence_id"] == str(evidence_id)

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# append-only history
# ---------------------------------------------------------------------------
def test_verification_history_rejects_update_and_delete(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-append")
        evidence_id = await attach_analysis_evidence(pg, incident_id, asset_id=asset_id)
        await _resolve(pg, incident_id, evidence_id)

        for statement in (
            "UPDATE incident_verification SET outcome = 'failed'",
            "DELETE FROM incident_verification",
            "TRUNCATE incident_verification",
        ):
            with pytest.raises(DBAPIError) as exc:
                async with pg.begin() as conn:
                    await conn.execute(text(statement))
            assert "append-only" in str(exc.value), str(exc.value)

        assert await _verification_count(pg, incident_id) == 1

    asyncio.run(scenario())


def test_resolved_incident_cannot_be_inserted_directly(pg):
    """A raw INSERT must not fabricate an already-resolved incident."""

    async def scenario():
        with pytest.raises(DBAPIError) as exc:
            async with pg.begin() as conn:
                await conn.execute(text(
                    "INSERT INTO incidents (incident_id, title, status, severity, "
                    "confidence, first_seen, last_seen, dedupe_key) "
                    "VALUES (:i, 'forged', 'resolved', 'high', 'weak', now(), now(), :k)"
                ), {"i": uuid.uuid4(), "k": uuid.uuid4().hex + uuid.uuid4().hex})
        assert "must be created in a non-resolved state" in str(exc.value), str(exc.value)

    asyncio.run(scenario())


def test_raw_sql_cannot_resolve_without_verification(pg):

    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-raw-sql")
        with pytest.raises(DBAPIError) as exc:
            async with pg.begin() as conn:
                await conn.execute(
                    text("UPDATE incidents SET status='resolved' WHERE incident_id=:i"),
                    {"i": incident_id},
                )
        assert "cannot be resolved without verification" in str(exc.value), str(exc.value)
        assert await _state(pg, incident_id) == ("investigating", 0)

    asyncio.run(scenario())


def test_verifier_cannot_verify_evidence_they_attached(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-sod")
        evidence_id = await attach_analysis_evidence(
            pg, incident_id, actor="reviewer", asset_id=asset_id
        )
        error = await _attempt(pg, incident_id, evidence_id, verifier="reviewer")
        assert isinstance(error, IncidentPermissionError), repr(error)
        assert "verifier_conflict" in str(error), str(error)
        assert await _state(pg, incident_id) == ("investigating", 0)
        assert await _verification_count(pg, incident_id) == 0

    asyncio.run(scenario())


def test_non_canonical_source_id_is_rejected(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        incident_id = await _ready_incident(pg, asset_id, "win-canonical")
        await create_analysis_observation(pg, asset_id=asset_id)
        canonical = (await _latest_analysis_id(pg))
        padded = "0" + canonical
        evidence_id = await _attach(
            pg, incident_id, source_type="analysis", source_id=padded,
            observed=datetime.now(UTC),
        )
        error = await _attempt(pg, incident_id, evidence_id)
        assert isinstance(error, IncidentValidationError), repr(error)
        assert "evidence_source_malformed" in str(error), str(error)
        assert await _verification_count(pg, incident_id) == 0

        # An all-digit id that cannot fit the integer column fails closed too.
        oversized = await _attach(
            pg, incident_id, source_type="analysis", source_id="99999999999999999999",
            observed=datetime.now(UTC),
        )
        error = await _attempt(pg, incident_id, oversized)
        assert isinstance(error, IncidentValidationError), repr(error)
        assert "evidence_source_malformed" in str(error), str(error)
        assert await _verification_count(pg, incident_id) == 0

    asyncio.run(scenario())


def test_analysis_observation_for_another_asset_is_rejected(pg):
    async def scenario():
        asset_id = await create_asset(pg)
        other_asset = await create_asset(pg, hostname="synthetic-foreign-asset")
        incident_id = await _ready_incident(pg, asset_id, "win-asset-match")
        evidence_id = await attach_analysis_evidence(
            pg, incident_id, asset_id=other_asset
        )
        error = await _attempt(pg, incident_id, evidence_id)
        assert isinstance(error, IncidentValidationError), repr(error)
        assert "evidence_asset_mismatch" in str(error), str(error)
        assert await _verification_count(pg, incident_id) == 0

    asyncio.run(scenario())


async def _latest_analysis_id(engine) -> str:
    async with session_factory(engine)() as db:
        return str((await db.execute(text(
            "SELECT max(id) FROM analysis_history"))).scalar())


# ---------------------------------------------------------------------------
# request-shape hardening (no database required)
# ---------------------------------------------------------------------------
def test_request_schema_refuses_forged_outcome_and_verifier():
    good = str(uuid.uuid4())
    with pytest.raises(ValidationError):
        IncidentStatusUpdateRequest(
            status="resolved",
            verification={"evidence_id": good, "verifier_id": "admin"},
        )
    with pytest.raises(ValidationError):
        IncidentStatusUpdateRequest(
            status="resolved",
            verification={"evidence_id": good, "outcome": "passed"},
        )
    # Omission is a valid request shape; the service rejects it as a missing
    # verification, not the parser.
    payload = IncidentStatusUpdateRequest(status="resolved")
    assert payload.verification is None
