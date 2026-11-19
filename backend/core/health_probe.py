"""Coalesce aggregate health checks and briefly reuse the last real probe result."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

Probe = Callable[[], Awaitable[bool]]


class HealthProbeCoordinator:
    """Single-flight probes; healthy snapshots live longer than degraded snapshots."""

    def __init__(self, ttl_seconds: float = 20.0, degraded_ttl_seconds: float = 3.0) -> None:
        self.ttl_seconds = ttl_seconds
        self.degraded_ttl_seconds = degraded_ttl_seconds
        self._loop: asyncio.AbstractEventLoop | None = None
        self._snapshot: tuple[float, tuple[bool, bool, bool]] | None = None
        self._task: asyncio.Task[tuple[bool, bool, bool]] | None = None

    @staticmethod
    def _observe_task(task: asyncio.Task[tuple[bool, bool, bool]]) -> None:
        """Retrieve failures even when every HTTP waiter disconnects."""
        if not task.cancelled():
            task.exception()

    async def check(self, database: Probe, redis: Probe, storage: Probe) -> tuple[bool, bool, bool]:
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self._loop, self._snapshot, self._task = loop, None, None
        cached = self._snapshot
        if cached is not None:
            age = time.monotonic() - cached[0]
            cache_ttl = self.ttl_seconds if all(cached[1]) else self.degraded_ttl_seconds
            if age < cache_ttl:
                return cached[1]
        task = self._task
        if task is None or task.done():
            task = loop.create_task(self._collect(database, redis, storage))
            task.add_done_callback(self._observe_task)
            self._task = task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done() and self._task is task:
                self._task = None

    async def _collect(self, database: Probe, redis: Probe, storage: Probe) -> tuple[bool, bool, bool]:
        results = await asyncio.gather(database(), redis(), storage())
        snapshot = (bool(results[0]), bool(results[1]), bool(results[2]))
        self._snapshot = (time.monotonic(), snapshot)
        return snapshot
