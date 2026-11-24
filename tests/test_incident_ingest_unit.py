"""Hermetic tests for Incident Core v1.1 ingestion (no database, no Redis, no network).

Covers envelope validation, severity/identity policy, emitter wiring, dispatcher ordering,
consumer ACK/retry/DLQ contracts and static migration/model parity with synthetic fakes only.
Real-transaction and real-Redis behaviour is covered by tests/test_incident_ingest_integration.py
(skipped unless the dedicated disposable services are configured).
"""
from __future__ import annotations

import asyncio
import importlib
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import DataError, IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.incident.service import IncidentConflict, IncidentValidationError
from backend.domain.incident_ingest import consumer as consumer_mod
from backend.domain.incident_ingest import dispatcher as dispatcher_mod
from backend.domain.incident_ingest import outbox as outbox_mod
from backend.domain.incident_ingest.envelope import (
    INGEST_ACTOR, INGEST_DEAD_LETTER_KEY, INGEST_STREAM_KEY, EnvelopeError, IngestEnvelope,
    qualifies_winlog_severity, sanitize_provenance,
)
from backend.domain.incident_ingest.models import IncidentIngestOutbox
from backend.domain.telemetry import worker as worker_module
from backend.domain.telemetry.broker import StubTelemetryStreamBroker
from backend.domain.telemetry.models import TelemetryMetric, WindowsEventLog
from backend.domain.telemetry.worker import TelemetryStreamConsumer

P = importlib.import_module("backend.domain.analyzer.services.import_pipeline")
ASSET = uuid.UUID("11111111-1111-4111-8111-111111111111")
OTHER_ASSET = uuid.UUID("22222222-2222-4222-8222-222222222222")
NOW = datetime(2026, 11, 16, 1, 2, 3, tzinfo=UTC)
MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def _fields(**over):
    base = {"outbox_id": str(uuid.uuid4()), "source_type": "winlog", "source_id": str(uuid.uuid4()),
            "observed_at": NOW.isoformat(), "provenance": "{}"}
    base.update(over)
    return base


def _row_params(statement):
    """Single-row multi-VALUES params with the _m0 suffix removed."""
    params = statement.compile(dialect=postgresql.dialect()).params
    return {re.sub(r"_m0$", "", key): value for key, value in params.items()}


# --------------------------------------------------------------------------- envelope / policy
class TestEnvelope:
    def test_roundtrip_with_null_event_key_and_null_asset(self):
        env = IngestEnvelope(outbox_id=uuid.uuid4(), source_type="analysis", source_id="42", observed_at=NOW)
        parsed = IngestEnvelope.from_stream_fields(env.to_stream_fields())
        assert parsed == env and parsed.source_event_key is None and parsed.asset_id is None

    def test_roundtrip_preserves_event_key_and_asset(self):
        env = IngestEnvelope(outbox_id=uuid.uuid4(), source_type="winlog", source_id=str(uuid.uuid4()),
                             observed_at=NOW, source_event_key="evtx:abc", asset_id=ASSET,
                             provenance={"origin": "telemetry_worker", "event_id": 4625})
        assert IngestEnvelope.from_stream_fields(env.to_stream_fields()) == env

    @pytest.mark.parametrize("over", [
        {"source_type": "telemetry"}, {"source_type": "audit"}, {"source_id": ""}, {"source_id": "x" * 65},
        {"source_event_key": "k" * 161}, {"observed_at": "2026-11-16T01:02:03"}, {"observed_at": "garbage"},
        {"outbox_id": "not-a-uuid"}, {"asset_id": "not-a-uuid"}, {"provenance": "[1]"}, {"provenance": "{"},
        {"source_id": "y" * 5000},
    ])
    def test_invalid_envelopes_are_rejected(self, over):
        with pytest.raises(EnvelopeError):
            IngestEnvelope.from_stream_fields(_fields(**over))

    def test_provenance_is_allow_listed_scalars_only(self):
        clean = sanitize_provenance({"origin": "x", "event_id": 7, "raw_log": "SECRET TEXT", "nested": {"a": 1},
                                     "severity": "Error", "flag": True})
        assert clean == {"origin": "x", "event_id": 7, "severity": "Error"}
        assert len(sanitize_provenance({"origin": "o" * 500})["origin"]) == 64

    @pytest.mark.parametrize("severity,expected", [
        ("Critical", True), ("error", True), (" Warning ", True), ("Information", False),
        ("Verbose", False), ("LogAlways", False), ("Unknown", False), (None, False)])
    def test_winlog_severity_policy(self, severity, expected):
        assert qualifies_winlog_severity(severity) is expected

    def test_stream_keys_use_approved_namespace_and_do_not_touch_alert_channel(self):
        assert INGEST_STREAM_KEY.startswith("eims:jobs:") and INGEST_DEAD_LETTER_KEY.startswith("eims:jobs:")
        assert not INGEST_STREAM_KEY.startswith("eims:events:alerts")
        assert INGEST_ACTOR == "system:incident-ingest"


# --------------------------------------------------------------------------- emission helpers
class TestOutboxHelpers:
    def test_only_returned_rows_become_items_and_info_is_filtered(self):
        returned = [
            (uuid.uuid4(), ASSET, NOW, "Warning", 4625, "k1"),
            (uuid.uuid4(), ASSET, NOW, "Information", 6005, "k2"),
            (uuid.uuid4(), ASSET, NOW, "Critical", 41, "k3")]
        items = outbox_mod.winlog_items_from_returned(returned, origin="telemetry_worker")
        assert [i.source_id for i in items] == [str(returned[0][0]), str(returned[2][0])]
        assert all(i.source_type == "winlog" and i.asset_id == ASSET for i in items)
        assert outbox_mod.winlog_items_from_returned([], origin="telemetry_worker") == []  # replay: nothing returned

    async def test_enqueue_is_idempotent_insert_with_utc_and_null_key(self):
        session = MagicMock()
        session.execute = AsyncMock()
        naive = datetime(2026, 11, 16, 1, 2, 3)  # legacy UTC-naive analysis_history.created_at
        count = await outbox_mod.enqueue_incident_ingest(session, [
            outbox_mod.OutboxItem("analysis", "9", naive, provenance={"origin": "o", "raw": "drop"})])
        assert count == 1
        stmt = session.execute.await_args.args[0]
        assert "ON CONFLICT (source_type, source_id) DO NOTHING" in str(stmt.compile(dialect=postgresql.dialect()))
        row = _row_params(stmt)
        assert row["observed_at"].tzinfo is not None and row["observed_at"].hour == 1
        assert row["source_event_key"] is None and row["asset_id"] is None
        assert row["provenance"] == {"origin": "o"}

    async def test_enqueue_empty_does_not_touch_the_session(self):
        session = MagicMock()
        session.execute = AsyncMock()
        assert await outbox_mod.enqueue_incident_ingest(session, []) == 0
        session.execute.assert_not_awaited()

    async def test_oversized_source_id_is_rejected_before_any_write(self):
        session = MagicMock()
        session.execute = AsyncMock()
        # F2: an invalid item is skipped + counted; it must never raise into the source transaction.
        before = outbox_mod.metrics["invalid_items_skipped"]
        assert await outbox_mod.enqueue_incident_ingest(
            session, [outbox_mod.OutboxItem("winlog", "z" * 65, NOW)]) == 0
        assert outbox_mod.metrics["invalid_items_skipped"] == before + 1
        session.execute.assert_not_awaited()

    async def test_analysis_history_uses_actual_persisted_id_and_never_infers_asset(self):
        db = MagicMock(spec=AsyncSession)
        db.flush, db.execute = AsyncMock(), AsyncMock()
        history = SimpleNamespace(id=7, created_at=datetime(2026, 11, 16, 1, 2, 3), event_id="4625")
        await outbox_mod.enqueue_analysis_history(db, history, origin="analyzer_submit")
        db.flush.assert_awaited_once()
        row = _row_params(db.execute.await_args.args[0])
        assert row["source_type"] == "analysis" and row["source_id"] == "7" and row["asset_id"] is None
        assert row["provenance"] == {"origin": "analyzer_submit", "event_id": "4625"}

    async def test_offline_analysis_carries_explicit_asset(self):
        db = MagicMock(spec=AsyncSession)
        db.flush, db.execute = AsyncMock(), AsyncMock()
        history = SimpleNamespace(id=8, created_at=datetime(2026, 11, 16), event_id="1")
        await outbox_mod.enqueue_analysis_history(db, history, origin="offline_import", asset_id=ASSET)
        assert _row_params(db.execute.await_args.args[0])["asset_id"] == ASSET

    async def test_unpopulated_history_id_is_counted_and_logged_never_raised(self):
        db = MagicMock(spec=AsyncSession)
        db.flush, db.execute = AsyncMock(), AsyncMock()
        before = outbox_mod.metrics["invalid_items_skipped"]
        assert await outbox_mod.enqueue_analysis_history(
            db, SimpleNamespace(id=None, created_at=NOW, event_id="1"), origin="analyzer_submit") == 0
        assert outbox_mod.metrics["invalid_items_skipped"] == before + 1
        db.execute.assert_not_awaited()

    async def test_non_orm_session_doubles_are_skipped(self):
        class Sink:
            pass
        before = outbox_mod.metrics["unsupported_session_skips"]
        assert await outbox_mod.enqueue_analysis_history(
            Sink(), SimpleNamespace(id=None, created_at=None, event_id="1"), origin="analyzer_submit") == 0
        assert outbox_mod.metrics["unsupported_session_skips"] == before + 1  # F9: observable, not silent

    def test_offline_asset_is_never_inferred(self):
        assert P._verified_asset_uuid(ASSET) == ASSET
        assert P._verified_asset_uuid("EIMS-2026-0001") is None
        assert P._verified_asset_uuid("workstation-01") is None
        assert P._verified_asset_uuid(None) is None

    def test_nudge_never_raises(self):
        calls = []

        def good():
            calls.append(1)

        def bad():
            raise RuntimeError("boom")

        outbox_mod.register_wakeup(bad)
        outbox_mod.register_wakeup(good)
        try:
            outbox_mod.nudge_dispatch()
        finally:
            outbox_mod.unregister_wakeup(bad)
            outbox_mod.unregister_wakeup(good)
        assert calls == [1]


# --------------------------------------------------------------------------- telemetry emitter wiring
class _Tx:
    def __init__(self, log):
        self.log = log

    async def __aenter__(self):
        self.log.append("begin")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.log.append("rollback" if exc_type else "commit")
        return False


class _Session:
    def __init__(self, log):
        self.log = log

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def begin(self):
        return _Tx(self.log)


def _winlog(severity="Warning", key="k"):
    return SimpleNamespace(log_id=uuid.uuid4(), asset_id=ASSET, occurrence_time=NOW, event_id=4625,
                           severity_level=severity, evtx_metadata={}, source_event_key=key)


def _metric():
    return SimpleNamespace(metric_id=uuid.uuid4(), asset_id=ASSET, event_time=NOW, cpu_utilization=1.0,
                           diagnostic_payload={}, source_event_key="hb")


def _worker(monkeypatch, log, inserted):
    consumer = TelemetryStreamConsumer(broker=StubTelemetryStreamBroker())

    async def insert_rows(session, model, rows):
        log.append(f"insert:{model.__name__}")
        return inserted if model is WindowsEventLog else []

    async def enqueue(session, items):
        items = list(items)
        log.append(f"enqueue:{len(items)}")
        consumer.enqueued = items
        return len(items)

    def nudge():
        log.append("nudge")

    consumer._insert_rows = insert_rows
    consumer._detect_brute_force = AsyncMock(return_value=[])
    consumer._ensure_redis = AsyncMock(side_effect=AssertionError("worker must not touch Redis for incident dispatch"))
    monkeypatch.setattr(worker_module, "enqueue_incident_ingest", enqueue)
    monkeypatch.setattr(worker_module, "nudge_dispatch", nudge)
    # F3: the worker has no dispatch entry point any more (single dispatch owner = consumer).
    assert not hasattr(worker_module, "dispatch_pending_safely")
    consumer.enqueued = []
    return consumer


class TestTelemetryEmission:
    async def test_only_qualifying_returned_winlogs_emit_and_dispatch_follows_commit(self, monkeypatch):
        log: list[str] = []
        returned = [(uuid.uuid4(), ASSET, NOW, "Error", 4625, "a"),
                    (uuid.uuid4(), ASSET, NOW, "Information", 6005, "b")]
        consumer = _worker(monkeypatch, log, returned)
        await consumer._persist_batch(lambda: _Session(log), [_metric()], [_winlog(), _winlog("Information", "b")])
        assert [i.source_id for i in consumer.enqueued] == [str(returned[0][0])]
        assert log == ["begin", "insert:TelemetryMetric", "insert:WindowsEventLog", "enqueue:1", "commit", "nudge"]

    async def test_replay_returns_nothing_so_nothing_is_enqueued_or_dispatched(self, monkeypatch):
        log: list[str] = []
        consumer = _worker(monkeypatch, log, [])
        await consumer._persist_batch(lambda: _Session(log), [], [_winlog()])
        assert consumer.enqueued == [] and "nudge" not in log

    async def test_heartbeat_only_batch_never_emits(self, monkeypatch):
        log: list[str] = []
        consumer = _worker(monkeypatch, log, [])
        await consumer._persist_batch(lambda: _Session(log), [_metric()], [])
        assert log == ["begin", "insert:TelemetryMetric", "commit"]

    async def test_source_rollback_means_no_dispatch(self, monkeypatch):
        log: list[str] = []
        consumer = _worker(monkeypatch, log, [(uuid.uuid4(), ASSET, NOW, "Error", 1, "a")])
        consumer._detect_brute_force = AsyncMock(side_effect=OperationalError("x", {}, Exception("db")))
        with pytest.raises(OperationalError):
            await consumer._persist_batch(lambda: _Session(log), [], [_winlog()])
        assert log[-1] == "rollback" and "nudge" not in log and "commit" not in log

    async def test_nudge_failure_never_fails_source_ingestion(self, monkeypatch):
        """F3: nudge_dispatch swallows hook errors; a raising hook cannot fail source ingestion."""
        log: list[str] = []
        consumer = _worker(monkeypatch, log, [(uuid.uuid4(), ASSET, NOW, "Error", 1, "a")])
        monkeypatch.setattr(worker_module, "nudge_dispatch", outbox_mod.nudge_dispatch)

        def boom():
            raise RuntimeError("hook down")

        outbox_mod.register_wakeup(boom)
        try:
            await consumer._persist_batch(lambda: _Session(log), [], [_winlog()])  # must not raise
        finally:
            outbox_mod.unregister_wakeup(boom)
        assert log[-1] == "commit"

    async def test_insert_rows_statement_conflicts_silently_and_returns_only_winlogs(self):
        executed = []

        class Result:
            def all(self):
                return ["row"]

        class Sess:
            async def execute(self, stmt):
                executed.append(stmt)
                return Result()

        winlog_rows = [{"log_id": uuid.uuid4(), "asset_id": ASSET, "occurrence_time": NOW, "event_id": 1,
                        "severity_level": "Error", "evtx_metadata": {}, "source_event_key": "k"}]
        assert await TelemetryStreamConsumer._insert_rows(Sess(), WindowsEventLog, winlog_rows) == ["row"]
        sql = str(executed[0].compile(dialect=postgresql.dialect()))
        assert "ON CONFLICT (source_event_key) DO NOTHING" in sql and "RETURNING" in sql
        metric_rows = [{"metric_id": uuid.uuid4(), "asset_id": ASSET, "event_time": NOW, "cpu_utilization": 1.0,
                        "diagnostic_payload": {}, "source_event_key": "m"}]
        assert await TelemetryStreamConsumer._insert_rows(Sess(), TelemetryMetric, metric_rows) == []


# --------------------------------------------------------------------------- offline emission
class _FakeDB:
    def __init__(self):
        self.added, self.commits, self.rollbacks = [], 0, 0

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def execute(self, stmt):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))


class TestOfflineWinlogEmission:
    async def test_offline_batch_enqueues_persisted_log_ids_with_null_key_before_commit(self, monkeypatch):
        order: list[str] = []
        captured: list = []

        async def no_keys(*a, **k):
            return set()

        async def persist(db, asset_id, event, dedup_key, fallback_time=None):
            return uuid.uuid4()

        async def enqueue(db, items):
            order.append("enqueue")
            captured.extend(items)
            return len(captured)

        db = _FakeDB()
        original_commit = db.commit

        async def commit():
            order.append("commit")
            await original_commit()

        db.commit = commit
        monkeypatch.setattr(P, "_fetch_duplicate_keys", no_keys)
        monkeypatch.setattr(P, "_persist_event", persist)
        monkeypatch.setattr(P, "enqueue_incident_ingest", enqueue)
        events = [{"event_id": 41, "severity": "Critical", "channel": "System", "provider": "P1",
                   "record_id": 1, "occurrence_time": "2026-09-14T10:00:00"},
                  {"event_id": 6005, "severity": "Information", "channel": "System", "provider": "P2",
                   "record_id": 2, "occurrence_time": "2026-09-14T10:00:01"},
                  {"event_id": 10016, "severity": "Warning", "channel": "System", "provider": "P3",
                   "record_id": 3, "occurrence_time": "2026-09-14T10:00:02"}]
        result = await P.ingest_report_events(db, ASSET, {"event_logs": {"events": events}}, analyze_max=0)
        assert result.events_new == 3
        assert order == ["enqueue", "commit"]
        assert sorted(i.provenance["severity"] for i in captured) == ["Critical", "Warning"]
        assert all(i.source_event_key is None and i.asset_id == ASSET and i.source_type == "winlog"
                   for i in captured)

    async def test_enqueue_failure_rolls_back_and_reports_events_failed(self, monkeypatch):
        async def no_keys(*a, **k):
            return set()

        async def persist(db, asset_id, event, dedup_key, fallback_time=None):
            return uuid.uuid4()

        monkeypatch.setattr(P, "_fetch_duplicate_keys", no_keys)
        monkeypatch.setattr(P, "_persist_event", persist)
        monkeypatch.setattr(P, "enqueue_incident_ingest", AsyncMock(side_effect=RuntimeError("outbox down")))
        db = _FakeDB()
        event = {"event_id": 41, "severity": "Critical", "channel": "System", "provider": "P1", "record_id": 1}
        result = await P.ingest_report_events(db, ASSET, {"event_logs": {"events": [event]}}, analyze_max=0)
        assert db.commits == 0 and db.rollbacks == 1
        assert result.events_new == 0 and result.events_failed == 1


# --------------------------------------------------------------------------- dispatcher
class _DSession:
    def __init__(self, store):
        self.store = store

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def begin(self):
        return _DTx(self.store)

    async def execute(self, stmt):
        text = str(stmt).lower()
        if text.startswith("update"):
            outbox_id = next(v for v in stmt.compile().params.values() if isinstance(v, uuid.UUID))
            self.store.log.append(f"stamp:{outbox_id}")
            if self.store.fail_stamp:
                raise OperationalError("UPDATE", {}, Exception("crash before stamp"))
            for row in self.store.rows:
                if row.outbox_id == outbox_id:
                    row.published_at = NOW
            return None
        self.store.log.append("claim")
        pending = [r for r in self.store.rows if r.published_at is None]
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: pending))


class _DTx:
    def __init__(self, store):
        self.store = store

    async def __aenter__(self):
        self.store.in_tx += 1
        return self

    async def __aexit__(self, *exc):
        self.store.in_tx -= 1
        return False


def _outbox_row(**over):
    base = dict(outbox_id=uuid.uuid4(), source_type="winlog", source_id=str(uuid.uuid4()), observed_at=NOW,
                source_event_key=None, asset_id=ASSET, provenance={"origin": "t"}, published_at=None)
    base.update(over)
    return SimpleNamespace(**base)


class _Store:
    def __init__(self, rows):
        self.rows, self.log, self.in_tx, self.fail_stamp = rows, [], 0, False


class _XRedis:
    def __init__(self, store, fail=False, unconfirmed=False):
        self.store, self.fail, self.unconfirmed, self.added = store, fail, unconfirmed, []

    async def xadd(self, key, fields):
        assert self.store.in_tx == 0, "XADD must never run inside a DB transaction"
        if self.fail:
            from redis.exceptions import ConnectionError as RedisConnectionError
            raise RedisConnectionError("down")
        if self.unconfirmed:
            return None
        self.added.append((key, fields))
        self.store.log.append("xadd")
        return "1-0"


class TestDispatcher:
    async def test_claim_then_xadd_outside_tx_then_stamp_in_order(self):
        rows = [_outbox_row(), _outbox_row()]
        store = _Store(rows)
        redis = _XRedis(store)
        assert await dispatcher_mod.dispatch_pending(lambda: _DSession(store), redis) == 2
        assert store.log[0] == "claim" and store.log[1] == "xadd" and store.log[2].startswith("stamp:")
        assert all(r.published_at for r in rows)
        key, fields = redis.added[0]
        assert key == INGEST_STREAM_KEY and fields["source_type"] == "winlog"
        assert "source_event_key" not in fields  # NULL key is omitted, not fabricated

    @pytest.mark.parametrize("kwargs", [{"fail": True}, {"unconfirmed": True}])
    async def test_redis_failure_or_unconfirmed_xadd_leaves_rows_pending(self, kwargs):
        rows = [_outbox_row()]
        store = _Store(rows)
        assert await dispatcher_mod.dispatch_pending(lambda: _DSession(store), _XRedis(store, **kwargs)) == 0
        assert rows[0].published_at is None and not any(e.startswith("stamp") for e in store.log)

    async def test_crash_between_xadd_and_stamp_republishes(self):
        rows = [_outbox_row()]
        store = _Store(rows)
        redis = _XRedis(store)
        store.fail_stamp = True
        with pytest.raises(OperationalError):
            await dispatcher_mod.dispatch_pending(lambda: _DSession(store), redis)
        assert rows[0].published_at is None and len(redis.added) == 1  # published, not stamped
        store.fail_stamp = False
        assert await dispatcher_mod.dispatch_pending(lambda: _DSession(store), redis) == 1
        assert len(redis.added) == 2 and rows[0].published_at  # republished: at-least-once

    async def test_safe_wrapper_swallows_failures(self):
        class Broken:
            def __call__(self):
                raise OperationalError("x", {}, Exception("db down"))

        assert await dispatcher_mod.dispatch_pending_safely(Broken(), object()) == 0
        assert await dispatcher_mod.dispatch_pending_safely(None, None) == 0


# --------------------------------------------------------------------------- consumer
class _Ctx:
    async def __aenter__(self):
        return SimpleNamespace()

    async def __aexit__(self, *exc):
        return False


class _FakeRedis:
    def __init__(self):
        self.new: list[tuple[str, dict]] = []
        self.pending: dict[str, dict] = {}
        self.deliveries: dict[str, int] = {}
        self.acked: list[str] = []
        self.dlq: list[dict] = []
        self.xclaims: list[dict] = []
        self.log: list[str] = []
        self.fail_ack = False

    async def xgroup_create(self, **kw):
        return True

    async def xautoclaim(self, **kw):
        claimed = list(self.pending.items())[: kw["count"]]
        for mid, _ in claimed:
            self.deliveries[mid] += 1
        return ["0-0", [(mid.encode(), {k.encode(): v.encode() for k, v in f.items()}) for mid, f in claimed], []]

    async def xreadgroup(self, **kw):
        batch, self.new = self.new[: kw["count"]], self.new[kw["count"]:]
        for mid, fields in batch:
            self.pending[mid] = fields
            self.deliveries[mid] = 1
        if not batch:
            return []
        return [(b"s", [(mid.encode(), {k.encode(): v.encode() for k, v in f.items()}) for mid, f in batch])]

    async def xack(self, key, group, *ids):
        if self.fail_ack:
            raise ConnectionError("ack lost")
        self.log.append("ack")
        for mid in ids:
            self.pending.pop(mid, None)
            self.acked.append(mid)
        return len(ids)

    async def xdel(self, key, *ids):
        return len(ids)

    async def xadd(self, key, fields):
        assert key == INGEST_DEAD_LETTER_KEY
        self.dlq.append(fields)
        self.log.append("dlq")
        return "9-0"

    async def xpending_range(self, key, group, min, max, count):
        return [{"times_delivered": self.deliveries[min]}] if min in self.pending else []

    async def xclaim(self, **kw):
        self.xclaims.append(kw)
        return []


class _FakeService:
    calls: list = []
    behaviour = staticmethod(lambda evidence, kw: (SimpleNamespace(), True))
    log: list = []

    def __init__(self, session):
        pass

    async def enrich_evidence(self, items, asset_id):
        # Pass-through: event-time/identity enrichment is covered by the PostgreSQL tests; the consumer must call it.
        _FakeService.enriched = True
        return items, asset_id

    async def create_from_evidence(self, evidence, **kw):
        _FakeService.calls.append((evidence, kw))
        _FakeService.log.append("commit")
        return _FakeService.behaviour(evidence, kw)


@pytest.fixture
def fx(monkeypatch):
    _FakeService.calls, _FakeService.log = [], []
    _FakeService.enriched = False
    _FakeService.behaviour = staticmethod(lambda evidence, kw: (SimpleNamespace(), True))
    monkeypatch.setattr(consumer_mod, "IncidentService", _FakeService)
    monkeypatch.setattr(consumer_mod, "dispatch_pending_safely", AsyncMock(return_value=0))
    redis = _FakeRedis()
    redis.log = _FakeService.log  # shared timeline: commit must precede ack
    consumer = consumer_mod.IncidentIngestConsumer(
        redis_provider=lambda: redis, session_maker_provider=lambda: (lambda: _Ctx()),
        max_delivery_attempts=3, reclaim_idle_ms=0)
    return consumer, redis


def _entry(mid="1-0", **over):
    return mid, {k: v for k, v in _fields(**over).items()}


class TestConsumer:
    async def test_ack_only_after_incident_commit_and_envelope_drives_evidence(self, fx):
        consumer, redis = fx
        key = "evtx:abc"
        mid, fields = _entry(source_event_key=key, asset_id=str(ASSET))
        redis.new.append((mid, fields))
        assert await consumer.process_batch() == 1
        assert redis.log == ["commit", "ack"]
        evidence, kw = _FakeService.calls[0]
        assert kw["actor"] == INGEST_ACTOR and kw["asset_id"] == ASSET
        item = evidence[0]
        assert (item.source_type, item.source_id, item.source_event_key) == ("winlog", fields["source_id"], key)
        assert item.observed_at == NOW
        assert _FakeService.enriched is True  # the stream path evaluates event time like the HTTP path

    async def test_null_asset_and_null_event_key_pass_through(self, fx):
        consumer, redis = fx
        redis.new.append(_entry(source_type="analysis", source_id="12"))
        await consumer.process_batch()
        evidence, kw = _FakeService.calls[0]
        assert kw["asset_id"] is None and evidence[0].source_event_key is None

    async def test_redelivery_after_lost_ack_is_idempotent(self, fx):
        consumer, redis = fx
        redis.new.append(_entry())
        redis.fail_ack = True
        assert await consumer.process_batch() == 0  # committed, ACK lost -> still pending
        assert "1-0" in redis.pending and consumer.metrics["ack_failures"] == 1
        redis.fail_ack = False
        _FakeService.behaviour = staticmethod(lambda e, kw: (SimpleNamespace(), False))  # sink says: exists
        assert await consumer.process_batch() == 1
        assert consumer.metrics["incidents_reused"] == 1 and redis.acked == ["1-0"]

    @pytest.mark.parametrize("exc", [
        OperationalError("x", {}, Exception("db down")), ConnectionError("redis"), asyncio.TimeoutError(),
        IncidentConflict("race")])
    async def test_transient_failures_never_ack_and_never_dead_letter(self, fx, exc):
        consumer, redis = fx

        def boom(evidence, kw):
            raise exc

        _FakeService.behaviour = staticmethod(boom)
        redis.new.append(_entry())
        for _ in range(consumer.max_delivery_attempts + 3):  # well past the poison cap
            await consumer.process_batch()
        assert redis.acked == [] and redis.dlq == [] and "1-0" in redis.pending

    async def test_poison_is_dead_lettered_only_at_the_delivery_cap_with_stable_reason(self, fx):
        consumer, redis = fx

        def reject(evidence, kw):
            raise IncidentValidationError("Asset is not registered.")

        _FakeService.behaviour = staticmethod(reject)
        redis.new.append(_entry("1-0"))
        redis.new.append(_entry("2-0", source_id="77"))
        await consumer.process_batch()  # delivery 1
        await consumer.process_batch()  # delivery 2
        assert redis.dlq == [] and redis.acked == []
        await consumer.process_batch()  # delivery 3 == cap
        assert [d["reason"] for d in redis.dlq] == ["incident-validation-rejected"] * 2
        assert redis.pending == {} and consumer.metrics["dead_lettered"] == 2
        assert redis.log.index("dlq") < redis.log.index("ack")  # DLQ confirmed before ACK

    async def test_invalid_envelope_is_poison_without_calling_the_sink(self, fx):
        consumer, redis = fx
        redis.new.append(("1-0", {"source_type": "bogus"}))
        for _ in range(3):
            await consumer.process_batch()
        assert _FakeService.calls == [] and redis.dlq[0]["reason"] == "invalid-envelope"

    async def test_valid_sibling_is_unaffected_by_a_poison_entry(self, fx):
        consumer, redis = fx
        bad_id = str(uuid.uuid4())

        def mixed(evidence, kw):
            if evidence[0].source_id == bad_id:
                raise IntegrityError("x", {}, Exception("row"))
            return SimpleNamespace(), True

        _FakeService.behaviour = staticmethod(mixed)
        redis.new.extend([_entry("1-0", source_id=bad_id), _entry("2-0")])
        await consumer.process_batch()
        assert redis.acked == ["2-0"] and "1-0" in redis.pending

    async def test_lease_refresh_uses_justid_and_zero_idle_so_deliveries_do_not_inflate(self, fx):
        consumer, redis = fx
        consumer.reclaim_idle_ms = 150  # interval = 0.05s
        redis.deliveries["1-0"] = 1
        redis.pending["1-0"] = {}
        task = asyncio.create_task(consumer._refresh_loop(redis, {"1-0"}))
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert redis.xclaims and all(c["justid"] is True and c["idle"] == 0 for c in redis.xclaims)
        assert redis.deliveries["1-0"] == 1

    async def test_concurrency_is_bounded(self, fx):
        consumer, redis = fx
        consumer.concurrency = 2
        state = {"now": 0, "max": 0}

        async def slow_create(session_maker, envelope):
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
            await asyncio.sleep(0.02)
            state["now"] -= 1
            return True

        consumer._create_incident = slow_create
        redis.new.extend([_entry(f"{i}-0", source_id=str(i)) for i in range(1, 7)])
        consumer.batch_size = 6
        assert await consumer.process_batch() == 6
        assert state["max"] == 2

    async def test_stop_leaves_unacked_entries_pending(self, fx):
        consumer, redis = fx
        started = asyncio.Event()

        async def hang(session_maker, envelope):
            started.set()
            await asyncio.sleep(30)

        consumer._create_incident = hang
        consumer.stop_grace_seconds = 0.05
        redis.new.append(_entry())
        await consumer.start()
        await asyncio.wait_for(started.wait(), 2)
        await consumer.stop()
        assert redis.acked == [] and redis.dlq == [] and "1-0" in redis.pending


class TestClassification:
    @pytest.mark.parametrize("exc,kind,reason", [
        (EnvelopeError("x"), consumer_mod.FailureKind.POISON, "invalid-envelope"),
        (IncidentValidationError("x"), consumer_mod.FailureKind.POISON, "incident-validation-rejected"),
        (IntegrityError("x", {}, Exception()), consumer_mod.FailureKind.POISON, "row-rejected-by-database"),
        (DataError("x", {}, Exception()), consumer_mod.FailureKind.POISON, "row-rejected-by-database"),
        (OperationalError("x", {}, Exception()), consumer_mod.FailureKind.TRANSIENT, "infrastructure-unavailable"),
        (ConnectionError("x"), consumer_mod.FailureKind.TRANSIENT, "infrastructure-unavailable"),
        (IncidentConflict("x"), consumer_mod.FailureKind.TRANSIENT, "incident-conflict"),
        # F4: unclassified is transient (never auto-DLQ'd) and surfaces via logging.
        (KeyError("x"), consumer_mod.FailureKind.TRANSIENT, "unclassified-processing-error")])
    def test_classify(self, exc, kind, reason):
        assert consumer_mod.classify_error(exc) == (kind, reason)


# --------------------------------------------------------------------------- migration / model parity
class TestMigrationStatic:
    def _graph(self):
        revision = re.compile(r"^revision(?::[^=]+)?\s*=\s*['\"]([0-9a-f]+)['\"]", re.M)
        down = re.compile(r"^down_revision(?::[^=]+)?\s*=\s*['\"]([0-9a-f]+)['\"]", re.M)
        revs, parents = set(), set()
        for path in MIGRATIONS.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if m := revision.search(text):
                revs.add(m.group(1))
            if m := down.search(text):
                parents.add(m.group(1))
        return revs, parents

    def test_single_head_and_parent_is_incident_core(self):
        revs, parents = self._graph()
        assert len(revs - parents) == 1 and "c4e8a1f7b932" in revs  # single head; the outbox migration is in its lineage
        assert "c4e8a1f7b932" in parents or revs - parents == {"c4e8a1f7b932"}  # and it is no dangling branch
        text = (MIGRATIONS / "c4e8a1f7b932_add_incident_ingest_outbox.py").read_text(encoding="utf-8")
        assert 'down_revision = "b8d3f5c1a720"' in text

    def test_migration_matches_model_and_is_additive(self):
        text = (MIGRATIONS / "c4e8a1f7b932_add_incident_ingest_outbox.py").read_text(encoding="utf-8")
        columns = set(re.findall(r'sa\.Column\("(\w+)"', text))
        assert columns == {c.name for c in IncidentIngestOutbox.__table__.columns}
        for name in ("uq_incident_ingest_outbox_source", "ck_incident_ingest_outbox_source_type",
                     "ck_incident_ingest_outbox_provenance_bounded", "idx_incident_ingest_outbox_pending",
                     "fk_incident_ingest_outbox_asset_id"):
            assert name in text
        assert 'ondelete="RESTRICT"' in text and "published_at IS NULL" in text
        upgrade = text.split("def downgrade")[0]
        assert not re.search(r"op\.(alter_|drop_|add_column)", upgrade)  # touches no existing table
        assert text.count('op.drop_table("incident_ingest_outbox")') == 1

    def test_telemetry_alert_outbox_is_untouched(self):
        source = Path(worker_module.__file__).read_text(encoding="utf-8")
        assert 'ALERT_STREAM_KEY = "eims:events:alerts:stream"' in source
        assert 'ALERT_CHANNEL = "eims:events:alerts"' in source
        assert "incident" not in source.split("async def dispatch_outbox")[1].split("async def _ack_and_trim")[0]
