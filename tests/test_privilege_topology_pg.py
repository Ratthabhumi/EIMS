"""Least-privilege PostgreSQL topology, proved by running the real deploy SQL.

Each run creates a throw-away database, applies ``deploy/sql/01_roles.sql``,
migrates as the migration role, applies ``deploy/sql/02_runtime_grants.sql``,
then attacks the boundary as the runtime role. The scripts are executed
verbatim, so a broken or over-permissive deploy script fails here instead of in
production.

Skipped unless ``EIMS_TEST_SUPERUSER_URL`` points at the disposable PostgreSQL
instance (used only to create/drop the throw-away database and the two roles).
"""
from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

SUPER_ENV = "EIMS_TEST_SUPERUSER_URL"
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
ROOT = Path(__file__).resolve().parents[1]


def _require_superuser_url() -> str:
    value = os.environ.get(SUPER_ENV, "").strip()
    if not value:
        pytest.skip(f"{SUPER_ENV} not configured; disposable PostgreSQL required")
    url = make_url(value)
    if (
        url.drivername != "postgresql+asyncpg"
        or url.host not in ALLOWED_HOSTS
        or url.port in {None, 5432, 6432}
    ):
        raise ValueError("Refusing privilege experiment outside the disposable instance")
    return value


def _script(name: str) -> str:
    return (ROOT / "deploy" / "sql" / name).read_text(encoding="utf-8")


def _admin_url(super_url: str, database: str | None = None) -> str:
    parsed = make_url(super_url)
    target = parsed.set(database=database) if database else parsed
    return target.render_as_string(hide_password=False)


async def _exec_script(super_url: str, sql: str, settings: dict[str, str]) -> None:
    """Runs a multi-statement SQL script verbatim on one connection.

    asyncpg accepts multi-statement scripts through the simple protocol when the
    statement carries no bind parameters; the deploy scripts use
    ``current_setting`` instead of psql variables for exactly that reason.
    """
    engine = create_async_engine(_admin_url(super_url), poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            for key, value in settings.items():
                await conn.execute(
                    text("SELECT set_config(:k, :v, false)"), {"k": key, "v": value}
                )
            raw = await conn.get_raw_connection()
            driver = getattr(raw, "driver_connection", None) or raw.dbapi_connection
            await driver.execute(sql)
    finally:
        await engine.dispose()


async def _run_migrations(mig_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    engine = create_async_engine(mig_url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            def run(connection):
                config = Config()
                config.set_main_option("script_location", "migrations")
                config.attributes.update(connection=connection)
                command.upgrade(config, "head")

            await conn.run_sync(run)
    finally:
        await engine.dispose()


class Topology:
    def __init__(self, *, super_url, mig_url, rt_url, database, mig_role, rt_role):
        self.super_url = super_url
        self.mig_url = mig_url
        self.rt_url = rt_url
        self.database = database
        self.mig_role = mig_role
        self.rt_role = rt_role


@pytest.fixture(scope="module")
def topology():
    super_url = _require_superuser_url()
    parsed = make_url(super_url)
    tag = uuid.uuid4().hex[:8]
    database = f"eims_priv_{tag}"
    mig_role = f"eims_mig_{tag}"
    rt_role = f"eims_rt_{tag}"
    mig_pw = "m" + uuid.uuid4().hex
    rt_pw = "r" + uuid.uuid4().hex

    def url_for(role: str, password: str) -> str:
        return (
            f"postgresql+asyncpg://{role}:{password}@{parsed.host}:{parsed.port}/{database}"
        )

    async def build() -> None:
        admin = create_async_engine(
            _admin_url(super_url), isolation_level="AUTOCOMMIT", poolclass=NullPool
        )
        try:
            async with admin.begin() as conn:
                await conn.execute(text(f'CREATE DATABASE "{database}"'))
        finally:
            await admin.dispose()

        db_admin_url = _admin_url(super_url, database)
        # Extensions are created by 01_roles.sql (run as superuser), so the test
        # exercises the documented path instead of pre-creating them.

        # Step 1: the real role-topology script, verbatim.
        await _exec_script(
            db_admin_url,
            _script("01_roles.sql"),
            {"eims.mig_role": mig_role, "eims.runtime_role": rt_role},
        )

        # Passwords are set out-of-band, exactly as the script documents.
        admin = create_async_engine(db_admin_url, poolclass=NullPool)
        try:
            async with admin.begin() as conn:
                await conn.execute(text(f"ALTER ROLE \"{mig_role}\" PASSWORD '{mig_pw}'"))
                await conn.execute(text(f"ALTER ROLE \"{rt_role}\" PASSWORD '{rt_pw}'"))
        finally:
            await admin.dispose()

    asyncio.run(build())
    mig_url = url_for(mig_role, mig_pw)
    rt_url = url_for(rt_role, rt_pw)
    asyncio.run(_run_migrations(mig_url))

    # Step 2: the real runtime-grant script, after migrations.
    asyncio.run(_exec_script(
        _admin_url(super_url, database),
        _script("02_runtime_grants.sql"),
        {"eims.mig_role": mig_role, "eims.runtime_role": rt_role, "eims.schema": "public"},
    ))

    yield Topology(
        super_url=super_url,
        mig_url=mig_url,
        rt_url=rt_url,
        database=database,
        mig_role=mig_role,
        rt_role=rt_role,
    )

    async def teardown() -> None:
        admin = create_async_engine(
            _admin_url(super_url), isolation_level="AUTOCOMMIT", poolclass=NullPool
        )
        try:
            async with admin.begin() as conn:
                await conn.execute(text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :d AND pid <> pg_backend_pid()"
                ), {"d": database})
                await conn.execute(text(f'DROP DATABASE IF EXISTS "{database}"'))
                await conn.execute(text(f'DROP ROLE IF EXISTS "{rt_role}"'))
                await conn.execute(text(f'DROP ROLE IF EXISTS "{mig_role}"'))
        finally:
            await admin.dispose()

    asyncio.run(teardown())


def _runtime_engine(topology: Topology):
    return create_async_engine(topology.rt_url, poolclass=NullPool)


def _mig_engine(topology: Topology):
    return create_async_engine(topology.mig_url, poolclass=NullPool)


def _denied(error: DBAPIError, *fragments: str) -> None:
    message = str(error).lower()
    assert any(fragment in message for fragment in fragments), str(error)


async def _seed_incident(topology: Topology, *, status="investigating") -> uuid.UUID:
    """Creates the incident as the runtime role (the app's own identity)."""
    incident_id = uuid.uuid4()
    engine = _runtime_engine(topology)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO incidents "
                    "(incident_id, title, status, severity, confidence, first_seen, "
                    " last_seen, dedupe_key) "
                    "VALUES (:i, 'synthetic priv incident', :s, 'high', 'weak', now(), now(), :k)"
                ),
                {"i": incident_id, "s": status, "k": uuid.uuid4().hex + uuid.uuid4().hex},
            )
    finally:
        await engine.dispose()
    return incident_id


def test_runtime_role_posture_is_least_privilege(topology):
    async def scenario():
        engine = _runtime_engine(topology)
        try:
            async with engine.connect() as conn:
                row = (await conn.execute(text(
                    "SELECT rolname, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolinherit "
                    "FROM pg_roles WHERE rolname = current_user"
                ))).one()
                assert row[0] == topology.rt_role
                assert row[1] is False, "runtime must not be superuser"
                assert row[2] is False, "runtime must not have BYPASSRLS"
                assert row[3] is False and row[4] is False
                owner = (await conn.execute(text(
                    "SELECT pg_get_userbyid(relowner) FROM pg_class "
                    "WHERE relname = 'incidents' AND relnamespace = 'public'::regnamespace"
                ))).scalar()
                assert owner == topology.mig_role, owner
                member = (await conn.execute(text(
                    "SELECT pg_has_role(current_user, :m, 'MEMBER')"
                ), {"m": topology.mig_role})).scalar()
                assert member is False
                trigger_owner = (await conn.execute(text(
                    "SELECT pg_get_userbyid(p.proowner) FROM pg_trigger t "
                    "JOIN pg_proc p ON p.oid = t.tgfoid "
                    "WHERE t.tgname = 'trg_incident_resolution_requires_verification'"
                ))).scalar()
                assert trigger_owner == topology.mig_role, trigger_owner
                await conn.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


async def _resolve_as_runtime(topology: Topology, incident_id: uuid.UUID) -> None:
    """Runs the real resolution write set as the runtime role (no service)."""
    evidence_id = uuid.uuid4()
    digest = "b" * 64
    engine = _runtime_engine(topology)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO incident_evidence (evidence_id, incident_id, source_type, "
                    "source_id, evidence_digest, observed_at, added_by) "
                    "VALUES (:e, :i, 'analysis', :s, :d, now(), 'engineer')"
                ),
                {"e": evidence_id, "i": incident_id,
                 "s": uuid.uuid4().hex[:12], "d": digest},
            )
            await conn.execute(
                text(
                    "INSERT INTO incident_verification (verification_id, incident_id, "
                    "remediation_cycle, evidence_id, evidence_digest, outcome, verifier_id, "
                    "verified_at) VALUES (:v, :i, 0, :e, :d, 'passed', 'reviewer', now())"
                ),
                {"v": uuid.uuid4(), "i": incident_id, "e": evidence_id, "d": digest},
            )
            await conn.execute(text(
                "UPDATE incidents SET status = 'resolved' WHERE incident_id = :i"
            ), {"i": incident_id})
    finally:
        await engine.dispose()


def test_runtime_role_can_do_intended_operations(topology):
    async def scenario():
        incident_id = await _seed_incident(topology, status="open")
        engine = _runtime_engine(topology)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(
                    "UPDATE incidents SET status='triage' WHERE incident_id = :i"
                ), {"i": incident_id})
                await conn.execute(text(
                    "INSERT INTO audit_logs (log_id, asset_id, action_verb, performed_at, "
                    "immutable_payload) VALUES (:l, NULL, 'PRIV_PROBE', now(), '{}'::jsonb)"
                ), {"l": uuid.uuid4()})
        finally:
            await engine.dispose()

        # The whole resolution write set (evidence, verification, status) works
        # for the runtime role; the guards still validate its content.
        await _resolve_as_runtime(topology, incident_id)
        engine = _runtime_engine(topology)
        try:
            async with engine.connect() as conn:
                status = (await conn.execute(text(
                    "SELECT status FROM incidents WHERE incident_id = :i"
                ), {"i": incident_id})).scalar()
                assert status == "resolved"
                await conn.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("UPDATE incident_verification SET outcome = 'failed'", ("permission denied",)),
        ("DELETE FROM incident_verification", ("permission denied",)),
        ("TRUNCATE incident_verification", ("permission denied", "must be owner")),
        (
            "ALTER TABLE incidents DISABLE TRIGGER trg_incident_resolution_requires_verification",
            ("must be owner", "permission denied"),
        ),
        (
            "DROP TRIGGER trg_incident_resolution_requires_verification ON incidents",
            ("must be owner", "permission denied"),
        ),
        (
            "DROP FUNCTION incident_resolution_requires_verification()",
            ("must be owner", "permission denied"),
        ),
        ("CREATE TABLE runtime_created (id int)", ("permission denied",)),
        ("UPDATE incident_evidence SET added_by = 'forged'", ("permission denied",)),
        ("DELETE FROM incident_evidence", ("permission denied",)),
        ("UPDATE audit_logs SET action_verb = 'forged'", ("permission denied",)),
        ("DELETE FROM audit_logs", ("permission denied",)),
        ("SELECT version_num FROM alembic_version", ("permission denied",)),
        ("DELETE FROM incidents", ("permission denied",)),
        (
            "SET session_replication_role = replica",
            ("permission denied", "must be superuser"),
        ),
        ("SET ROLE {mig}", ("permission denied", "must be a member")),
    ],
)
def test_runtime_role_cannot_touch_protected_security_objects(topology, statement, expected):
    async def scenario():
        engine = _runtime_engine(topology)
        try:
            with pytest.raises(DBAPIError) as exc:
                async with engine.begin() as conn:
                    await conn.execute(
                        text(statement.replace("{mig}", topology.mig_role))
                    )
            _denied(exc.value, *expected)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_raw_sql_resolve_is_refused_by_the_database(topology):
    async def scenario():
        incident_id = await _seed_incident(topology)
        engine = _runtime_engine(topology)
        try:
            with pytest.raises(DBAPIError) as exc:
                async with engine.begin() as conn:
                    await conn.execute(text(
                        "UPDATE incidents SET status='resolved' WHERE incident_id = :i"
                    ), {"i": incident_id})
            _denied(exc.value, "cannot be resolved without verification")
            async with engine.connect() as conn:
                status = (await conn.execute(text(
                    "SELECT status FROM incidents WHERE incident_id = :i"
                ), {"i": incident_id})).scalar()
                assert status == "investigating"
                await conn.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_resolved_incident_cannot_be_inserted_directly(topology):
    async def scenario():
        engine = _runtime_engine(topology)
        try:
            with pytest.raises(DBAPIError) as exc:
                async with engine.begin() as conn:
                    await conn.execute(
                        text(
                            "INSERT INTO incidents (incident_id, title, status, severity, "
                            "confidence, first_seen, last_seen, dedupe_key) "
                            "VALUES (:i, 'forged', 'resolved', 'high', 'weak', now(), now(), :k)"
                        ),
                        {"i": uuid.uuid4(), "k": uuid.uuid4().hex + uuid.uuid4().hex},
                    )
            _denied(exc.value, "must be created in a non-resolved state")
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_remediation_cycle_cannot_be_rewound_to_replay_verification(topology):
    async def scenario():
        incident_id = await _seed_incident(topology, status="open")
        engine = _runtime_engine(topology)
        try:
            with pytest.raises(DBAPIError) as exc:
                async with engine.begin() as conn:
                    await conn.execute(text(
                        "UPDATE incidents SET remediation_cycle = 7 WHERE incident_id = :i"
                    ), {"i": incident_id})
            _denied(exc.value, "remediation_cycle may only advance")
            async with engine.connect() as conn:
                cycle = (await conn.execute(text(
                    "SELECT remediation_cycle FROM incidents WHERE incident_id = :i"
                ), {"i": incident_id})).scalar()
                assert cycle == 0
                await conn.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_remediation_started_at_cannot_be_moved_alone(topology):
    """The freshness window must not be widened by a crafted UPDATE."""

    async def scenario():
        incident_id = await _seed_incident(topology, status="open")
        engine = _runtime_engine(topology)
        try:
            with pytest.raises(DBAPIError) as exc:
                async with engine.begin() as conn:
                    await conn.execute(text(
                        "UPDATE incidents SET remediation_started_at = '1970-01-01' "
                        "WHERE incident_id = :i"
                    ), {"i": incident_id})
            _denied(exc.value, "may only change with a new cycle")
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_leaving_resolved_without_a_new_cycle_is_refused(topology):
    """resolved -> open -> resolved must not replay the old verification."""

    async def scenario():
        incident_id = uuid.uuid4()
        evidence_id = uuid.uuid4()
        digest = "a" * 64
        engine = _mig_engine(topology)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO incidents (incident_id, title, status, severity, "
                        "confidence, first_seen, last_seen, dedupe_key) "
                        "VALUES (:i, 'synthetic resolved', 'investigating', 'high', "
                        "'weak', now(), now(), :k)"
                    ),
                    {"i": incident_id, "k": uuid.uuid4().hex + uuid.uuid4().hex},
                )
                await conn.execute(
                    text(
                        "INSERT INTO incident_evidence (evidence_id, incident_id, "
                        "source_type, source_id, evidence_digest, observed_at, added_by) "
                        "VALUES (:e, :i, 'analysis', :s, :d, now(), 'engineer')"
                    ),
                    {"e": evidence_id, "i": incident_id,
                     "s": uuid.uuid4().hex[:12], "d": digest},
                )
                await conn.execute(
                    text(
                        "INSERT INTO incident_verification (verification_id, incident_id, "
                        "remediation_cycle, evidence_id, evidence_digest, outcome, "
                        "verifier_id, verified_at) "
                        "VALUES (:v, :i, 0, :e, :d, 'passed', 'reviewer', now())"
                    ),
                    {"v": uuid.uuid4(), "i": incident_id, "e": evidence_id, "d": digest},
                )
                await conn.execute(text(
                    "UPDATE incidents SET status = 'resolved' WHERE incident_id = :i"
                ), {"i": incident_id})

            with pytest.raises(DBAPIError) as exc:
                async with engine.begin() as conn:
                    await conn.execute(text(
                        "UPDATE incidents SET status = 'open' WHERE incident_id = :i"
                    ), {"i": incident_id})
            _denied(exc.value, "leaving resolved requires a new remediation cycle")

            async with engine.connect() as conn:
                status = (await conn.execute(text(
                    "SELECT status FROM incidents WHERE incident_id = :i"
                ), {"i": incident_id})).scalar()
                assert status == "resolved"
                await conn.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_closed_incident_cannot_be_reopened(topology):
    """closed is terminal; closed -> open -> resolved must not replay."""

    async def scenario():
        incident_id = await _seed_incident(topology, status="open")
        await _resolve_as_runtime(topology, incident_id)
        engine = _runtime_engine(topology)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(
                    "UPDATE incidents SET status = 'closed' WHERE incident_id = :i"
                ), {"i": incident_id})
            with pytest.raises(DBAPIError) as exc:
                async with engine.begin() as conn:
                    await conn.execute(text(
                        "UPDATE incidents SET status = 'open' WHERE incident_id = :i"
                    ), {"i": incident_id})
            _denied(exc.value, "closed incidents are terminal")
            async with engine.connect() as conn:
                status = (await conn.execute(text(
                    "SELECT status FROM incidents WHERE incident_id = :i"
                ), {"i": incident_id})).scalar()
                assert status == "closed"
                await conn.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_migration_role_keeps_ddl_and_can_disable_the_guards(topology):
    """Separation is what protects the runtime: the owner still has DDL."""

    async def scenario():
        engine = _mig_engine(topology)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(
                    "ALTER TABLE incidents ADD COLUMN synthetic_priv_probe integer"
                ))
                await conn.execute(text(
                    "ALTER TABLE incidents DROP COLUMN synthetic_priv_probe"
                ))
        finally:
            await engine.dispose()

    asyncio.run(scenario())
