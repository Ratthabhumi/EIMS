# Analyzer Incident UI P0 Correction — Acceptance

**Date:** 2026-11-19  
**Branch:** `demo/2026-11-24`  
**HEAD:** `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de`  
**Verdict:** **ACCEPTED WITH LIMITATIONS** (P0 UI/integration embedding only — not full E2E)

## Root cause of “History missing”

Owner screenshots of a standalone Incidents list were the **Claude compat page** (`/incidents`), not a deletion of Analysis History. History remained on `/analyzer` via `AnalyzerHistoryList` tabs. Regression perception: Incidents menu + separate page as the normal workflow.

## Fixes (Cursor-owned)

| Item | Change |
|---|---|
| Mojibake | Source literals in `AnalyzerHistoryList.tsx` → UTF-8 `·` / `—` |
| Right panel | `IncidentWorkspace` docked from `analyzer/page.tsx`; `EventIncidentLink` in history detail |
| Tabs | Analysis History + Diagnostic Knowledge Catalog unchanged |
| Nav | Removed standalone Incidents sidebar entry |
| Deep link | `/incidents?id=` redirects to `/analyzer?incident=` |
| Infra nav | Restored clickable Grafana/Prometheus/MinIO/Docs/Settings (no OFF labels) |
| Observability default | Grafana/Prometheus start with `up-core` / `start_eims.bat` |
| Header overflow | `layout.tsx` shrink padding, hide avatar on xs |
| PgBouncer honesty | Observability card renamed/clarified as PostgreSQL probe (`:5432` default) |

## Tests

`tests/test_system_infrastructure_consoles.py` — **10 passed**, exit 0

## Limitations

1. Full Chromium E2E create/link/diagnose/remediate/resolve/knowledge on shared `:8000` not completed in this pass.
2. Correlation 15-minute / unattributed reopen remain Claude domain review items.
3. `test_analyzer_postgres_integration.py` 8 errors not re-run here (needs isolated DB setup).

## Owner check before E2E

- [ ] Analysis History + Catalog visible on `/analyzer`
- [ ] Encoding shows `·` correctly
- [ ] Incident Workspace opens on the right from Event Detail
- [ ] System & Infra entries clickable; Grafana/Prometheus up after Core start
