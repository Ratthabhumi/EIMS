"""
==============================================================================
EIMS Automated Test Suite — Sprint 10 Schema Migration & Route Registration
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 4 Compliance
==============================================================================
"""

from pathlib import Path

from backend.main import app

SPRINT10_REVISION = "d6a97e3f2b15"
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "versions"
SPRINT10_MIGRATION_FILE = MIGRATIONS_DIR / f"{SPRINT10_REVISION}_add_sprint10_search_indexes.py"


def test_sprint10_migration_revision_chain():
    import importlib.util

    spec = importlib.util.spec_from_file_location("sprint10_migration", SPRINT10_MIGRATION_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == SPRINT10_REVISION
    assert module.down_revision == "5811549d7120"


def test_sprint10_migration_is_chain_head():
    """No other migration may declare the Sprint 10 revision as its predecessor."""
    offenders = []
    for path in MIGRATIONS_DIR.glob("*.py"):
        if path.name == SPRINT10_MIGRATION_FILE.name or path.name == "__init__.py":
            continue
        content = path.read_text(encoding="utf-8")
        if f"down_revision: Union[str, None] = '{SPRINT10_REVISION}'" in content:
            offenders.append(path.name)
    assert offenders == []


def test_sprint10_migration_contains_expected_ddl():
    content = SPRINT10_MIGRATION_FILE.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm;" in content
    assert "idx_assets_hostname_trgm" in content
    assert "idx_assets_canonical_ip_trgm" in content
    assert "idx_audit_logs_action_trgm" in content
    assert "search_vector" in content
    assert "idx_analysis_history_search_vector" in content


def _routes_map():
    """Recursively flattens app routes (FastAPI nests included routers in _IncludedRouter)."""
    from fastapi.routing import APIRoute

    mapping: dict[str, set] = {}

    def walk(routes):
        for route in routes:
            if isinstance(route, APIRoute):
                mapping[route.path] = set(route.methods)
                continue
            nested = getattr(route, "original_router", None)
            if nested is not None:
                walk(nested.routes)
            elif hasattr(route, "routes"):
                walk(route.routes)

    walk(app.routes)
    return mapping


def test_sprint10_query_routes_registered():
    paths = set(_routes_map())
    assert "/api/v1/search" in paths
    assert "/api/v1/timeline" in paths
    assert "/api/v1/audit-logs" in paths
    assert "/api/v1/telemetry/metrics" in paths
    assert "/api/v1/telemetry/winlogs" in paths


def test_telemetry_search_endpoint_uses_only_get_method():
    """Sprint 10 query endpoints must be strictly read-only."""
    routes = _routes_map()
    for path in ("/api/v1/search", "/api/v1/timeline", "/api/v1/audit-logs"):
        assert "GET" in routes[path]
        assert not (routes[path] & {"POST", "PUT", "PATCH", "DELETE"})