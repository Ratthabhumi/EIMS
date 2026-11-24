"""Hermetic contracts: NOGROUP self-healing (telemetry broker + EVTX worker), asset row locking
during brute-force quarantine, and the 4625 partial index migration/model parity.

No Redis/PostgreSQL. Redis and the DB are in-memory fakes; the real FOR UPDATE / index SQL is
only asserted on compiled statement text, never executed.
"""
import asyncio
import importlib.util
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from redis.exceptions import ResponseError
from sqlalchemy.dialects import postgresql

from backend.domain.telemetry import evtx_worker as evtx_module
from backend.domain.telemetry.broker import (
    TELEMETRY_CONSUMER_GROUP, TELEMETRY_STREAM_KEY, RedisTelemetryStreamBroker, is_nogroup_error,
)
from backend.domain.telemetry.models import TelemetryAlertOutbox, WindowsEventLog
from backend.domain.telemetry.worker import TelemetryStreamConsumer
from backend.infrastructure.cache import AsynchronousCacheManager
from tests.test_evtx_worker_fault_contracts import FakeStreamRedis, _job, _worker
from tests.test_telemetry_reliability_fixes import FakeResult

ROOT = Path(__file__).resolve().parents[1]
NOGROUP = "NOGROUP No such key 'x' or consumer group 'y' in XREADGROUP with GROUP option"
NOW = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)


# --- A: NOGROUP, telemetry broker -----------------------------------------------

class FakeTelemetryRedis:
    def __init__(self):
        self.group_exists = False
        self.create_calls = 0
        self.fail_next_read_with = None
        self.create_error = None
        self.reads = 0
        self.autoclaims = 0

    async def xgroup_create(self, name, groupname, id="0-0", mkstream=True):
        self.create_calls += 1
        if self.create_error is not None:
            raise self.create_error
        if self.group_exists:
            raise ResponseError("BUSYGROUP Consumer Group name already exists")
        self.group_exists = True

    async def xautoclaim(self, **kwargs):
        self.autoclaims += 1
        if self.fail_next_read_with is not None:
            exc, self.fail_next_read_with = self.fail_next_read_with, None
            raise exc
        return "0-0", [], []

    async def xreadgroup(self, **kwargs):
        self.reads += 1
        return [[TELEMETRY_STREAM_KEY, [("1-0", {"event_type": "heartbeat"})]]]


def _broker(redis_client):
    cache = AsynchronousCacheManager()
    cache._redis_client = redis_client
    return RedisTelemetryStreamBroker(cache, reclaim_idle_ms=0)


def test_is_nogroup_error_matches_only_nogroup_response_errors():
    assert is_nogroup_error(ResponseError(NOGROUP))
    assert is_nogroup_error(ResponseError("nogroup lowercase"))
    assert not is_nogroup_error(ResponseError("WRONGTYPE bad key"))
    assert not is_nogroup_error(RuntimeError(NOGROUP))


@pytest.mark.asyncio
async def test_broker_nogroup_invalidates_flag_recreates_group_and_next_poll_reads():
    redis = FakeTelemetryRedis()
    broker = _broker(redis)
    messages, _, signal = await broker.fetch_stream_batch(TELEMETRY_STREAM_KEY, "0", 10)
    assert signal is None and len(messages) == 1
    identity = (TELEMETRY_STREAM_KEY, TELEMETRY_CONSUMER_GROUP)
    assert identity in broker._ready_groups and redis.create_calls == 1

    # Redis loses the stream/group; the broker's cached flag is now stale.
    redis.group_exists = False
    redis.fail_next_read_with = ResponseError(NOGROUP)
    other = ("other-stream", TELEMETRY_CONSUMER_GROUP)
    broker._ready_groups.add(other)

    messages, _, signal = await broker.fetch_stream_batch(TELEMETRY_STREAM_KEY, "0", 10)
    assert messages == [] and signal == "group-recreated"
    assert redis.create_calls == 2 and redis.group_exists  # recreated with mkstream
    assert identity in broker._ready_groups  # re-validated by the recreate
    assert other in broker._ready_groups  # unrelated group untouched
    assert redis.reads == 1  # healing did not itself read/ack/drop anything

    messages, _, signal = await broker.fetch_stream_batch(TELEMETRY_STREAM_KEY, "0", 10)
    assert signal is None and len(messages) == 1


@pytest.mark.asyncio
async def test_broker_nogroup_recreate_accepts_busygroup_race():
    redis = FakeTelemetryRedis()
    broker = _broker(redis)
    await broker.fetch_stream_batch(TELEMETRY_STREAM_KEY, "0", 10)
    redis.fail_next_read_with = ResponseError(NOGROUP)
    # Another consumer already recreated it: group_exists stays True -> BUSYGROUP on our create.
    _, _, signal = await broker.fetch_stream_batch(TELEMETRY_STREAM_KEY, "0", 10)
    assert signal == "group-recreated"
    assert (TELEMETRY_STREAM_KEY, TELEMETRY_CONSUMER_GROUP) in broker._ready_groups


@pytest.mark.asyncio
async def test_broker_recreate_failure_keeps_flag_cleared_and_is_not_a_tight_loop():
    redis = FakeTelemetryRedis()
    broker = _broker(redis)
    await broker.fetch_stream_batch(TELEMETRY_STREAM_KEY, "0", 10)
    redis.fail_next_read_with = ResponseError(NOGROUP)
    redis.create_error = ConnectionError("redis down")
    before = redis.create_calls
    messages, _, signal = await broker.fetch_stream_batch(TELEMETRY_STREAM_KEY, "0", 10)
    assert messages == [] and signal == "group-recreated"
    assert redis.create_calls == before + 1  # exactly one attempt per poll, no inner retry loop
    assert (TELEMETRY_STREAM_KEY, TELEMETRY_CONSUMER_GROUP) not in broker._ready_groups

    redis.create_error = None  # next poll: _ensure_group retries and polling resumes
    messages, _, signal = await broker.fetch_stream_batch(TELEMETRY_STREAM_KEY, "0", 10)
    assert signal is None and len(messages) == 1


@pytest.mark.asyncio
async def test_broker_non_nogroup_response_error_does_not_invalidate_group():
    redis = FakeTelemetryRedis()
    broker = _broker(redis)
    await broker.fetch_stream_batch(TELEMETRY_STREAM_KEY, "0", 10)
    redis.fail_next_read_with = ResponseError("WRONGTYPE Operation against a key")
    before = redis.create_calls
    _, _, signal = await broker.fetch_stream_batch(TELEMETRY_STREAM_KEY, "0", 10)
    assert signal == "stream-read-error"
    assert redis.create_calls == before
    assert (TELEMETRY_STREAM_KEY, TELEMETRY_CONSUMER_GROUP) in broker._ready_groups


# --- A: NOGROUP, EVTX worker -----------------------------------------------------

class NoGroupOnceRedis(FakeStreamRedis):
    def __init__(self, *entries):
        super().__init__(*entries)
        self.create_calls = 0
        self.nogroup_pending = False

    async def xgroup_create(self, name, groupname, id="0-0", mkstream=True):
        self.create_calls += 1
        return await super().xgroup_create(name, groupname, id, mkstream)

    async def xautoclaim(self, *args, **kwargs):
        if self.nogroup_pending:
            self.nogroup_pending = False
            raise ResponseError(NOGROUP)
        return await super().xautoclaim(*args, **kwargs)


@pytest.mark.asyncio
async def test_evtx_nogroup_invalidates_flag_recreates_group_then_next_poll_processes(monkeypatch):
    redis = NoGroupOnceRedis(_job())
    worker, _, _ = _worker(monkeypatch, redis_client=redis)
    monkeypatch.setattr(evtx_module, "parse_evtx_records", lambda _: [])
    await worker._process_pending_tasks()  # job 1 processed on a healthy group
    assert worker._group_ready and redis.create_calls == 1
    redis.entries.append(("3000-0", {"payload": _job()}))

    redis.groups.clear()
    redis.nogroup_pending = True
    await worker._process_pending_tasks()  # NOGROUP: heal, do not raise, do not consume
    assert worker._group_ready and redis.create_calls == 2
    assert redis.groups  # recreated
    assert "3000-0" not in redis.pending and "3000-0" not in redis.acked  # nothing dropped/acked

    await worker._process_pending_tasks()  # next poll resumes
    assert "3000-0" in redis.acked


@pytest.mark.asyncio
async def test_evtx_recreate_failure_clears_flag_single_attempt_then_recovers(monkeypatch):
    redis = NoGroupOnceRedis(_job())
    worker, _, _ = _worker(monkeypatch, redis_client=redis)
    monkeypatch.setattr(evtx_module, "parse_evtx_records", lambda _: [])
    await worker._process_pending_tasks()
    redis.nogroup_pending = True
    real_create = redis.xgroup_create

    async def failing_create(*a, **k):
        redis.create_calls += 1
        raise ConnectionError("redis down")

    redis.xgroup_create = failing_create
    before = redis.create_calls
    await worker._process_pending_tasks()  # must not raise or spin
    assert redis.create_calls == before + 1 and worker._group_ready is False

    redis.xgroup_create = real_create
    await worker._process_pending_tasks()
    assert worker._group_ready is True


@pytest.mark.asyncio
async def test_evtx_non_nogroup_response_error_still_propagates_and_keeps_flag(monkeypatch):
    redis = NoGroupOnceRedis(_job())
    worker, _, _ = _worker(monkeypatch, redis_client=redis)
    monkeypatch.setattr(evtx_module, "parse_evtx_records", lambda _: [])
    await worker._process_pending_tasks()

    async def wrongtype(*a, **k):
        raise ResponseError("WRONGTYPE nope")

    redis.xautoclaim = wrongtype
    with pytest.raises(ResponseError):
        await worker._process_pending_tasks()
    assert worker._group_ready is True


@pytest.mark.asyncio
async def test_evtx_loop_nogroup_from_other_call_clears_flag_and_sleeps_between_passes(monkeypatch):
    redis = NoGroupOnceRedis()
    worker, _, _ = _worker(monkeypatch, redis_client=redis)
    monkeypatch.setattr(evtx_module, "parse_evtx_records", lambda _: [])
    worker.polling_interval = 7
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)
        worker._running = False

    monkeypatch.setattr(evtx_module.asyncio, "sleep", fake_sleep)
    worker._group_ready = True

    async def boom():
        raise ResponseError(NOGROUP)

    worker._process_pending_tasks = boom
    worker._running = True
    await worker._loop()
    assert worker._group_ready is False and sleeps == [7]  # backoff preserved: no tight loop


# --- B: asset row lock -------------------------------------------------------------

def _logon_items(asset_id, n, ip="203.0.113.7", base=0):
    return [SimpleNamespace(asset_id=asset_id, event_id=4625,
                            occurrence_time=NOW + timedelta(seconds=base + i),
                            evtx_metadata={"source_network_ip": ip}) for i in range(n)]


def _consumer():
    return TelemetryStreamConsumer(broker=RedisTelemetryStreamBroker(AsynchronousCacheManager()))


class LockingSession:
    """Models a consumer's DB transaction: FOR UPDATE on the asset row blocks until the holder
    commits; a plain SELECT does not. Counts see committed rows plus this session's staged rows."""

    def __init__(self, shared, staged_rows):
        self.shared = shared
        self.staged = list(staged_rows)
        self.added = []
        self.holds_lock = False
        self.statements = []
        self.private_asset = None  # uncommitted per-transaction view of the asset row

    def add(self, obj):
        self.added.append(obj)

    async def execute(self, stmt):
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        self.statements.append(sql)
        await asyncio.sleep(0)
        if "FOR UPDATE" in sql and not self.holds_lock:
            await self.shared["lock"].acquire()
            self.holds_lock = True
        await asyncio.sleep(0)
        committed = self.shared["asset"]
        if committed is not None and self.private_asset is None:
            self.private_asset = SimpleNamespace(**vars(committed))  # snapshot at read time
        return FakeResult(self.private_asset)

    def commit(self):
        if self.private_asset is not None:
            vars(self.shared["asset"]).update(vars(self.private_asset))
        self.shared["rows"].extend(self.staged)
        self.shared["audit"].extend(o for o in self.added if not isinstance(o, TelemetryAlertOutbox))
        self.shared["outbox"].extend(o for o in self.added if isinstance(o, TelemetryAlertOutbox))
        if self.holds_lock:
            self.holds_lock = False
            self.shared["lock"].release()


def _shared(asset_id):
    return {"lock": asyncio.Lock(), "rows": [], "audit": [], "outbox": [],
            "asset": SimpleNamespace(asset_id=asset_id, lifecycle_state="Active", current_compliance_score=100)}


async def _run_consumer(shared, items):
    consumer = _consumer()
    session = LockingSession(shared, items)

    async def count(sess, ip, window_end, window_start, *, asset_id=None):
        await asyncio.sleep(0)
        visible = shared["rows"] + sess.staged
        return sum(1 for r in visible if window_start <= r.occurrence_time <= window_end
                   and r.evtx_metadata.get("source_network_ip") == ip
                   and (asset_id is None or r.asset_id == asset_id))

    consumer._count_failed_logons = count
    alerts = await consumer._detect_brute_force(session, items)
    await asyncio.sleep(0)
    session.commit()
    return alerts, session


@pytest.mark.asyncio
@pytest.mark.parametrize("per_consumer", [3, 6])  # 3+3 only crosses the threshold jointly; 6+6 each alone
async def test_two_concurrent_consumers_produce_exactly_one_quarantine_transition(per_consumer):
    asset_id = uuid.uuid4()
    shared = _shared(asset_id)
    a = _logon_items(asset_id, per_consumer, base=0)
    b = _logon_items(asset_id, per_consumer, base=10)
    (alerts_a, _), (alerts_b, _) = await asyncio.gather(
        _run_consumer(shared, a), _run_consumer(shared, b))
    assert len(alerts_a) + len(alerts_b) == 1
    assert len(shared["audit"]) == 1 and len(shared["outbox"]) == 1
    assert shared["asset"].lifecycle_state == "Quarantined"
    assert shared["asset"].current_compliance_score == 70  # penalty applied once


@pytest.mark.asyncio
async def test_asset_lookup_uses_for_update_and_only_asset_rows_are_locked():
    asset_id = uuid.uuid4()
    shared = _shared(asset_id)
    _, session = await _run_consumer(shared, _logon_items(asset_id, 6))
    assert session.statements, "asset lookup must run"
    assert all("FOR UPDATE" in s and "infrastructure_assets" in s for s in session.statements)
    assert all("SKIP LOCKED" not in s for s in session.statements)


@pytest.mark.asyncio
async def test_lock_taken_before_count_so_waiting_consumer_counts_committed_rows():
    asset_id = uuid.uuid4()
    shared = _shared(asset_id)
    order = []
    consumer = _consumer()
    session = LockingSession(shared, _logon_items(asset_id, 6))
    original = session.execute

    async def traced(stmt):
        order.append("lock")
        return await original(stmt)

    async def count(*a, **kwargs):
        order.append("count")
        return 6

    session.execute, consumer._count_failed_logons = traced, count
    await consumer._detect_brute_force(session, session.staged)
    session.commit()
    assert order == ["lock", "count"]


@pytest.mark.asyncio
async def test_unresolved_asset_is_skipped_without_alert_or_error():
    asset_id = uuid.uuid4()
    shared = _shared(asset_id)
    shared["asset"] = None
    alerts, session = await _run_consumer(shared, _logon_items(asset_id, 6))
    assert alerts == [] and session.added == []


@pytest.mark.asyncio
async def test_already_quarantined_asset_creates_no_duplicate_alert():
    asset_id = uuid.uuid4()
    shared = _shared(asset_id)
    shared["asset"].lifecycle_state = "Quarantined"
    alerts, session = await _run_consumer(shared, _logon_items(asset_id, 6))
    assert alerts == [] and session.added == []


@pytest.mark.asyncio
async def test_assets_are_locked_in_sorted_order_to_avoid_deadlocks():
    low, high = uuid.UUID(int=1), uuid.UUID(int=2)
    seen = []

    class S:
        def add(self, obj): ...

        async def execute(self, stmt):
            seen.append(next(iter(stmt.compile().params.values())))
            return FakeResult(None)

    consumer = _consumer()
    items = _logon_items(high, 1, ip="198.51.100.1") + _logon_items(low, 1, ip="198.51.100.2")

    async def count(*a, **kwargs):
        return 0

    consumer._count_failed_logons = count
    await consumer._detect_brute_force(S(), items)
    assert seen == [low, high]


# --- C: 4625 partial index ------------------------------------------------------------

def _load_index_migration():
    path = next((ROOT / "migrations" / "versions").glob("a3d6f1e8c295_*.py"))
    spec = importlib.util.spec_from_file_location("winlog_4625_index_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_count_query_inlines_4625_and_extracts_source_ip_text_matching_index():
    captured = {}

    class Session:
        async def execute(self, stmt):
            captured["sql"] = str(stmt.compile(dialect=postgresql.dialect(),
                                               compile_kwargs={"literal_binds": False}))
            return FakeResult(0)

    asyncio.run(TelemetryStreamConsumer._count_failed_logons(Session(), "203.0.113.7", NOW, NOW))
    sql = captured["sql"]
    assert "event_id = 4625" in sql  # literal => partial-index predicate provable in generic plans
    assert "windows_event_logs.evtx_metadata ->> " in sql


def test_index_migration_is_concurrent_partial_functional_and_reversible():
    module = _load_index_migration()
    assert module.down_revision == "f7b3d91c4a58" and "Revises: f7b3d91c4a58" in module.__doc__
    state = {"in_block": False, "calls": []}

    class Block:
        def __enter__(self):
            state["in_block"] = True

        def __exit__(self, *exc):
            state["in_block"] = False

    fake_op = MagicMock()
    fake_op.get_context.return_value.autocommit_block = Block
    for name in ("create_index", "drop_index"):
        getattr(fake_op, name).side_effect = (
            lambda *a, _n=name, **k: state["calls"].append((_n, a, k, state["in_block"])))
    module.op = fake_op

    module.upgrade()
    assert [c[0] for c in state["calls"]] == ["drop_index", "create_index"]  # invalid leftover cleared first
    assert all(c[3] for c in state["calls"])
    drop, create = state["calls"]
    assert drop[2]["if_exists"] and drop[2]["postgresql_concurrently"]
    assert create[1][0] == "idx_winlog_4625_src_ip_time" and create[1][1] == "windows_event_logs"
    assert str(create[1][2][0]) == "(evtx_metadata ->> 'source_network_ip')" and create[1][2][1] == "occurrence_time"
    assert create[2]["postgresql_concurrently"] and str(create[2]["postgresql_where"]) == "event_id = 4625"

    state["calls"].clear()
    module.downgrade()
    assert [c[0] for c in state["calls"]] == ["drop_index"] and state["calls"][0][3]


def test_orm_index_matches_migration():
    index = next(i for i in WindowsEventLog.__table__.indexes if i.name == "idx_winlog_4625_src_ip_time")
    assert str(index.dialect_options["postgresql"]["where"]) == "event_id = 4625"
    exprs = [str(e) for e in index.expressions]
    assert exprs == ["(evtx_metadata ->> 'source_network_ip')", "windows_event_logs.occurrence_time"]
    assert not index.unique
