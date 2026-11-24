"""Incident Core migration: single head, additive upgrade, safe downgrade, FKs.

Runs only against the explicitly allowlisted disposable PostgreSQL role and
database. Every test creates a uniquely named schema and retains it.
"""

import asyncio
import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.incident_db_support import require_database_url, scoped_engine

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "versions"
PARENT_REVISION = "a4b7c9d2e601"
INCIDENT_REVISION = "b8d3f5c1a720"
# v1.1 added the additive incident_ingest_outbox revision on top of the Incident Core revision.
HEAD_REVISION = "c9f4a7b0d826"
INCIDENT_MIGRATION_FILE = MIGRATIONS_DIR / f"{INCIDENT_REVISION}_add_incident_core.py"

_REVISION_RE = re.compile(r"^revision(?::[^=]+)?\s*=\s*['\"]([0-9a-f]+)['\"]", re.MULTILINE)
_DOWN_REVISION_RE = re.compile(
    r"^down_revision(?::[^=]+)?\s*=\s*['\"]([0-9a-f]+)['\"]", re.MULTILINE
)


def _migration_graph():
    revisions = set()
    parents = set()
    for path in MIGRATIONS_DIR.glob("*.py"):
        if path.name == "__init__.py":
            continue
        content = path.read_text(encoding="utf-8")
        revision = _REVISION_RE.search(content)
        if revision:
            revisions.add(revision.group(1))
        parent = _DOWN_REVISION_RE.search(content)
        if parent:
            parents.add(parent.group(1))
    return revisions, parents


def test_incident_migration_is_the_single_head():
    revisions, parents = _migration_graph()
    heads = revisions - parents
    assert heads == {HEAD_REVISION}, heads
    assert INCIDENT_REVISION in revisions
    content = INCIDENT_MIGRATION_FILE.read_text(encoding="utf-8")
    assert f'down_revision = "{PARENT_REVISION}"' in content


async def _create_schema(url: str) -> tuple[str, object]:
    schema = "eims_incident_mig_" + uuid.uuid4().hex
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    return schema, engine


async def _run_migrations(engine, schema: str, *, upgrade: str | None = None,
                          downgrade: str | None = None) -> None:
    from alembic import command
    from alembic.config import Config

    async with engine.connect() as conn:
        extension_schemas = (
            await conn.execute(
                text(
                    "SELECT DISTINCT n.nspname FROM pg_extension e "
                    "JOIN pg_namespace n ON n.oid = e.extnamespace "
                    "WHERE e.extname IN ('vector','pg_trgm') ORDER BY n.nspname"
                )
            )
        ).scalars().all()
        suffix = "".join(
            ", " + conn.dialect.identifier_preparer.quote(name)
            for name in extension_schemas
            if name != schema
        )
        await conn.execute(text(f'SET search_path TO "{schema}"{suffix}'))
        await conn.commit()

        def run(connection):
            config = Config()
            config.set_main_option("script_location", "migrations")
            config.attributes.update(
                connection=connection, version_table_schema=schema
            )
            if upgrade is not None:
                command.upgrade(config, upgrade)
            if downgrade is not None:
                command.downgrade(config, downgrade)

        await conn.run_sync(run)


async def _version(engine, schema: str) -> str:
    async with engine.connect() as conn:
        return await conn.scalar(text(f'SELECT version_num FROM "{schema}".alembic_version'))


async def _expect_integrity_error(engine, sql: str, params=None) -> None:
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(text(sql), params or {})


def test_empty_schema_upgrade_downgrade_and_reupgrade():
    url = require_database_url()

    async def scenario():
        schema, bootstrap = await _create_schema(url)
        try:
            await _run_migrations(bootstrap, schema, upgrade="head")
            engine = scoped_engine(url, schema)
            try:
                assert await _version(bootstrap, schema) == HEAD_REVISION

                async with engine.connect() as conn:
                    role, is_super = (
                        await conn.execute(
                            text("SELECT current_user, rolsuper FROM pg_roles "
                                 "WHERE rolname = current_user")
                        )
                    ).one()
                    assert role == "eims_incident_test"
                    assert is_super is False

                    tables = await conn.run_sync(
                        lambda c: set(inspect(c).get_table_names(schema=schema))
                    )
                    assert {"incidents", "incident_evidence", "analysis_history"} <= tables

                    history_columns = await conn.run_sync(
                        lambda c: {col["name"] for col in inspect(c).get_columns("analysis_history", schema=schema)}
                    )
                    assert "asset_id" in history_columns

                    history_indexes = await conn.run_sync(
                        lambda c: {idx["name"] for idx in inspect(c).get_indexes("analysis_history", schema=schema)}
                    )
                    assert "ix_analysis_history_asset_id" in history_indexes

                    incident_indexes = await conn.run_sync(
                        lambda c: {idx["name"] for idx in inspect(c).get_indexes("incidents", schema=schema)}
                    )
                    assert {
                        "ix_incidents_asset_id",
                        "ix_incidents_status_last_seen",
                        "ix_incidents_severity_last_seen",
                    } <= incident_indexes

                    evidence_indexes = await conn.run_sync(
                        lambda c: {idx["name"] for idx in inspect(c).get_indexes("incident_evidence", schema=schema)}
                    )
                    assert {
                        "ix_incident_evidence_incident_id",
                        "ix_incident_evidence_observed_at",
                    } <= evidence_indexes

                    unique_names = await conn.run_sync(
                        lambda c: {u["name"] for u in inspect(c).get_unique_constraints("incidents", schema=schema)}
                    )
                    assert "uq_incidents_dedupe_key" in unique_names
                    evidence_unique = await conn.run_sync(
                        lambda c: {u["name"] for u in inspect(c).get_unique_constraints("incident_evidence", schema=schema)}
                    )
                    assert "uq_incident_evidence_source" in evidence_unique

                    checks = await conn.run_sync(
                        lambda c: {ck["name"] for ck in inspect(c).get_check_constraints("incidents", schema=schema)}
                    )
                    assert {
                        "ck_incident_status_valid",
                        "ck_incident_severity_valid",
                        "ck_incident_confidence_valid",
                        "ck_incident_root_cause_state_valid",
                        "ck_incident_seen_window_ordered",
                    } <= checks

                    incident_fks = await conn.run_sync(
                        lambda c: inspect(c).get_foreign_keys("incidents", schema=schema)
                    )
                    assert any(
                        fk["referred_table"] == "infrastructure_assets"
                        and fk.get("options", {}).get("ondelete") == "RESTRICT"
                        for fk in incident_fks
                    )
                    evidence_fks = await conn.run_sync(
                        lambda c: inspect(c).get_foreign_keys("incident_evidence", schema=schema)
                    )
                    assert any(
                        fk["referred_table"] == "incidents"
                        and fk.get("options", {}).get("ondelete") == "CASCADE"
                        for fk in evidence_fks
                    )

                    await conn.execute(
                        text(
                            "INSERT INTO analysis_history (event_id, provider, username, description) "
                            "VALUES ('1129','synthetic','synthetic-mig','SYNTHETIC ONLY')"
                        )
                    )
                    await conn.commit()
            finally:
                await engine.dispose()

            # Safe downgrade: new tables/column disappear, existing rows survive.
            await _run_migrations(bootstrap, schema, downgrade=PARENT_REVISION)
            assert await _version(bootstrap, schema) == PARENT_REVISION
            downgraded = scoped_engine(url, schema)
            try:
                async with downgraded.connect() as conn:
                    tables = await conn.run_sync(
                        lambda c: set(inspect(c).get_table_names(schema=schema))
                    )
                    assert "incidents" not in tables
                    assert "incident_evidence" not in tables
                    columns = await conn.run_sync(
                        lambda c: {col["name"] for col in inspect(c).get_columns("analysis_history", schema=schema)}
                    )
                    assert "asset_id" not in columns
                    assert await conn.scalar(text("SELECT count(*) FROM analysis_history")) == 1
            finally:
                await downgraded.dispose()

            await _run_migrations(bootstrap, schema, upgrade="head")
            assert await _version(bootstrap, schema) == HEAD_REVISION
            reupgraded = scoped_engine(url, schema)
            try:
                async with reupgraded.connect() as conn:
                    assert await conn.scalar(text("SELECT count(*) FROM analysis_history")) == 1
                    assert await conn.scalar(
                        text("SELECT count(*) FROM analysis_history WHERE asset_id IS NOT NULL")
                    ) == 0
            finally:
                await reupgraded.dispose()
        finally:
            await bootstrap.dispose()

    asyncio.run(scenario())


def test_populated_parent_upgrade_preserves_rows_and_never_backfills_asset():
    url = require_database_url()
    fingerprint = uuid.uuid4().hex + uuid.uuid4().hex

    async def scenario():
        schema, bootstrap = await _create_schema(url)
        try:
            await _run_migrations(bootstrap, schema, upgrade=PARENT_REVISION)
            assert await _version(bootstrap, schema) == PARENT_REVISION

            engine = scoped_engine(url, schema)
            try:
                async with engine.begin() as conn:
                    asset_id = uuid.uuid4()
                    await conn.execute(
                        text(
                            "INSERT INTO infrastructure_assets "
                            "(asset_id, hostname, canonical_ip, cryptographic_fingerprint, "
                            "lifecycle_state, current_compliance_score, created_at, updated_at) "
                            "VALUES (:id,'synthetic-mig-host','127.0.0.1',:fp,'Discovered',0,now(),now())"
                        ),
                        {"id": asset_id, "fp": fingerprint},
                    )
                    for name in ("synthetic-pre-user", "synthetic-pre-other"):
                        await conn.execute(
                            text(
                                "INSERT INTO analysis_history "
                                "(event_id, provider, username, description, solution_summary) "
                                "VALUES ('1129','synthetic',:u,'SYNTHETIC ONLY',:s)"
                            ),
                            {"u": name, "s": '{"overview":"synthetic retained evidence"}'},
                        )
                    await conn.execute(
                        text(
                            "INSERT INTO audit_logs (log_id, asset_id, action_verb, performed_at, immutable_payload) "
                            "VALUES (:l,:a,'TRANSITION_STATE',now(),CAST(:p AS jsonb))"
                        ),
                        {
                            "l": uuid.uuid4(),
                            "a": asset_id,
                            "p": '{"previous_state":"Discovered","new_state":"Active"}',
                        },
                    )
                    before_history = (
                        await conn.execute(
                            text(
                                "SELECT (to_jsonb(h) - 'asset_id')::text "
                                "FROM analysis_history h ORDER BY id"
                            )
                        )
                    ).scalars().all()
                    before_audit = (
                        await conn.execute(
                            text("SELECT row_to_json(a)::text FROM audit_logs a ORDER BY log_id")
                        )
                    ).scalars().all()
            finally:
                await engine.dispose()

            await _run_migrations(bootstrap, schema, upgrade="head")
            assert await _version(bootstrap, schema) == HEAD_REVISION

            engine = scoped_engine(url, schema)
            try:
                async with engine.connect() as conn:
                    after_history = (
                        await conn.execute(
                            text(
                                "SELECT (to_jsonb(h) - 'asset_id')::text "
                                "FROM analysis_history h ORDER BY id"
                            )
                        )
                    ).scalars().all()
                    after_audit = (
                        await conn.execute(
                            text("SELECT row_to_json(a)::text FROM audit_logs a ORDER BY log_id")
                        )
                    ).scalars().all()
                    assert after_history == before_history
                    assert after_audit == before_audit
                    assert await conn.scalar(
                        text("SELECT count(*) FROM analysis_history WHERE asset_id IS NOT NULL")
                    ) == 0

                    # Explicit identity linking works; fabricated ids are refused.
                    await conn.execute(
                        text("UPDATE analysis_history SET asset_id = :a WHERE username = 'synthetic-pre-user'"),
                        {"a": asset_id},
                    )
                    await conn.commit()
                    assert await conn.scalar(
                        text("SELECT count(*) FROM analysis_history WHERE asset_id = :a"),
                        {"a": asset_id},
                    ) == 1
            finally:
                await engine.dispose()

            engine = scoped_engine(url, schema)
            try:
                await _expect_integrity_error(
                    engine,
                    "UPDATE analysis_history SET asset_id = :a WHERE username = 'synthetic-pre-other'",
                    {"a": uuid.uuid4()},
                )
            finally:
                await engine.dispose()
        finally:
            await bootstrap.dispose()

    asyncio.run(scenario())


def test_constraint_and_referential_integrity_behavior():
    url = require_database_url()
    first = uuid.uuid4().hex + uuid.uuid4().hex
    second = uuid.uuid4().hex + uuid.uuid4().hex
    dedupe = "c" * 64

    async def scenario():
        schema, bootstrap = await _create_schema(url)
        try:
            await _run_migrations(bootstrap, schema, upgrade="head")
            engine = scoped_engine(url, schema)
            try:
                async with engine.begin() as conn:
                    asset_a = uuid.uuid4()
                    asset_b = uuid.uuid4()
                    incident_a = uuid.uuid4()
                    await conn.execute(
                        text(
                            "INSERT INTO infrastructure_assets "
                            "(asset_id, hostname, canonical_ip, cryptographic_fingerprint, "
                            "lifecycle_state, current_compliance_score, created_at, updated_at) "
                            "VALUES (:id,'synthetic-a','127.0.0.1',:fp,'Discovered',0,now(),now())"
                        ),
                        {"id": asset_a, "fp": first},
                    )
                    await conn.execute(
                        text(
                            "INSERT INTO infrastructure_assets "
                            "(asset_id, hostname, canonical_ip, cryptographic_fingerprint, "
                            "lifecycle_state, current_compliance_score, created_at, updated_at) "
                            "VALUES (:id,'synthetic-b','127.0.0.1',:fp,'Discovered',0,now(),now())"
                        ),
                        {"id": asset_b, "fp": second},
                    )
                    await conn.execute(
                        text(
                            "INSERT INTO incidents "
                            "(incident_id, title, severity, confidence, asset_id, first_seen, last_seen, dedupe_key) "
                            "VALUES (:iid,'synthetic incident A','high','strong',:a,"
                            "'2026-11-16T10:00:00Z','2026-11-16T10:05:00Z',:k)"
                        ),
                        {"iid": incident_a, "a": asset_a, "k": dedupe},
                    )
                    await conn.execute(
                        text(
                            "INSERT INTO incidents "
                            "(incident_id, title, severity, confidence, asset_id, first_seen, last_seen, dedupe_key) "
                            "VALUES (:iid,'synthetic incident B','low','weak',:b,"
                            "'2026-11-16T10:00:00Z','2026-11-16T10:05:00Z',:k)"
                        ),
                        {"iid": uuid.uuid4(), "b": asset_b, "k": "d" * 64},
                    )
                    await conn.execute(
                        text(
                            "INSERT INTO incident_evidence "
                            "(evidence_id, incident_id, source_type, source_id, evidence_digest, observed_at, added_by) "
                            "VALUES (:eid,:i,'winlog','synthetic-1',:d,'2026-11-16T10:00:00Z','synthetic-tester')"
                        ),
                        {"eid": uuid.uuid4(), "i": incident_a, "d": "e" * 64},
                    )
                    await conn.commit()

                await _expect_integrity_error(
                    engine,
                    "INSERT INTO incidents "
                    "(incident_id, title, severity, confidence, asset_id, first_seen, last_seen, dedupe_key) "
                    "VALUES (:iid,'duplicate','low','weak',:a,'2026-11-16T10:00:00Z',"
                    "'2026-11-16T10:05:00Z',:k)",
                    {"iid": uuid.uuid4(), "a": asset_a, "k": dedupe},
                )
                await _expect_integrity_error(
                    engine,
                    "INSERT INTO incident_evidence "
                    "(evidence_id, incident_id, source_type, source_id, evidence_digest, observed_at, added_by) "
                    "VALUES (:eid,:i,'winlog','synthetic-1',:d,'2026-11-16T10:00:00Z','synthetic-tester')",
                    {"eid": uuid.uuid4(), "i": incident_a, "d": "f" * 64},
                )
                await _expect_integrity_error(
                    engine,
                    "INSERT INTO incidents "
                    "(incident_id, title, severity, confidence, asset_id, first_seen, last_seen, dedupe_key) "
                    "VALUES (:iid,'bad fk','low','weak',:a,'2026-11-16T10:00:00Z',"
                    "'2026-11-16T10:05:00Z',:k)",
                    {"iid": uuid.uuid4(), "a": uuid.uuid4(), "k": "1" * 64},
                )
                await _expect_integrity_error(
                    engine,
                    "INSERT INTO incidents "
                    "(incident_id, title, status, severity, confidence, first_seen, last_seen, dedupe_key) "
                    "VALUES (:iid,'bad status','archived','low','weak','2026-11-16T10:00:00Z',"
                    "'2026-11-16T10:05:00Z',:k)",
                    {"iid": uuid.uuid4(), "k": "2" * 64},
                )
                await _expect_integrity_error(
                    engine,
                    "INSERT INTO incidents "
                    "(incident_id, title, severity, confidence, first_seen, last_seen, dedupe_key) "
                    "VALUES (:iid,'bad window','low','weak','2026-11-16T10:10:00Z',"
                    "'2026-11-16T10:00:00Z',:k)",
                    {"iid": uuid.uuid4(), "k": "3" * 64},
                )
                await _expect_integrity_error(
                    engine,
                    "DELETE FROM infrastructure_assets WHERE asset_id = :a",
                    {"a": asset_a},
                )

                async with engine.begin() as conn:
                    assert await conn.scalar(
                        text("SELECT count(*) FROM incidents")
                    ) == 2, "different assets must remain separate incidents"
                    await conn.execute(
                        text("DELETE FROM incidents WHERE incident_id = :i"), {"i": incident_a}
                    )
                    assert await conn.scalar(
                        text("SELECT count(*) FROM incident_evidence WHERE incident_id = :i"),
                        {"i": incident_a},
                    ) == 0
            finally:
                await engine.dispose()
        finally:
            await bootstrap.dispose()

    asyncio.run(scenario())
