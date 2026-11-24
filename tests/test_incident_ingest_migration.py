"""c4e8a1f7b932 (incident_ingest_outbox): empty/populated upgrade, downgrade/re-upgrade, non-superuser.

Runs only on the dedicated disposable Incident Ingest v1.1 PostgreSQL (identity-verified); every test
uses a unique retained schema. Reuses the Alembic runner helpers of the Incident Core migration tests.
"""
from __future__ import annotations

import uuid

from sqlalchemy import inspect, text

from tests.incident_ingest_support import require_pg_url, verify_pg_identity
from tests.incident_db_support import scoped_engine
from tests.test_incident_migration import (
    HEAD_REVISION, INCIDENT_REVISION, _create_schema, _run_migrations, _version,
)


async def _prepare():
    url = require_pg_url()
    await verify_pg_identity(url)
    schema, bootstrap = await _create_schema(url)
    return url, schema, bootstrap


async def _outbox_facts(engine, schema):
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names(schema=schema)))
        if "incident_ingest_outbox" not in tables:
            return tables, None
        info = await conn.run_sync(lambda c: {
            "unique": {u["name"] for u in inspect(c).get_unique_constraints("incident_ingest_outbox", schema=schema)},
            "checks": {k["name"] for k in inspect(c).get_check_constraints("incident_ingest_outbox", schema=schema)},
            "indexes": {i["name"]: i for i in inspect(c).get_indexes("incident_ingest_outbox", schema=schema)},
            "fks": inspect(c).get_foreign_keys("incident_ingest_outbox", schema=schema)})
        return tables, info


def test_empty_schema_upgrade_downgrade_and_reupgrade():
    import asyncio

    async def scenario():
        url, schema, bootstrap = await _prepare()
        try:
            await _run_migrations(bootstrap, schema, upgrade="head")
            assert await _version(bootstrap, schema) == HEAD_REVISION
            engine = scoped_engine(url, schema)
            try:
                async with engine.connect() as conn:
                    is_super = await conn.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user"))
                assert is_super is False
                tables, info = await _outbox_facts(engine, schema)
                assert info is not None and {"incidents", "incident_evidence"} <= tables
                assert info["unique"] == {"uq_incident_ingest_outbox_source"}
                assert {"ck_incident_ingest_outbox_source_type",
                        "ck_incident_ingest_outbox_provenance_bounded"} <= info["checks"]
                assert "idx_incident_ingest_outbox_pending" in info["indexes"]
                assert any(fk["referred_table"] == "infrastructure_assets"
                           and fk.get("options", {}).get("ondelete") == "RESTRICT" for fk in info["fks"])
            finally:
                await engine.dispose()

            await _run_migrations(bootstrap, schema, downgrade=INCIDENT_REVISION)
            assert await _version(bootstrap, schema) == INCIDENT_REVISION
            engine = scoped_engine(url, schema)
            try:
                tables, info = await _outbox_facts(engine, schema)
                assert info is None and {"incidents", "incident_evidence", "analysis_history"} <= tables
            finally:
                await engine.dispose()

            await _run_migrations(bootstrap, schema, upgrade="head")
            assert await _version(bootstrap, schema) == HEAD_REVISION
        finally:
            await bootstrap.dispose()

    asyncio.run(scenario())


def test_populated_parent_is_preserved_and_downgrade_touches_only_the_outbox():
    import asyncio

    async def scenario():
        url, schema, bootstrap = await _prepare()
        try:
            await _run_migrations(bootstrap, schema, upgrade=INCIDENT_REVISION)
            engine = scoped_engine(url, schema)
            asset_id = uuid.uuid4()
            try:
                async with engine.begin() as conn:
                    await conn.execute(text(
                        "INSERT INTO infrastructure_assets (asset_id, hostname, canonical_ip, "
                        "cryptographic_fingerprint, lifecycle_state, current_compliance_score, "
                        "created_at, updated_at) "
                        "VALUES (:a, 'synthetic', '127.0.0.1', :f, 'Discovered', 0, now(), now())"),
                        {"a": asset_id, "f": uuid.uuid4().hex + uuid.uuid4().hex})
                    await conn.execute(text(
                        "INSERT INTO analysis_history (event_id, provider, username, asset_id) "
                        "VALUES ('1', 'synthetic', 'synthetic', :a)"), {"a": asset_id})
            finally:
                await engine.dispose()

            await _run_migrations(bootstrap, schema, upgrade="head")
            engine = scoped_engine(url, schema)
            try:
                async with engine.begin() as conn:
                    assert await conn.scalar(text("SELECT count(*) FROM analysis_history")) == 1
                    assert await conn.scalar(text("SELECT count(*) FROM incident_ingest_outbox")) == 0
                    await conn.execute(text(
                        "INSERT INTO incident_ingest_outbox (outbox_id, source_type, source_id, observed_at) "
                        "VALUES (:o, 'analysis', '1', now())"), {"o": uuid.uuid4()})
            finally:
                await engine.dispose()

            await _run_migrations(bootstrap, schema, downgrade=INCIDENT_REVISION)
            engine = scoped_engine(url, schema)
            try:
                async with engine.connect() as conn:
                    assert await conn.scalar(text("SELECT count(*) FROM analysis_history")) == 1
                    assert await conn.scalar(text("SELECT count(*) FROM infrastructure_assets")) == 1
                    gone = await conn.scalar(text("SELECT to_regclass('incident_ingest_outbox')"))
                assert gone is None
            finally:
                await engine.dispose()
        finally:
            await bootstrap.dispose()

    asyncio.run(scenario())
