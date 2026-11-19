"""Provision the Neon demo database for EIMS.

Reads the owner connection string from a local file, derives the DIRECT host
(the copied string uses the -pooler hostname), then:
  1. verifies the target database identity,
  2. applies deploy/sql/01_roles.sql (roles + schema access),
  3. sets generated passwords for eims_migrator / eims_runtime,
  4. runs Alembic with the MIGRATION role on the direct host,
  5. applies deploy/sql/02_runtime_grants.sql as the migration role,
  6. verifies ownership, posture and triggers.

Secrets are written to a local file next to the input; nothing secret is printed.
"""
from __future__ import annotations

import asyncio
import os
import re
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


def _read_url() -> str:
    raw = URL_FILE.read_text(encoding="utf-8").strip().strip('"').strip("'")
    if not raw.startswith(("postgres://", "postgresql://")):
        raise SystemExit("connection string missing")
    parts = urlsplit(raw)
    host = parts.hostname or ""
    direct_host = host.replace("-pooler", "")
    query = "ssl=require"
    netloc = parts.netloc.replace(host, direct_host)
    return urlunsplit(("postgresql+asyncpg", netloc, parts.path, query, ""))


def _with_role(super_url: str, role: str, password: str) -> str:
    parts = urlsplit(super_url)
    userinfo = f"{role}:{password}"
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{userinfo}@{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, ""))


async def _exec_script(engine, sql: str, settings: dict[str, str] | None = None) -> None:
    async with engine.begin() as conn:
        for key, value in (settings or {}).items():
            await conn.execute(text("SELECT set_config(:k, :v, false)"), {"k": key, "v": value})
        raw = await conn.get_raw_connection()
        driver = getattr(raw, "driver_connection", None) or raw.dbapi_connection
        await driver.execute(sql)


async def _scalar(engine, sql: str, **params):
    async with engine.connect() as conn:
        value = (await conn.execute(text(sql), params)).scalar()
        await conn.rollback()
        return value


async def main() -> int:
    owner_url = _read_url()
    db_name = urlsplit(owner_url).path.lstrip("/")
    print(f"target_database={db_name}")

    owner = create_async_engine(owner_url, poolclass=None)
    try:
        ident = await _scalar(owner, "SELECT current_database() || '|' || current_user")
        print(f"identity={ident}")
        if not ident.startswith(db_name + "|"):
            raise SystemExit("database identity mismatch")

        roles_sql = (ROOT / "deploy" / "sql" / "01_roles.sql").read_text(encoding="utf-8")
        try:
            await _exec_script(owner, roles_sql, {
                "eims.mig_role": "eims_migrator",
                "eims.runtime_role": "eims_runtime",
            })
            print("step=01_roles ok")
        except Exception as exc:  # noqa: BLE001
            print(f"step=01_roles failed: {type(exc).__name__}: {str(exc)[:300]}")
            raise

        mig_pw = secrets.token_urlsafe(24)
        rt_pw = secrets.token_urlsafe(24)
        async with owner.begin() as conn:
            await conn.execute(text(f"ALTER ROLE eims_migrator PASSWORD '{mig_pw}'"))
            await conn.execute(text(f"ALTER ROLE eims_runtime  PASSWORD '{rt_pw}'"))
        print("step=passwords set")

        SECRET_FILE.write_text(
            "# EIMS demo secrets (local only, do not commit)\n"
            f"EIMS_DB_USER=eims_runtime\nEIMS_DB_PASSWORD={rt_pw}\n"
            f"EIMS_MIGRATOR_USER=eims_migrator\nEIMS_MIGRATOR_PASSWORD={mig_pw}\n",
            encoding="utf-8",
        )
        print(f"secrets_file={SECRET_FILE}")
    finally:
        await owner.dispose()

    mig_url = _with_role(owner_url, "eims_migrator", mig_pw)
    env = os.environ.copy()
    parts = urlsplit(mig_url)
    env.update({
        "EIMS_DB_USER": "eims_migrator",
        "EIMS_DB_PASSWORD": mig_pw,
        "EIMS_DB_HOST": parts.hostname or "",
        "EIMS_DB_PORT": str(parts.port or 5432),
        "EIMS_DB_NAME": db_name,
    })
    proc = subprocess.run(
        [str(ROOT / "venv" / "Scripts" / "python.exe"), "-m", "alembic", "upgrade", "head"],
        cwd=str(ROOT), env=env, capture_output=True, text=True,
    )
    print(f"step=alembic exit={proc.returncode}")
    if proc.returncode != 0:
        print((proc.stdout or "")[-800:])
        print((proc.stderr or "")[-1200:])
        return proc.returncode

    mig = create_async_engine(mig_url, poolclass=None)
    try:
        grants_sql = (ROOT / "deploy" / "sql" / "02_runtime_grants.sql").read_text(encoding="utf-8")
        await _exec_script(mig, grants_sql, {
            "eims.mig_role": "eims_migrator",
            "eims.runtime_role": "eims_runtime",
        })
        print("step=02_grants ok")

        version = (await _scalar(mig, "SELECT version_num FROM alembic_version"))
        print(f"alembic_current={version}")
        owners = await _scalar(mig, (
            "SELECT string_agg(relname || '=' || pg_get_userbyid(relowner), ',' ORDER BY relname) "
            "FROM pg_class WHERE relname IN ('incidents','incident_evidence','incident_verification')"
        ))
        print(f"owners={owners}")
        triggers = await _scalar(mig, (
            "SELECT string_agg(tgname, ',' ORDER BY tgname) FROM pg_trigger "
            "WHERE tgname LIKE 'trg_incident_%' AND NOT tgisinternal"
        ))
        print(f"triggers={triggers}")
        posture = await _scalar(mig, (
            "SELECT rolname || '|super=' || rolsuper || '|bypassrls=' || rolbypassrls "
            "FROM pg_roles WHERE rolname='eims_runtime'"
        ))
        print(f"runtime_posture={posture}")
        owned = await _scalar(mig, (
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relowner = 'eims_runtime'::regrole"
        ))
        print(f"runtime_owned_relations={owned}")
        memberships = await _scalar(mig, (
            "SELECT count(*) FROM pg_auth_members WHERE member = 'eims_runtime'::regrole"
        ))
        print(f"runtime_memberships={memberships}")
    finally:
        await mig.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
