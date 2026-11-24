import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

T = Path(os.environ["TEMP"]) / "opencode"
sec = {}
for line in (T / "eims_demo_secrets.txt").read_text(encoding="utf-8").splitlines():
    if line.strip() and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        sec[k.strip()] = v.strip()
raw = (T / "neon_url.txt.txt").read_text(encoding="utf-8").strip().strip('"')
p = urlsplit(raw)
h = (p.hostname or "").replace("-pooler", "")
url = urlunsplit((
    "postgresql+asyncpg",
    f"eims_runtime:{sec['EIMS_DB_PASSWORD']}@{h}:{p.port or 5432}",
    p.path, "ssl=require", "",
))

FIX = {
    "why": (
        "The first remediation was verified with evidence from the cycle that was open at the time. "
        "Reopening starts a new remediation cycle, and evidence from a previous cycle can no longer "
        "authorise resolution."
    ),
    "risks": (
        "Verification rows from earlier cycles are retained for audit but are intentionally "
        "insufficient for the current cycle."
    ),
    "proof": (
        "A verification row for the current cycle exists only after evidence attached in that cycle "
        "is verified; an attempt with earlier-cycle evidence is rejected."
    ),
}

COUNTS = {
    "assets": "select count(*) from infrastructure_assets",
    "observations": "select count(*) from analysis_history",
    "incidents_open": "select count(*) from incidents where status='open'",
    "incidents_investigating": "select count(*) from incidents where status='investigating'",
    "incidents_resolved": "select count(*) from incidents where status='resolved'",
    "evidence": "select count(*) from incident_evidence",
    "verifications": "select count(*) from incident_verification",
    "audit": "select count(*) from audit_logs",
}


async def main() -> None:
    engine = create_async_engine(url, poolclass=None)
    try:
        async with engine.begin() as conn:
            summary = (await conn.execute(text(
                "select summary from incidents where title like 'Disk latency spike%'"
            ))).scalar()
            guidance = dict((summary or {}).get("demo_guidance") or {})
            guidance.update(FIX)
            await conn.execute(
                text(
                    "update incidents set summary = jsonb_set(coalesce(summary,'{}'::jsonb), "
                    "'{demo_guidance}', cast(:g as jsonb), true) where title like 'Disk latency spike%'"
                ),
                {"g": json.dumps(guidance)},
            )
        for name, sql in COUNTS.items():
            async with engine.connect() as conn:
                print(name, (await conn.execute(text(sql))).scalar())
                await conn.rollback()
    finally:
        await engine.dispose()


asyncio.run(main())
