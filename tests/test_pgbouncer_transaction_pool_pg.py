"""PgBouncer transaction-pooling harness (NOT yet proven; skipped by default).

Status: **never executed successfully.** A local attempt against a throw-away
`edoburu/pgbouncer` container accepted TCP and then timed out during
authentication, so this file must not be cited as pooler evidence. It is kept as
a harness for whoever owns the pooler acceptance, with the checks that actually
matter:

  * the identity guard reads the *server-side* identity through the pooler;
  * a wrong identity is denied and cannot mutate.

It deliberately does **not** assert that `pg_backend_pid()` repeats: transaction
pooling may or may not hand the same backend to two client transactions, and a
pass/fail on that would be a flaky claim. What must be proved by a real pooler
test is that the guard re-checks the identity of whatever backend is used, which
the second test does.

Enable with ``EIMS_PGBOUNCER_TEST_URL`` pointing at a disposable pooler.
"""
from __future__ import annotations

import asyncio
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.infrastructure import db_identity

URL_ENV = "EIMS_PGBOUNCER_TEST_URL"


@pytest.fixture()
def pooler_url() -> str:
    value = os.environ.get(URL_ENV, "").strip()
    if not value:
        pytest.skip(f"{URL_ENV} not configured; disposable PgBouncer required")
    return value


def _engine(url: str):
    # prepared_statement_cache_size=0 matches the application's PgBouncer config.
    return create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={"prepared_statement_cache_size": 0},
    )


async def _identity(engine) -> tuple[int, str, str, str]:
    async with engine.connect() as conn:
        row = (await conn.execute(text(
            "SELECT pg_backend_pid(), current_database(), current_user, session_user"
        ))).one()
        await conn.rollback()
        return row


def test_server_identity_is_stable_across_pooled_transactions(pooler_url):
    """Identity must be the same regardless of which backend serves the client."""

    async def scenario():
        engine = _engine(pooler_url)
        try:
            rows = [await _identity(engine) for _ in range(5)]
        finally:
            await engine.dispose()
        return rows

    rows = asyncio.run(scenario())
    identities = {(row[1], row[2], row[3]) for row in rows}
    assert len(identities) == 1, identities
    assert all(isinstance(row[0], int) for row in rows)


def test_identity_guard_runs_through_the_pooler(pooler_url, monkeypatch):
    """The guard reads the live server identity, not the client's belief."""

    async def scenario():
        engine = _engine(pooler_url)
        try:
            row = await _identity(engine)
            database, user = row[1], row[2]

            monkeypatch.delenv(db_identity.IDENTITY_ENV, raising=False)
            monkeypatch.delenv(db_identity.REQUIRED_ENV, raising=False)
            monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{database}|{user}")
            monkeypatch.setenv(db_identity.REQUIRED_ENV, "1")
            async with engine.connect() as conn:
                identity = await db_identity.require_runtime_identity(conn)
                assert identity.database == database
                assert identity.user == user
                await conn.rollback()

            monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{database}|not_the_role")
            with pytest.raises(db_identity.MutationTargetError):
                async with engine.connect() as conn:
                    await db_identity.require_runtime_identity(conn)
                    await conn.execute(text(
                        "INSERT INTO analysis_history (event_id, provider, username, "
                        "description) VALUES ('4625','pooler','pooler','SHOULD NOT PERSIST')"
                    ))
                    await conn.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_denied_pooler_session_persisted_nothing(pooler_url):
    async def scenario():
        engine = _engine(pooler_url)
        try:
            async with engine.connect() as conn:
                exists = (await conn.execute(text(
                    "SELECT to_regclass('analysis_history')"
                ))).scalar()
                assert exists is not None, "harness requires the incident schema"
                count = (await conn.execute(text(
                    "SELECT count(*) FROM analysis_history "
                    "WHERE description = 'SHOULD NOT PERSIST'"
                ))).scalar()
                assert count == 0
                await conn.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())
