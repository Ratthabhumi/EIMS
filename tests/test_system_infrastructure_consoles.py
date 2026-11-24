"""System & Infrastructure destinations, structure, and secret-leak guards."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDEBAR = ROOT / "clients" / "dashboard" / "src" / "components" / "SidebarNav.tsx"
HOME = ROOT / "clients" / "dashboard" / "src" / "app" / "page.tsx"
INFRA = ROOT / "clients" / "dashboard" / "src" / "lib" / "infra-consoles.ts"
STATUS_ROUTE = ROOT / "clients" / "dashboard" / "src" / "app" / "api" / "infra-status" / "route.ts"
LAYOUT = ROOT / "clients" / "dashboard" / "src" / "app" / "layout.tsx"

MENU_LABELS = (
    "Grafana Metrics",
    "MinIO Console",
    "Prometheus DB",
    "Core API Docs",
    "Settings",
)

FORBIDDEN_CLIENT = (
    "ADMIN_TOKEN",
    "EIMS_ADMIN_TOKEN",
    "EIMS-ADMIN-TOKEN",
    "MINIO_ROOT_PASSWORD",
    "EIMS_MINIO_SECRET_KEY",
    "eims_minio_secret",
    "EIMS_DB_PASSWORD",
    "eims_secret_password",
    "JWT_SECRET",
    "EIMS_JWT_SECRET_KEY",
    "GF_SECURITY_ADMIN_PASSWORD",
    "eims_admin",
)


def test_infra_menu_labels_preserved_in_sidebar_and_home():
    sidebar = SIDEBAR.read_text(encoding="utf-8")
    home = HOME.read_text(encoding="utf-8")
    assert "System & Infra" in sidebar
    assert "System & Infrastructure" in home
    for label in MENU_LABELS:
        assert label in sidebar, f"Sidebar missing {label}"
        assert label in home, f"Home missing {label}"


def test_infra_destinations_use_config_helper_not_broken_bff_docs():
    sidebar = SIDEBAR.read_text(encoding="utf-8")
    home = HOME.read_text(encoding="utf-8")
    infra = INFRA.read_text(encoding="utf-8")
    assert "infraConsoleUrls" in sidebar and "infraConsoleUrls" in home
    assert 'apiUrl("/api/docs")' not in sidebar
    assert 'apiUrl("/api/docs")' not in home
    assert "http://localhost:3000" in infra
    assert "http://localhost:9001" in infra
    assert "http://localhost:9090" in infra
    assert "/api/docs" in infra
    # Console port must stay distinct from S3 API :9000 default in helper docs/comments
    assert "9001" in infra


def test_infra_helper_and_status_route_forbid_embedding_secrets():
    for path in (INFRA, STATUS_ROUTE, SIDEBAR, HOME):
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN_CLIENT:
            assert needle not in text, f"{path.name} must not contain {needle}"


def test_theme_fouc_script_present_to_reduce_flicker():
    layout = LAYOUT.read_text(encoding="utf-8")
    assert "eims-theme" in layout
    assert "prefers-color-scheme" in layout


def test_infra_status_route_is_read_only_get_and_independent():
    text = STATUS_ROUTE.read_text(encoding="utf-8")
    assert "export async function GET" in text
    assert "Promise.all" in text
    assert "MINIO_ROOT" not in text
    assert "ADMIN_TOKEN" not in text
    assert "EIMS_MINIO_SECRET_KEY" not in text
    assert "password" not in text.lower()


def test_infra_status_supports_not_enabled_for_optional_services():
    text = STATUS_ROUTE.read_text(encoding="utf-8")
    assert "NOT_ENABLED" in text
    assert "notEnabledWhenUnreachable" in text
    assert "readProfileExpect" in text
    sidebar = (ROOT / "clients" / "dashboard" / "src" / "components" / "SidebarNav.tsx").read_text(encoding="utf-8")
    # Nav entries stay clickable links (no OFF/NOT_ENABLED presentation in sidebar)
    assert "Grafana Metrics" in sidebar
    assert "NOT_ENABLED" not in sidebar
    assert 'href="/incidents"' not in sidebar


def test_compose_profiles_core_vs_optional():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert 'profiles: ["pooler", "full"]' in compose
    assert "postgres_db:" in compose and "redis_cache:" in compose and "minio_s3:" in compose
    # Loki removed from active runtime
    assert "\n  loki:" not in compose and "eims-loki" not in compose
    for core in ("postgres_db:", "redis_cache:", "minio_s3:", "prometheus:", "grafana:"):
        assert core in compose
    # PgBouncer remains optional profile; Observability is default (no required profile)
    assert "pgbouncer:" in compose
    # prometheus/grafana should not be gated solely behind observability profile anymore
    prom_block = compose.split("prometheus:", 1)[1].split("grafana:", 1)[0]
    assert "profiles:" not in prom_block


def test_start_eims_bat_starts_core_with_observability():
    bat = (ROOT / "start_eims.bat").read_text(encoding="utf-8")
    assert "up-core" in bat
    assert "Observability" in bat
    assert "start_eims_pooler.bat" in bat
    assert "docker compose up -d\n" not in bat.replace("\r\n", "\n")


_IMPORT = re.compile(r"""(?:from|import)\s+['"]((?:@/|\./|\.\./)[^'"]+)['"]""")


def _resolve_local_import(importer: Path, spec: str) -> Path | None:
    src = ROOT / "clients" / "dashboard" / "src"
    base = (src / spec[2:]) if spec.startswith("@/") else (importer.parent / spec)
    for candidate in (base.with_suffix(".tsx"), base.with_suffix(".ts"), base / "index.tsx", base / "index.ts"):
        if candidate.is_file():
            return candidate.resolve()
    return None


def _reachable_modules(entry: Path) -> set[Path]:
    """Local TS/TSX modules reachable from `entry` through static imports (a contract on wiring, not on file layout)."""
    seen: set[Path] = set()
    todo = [entry.resolve()]
    while todo:
        current = todo.pop()
        if current in seen:
            continue
        seen.add(current)
        for spec in _IMPORT.findall(current.read_text(encoding="utf-8")):
            target = _resolve_local_import(current, spec)
            if target is not None and target not in seen:
                todo.append(target)
    return seen


def test_analyzer_history_encoding_and_incident_embed_hooks():
    src = ROOT / "clients" / "dashboard" / "src"
    history = (src / "components" / "AnalyzerHistoryList.tsx").read_text(encoding="utf-8")
    link = (src / "components" / "incidents" / "EventIncidentLink.tsx").read_text(encoding="utf-8")
    assert "analysis records · Sorted by analysis date" in history
    assert "Ã‚Â·" not in history
    assert "EventIncidentLink" in history
    # Wiring contract (survives moving the workspace between components): the Incident Workspace is reachable from the
    # Analyzer route, and the Analyzer route reaches the association link used for background incident association.
    reachable = {m.name for m in _reachable_modules(src / "app" / "analyzer" / "page.tsx")}
    assert "IncidentWorkspace.tsx" in reachable
    assert "EventIncidentLink.tsx" in reachable
    assert "Analysis History" in history
    assert "Diagnostic Knowledge Catalog" in history
    # Association is background-first (approved UX): the link ensures the incident automatically, never offers a
    # manual "Create Incident" action, surfaces ambiguity instead of guessing, and opens an incident only on an
    # explicit click.
    assert "autoEnsure = true" in link
    assert "Create Incident" not in link
    assert "ambiguous-candidates" in link
    assert 'data-testid="open-associated-incident"' in link
    assert "event-incident-actions" in link
    incidents = (src / "app" / "incidents" / "page.tsx").read_text(encoding="utf-8")
    assert "/analyzer?incident=" in incidents   # explicit navigation target for an incident


def test_settings_page_has_configuration_and_diagnostics_tabs():
    """Current IA (Cursor): Settings holds genuine browser preferences; analysis language lives on Analyzer; runtime
    diagnostics live under Observability, which Settings links to. The contract is where each capability is wired."""
    src = ROOT / "clients" / "dashboard" / "src"
    settings = (src / "app" / "settings" / "page.tsx").read_text(encoding="utf-8")
    prefs = (src / "lib" / "portal-preferences.ts").read_text(encoding="utf-8")
    analyzer = (src / "app" / "analyzer" / "page.tsx").read_text(encoding="utf-8")
    observability = (src / "app" / "observability" / "page.tsx").read_text(encoding="utf-8")
    assert "writePortalPreferences" in prefs and "analyzerLanguage" in prefs
    # Settings persists a preference through the shared preference module (not ad-hoc storage).
    assert "writePortalPreferences" in settings and "theme" in settings
    # The analysis language preference is read and written by the Analyzer page itself.
    assert "readPortalPreferences().analyzerLanguage" in analyzer
    assert "writePortalPreferences({ analyzerLanguage" in analyzer
    # Runtime diagnostics are reachable from Settings and exist on the Observability route.
    assert 'href="/observability"' in settings
    assert "diagnostics" in observability.lower()


def test_grafana_prometheus_provisioning_present():
    ds = (ROOT / "deployments" / "observability" / "grafana" / "provisioning" / "datasources" / "prometheus.yml").read_text(
        encoding="utf-8"
    )
    dash = (ROOT / "deployments" / "observability" / "grafana" / "dashboards" / "eims-operations.json").read_text(
        encoding="utf-8"
    )
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "http://prometheus:9090" in ds
    assert "eims_fastapi" in dash
    assert "grafana/provisioning" in compose
    assert "host.docker.internal:host-gateway" in compose


def test_set_active_profiles_helper_roundtrip(monkeypatch):
    import scripts.set_active_profiles as sap

    # Avoid pytest tmp_path cleanup PermissionError on Windows junction pytest-current.
    target = ROOT / "deployments" / "local" / "_test_active-profiles.env"
    monkeypatch.setattr(sap, "PATH", target)
    try:
        sap.write(obs="1", pool="0")
        assert sap.read() == {"EIMS_EXPECT_OBSERVABILITY": "1", "EIMS_EXPECT_POOLER": "0"}
        sap.write(obs="0", pool="1")
        assert sap.read() == {"EIMS_EXPECT_OBSERVABILITY": "0", "EIMS_EXPECT_POOLER": "1"}
        text = target.read_text(encoding="utf-8")
        assert "EIMS_EXPECT_OBSERVABILITY=0" in text
        assert "EIMS_EXPECT_POOLER=1" in text
    finally:
        if target.exists():
            target.unlink()
