"""R-1 application-level identity: real FastAPI lifespan, real HTTP, real engine.

The application under test is built with the real ``AsynchronousDatabaseEngine``
singleton, the real ``get_db_session`` dependency (no ``dependency_overrides``)
and the real incident router. ``TestClient`` is used as a context manager so the
lifespan startup/shutdown actually runs.

Every denied case asserts persisted state from an independent connection, so a
green result cannot come from a 500 alone.
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.domain.incident.controller import incident_router
from backend.infrastructure import db_identity
from backend.infrastructure.database import Base, database_engine
from tests.incident_db_support import (
    INCIDENT_TABLES,
    install_verification_append_only,
    point_settings_at,
    require_database_url,
)

DISPOSABLE_DB = "eims_incident_test"
DISPOSABLE_ROLE = "eims_incident_test"


@pytest.fixture(scope="module", autouse=True)
def public_schema():
    """Creates the incident surface in the disposable database's public schema."""
    url = require_database_url()

    async def create():
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(
                    lambda c: Base.metadata.create_all(c, tables=list(INCIDENT_TABLES))
                )
        finally:
            await engine.dispose()
        engine = create_async_engine(url)
        try:
            await install_verification_append_only(engine)
        finally:
            await engine.dispose()

    asyncio.run(create())
    return url


def _app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await database_engine.initialize()
        try:
            await database_engine.verify_runtime_identity()
        except Exception:
            await database_engine.close()
            raise
        yield
        await database_engine.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(incident_router)
    return app


def _body(source_id: str | None = None) -> dict:
    return {
        "title": "Synthetic R-1 incident",
        "severity": "high",
        "evidence": [
            {
                "source_type": "winlog",
                "source_id": source_id or f"r1-api-{uuid.uuid4().hex[:10]}",
                "source_event_key": "4625",
                "observed_at": "2026-11-19T09:00:00Z",
            }
        ],
    }


def _count(database_url: str, table: str) -> int:
    async def go():
        engine = create_async_engine(database_url)
        try:
            async with engine.connect() as conn:
                return (await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar()
        finally:
            await engine.dispose()

    return asyncio.run(go())


def _configure(monkeypatch, database_url: str, identity: str | None, required: bool) -> None:
    point_settings_at(monkeypatch, database_url)
    monkeypatch.delenv(db_identity.IDENTITY_ENV, raising=False)
    monkeypatch.delenv(db_identity.REQUIRED_ENV, raising=False)
    if identity is not None:
        monkeypatch.setenv(db_identity.IDENTITY_ENV, identity)
    if required:
        monkeypatch.setenv(db_identity.REQUIRED_ENV, "1")


def _new_asset(database_url: str):
    """A fresh asset makes the created incident uncorrelatable by design."""
    from tests.incident_db_support import create_asset

    async def go():
        engine = create_async_engine(database_url)
        try:
            return await create_asset(engine, hostname="synthetic-r1-api-host")
        finally:
            await engine.dispose()

    return asyncio.run(go())


def test_correct_identity_allows_real_http_read_and_write(public_schema, monkeypatch):
    _configure(
        monkeypatch, public_schema, f"{DISPOSABLE_DB}|{DISPOSABLE_ROLE}", required=True
    )
    before = _count(public_schema, "incidents")
    asset_id = _new_asset(public_schema)
    body = _body()
    body["asset_id"] = str(asset_id)

    with TestClient(_app(), raise_server_exceptions=False) as client:
        listing = client.get("/api/v1/incidents")
        assert listing.status_code == 200, listing.text
        created = client.post("/api/v1/incidents", json=body)
        assert created.status_code == 201, created.text
        incident_id = created.json()["incident_id"]
        assert created.json()["asset_id"] == str(asset_id)
        detail = client.get(f"/api/v1/incidents/{incident_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["status"] == "open"

    assert _count(public_schema, "incidents") == before + 1

    # The lifespan really did use the guarded session path.
    async def status():
        async for session in database_engine.get_session():
            return session.info.get("eims_identity_status")

    assert asyncio.run(status()) == "verified"


def test_wrong_database_is_denied_before_any_mutation(public_schema, monkeypatch):
    _configure(
        monkeypatch, public_schema, f"not_the_database|{DISPOSABLE_ROLE}", required=True
    )
    before = _count(public_schema, "incidents")
    with pytest.raises(db_identity.MutationTargetError), TestClient(
        _app(), raise_server_exceptions=False
    ) as client:
        client.post("/api/v1/incidents", json=_body())
    assert _count(public_schema, "incidents") == before


def test_wrong_role_is_denied_before_any_mutation(public_schema, monkeypatch):
    _configure(
        monkeypatch, public_schema, f"{DISPOSABLE_DB}|not_the_role", required=True
    )
    before = _count(public_schema, "incidents")
    with pytest.raises(db_identity.MutationTargetError), TestClient(
        _app(), raise_server_exceptions=False
    ) as client:
        client.post("/api/v1/incidents", json=_body())
    assert _count(public_schema, "incidents") == before


def test_required_without_configuration_fails_closed(public_schema, monkeypatch):
    _configure(monkeypatch, public_schema, None, required=True)
    before = _count(public_schema, "incidents")
    with pytest.raises(db_identity.MutationTargetError), TestClient(
        _app(), raise_server_exceptions=False
    ):
        pass
    assert _count(public_schema, "incidents") == before


def test_unconfigured_optional_mode_still_serves_but_is_not_verified(
    public_schema, monkeypatch
):
    _configure(monkeypatch, public_schema, None, required=False)
    with TestClient(_app(), raise_server_exceptions=False) as client:
        assert client.get("/api/v1/incidents").status_code == 200

    async def status():
        async for session in database_engine.get_session():
            return session.info.get("eims_identity_status")

    # Not "verified": an unconfigured deployment must never look compliant.
    assert asyncio.run(status()) == "unconfigured"


def test_recovery_after_denied_lifecycle_uses_a_fresh_guarded_engine(
    public_schema, monkeypatch
):
    _configure(monkeypatch, public_schema, f"{DISPOSABLE_DB}|not_the_role", required=True)
    with pytest.raises(db_identity.MutationTargetError), TestClient(
        _app(), raise_server_exceptions=False
    ) as client:
        client.get("/api/v1/incidents")

    _configure(
        monkeypatch, public_schema, f"{DISPOSABLE_DB}|{DISPOSABLE_ROLE}", required=True
    )
    with TestClient(_app(), raise_server_exceptions=False) as client:
        assert client.get("/api/v1/incidents").status_code == 200


# ---------------------------------------------------------------------------
# Core / textual SQL at the engine boundary
# ---------------------------------------------------------------------------
def test_core_and_text_paths_allow_correct_identity(public_schema, monkeypatch):
    _configure(
        monkeypatch, public_schema, f"{DISPOSABLE_DB}|{DISPOSABLE_ROLE}", required=True
    )

    async def scenario():
        await database_engine.initialize()
        try:
            async with database_engine.connect() as conn:
                assert (await conn.execute(text("SELECT 1"))).scalar() == 1
                assert (await conn.execute(
                    text("SELECT current_database()"))).scalar() == DISPOSABLE_DB
                await conn.rollback()
        finally:
            await database_engine.close()

    asyncio.run(scenario())


def test_core_and_text_paths_deny_wrong_identity_without_mutation(
    public_schema, monkeypatch
):
    _configure(
        monkeypatch, public_schema, f"{DISPOSABLE_DB}|not_the_role", required=True
    )
    before = _count(public_schema, "incidents")

    async def scenario():
        await database_engine.initialize()
        try:
            with pytest.raises(db_identity.MutationTargetError):
                async with database_engine.connect() as conn:
                    await conn.execute(
                        text(
                            "INSERT INTO analysis_history "
                            "(event_id, provider, username, description) "
                            "VALUES ('4625','r1','r1','SHOULD NOT PERSIST')"
                        )
                    )
                    await conn.commit()
        finally:
            await database_engine.close()

    asyncio.run(scenario())
    assert _count(public_schema, "incidents") == before

    async def leaked():
        engine = create_async_engine(public_schema)
        try:
            async with engine.connect() as conn:
                return (await conn.execute(text(
                    "SELECT count(*) FROM analysis_history "
                    "WHERE description = 'SHOULD NOT PERSIST'"
                ))).scalar()
        finally:
            await engine.dispose()

    assert asyncio.run(leaked()) == 0


def test_no_production_module_reaches_past_the_guarded_boundary():
    """A raw engine handle would bypass every guard; prove none is used."""
    offenders = []
    for path in Path("backend").rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        if "database_engine._engine" in content or ".sync_engine" in content:
            offenders.append(str(path))
    assert offenders == [], offenders
