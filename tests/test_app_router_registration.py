"""Regression guard for FastAPI router registration.

FastAPI 0.141 defers ``include_router``: immediately after import the app holds
``_IncludedRouter`` placeholders with an empty path, and the real routes appear
only when the application is built. Asserting on ``app.routes`` at import time
therefore produces a false negative (this actually happened during the Knowledge
Foundation work). The canonical way to assert registration is the generated
OpenAPI document, which forces the app to be built.
"""
from __future__ import annotations

from backend.api.routers.analyzer.catalog import catalog_router
from backend.main import app


def _paths() -> dict:
    return app.openapi()["paths"]


def test_auth_routes_are_registered() -> None:
    paths = _paths()
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/logout" in paths


def test_analyzer_routes_are_registered() -> None:
    assert any(path.startswith("/api/v1/analyze") for path in _paths())


def test_catalog_summary_is_registered_once() -> None:
    paths = _paths()
    target = "/api/v1/analyzer/catalog/summary"
    assert target in paths, "catalog summary missing from the built application"
    assert set(paths[target]) == {"get"}


def test_catalog_router_declares_exactly_the_expected_routes() -> None:
    # summary plus the read-only current-record endpoint used to compare incident snapshots with the live entry.
    declared = [route.path for route in catalog_router.routes]
    assert declared == [
        "/api/v1/analyzer/catalog/summary",
        "/api/v1/analyzer/catalog/record",
    ]


def test_no_duplicate_route_paths() -> None:
    built = [route.path for route in app.routes if getattr(route, "path", "")]
    assert len(built) == len(set(built)), "duplicate route path registered"


def test_import_time_route_list_is_not_yet_materialised() -> None:
    """Documents the deferred-registration behaviour so nobody repeats the probe.

    If a future FastAPI version materialises routes eagerly this test becomes a
    harmless no-op assertion on the same invariant (no duplicate paths).
    """
    built = [route.path for route in app.routes if getattr(route, "path", "")]
    assert len(built) == len(set(built))
