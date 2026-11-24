"""Probe local Docker MinIO live endpoint on 127.0.0.1:9000. Exit 0=ok, 1=fail."""
from __future__ import annotations

import sys
import urllib.error
import urllib.request


def main() -> int:
    url = "http://127.0.0.1:9000/minio/health/live"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            if 200 <= resp.status < 300:
                return 0
            print(f"minio probe failed: status={resp.status}", file=sys.stderr)
            return 1
    except Exception as exc:  # noqa: BLE001 — startup probe
        print(f"minio probe failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
