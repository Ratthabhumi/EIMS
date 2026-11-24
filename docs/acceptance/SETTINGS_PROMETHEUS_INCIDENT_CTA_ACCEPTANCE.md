# Settings + Prometheus/Grafana + Incident CTA — Acceptance

**Date:** 2026-11-19  
**Branch:** `demo/2026-11-24`  
**HEAD:** `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de`  
**Verdict:** **ACCEPTED WITH LIMITATIONS**

## 1. Settings (configuration vs diagnostics)

### Inventory (source-backed)

| Setting | Source of truth | Default | Runtime | Restart | Consumer |
|---|---|---|---|---|---|
| analyzerLanguage | `localStorage` `eims.pref.analyzerLanguage` | th | yes | no | Log Analyzer language select |
| historySort | `localStorage` `eims.pref.historySort` | newest | yes | no | Analysis History default sort |
| theme | `localStorage` `eims-theme` | system | yes | no | ThemeProvider |

**Not fabricated as editable UI:** DB/Redis/MinIO secrets, scrape targets, PgBouncer, app login.

### UI

- Settings → **Configuration** tab: Analyzer language, history sort, theme (persisted + applied).
- Settings → **Runtime Diagnostics** tab: previous health/ready facts (read-only).
- No credentials in the browser.

## 2. Prometheus / Grafana

### Evidence (runtime, this host)

| Check | Result |
|---|---|
| Targets | `eims_fastapi health=up`, `prometheus health=up` |
| `up{job="eims_fastapi"}` | value **1** |
| `sum(rate(http_requests_total[5m]))` | **> 0** (synthetic traffic against `/metrics` + `/ready`) |
| Grafana `/api/health` | `database=ok` |
| Provisioning mounted | `prometheus.yml` datasource + `eims-operations.json` dashboard |

### Repo changes

- `deployments/observability/prometheus.yml` — explicit `/metrics`, host gateway scrape.
- Compose: `extra_hosts host.docker.internal:host-gateway`; Grafana provisioning volumes.
- Dashboard **EIMS Operations** (request rate, latency, target up).

Synthetic traffic is labelled as test load in this acceptance — not production workload.

## 3. Incident CTA

- `EventIncidentLink` restyled with primary **Create Incident** / **Open Incident** / **Link to Incident**.
- Placed **at the top** of Analysis History Event Detail (before the long report).
- Also on post-analyze Diagnostic Report modal when `historyId` is present.
- Right-side `IncidentWorkspace` unchanged (Claude components).

## Tests

`tests/test_system_infrastructure_consoles.py` — **12 passed**, exit 0

## Limitations

1. Full Chromium Browser E2E of Create/Open/Link on Portal `:3001` not re-captured in this pass (UI wiring + Prometheus query evidence present).
2. Grafana dashboard panels need a logged-in Grafana session to screenshot; provisioning files are in-repo and mounted.
3. No new backend preference API — Portal prefs are localStorage by design (no login).
4. Additional Analyzer/worker-specific custom metrics not added (Instrumentator HTTP metrics are the verified series).
