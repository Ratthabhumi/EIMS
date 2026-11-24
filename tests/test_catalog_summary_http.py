"""HTTP acceptance for the Catalog summary endpoint (database-backed).

The application is started through TestClient (lifespan executes) against the
disposable PostgreSQL. The Knowledge governance tables are created in the same
database/schema the application session uses, and the append-only trigger is
installed from the real migration module (not re-typed here).

Why the application target is pinned explicitly
-----------------------------------------------
``tests/conftest.py`` imports ``backend.main`` at collection time, so the global
``settings`` object (and therefore ``settings.database_url`` used by the global
``database_engine`` during lifespan) is already built from defaults
(``localhost:5432/eims_registry`` -- the *operational* database) before any test
module can set ``EIMS_DB_*`` environment variables.  Setting the environment
inside the test module is therefore a no-op for the application and the request
silently targets the wrong database.  The ``disposable_app`` fixture pins the
already-instantiated settings object to the disposable database for the duration
of the test, refuses to run if the target still looks operational, and proves the
identity of the connection that actually serves the request.

Note: the *migration chain itself* is proven separately by
``tests/test_knowledge_overlay_pg.py``; this test proves the HTTP layer reads
the overlay.
"""
from __future__ import annotations

from tests import catalog_expectations as X
import asyncio
import importlib.util
import os
import uuid
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.core.config import settings
from backend.domain.knowledge.models import KnowledgeReview, KnowledgeReviewEvent
from backend.domain.knowledge.service import resolve_catalog
from backend.infrastructure.database import Base, get_db_session
from backend.main import app

_TEST_URL = os.environ.get("EIMS_TEST_DATABASE_URL", "").strip()
_OPERATIONAL_DEFAULT = ("localhost", 5432, "eims_registry")

pytestmark = pytest.mark.skipif(not _TEST_URL, reason="disposable PostgreSQL required")


def _migration_module():
    path = (Path(__file__).resolve().parents[1] / "migrations" / "versions"
            / "a1c4e7b9d201_add_knowledge_review.py")
    spec = importlib.util.spec_from_file_location("_knowledge_migration", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _target(url: str) -> dict:
    parts = urlsplit(url)
    return {
        "host": parts.hostname or "127.0.0.1",
        "port": parts.port or 5432,
        "name": (parts.path or "/").lstrip("/"),
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
    }


@pytest.fixture
def disposable_app(monkeypatch):
    """Point the already-initialised application settings at the disposable DB."""
    target = _target(_TEST_URL)
    if (target["host"].lower(), target["port"], target["name"]) == _OPERATIONAL_DEFAULT or \
            target["name"] == "eims_registry":
        pytest.fail("EIMS_TEST_DATABASE_URL resolves to the operational database; refusing to run")

    monkeypatch.setattr(settings, "DB_HOST", target["host"])
    monkeypatch.setattr(settings, "DB_PORT", target["port"])
    monkeypatch.setattr(settings, "DB_NAME", target["name"])
    monkeypatch.setattr(settings, "DB_USER", target["user"])
    monkeypatch.setattr(settings, "DB_PASSWORD", target["password"])
    # Application-side switches are read from os.environ at request/lifespan time.
    monkeypatch.setenv("EIMS_DEMO_SOFT_DEPS", "1")
    monkeypatch.setenv("EIMS_AUTH_MODE", "demo")
    monkeypatch.delenv("EIMS_DB_IDENTITY", raising=False)
    monkeypatch.delenv("EIMS_DB_IDENTITY_REQUIRED", raising=False)

    # The pinned URL must now be what the global engine will use in lifespan.
    assert (settings.DB_HOST, settings.DB_PORT, settings.DB_NAME) == (
        target["host"], target["port"], target["name"])

    async def identity_probe(db: AsyncSession = Depends(get_db_session)) -> dict:
        row = (await db.execute(text(
            "SELECT current_database() AS database_name, "
            "inet_server_port() AS server_port, "
            "current_schema() AS current_schema, "
            "to_regclass('knowledge_review')::text AS knowledge_review, "
            "to_regclass('knowledge_review_event')::text AS knowledge_review_event"
        ))).mappings().one()
        return dict(row)

    app.add_api_route("/__test__/db-identity", identity_probe, methods=["GET"])
    try:
        yield target
    finally:
        app.router.routes[:] = [r for r in app.router.routes
                                if getattr(r, "path", None) != "/__test__/db-identity"]


async def _prepare() -> str:
    engine = create_async_engine(_TEST_URL)
    try:
        async with engine.begin() as conn:
            # Append-only triggers (correctly) reject DELETE/TRUNCATE, so a rerun on
            # the disposable database resets state by dropping the two tables, then
            # recreating them and the real migration triggers from scratch.
            await conn.execute(text(
                "DROP TABLE IF EXISTS knowledge_review_event, knowledge_review CASCADE"))
            await conn.run_sync(lambda c: Base.metadata.create_all(
                c, tables=[KnowledgeReview.__table__, KnowledgeReviewEvent.__table__]
            ))
            mod = _migration_module()
            for ddl in (mod.APPEND_ONLY_FUNCTION_DDL, mod.APPEND_ONLY_TRIGGER_DDL,
                        mod.APPEND_ONLY_TRUNCATE_DDL):
                await conn.execute(text(ddl))
            diag = next(e for e in resolve_catalog()
                        if e["knowledge_class"] == "diagnostic_candidate")
            await conn.execute(
                text(
                    "INSERT INTO knowledge_review (catalog_id, catalog_source, content_hash, "
                    "lifecycle_status, review_required, revision, concurrency_version, created_at, updated_at) "
                    "VALUES (:c, 'diagnostic', :h, 'approved', false, 3, 1, now(), now())"
                ),
                {"c": diag["catalog_id"], "h": diag["content_hash"]},
            )
            await conn.execute(
                text(
                    "INSERT INTO knowledge_review_event (event_id, catalog_id, event_type, "
                    "to_status, actor, rationale, source_hash, revision, created_at) "
                    "VALUES (:e, :c, 'transition', 'approved', 'demo.reviewer', "
                    "        'independent approval', :h, 3, now())"
                ),
                {"e": uuid.uuid4(), "c": diag["catalog_id"], "h": diag["content_hash"]},
            )
            return diag["catalog_id"]
    finally:
        await engine.dispose()


async def _mark_stale(catalog_id: str) -> None:
    engine = create_async_engine(_TEST_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE knowledge_review SET review_required = true WHERE catalog_id = :c"),
                {"c": catalog_id},
            )
    finally:
        await engine.dispose()


def test_catalog_summary_reads_governance_overlay(disposable_app) -> None:
    catalog_id = asyncio.run(_prepare())

    with TestClient(app) as client:
        # The request-serving connection must be the disposable database that
        # holds the tables created above -- not the operational default.
        ident = client.get("/__test__/db-identity")
        assert ident.status_code == 200, ident.text
        ident = ident.json()
        assert ident["database_name"] == disposable_app["name"], ident
        assert ident["server_port"] == 5432  # in-container port; host port differs by mapping
        assert ident["knowledge_review"] == "knowledge_review", ident
        assert ident["knowledge_review_event"] == "knowledge_review_event", ident

        response = client.get("/api/v1/analyzer/catalog/summary")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total_records"] == X.TOTAL
        assert body["counts"]["operational_context"] == 153
        assert body["counts"]["diagnostic_candidates"] == X.VENDOR_COUNT
        assert body["counts"]["approved"] == 1, body["counts"]
        assert body["counts"]["stale_review"] == 0
        assert body["counts"]["overlay_rows"] == 1

        # mark it stale -> the API must stop counting it as trusted
        asyncio.run(_mark_stale(catalog_id))

        again = client.get("/api/v1/analyzer/catalog/summary").json()
        assert again["counts"]["approved"] == 0, again["counts"]
        assert again["counts"]["stale_review"] == 1


def test_application_settings_are_not_operational_when_pinned(disposable_app) -> None:
    """Regression: conftest imports the app first, so env set in a test module is
    ignored. The pinned target must never be the operational default."""
    assert (settings.DB_HOST.lower(), settings.DB_PORT, settings.DB_NAME) != _OPERATIONAL_DEFAULT
    assert settings.DB_NAME != "eims_registry"
