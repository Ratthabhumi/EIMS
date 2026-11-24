"""R-1 active-connection invalidation (not close/reinitialize).

Invalidates a checked-out connection on the application's own engine, then proves
a fresh DBAPI connection is established and the identity guard runs again on it.
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
def app_engine(url, monkeypatch):
    point_settings_at(monkeypatch, url)
    from backend.core.config import settings
    assert settings.DB_NAME == "eims_incident_test", settings.DB_NAME
    engine = AsynchronousDatabaseEngine()
    yield engine


@pytest.fixture()
def url() -> str:
    value = os.environ.get(URL_ENV)
    if not value:
        pytest.skip(f"{URL_ENV} not configured; disposable PostgreSQL required")
    return value


def _clean(monkeypatch):
    monkeypatch.delenv(db_identity.IDENTITY_ENV, raising=False)
    monkeypatch.delenv(db_identity.REQUIRED_ENV, raising=False)


async def test_invalidation_forces_a_new_connection_and_rechecks_identity(
        app_engine, monkeypatch):
    await app_engine.initialize()
    try:
        # 1. a real checked-out connection, correctly identified
        async with app_engine._engine.connect() as conn:
            row = (await conn.execute(text(
                "SELECT current_database(), current_user"))).first()
            assert row[0] == "eims_incident_test", row
            pg_backend_pid_before = (await conn.execute(text(
                "SELECT pg_backend_pid()"))).scalar()
            _clean(monkeypatch)
            monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{row[0]}|{row[1]}")

            # 2. invalidate the active connection (SQLAlchemy-supported API)
            await conn.invalidate()

        # 3. a fresh connection is a different backend, and the guard runs again
        async with app_engine._engine.connect() as conn:
            pg_backend_pid_after = (await conn.execute(text(
                "SELECT pg_backend_pid()"))).scalar()
        assert pg_backend_pid_after != pg_backend_pid_before, \
            "invalidation must produce a replacement DBAPI connection"

        maker = app_engine.get_session_maker()
        async with maker() as s:
            assert s.info["eims_identity_status"] == "verified"
            assert (await s.execute(text("SELECT 1"))).scalar() == 1
            await s.rollback()

        # 4. the replacement connection must reject a wrong identity
        monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{row[0]}|not_the_role")
        with pytest.raises(db_identity.MutationTargetError):
            async with maker() as s:
                await s.execute(text("SELECT 1"))

        # 5. and must not let a wrong identity mutate anything
        monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{row[0]}|{row[1]}")
        async with maker() as s:
            await s.execute(text("CREATE TABLE IF NOT EXISTS r1_invalidate_probe (m text)"))
            await s.commit()
        monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{row[0]}|not_the_role")
        with pytest.raises(db_identity.MutationTargetError):
            async with maker() as s:
                await s.execute(text("INSERT INTO r1_invalidate_probe VALUES ('denied')"))
                await s.commit()

        monkeypatch.setenv(db_identity.IDENTITY_ENV, f"{row[0]}|{row[1]}")
        async with maker() as s:
            count = (await s.execute(text(
                "SELECT count(*) FROM r1_invalidate_probe"))).scalar()
            await s.rollback()
        assert count == 0, "a wrong identity after reconnect must not persist a row"
    finally:
        await app_engine.close()
