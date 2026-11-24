"""Hermetic contracts for telemetry asset isolation, replay-safe brute force, and the migration.

No Redis/PostgreSQL: the database is an in-memory fake that models the unique
source_event_key constraint, transactional commit/rollback, and FK/integrity rejection.
The real SQL (ON CONFLICT, JSONB count) is not executed here.
"""
import importlib.util
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, OperationalError

from backend.domain.telemetry import worker as worker_module
from backend.domain.telemetry.models import TelemetryAlertOutbox
from backend.domain.telemetry.broker import RedisTelemetryStreamBroker, TELEMETRY_STREAM_KEY
from backend.domain.telemetry.worker import (
    ROW_REJECTED_REASON, UNRESOLVED_ASSET_REASON, TelemetryStreamConsumer,
)
from backend.infrastructure.cache import AsynchronousCacheManager

ROOT = Path(__file__).resolve().parents[1]
KNOWN_FP = "a" * 64
ASSET_ID = uuid.UUID("00000000-0000-0000-0000-0000000000aa")
NOW = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def first(self):
        return self._value

    def all(self):
        return list(self._value)

    def scalar(self):
        return self._value


class FakeDB:
    def __init__(self):
        self.metrics: dict[str, object] = {}
        self.winlogs: dict[str, object] = {}
        self.bad_keys: set[str] = set()
        self.fail_commit = False
        self.commits = 0
        self.asset = SimpleNamespace(asset_id=ASSET_ID, lifecycle_state="Active", current_compliance_score=100)
        self.audit_logs: list[object] = []
        self.outbox: dict[object, object] = {}


class FakeSession:
    def __init__(self, db):
        self.db = db
        self.staged_metrics: dict[str, object] = {}
        self.staged_winlogs: dict[str, object] = {}
        self.staged_audit: list[object] = []
        self.staged_outbox: list[object] = []
        self.staged_state = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def begin(self):
        return _Tx(self)

    def add(self, obj):
        (self.staged_outbox if isinstance(obj, TelemetryAlertOutbox) else self.staged_audit).append(obj)

    async def execute(self, stmt):
        sql = str(stmt).lower()
        if "update telemetry_alert_outbox" in sql:
            params = stmt.compile().params
            alert_id = next((value for value in params.values() if isinstance(value, uuid.UUID)), None)
            row = self.db.outbox.get(alert_id)
            if row is not None:
                row.published_at = datetime.now(UTC)
            return FakeResult([])
        if "telemetry_alert_outbox" in sql:
            return FakeResult([r for r in self.db.outbox.values() if r.published_at is None])
        value = next(iter(stmt.compile().params.values()))
        # Asset lookup by UUID; fingerprint lookups (str) never match a registered asset.
        return FakeResult(self.db.asset if value == ASSET_ID else None)


class _Tx:
    def __init__(self, session):
        self.s = session

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        db = self.s.db
        if exc_type is not None:
            return False  # rollback: staged state discarded
        if db.fail_commit:
            raise OperationalError("COMMIT", {}, Exception("synthetic commit failure"))
        db.metrics.update(self.s.staged_metrics)
        db.winlogs.update(self.s.staged_winlogs)
        db.audit_logs.extend(self.s.staged_audit)
        for row in self.s.staged_outbox:
            db.outbox[row.alert_id] = row
        db.commits += 1
        return False


def _wire(monkeypatch, db):
    """Return a consumer whose persistence and broker are fully in-memory."""
    monkeypatch.setattr(worker_module.database_engine, "get_session_maker", lambda: (lambda: FakeSession(db)))
    broker = RedisTelemetryStreamBroker(AsynchronousCacheManager())
    broker.dead_letter_stream_message = AsyncMock()
    broker.ack_stream_messages = AsyncMock()
    consumer = TelemetryStreamConsumer(broker=broker)
    consumer.register_agent_mapping(KNOWN_FP, ASSET_ID)
    consumer.published: list[dict] = []
    consumer.published_at_commit_count: list[int] = []

    async def publish(_channel, payload):
        consumer.published.append(payload)
        consumer.published_at_commit_count.append(db.commits)

    consumer.xadds: list[dict] = []
    consumer.xadd_commit_count: list[int] = []
    consumer.xadd_db_state: list[tuple[int, int]] = []
    consumer.redis_down = False
    consumer.pubsub_down = False

    async def publish_checked(channel, payload):
        if consumer.pubsub_down:
            raise ConnectionError("synthetic pubsub failure")
        await publish(channel, payload)

    async def xadd(key, fields):
        if consumer.redis_down:
            raise ConnectionError("synthetic redis outage")
        consumer.xadds.append({"key": key, **fields})
        consumer.xadd_commit_count.append(db.commits)
        consumer.xadd_db_state.append((len(db.outbox), len(db.audit_logs)))  # durable at XADD time
        return f"{len(consumer.xadds)}-0"

    consumer._redis = SimpleNamespace(publish=publish_checked, xadd=xadd)

    async def insert_rows(session, model, rows):
        target = session.staged_metrics if "cpu_utilization" in rows[0] else session.staged_winlogs
        committed = db.metrics if "cpu_utilization" in rows[0] else db.winlogs
        for row in rows:
            key = row["source_event_key"]
            if key in db.bad_keys:
                raise IntegrityError("INSERT", {}, Exception("synthetic FK violation"))
            if key not in committed and key not in target:  # ON CONFLICT DO NOTHING
                target[key] = SimpleNamespace(**row)

    async def count(session, src_ip, window_end, window_start, *, asset_id=None):
        rows = {**db.winlogs, **session.staged_winlogs}.values()
        return sum(1 for r in rows if r.event_id == 4625
                   and (asset_id is None or r.asset_id == asset_id)
                   and r.evtx_metadata.get("source_network_ip") == src_ip
                   and window_start <= r.occurrence_time <= window_end)

    consumer._insert_rows = insert_rows
    consumer._count_failed_logons = count
    return consumer, broker


def _heartbeat(key, fingerprint=KNOWN_FP):
    payload = ('{"agent_version":"synthetic","timestamp":"%s","metrics":{"cpu_utilization":9,'
               '"ram_used_mb":100,"ram_total_mb":1000,"disk_iops":1}}' % NOW.isoformat())
    return key, {"event_type": "heartbeat", "cert_fingerprint": fingerprint,
                 "source_event_key": key, "payload": payload}


def _failed_logon(key, offset=0, ip="203.0.113.7", fingerprint=KNOWN_FP):
    payload = ('{"occurrence_time":"%s","event_id":4625,"severity":"Warning","event_channel":"Security",'
               '"metadata":{"source_network_ip":"%s"}}' % ((NOW + timedelta(seconds=offset)).isoformat(), ip))
    return key, {"event_type": "winlog", "cert_fingerprint": fingerprint,
                 "source_event_key": key, "payload": payload}


def _feed(consumer, *messages):
    consumer._fetch_batch = AsyncMock(return_value=(list(messages), TELEMETRY_STREAM_KEY, None))


# --- P1-1: unresolved assets -------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_asset_is_dead_lettered_and_does_not_poison_valid_rows(monkeypatch):
    db = FakeDB()
    consumer, broker = _wire(monkeypatch, db)
    _feed(consumer, _heartbeat("k-valid-1"), _heartbeat("k-unknown", "eims-evtx-upload-system"),
          _heartbeat("k-valid-2"))

    assert await consumer.process_batch() == 2

    assert set(db.metrics) == {"k-valid-1", "k-valid-2"}
    assert all(m.asset_id == ASSET_ID for m in db.metrics.values())  # no fabricated IDs
    broker.dead_letter_stream_message.assert_awaited_once()
    assert broker.dead_letter_stream_message.await_args.args[1] == "k-unknown"
    assert broker.dead_letter_stream_message.await_args.args[3] == UNRESOLVED_ASSET_REASON
    assert sorted(broker.ack_stream_messages.await_args.args[1]) == ["k-unknown", "k-valid-1", "k-valid-2"]


@pytest.mark.asyncio
async def test_persistent_bad_row_goes_to_dlq_and_valid_siblings_commit(monkeypatch):
    db = FakeDB()
    db.bad_keys = {"k-bad"}
    consumer, broker = _wire(monkeypatch, db)
    _feed(consumer, _heartbeat("k-1"), _heartbeat("k-bad"), _heartbeat("k-2"), _heartbeat("k-3"))

    assert await consumer.process_batch() == 3

    assert set(db.metrics) == {"k-1", "k-2", "k-3"}
    broker.dead_letter_stream_message.assert_awaited_once()
    args = broker.dead_letter_stream_message.await_args.args
    assert args[1] == "k-bad" and args[3] == ROW_REJECTED_REASON
    assert len(broker.ack_stream_messages.await_args.args[1]) == 4  # ACK only after DLQ write
    assert {m.source_event_key for m in consumer.processed_metrics} == {"k-1", "k-2", "k-3"}


@pytest.mark.asyncio
async def test_transient_db_error_leaves_batch_pending_not_dead_lettered(monkeypatch):
    db = FakeDB()
    consumer, broker = _wire(monkeypatch, db)
    consumer._insert_rows = AsyncMock(side_effect=OperationalError("INSERT", {}, Exception("db down")))
    _feed(consumer, _heartbeat("k-1"), _heartbeat("k-2"))

    with pytest.raises(OperationalError):
        await consumer.process_batch()

    broker.dead_letter_stream_message.assert_not_awaited()
    broker.ack_stream_messages.assert_not_awaited()
    assert consumer._last_id == "0-0"


# --- P2-1: replay-safe brute force, publish after commit ----------------------

@pytest.mark.asyncio
async def test_duplicate_4625_event_does_not_increment_count_twice(monkeypatch):
    db = FakeDB()
    consumer, _ = _wire(monkeypatch, db)
    five = [_failed_logon(f"k-{i}", offset=i) for i in range(5)]

    _feed(consumer, *five)
    await consumer.process_batch()
    _feed(consumer, five[-1], five[0])  # replay / duplicate delivery of already-committed events
    await consumer.process_batch()
    _feed(consumer, *five)  # whole-batch replay (commit succeeded, ACK lost)
    await consumer.process_batch()

    assert len(db.winlogs) == 5
    assert db.asset.lifecycle_state == "Active" and consumer.published == []

    _feed(consumer, _failed_logon("k-5", offset=5))  # genuinely new 6th event crosses > 5
    await consumer.process_batch()
    assert db.asset.lifecycle_state == "Quarantined"
    assert len(consumer.published) == 1
    assert len(db.audit_logs) == 1

    _feed(consumer, *five, _failed_logon("k-5", offset=5))  # replay after quarantine: no second alert
    await consumer.process_batch()
    assert len(consumer.published) == 1 and len(db.audit_logs) == 1


@pytest.mark.asyncio
async def test_alert_is_published_only_after_commit(monkeypatch):
    db = FakeDB()
    consumer, _ = _wire(monkeypatch, db)
    _feed(consumer, *[_failed_logon(f"k-{i}", offset=i) for i in range(6)])

    await consumer.process_batch()

    assert len(consumer.published) == 1
    assert consumer.xadd_db_state == [(1, 1)]  # outbox+audit already committed when XADD ran
    assert min(consumer.published_at_commit_count) >= 1


@pytest.mark.asyncio
async def test_rollback_publishes_no_alert_and_acks_nothing(monkeypatch):
    db = FakeDB()
    db.fail_commit = True
    consumer, broker = _wire(monkeypatch, db)
    _feed(consumer, *[_failed_logon(f"k-{i}", offset=i) for i in range(6)])

    with pytest.raises(OperationalError):
        await consumer.process_batch()

    assert consumer.published == []
    assert db.winlogs == {} and db.audit_logs == []
    broker.ack_stream_messages.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_logon_count_statement_is_row_derived_postgres_sql():
    captured = {}

    class Session:
        async def execute(self, stmt):
            compiled = stmt.compile(dialect=postgresql.dialect())
            captured["sql"] = str(compiled)
            captured["params"] = compiled.params
            return FakeResult(0)

    await TelemetryStreamConsumer._count_failed_logons(Session(), "203.0.113.7", NOW, NOW - timedelta(seconds=60))
    sql = captured["sql"]
    assert "count(*)" in sql and "windows_event_logs" in sql
    assert "event_id" in sql and "occurrence_time" in sql
    # The JSONB key is compiled as a bind parameter, so it appears in params, not in the SQL text.
    assert "source_network_ip" in captured["params"].values()


# --- brute-force scoping: asset + valid IP, per-candidate window ---------------

def _items(asset_id, offsets, ip="203.0.113.7"):
    return [SimpleNamespace(asset_id=asset_id, event_id=4625, occurrence_time=NOW + timedelta(seconds=o),
                            evtx_metadata={"source_network_ip": ip}) for o in offsets]


def _detector(monkeypatch, db, rows):
    """Consumer whose count evaluates `rows` (list of SimpleNamespace) and records every call."""
    consumer, _ = _wire(monkeypatch, db)
    calls = []

    async def count(session, src_ip, window_end, window_start, *, asset_id=None):
        calls.append((asset_id, src_ip, window_end))
        return sum(1 for r in rows if (asset_id is None or r.asset_id == asset_id)
                   and r.evtx_metadata["source_network_ip"] == src_ip
                   and window_start <= r.occurrence_time <= window_end)

    consumer._count_failed_logons = count
    return consumer, calls


@pytest.mark.asyncio
@pytest.mark.parametrize("ip", ["-", "", "127.0.0.1", "::1", "0.0.0.0", "::", "255.255.255.255",
                                "224.0.0.1", "::ffff:127.0.0.1", "not-an-ip", " 203.0.113.7", "999.1.1.1"])
async def test_placeholder_loopback_and_invalid_source_ips_are_never_aggregated(monkeypatch, ip):
    db = FakeDB()
    items = _items(ASSET_ID, range(8), ip=ip)
    consumer, calls = _detector(monkeypatch, db, items)

    alerts = await consumer._detect_brute_force(FakeSession(db), items)

    assert alerts == [] and calls == []
    assert db.asset.lifecycle_state == "Active"


@pytest.mark.asyncio
async def test_failed_logons_are_counted_per_asset_not_across_unrelated_assets(monkeypatch):
    other = uuid.UUID("00000000-0000-0000-0000-0000000000bb")
    db = FakeDB()
    items = _items(ASSET_ID, range(3)) + _items(other, range(3))  # same IP, 6 total, 3 each
    consumer, calls = _detector(monkeypatch, db, items)

    alerts = await consumer._detect_brute_force(FakeSession(db), items)

    assert alerts == [] and db.asset.lifecycle_state == "Active"
    assert calls and all(asset_id is not None for asset_id, _, _ in calls)

    burst = items + _items(ASSET_ID, range(3, 6))  # now asset A alone has 6
    consumer, _ = _detector(monkeypatch, db, burst)
    alerts = await consumer._detect_brute_force(FakeSession(db), burst)
    assert [a["asset_id"] for a in alerts] == [str(ASSET_ID)]


@pytest.mark.asyncio
async def test_burst_early_in_long_batch_is_not_hidden_by_a_later_event(monkeypatch):
    db = FakeDB()
    items = _items(ASSET_ID, [0, 1, 2, 3, 4, 5, 3600])  # 6-event burst, then an hour later
    consumer, _ = _detector(monkeypatch, db, items)

    session = FakeSession(db)
    alerts = await consumer._detect_brute_force(session, items)

    assert len(alerts) == 1 and db.asset.lifecycle_state == "Quarantined"
    assert [o.action_verb for o in session.staged_audit] == ["AUTOMATED_QUARANTINE_4625"]
    assert session.staged_audit[0].immutable_payload["failed_attempts"] == 6
    assert len(session.staged_outbox) == 1


@pytest.mark.asyncio
async def test_slow_failures_spread_beyond_the_window_do_not_trigger(monkeypatch):
    db = FakeDB()
    items = _items(ASSET_ID, [i * 20 for i in range(12)])  # max 4 per 60s window (inclusive bounds)
    consumer, _ = _detector(monkeypatch, db, items)

    assert await consumer._detect_brute_force(FakeSession(db), items) == []
    assert db.asset.lifecycle_state == "Active"


@pytest.mark.asyncio
async def test_threshold_is_still_strictly_greater_than_five(monkeypatch):
    db = FakeDB()
    items = _items(ASSET_ID, range(5))
    consumer, _ = _detector(monkeypatch, db, items)
    assert await consumer._detect_brute_force(FakeSession(db), items) == []


@pytest.mark.asyncio
async def test_failed_logon_count_statement_is_scoped_by_asset():
    captured = {}

    class Session:
        async def execute(self, stmt):
            compiled = stmt.compile(dialect=postgresql.dialect())
            captured["sql"], captured["params"] = str(compiled), compiled.params
            return FakeResult(0)

    await TelemetryStreamConsumer._count_failed_logons(
        Session(), "203.0.113.7", NOW, NOW - timedelta(seconds=60), asset_id=ASSET_ID)
    assert "windows_event_logs.asset_id" in captured["sql"]
    assert ASSET_ID in captured["params"].values()


# --- P2-5: migration ----------------------------------------------------------

def _load_migration():
    path = ROOT / "migrations" / "versions" / "e4a9c8b12d77_add_telemetry_event_idempotency.py"
    spec = importlib.util.spec_from_file_location("telemetry_idempotency_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


def test_migration_revision_chain_and_docstring_match():
    module, path = _load_migration()
    assert module.revision == "e4a9c8b12d77" and module.down_revision == "e1a202610250"
    assert f"Revises: {module.down_revision}" in module.__doc__
    parent = next((ROOT / "migrations" / "versions").glob("e1a202610250_*.py")).read_text(encoding="utf-8")
    assert re.search(r"^revision\s*(?::[^=]+)?=\s*['\"]e1a202610250['\"]", parent, re.M)
    siblings = [p for p in (ROOT / "migrations" / "versions").glob("*.py")
                if p != path and re.search(r"^down_revision.*['\"]e1a202610250['\"]", p.read_text(encoding="utf-8"), re.M)]
    assert siblings == []  # single head on this branch


def test_migration_builds_and_drops_unique_indexes_concurrently_in_autocommit():
    module, _ = _load_migration()
    state = {"in_block": False, "calls": []}

    class Block:
        def __enter__(self):
            state["in_block"] = True

        def __exit__(self, *exc):
            state["in_block"] = False

    fake_op = MagicMock()
    fake_op.get_context.return_value.autocommit_block = Block
    for name in ("create_index", "drop_index", "execute", "drop_column"):
        getattr(fake_op, name).side_effect = (
            lambda *a, _n=name, **k: state["calls"].append((_n, a, k, state["in_block"])))
    module.op = fake_op

    module.upgrade()
    creates = [c for c in state["calls"] if c[0] == "create_index"]
    assert len(creates) == 2
    for _, args, kwargs, in_block in creates:
        assert kwargs["unique"] is True and kwargs["postgresql_concurrently"] is True and in_block
        assert args[2] == ["source_event_key"]
    adds = [c for c in state["calls"] if c[0] == "execute"]
    assert len(adds) == 2  # idempotent column adds so a rerun after a failed index build works
    assert all("ADD COLUMN IF NOT EXISTS source_event_key" in c[1][0] and not c[3] for c in adds)
    names_up = [c[0] for c in state["calls"]]
    assert max(i for i, n in enumerate(names_up) if n == "execute") < min(
        i for i, n in enumerate(names_up) if n == "create_index")

    state["calls"].clear()
    module.downgrade()
    drops = [c for c in state["calls"] if c[0] == "drop_index"]
    assert len(drops) == 2 and all(c[2]["postgresql_concurrently"] and c[3] for c in drops)
    # Indexes are dropped before their columns.
    names = [c[0] for c in state["calls"]]
    assert max(i for i, n in enumerate(names) if n == "drop_index") < min(
        i for i, n in enumerate(names) if n == "drop_column")
