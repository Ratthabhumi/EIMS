# System & Infrastructure Service Integration & Security Acceptance

Date: 2026-11-19  
Branch: `demo/2026-11-24`  
HEAD: `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de` (no commit this task)  
Machine: Mew (Windows)

## Verdict

**ACCEPTED WITH LIMITATIONS**

The existing System & Infrastructure menu (five items, same visual structure) now points at verified real services via configurable public URLs. Live health probes succeed for Grafana, MinIO (API + Console), and Prometheus. Core API Docs links to FastAPI `/api/docs` (no longer the broken BFF path). No administrative credentials observed in Portal HTML. Theme FOUC mitigation and `start_eims.bat` readiness poll reduce Portal flicker during boot.

---

## 1. Destinations (evidence-backed)

| Menu item | Destination | Source of truth | Identity proof |
|---|---|---|---|
| Grafana Metrics | `http://localhost:3000` | `docker-compose.yml` → `eims-grafana` `127.0.0.1:3000:3000`; override `NEXT_PUBLIC_EIMS_GRAFANA_URL` | `GET /api/health` → `database=ok`, version Grafana 13.x; `/login` HTML contains `grafana`, not EIMS Portal |
| MinIO Console | `http://localhost:9001` | compose `server … --console-address ":9001"`; ports `9000` (S3 API) + `9001` (Console); override `NEXT_PUBLIC_EIMS_MINIO_CONSOLE_URL` | Console root HTML contains `MinIO`; API health `GET :9000/minio/health/live` → 200 |
| Prometheus DB | `http://localhost:9090` | compose `eims-prometheus` `127.0.0.1:9090:9090`; override `NEXT_PUBLIC_EIMS_PROMETHEUS_URL` | `GET /-/ready` → `Prometheus Server is Ready.`; UI contains `Prometheus` |
| Core API Docs | `http://localhost:8000/api/docs` | FastAPI `docs_url="/api/docs"` in `backend/main.py`; override `NEXT_PUBLIC_EIMS_API_DOCS_URL` / `NEXT_PUBLIC_EIMS_API_URL` | HTTP 200 `text/html`; `GET /api/openapi.json` → 200 |
| Settings | `/settings` (in-app) | Existing Portal Correction | Still reads `/api/v1/health` + `/api/v1/ready` via BFF |

**Bug fixed:** prior Core API Docs used `apiUrl("/api/docs")` → `/api/eims/api/docs`, which the BFF rejects (only `api/v1` is proxied) → 404. Now links to the real FastAPI docs origin.

Defaults match compose; no ports were guessed. Production/deployments must set `NEXT_PUBLIC_EIMS_*` URLs — they must never contain credentials.

---

## 2. Health-check methods & results

Probe endpoint (server-side, read-only, ≤2.5s each, independent):  
`GET http://localhost:3001/api/infra-status`

| Service | Method | Runtime result (2026-11-19) |
|---|---|---|
| Grafana | `GET {grafana}/api/health` JSON `database==ok` | **HEALTHY** |
| MinIO API | `GET {minioApi}/minio/health/live` | **HEALTHY** |
| MinIO Console | `GET {console}` body matches MinIO | **HEALTHY** |
| Prometheus | `GET {prom}/-/ready` | **HEALTHY** |
| Core API health | `GET {api}/api/v1/health` | **DEGRADED** (HTTP 503 soft-deps Redis down on disposable backend — honest) |
| Core API ready | `GET {api}/api/v1/ready` | **HEALTHY** |
| Settings | existing Settings page | Unchanged; real Health/Readiness |

Semantics used: HEALTHY / DEGRADED / UNAVAILABLE / UNKNOWN / **NOT_ENABLED** (optional Observability profile not started — 2026-11-19 consolidation). One failure does not force others unavailable (`Promise.all` of independent probes).

**Update 2026-11-19:** Grafana/Prometheus are Compose profile `observability` and are **not** started by default Core. When disabled, `/api/infra-status` reports `NOT_ENABLED` (not DOWN). See `docs/acceptance/LOCAL_FIRST_INFRASTRUCTURE_CONSOLIDATION_ACCEPTANCE.md`.

---

## 3. Credential exposure audit

| Check | Result |
|---|---|
| Home HTML: ADMIN_TOKEN / EIMS-ADMIN-TOKEN | **Absent** |
| Home HTML: MinIO secret / root user strings | **Absent** |
| Home HTML: DB password / JWT / Grafana admin password | **Absent** |
| `infra-consoles.ts` / Sidebar / Home / infra-status route source | Forbidden secret tokens absent (focused tests) |
| `.env.example` guidance | Documents that `NEXT_PUBLIC_*` console URLs must never carry secrets |
| Browser-visible destinations | Public console URLs only (Grafana/MinIO Console/Prometheus/API Docs) |

Grafana/MinIO retain their own login UIs; EIMS does not embed their credentials or reintroduce application login.

---

## 4. UI preservation

- System & Infra group unchanged in structure and labels (five items).
- No new menu group, no card redesign, no status badges added to Home/Sidebar.
- Home descriptions preserved: Live telemetry / S3 Object storage / Time-series DB / OpenAPI specs / Runtime health & readiness.

---

## 5. Flicker investigation (`start_eims.bat`)

| Cause | Evidence | Mitigation |
|---|---|---|
| Theme FOUC | `ThemeProvider` applied `dark`/`light` only after hydration; layout used `defaultTheme="system"` | Blocking script in `layout.tsx` sets class from `localStorage` / `prefers-color-scheme` before paint |
| Boot using `/api/v1/health` | HTTP 503 DEGRADED makes `urllib.urlopen` fail → long wait / restart churn | `start_eims.bat` now polls **`/api/v1/ready`** (200 = DB ready) |
| Portal process previously aborted | Port 3001 was not listening after user terminate | Restarted for this verification |

Residual: first Next.js compile and Fast Refresh during `npm run dev` can still refresh once — expected for dev mode, not treated as a product defect.

---

## 6. Tests

```
.\venv\Scripts\python.exe -m pytest tests/test_system_infrastructure_consoles.py tests/test_analyzer_open_access_ui.py -q
```

Result: **8 passed**, exit **0**

Coverage: menu labels preserved; destinations via `infraConsoleUrls`; broken BFF docs link absent; secret markers absent; FOUC script present; infra-status GET is independent/read-only; Analyzer open-access UI guards still pass.

---

## 7. Browser / HTTP verification

- Portal `http://localhost:3001/` HTML contains all five labels and correct hrefs.
- `GET /api/infra-status` returns destinations + per-service status (above).
- Disposable FastAPI on `:8000` used for API docs/ready only — **not** Operational PG `:5432` for this task’s backend process.
- Compose Grafana/MinIO/Prometheus on loopback ports used as live identity targets.

---

## 8. Files touched

| Path | Change |
|---|---|
| `clients/dashboard/src/lib/infra-consoles.ts` | Public console URL helper |
| `clients/dashboard/src/app/api/infra-status/route.ts` | Read-only independent probes |
| `clients/dashboard/src/components/SidebarNav.tsx` | Use helper (same markup) |
| `clients/dashboard/src/app/page.tsx` | Use helper (same cards) |
| `clients/dashboard/src/app/layout.tsx` | Theme pre-paint script |
| `start_eims.bat` | Ready poll instead of Health 503 trap |
| `.env.example` | Document public console URL overrides |
| `tests/test_system_infrastructure_consoles.py` | Focused guards |
| `docs/acceptance/SYSTEM_INFRASTRUCTURE_SERVICE_ACCEPTANCE.md` | This document |

Not touched: Knowledge Foundation, Timeline logic, Analyzer retrieval, Operational DB mutations.

---

## 9. Remaining limitations

1. Default localhost URLs apply when `NEXT_PUBLIC_EIMS_*` unset — correct for compose; deployments must configure explicitly.
2. Core API `/health` may report **DEGRADED** under soft-deps / missing Redis while `/ready` is HEALTHY — intentional distinction.
3. MinIO/Grafana console authentication remains the service’s own login (no EIMS credential proxy) — by design.
4. Physical/network ACL for exposing consoles beyond loopback is an ops concern, not Portal UI scope.
5. Dev-mode Fast Refresh can still cause a single refresh on compile — not eliminated.

---

## Append — Timeline / Health / Credentials closure (2026-11-19)

See:

- `docs/acceptance/UNIFIED_TIMELINE_E2E_ACCEPTANCE.md`
- `docs/acceptance/RUNTIME_HEALTH_AND_READINESS_ACCEPTANCE.md`
- `docs/acceptance/INFRASTRUCTURE_CREDENTIAL_ROTATION_ACCEPTANCE.md`

Observability “PgBouncer Pool” / “MinIO Storage” cards are **health probes via Core API**, not missing Compose services. Compose already publishes `:5432/:6432` and `:9000/:9001`. When Core API is down, cards now show UNAVAILABLE instead of implying each dependency was probed DOWN.

---

## Definition of Done

| Criterion | Met |
|---|---|
| UI visually unchanged; five items present | **Yes** |
| Each item links to intended service (verified) | **Yes** |
| No guessed ports vs compose | **Yes** |
| Real checks via `/api/infra-status` + Settings | **Yes** |
| Missing/degraded reported honestly | **Yes** |
| No secrets in browser HTML | **Yes** |
| Checks non-blocking / independent | **Yes** |
| Regression tests pass | **Yes** (9/9 after consolidation) |
| Acceptance documented | **Yes** |
