import asyncio
import json
import time

import pytest

from backend import main
from backend.core.health_probe import HealthProbeCoordinator
from backend.infrastructure.object_store import object_storage


def test_health_probe_runs_independent_dependencies_concurrently(monkeypatch):
    async def delayed_ok():
        await asyncio.sleep(0.08)
        return True

    monkeypatch.setattr(main.database_engine, "ping", delayed_ok)
    monkeypatch.setattr(main.cache_manager, "ping", delayed_ok)
    monkeypatch.setattr(object_storage, "ping", delayed_ok)

    async def run():
        started = time.perf_counter()
        response = await main.read_system_health()
        elapsed = time.perf_counter() - started
        payload = json.loads(response.body)
        assert response.status_code == 200
        assert payload["status"] == "HEALTHY"
        assert all(value == "UP" for value in payload["components"].values())
        assert elapsed < 0.18, f"independent probes were serialized: {elapsed:.3f}s"

    monkeypatch.setattr(main, "_health_probe", HealthProbeCoordinator())
    asyncio.run(run())


def test_health_requests_share_inflight_probe_and_recent_snapshot(monkeypatch):
    calls = {"db": 0, "redis": 0, "minio": 0}

    async def probe(name):
        calls[name] += 1
        await asyncio.sleep(0.05)
        return True

    monkeypatch.setattr(main, "_health_probe", HealthProbeCoordinator())
    monkeypatch.setattr(main.database_engine, "ping", lambda: probe("db"))
    monkeypatch.setattr(main.cache_manager, "ping", lambda: probe("redis"))
    monkeypatch.setattr(object_storage, "ping", lambda: probe("minio"))

    async def run():
        responses = await asyncio.gather(*(main.read_system_health() for _ in range(8)))
        responses.append(await main.read_system_health())
        assert all(response.status_code == 200 for response in responses)
        assert calls == {"db": 1, "redis": 1, "minio": 1}

    asyncio.run(run())


def test_health_snapshot_expires_and_degraded_state_is_preserved(monkeypatch):
    calls = {"db": 0, "redis": 0, "minio": 0}

    async def probe(name, result):
        calls[name] += 1
        return result

    monkeypatch.setattr(main, "_health_probe", HealthProbeCoordinator(ttl_seconds=-1.0, degraded_ttl_seconds=-1.0))
    monkeypatch.setattr(main.database_engine, "ping", lambda: probe("db", False))
    monkeypatch.setattr(main.cache_manager, "ping", lambda: probe("redis", True))
    monkeypatch.setattr(object_storage, "ping", lambda: probe("minio", True))

    async def run():
        first = await main.read_system_health()
        second = await main.read_system_health()
        for response in (first, second):
            payload = json.loads(response.body)
            assert response.status_code == 503
            assert payload["status"] == "DEGRADED"
            assert payload["components"]["postgresql_pgbouncer_tier"] == "DOWN"
        assert calls == {"db": 2, "redis": 2, "minio": 2}

    asyncio.run(run())

def test_degraded_health_snapshot_is_cached_without_reporting_healthy(monkeypatch):
    calls = {"db": 0, "redis": 0, "minio": 0}

    async def probe(name, result):
        calls[name] += 1
        return result

    monkeypatch.setattr(main, "_health_probe", HealthProbeCoordinator(ttl_seconds=5.0))
    monkeypatch.setattr(main.database_engine, "ping", lambda: probe("db", False))
    monkeypatch.setattr(main.cache_manager, "ping", lambda: probe("redis", True))
    monkeypatch.setattr(object_storage, "ping", lambda: probe("minio", True))

    async def run():
        first = await main.read_system_health()
        second = await main.read_system_health()
        for response in (first, second):
            payload = json.loads(response.body)
            assert response.status_code == 503
            assert payload["status"] == "DEGRADED"
            assert payload["components"]["postgresql_pgbouncer_tier"] == "DOWN"
        assert calls == {"db": 1, "redis": 1, "minio": 1}

    asyncio.run(run())


def test_cancelled_health_waiter_does_not_cancel_shared_probe():
    coordinator = HealthProbeCoordinator()
    started = asyncio.Event()
    release = asyncio.Event()
    calls = {"db": 0, "redis": 0, "minio": 0}

    def make_probe(name):
        async def probe():
            calls[name] += 1
            started.set()
            await release.wait()
            return True
        return probe

    async def run():
        probes = (make_probe("db"), make_probe("redis"), make_probe("minio"))
        cancelled_waiter = asyncio.create_task(coordinator.check(*probes))
        await started.wait()
        surviving_waiter = asyncio.create_task(coordinator.check(*probes))
        await asyncio.sleep(0)
        cancelled_waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled_waiter
        release.set()
        assert await surviving_waiter == (True, True, True)
        assert calls == {"db": 1, "redis": 1, "minio": 1}

    asyncio.run(run())


def test_cancelled_health_waiter_does_not_cancel_shared_probe_after_short_wait():
    coordinator = HealthProbeCoordinator(ttl_seconds=5.0)
    calls = {"db": 0, "redis": 0, "minio": 0}

    async def probe(name):
        calls[name] += 1
        await asyncio.sleep(0.05)
        return True

    async def run():
        probes = (lambda: probe("db"), lambda: probe("redis"), lambda: probe("minio"))
        cancelled_waiter = asyncio.create_task(coordinator.check(*probes))
        await asyncio.sleep(0)
        surviving_waiter = asyncio.create_task(coordinator.check(*probes))
        await asyncio.sleep(0)
        cancelled_waiter.cancel()
        try:
            await cancelled_waiter
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("the cancelled waiter unexpectedly completed")
        assert await surviving_waiter == (True, True, True)
        assert calls == {"db": 1, "redis": 1, "minio": 1}

    asyncio.run(run())


def test_health_coordinator_resets_task_state_when_event_loop_restarts():
    coordinator = HealthProbeCoordinator(ttl_seconds=60.0)
    calls = {"db": 0, "redis": 0, "minio": 0}

    async def probe(name):
        calls[name] += 1
        return True

    async def run_once():
        return await coordinator.check(
            lambda: probe("db"), lambda: probe("redis"), lambda: probe("minio")
        )

    assert asyncio.run(run_once()) == (True, True, True)
    assert asyncio.run(run_once()) == (True, True, True)
    assert calls == {"db": 2, "redis": 2, "minio": 2}


def test_degraded_snapshot_uses_short_retry_ttl_not_healthy_ttl():
    calls = {"db": 0, "redis": 0, "minio": 0}
    coordinator = HealthProbeCoordinator(ttl_seconds=60.0, degraded_ttl_seconds=-1.0)

    async def probe(name, result):
        calls[name] += 1
        return result

    async def run():
        probes = (
            lambda: probe("db", False),
            lambda: probe("redis", True),
            lambda: probe("minio", True),
        )
        assert await coordinator.check(*probes) == (False, True, True)
        assert await coordinator.check(*probes) == (False, True, True)

    asyncio.run(run())
    assert calls == {"db": 2, "redis": 2, "minio": 2}
