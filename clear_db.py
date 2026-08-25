import asyncio
import sys
import os

# Add project root to Python path
sys.path.append(os.path.dirname(__file__))

from backend.infrastructure.database import database_engine
from sqlalchemy import text

async def clear():
    await database_engine.initialize()
    async with database_engine._engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE analysis_history RESTART IDENTITY CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE ai_knowledge RESTART IDENTITY CASCADE;"))
        print("Database cleared successfully.")
    await database_engine.close()

if __name__ == "__main__":
    asyncio.run(clear())
