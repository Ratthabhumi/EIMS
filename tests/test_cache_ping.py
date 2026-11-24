"""Redis health-probe single-flight and cancellation lifecycle tests."""
import asyncio

import pytest

from backend.infrastructure import cache
from backend.infrastructure.cache import AsynchronousCacheManager


@pytest.mark.asyncio
async def test_set_value_is_non_fatal_when_redis_unavailable():
    """USB import / asset upsert must survive a down Redis cache tier."""
    manager = AsynchronousCacheManager()
    await manager.set_value("eims:asset:soft-deps", {"ok": True}, ttl_seconds=30)

    class BoomRedis:
        async def set(self, *args, **kwargs):
            raise ConnectionError("redis down")

    manager._redis_client = BoomRedis()
    await manager.set_value("eims:asset:soft-deps", {"ok": True}, ttl_seconds=30)


class BlockingRedis:
    def __init__(self):
        self.calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = False
        self.closed = False

    async def ping(self):
        self.calls += 1
        self.started.set()
        try:
            await self.release.wait()
            return True
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    async def aclose(self):
        self.closed = True


def test_redis_health_probe_uses_dedicated_client_pool():
    async def scenario():
        manager = AsynchronousCacheManager()
        application_redis = BlockingRedis()
        health_redis = BlockingRedis()
        manager._redis_client = application_redis
        manager._health_redis_client = health_redis
        waiter = asyncio.create_task(manager.ping())
        await health_redis.started.wait()
        assert health_redis.calls == 1
        assert application_redis.calls == 0
        health_redis.release.set()
        assert await waiter is True

    asyncio.run(scenario())


def test_concurrent_redis_health_probes_share_one_command():

    async def scenario():
        manager = AsynchronousCacheManager()
        redis = BlockingRedis()
        manager._redis_client = redis
        tasks = [asyncio.create_task(manager.ping()) for _ in range(12)]
        await redis.started.wait()
        assert redis.calls == 1
        redis.release.set()
        assert await asyncio.gather(*tasks) == [True] * 12
        assert manager._ping_inflight is None

    asyncio.run(scenario())


def test_cancelled_health_caller_does_not_cancel_shared_redis_command():
    async def scenario():
        manager = AsynchronousCacheManager()
        redis = BlockingRedis()
        manager._redis_client = redis
        first = asyncio.create_task(manager.ping())
        second = asyncio.create_task(manager.ping())
        await redis.started.wait()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert not redis.cancelled
        redis.release.set()
        assert await second is True
        assert redis.calls == 1

    asyncio.run(scenario())


def test_timeout_does_not_cancel_or_duplicate_inflight_redis_command(monkeypatch):
    monkeypatch.setattr(cache, "_PING_TIMEOUT_SECONDS", 0.01)

    async def scenario():
        manager = AsynchronousCacheManager()
        redis = BlockingRedis()
        manager._redis_client = redis
        assert await manager.ping() is False
        task = manager._ping_inflight
        assert task is not None and not task.done()
        assert not redis.cancelled
        assert await manager.ping() is False
        assert redis.calls == 1 and manager._ping_inflight is task
        redis.release.set()
        assert await task is True
        assert await manager.ping() is True
        assert redis.calls == 2

    asyncio.run(scenario())


def test_close_cancels_inflight_probe_before_closing_redis():
    async def scenario():
        manager = AsynchronousCacheManager()
        redis = BlockingRedis()
        manager._redis_client = redis
        waiter = asyncio.create_task(manager.ping())
        await redis.started.wait()
        await manager.close()
        assert redis.cancelled
        assert redis.closed
        assert manager._ping_inflight is None
        with pytest.raises(asyncio.CancelledError):
            await waiter

    asyncio.run(scenario())
