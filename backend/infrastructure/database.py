"""
==============================================================================
EIMS SQLAlchemy 2.0 Asynchronous Database Engine & PgBouncer Interface
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 3 & 4 Compliance
==============================================================================
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import text

from backend.core.config import settings
from backend.core.logger import get_logger
from backend.infrastructure.db_identity import (
    identity_enforcement_expected,
    require_runtime_identity,
    validate_runtime_identity_configuration,
)

logger = get_logger("eims.infrastructure.database")
# Deadline triggers cancellation; SQLAlchemy completes cleanup before returning.
# Safe cleanup may extend wall-clock duration beyond the deadline.
_DB_PING_TIMEOUT_SECONDS = 10.0

# Canonical ORM base class for Phase 2 declarative asset table schema definitions
Base = declarative_base()


async def rollback_read_only_transaction(session: AsyncSession) -> bool | None:
    """Release a known read-only engine-bound transaction before slow work.

    Rollback, rather than commit, preserves caller transaction semantics and
    guarantees that no incidental Core DML is committed at this boundary.
    Call only where the caller has established that the active transaction is
    read-only. Returns None for connection-bound sessions and False when ORM
    state is pending.
    """
    if not isinstance(getattr(session, "bind", None), AsyncEngine):
        return None
    if not session.in_transaction():
        return True
    if session.new or session.dirty or session.deleted:
        return False
    await session.rollback()
    return True


class AsynchronousDatabaseEngine:
    """
    Authoritative database connection management encapsulation operating over
    asynchronous TCP network pipelines directly into PgBouncer transaction pools.
    """
    def __init__(self):
        self._engine: AsyncEngine | None = None
        # Independent, bounded pool prevents readiness checks from competing
        # with request transactions or reporting false DB outages on pool exhaustion.
        self._health_engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._ping_inflight: asyncio.Task[bool] | None = None
        self._ping_waiters = 0

    async def initialize(self) -> None:
        """Instantiates async SQLAlchemy 2.0 engine using Pydantic parameters."""
        # Fail closed before a pool exists: REQUIRED=1 without a usable identity
        # must stop the process, not the first request.
        validate_runtime_identity_configuration()
        self._guarded_session_factory = None
        self._engine = create_async_engine(
            settings.database_url,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_pre_ping=True, # Validates network socket viability before query execution
            echo=(settings.LOG_LEVEL == "DEBUG"),
            connect_args={"prepared_statement_cache_size": 0}, # Required for PgBouncer Transaction Mode
        )
        self._health_engine = create_async_engine(
            settings.database_url,
            pool_size=1,
            max_overflow=0,
            pool_timeout=1.0,
            # The explicit SELECT 1 below is the health check; pre-ping would
            # perform a duplicate network round-trip during connection checkout.
            pool_pre_ping=False,
            echo=False,
            connect_args={"prepared_statement_cache_size": 0},
        )
        
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False, # Essential for async execution workflows to prevent background read hangs
            autoflush=False,
        )
        logger.info("SQLAlchemy Asynchronous Database Engine connected successfully to PgBouncer target.")

    @property
    def is_initialized(self) -> bool:
        """Public readiness accessor: callers must not reach into the private engine handle (it bypasses the guards)."""
        return self._engine is not None

    async def close(self) -> None:
        """Waits for the shared health probe to clean up before disposing the pool."""
        task = self._ping_inflight
        self._ping_inflight = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=5.0)
            except (RuntimeError, asyncio.TimeoutError, OSError):
                pass
        for engine in (self._health_engine, self._engine):
            if engine is not None:
                try:
                    await engine.dispose()
                except RuntimeError:
                    pass  # Event loop already closed (TestClient teardown)
        self._health_engine = None
        self._guarded_session_factory = None
        logger.info("SQLAlchemy Asynchronous Database Engines closed completely.")

    async def ping(self) -> bool:
        """Single-flight health probe; cancellation never abandons connection cleanup."""
        if self._engine is None:
            return False
        loop = asyncio.get_running_loop()
        task = self._ping_inflight
        if task is not None and task.get_loop() is not loop:
            task = None
            self._ping_inflight = None
            self._ping_waiters = 0
        if task is None or task.done():
            task = loop.create_task(self._ping_once())
            self._ping_inflight = task
            self._ping_waiters = 0
        self._ping_waiters += 1
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # A sole caller owns cancellation and must await SQLAlchemy cleanup.
            # If another request is sharing this probe, preserve it for that caller.
            if self._ping_inflight is task and self._ping_waiters == 1:
                task.cancel()
                try:
                    await asyncio.shield(task)
                except BaseException:
                    pass
            raise
        finally:
            if self._ping_inflight is task:
                self._ping_waiters = max(0, self._ping_waiters - 1)
                if task.done() and self._ping_waiters == 0:
                    self._ping_inflight = None

    async def _ping_once(self) -> bool:
        """Probe the full connection lifecycle; safe cleanup may finish after the deadline."""
        engine = self._health_engine or self._engine
        if engine is None:
            return False
        import asyncio
        from time import perf_counter

        phase = "checkout"
        checkout_ms = execute_ms = cleanup_ms = None
        failure: BaseException | None = None
        operation_error: BaseException | None = None
        operation_phase = None
        started = phase_started = perf_counter()
        deadline = asyncio.timeout(_DB_PING_TIMEOUT_SECONDS)

        try:
            async with deadline:
                try:
                    async with engine.connect() as conn:
                        checkout_ms = (perf_counter() - phase_started) * 1000
                        phase = "execute"
                        phase_started = perf_counter()
                        try:
                            result = await conn.execute(text("SELECT 1"))
                            if result.scalar_one() != 1:
                                raise RuntimeError(
                                    "Database health probe returned an unexpected value."
                                )
                        except BaseException as e:
                            operation_error = e
                            operation_phase = phase
                            execute_ms = (perf_counter() - phase_started) * 1000
                            raise
                        else:
                            execute_ms = (perf_counter() - phase_started) * 1000
                        finally:
                            phase = "cleanup"
                            phase_started = perf_counter()
                finally:
                    if phase == "cleanup":
                        cleanup_ms = (perf_counter() - phase_started) * 1000
            return True
        except TimeoutError as e:
            failure = e
            if operation_error is not None and (
                e is operation_error or isinstance(operation_error, asyncio.CancelledError)
            ):
                failure_phase = operation_phase
            else:
                failure_phase = phase
        except (SQLAlchemyError, OSError, RuntimeError) as e:
            failure = e
            failure_phase = operation_phase if e is operation_error else phase

        if failure_phase == "checkout" and checkout_ms is None:
            checkout_ms = (perf_counter() - phase_started) * 1000
        elif failure_phase == "execute" and execute_ms is None:
            execute_ms = (perf_counter() - phase_started) * 1000
        elif failure_phase == "cleanup" and cleanup_ms is None:
            cleanup_ms = (perf_counter() - phase_started) * 1000

        total_ms = (perf_counter() - started) * 1000
        self._log_ping_failure(
            failure_phase,
            failure,
            checkout_ms,
            execute_ms,
            cleanup_ms,
            total_ms,
            deadline.expired(),
        )
        return False

    def _log_ping_failure(
        self, phase, exc, checkout_ms, execute_ms, cleanup_ms, total_ms, deadline_expired
    ) -> None:
        """Emit sanitized ping diagnostics; never raises and never logs raw error text/DSNs."""
        try:
            def fmt(v):
                return "n/a" if v is None else f"{v:.1f}ms"

            try:
                pool_status = self._engine.pool.status()
            except Exception:  # noqa: BLE001 - diagnostics must not fail with pool status
                pool_status = "unavailable"
            logger.error(
                "Relational Database Health Diagnostic Failure: phase=%s error_class=%s "
                "checkout=%s execute=%s cleanup=%s total=%s deadline_expired=%s pool=%s",
                phase,
                type(exc).__name__,
                fmt(checkout_ms),
                fmt(execute_ms),
                fmt(cleanup_ms),
                fmt(total_ms),
                deadline_expired,
                pool_status,
            )
        except Exception:  # noqa: BLE001, S110 - diagnostics must never escape
            pass

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Dependency injection session yield generator wrapped with strict
        ACID rollback protection upon runtime execution anomalies.
        """
        if self._session_factory is None:
            raise RuntimeError("Database Engine invoked prior to initialization lifecycle step.")
        
        async with self._session_factory() as session:
            try:
                # R-1 Policy A: one choke point for every API request session.
                # The check runs on the connection this request will use, before
                # the caller can execute a statement.
                await require_runtime_identity(session)
                yield session
            except Exception:
                await session.rollback()
                logger.exception("ACID Transaction anomaly intercepted; executing automatic database rollback.")
                raise
            finally:
                await session.close()

    def get_session_maker(self):
        """Returns a guarded session factory for background workers.
        Worker code builds sessions directly, so the request dependency never
        runs for it. The returned factory applies the same Policy A check to the
        connection the worker session will use; a mismatch raises before the body
        executes. The wrapper is cached so repeated calls cannot drift.
        """
        if self._session_factory is None:
            raise RuntimeError("Database Engine invoked prior to initialization lifecycle step.")
        existing = getattr(self, "_guarded_session_factory", None)
        if existing is not None:
            return existing

        raw = self._session_factory

        @asynccontextmanager
        async def guarded():
            async with raw() as session:
                await require_runtime_identity(session)
                yield session

        self._guarded_session_factory = guarded
        return guarded

    async def verify_runtime_identity(self) -> None:
        """Startup pre-flight: refuse to serve on an unexpected live connection.

        Config-shape validation already ran in ``initialize``. This asks the
        actual database who it is, so a wrong DB/role fails at startup instead
        of on the first request. Unconfigured + not required stays allowed (and
        is reported as ``unconfigured``, never ``verified``).
        """
        if self._engine is None:
            raise RuntimeError("Database Engine invoked prior to initialization lifecycle step.")
        if not identity_enforcement_expected():
            # Unconfigured development mode keeps the engine lazy: a transient
            # database outage must not crash-loop a process that has no identity
            # contract to enforce. It is never reported as "verified".
            return
        async with self._engine.connect() as conn:
            await require_runtime_identity(conn)

    @asynccontextmanager
    async def connect(self):
        """Guarded Core/text database boundary.

        ORM sessions are guarded by ``get_session`` / ``get_session_maker``.
        Core and textual SQL use a raw connection, which would otherwise reach
        PostgreSQL without any identity check. This is the only supported way
        for application code to obtain one, and it revalidates identity on the
        connection actually being used before any statement runs.
        """
        if self._engine is None:
            raise RuntimeError("Database Engine invoked prior to initialization lifecycle step.")
        async with self._engine.connect() as conn:
            await require_runtime_identity(conn)
            yield conn


# Global instantiated database engine singleton
database_engine = AsynchronousDatabaseEngine()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Dependency injection endpoint function for ORM Controllers."""
    async for session in database_engine.get_session():
        yield session
