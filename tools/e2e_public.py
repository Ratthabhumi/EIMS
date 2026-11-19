"""Public acceptance E2E against the deployed Render service.

Uses only the public HTTPS API. Prints non-secret results only.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

BASE = os.environ.get("EIMS_DEMO_BASE_URL", "https://eims-demo-api.onrender.com").rstrip("/")
TMP = Path(os.environ["TEMP"]) / "opencode"
SECRETS = TMP / "eims_demo_secrets.txt"
NEON = TMP / "neon_url.txt.txt"


def kv(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def call(method: str, path: str, body=None, token: str | None = None, timeout: int = 120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        return exc.code, parsed


def login(username: str, password: str) -> str:
    status, body = call("POST", "/api/v1/auth/login",
                        {"username": username, "password": password})
    if status != 200 or not isinstance(body, dict) or not body.get("access_token"):
        raise SystemExit(f"login failed for {username}: {status} {str(body)[:200]}")
    return body["access_token"]


async def insert_observation(incident_asset: str | None) -> str:
    secret = kv(SECRETS)
    raw = NEON.read_text(encoding="utf-8").strip().strip('"')
    parts = urlsplit(raw)
    host = (parts.hostname or "").replace("-pooler", "")
    mig = urlunsplit((
        "postgresql+asyncpg",
        f"eims_migrator:{secret['EIMS_MIGRATOR_PASSWORD']}@{host}:{parts.port or 5432}",
        parts.path, "ssl=require", "",
    ))
    engine = create_async_engine(mig, poolclass=None)
    try:
        async with engine.begin() as conn:
            row = (await conn.execute(
                text(
                    "INSERT INTO analysis_history (event_id, provider, username, description, asset_id, created_at) "
                    "VALUES ('demo-live-verification', 'DEMO-SYNTHETIC', 'demo.engineer', "
                    "'Live demo: post-remediation telemetry observation', :a, now()) RETURNING id"
                ),
                {"a": incident_asset},
            )).scalar()
        return str(row)
    finally:
        await engine.dispose()


def main() -> int:
    secret = kv(SECRETS)
    out: dict[str, object] = {"base_url": BASE}

    status, health = call("GET", "/api/v1/health", timeout=180)
    out["health_status"] = status
    out["health_state"] = (health or {}).get("status") if isinstance(health, dict) else None

    status, body = call("GET", "/api/v1/incidents")
    out["unauth_incidents_status"] = status
    assert status in (401, 403), f"unauthenticated access not blocked: {status}"

    engineer = login(secret["EIMS_DEMO_ENGINEER"], secret["EIMS_DEMO_PASSWORD"])
    reviewer = login(secret["EIMS_DEMO_REVIEWER"], secret["EIMS_DEMO_PASSWORD"])
    out["login"] = "ok"

    status, listing = call("GET", "/api/v1/incidents?limit=50", token=engineer)
    incidents = (listing or {}).get("data", [])
    out["incident_count"] = len(incidents)
    out["statuses"] = sorted({(i["status"], i.get("remediation_cycle", 0)) for i in incidents})

    target = next((i for i in incidents if i.get("remediation_cycle", 0) >= 1), None)
    if target is None:
        out["error"] = "no reopened incident found"
        print(json.dumps(out, indent=2))
        return 1
    incident_id = target["incident_id"]
    out["target_incident"] = {"id": incident_id, "status": target["status"],
                              "cycle": target["remediation_cycle"]}

    status, detail = call("GET", f"/api/v1/incidents/{incident_id}", token=engineer)
    out["detail_evidence_before"] = len(detail.get("evidence", []))
    out["verifications_before"] = len(detail.get("verifications", []))

    # A stale cycle-0 evidence must be refused.
    stale = (detail.get("evidence") or [{}])[0].get("evidence_id")
    status, blocked = call("PATCH", f"/api/v1/incidents/{incident_id}/status",
                           {"status": "resolved", "verification": {"evidence_id": stale}},
                           token=reviewer)
    out["stale_evidence_attempt"] = {"status": status,
                                     "detail": str((blocked or {}).get("detail", ""))[:160]}

    # A fresh, current-cycle observation attached by the engineer, verified by the reviewer.
    source_id = asyncio.run(insert_observation(target.get("asset_id")))
    status, attached = call("POST", f"/api/v1/incidents/{incident_id}/evidence",
                            {"evidence": [{"source_type": "analysis", "source_id": source_id,
                                           "observed_at": "2026-11-19T12:00:00Z"}]},
                            token=engineer)
    out["attach_status"] = status
    evidence_id = None
    for row in (attached or {}).get("evidence", []):
        if row.get("source_id") == source_id:
            evidence_id = row["evidence_id"]
    out["attached_evidence_id"] = evidence_id

    status, resolved = call("PATCH", f"/api/v1/incidents/{incident_id}/status",
                            {"status": "resolved", "verification": {"evidence_id": evidence_id}},
                            token=reviewer)
    out["resolve_status"] = status
    if status == 200:
        out["resolved_state"] = resolved.get("status")
        out["verification_rows"] = len(resolved.get("verifications", []))
        latest = (resolved.get("verifications") or [{}])[-1]
        out["latest_verifier"] = latest.get("verifier_id")
        out["latest_cycle"] = latest.get("remediation_cycle")

    status, after = call("GET", f"/api/v1/incidents/{incident_id}", token=engineer)
    out["persisted_status"] = after.get("status")
    out["persisted_verifications"] = len(after.get("verifications", []))

    print(json.dumps(out, indent=2))
    return 0 if out.get("resolve_status") == 200 and out.get("persisted_status") == "resolved" else 1


if __name__ == "__main__":
    sys.exit(main())
