"""Evidence identity, idempotency and conservative correlation (real PostgreSQL, disposable database).

Policy under test (see backend/domain/incident/evidence_identity.py and service._assess_candidates):
* identity of an event occurrence is a fingerprint over provider/event/record id/time/channel/host/message, produced only
  when a record id or an event time exists; text alone is never an identity;
* the correlation key is provider-qualified (`<event id>@<provider>`);
* only a STRONG match (same concrete asset + same signature inside the window, open incident) merges automatically;
* weaker candidates are recorded as `ambiguous_not_merged`; resolved incidents are never merged into.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text

from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.incident.models import Incident, IncidentEvidence
from tests.incident_db_support import create_asset, session_factory
from tests.test_incident_workflow_records_pg import OPEN, _client, api  # noqa: F401

BASE = datetime.now(UTC).replace(microsecond=0)


async def hist(engine, event_id, provider, message="Application crashed", *, record_id=None, occurred=None,
               asset_id=None, computer="HOST-1", untimed=False, timezone=None):
    """One analysed record. Since correlation uses EVENT time only, rows carry an explicit UTC event timestamp unless
    ``untimed`` (the request's observed_at is never an event time)."""
    meta = {"sourceFamily": "windows_event", "computer": computer, "logName": "Application"}
    if record_id is not None:
        meta["record_id"] = record_id
    if occurred is None and not untimed:
        occurred = BASE.isoformat().replace("+00:00", "Z")
    if occurred is not None:
        meta["timestamp"] = occurred
    if timezone is not None:
        meta["timezone"] = timezone
    async with session_factory(engine)() as db:
        row = AnalysisHistory(event_id=event_id, provider=provider, username="demo", description=message,
                              solution_summary={}, event_metadata=meta, search_results=[], asset_id=asset_id)
        db.add(row)
        await db.commit()
        return row.id


def body(*history_ids, at=None, asset=None):
    when = (at or BASE).isoformat()
    payload = {"severity": "medium", "evidence": [
        {"source_type": "analysis", "source_id": str(h), "observed_at": when} for h in history_ids]}
    if asset:
        payload["asset_id"] = str(asset)
    return payload


async def post(client, payload):
    response = await client.post("/api/v1/incidents", json=payload, headers=OPEN)
    assert response.status_code == 201, response.text
    return response.json()


async def counts(engine):
    async with session_factory(engine)() as db:
        incidents = (await db.execute(select(func.count()).select_from(Incident))).scalar_one()
        evidence = (await db.execute(select(func.count()).select_from(IncidentEvidence))).scalar_one()
        digests = (await db.execute(select(func.count(func.distinct(IncidentEvidence.evidence_digest))))).scalar_one()
        return incidents, evidence, digests


def test_01_same_asset_provider_event_close_in_time_merges_strongly(api):
    app, asset, engine = api

    async def run():
        a = await hist(engine, "1026", ".NET Runtime", record_id="101")
        b = await hist(engine, "1026", ".NET Runtime", record_id="102")
        async with _client(app) as c:
            first = await post(c, body(a, asset=asset))
            second = await post(c, body(b, at=BASE + timedelta(seconds=60), asset=asset))
        assert (first["match"], second["match"]) == ("created", "correlated_with_open_incident")
        assert second["incident_id"] == first["incident_id"]
        assert await counts(engine) == (1, 2, 2)   # two distinct occurrences, both kept

    asyncio.run(run())


def test_02_same_asset_different_event_is_ambiguous_not_merged(api):
    app, asset, engine = api

    async def run():
        a = await hist(engine, "1000", "Application Error", record_id="1")
        b = await hist(engine, "7034", "Service Control Manager", record_id="2")
        async with _client(app) as c:
            first = await post(c, body(a, asset=asset))
            second = await post(c, body(b, at=BASE + timedelta(seconds=30), asset=asset))
        assert second["match"] == "ambiguous_not_merged" and second["incident_id"] != first["incident_id"]
        cand = second["summary"]["correlation"]["candidates"]
        assert [x["incident_id"] for x in cand] == [first["incident_id"]]
        assert "different_signature" in cand[0]["reasons"]

    asyncio.run(run())


def test_03_different_asset_same_signature_never_candidates(api):
    app, asset, engine = api

    async def run():
        other = await create_asset(engine, "other-host")
        a = await hist(engine, "1026", ".NET Runtime", record_id="1")
        b = await hist(engine, "1026", ".NET Runtime", record_id="2")
        async with _client(app) as c:
            first = await post(c, body(a, asset=asset))
            second = await post(c, body(b, at=BASE + timedelta(seconds=30), asset=other))
        assert second["match"] == "created" and second["incident_id"] != first["incident_id"]
        assert "candidates" not in second["summary"]["correlation"]

    asyncio.run(run())


def test_04_same_event_id_different_providers_are_not_the_same_signature(api):
    app, asset, engine = api

    async def run():
        a = await hist(engine, "1001", "Windows Error Reporting", record_id="1")
        b = await hist(engine, "1001", "Microsoft-Windows-WER-SystemErrorReporting", record_id="2")
        async with _client(app) as c:
            first = await post(c, body(a, asset=asset))
            second = await post(c, body(b, at=BASE + timedelta(seconds=30), asset=asset))
        assert second["incident_id"] != first["incident_id"]
        assert second["match"] == "ambiguous_not_merged"
        sigs = {first["summary"]["correlation"]["signature"], second["summary"]["correlation"]["signature"]}
        assert sigs == {"analysis:1001@windows error reporting",
                        "analysis:1001@microsoft-windows-wer-systemerrorreporting"}

    asyncio.run(run())


def test_05_same_provider_event_different_record_ids_are_distinct_occurrences(api):
    app, asset, engine = api

    async def run():
        ids = [await hist(engine, "1000", "Application Error", "identical message", record_id=str(r)) for r in (1, 2, 3)]
        async with _client(app) as c:
            results = [await post(c, body(h, at=BASE + timedelta(seconds=i), asset=asset)) for i, h in enumerate(ids)]
        assert len({r["incident_id"] for r in results}) == 1
        incidents, evidence, digests = await counts(engine)
        assert (incidents, evidence, digests) == (1, 3, 3), "identical text must not collapse distinct record ids"

    asyncio.run(run())


def test_06_missing_asset_never_merges_automatically(api):
    app, _asset, engine = api

    async def run():
        a = await hist(engine, "1026", ".NET Runtime", record_id="1")
        b = await hist(engine, "1026", ".NET Runtime", record_id="2")
        async with _client(app) as c:
            first = await post(c, body(a))
            second = await post(c, body(b, at=BASE + timedelta(seconds=30)))
        assert second["incident_id"] != first["incident_id"] and second["match"] == "ambiguous_not_merged"
        assert "asset_unresolved" in second["summary"]["correlation"]["candidates"][0]["reasons"]

    asyncio.run(run())


def test_07_missing_provider_does_not_match_a_provider_qualified_signature(api):
    app, asset, engine = api

    async def run():
        a = await hist(engine, "1026", ".NET Runtime", record_id="1")
        b = await hist(engine, "1026", "", record_id="2")
        async with _client(app) as c:
            first = await post(c, body(a, asset=asset))
            second = await post(c, body(b, at=BASE + timedelta(seconds=30), asset=asset))
        assert second["incident_id"] != first["incident_id"] and second["match"] == "ambiguous_not_merged"
        assert second["summary"]["correlation"]["signature"] == "analysis:1026"

    asyncio.run(run())


def test_08_no_record_id_and_no_event_time_produces_no_fingerprint(api):
    app, asset, engine = api

    async def run():
        a = await hist(engine, "1000", "Application Error", "same text", untimed=True)
        b = await hist(engine, "1000", "Application Error", "same text", untimed=True)
        async with _client(app) as c:
            first = await post(c, body(a, asset=asset))
            second = await post(c, body(b, at=BASE + timedelta(seconds=5), asset=asset))
        # Indistinguishable by text alone: no fingerprint (no record id, no event time). With no event time the two
        # are also NOT merged on ingestion proximity: separate incidents, the first listed as an ambiguous candidate.
        assert second["match"] == "ambiguous_not_merged"
        assert second["incident_id"] != first["incident_id"]
        assert await counts(engine) == (2, 2, 2)
        digests = {e["evidence_digest"] for e in second["evidence"]}
        assert len(digests) == 1 and all(len(d) == 64 for d in digests)
        async with session_factory(engine)() as db:
            rows = (await db.execute(select(IncidentEvidence))).scalars().all()
        assert {r.time_confidence for r in rows} == {"missing"} and all(r.event_time is None for r in rows)

    asyncio.run(run())


def test_09_out_of_order_evidence_extends_the_window_backwards(api):
    app, asset, engine = api

    async def run():
        late = await hist(engine, "1026", ".NET Runtime", record_id="20")
        early = await hist(engine, "1026", ".NET Runtime", record_id="10",
                           occurred=(BASE - timedelta(seconds=120)).isoformat().replace("+00:00", "Z"))
        async with _client(app) as c:
            first = await post(c, body(late, at=BASE, asset=asset))
            second = await post(c, body(early, at=BASE - timedelta(seconds=120), asset=asset))
        assert second["incident_id"] == first["incident_id"]
        assert datetime.fromisoformat(second["first_seen"]) == BASE - timedelta(seconds=120)
        assert datetime.fromisoformat(second["last_seen"]) == BASE

    asyncio.run(run())


def test_10_same_evidence_repeated_is_idempotent_by_source_and_by_occurrence(api):
    app, asset, engine = api

    async def run():
        a = await hist(engine, "1026", ".NET Runtime", "crash", record_id="77", occurred="2026-11-20T01:02:03Z")
        again = await hist(engine, "1026", ".NET Runtime", "crash", record_id="77", occurred="2026-11-20T01:02:03Z")
        async with _client(app) as c:
            first = await post(c, body(a, asset=asset))
            same_source = await post(c, body(a, asset=asset))
            same_event_other_row = await post(c, body(again, asset=asset))
        assert same_source["match"] == "event_already_linked" and same_source["incident_id"] == first["incident_id"]
        assert same_event_other_row["match"] == "event_already_linked"
        assert same_event_other_row["incident_id"] == first["incident_id"]
        incidents, evidence, digests = await counts(engine)
        assert incidents == 1 and digests == 1, "one occurrence = one fingerprint, however many times it is submitted"

    asyncio.run(run())


def test_11_resolved_incident_is_never_merged_into(api):
    app, asset, engine = api

    async def run():
        a = await hist(engine, "1026", ".NET Runtime", record_id="1")
        b = await hist(engine, "1026", ".NET Runtime", record_id="2")
        async with _client(app) as c:
            first = await post(c, body(a, asset=asset))
            async with session_factory(engine)() as db:
                await db.execute(text("ALTER TABLE incidents DISABLE TRIGGER USER"))
                await db.execute(text("UPDATE incidents SET status='resolved' WHERE incident_id=:i"),
                                 {"i": first["incident_id"]})
                await db.execute(text("ALTER TABLE incidents ENABLE TRIGGER USER"))
                await db.commit()
            second = await post(c, body(b, at=BASE + timedelta(seconds=60), asset=asset))
        assert second["incident_id"] != first["incident_id"] and second["created"] is True

    asyncio.run(run())


def test_12_multiple_related_events_submitted_together_share_one_incident(api):
    app, asset, engine = api

    async def run():
        ids = [await hist(engine, ev, prov, record_id=str(i)) for i, (ev, prov) in enumerate(
            [("1000", "Application Error"), ("1026", ".NET Runtime"), ("1001", "Windows Error Reporting")])]
        async with _client(app) as c:
            made = await post(c, body(*ids, asset=asset))
        assert made["created"] is True and len(made["evidence"]) == 3
        assert await counts(engine) == (1, 3, 3)

    asyncio.run(run())


def test_13_similar_messages_on_different_assets_and_records_stay_separate(api):
    app, asset, engine = api

    async def run():
        other = await create_asset(engine, "similar-host")
        a = await hist(engine, "1000", "Application Error", "faulting module x.dll", record_id="5")
        b = await hist(engine, "1000", "Application Error", "faulting module x.dll", record_id="6")
        async with _client(app) as c:
            r1 = await post(c, body(a, asset=asset))
            r2 = await post(c, body(b, asset=other))
        assert r1["incident_id"] != r2["incident_id"]
        assert await counts(engine) == (2, 2, 2)

    asyncio.run(run())


def test_14_occurrence_fingerprint_is_recomputable_for_verification(api):
    """Regression found by the end-to-end run: verification recomputes evidence digests server-side, so evidence that
    carries an occurrence fingerprint must still verify, and a tampered digest must not."""
    from backend.domain.incident.verification import _matches_occurrence_fingerprint, recompute_evidence_digest

    app, asset, engine = api

    async def run():
        with_id = await hist(engine, "1026", ".NET Runtime", record_id="55")
        bare = await hist(engine, "1026", ".NET Runtime", untimed=True)
        async with _client(app) as c:
            made = await post(c, body(with_id, bare, asset=asset))
        async with session_factory(engine)() as db:
            rows = {r.source_id: r for r in (await db.execute(select(IncidentEvidence))).scalars().all()}
            fingerprinted, source_only = rows[str(with_id)], rows[str(bare)]
            assert fingerprinted.evidence_digest != recompute_evidence_digest(fingerprinted)   # content-based identity
            assert await _matches_occurrence_fingerprint(db, fingerprinted) is True
            assert source_only.evidence_digest == recompute_evidence_digest(source_only)      # no fingerprint: unchanged
            assert await _matches_occurrence_fingerprint(db, source_only) is False
            fingerprinted.evidence_digest = "0" * 64                                         # tampering is still detected
            assert await _matches_occurrence_fingerprint(db, fingerprinted) is False
        assert made["created"] is True

    asyncio.run(run())
