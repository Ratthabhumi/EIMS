"""R-1 worker/pool integration against disposable PostgreSQL.

Uses the application's own AsynchronousDatabaseEngine (not a hand-built session),
pointed at the disposable test database, to prove:
  * the worker session factory enforces identity,
  * enforcement survives engine.dispose() and re-initialisation (replacement pool),
  * a denied worker session cannot mutate the database.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from backend.infrastructure import db_identity
from backend.infrastructure.database import AsynchronousDatabaseEngine
from tests.incident_db_support import point_settings_at

URL_ENV = "EIMS_TEST_DATABASE_URL"


@pytest.fixture()
def url() -> str:
    value = os.environ.get(URL_ENV)
    if not value:
        pytest.skip(f"{URL_ENV} not configured; disposable PostgreSQL required")
    return value


@pytest.fixture()
def engine(url, monkeypatch):
    # Patch the fields the database_url property reads, then verify the target.
    point_settings_at(monkeypatch, url)
    from backend.core.config import settings
    assert settings.DB_NAME == "eims_incident_test", settings.DB_NAME
    eng = AsynchronousDatabaseEngine()
    yield eng


def _clean(monkeypatch):
    monkeypatch.delenv(db_identity.IDENTITY_ENV, raising=False)
    monkeypatch.delenv(db_identity.REQUIRED_ENV, raising=False)


async def _identity(maker):
    async with maker() as s:
        row = (await s.execute(text(
            "SELECT current_database(), current_user"))).first()
        await s.rollback()
        return row


async def test_worker_factory_allows_correct_identity(engine, monkeypatch):
    await engine.initialize()
    try:
        maker = engine.get_session_maker()
        row = await _identity(maker)
        assert row[0] == "eims_incident_test", row
        _clean(monkeypatch)
        monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{row[0]}|{row[1]}")
        async with maker() as s:
            assert (await s.execute(text("SELECT 1"))).scalar() == 1
            assert s.info["eims_identity_status"] == "verified"
            await s.rollback()
    finally:
        await engine.close()


async def test_worker_factory_denies_wrong_role(engine, monkeypatch):
    await engine.initialize()
    try:
        maker = engine.get_session_maker()
        row = await _identity(maker)
        _clean(monkeypatch)
        monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{row[0]}|definitely_not_the_role")

        async with maker() as _session:
            # The guard runs before this body executes.
            raise AssertionError("worker session must not be yielded on mismatch")
    except db_identity.MutationTargetError:
        pass
    finally:
        await engine.close()


async def test_denied_worker_session_writes_nothing(engine, monkeypatch):
    await engine.initialize()
    try:
        maker = engine.get_session_maker()
        row = await _identity(maker)
        _clean(monkeypatch)
        monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{row[0]}|not_the_role")

        with pytest.raises(db_identity.MutationTargetError):
            async with maker() as s:
                await s.execute(text("CREATE TABLE IF NOT EXISTS r1_worker_probe (m text)"))
                await s.execute(text("INSERT INTO r1_worker_probe VALUES ('x')"))
                await s.commit()

        # Re-configure the correct identity so the verification query itself passes
        # the guard; only the denied attempt above is under test.
        monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{row[0]}|{row[1]}")
        async with maker() as s:
            exists = (await s.execute(text(
                "SELECT to_regclass('r1_worker_probe')"))).scalar()
            count = 0
            if exists:
                count = (await s.execute(text("SELECT count(*) FROM r1_worker_probe"))).scalar()
            await s.rollback()
        assert count == 0, "a denied worker session must not persist anything"
    finally:
        await engine.close()


async def test_enforcement_survives_engine_dispose_and_reinit(engine, monkeypatch):
    await engine.initialize()
    maker = engine.get_session_maker()
    row = await _identity(maker)
    await engine.close()

    # dispose() then use the same engine instance again: the factory must still guard
    await engine.initialize()
    try:
        _clean(monkeypatch)
        monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{row[0]}|wrong_role_after_dispose")
        with pytest.raises(db_identity.MutationTargetError):
            async with engine.get_session_maker()() as s:
                await s.execute(text("SELECT 1"))

        # and the same factory accepts the correct identity once configured
        monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{row[0]}|{row[1]}")
        async with engine.get_session_maker()() as s:
            assert (await s.execute(text("SELECT 1"))).scalar() == 1
            await s.rollback()
    finally:
        await engine.close()
