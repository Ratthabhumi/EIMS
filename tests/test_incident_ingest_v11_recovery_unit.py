"""Hermetic recovery-pass tests for Incident Core v1.1 (F1-F11). No DB, no Redis, no network.

Every Redis/session object is an explicit local stub; nothing reads ``cache_manager.redis``.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.incident_ingest import consumer as consumer_mod
from backend.domain.incident_ingest import dispatcher as dispatcher_mod
from backend.domain.incident_ingest import outbox as outbox_mod
from backend.domain.incident_ingest.envelope import INGEST_DEAD_LETTER_KEY, INGEST_STREAM_KEY, IngestEnvelope
from backend.domain.telemetry import worker as worker_module

P = importlib.import_module("backend.domain.analyzer.services.import_pipeline")
NOW = datetime(2026, 11, 16, 1, 2, 3, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]


class _Savepoint:
    def __init__(self, log, fail=False):
        self.log, self.fail = log, fail

    async def __aenter__(self):
        self.log.append("savepoint")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.log.append("release" if exc is None else "rollback-to-savepoint")
        return False  # never swallow: the helper decides


class _Sess:
    def __init__(self, fail=False):
        self.log, self.fail = [], fail

    def begin_nested(self):
        return _Savepoint(self.log)

    async def execute(self, stmt):
        self.log.append("execute")
        if self.fail:
            raise OperationalError("insert", {}, Exception('relation "incident_ingest_outbox" does not exist'))


# ---- F2 / F9
class TestSourceIsolation:
    async def test_outbox_insert_failure_is_savepoint_scoped_and_never_raises(self):
        sess = _Sess(fail=True)
        before = outbox_mod.metrics["outbox_insert_failures"]
        n = await outbox_mod.enqueue_incident_ingest(sess, [outbox_mod.OutboxItem("winlog", "a", NOW)])
        assert n == 0 and sess.log == ["savepoint", "execute", "rollback-to-savepoint"]
        assert outbox_mod.metrics["outbox_insert_failures"] == before + 1

    async def test_success_uses_savepoint_in_caller_transaction(self):
        sess = _Sess()
        assert await outbox_mod.enqueue_incident_ingest(sess, [outbox_mod.OutboxItem("winlog", "a", NOW)]) == 1
        assert sess.log == ["savepoint", "execute", "release"]

    async def test_invalid_item_does_not_block_valid_siblings(self):
        sess = _Sess()
        n = await outbox_mod.enqueue_incident_ingest(sess, [
            outbox_mod.OutboxItem("bogus", "x", NOW), outbox_mod.OutboxItem("winlog", "ok", NOW)])
        assert n == 1 and sess.log.count("execute") == 1

    async def test_non_schema_error_is_raised_and_counted_once(self):
        """A deadlock/timeout must fail the source transaction, not be swallowed (review M1)."""
        class _DeadlockSess(_Sess):
            async def execute(self, stmt):
                self.log.append("execute")
                raise OperationalError("insert", {}, Exception("deadlock detected"))

        sess = _DeadlockSess()
        before = outbox_mod.metrics["outbox_insert_failures"]
        with pytest.raises(OperationalError):
            await outbox_mod.enqueue_incident_ingest(sess, [outbox_mod.OutboxItem("winlog", "a", NOW)])
        assert outbox_mod.metrics["outbox_insert_failures"] == before + 1
        assert sess.log == ["savepoint", "execute", "rollback-to-savepoint"]

    async def test_rows_are_chunked_below_driver_parameter_limit(self):
        """More rows than one statement allows must be split, with the count preserved (review M2)."""
        sess = _Sess()
        per = outbox_mod.MAX_ROWS_PER_INSERT
        total = per * 2 + 200
        items = [outbox_mod.OutboxItem("winlog", str(i), NOW) for i in range(total)]
        assert await outbox_mod.enqueue_incident_ingest(sess, items) == total
        assert sess.log.count("execute") == 3
        assert sess.log[0] == "savepoint" and sess.log[-1] == "release"

    async def test_cancellation_is_not_swallowed(self):
        sess = _Sess()
        sess.execute = AsyncMock(side_effect=asyncio.CancelledError())
        with pytest.raises(asyncio.CancelledError):
            await outbox_mod.enqueue_incident_ingest(sess, [outbox_mod.OutboxItem("winlog", "a", NOW)])

    async def test_unsupported_session_is_logged_and_counted(self):
        before = outbox_mod.metrics["unsupported_session_skips"]
        await outbox_mod.enqueue_analysis_history(object(), SimpleNamespace(id=1, created_at=NOW, event_id="1"),
                                                  origin="x")
        assert outbox_mod.metrics["unsupported_session_skips"] == before + 1

    async def test_returning_rows_only_feed_the_outbox(self):
        """Only RETURNING rows (actually inserted) become items; a replay returns nothing."""
        assert outbox_mod.winlog_items_from_returned([], origin="telemetry_worker") == []
        rid = uuid.uuid4()
        items = outbox_mod.winlog_items_from_returned(
            [(rid, None, NOW, "Warning", 1, None), (uuid.uuid4(), None, NOW, "Information", 2, "k")],
            origin="telemetry_worker")
        assert [i.source_id for i in items] == [str(rid)] and items[0].source_event_key is None


# ---- F3
def test_worker_has_no_direct_dispatch_path():
    src = (ROOT / "backend/domain/telemetry/worker.py").read_text(encoding="utf-8")
    assert "dispatch_pending_safely" not in src and "nudge_dispatch()" in src
    assert not hasattr(worker_module, "dispatch_pending_safely")


# ---- F4 / F6 / F5 / F11
def _env(**prov):
    return SimpleNamespace(source_type=prov.pop("st", "winlog"), provenance=prov)


class TestSeverityMapping:
    @pytest.mark.parametrize("raw,expected", [("Critical", "critical"), ("Error", "high"), ("Warning", "medium"),
                                              ("Information", None), (None, None)])
    def test_winlog(self, raw, expected):
        assert consumer_mod.incident_severity_for(_env(severity=raw)) == expected

    def test_analysis_keeps_incident_core_default(self):
        assert consumer_mod.incident_severity_for(_env(st="analysis", severity="Critical")) is None


class TestClassification:
    def test_unclassified_is_transient_and_never_poison(self):
        kind, reason = consumer_mod.classify_error(ZeroDivisionError())
        assert kind is consumer_mod.FailureKind.TRANSIENT and reason == consumer_mod.REASON_UNCLASSIFIED


class TestCapAndStop:
    def test_db_concurrency_is_capped(self):
        c = consumer_mod.IncidentIngestConsumer(redis_provider=lambda: None, session_maker_provider=lambda: None,
                                                concurrency=500)
        assert c.concurrency == consumer_mod.MAX_DB_CONCURRENCY

    async def test_outer_cancellation_of_stop_propagates_and_tears_down_loop(self):
        c = consumer_mod.IncidentIngestConsumer(redis_provider=lambda: None, session_maker_provider=lambda: None,
                                                polling_interval=30, stop_grace_seconds=30)
        await c.start()
        task = c._task
        stopper = asyncio.create_task(c.stop())
        await asyncio.sleep(0)  # let stop() start waiting on the (sleeping) loop
        c._running = True  # keep the loop alive so stop() is genuinely waiting
        stopper.cancel()
        with pytest.raises(asyncio.CancelledError):
            await stopper
        await asyncio.sleep(0)
        assert task.cancelled() or task.done()


# ---- F4: DLQ replay + reconcile
class _R:
    def __init__(self, dlq):
        self.dlq, self.main, self.deleted = dlq, [], []

    async def xrange(self, key, min, max, count):
        assert key == INGEST_DEAD_LETTER_KEY
        return self.dlq

    async def xadd(self, key, fields):
        assert key == INGEST_STREAM_KEY
        self.main.append(fields)
        return "5-0"

    async def xdel(self, key, *ids):
        assert key == INGEST_DEAD_LETTER_KEY
        self.deleted.extend(ids)


def _dlq_entry(mid, fields):
    return (mid.encode(), {b"entry": json.dumps(fields).encode(), b"reason": b"x"})


class TestDlqReplay:
    async def test_valid_entry_is_readded_then_deleted(self):
        good = IngestEnvelope(uuid.uuid4(), "winlog", "s1", NOW).to_stream_fields()
        r = _R([_dlq_entry("1-0", good)])
        assert await dispatcher_mod.replay_dead_letter(r) == 1
        assert r.main == [good] and r.deleted == [b"1-0"]

    async def test_corrupt_or_truncated_entry_is_left_in_dlq(self):
        r = _R([(b"1-0", {b"entry": b'{"outbox_id": "trunc'}), _dlq_entry("2-0", {"source_type": "bogus"})])
        assert await dispatcher_mod.replay_dead_letter(r) == 0
        assert r.main == [] and r.deleted == []

    async def test_unconfirmed_xadd_keeps_the_entry(self):
        good = IngestEnvelope(uuid.uuid4(), "analysis", "9", NOW).to_stream_fields()
        r = _R([_dlq_entry("1-0", good)])
        r.xadd = AsyncMock(return_value=None)
        assert await dispatcher_mod.replay_dead_letter(r) == 0 and r.deleted == []

    async def test_no_redis_is_a_noop(self):
        assert await dispatcher_mod.replay_dead_letter(None) == 0


class _Result:
    rowcount = 3


class _RecSess:
    def __init__(self, store):
        self.store = store

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def begin(self):
        return self

    async def execute(self, stmt):
        self.store.append(stmt)
        return _Result()


async def test_reconcile_rearms_only_published_rows_without_evidence_and_never_deletes():
    seen = []
    n = await dispatcher_mod.reconcile_published_without_evidence(lambda: _RecSess(seen))
    sql = str(seen[0].compile(dialect=postgresql.dialect())).upper()
    assert n == 3 and sql.startswith("UPDATE INCIDENT_INGEST_OUTBOX SET PUBLISHED_AT=")
    assert "NOT (EXISTS" in sql and "INCIDENT_EVIDENCE" in sql and "FOR UPDATE SKIP LOCKED" in sql
    assert "DELETE" not in sql


# ---- F7
async def test_offline_fallback_timestamp_is_shared_by_row_and_outbox(monkeypatch):
    added, enq = [], []
    db = MagicMock()
    db.add = added.append
    db.commit = AsyncMock()
    monkeypatch.setattr(P, "_fetch_duplicate_keys", AsyncMock(return_value=set()))
    monkeypatch.setattr(P, "nudge_dispatch", lambda: None)

    async def capture(session, items):
        enq.extend(items)
        return len(items)

    monkeypatch.setattr(P, "enqueue_incident_ingest", capture)
    monkeypatch.setattr(P, "analyze_event_if_needed", AsyncMock(), raising=False)
    report = {"event_logs": {"events": [{"event_id": 41, "provider": "p", "severity": "Error",
                                          "message": "m"}]}}
    await P.ingest_report_events(db, uuid.uuid4(), report, analyze_max=0)
    row = added[0]
    assert row.occurrence_time is not None and enq and enq[0].observed_at == row.occurrence_time
    assert enq[0].source_id == str(row.log_id) and enq[0].source_event_key is None


# ---- F1 / F11 static
def test_real_postgres_harnesses_create_the_outbox_table():
    for name in ("tests/analyzer_synthetic_demo_app.py", "tests/test_analyzer_postgres_integration.py"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "IncidentIngestOutbox.__table__.create" in text, name
    assert "a4b7c9d2e601'" not in (ROOT / "tests/test_analyzer_postgres_integration.py").read_text(encoding="utf-8")


def test_alembic_env_registers_outbox_metadata_and_graph_is_single_head():
    assert "IncidentIngestOutbox" in (ROOT / "migrations/env.py").read_text(encoding="utf-8")
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config()
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    script = ScriptDirectory.from_config(cfg)
    assert len(script.get_heads()) == 1  # a pin on the latest head goes stale; keep the single-head + lineage intent
    assert "c4e8a1f7b932" in {rev.revision for rev in script.walk_revisions()}
