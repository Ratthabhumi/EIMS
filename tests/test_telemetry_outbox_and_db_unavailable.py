"""Hermetic contracts for P1-B (DB session maker missing) and P1-C (transactional alert outbox).

Reuses the in-memory FakeDB/FakeSession from test_telemetry_reliability_fixes. No Redis/PostgreSQL;
the SKIP LOCKED claim is verified by compiling the statement for the PostgreSQL dialect.
"""
import asyncio
import importlib.util
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError

from backend.domain.telemetry import worker as worker_module
from backend.domain.telemetry.broker import (
    TELEMETRY_STREAM_KEY,
    RedisTelemetryStreamBroker,
    StubTelemetryStreamBroker,
)
from backend.domain.telemetry.models import TelemetryAlertOutbox
from backend.domain.telemetry.worker import TelemetryStreamConsumer
from backend.infrastructure.cache import AsynchronousCacheManager
from tests.test_telemetry_reliability_fixes import (
    FakeDB,
    FakeResult,
    _failed_logon,
    _feed,
    _heartbeat,
    _wire,
)

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "migrations" / "versions"


def _quarantine_batch():
    return [_failed_logon(f"k-{i}", offset=i) for i in range(6)]


# --- P1-B ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_session_maker_leaves_message_pending_no_dlq_no_ack(monkeypatch):
    monkeypatch.setattr(worker_module.database_engine, "get_session_maker", lambda: None)
    broker = RedisTelemetryStreamBroker(AsynchronousCacheManager())
    broker.dead_letter_stream_message = AsyncMock()
    broker.ack_stream_messages = AsyncMock()
    consumer = TelemetryStreamConsumer(broker=broker)
    _feed(consumer, _heartbeat("k-unknown", "f" * 64))

    with pytest.raises(worker_module.DatabaseUnavailableError):
        await consumer.process_batch()

    broker.dead_letter_stream_message.assert_not_awaited()
    broker.ack_stream_messages.assert_not_awaited()
    assert consumer._last_id == "0-0"


@pytest.mark.asyncio
async def test_stub_broker_without_session_maker_keeps_unresolved_behavior(monkeypatch):
    monkeypatch.setattr(worker_module.database_engine, "get_session_maker", lambda: None)
    consumer = TelemetryStreamConsumer(broker=StubTelemetryStreamBroker())
    with pytest.raises(worker_module.UnresolvedAssetError):
        await consumer._resolve_asset("f" * 64)


# --- P1-C: outbox semantics ----------------------------------------------------

@pytest.mark.asyncio
async def test_outbox_row_written_in_same_transaction_as_quarantine(monkeypatch):
    db = FakeDB()
    consumer, broker = _wire(monkeypatch, db)
    consumer.redis_down = True  # Redis unavailable: source event is still ACKed (alert is durable)
    _feed(consumer, *_quarantine_batch())

    await consumer.process_batch()

    assert db.asset.lifecycle_state == "Quarantined" and len(db.audit_logs) == 1
    assert len(db.outbox) == 1
    row = next(iter(db.outbox.values()))
    assert row.published_at is None and row.payload["severity"] == "Critical"
    assert row.alert_id is not None and row.created_at is not None
    broker.ack_stream_messages.assert_awaited_once()


@pytest.mark.asyncio
async def test_rollback_leaves_neither_quarantine_audit_nor_outbox(monkeypatch):
    db = FakeDB()
    db.fail_commit = True
    consumer, broker = _wire(monkeypatch, db)
    _feed(consumer, *_quarantine_batch())

    with pytest.raises(OperationalError):
        await consumer.process_batch()

    assert db.audit_logs == [] and db.outbox == {} and db.winlogs == {}
    assert consumer.xadds == [] and consumer.published == []
    broker.ack_stream_messages.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_redis_publish_before_commit(monkeypatch):
    ok = FakeDB()
    consumer, _ = _wire(monkeypatch, ok)
    _feed(consumer, *_quarantine_batch())
    await consumer.process_batch()
    assert consumer.xadds and consumer.xadd_db_state == [(1, 1)]  # rows committed before XADD

    failing = FakeDB()
    failing.fail_commit = True
    consumer2, _ = _wire(monkeypatch, failing)
    _feed(consumer2, *_quarantine_batch())
    with pytest.raises(OperationalError):
        await consumer2.process_batch()
    assert consumer2.xadds == [] and consumer2.published == []


@pytest.mark.asyncio
async def test_redis_outage_leaves_outbox_pending_then_later_dispatch_publishes(monkeypatch):
    db = FakeDB()
    consumer, _ = _wire(monkeypatch, db)
    consumer.redis_down = True
    _feed(consumer, *_quarantine_batch())
    await consumer.process_batch()  # does not raise
    row = next(iter(db.outbox.values()))
    assert row.published_at is None and consumer.xadds == []

    consumer.redis_down = False
    consumer._fetch_batch = AsyncMock(return_value=([], TELEMETRY_STREAM_KEY, None))  # no telemetry
    await consumer.process_batch()

    assert row.published_at is not None and len(consumer.xadds) == 1
    entry = consumer.xadds[0]
    assert entry["key"] == worker_module.ALERT_STREAM_KEY
    assert entry["alert_id"] == str(row.alert_id)
    assert json.loads(entry["payload"])["alert_id"] == str(row.alert_id)

    await consumer.process_batch()  # already published: not re-sent
    assert len(consumer.xadds) == 1


@pytest.mark.asyncio
async def test_unconfirmed_xadd_keeps_row_pending(monkeypatch):
    db = FakeDB()
    consumer, _ = _wire(monkeypatch, db)
    consumer._redis.xadd = AsyncMock(return_value=None)
    _feed(consumer, *_quarantine_batch())
    await consumer.process_batch()
    assert next(iter(db.outbox.values())).published_at is None


@pytest.mark.asyncio
async def test_pubsub_failure_does_not_erase_durable_record(monkeypatch):
    db = FakeDB()
    consumer, _ = _wire(monkeypatch, db)
    consumer.pubsub_down = True
    _feed(consumer, *_quarantine_batch())
    await consumer.process_batch()
    assert len(consumer.xadds) == 1
    assert next(iter(db.outbox.values())).published_at is not None


@pytest.mark.asyncio
async def test_duplicate_replay_does_not_create_duplicate_outbox_row(monkeypatch):
    db = FakeDB()
    consumer, _ = _wire(monkeypatch, db)
    batch = _quarantine_batch()
    _feed(consumer, *batch)
    await consumer.process_batch()
    _feed(consumer, *batch)  # commit succeeded, ACK lost
    await consumer.process_batch()
    _feed(consumer, *batch, _failed_logon("k-6", offset=6))
    await consumer.process_batch()
    assert len(db.outbox) == 1 and len(db.audit_logs) == 1 and len(consumer.xadds) == 1


def test_outbox_claim_query_uses_skip_locked_so_dispatchers_do_not_share_rows():
    captured = {}

    class Session:
        def begin(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            captured["sql"] = str(stmt.compile(dialect=postgresql.dialect()))
            return FakeResult([])

    consumer = TelemetryStreamConsumer(broker=RedisTelemetryStreamBroker(AsynchronousCacheManager()))
    consumer._redis = SimpleNamespace()
    asyncio.run(consumer.dispatch_outbox(lambda: Session()))
    assert "FOR UPDATE SKIP LOCKED" in captured["sql"]
    assert "published_at IS NULL" in captured["sql"]


# --- P1-C: migration + model ---------------------------------------------------

def _load_outbox_migration():
    path = next(VERSIONS.glob("f7b3d91c4a58_*.py"))
    spec = importlib.util.spec_from_file_location("telemetry_outbox_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_outbox_migration_follows_e4a9_and_is_single_head():
    module = _load_outbox_migration()
    assert module.revision == "f7b3d91c4a58" and module.down_revision == "e4a9c8b12d77"
    assert "Revises: e4a9c8b12d77" in module.__doc__
    rev_re = re.compile(r"^revision\s*(?::[^=]+)?=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
    down_re = re.compile(r"^down_revision\s*(?::[^=]+)?=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
    revs, downs = set(), set()
    for path in VERSIONS.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        revs.update(rev_re.findall(text))
        downs.update(down_re.findall(text))
    # Exactly one head (the latest migration changes; do not pin it). The knowledge-usage migration d2f6 is in the lineage.
    assert len(revs - downs) == 1 and "d2f6b8c1e305" in revs
    assert "a3d6f1e8c295" in downs
    assert "f7b3d91c4a58" in downs


def test_outbox_migration_creates_and_drops_table_and_partial_index():
    module = _load_outbox_migration()
    fake_op = MagicMock()
    module.op = fake_op
    module.upgrade()
    create = fake_op.create_table.call_args
    assert create.args[0] == "telemetry_alert_outbox"
    cols = {c.name: c for c in create.args[1:] if hasattr(c, "nullable")}
    assert set(cols) == {"alert_id", "payload", "created_at", "published_at"}
    assert cols["published_at"].nullable is True
    assert not any(cols[n].nullable for n in ("alert_id", "payload", "created_at"))
    assert any(getattr(c, "name", None) == "pk_telemetry_alert_outbox" for c in create.args)
    index = fake_op.create_index.call_args
    assert index.args[:3] == ("idx_telemetry_alert_outbox_pending", "telemetry_alert_outbox", ["created_at"])
    assert str(index.kwargs["postgresql_where"]) == "published_at IS NULL"

    fake_op.reset_mock()
    module.downgrade()
    assert [c[0] for c in fake_op.method_calls] == ["drop_index", "drop_table"]


def test_outbox_orm_model_matches_migration():
    table = TelemetryAlertOutbox.__table__
    assert table.name == "telemetry_alert_outbox"
    assert [c.name for c in table.primary_key.columns] == ["alert_id"]
    assert table.c.published_at.nullable
    assert not table.c.payload.nullable and not table.c.created_at.nullable
    assert "idx_telemetry_alert_outbox_pending" in {i.name for i in table.indexes}


@pytest.mark.asyncio
async def test_outbox_releases_database_transaction_before_redis_io():
    row = SimpleNamespace(
        alert_id=__import__("uuid").uuid4(),
        payload={"event_type": "SYNTHETIC_ALERT"},
        created_at=None,
        published_at=None,
    )
    transaction_state = {"active": False, "xadd_seen": False}

    class Tx:
        async def __aenter__(self):
            transaction_state["active"] = True
            return self
        async def __aexit__(self, *exc):
            transaction_state["active"] = False
            return False

    class Session:
        def begin(self):
            return Tx()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *exc):
            return False
        async def execute(self, stmt):
            if str(stmt).lower().startswith("select"):
                return FakeResult([row])
            return FakeResult([])

    class Redis:
        async def xadd(self, *args, **kwargs):
            assert transaction_state["active"] is False
            transaction_state["xadd_seen"] = True
            return "1-0"
        async def publish(self, *args, **kwargs):
            assert transaction_state["active"] is False

    consumer = TelemetryStreamConsumer(broker=RedisTelemetryStreamBroker(AsynchronousCacheManager()))
    consumer._redis = Redis()
    assert await consumer.dispatch_outbox(lambda: Session()) == 1
    assert transaction_state["xadd_seen"] is True
