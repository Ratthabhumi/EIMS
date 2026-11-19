"""Reset the demo account passwords to the value held in the local secrets file.

The demo users already exist, so the seed's create-if-missing path does not
rewrite their hash. This keeps the account usable without printing the secret.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(os.environ["TEMP"]) / "opencode"

sys.path.insert(0, str(ROOT))
from backend.domain.analyzer.auth import hash_password  # noqa: E402


def kv(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


async def main() -> int:
    secret = kv(TMP / "eims_demo_secrets.txt")
    raw = (TMP / "neon_url.txt.txt").read_text(encoding="utf-8").strip().strip('"')
    parts = urlsplit(raw)
    host = (parts.hostname or "").replace("-pooler", "")
    url = urlunsplit((
        "postgresql+asyncpg",
        f"eims_runtime:{secret['EIMS_DB_PASSWORD']}@{host}:{parts.port or 5432}",
        parts.path, "ssl=require", "",
    ))
    hashed = hash_password(secret["EIMS_DEMO_PASSWORD"])
    engine = create_async_engine(url, poolclass=None)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("UPDATE users SET password = :p WHERE username IN ('demo.engineer','demo.reviewer')"),
                {"p": hashed},
            )
            print(f"users_updated={result.rowcount}")
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
