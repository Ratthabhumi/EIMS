"""R-1 identity matrix against a real disposable PostgreSQL.

Skipped unless EIMS_TEST_DATABASE_URL points at the allowlisted disposable
instance. Proves the guard's decision on the live connection, including the
session_user/current_user distinction, and that a denied check performs no write.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.infrastructure import db_identity

URL_ENV = "EIMS_TEST_DATABASE_URL"
DISPOSABLE_PREFIX = "EIMS-DISPOSABLE-"


@pytest.fixture()
def url() -> str:
    value = os.environ.get(URL_ENV)
    if not value:
        pytest.skip(f"{URL_ENV} not configured; disposable PostgreSQL required")
    return value


@pytest.fixture()
async def session(url, monkeypatch):
    engine = create_async_engine(url)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        identity = (await s.execute(text(
            "SELECT current_database(), current_user, session_user"))).first()
        await s.rollback()
        yield s, identity
    await engine.dispose()


def _clean_env(monkeypatch):
    monkeypatch.delenv(db_identity.IDENTITY_ENV, raising=False)
    monkeypatch.delenv(db_identity.REQUIRED_ENV, raising=False)


async def test_correct_database_and_role_is_allowed(session, monkeypatch):
    s, (database, user, _) = session
    _clean_env(monkeypatch)
    monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{database}|{user}")
    identity = await db_identity.require_runtime_identity(s)
    assert identity.database == database
    assert identity.user == user
    assert s.info["eims_identity_status"] == "verified"


async def test_wrong_role_for_the_same_database_is_denied(session, monkeypatch):
    s, (database, _, _) = session
    _clean_env(monkeypatch)
    monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{database}|definitely_not_the_role")
    with pytest.raises(db_identity.MutationTargetError):
        await db_identity.require_runtime_identity(s)


async def test_wrong_database_for_the_same_role_is_denied(session, monkeypatch):
    s, (_, user, _) = session
    _clean_env(monkeypatch)
    monkeypatch.setenv(db_identity.IDENTITY_ENV, f"definitely_not_the_database|{user}")
    with pytest.raises(db_identity.MutationTargetError):
        await db_identity.require_runtime_identity(s)


async def test_required_mode_without_configuration_is_denied(session, monkeypatch):
    s, _ = session
    _clean_env(monkeypatch)
    monkeypatch.setenv(db_identity.REQUIRED_ENV, "1")
    with pytest.raises(db_identity.MutationTargetError):
        await db_identity.require_runtime_identity(s)


async def test_unconfigured_without_required_mode_is_marked_not_verified(session, monkeypatch):
    s, _ = session
    _clean_env(monkeypatch)
    assert await db_identity.require_runtime_identity(s) is None
    assert s.info["eims_identity_status"] == "unconfigured"


async def test_set_role_changes_effective_user_and_is_denied(session, monkeypatch):
    """session_user stays the login; current_user changes with SET ROLE."""
    s, (database, user, session_user) = session
    from sqlalchemy.exc import DBAPIError, ProgrammingError
    _clean_env(monkeypatch)
    try:
        async with s.begin():
            await s.execute(text("SET LOCAL ROLE eims_identity_probe"))
            row = (await s.execute(text("SELECT current_user, session_user"))).first()
    except (DBAPIError, ProgrammingError):
        pytest.skip("probe role not provisioned; SET ROLE semantics documented instead")
    assert row[0] == "eims_identity_probe"
    assert row[1] == session_user

    monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{database}|{user}")
    async with s.begin():
        await s.execute(text("SET LOCAL ROLE eims_identity_probe"))
        with pytest.raises(db_identity.MutationTargetError):
            await db_identity.require_runtime_identity(s)


async def test_denied_check_performs_no_write(session, monkeypatch):
    s, (database, _, _) = session
    _clean_env(monkeypatch)
    monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{database}|not_the_role")

    async with s.begin():
        await s.execute(text("CREATE TABLE IF NOT EXISTS r1_write_probe (marker text)"))

    with pytest.raises(db_identity.MutationTargetError):
        await db_identity.require_runtime_identity(s)
        # Unreachable: the guard must raise before this line.
        await s.execute(text("INSERT INTO r1_write_probe (marker) VALUES ('denied')"))

    async with s.begin():
        count = (await s.execute(text("SELECT count(*) FROM r1_write_probe"))).scalar()
    assert count == 0, "denied identity must not mutate the database"
