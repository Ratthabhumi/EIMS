import asyncio
from backend.infrastructure.database import database_engine, Base
from backend.domain.analyzer.models.history import AnalysisHistory

async def create_tables():
    await database_engine.initialize()
    async with database_engine._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await database_engine.close()

if __name__ == "__main__":
    asyncio.run(create_tables())
