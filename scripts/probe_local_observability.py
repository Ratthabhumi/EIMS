"""Probe local Prometheus :9090 and Grafana :3000. Exit 0=ok, 1=fail."""
from __future__ import annotations

import sys
import urllib.request


def _ok(url: str) -> None:
    with urllib.request.urlopen(url, timeout=5) as resp:
        if not (200 <= resp.status < 300):
            raise RuntimeError(f"{url} status={resp.status}")


def main() -> int:
    try:
        _ok("http://127.0.0.1:9090/-/ready")
        _ok("http://127.0.0.1:3000/api/health")
        return 0
    except Exception as exc:  # noqa: BLE001 — startup probe
        print(f"observability probe failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
