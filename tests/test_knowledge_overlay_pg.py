"""Gate 2b: knowledge overlay migration and append-only enforcement.

Runs the real Alembic chain to head on a throw-away schema in the disposable
PostgreSQL instance, then proves:
  * the new tables exist with their constraints,
  * the append-only trigger rejects UPDATE / DELETE / TRUNCATE,
  * inserting a decision and a current-state row works.
"""
import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.incident_db_support import require_database_url, scoped_engine

HEAD = "c9f4a7b0d826"


def _create_schema(url: str) -> tuple[str, object]:
    schema = "eims_know_" + uuid.uuid4().hex
    engine = create_async_engine(url, poolclass=NullPool)
    return schema, engine


async def _migrate(engine, schema: str) -> None:
    from alembic import command
    from alembic.config import Config

    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    async with engine.connect() as conn:
        ext = (await conn.execute(text(
            "SELECT DISTINCT n.nspname FROM pg_extension e "
            "JOIN pg_namespace n ON n.oid = e.extnamespace "
            "WHERE e.extname IN ('vector','pg_trgm')"
        ))).scalars().all()
        suffix = "".join(
            ", " + conn.dialect.identifier_preparer.quote(n) for n in ext if n != schema
        )
        await conn.execute(text(f'SET search_path TO "{schema}"{suffix}'))
        await conn.commit()

        def run(connection):
            cfg = Config()
            cfg.set_main_option("script_location", "migrations")
            cfg.attributes.update(connection=connection, version_table_schema=schema)
            command.upgrade(cfg, "head")

        await conn.run_sync(run)


def test_knowledge_overlay_migration_and_immutability():
    url = require_database_url()

    async def scenario():
        schema, bootstrap = _create_schema(url)
        try:
            await _migrate(bootstrap, schema)
            engine = scoped_engine(url, schema)
            try:
                async with engine.connect() as conn:
                    head = await conn.scalar(
                        text(f'SELECT version_num FROM "{schema}".alembic_version')
                    )
                    assert head == HEAD, head
                    tables = (await conn.execute(text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = :s AND table_name LIKE 'knowledge_%'"
                    ), {"s": schema})).scalars().all()
                    assert set(tables) >= {"knowledge_review", "knowledge_review_event"}

                # insert a decision + current state
                async with engine.begin() as conn:
                    await conn.execute(text(
                        f'INSERT INTO {schema}.knowledge_review_event '
                        "(event_id, catalog_id, event_type, to_status, actor, "
                        " source_hash, revision) "
                        "VALUES (:e, 'windows_event:official_event_id:4625', 'promotion', "
                        "        'candidate', 'demo.reviewer', :h, 1)"
                    ), {"e": uuid.uuid4(), "h": "a" * 64})
                    await conn.execute(text(
                        f'INSERT INTO {schema}.knowledge_review '
                        "(catalog_id, catalog_source, content_hash, lifecycle_status) "
                        "VALUES ('windows_event:official_event_id:4625', 'operational', :h, 'candidate')"
                    ), {"h": "a" * 64})

                for statement in (
                    f"UPDATE {schema}.knowledge_review_event SET actor = 'forged'",
                    f"DELETE FROM {schema}.knowledge_review_event",
                    f"TRUNCATE {schema}.knowledge_review_event",
                ):
                    with pytest.raises(DBAPIError) as exc:
                        async with engine.begin() as conn:
                            await conn.execute(text(statement))
                    assert "append-only" in str(exc.value), str(exc.value)

                # history still readable and intact
                async with engine.connect() as conn:
                    rows = (await conn.execute(text(
                        f"SELECT count(*) FROM {schema}.knowledge_review_event"
                    ))).scalar()
                    assert rows == 1
                    await conn.rollback()
            finally:
                await engine.dispose()
        finally:
            await bootstrap.dispose()

    asyncio.run(scenario())


def test_startup_scenarios_idempotent_upgrade_and_lifespan():
    """Scenario A/B approximation on disposable infrastructure.

    A: upgrade to head twice -> second run is a no-op (already-upgraded DB stays
       compatible with the startup path).
    B: the application lifespan starts with the new revision present in the
       graph, and the canonical summary endpoint answers.
    """
    import os
    from urllib.parse import urlsplit

    from fastapi.testclient import TestClient

    url = require_database_url()
    schema, bootstrap = _create_schema(url)

    async def migrate_twice() -> str:
        await _migrate(bootstrap, schema)
        await _migrate(bootstrap, schema)  # must not raise
        engine = scoped_engine(url, schema)
        try:
            async with engine.connect() as conn:
                head = await conn.scalar(
                    text(f'SELECT version_num FROM "{schema}".alembic_version')
                )
                await conn.rollback()
                return head
        finally:
            await engine.dispose()

    try:
        head = asyncio.run(migrate_twice())
        assert head == HEAD, head
    finally:
        asyncio.run(bootstrap.dispose())

    # Scenario B: real lifespan against the disposable database.
    # tests/conftest.py imports backend.main (and thus builds the global settings
    # object) at collection time, so environment variables set here would be
    # ignored and lifespan would connect to the operational default. Pin the
    # already-built settings object to the disposable database instead.
    from urllib.parse import unquote

    from backend.core.config import settings
    from backend.main import app

    parts = urlsplit(url)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "DB_HOST", parts.hostname or "127.0.0.1")
        mp.setattr(settings, "DB_PORT", parts.port or 5432)
        mp.setattr(settings, "DB_NAME", (parts.path or "/").lstrip("/"))
        mp.setattr(settings, "DB_USER", unquote(parts.username or ""))
        mp.setattr(settings, "DB_PASSWORD", unquote(parts.password or ""))
        mp.setenv("EIMS_DEMO_SOFT_DEPS", "1")
        mp.setenv("EIMS_AUTH_MODE", "demo")
        mp.delenv("EIMS_DB_IDENTITY", raising=False)
        mp.delenv("EIMS_DB_IDENTITY_REQUIRED", raising=False)
        assert (settings.DB_HOST, settings.DB_PORT) != ("localhost", 5432)
        assert settings.DB_NAME != "eims_registry"

        # The migrated objects live in a private schema, which the application's
        # default search path does not include; the schema-bound HTTP proof is in
        # tests/test_catalog_summary_http.py. Here we prove the lifespan starts
        # against the disposable target, and that a missing overlay fails loudly
        # rather than returning fabricated counts.
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/analyzer/catalog/summary")
            if response.status_code == 200:
                assert response.json()["counts"]["operational_context"] == 153
            else:
                assert response.status_code in (401, 403, 500), response.text
                assert "counts" not in (response.json() if response.headers.get(
                    "content-type", "").startswith("application/json") else {})

