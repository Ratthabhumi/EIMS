"""Development helper: create ORM tables through the guarded engine boundary.

Not a migration tool — schema changes belong in ``migrations/``. This script is
kept for local bootstrapping only, and it now goes through
``AsynchronousDatabaseEngine.connect()`` so the R-1 identity policy applies
instead of reaching past the guard with a raw engine handle.
"""
import asyncio

from backend.domain.analyzer.models.history import (
    AnalysisHistory,  # noqa: F401 - metadata
)
from backend.infrastructure.database import Base, database_engine


async def create_tables() -> None:
    await database_engine.initialize()
    try:
        await database_engine.verify_runtime_identity()
        async with database_engine.connect() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # connect() does not autocommit in SQLAlchemy 2.0; commit the DDL
            # explicitly or it rolls back when the context exits.
            await conn.commit()
    finally:
        await database_engine.close()


if __name__ == "__main__":
    asyncio.run(create_tables())
