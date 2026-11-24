"""Probe local Docker Postgres on 127.0.0.1:5432 for asyncpg. Exit 0=ok, 1=fail."""
from __future__ import annotations

import asyncio
import sys

import asyncpg


async def main() -> int:
    try:
        conn = await asyncpg.connect(
            host="127.0.0.1",
            port=5432,
            user="eims_user",
            password="eims_secret_password",
            database="eims_registry",
            timeout=5,
        )
        await conn.fetchval("SELECT 1")
        await conn.close()
        return 0
    except Exception as exc:  # noqa: BLE001 — startup probe
        print(f"postgres probe failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
