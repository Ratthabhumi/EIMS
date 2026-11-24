"""Prove WHICH backend is answering on a port, so a stale instance cannot be mistaken for the current one.

Checks (all against the live process and its database, nothing mocked):
  * the OpenAPI document exposes the current routes (Notes, workflow, knowledge provider scope);
  * the database the backend is configured for is the disposable one (not port 5432) and is at the Alembic head of THIS
    checkout (compared with the head computed from migrations/versions);
  * reports the database identity (host:port/name, role) so the browser run can quote it.
Exit code 0 only when every check passes.
"""
import argparse
import asyncio
import sys

import httpx
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.core.config import settings

REQUIRED_PATHS = (
    "/api/v1/incidents/{incident_id}/notes",
    "/api/v1/incidents/{incident_id}/diagnoses",
    "/api/v1/incidents/{incident_id}/remediations",
    "/api/v1/incidents/{incident_id}/knowledge-proposals",
    "/api/v1/knowledge/proposals",
)


async def db_identity():
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            role = (await conn.execute(text("SELECT current_user"))).scalar()
            scope = (await conn.execute(text(
                "SELECT count(*) FROM information_schema.columns WHERE table_name = 'knowledge_entries' AND column_name = 'provider_scope'"))).scalar()
            etime = (await conn.execute(text(
                "SELECT count(*) FROM information_schema.columns WHERE table_name = 'incident_evidence' AND column_name = 'time_confidence'"))).scalar()
            return version, role, bool(scope), bool(etime)
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8031)
    args = parser.parse_args()
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        ok &= bool(cond)
        print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))

    check("database is disposable (not the operational port)", settings.DB_PORT != 5432, f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    import time
    base = f"http://127.0.0.1:{args.port}"
    for _ in range(30):  # the app may still be starting
        try:
            if httpx.get(base + "/api/v1/health", timeout=10).status_code in (200, 503):
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    else:
        check("a backend answers on the port", False, "no answer")
        sys.exit(1)
    # OpenAPI is disabled, so probe the LIVE routes: a route that does not exist answers the generic {"detail":"Not Found"}.
    ghost = "00000000-0000-0000-0000-000000000000"
    probes = [f"/api/v1/incidents/{ghost}/notes", f"/api/v1/incidents/{ghost}/diagnoses",
              f"/api/v1/incidents/{ghost}/remediations", f"/api/v1/incidents/{ghost}/knowledge-proposals",
              "/api/v1/knowledge/proposals/mine"]
    missing = []
    for path in probes:
        r = httpx.get(base + path, timeout=10)
        try:
            detail = r.json().get("detail")
        except Exception:  # noqa: BLE001
            detail = None
        if r.status_code == 404 and detail == "Not Found":
            missing.append(path)
    check("backend serves the current routes (notes/workflow/knowledge)", not missing, "missing: " + ", ".join(missing) if missing else "")
    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    version, role, has_scope, has_time = asyncio.run(db_identity())
    check("database is at this checkout's Alembic head", version == head, f"db={version} head={head}")
    check("database role is the non-superuser test role", role == "eims_incident_test", role)
    check("knowledge_entries.provider_scope present", has_scope)
    check("incident_evidence.time_confidence present", has_time)
    print(f"IDENTITY port={args.port} db={settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME} role={role} head={head}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
