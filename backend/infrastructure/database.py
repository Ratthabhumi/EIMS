"""
==============================================================================
EIMS SQLAlchemy 2.0 Asynchronous Database Engine & PgBouncer Interface
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 3 & 4 Compliance
==============================================================================
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import text

from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("eims.infrastructure.database")

# Canonical ORM base class for Phase 2 declarative asset table schema definitions
Base = declarative_base()


class AsynchronousDatabaseEngine:
    """
    Authoritative database connection management encapsulation operating over
    asynchronous TCP network pipelines directly into PgBouncer transaction pools.
    """
    def __init__(self):
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def initialize(self) -> None:
        """Instantiates async SQLAlchemy 2.0 engine using Pydantic parameters."""
        self._engine = create_async_engine(
            settings.database_url,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_pre_ping=True, # Validates network socket viability before query execution
            echo=(settings.LOG_LEVEL == "DEBUG"),
            connect_args={"prepared_statement_cache_size": 0}, # Required for PgBouncer Transaction Mode
        )
        
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False, # Essential for async execution workflows to prevent background read hangs
            autoflush=False,
        )
        logger.info("SQLAlchemy Asynchronous Database Engine connected successfully to PgBouncer target.")

    async def close(self) -> None:
        """Drains open pool sockets and gracefully terminates engine thread loops."""
        if self._engine is not None:
            await self._engine.dispose()
            logger.info("SQLAlchemy Asynchronous Database Engine closed completely.")

    async def ping(self) -> bool:
        """Executes lightweight structural SQL verification probe for health diagnostics."""
        if self._engine is None:
            return False
        import asyncio
        try:
            async with self._engine.connect() as conn:
                await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=2.0)
            return True
        except Exception as e:
            logger.error(f"Relational Database Health Diagnostic Failure: {e}")
            return False

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Dependency injection session yield generator wrapped with strict
        ACID rollback protection upon runtime execution anomalies.
        """
        if self._session_factory is None:
            raise RuntimeError("Database Engine invoked prior to initialization lifecycle step.")
        
        async with self._session_factory() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error("ACID Transaction anomaly intercepted; executing automatic database rollback.", exc_info=True)
                raise
            finally:
                await session.close()

    def get_session_maker(self):
        """Returns the internal session factory for background workers."""
        return self._session_factory


# Global instantiated database engine singleton
database_engine = AsynchronousDatabaseEngine()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Dependency injection endpoint function for ORM Controllers."""
    async for session in database_engine.get_session():
        yield session
