"""Regression for the defect found by the end-to-end run: occurrence-fingerprint evidence must verify and resolve.

Sequence that failed over real HTTP: evidence enriched with an occurrence fingerprint -> verification recomputed only the
source-identity digest -> ``evidence_digest_mismatch`` and, after a partial fix, a database CHECK violation
(``cannot be resolved without verification``). These tests drive the same sequence through the real service on
PostgreSQL and assert persisted state from fresh sessions after every denial.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text

from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.incident.models import IncidentEvidence, IncidentVerification
from backend.domain.incident.service import EvidenceInput, IncidentService, IncidentValidationError
from backend.domain.incident.verification import VerificationRequest
from tests.incident_db_support import (
    create_asset, create_schema, create_user, install_verification_append_only, require_database_url, session_factory,
)

NOW = datetime.now(UTC).replace(microsecond=0)


@pytest.fixture
def pg():
    url = require_database_url()

    async def boot():
        _schema, engine = await create_schema(url)
        await install_verification_append_only(engine)
        for name, reviewer in (("engineer", False), ("reviewer", True)):
            await create_user(engine, name, role="user", knowledge_reviewer=reviewer)
        return engine

    engine = asyncio.run(boot())
    try:
        yield engine
    finally:
        asyncio.run(engine.dispose())


async def _row(engine, asset_id, *, record_id, timestamp=None):
    meta = {"sourceFamily": "windows_event", "computer": "HOST-1", "logName": "Application", "record_id": record_id}
    if timestamp is not None:
        meta["timestamp"] = timestamp
    async with session_factory(engine)() as db:
        row = AnalysisHistory(event_id="1026", provider=".NET Runtime", username="engineer", description="fault " + record_id,
                              solution_summary={}, event_metadata=meta, search_results=[], asset_id=asset_id)
        db.add(row)
        await db.commit()
        return str(row.id)


async def _incident_investigating(engine, asset_id):
    async with session_factory(engine)() as db:
        incident, _ = await IncidentService(db).create_from_evidence(
            [EvidenceInput("winlog", "w-seed", NOW, source_event_key="4625")], actor="engineer", asset_id=asset_id)
        incident_id = incident.incident_id
    for target in ("triage", "investigating"):
        async with session_factory(engine)() as db:
            await IncidentService(db).change_status(incident_id, target, actor="engineer")
    return incident_id


async def _attach_enriched(engine, incident_id, asset_id, source_id, *, caller_digest=None):
    async with session_factory(engine)() as db:
        svc = IncidentService(db)
        items, _asset = await svc.enrich_evidence(
            [EvidenceInput("analysis", source_id, NOW, evidence_digest=caller_digest)], asset_id)
        await svc.attach_evidence(incident_id, items, actor="engineer")
    async with session_factory(engine)() as db:
        return (await db.execute(select(IncidentEvidence).where(IncidentEvidence.source_id == source_id))).scalar_one()


async def _resolve(engine, incident_id, evidence_id, verifier="reviewer"):
    async with session_factory(engine)() as db:
        return await IncidentService(db).change_status(
            incident_id, "resolved", actor="engineer", verification=VerificationRequest(evidence_id=evidence_id), verifier=verifier)


async def _counts(engine, incident_id):
    async with session_factory(engine)() as db:
        verifications = (await db.execute(select(func.count()).select_from(IncidentVerification).where(
            IncidentVerification.incident_id == incident_id))).scalar()
        audits = (await db.execute(text(
            "SELECT count(*) FROM audit_logs WHERE immutable_payload ->> 'new_state' = 'resolved'"))).scalar()
        status = (await db.execute(text("SELECT status FROM incidents WHERE incident_id = :i"), {"i": incident_id})).scalar()
        return verifications, audits, status


def test_fingerprinted_analysis_evidence_verifies_and_resolves(pg):
    async def scenario():
        asset = await create_asset(pg)
        incident_id = await _incident_investigating(pg, asset)
        source = await _row(pg, asset, record_id="901", timestamp="2026-11-20T01:02:03Z")
        evidence = await _attach_enriched(pg, incident_id, asset, source)
        assert evidence.time_confidence == "exact" and evidence.event_time is not None   # event time, not request time
        resolved = await _resolve(pg, incident_id, evidence.evidence_id)
        assert resolved.status == "resolved"
        async with session_factory(pg)() as db:
            row = (await db.execute(select(IncidentVerification).where(IncidentVerification.incident_id == incident_id))).scalar_one()
        # The verification stores the very digest the evidence row carries (what the DB trigger compares).
        assert row.evidence_digest == evidence.evidence_digest and row.outcome == "passed"
        assert await _counts(pg, incident_id) == (1, 1, "resolved")

    asyncio.run(scenario())


def test_caller_cannot_forge_the_fingerprint_and_tampering_is_rejected_without_side_effects(pg):
    async def scenario():
        asset = await create_asset(pg)
        incident_id = await _incident_investigating(pg, asset)
        source = await _row(pg, asset, record_id="902", timestamp="2026-11-20T01:02:03Z")
        forged = "a" * 64
        evidence = await _attach_enriched(pg, incident_id, asset, source, caller_digest=forged)
        assert evidence.evidence_digest != forged                      # caller digest ignored for analysis evidence
        async with session_factory(pg)() as db:                        # now tamper with the stored digest directly
            await db.execute(text("UPDATE incident_evidence SET evidence_digest = :d WHERE evidence_id = :e"),
                             {"d": "f" * 64, "e": evidence.evidence_id})
            await db.commit()
        before = await _counts(pg, incident_id)
        for _ in range(2):                                              # a retry must neither succeed nor duplicate anything
            with pytest.raises(IncidentValidationError) as error:
                await _resolve(pg, incident_id, evidence.evidence_id)
            assert "evidence_digest_mismatch" in str(error.value)
        assert await _counts(pg, incident_id) == before == (0, 0, "investigating")
        # Repair the evidence (restore the server-derived digest) and the same incident now resolves exactly once.
        async with session_factory(pg)() as db:
            from backend.domain.incident.evidence_identity import analysis_fingerprint
            row = await db.get(AnalysisHistory, int(source))
            await db.execute(text("UPDATE incident_evidence SET evidence_digest = :d WHERE evidence_id = :e"),
                             {"d": analysis_fingerprint(row), "e": evidence.evidence_id})
            await db.commit()
        assert (await _resolve(pg, incident_id, evidence.evidence_id)).status == "resolved"
        assert await _counts(pg, incident_id) == (1, 1, "resolved")

    asyncio.run(scenario())


def test_untimed_fingerprint_free_evidence_still_resolves_and_privileged_transitions_stay_gated(pg):
    async def scenario():
        asset = await create_asset(pg)
        incident_id = await _incident_investigating(pg, asset)
        source = await _row(pg, asset, record_id="903")                # record id present, no timestamp: fingerprint, time missing
        evidence = await _attach_enriched(pg, incident_id, asset, source)
        assert evidence.time_confidence == "missing" and evidence.event_time is None
        for blocked in ("engineer", "demo", "shared-admin-token", "nobody"):
            with pytest.raises(Exception):
                await _resolve(pg, incident_id, evidence.evidence_id, verifier=blocked)
        assert await _counts(pg, incident_id) == (0, 0, "investigating")
        assert (await _resolve(pg, incident_id, evidence.evidence_id)).status == "resolved"

    asyncio.run(scenario())
