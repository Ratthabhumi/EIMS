"""Free EIMS local ports before start_eims.bat brings the stack up.

Host listeners (uvicorn/Next): 8000, 3001 — taskkill owning PIDs.
Docker-published ports: stop EIMS containers so Windows rebinds on compose up.
Never kills docker-proxy / Docker Desktop by port alone.
Exit 0 always (best-effort); prints what was cleared.
"""
from __future__ import annotations

import subprocess
import sys

HOST_PORTS = (8000, 3001)
EIMS_CONTAINERS = (
    "eims-postgres",
    "eims-redis",
    "eims-minio",
    "eims-prometheus",
    "eims-grafana",
)


def _listening_pids(port: int) -> set[int]:
    pids: set[int] = set()
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.CalledProcessError):
        return pids
    needle = f":{port} "
    for line in out.splitlines():
        if "LISTENING" not in line.upper() or needle not in line:
            continue
        # Match only "...:PORT " (avoid :30010 matching :3001)
        parts = line.split()
        if len(parts) < 2:
            continue
        local = parts[1]
        if not (local.endswith(f":{port}") or local.endswith(f"]:{port}")):
            continue
        try:
            pids.add(int(parts[-1]))
        except ValueError:
            continue
    return pids


def _kill_pid(pid: int) -> None:
    if pid <= 0:
        return
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def main() -> int:
    for port in HOST_PORTS:
        pids = _listening_pids(port)
        if not pids:
            print(f"  host :{port} — free")
            continue
        for pid in sorted(pids):
            print(f"  host :{port} — kill PID {pid}")
            _kill_pid(pid)

    print("  docker — stop EIMS containers to release published ports...")
    subprocess.run(
        ["docker", "stop", *EIMS_CONTAINERS],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    # Ports that compose publishes (informational; freed by container stop)
    for port in (5432, 6379, 9000, 9001, 9090, 3000):
        leftover = _listening_pids(port)
        if leftover:
            print(f"  warn :{port} still LISTENING (PIDs {sorted(leftover)}); compose up will rebind")
        else:
            print(f"  publish :{port} — clear")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
