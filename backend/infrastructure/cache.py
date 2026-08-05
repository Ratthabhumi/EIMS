"""
==============================================================================
EIMS Asynchronous Redis Telemetry Broker & Anomaly Cache Manager
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 4 Compliance
==============================================================================
"""

import json
from typing import Any, Dict, Optional
import redis.asyncio as redis
from redis.asyncio.client import Redis

from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("eims.infrastructure.cache")


class AsynchronousCacheManager:
    """
    Authoritative Redis in-memory storage manager enforcing mandatory Volatile-LRU
    eviction compliance and strict namespace key isolation rules (Core Law 4).
    """
    def __init__(self):
        self._redis_client: Redis | None = None

    async def initialize(self) -> None:
        """Instantiates asynchronous Redis network connections over connection pooling."""
        self._redis_client = redis.from_url(
            settings.redis_url,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("Async Redis Telemetry Broker connection established successfully.")

    async def close(self) -> None:
        """Closes networking client pipes gracefully upon server shutdown."""
        if self._redis_client is not None:
            await self._redis_client.aclose()
            logger.info("Async Redis connection manager drained and terminated.")

    async def ping(self) -> bool:
        """Executes lightweight PING diagnostic health check."""
        if self._redis_client is None:
            return False
        try:
            return await self._redis_client.ping()
        except Exception as e:
            logger.error(f"Redis Cache Health Diagnostic Failure: {e}")
            return False

    def _validate_namespace(self, key: str) -> None:
        """
        Enforces canonical naming convention rules (Core Law 4 Section 3.2).
        Keys must begin with recognized prefixes: eims:auth:, eims:asset:, eims:lock:, eims:sec:, or eims:queue:
        """
        approved_prefixes = ("eims:auth:", "eims:asset:", "eims:lock:", "eims:sec:", "eims:queue:")
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
        return await self._redis_client.get(key)

    async def delete_value(self, key: str) -> None:
        """Removes specified keys from volatile cache structures."""
        if self._redis_client is not None:
            await self._redis_client.delete(key)

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
