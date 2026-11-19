"""Run the demo seed against the provisioned Neon database.

Reads the owner URL and the generated role secrets from local files, builds the
runtime URL, generates a demo account password (stored only in the local secrets
file), runs tools/seed_demo_2026.py, then prints persisted counts.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(os.environ["TEMP"]) / "opencode"
URL_FILE = TMP / "neon_url.txt.txt"
SECRET_FILE = TMP / "eims_demo_secrets.txt"


def _kv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _runtime_url(owner_raw: str, secret: dict[str, str]) -> str:
    raw = owner_raw.strip().strip('"').strip("'")
    parts = urlsplit(raw)
    host = (parts.hostname or "").replace("-pooler", "")
    userinfo = f"eims_runtime:{secret['EIMS_DB_PASSWORD']}"
    port = f":{parts.port}" if parts.port else ""
    return urlunsplit(
        ("postgresql+asyncpg", f"{userinfo}@{host}{port}", parts.path, "ssl=require", "")
    )


async def _counts(url: str) -> dict[str, int]:
    engine = create_async_engine(url, poolclass=None)
    try:
        out = {}
        async with engine.connect() as conn:
            for name, sql in {
                "assets": "SELECT count(*) FROM infrastructure_assets",
                "analysis_observations": "SELECT count(*) FROM analysis_history",
                "incidents": "SELECT count(*) FROM incidents",
                "incidents_resolved": "SELECT count(*) FROM incidents WHERE status='resolved'",
                "incidents_investigating": "SELECT count(*) FROM incidents WHERE status='investigating'",
                "evidence": "SELECT count(*) FROM incident_evidence",
                "verifications": "SELECT count(*) FROM incident_verification",
                "audit_rows": "SELECT count(*) FROM audit_logs",
                "users": "SELECT count(*) FROM users",
            }.items():
                out[name] = (await conn.execute(text(sql))).scalar()
            await conn.rollback()
        return out
    finally:
        await engine.dispose()


async def main() -> int:
    owner_raw = URL_FILE.read_text(encoding="utf-8")
    secret = _kv(SECRET_FILE)
    demo_password = secret.get("EIMS_DEMO_PASSWORD") or secrets.token_urlsafe(18)
    secret["EIMS_DEMO_PASSWORD"] = demo_password
    secret["EIMS_DEMO_ENGINEER"] = "demo.engineer"
    secret["EIMS_DEMO_REVIEWER"] = "demo.reviewer"
    SECRET_FILE.write_text(
        "# EIMS demo secrets (local only, do not commit)\n"
        + "".join(f"{k}={v}\n" for k, v in secret.items()),
        encoding="utf-8",
    )

    runtime_url = _runtime_url(owner_raw, secret)
    env = os.environ.copy()
    env.update({
        "EIMS_DEMO_SEED_DATABASE_URL": runtime_url,
        "EIMS_DEMO_DATABASE_NAME": "eims_demo",
        "EIMS_DEMO_PASSWORD": demo_password,
        "PYTHONPATH": str(ROOT),
    })
    proc = subprocess.run(
        [str(ROOT / "venv" / "Scripts" / "python.exe"), str(ROOT / "tools" / "seed_demo_2026.py")],
        cwd=str(ROOT), env=env, capture_output=True, text=True,
    )
    print(f"seed_exit={proc.returncode}")
    print(proc.stdout.strip()[-2500:])
    if proc.returncode != 0:
        print(proc.stderr.strip()[-1500:])
        return proc.returncode

    counts = await _counts(runtime_url)
    print("persisted_counts=" + ",".join(f"{k}={v}" for k, v in counts.items()))
    print(f"demo_accounts=demo.engineer,demo.reviewer  (password in {SECRET_FILE.name})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
