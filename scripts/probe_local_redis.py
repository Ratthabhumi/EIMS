"""Probe local Docker Redis on 127.0.0.1:6379. Exit 0=ok, 1=fail."""
from __future__ import annotations

import asyncio
import sys

import redis.asyncio as redis


async def main() -> int:
    client = redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)
    try:
        ok = await client.ping()
        if not ok:
            print("redis probe failed: ping returned false", file=sys.stderr)
            return 1
        return 0
    except Exception as exc:  # noqa: BLE001 — startup probe
        print(f"redis probe failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        await client.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
