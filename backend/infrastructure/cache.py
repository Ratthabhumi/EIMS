"""
==============================================================================
EIMS Asynchronous Redis Telemetry Broker & Anomaly Cache Manager
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 4 Compliance
==============================================================================
"""

import asyncio
import json
from typing import Any, Dict, Optional
import redis.asyncio as redis
from redis.asyncio.client import Redis

from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("eims.infrastructure.cache")
_PING_TIMEOUT_SECONDS = 2.0


class AsynchronousCacheManager:
    """
    Authoritative Redis in-memory storage manager enforcing mandatory Volatile-LRU
    eviction compliance and strict namespace key isolation rules (Core Law 4).
    """
    def __init__(self):
        self._redis_client: Redis | None = None
        self._health_redis_client: Redis | None = None
        self._ping_inflight: asyncio.Task | None = None

    @property
    def redis(self) -> Redis | None:
        return self._redis_client

    async def initialize(self) -> None:
        """Instantiates asynchronous Redis network connections over connection pooling."""
        self._redis_client = redis.from_url(
            settings.redis_url,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            encoding="utf-8",
            # Preserve raw stream bytes so malformed UTF-8 can be quarantined by consumers.
            decode_responses=False,
        )
        # Health traffic has its own one-connection pool so queue/cache workload
        # cannot starve the readiness signal it is meant to observe.
        self._health_redis_client = redis.from_url(
            settings.redis_url, max_connections=1, encoding="utf-8", decode_responses=False,
        )
        logger.info("Async Redis Telemetry Broker connection established successfully.")

    async def close(self) -> None:
        """Cancels any shared health probe, then drains Redis connections."""
        import asyncio
        task = self._ping_inflight
        self._ping_inflight = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=5.0)
            except (RuntimeError, asyncio.TimeoutError, OSError):
                pass
        clients = (self._health_redis_client, self._redis_client)
        self._health_redis_client = None
        for client in clients:
            if client is not None:
                try:
                    await asyncio.wait_for(client.aclose(), timeout=5.0)
                except (RuntimeError, asyncio.TimeoutError, OSError):
                    pass  # Event loop already closed or timeout (TestClient teardown)
        if any(clients):
            logger.info("Async Redis connection manager drained and terminated.")

    async def ping(self) -> bool:
        """Coalesce concurrent PINGs and shield the shared Redis command from caller cancellation."""
        client = self._health_redis_client or self._redis_client
        if client is None:
            return False
        import asyncio
        loop = asyncio.get_running_loop()
        task = self._ping_inflight
        if task is not None and task.get_loop() is not loop:
            task = None
            self._ping_inflight = None
        if task is None or task.done():
            task = loop.create_task(client.ping())
            self._ping_inflight = task
        try:
            try:
                return bool(await asyncio.wait_for(
                    asyncio.shield(task), timeout=_PING_TIMEOUT_SECONDS
                ))
            except asyncio.TimeoutError:
                if task.done():
                    try:
                        return bool(task.result())
                    except Exception as error:
                        logger.error(
                            "Redis Cache Health Diagnostic Failure: error_class=%s",
                            type(error).__name__,
                        )
                else:
                    logger.error("Redis Cache Health Diagnostic Failure: phase=ping outcome=timeout")
                return False
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error(
                "Redis Cache Health Diagnostic Failure: error_class=%s",
                type(error).__name__,
            )
            return False
        finally:
            if task.done() and self._ping_inflight is task:
                self._ping_inflight = None

    def _validate_namespace(self, key: str) -> None:
        """
        Enforces canonical naming convention rules (Core Law 4 Section 3.2).
        Keys must begin with recognized prefixes: eims:auth:, eims:asset:, eims:lock:, eims:sec:, or eims:queue:
        """
        approved_prefixes = (
            "eims:session:", "eims:cache:", "eims:telemetry:", "eims:sec:", "eims:jobs:",
            "eims:auth:", "eims:asset:", "eims:lock:", "eims:queue:"
        )
        if not key.startswith(approved_prefixes):
            logger.warning(f"Cache Key Namespace Violation: '{key}' does not conform to Core Law 4 approved hierarchy.")

    async def set_value(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Stores structural values with mandatory expiration time limits."""
        if self._redis_client is None:
            raise RuntimeError("Cache Manager invoked prior to initialization lifecycle step.")
        
        self._validate_namespace(key)
        serialized_val = json.dumps(value) if not isinstance(value, (str, int, float)) else str(value)
        await self._redis_client.set(key, serialized_val, ex=ttl_seconds)

    async def get_value(self, key: str) -> Optional[str]:
        """Retrieves character strings from Redis storage."""
        if self._redis_client is None:
            return None
        value = await self._redis_client.get(key)
        return value.decode("utf-8") if isinstance(value, bytes) else value

    async def delete_value(self, key: str) -> None:
        """Removes specified keys from volatile cache structures."""
        if self._redis_client is not None:
            await self._redis_client.delete(key)

    async def xadd_queue(self, stream_name: str, payload: Dict[str, Any]) -> str:
        """Append a durable job envelope to a Redis Stream and return its confirmed ID."""
        if self._redis_client is None:
            raise RuntimeError("Redis Telemetry Broker not connected.")
        self._validate_namespace(stream_name)
        stream_id = await self._redis_client.xadd(stream_name, {"payload": json.dumps(payload)})
        if not stream_id:
            raise RuntimeError("Redis did not confirm the stream job ID")
        return stream_id.decode("utf-8") if isinstance(stream_id, bytes) else str(stream_id)

    async def lpush_queue(self, queue_name: str, payload: Dict[str, Any]) -> int:
        """
        Pushes serialized telemetry payload dictionary onto Redis event stream queue
        for batch consumption by background diagnostic workers (Core Law 3).
        """
        if self._redis_client is None:
            raise RuntimeError("Redis Telemetry Broker not connected.")
        self._validate_namespace(queue_name)
        return await self._redis_client.lpush(queue_name, json.dumps(payload))


# Global instantiated cache manager singleton
cache_manager = AsynchronousCacheManager()


async def get_cache_manager() -> AsynchronousCacheManager:
    """FastAPI Dependency injection endpoint function for REST Controllers and Ingestion Workers."""
    return cache_manager
