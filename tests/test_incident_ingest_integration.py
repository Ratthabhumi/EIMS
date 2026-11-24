"""Incident Core v1.1 ingestion against the dedicated disposable PostgreSQL + Redis (synthetic data only).

Skipped unless EIMS_INGEST_TEST_DATABASE_URL / EIMS_INGEST_TEST_REDIS_URL / EIMS_INGEST_TEST_SENTINEL
identify the NEW disposable services (tests/incident_ingest_support.py verifies identity before any DDL).
Every test uses a unique retained schema and a unique Redis key namespace; nothing is dropped or flushed.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.asset_registry.models import AuditLog
from backend.domain.incident.models import Incident, IncidentEvidence
from backend.domain.incident.service import ACTION_INCIDENT_CREATED
from backend.domain.incident_ingest import consumer as consumer_mod
from backend.domain.incident_ingest import dispatcher as dispatcher_mod
from backend.domain.incident_ingest.models import IncidentIngestOutbox
from backend.domain.incident_ingest.outbox import (
    OutboxItem, enqueue_analysis_history, enqueue_incident_ingest, winlog_items_from_returned,
)
from backend.domain.telemetry.models import TelemetryMetric, WindowsEventLog
from backend.domain.telemetry.worker import TelemetryStreamConsumer
from tests.incident_db_support import create_asset
from tests.incident_ingest_support import (
    create_ingest_schema, redis_client, require_pg_url, require_redis_url, session_factory,
)

NOW = datetime(2026, 11, 16, 1, 2, 3, tzinfo=UTC)


@pytest.fixture
async def env(monkeypatch):
    pg_url, redis_url = require_pg_url(), require_redis_url()
    schema, engine = await create_ingest_schema(pg_url)
    async with redis_client(redis_url) as client:
        suffix = uuid.uuid4().hex[:10]
        keys = {"stream": f"eims:jobs:incident-ingest-it-{suffix}:stream",
                "group": f"eims:jobs:incident-ingest-it-{suffix}:workers",
                "dlq": f"eims:jobs:incident-ingest-it-{suffix}:dead-letter"}
        for module in (dispatcher_mod, consumer_mod):
            monkeypatch.setattr(module, "INGEST_STREAM_KEY", keys["stream"])
        monkeypatch.setattr(consumer_mod, "INGEST_GROUP", keys["group"])
        monkeypatch.setattr(consumer_mod, "INGEST_DEAD_LETTER_KEY", keys["dlq"])
        yield SimpleNamespace(engine=engine, maker=session_factory(engine), redis=client, **keys)
    await engine.dispose()


def make_consumer(env, **kw):
    options = dict(redis_provider=lambda: env.redis, session_maker_provider=lambda: env.maker,
                   reclaim_idle_ms=0, max_delivery_attempts=3, polling_interval=0.05)
    options.update(kw)
    return consumer_mod.IncidentIngestConsumer(**options)


async def count(env, model, *where):
    async with env.maker() as s:
        return await s.scalar(select(func.count()).select_from(model).where(*where))


async def add_outbox(env, source_id=None, *, asset_id=None, source_type="winlog", key=None, observed=NOW):
    source_id = source_id or str(uuid.uuid4())
    async with env.maker() as s:
        async with s.begin():
            await enqueue_incident_ingest(s, [OutboxItem(source_type, source_id, observed,
                                                         source_event_key=key, asset_id=asset_id)])
    return source_id


def winlog_row(asset_id, severity="Warning", key=None):
    return WindowsEventLog(log_id=uuid.uuid4(), asset_id=asset_id, occurrence_time=NOW, event_id=4625,
                           severity_level=severity, evtx_metadata={}, source_event_key=key)


# ------------------------------------------------------------------ source + outbox atomicity
async def test_source_and_outbox_commit_together_or_not_at_all(env):
    asset = await create_asset(env.engine)
    for fail in (True, False):
        row = winlog_row(asset)
        async with env.maker() as s:
            try:
                async with s.begin():
                    s.add(row)
                    await s.flush()
                    await enqueue_incident_ingest(s, [OutboxItem("winlog", str(row.log_id), NOW, asset_id=asset)])
                    if fail:
                        raise RuntimeError("forced failure after flush")
            except RuntimeError:
                pass
        expected = 0 if fail else 1
        assert await count(env, WindowsEventLog, WindowsEventLog.log_id == row.log_id) == expected
        assert await count(env, IncidentIngestOutbox, IncidentIngestOutbox.source_id == str(row.log_id)) == expected


async def test_returning_suppresses_replay_so_transient_pk_never_becomes_identity(env):
    asset = await create_asset(env.engine)

    def values(row):
        return [{"log_id": row.log_id, "asset_id": asset, "occurrence_time": NOW, "event_id": 4625,
                 "severity_level": "Warning", "evtx_metadata": {}, "source_event_key": "evtx:same"}]

    first, replay = winlog_row(asset), winlog_row(asset)
    for attempt in (first, replay):
        async with env.maker() as s:
            async with s.begin():
                inserted = await TelemetryStreamConsumer._insert_rows(s, WindowsEventLog, values(attempt))
                await enqueue_incident_ingest(s, winlog_items_from_returned(inserted, origin="telemetry_worker"))
    async with env.maker() as s:
        ids = (await s.execute(select(IncidentIngestOutbox.source_id))).scalars().all()
    assert ids == [str(first.log_id)] and str(replay.log_id) not in ids


async def test_persist_batch_emits_only_new_qualifying_winlogs_never_heartbeats(env):
    asset = await create_asset(env.engine)
    worker = TelemetryStreamConsumer()
    metric = TelemetryMetric(metric_id=uuid.uuid4(), asset_id=asset, event_time=NOW, cpu_utilization=1.0,
                             diagnostic_payload={}, source_event_key="hb-1")
    logs = [winlog_row(asset, "Error", "k-error"), winlog_row(asset, "Information", "k-info"),
            winlog_row(asset, "Critical", "k-crit")]
    await worker._persist_batch(env.maker, [metric], logs)
    await worker._persist_batch(env.maker, [metric], [winlog_row(asset, "Error", "k-error")])  # replay
    async with env.maker() as s:
        rows = (await s.execute(select(IncidentIngestOutbox))).scalars().all()
    persisted = {str(r.log_id) for r in (await _all(env, WindowsEventLog))}
    assert len(rows) == 2 and {r.source_id for r in rows} <= persisted
    assert {r.source_event_key for r in rows} == {"k-error", "k-crit"} and all(r.asset_id == asset for r in rows)


async def _all(env, model):
    async with env.maker() as s:
        return (await s.execute(select(model))).scalars().all()


# ------------------------------------------------------------------ dispatcher
async def test_dispatch_crash_between_xadd_and_stamp_republishes_and_yields_one_evidence(env):
    asset = await create_asset(env.engine)
    source_id = await add_outbox(env, asset_id=asset)

    class CrashOnStamp:
        calls = 0

        def __call__(self):
            CrashOnStamp.calls += 1
            if CrashOnStamp.calls == 2:  # claim is call 1, stamp is call 2
                raise RuntimeError("crash after XADD, before stamp")
            return env.maker()

    with pytest.raises(RuntimeError):
        await dispatcher_mod.dispatch_pending(CrashOnStamp(), env.redis)
    assert await env.redis.xlen(env.stream) == 1
    assert await count(env, IncidentIngestOutbox, IncidentIngestOutbox.published_at.is_(None)) == 1
    assert await dispatcher_mod.dispatch_pending(env.maker, env.redis) == 1
    assert await env.redis.xlen(env.stream) == 2  # at-least-once republish

    consumer = make_consumer(env)
    await consumer.process_batch()
    assert await count(env, IncidentEvidence, IncidentEvidence.source_id == source_id) == 1
    assert await count(env, AuditLog, AuditLog.action_verb == ACTION_INCIDENT_CREATED) == 1
    assert consumer.metrics["incidents_created"] == 1 and consumer.metrics["incidents_reused"] == 1


async def test_two_concurrent_dispatchers_never_lose_or_unstamp_rows(env):
    asset = await create_asset(env.engine)
    for _ in range(6):
        await add_outbox(env, asset_id=asset)
    await asyncio.gather(dispatcher_mod.dispatch_pending(env.maker, env.redis),
                         dispatcher_mod.dispatch_pending(env.maker, env.redis))
    assert await count(env, IncidentIngestOutbox, IncidentIngestOutbox.published_at.is_(None)) == 0
    assert await env.redis.xlen(env.stream) >= 6


# ------------------------------------------------------------------ consumer
async def test_commit_before_ack_crash_is_absorbed_by_redelivery(env):
    asset = await create_asset(env.engine)
    source_id = await add_outbox(env, asset_id=asset)
    await dispatcher_mod.dispatch_pending(env.maker, env.redis)
    consumer = make_consumer(env)

    async def lost_ack(client, message_id):
        return False  # process died after the incident commit, before XACK

    real_ack, consumer._ack = consumer._ack, lost_ack
    await consumer.process_batch()
    assert await count(env, IncidentEvidence, IncidentEvidence.source_id == source_id) == 1
    assert (await env.redis.xpending(env.stream, env.group))["pending"] == 1
    consumer._ack = real_ack
    await consumer.process_batch()
    assert (await env.redis.xpending(env.stream, env.group))["pending"] == 0
    assert await count(env, IncidentEvidence) == 1
    assert await count(env, AuditLog, AuditLog.action_verb == ACTION_INCIDENT_CREATED) == 1
    assert consumer.metrics["incidents_reused"] == 1


async def test_transient_db_outage_never_acks_or_dead_letters(env):
    asset = await create_asset(env.engine)
    await add_outbox(env, asset_id=asset)
    await dispatcher_mod.dispatch_pending(env.maker, env.redis)

    def down():
        raise OperationalError("SELECT", {}, Exception("synthetic outage"))

    outage = make_consumer(env, session_maker_provider=lambda: down)
    for _ in range(6):  # past the poison cap
        await outage.process_batch()
    assert (await env.redis.xpending(env.stream, env.group))["pending"] == 1
    assert await env.redis.xlen(env.dlq) == 0
    healthy = make_consumer(env)
    await healthy.process_batch()  # recovery processes it
    assert (await env.redis.xpending(env.stream, env.group))["pending"] == 0
    assert await count(env, IncidentEvidence) == 1


async def test_poison_goes_to_dlq_after_cap_while_valid_sibling_succeeds(env):
    asset = await create_asset(env.engine)
    good = await add_outbox(env, asset_id=asset)
    await dispatcher_mod.dispatch_pending(env.maker, env.redis)
    ghost = str(uuid.uuid4())  # asset that is not registered -> IncidentValidationError (deterministic)
    await env.redis.xadd(env.stream, {
        "outbox_id": str(uuid.uuid4()), "source_type": "winlog", "source_id": str(uuid.uuid4()),
        "observed_at": NOW.isoformat(), "asset_id": ghost, "provenance": "{}"})
    consumer = make_consumer(env)
    for _ in range(3):
        await consumer.process_batch()
    assert await count(env, IncidentEvidence, IncidentEvidence.source_id == good) == 1
    entries = await env.redis.xrange(env.dlq)
    assert len(entries) == 1
    fields = {k.decode(): v.decode() for k, v in entries[0][1].items()}
    assert fields["reason"] == "incident-validation-rejected" and int(fields["deliveries"]) >= 3
    assert (await env.redis.xpending(env.stream, env.group))["pending"] == 0


async def test_lease_refresh_does_not_inflate_delivery_count(env):
    asset = await create_asset(env.engine)
    await add_outbox(env, asset_id=asset)
    await dispatcher_mod.dispatch_pending(env.maker, env.redis)
    consumer = make_consumer(env, reclaim_idle_ms=150)
    messages = await consumer._fetch(env.redis)
    ids = {mid for mid, _ in messages}
    task = asyncio.create_task(consumer._refresh_loop(env.redis, ids))
    await asyncio.sleep(0.4)  # several refresh ticks
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    (entry,) = await env.redis.xpending_range(env.stream, env.group, min="-", max="+", count=10)
    assert entry["times_delivered"] == 1


async def test_cross_asset_isolation_same_event_key_two_assets(env):
    one, two = await create_asset(env.engine, "host-one"), await create_asset(env.engine, "host-two")
    await add_outbox(env, asset_id=one, key="same-signature")
    await add_outbox(env, asset_id=two, key="same-signature")
    await dispatcher_mod.dispatch_pending(env.maker, env.redis)
    await make_consumer(env).process_batch()
    async with env.maker() as s:
        assets = (await s.execute(select(Incident.asset_id))).scalars().all()
    assert sorted(map(str, assets)) == sorted(map(str, [one, two]))


async def test_null_key_rows_and_naive_analysis_timestamp(env):
    asset = await create_asset(env.engine)
    await add_outbox(env, asset_id=asset, key=None)
    await add_outbox(env, asset_id=asset, key=None)  # two NULL source_event_keys are accepted
    assert await count(env, IncidentIngestOutbox, IncidentIngestOutbox.source_event_key.is_(None)) == 2
    async with env.maker() as s:
        async with s.begin():
            history = AnalysisHistory(event_id="4625", provider="synthetic", username="synthetic")
            s.add(history)
            await enqueue_analysis_history(s, history, origin="analyzer_submit")
    async with env.maker() as s:
        row = (await s.execute(select(IncidentIngestOutbox).where(
            IncidentIngestOutbox.source_type == "analysis"))).scalar_one()
    assert row.asset_id is None and row.observed_at.tzinfo is not None
    assert abs(row.observed_at - datetime.now(UTC)) < timedelta(minutes=5)


async def test_analysis_without_asset_stays_unresolved_and_offline_keeps_explicit_asset(env):
    asset = await create_asset(env.engine)
    async with env.maker() as s:
        async with s.begin():
            plain = AnalysisHistory(event_id="1", provider="p", username="synthetic")
            offline = AnalysisHistory(event_id="2", provider="p", username="system", asset_id=asset)
            s.add_all([plain, offline])
            await enqueue_analysis_history(s, plain, origin="analyzer_submit")
            await enqueue_analysis_history(s, offline, origin="offline_import", asset_id=asset)
    await dispatcher_mod.dispatch_pending(env.maker, env.redis)
    await make_consumer(env).process_batch()
    async with env.maker() as s:
        by_source = {e.source_id: e for e in (await s.execute(select(IncidentEvidence))).scalars().all()}
        incidents = {i.incident_id: i for i in (await s.execute(select(Incident))).scalars().all()}
    assert incidents[by_source[str(plain.id)].incident_id].asset_id is None
    assert incidents[by_source[str(offline.id)].incident_id].asset_id == asset


async def test_two_consumers_racing_on_duplicate_entries_yield_one_incident(env):
    asset = await create_asset(env.engine)
    source_id = await add_outbox(env, asset_id=asset)
    await dispatcher_mod.dispatch_pending(env.maker, env.redis)
    await dispatcher_mod.dispatch_pending(env.maker, env.redis)  # row already stamped -> no dup
    row = (await _all(env, IncidentIngestOutbox))[0]
    for _ in range(3):  # force duplicate stream entries for the same source identity
        await env.redis.xadd(env.stream, {
            "outbox_id": str(row.outbox_id), "source_type": "winlog", "source_id": source_id,
            "observed_at": NOW.isoformat(), "asset_id": str(asset), "provenance": "{}"})
    first, second = make_consumer(env, concurrency=4), make_consumer(env, concurrency=4)
    await asyncio.gather(first.process_batch(), second.process_batch())
    await asyncio.gather(first.process_batch(), second.process_batch())
    assert await count(env, IncidentEvidence, IncidentEvidence.source_id == source_id) == 1
    assert await count(env, Incident) == 1


# ------------------------------------------------------------------ schema constraints
async def test_outbox_constraints_reject_bad_source_type_oversize_provenance_and_duplicates(env):
    asset = await create_asset(env.engine)
    base = dict(source_id="s1", observed_at=NOW, asset_id=asset)
    async with env.maker() as s:
        s.add(IncidentIngestOutbox(source_type="telemetry", **base))
        with pytest.raises(IntegrityError):
            await s.commit()
    async with env.maker() as s:
        s.add(IncidentIngestOutbox(source_type="winlog", provenance={"origin": "x" * 2000}, **base))
        with pytest.raises(DBAPIError):
            await s.commit()
    await add_outbox(env, "dup-1", asset_id=asset)
    await add_outbox(env, "dup-1", asset_id=asset)  # ON CONFLICT DO NOTHING absorbs the duplicate
    assert await count(env, IncidentIngestOutbox, IncidentIngestOutbox.source_id == "dup-1") == 1
    async with env.maker() as s:
        s.add(IncidentIngestOutbox(source_type="winlog", source_id="x", observed_at=NOW,
                                   asset_id=uuid.uuid4()))
        with pytest.raises(IntegrityError):  # asset FK
            await s.commit()
