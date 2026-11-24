"""Hermetic tests for the database health probe lifecycle and diagnostics."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

import backend.infrastructure.database as database_module
from backend.infrastructure.database import AsynchronousDatabaseEngine

DSN = "postgresql+asyncpg://user:hunter2@db.invalid:6432/eims"


class _ConnectionContext:
    def __init__(self, conn=None, enter_side_effect=None, exit_side_effect=None):
        self.conn = conn or MagicMock()
        self.enter_side_effect = enter_side_effect
        self.exit_side_effect = exit_side_effect
        self.entered = False
        self.exited = False
        self.conn.execute = AsyncMock(return_value=MagicMock())
        self.conn.execute.return_value.scalar_one.return_value = 1

    async def __aenter__(self):
        if self.enter_side_effect:
            await self.enter_side_effect()
        self.entered = True
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if self.exit_side_effect:
                await self.exit_side_effect()
        finally:
            self.exited = True
        return False


def _engine_with(context=None):
    eng = AsynchronousDatabaseEngine()
    fake = MagicMock()
    fake.connect = MagicMock(return_value=context or _ConnectionContext())
    fake.pool.status.return_value = "Pool size: 5 Connections in pool: 0"
    eng._engine = fake
    return eng


def _run(eng):
    return asyncio.run(eng.ping())


def _short_deadline(monkeypatch):
    monkeypatch.setattr(database_module, "_DB_PING_TIMEOUT_SECONDS", 0.03)


def test_health_probe_uses_dedicated_pool_when_configured():
    request_engine = _engine_with()
    health_engine = _engine_with()
    request_engine._health_engine = health_engine._engine

    assert _run(request_engine) is True
    request_engine._engine.connect.assert_not_called()
    health_engine._engine.connect.assert_called_once_with()


def test_health_pool_avoids_duplicate_pre_ping_before_explicit_select_one(monkeypatch):
    request_pool = MagicMock(name="request_pool")
    health_pool = MagicMock(name="health_pool")
    create_engine = MagicMock(side_effect=[request_pool, health_pool])
    monkeypatch.setattr(database_module, "create_async_engine", create_engine)
    engine = AsynchronousDatabaseEngine()

    asyncio.run(engine.initialize())

    assert create_engine.call_count == 2
    assert create_engine.call_args_list[0].kwargs["pool_pre_ping"] is True
    assert create_engine.call_args_list[1].kwargs["pool_pre_ping"] is False
    assert create_engine.call_args_list[1].kwargs["pool_timeout"] == 1.0


def test_checkout_failure_logged_as_checkout(caplog):
    async def fail_checkout():
        raise ConnectionRefusedError(DSN)

    context = _ConnectionContext(enter_side_effect=fail_checkout)
    eng = _engine_with(context)
    with caplog.at_level("ERROR", logger="eims.infrastructure.database"):
        assert _run(eng) is False
    assert "phase=checkout" in caplog.text
    assert "ConnectionRefusedError" in caplog.text
    assert "Pool size" in caplog.text
    assert "hunter2" not in caplog.text and "db.invalid" not in caplog.text
    assert context.exited is False


def test_stalled_pool_checkout_is_bounded(monkeypatch, caplog):
    _short_deadline(monkeypatch)
    started = asyncio.Event()

    async def stall_checkout():
        started.set()
        await asyncio.Event().wait()

    context = _ConnectionContext(enter_side_effect=stall_checkout)
    eng = _engine_with(context)

    async def scenario():
        with caplog.at_level("ERROR", logger="eims.infrastructure.database"):
            result = await eng.ping()
        return result

    assert asyncio.run(scenario()) is False
    assert started.is_set()
    assert "phase=checkout" in caplog.text
    assert "checkout=n/a" not in caplog.text
    assert context.exited is False


def test_select_timeout_logged_as_execute(monkeypatch, caplog):
    _short_deadline(monkeypatch)
    context = _ConnectionContext()
    context.conn.execute.side_effect = TimeoutError()
    eng = _engine_with(context)
    with caplog.at_level("ERROR", logger="eims.infrastructure.database"):
        assert _run(eng) is False
    assert "phase=execute" in caplog.text
    assert "TimeoutError" in caplog.text
    assert "deadline_expired=False" in caplog.text
    assert context.exited is True


def test_stalled_select_is_bounded_and_connection_context_exits(monkeypatch, caplog):
    _short_deadline(monkeypatch)
    started = asyncio.Event()
    context = _ConnectionContext()

    async def stall_execute(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    context.conn.execute.side_effect = stall_execute
    eng = _engine_with(context)

    async def scenario():
        with caplog.at_level("ERROR", logger="eims.infrastructure.database"):
            return await eng.ping()

    assert asyncio.run(scenario()) is False
    assert started.is_set()
    assert "phase=execute" in caplog.text
    assert context.exited is True


def test_cleanup_failure_logged_as_cleanup(caplog):
    async def fail_cleanup():
        raise RuntimeError(DSN)

    context = _ConnectionContext(exit_side_effect=fail_cleanup)
    eng = _engine_with(context)
    with caplog.at_level("ERROR", logger="eims.infrastructure.database"):
        assert _run(eng) is False
    assert "phase=cleanup" in caplog.text
    assert "hunter2" not in caplog.text
    assert context.exited is True


def test_deadline_waits_for_cancellation_safe_cleanup(monkeypatch, caplog):
    _short_deadline(monkeypatch)
    cleanup_cancelled = asyncio.Event()
    release_cleanup = asyncio.Event()

    async def stall_cleanup():
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cleanup_cancelled.set()
            await release_cleanup.wait()
            raise

    context = _ConnectionContext(exit_side_effect=stall_cleanup)
    eng = _engine_with(context)

    async def scenario():
        with caplog.at_level("ERROR", logger="eims.infrastructure.database"):
            task = asyncio.create_task(eng.ping())
            await asyncio.wait_for(cleanup_cancelled.wait(), timeout=1.0)
            assert not task.done()
            release_cleanup.set()
            return await task

    assert asyncio.run(scenario()) is False
    assert "phase=cleanup" in caplog.text
    assert "deadline_expired=True" in caplog.text
    assert context.exited is True


def test_external_cancellation_propagates_after_context_cleanup():
    started = asyncio.Event()
    context = _ConnectionContext()

    async def wait_for_cancellation(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    context.conn.execute.side_effect = wait_for_cancellation
    eng = _engine_with(context)

    async def scenario():
        task = asyncio.create_task(eng.ping())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert context.exited is True


def test_rollback_read_only_transaction_releases_clean_engine_session(monkeypatch):
    class FakeEngine:
        pass

    class FakeSession:
        bind = FakeEngine()
        active = True
        new = set()
        dirty = set()
        deleted = set()
        rollbacks = 0

        def in_transaction(self):
            return self.active

        async def rollback(self):
            self.rollbacks += 1
            self.active = False

    monkeypatch.setattr(database_module, "AsyncEngine", FakeEngine)
    session = FakeSession()

    assert asyncio.run(database_module.rollback_read_only_transaction(session)) is True
    assert session.rollbacks == 1
    assert session.active is False


def test_rollback_read_only_transaction_refuses_pending_orm_changes(monkeypatch):
    class FakeEngine:
        pass

    class FakeSession:
        bind = FakeEngine()
        active = True
        new = set()
        dirty = {object()}
        deleted = set()
        rollbacks = 0

        def in_transaction(self):
            return self.active

        async def rollback(self):
            self.rollbacks += 1
            self.active = False

    monkeypatch.setattr(database_module, "AsyncEngine", FakeEngine)
    session = FakeSession()

    assert asyncio.run(database_module.rollback_read_only_transaction(session)) is False
    assert session.rollbacks == 0
    assert session.active is True


def test_rollback_read_only_transaction_noops_without_transaction(monkeypatch):
    class FakeEngine:
        pass

    class FakeSession:
        bind = FakeEngine()
        active = False
        new = set()
        dirty = set()
        deleted = set()
        rollbacks = 0

        def in_transaction(self):
            return self.active

        async def rollback(self):
            self.rollbacks += 1

    monkeypatch.setattr(database_module, "AsyncEngine", FakeEngine)
    session = FakeSession()

    assert asyncio.run(database_module.rollback_read_only_transaction(session)) is True
    assert session.rollbacks == 0


def test_rollback_read_only_transaction_ignores_connection_bound_session(monkeypatch):
    class FakeEngine:
        pass

    monkeypatch.setattr(database_module, "AsyncEngine", FakeEngine)
    session = type("ConnectionBoundSession", (), {"bind": object()})()

    assert asyncio.run(database_module.rollback_read_only_transaction(session)) is None


def test_external_cancellation_during_cleanup_is_not_suppressed():
    cleanup_started = asyncio.Event()
    cleanup_cancelled = asyncio.Event()
    release_cleanup = asyncio.Event()

    async def wait_for_cleanup():
        cleanup_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cleanup_cancelled.set()
            await release_cleanup.wait()
            raise

    context = _ConnectionContext(exit_side_effect=wait_for_cleanup)
    eng = _engine_with(context)

    async def scenario():
        task = asyncio.create_task(eng.ping())
        await asyncio.wait_for(cleanup_started.wait(), timeout=1.0)
        task.cancel()
        await asyncio.wait_for(cleanup_cancelled.wait(), timeout=1.0)
        assert not task.done()
        release_cleanup.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert context.exited is True


def test_probe_recovers_after_checkout_timeout(monkeypatch):
    _short_deadline(monkeypatch)
    started = asyncio.Event()

    async def stall_checkout():
        started.set()
        await asyncio.Event().wait()

    failed_context = _ConnectionContext(enter_side_effect=stall_checkout)
    recovered_context = _ConnectionContext()
    eng = _engine_with(failed_context)
    eng._engine.connect.side_effect = [failed_context, recovered_context]

    async def scenario():
        assert await eng.ping() is False
        assert await eng.ping() is True

    asyncio.run(scenario())
    assert started.is_set()
    assert recovered_context.exited is True


def test_concurrent_health_probes_share_one_database_checkout():
    started = asyncio.Event()
    release = asyncio.Event()
    context = _ConnectionContext()
    result = context.conn.execute.return_value

    async def stall_execute(*args, **kwargs):
        started.set()
        await release.wait()
        return result

    context.conn.execute.side_effect = stall_execute
    eng = _engine_with(context)

    async def scenario():
        tasks = [asyncio.create_task(eng.ping()) for _ in range(8)]
        await started.wait()
        assert context.conn.execute.await_count == 1
        release.set()
        assert await asyncio.gather(*tasks) == [True] * 8

    asyncio.run(scenario())
    assert context.exited is True
    assert eng._ping_inflight is None


def test_cancelled_waiter_does_not_cancel_probe_shared_by_other_requests():
    started = asyncio.Event()
    release = asyncio.Event()
    context = _ConnectionContext()
    result = context.conn.execute.return_value

    async def stall_execute(*args, **kwargs):
        started.set()
        await release.wait()
        return result

    context.conn.execute.side_effect = stall_execute
    eng = _engine_with(context)

    async def scenario():
        first = asyncio.create_task(eng.ping())
        second = asyncio.create_task(eng.ping())
        await started.wait()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert not context.exited
        assert not second.done()
        release.set()
        assert await second is True

    asyncio.run(scenario())
    assert context.exited is True
    assert eng._ping_inflight is None


def test_success_returns_true_and_logs_nothing(caplog):
    eng = _engine_with()
    with caplog.at_level("ERROR", logger="eims.infrastructure.database"):
        assert _run(eng) is True
    assert caplog.text == ""


def test_pool_status_failure_does_not_escape(caplog):
    async def fail_checkout():
        raise OSError("x")

    eng = _engine_with(_ConnectionContext(enter_side_effect=fail_checkout))
    eng._engine.pool.status.side_effect = RuntimeError("boom")
    with caplog.at_level("ERROR", logger="eims.infrastructure.database"):
        assert _run(eng) is False
    assert "pool=unavailable" in caplog.text


def test_uninitialized_engine_returns_false():
    assert _run(AsynchronousDatabaseEngine()) is False
