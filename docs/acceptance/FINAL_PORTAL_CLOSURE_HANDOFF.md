# Final Portal Closure Handoff (Cursor → OpenCode)

Date: 2026-11-19 (Final Cursor Closure)  
Branch: `demo/2026-11-24`  
HEAD (start = end; no commit): `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de`  
Machine: Mew (Windows)

## Verdict

**ACCEPTED WITH LIMITATIONS**

Portal / Frontend / disposable-backend runtime closure is complete with evidence. Remaining items are named limitations and OpenCode-owned Knowledge / Analyzer intelligence work — not unfinished Portal ownership.

Cross-references:
- `docs/acceptance/PORTAL_CORRECTION_ACCEPTANCE.md`
- `docs/acceptance/ANALYZER_UX_AND_WEBSITE_COPY_ACCEPTANCE.md`

---

## A. Repository state

| Field | Value |
|---|---|
| Branch | `demo/2026-11-24` |
| Starting HEAD | `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de` |
| Ending HEAD | `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de` (no commit/push) |
| Working tree | Pre-existing modifications preserved; no `git reset` / `clean` / stash |

### Files changed in this Final Closure round (Cursor)

| Path | Why |
|---|---|
| `backend/infrastructure/cache.py` | Cache `set_value` best-effort so Redis-down soft-deps cannot fail DB commits (USB import root cause) |
| `backend/main.py` | Soft-deps: close Redis client after ping fail so optional cache no-ops |
| `clients/dashboard/src/app/settings/page.tsx` | `Promise.allSettled` + 10s timeout so one probe timeout cannot wipe sibling Health/Ready |
| `clients/dashboard/src/app/analyzer/page.tsx` | Copy: `AI Model`/`Vector RAG` → `Analysis engine`/`Knowledge match` |
| `tests/test_cache_ping.py` | Regression: non-fatal cache set when Redis unavailable |
| `tests/test_analyzer_open_access_ui.py` | Ban `Vector RAG` in Analyzer UI copy |
| `docs/acceptance/FINAL_PORTAL_CLOSURE_HANDOFF.md` | This handoff |
| `docs/acceptance/PORTAL_CORRECTION_ACCEPTANCE.md` | Runtime close-out append |
| `docs/acceptance/ANALYZER_UX_AND_WEBSITE_COPY_ACCEPTANCE.md` | Copy/security close-out append |

### Explicitly not modified (OpenCode)

- Knowledge Foundation / `backend/domain/knowledge/` feature work
- Knowledge migrations / `knowledge_review` schema
- Knowledge catalog expansion / quality gates
- Analyzer Knowledge Retrieval redesign
- Operational PostgreSQL on `:5432` / PgBouncer `:6432`

---

## B. Runtime acceptance

| Item | Evidence |
|---|---|
| Portal URL | `http://localhost:3001` (Grafana remains on `:3000`) |
| Backend URL | `http://127.0.0.1:8000` |
| Disposable DB | Container `eims-portal-accept-pg-20261119`, host `127.0.0.1:56456`, db/role `eims_portal_accept`, comment `EIMS-DISPOSABLE-portal-accept-20261119` |
| Startup | uvicorn + `EIMS_DEMO_SOFT_DEPS=1`, Redis/MinIO pointed at unused `56999`/`56998`, `EIMS_AUTH_MODE=demo`, `EIMS_DB_IDENTITY=eims_portal_accept\|eims_portal_accept` |
| Secrets | `%TEMP%\eims-portal-accept.secret` only (not in repo/docs) |

### Unauthenticated-by-design

| Check | Result |
|---|---|
| Portal loads without login | **PASS** (browser Home) |
| Analyzer has no username/password form | **PASS** |
| Product name Log Analyzer | **PASS** |
| `/api/v1/auth/login` | **410 Gone** |
| BFF `POST /api/session/login` | **410 Gone** |
| Open-access analyze without bearer | **PASS** HTTP 200 |

### Analyzer (real fixture)

| Scenario | Result |
|---|---|
| Valid synthetic Event ID 1000 text (multipart form) | **PASS** HTTP 200; keys include `eventId`, `provider`, `aiSummary`, `historyId` |
| Empty text | **PASS** HTTP 400 `Paste log text or attach...` |
| Browser → BFF → FastAPI analyze | **PASS** Diagnostic Report Event ID 1000 rendered; history count 1→2 |

### Settings

| Scenario | Result |
|---|---|
| Healthy/degraded path | **PASS** Process health `DEGRADED`; PG `UP`; Redis/MinIO `DOWN` |
| Ready | **PASS** `ready` / database `connected` |
| Soft-deps honesty | **PASS** (not fabricated HEALTHY) |
| Save / Gemini controls | **PASS** none present (copy notes removal only) |

### Timeline

| Scenario | Result |
|---|---|
| Real disposable rows | **PASS** verification, INCIDENT_*, evidence, IMPORT/UPDATE_FROM_REPORT (USB) |
| API pagination `limit=2` | **PASS** (prior + this run) |
| Empty ≠ fabricated problem | **PASS** (truthful actor/corr unavailable where unset) |

### Failure / recovery

| Scenario | Result |
|---|---|
| USB import with Redis down (before fix) | HTTP 500 after DB commit — **root-caused** |
| USB import with Redis down (after fix) | **PASS** HTTP 200 |
| Settings sibling timeout wipe (before fix) | both panels `unavailable` / `signal timed out` |
| Settings after allSettled fix | **PASS** DEGRADED + ready |

### Unverified / limited

- Physical USB hardware scan (synthetic fixture only)
- Browser multi-page Timeline click (API pagination proven; UI page size 50)
- Full production secure-tier secret override boot (dev tier used)
- Backend-unavailable Settings re-proof this round (proven in prior Portal Correction; not re-stopped uvicorn to avoid interrupting other checks)

---

## C. Security audit

OpenAPI: `GET /api/openapi.json` → **75** operations (41 GET / 25 POST / 5 DELETE / 3 PATCH / 1 PUT).  
Inventory artifact: `%TEMP%\eims-portal-closure\api-inventory.csv`

### Classification summary

| Class | Examples | Access under open-access product rule |
|---|---|---|
| **A. Read-only** | `/api/v1/health`, `/api/v1/ready`, `/api/v1/timeline`, asset list, history read | Open (`get_current_user` → `demo`) |
| **B. Operational** | `/api/v1/analyze/`, `/api/v1/assets/import-report`, evaluation session create, telemetry ingest | Open on trusted deployment boundary (`require_admin_or_token` → `demo`) |
| **C. Administrative** | `/api/v1/admin/users*`, knowledge-reviewer capability, leaderboard | **Gated** — unauthenticated → **401** (`require_admin`) |

### Verified behaviors

| Check | Result |
|---|---|
| Login not required for Portal | **PASS** |
| Login endpoints 410 | **PASS** (API + BFF) |
| `ADMIN_TOKEN` / secrets in Portal HTML | **PASS** none found |
| `ADMIN_TOKEN` / secrets in dashboard src/env markers | **PASS** none found |
| CORS allow Portal origin | **PASS** `Access-Control-Allow-Origin: http://localhost:3001` |
| CORS foreign origin | **PASS** no `Access-Control-Allow-Origin` for `http://evil.example` |
| BFF same-origin mutation gate | Present in `api/eims/[...path]/route.ts` |
| Open-access identity | Shared principal `demo` — not presented as a human user account |
| Admin user CRUD without token | **401** |

### Remaining security risks (honest)

1. **Trusted-network assumption:** Operational writes (analyze, USB import, evaluation create/update/delete, asset lifecycle, OCR history clear) succeed without application login. This matches the product rule but is **not** safe on a public internet exposure without network controls.
2. **`DELETE /api/v1/assets/ocr-history`** succeeded without bearer during this audit (operational open-access). Documented risk; do not “fix” by reintroducing application login.
3. Evaluation admin DELETE/PUT similarly open under `require_admin_or_token` (covered by existing open-access tests). Treat as Operational on the trusted boundary.
4. Default `EIMS_ADMIN_TOKEN` / JWT defaults remain development defaults — must be overridden outside development (existing `model_post_init` guard).

---

## D. Website copy / navigation audit

### Routes inspected

Primary nav + Home: `/`, `/analyzer`, `/observability`, `/evaluations/admin`, `/timeline`, `/endpoints`, `/settings`  
Direct-URL retained (hidden from nav): `/agents`, `/knowledge`, `/ocr-history`

### Corrections this round

| Route / Component | Issue | Correction | Verification |
|---|---|---|---|
| Analyzer engine panel | `Vector RAG` / `AI Model` marketing | `Knowledge match` / `Analysis engine` | Source + UI test ban |
| Home / Sidebar | (prior) Client Agents cards | Already USB-only in Endpoint Evidence | Browser Home |

### Observed (no change required)

| Area | Note |
|---|---|
| Settings “Gemini” string | Intentional: states unsupported Gemini/Save were removed |
| `/agents`, `/knowledge`, `/ocr-history` | Retain Client Agents / Engineering Knowledge / Sticker OCR titles — routes preserved, not primary nav |
| Thai Analyzer result copy | Professional engineer Thai present in Diagnostic Report |
| No `AI Log Analyzer` / `EventIQ` / login form on primary routes | Confirmed |

---

## E. USB Auditor E2E

| Item | Value |
|---|---|
| Fixture | `%TEMP%\eims-portal-closure\usb-auditor-synthetic-fixture*.json` (derived from `clients/usb_auditor/reports/Mew_12-08-2026_14.45.json`) |
| Invalid fixture | Plain text → HTTP **400** `Invalid JSON format` |
| Valid import (after cache fix) | HTTP **200**; hostname `Mew`; compliance **88**; `offline_report_data` present |
| Browser | `/endpoints` shows **Mew** Compliant 88 + PORTAL-ACCEPT-HOST; Import control present |
| Timeline side-effect | `IMPORT_REPORT` / `UPDATE_FROM_REPORT` audit events visible |
| Hardware-specific | **Not covered** (synthetic JSON only) |

---

## F. Regression

```
.\venv\Scripts\python.exe -m pytest tests/test_auth_modes.py tests/test_analyzer_open_access_ui.py tests/test_timeline.py tests/test_timeline_portal_correction.py tests/test_cache_ping.py -q --tb=line
```

| Metric | Value |
|---|---|
| Passed | **30** |
| Failed | **0** |
| Skipped | **0** |
| Exit | **0** |
| Log | `%TEMP%\eims-portal-closure-pytest.log` |

Browser: Home, Analyzer (live analyze), Settings (DEGRADED/ready), Timeline (real events), USB Auditor (imported asset) — all against disposable backend.

---

## G. Handoff to OpenCode

### Cursor completed

1. Backend runtime acceptance on positively identified disposable DB  
2. Security boundary inventory + spot tests (admin gate, CORS, secrets, login 410)  
3. Website copy/nav audit on declared routes; Vector RAG copy fix  
4. USB Auditor synthetic import E2E (root-cause Redis cache fail fixed)  
5. Focused regression 30/30 + acceptance docs  

### Remains for OpenCode

- Knowledge Foundation expansion and quality  
- Knowledge migrations / schema / catalogue import  
- Analyzer Knowledge Retrieval depth and coverage  
- Any backend analyzer intelligence beyond Portal UX  

### Cross-workstream dependencies

- Portal Analyze works without Knowledge Foundation completeness (returns analysis with available local/search context). Knowledge overlay quality is OpenCode’s domain.
- Do not re-own Portal Settings/Timeline/open-access unless a regression is proven.

### Safety confirmation

- No Operational DB use  
- No Knowledge Foundation feature changes in this closure  
- No git commit/push  
- Pre-existing working tree preserved  

---

## Definition of Done checklist

1. Portal opens without application login — **YES**  
2. Analyzer without session/login — **YES**  
3. Real Analyzer against disposable backend — **YES**  
4. Settings reads Health/Readiness — **YES**  
5. Timeline real backend data — **YES**  
6. Failure/recovery truthful — **YES** (cache soft-fail + Settings allSettled)  
7. Security boundary documented — **YES**  
8. No secrets / unintended admin user APIs exposed — **YES** (admin CRUD gated; operational open-access documented)  
9. Website copy/nav audit to declared coverage — **YES**  
10. Home cards / stale nav — **YES** (prior + verified)  
11. USB synthetic E2E — **YES**  
12. No regression on focused suites — **YES** 30/30  
13. Handoff docs complete — **YES**  
14. Knowledge Foundation untouched — **YES**  
