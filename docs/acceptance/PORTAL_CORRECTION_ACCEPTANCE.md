# Portal Correction Acceptance

Date: 2026-11-19 (runtime close-out)  
Workstream: Portal Correction (independent of Knowledge Foundation / OpenCode)  
Branch: `demo/2026-11-24`  
HEAD: `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de`  
Machine: Mew (Windows)

## Verdict

**ACCEPTED WITH LIMITATIONS**

Runtime + browser evidence for Settings, Timeline, navigation/Home consistency, and USB Auditor reachability is retained below. Residual limitations are documented; none block the Portal Correction close-out.

## Process / port identity

| Process | URL / binding | Notes |
|---|---|---|
| EIMS Portal (Next.js) | `http://localhost:3001` | Confirmed. Port **3000 is Grafana**, not the Portal. |
| FastAPI backend | `http://127.0.0.1:8000` | Started for this acceptance against disposable PG only |
| Disposable PostgreSQL | `127.0.0.1:56456` | Container `eims-portal-accept-pg-20261119` |
| Operational PostgreSQL | `127.0.0.1:5432` | **Not used** |
| Operational PgBouncer | `127.0.0.1:6432` | **Not used** |

## Disposable database identity (non-secret)

| Field | Value |
|---|---|
| Container | `eims-portal-accept-pg-20261119` |
| Host / port | `127.0.0.1:56456` |
| Database | `eims_portal_accept` |
| Role | `eims_portal_accept` |
| DB comment | `EIMS-DISPOSABLE-portal-accept-20261119` |
| Live proof | `current_database()\|current_user\|comment` = `eims_portal_accept\|eims_portal_accept\|EIMS-DISPOSABLE-portal-accept-20261119` |
| Alembic revision | `a1c4e7b9d201` (head) |
| Soft deps | `EIMS_DEMO_SOFT_DEPS=1`; Redis/MinIO pointed at unused high ports so optional tiers are DOWN without touching operational Redis/MinIO |
| Auth | `EIMS_AUTH_MODE=demo` |
| Identity env | `EIMS_DB_IDENTITY=eims_portal_accept\|eims_portal_accept`, `EIMS_DB_IDENTITY_REQUIRED=1` |

Synthetic seed marker: payload/title values include `synthetic: portal-accept` / hostname `PORTAL-ACCEPT-HOST`. Not production evidence.

## Commands and results

### Migration

```
EIMS_DB_* -> 127.0.0.1:56456/eims_portal_accept
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m alembic current
```

- Exit: **0**
- Current: **a1c4e7b9d201 (head)**
- Log: `%TEMP%\eims-portal-accept-alembic.log`

### Focused regression

```
.\venv\Scripts\python.exe -m pytest tests/test_timeline.py tests/test_timeline_portal_correction.py -q
```

- Result: **15 passed**, exit **0**
- Log: `%TEMP%\eims-portal-accept-pytest.log`

### Health / readiness (direct backend)

```
curl.exe -s -w "HTTP_CODE=%{http_code}" http://127.0.0.1:8000/api/v1/health
curl.exe -s -w "HTTP_CODE=%{http_code}" http://127.0.0.1:8000/api/v1/ready
```

**Health** HTTP **503** (expected under soft-deps):

```json
{
  "system": "EIMS Core Gateway",
  "version": "0.3.0",
  "status": "DEGRADED",
  "licensing_model": "Source-Available (All Rights Reserved)",
  "components": {
    "postgresql_pgbouncer_tier": "UP",
    "redis_volatile_lru_tier": "DOWN",
    "minio_object_storage_tier": "DOWN"
  }
}
```

**Ready** HTTP **200**:

```json
{"status":"ready","database":true}
```

Health vs readiness are distinct: process can be DEGRADED while the required DB tier is ready.

### Timeline API (real disposable rows)

Seed counts: audits=4, evidence=1, verifications=1, incidents=1.

`GET /api/v1/timeline?page=1&limit=2` → 200; `total_records=6`; page 1 types: `verification`, `audit` (`INCIDENT_STATUS_CHANGED`).

`GET /api/v1/timeline?page=2&limit=2` → 200; page 2 types: `evidence`, `audit` (`INCIDENT_CREATED`). No overlap with page 1 IDs.

Filters:

| type | total_records | titles observed |
|---|---|---|
| audit | 4 | INCIDENT_STATUS_CHANGED, INCIDENT_CREATED, UPDATE_FROM_REPORT, IMPORT_REPORT |
| incident_transition | 1 | INCIDENT_STATUS_CHANGED |
| evidence | 1 | Evidence attached (analysis/portal-accept-analysis-1) |
| verification | 1 | Verification passed (cycle 0) |

Descriptions retain original verbs (e.g. `IMPORT_REPORT`, `UPDATE_FROM_REPORT`) and map transitions as `investigating → resolved`.

## Browser acceptance (`http://localhost:3001`)

| Check | Result |
|---|---|
| Portal port identity | **PASS** — Portal on **3001**; Grafana remains on 3000 |
| Settings shows real health/ready | **PASS** — Process health `DEGRADED`, readiness `ready`, DB `connected`, PG `UP`, Redis/MinIO `DOWN` |
| No Gemini / Save controls | **PASS** — 0 inputs, 0 Save buttons |
| Backend unavailable fail-fast | **PASS** — after stopping uvicorn on :8000, Settings left Loading and showed `unavailable` / `signal timed out` (not fabricated success) |
| Timeline real records | **PASS** — verification, INCIDENT_STATUS_CHANGED, evidence, IMPORT_REPORT/UPDATE_FROM_REPORT visible with actor/asset/incident; `corr unavailable` |
| Pagination | **PASS at API** (page/limit=2). Browser default page size 50 shows all 6 on one page (`events` + page indicator present) |
| Nav: Client Agents / Knowledge / Sticker OCR hidden | **PASS** |
| USB Auditor accessible | **PASS** — `/endpoints` Launch Agent + Import present |
| Home cards consistent | **PASS** — section “Endpoint Evidence”; USB Auditor only; Client Agents / Sticker OCR cards removed; Settings card copy “Runtime health & readiness” |
| Auth / route protection | Demo mode for this disposable run; secure-mode retest not claimed |

## Files changed in this close-out

- `clients/dashboard/src/app/page.tsx` — Home cards aligned with primary nav (USB Auditor kept; Client Agents / Sticker OCR cards removed)
- `docs/acceptance/PORTAL_CORRECTION_ACCEPTANCE.md` — this runtime evidence update

Prior Portal Correction implementation files remain as previously recorded (Settings, SidebarNav, Timeline service/UI, focused tests). Knowledge Foundation sources were not modified in this close-out beyond applying existing Alembic revisions onto the **disposable** database.

## Remaining limitations

1. **Database identity / recovery** still have no general authorized Settings contract → displayed as unavailable (by design; not invented).
2. **Correlation ID** is not stored on these source rows → UI shows `unavailable`.
3. Soft-deps acceptance intentionally yields **health DEGRADED** with Redis/MinIO DOWN; this is honest, not a fake HEALTHY.
4. Browser multi-page click path not exercised because UI `PAGE_SIZE=50` and fixture has 6 events; server-side pagination proven via API `limit=2`.
5. Routes `/agents`, `/knowledge`, `/ocr-history` remain reachable by direct URL (hide ≠ delete).
6. Secrets for the disposable container were kept only in `%TEMP%\eims-portal-accept.secret` (outside the repo) and are not recorded here.

## Safety

- No Operational DB access on `:5432` / `:6432`
- No Knowledge Foundation feature work
- No git commit/push
- Existing working tree preserved
- Disposable container positively identified by name, port, DB comment sentinel, and live identity query

---

## Final Cursor Closure append (2026-11-19)

Consolidated evidence moved to **`docs/acceptance/FINAL_PORTAL_CLOSURE_HANDOFF.md`**.

Additional runtime proof on the same disposable identity (`eims-portal-accept-pg-20261119` @ `127.0.0.1:56456`):

- Live Analyzer multipart + browser Diagnostic Report (Event ID 1000)
- USB Auditor synthetic import HTTP 200 after Redis soft-deps cache fix
- Settings DEGRADED/ready after `Promise.allSettled` load fix
- Timeline shows USB `IMPORT_REPORT` / `UPDATE_FROM_REPORT` plus prior synthetic incident events
- Focused regression **30 passed** (auth + analyzer UI + timeline + cache)

Portal Correction status remains **ACCEPTED WITH LIMITATIONS**; see Final Handoff for the full closure checklist and OpenCode boundary.
