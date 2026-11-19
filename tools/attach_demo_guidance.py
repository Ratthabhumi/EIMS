"""Attach clearly-labelled synthetic demo guidance to the seeded incidents.

Stored in ``incidents.summary.demo_guidance`` so the demo API can present the
engineer story without inventing fields the domain does not have. Re-runnable.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TMP = Path(os.environ["TEMP"]) / "opencode"

GUIDANCE = {
    "Repeated failed logon attempts on DEMO-WS-01": {
        "what_happened": "Windows recorded repeated 4625 failed logon events on the workstation inside the correlation window, which opened this incident.",
        "why": "The events share the same source signature on the same asset inside the window, so the correlation engine grouped them instead of creating separate incidents. The root cause is not inferred automatically.",
        "impact": "A single workstation is affected. No lateral movement is evidenced by the current records.",
        "inspect": [
            "Windows Security log 4625 on DEMO-WS-01 around the observation window",
            "Whether the account involved is local or domain, and its lockout policy",
            "Any 4624 success that follows the failures",
        ],
        "remediation": [
            "Confirm whether the attempts were user error or password spraying",
            "Reset the credential and enforce lockout if abuse is suspected",
        ],
        "risks": "The dataset contains no firewall or identity-provider telemetry, so the origin of the attempts is unknown.",
    },
    "Authentication failures on DEMO-WEB-01": {
        "what_happened": "Authentication failures were recorded on the web host, remediated, and then a post-patch observation was attached as evidence.",
        "why": "The failure pattern matched a known authentication defect on the web service; the fix was applied and re-observed.",
        "impact": "The web host was briefly unable to authenticate clients.",
        "inspect": [
            "The post-patch analysis observation for the absence of further failures",
            "Service configuration changes applied during the remediation window",
        ],
        "remediation": [
            "Apply the authentication configuration fix",
            "Confirm no new 4625 events after the change",
        ],
        "risks": "Verification proves the recorded observation, not the health of the upstream identity provider.",
        "proof": "The persisted verification row records which evidence was checked, by whom, and for which remediation cycle.",
    },
    "Disk latency spike on DEMO-DB-01": {
        "what_happened": "A disk latency observation on the database host opened this incident. It was resolved, then reopened, so it is now in remediation cycle 1.",
        "why": "The first remediation was verified with evidence from cycle 0. Reopening started a new cycle, and evidence from the previous cycle can no longer authorise resolution.",
        "impact": "Database response times were affected while the incident was open.",
        "inspect": [
            "Volume latency and queue depth on DEMO-DB-01",
            "Recent schema or backup activity during the window",
        ],
        "remediation": [
            "Address the storage bottleneck, then attach a fresh observation",
            "Have a reviewer verify the new-cycle evidence",
        ],
        "risks": "The stored verification from cycle 0 is retained for audit but is intentionally insufficient for cycle 1.",
        "proof": "A cycle-1 verification row exists only after evidence attached in cycle 1 is verified; an attempt with cycle-0 evidence is rejected.",
    },
}


async def main() -> int:
    secret = {}
    for line in (TMP / "eims_demo_secrets.txt").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            secret[k.strip()] = v.strip()
    raw = (TMP / "neon_url.txt.txt").read_text(encoding="utf-8").strip().strip('"')
    parts = urlsplit(raw)
    host = (parts.hostname or "").replace("-pooler", "")
    url = urlunsplit((
        "postgresql+asyncpg",
        f"eims_runtime:{secret['EIMS_DB_PASSWORD']}@{host}:{parts.port or 5432}",
        parts.path, "ssl=require", "",
    ))
    engine = create_async_engine(url, poolclass=None)
    try:
        async with engine.begin() as conn:
            for title, guidance in GUIDANCE.items():
                result = await conn.execute(
                    text(
                        "UPDATE incidents SET summary = jsonb_set(coalesce(summary, '{}'::jsonb), "
                        "'{demo_guidance}', cast(:g as jsonb), true) WHERE title = :t"
                    ),
                    {"g": json.dumps(guidance), "t": title},
                )
                print(f"{title}: updated={result.rowcount}")
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
