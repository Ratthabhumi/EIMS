# EIMS — Local-First Infrastructure Necessity Audit

**Date:** 2026-11-19  
**Branch / HEAD:** `demo/2026-11-24` @ `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de`  
**Mode:** Audit completed; **implementation applied 2026-11-19** (Compose profiles, Core-only `start_eims.bat`, Loki removed from active runtime, NOT_ENABLED infra status). See `docs/operations/LOCAL_OPERATIONS_RUNBOOK.md`.  
**Scope:** Owner Windows local-first footprint — smallest reliable set that preserves engineering capability and data integrity.

## Evidence classes (legend)

| Tag | Meaning |
|---|---|
| **R** | Verified from repository configuration / code |
| **RT** | Measured or probed at runtime on this host |
| **D** | Official product documentation (version-sensitive notes) |
| **REC** | Engineering recommendation (owner decision still required) |
| **U** | Unverified / insufficient evidence |

---

## 1. Current architecture

### Compose stack (`docker-compose.yml`) — **R**

All services start on every `docker compose up -d`. **No Compose `profiles:` keys exist** (`profiles_key_count=0`).

| Service (compose key) | Container | Host bind | Restart | Persistent volume |
|---|---|---|---|---|
| `postgres_db` | `eims-postgres` | `127.0.0.1:5432` | unless-stopped | `eims_postgres_storage` |
| `pgbouncer` | `eims-pgbouncer` | `127.0.0.1:6432` | unless-stopped | none |
| `redis_cache` | `eims-redis` | `127.0.0.1:6379` | unless-stopped | `eims_redis_storage` (AOF) |
| `minio_s3` | `eims-minio` | `127.0.0.1:9000`, `:9001` | unless-stopped | `eims_minio_storage` |
| `minio_setup` | `eims-minio-setup` | — | one-shot | creates bucket `eims-ocr-manifests` |
| `prometheus` | `eims-prometheus` | `127.0.0.1:9090` | unless-stopped | `eims_prometheus_storage` |
| `grafana` | `eims-grafana` | `127.0.0.1:3000` | unless-stopped | `eims_grafana_storage` |
| `loki` | `eims-loki` | `127.0.0.1:3100` | unless-stopped | **none** (ephemeral container FS) |

### Host processes (outside Compose) — **R**

| Process | How started | Port |
|---|---|---|
| FastAPI Core API | `start_eims.bat` → uvicorn `:8000` | 8000 |
| Next.js Portal | `start_eims.bat` → `npm run dev -p 3001` | 3001 |

### Default application DB path — **R**

`backend/core/config.py` defaults `DB_PORT=5432` with explicit comment to **bypass PgBouncer** for asyncpg transaction-mode incompatibilities. SQLAlchemy still sets `prepared_statement_cache_size=0` (PgBouncer-safe), but the default URL does not target `:6432`.

SQLAlchemy pool: `DB_POOL_SIZE=20`, `DB_MAX_OVERFLOW=10` (**R**).

### Soft-deps escape hatch — **R**

`EIMS_DEMO_SOFT_DEPS=1` makes Redis, object storage, and background workers optional. `/api/v1/ready` requires only PostgreSQL. `/health` may report DEGRADED.

### Audit-time runtime snapshot — **RT** (2026-11-19)

Compose containers up: postgres, pgbouncer, redis, minio, prometheus, grafana, loki.  
Also present (not compose daily stack): disposable PG containers including `eims-knowledge-b-pg-20261119` (~2.1 GiB RSS) — **out of scope for “compose necessity” but dominate host RAM**.

---

## 2. Dependency graph

```
Owner browser
  └─ Portal :3001 (Next.js)
       ├─ BFF /api/eims/* ──► Core API :8000
       └─ infra links (optional) ──► Grafana :3000, Prometheus :9090, MinIO Console :9001

Core API :8000
  ├─ PostgreSQL :5432  (REQUIRED for /ready, Timeline, Audit, Incident, Knowledge, Analyzer history)
  ├─ Redis :6379       (REQUIRED for workers/streams/pubsub unless soft-deps)
  │    ├─ asset cache (optional LRU)
  │    ├─ telemetry / EVTX / incident-ingest streams
  │    └─ pubsub → WebSocket alerts
  ├─ MinIO :9000       (REQUIRED for OCR upload/download + EVTX object fetch unless soft-deps)
  └─ /metrics          ◄── Prometheus scrape (host.docker.internal:8000)

PgBouncer :6432 ──► PostgreSQL   (Compose-started; default app path does NOT use it)
Grafana :3000    ◄── (intended) Prometheus; no repo-provisioned dashboards found
Loki :3100       ── no in-repo EIMS producer/consumer traced
```

---

## 3. Actual runtime consumers

### 3.1 EIMS Portal / Next.js — **KEEP REQUIRED**

- Defined: `clients/dashboard`, started by `start_eims.bat` on `:3001`.
- Depends on Core API for product surfaces; infra consoles are link/probe only (`infra-consoles.ts`, `/api/infra-status`).
- Portal becomes usable after API `/ready` (Postgres-only).

### 3.2 Core API / FastAPI — **KEEP REQUIRED**

- `backend/main.py`: lifespan initializes DB, Redis (hard fail unless soft-deps), seeds users, starts Redis pubsub + workers when not soft.
- Exposes Prometheus instrumentation on `/metrics` via `prometheus_fastapi_instrumentator` (**R**, **/metrics 200** **RT**).

### 3.3 PostgreSQL — **KEEP REQUIRED**

- Consumers: SQLAlchemy engine, Alembic migrations (`start_eims.bat`), Timeline (SQL UNION — **no Redis in timeline package**), Audit, Incident, Knowledge, Analyzer persistence, USB import persistence paths.
- Unavailable → `/ready` fails; Portal Timeline/Analyzer/USB persistence fail.
- Data persisted on `eims_postgres_storage` (~65.5 MiB used **RT**).

### 3.4 PgBouncer

| Question | Finding | Class |
|---|---|---|
| App connect direct or via PgBouncer? | **Direct `:5432` by default** | R |
| Migrations / tests / workers | Default and demo docs use `:5432`; tests treat `5432`/`6432` as operational ports to avoid | R |
| SQLAlchemy pooling already? | Yes — pool 20 + overflow 10 + pre-ping | R |
| Measurable local benefit? | Not demonstrated for single-user; container RSS ~1.4 MiB | RT |
| Transaction pooling vs prepared statements | Compose `POOL_MODE=transaction`; app disables prepared-statement cache for compatibility | R / D |
| Optional for single-user local? | **Yes on default path** — already bypassed | R |
| Removal risk | Low for default config; high if any `.env` or external tool points at `:6432` without updating | U for every env file on disk |

**Recommendation:** `OPTIONAL PROFILE` (local). Do not remove until every connection path (`.env`, tools, docs, Observability probes) is inventoried in an implementation pass.

### 3.5 Redis — consumer classification

| Consumer | Classification | Downtime effect | Evidence |
|---|---|---|---|
| Asset registry read-through cache | optional cache | miss → DB; writes best-effort (do not fail DB commit) | R (`cache.py` set_value soft-fail) |
| Telemetry stream worker | required for feature | ingest/alert pipeline stalls | R |
| EVTX worker streams | required for feature | EVTX job processing stops; objects may sit in MinIO | R |
| Incident ingest streams + consumer | required for correctness of async ingest | outbox/stream lag; jobs pending until Redis returns | R |
| Redis pubsub → WebSocket alerts | required for live alert fan-out | WS alerts silent; durable stream may still exist | R |
| Timeline persistence | **not a Redis consumer** | N/A | R (no redis imports in timeline) |
| Audit journal / PG outbox tables | PG durable; Redis is broker for async consume | PG rows retained; processing delayed | R |
| Analyzer core analyze path | PG (+ optional soft deps) | Analyzer history still PG | R / prior acceptance |
| Rate limiting | none traced as Redis-backed | — | U→none found |
| Health monitoring | Redis ping is a health *signal*, not product store | DEGRADED/DOWN labels | R |

Runtime: `PING`→PONG, `DBSIZE=3` (**RT**) — live but lightly used at probe time.

**Without soft-deps, process startup fails if Redis is down** (**R**). Soft-deps allows Portal-ready without Redis, but workers/OCR-async/ingest do not start.

**Recommendation:** `KEEP REQUIRED` for engineer-grade local (workers + ingest). `KEEP OPTIONAL` only under explicit soft-deps / demo portal-only profile — not as the default engineering Core.

### 3.6 MinIO

| Question | Finding | Class |
|---|---|---|
| Real upload/download? | OCR upload + image stream; EVTX upload + worker `get_object` | R |
| Buckets | `eims-ocr-manifests` (compose setup); runtime also listed `eims-integration-test` | R / RT |
| Persistence | `eims_minio_storage` ~392 KiB used | RT |
| Local filesystem alternative in prod path? | **No** — singleton is `MinIOStorageManager`; only `StubObjectStorage` for tests | R |
| Soft-deps | Can skip init; OCR/EVTX object features unavailable | R |

**Recommendation:** `KEEP REQUIRED` for Core that includes OCR/EVTX evidence. Do **not** remove while those features are in scope — would weaken evidence integrity. Soft-deps Portal-only can omit it.

### 3.7 Prometheus

- Config: scrapes self + `host.docker.internal:8000` (`deployments/observability/prometheus.yml`) **R**.
- Targets both `up` **RT**; FastAPI HTTP metrics present (`http_requests_total`, duration histograms) **RT**.
- Retention/cardinality: storage volume ~135 MiB **RT**; default Prometheus retention not overridden in compose (**U** exact retention days).
- Not required for Portal/API correctness.

**Recommendation:** `OPTIONAL PROFILE` (Engineering Observability).

### 3.8 Grafana

- Compose service + volume ~117 MiB **RT**; RSS ~135 MiB **RT**.
- Portal links exist; `/api/search` returned **401** without credentials — dashboard content **not** verified this audit (**U**).
- No dashboard JSON/provisioning under repo `**/grafana/**` (**R**).
- Healthy container ≠ useful EIMS observability.

**Recommendation:** `OPTIONAL PROFILE`. Dashboard usefulness: `INSUFFICIENT EVIDENCE` until authenticated inventory.

### 3.9 Loki (discovered)

- In compose; port `:3100`; `/ready` returned **503** at probe **RT**.
- No EIMS app log shipper / Promtail / Alloy traced in repo (**R** search scope).
- No named volume — logs not durable across recreate.

**Recommendation:** `REMOVE CANDIDATE` for local-first (or leave stopped). Confirm no external Promtail before deletion.

### 3.10 Exporters / workers / schedulers

- Background workers are **in-process** with Core API (telemetry, EVTX, incident ingest) — not separate containers **R**.
- No separate node-exporter / postgres-exporter in compose **R**.

---

## 4. Decision matrix

| Component | Actual Consumers | Criticality | Runtime Usage | Resource Cost (RSS / vol approx) | Recommendation | Evidence |
|---|---|---|---|---|---|---|
| Portal Next.js | Engineer UI | Critical | Host process | Node (not measured this pass) | **KEEP REQUIRED** | R |
| Core API FastAPI | All product APIs | Critical | Host `:8000` | Host Python | **KEEP REQUIRED** | R / RT `/metrics` |
| PostgreSQL | Timeline, Audit, Incident, Knowledge, Analyzer, migrations | Critical | healthy | ~23 MiB / 65.5 MiB vol | **KEEP REQUIRED** | R / RT |
| PgBouncer | None on default app path; Observability probe only | Non-critical local | running unused by default | ~1.4 MiB / 0 vol | **OPTIONAL PROFILE** | R / RT |
| Redis | Cache; streams; pubsub; workers | Critical for full features; optional soft-deps | healthy, DBSIZE=3 | ~8 MiB / 84 KiB vol | **KEEP REQUIRED** (Core engineer); soft-deps exception | R / RT |
| MinIO | OCR, EVTX objects | Critical for evidence features | healthy, buckets present | ~103 MiB / 392 KiB vol | **KEEP REQUIRED** (evidence Core) | R / RT |
| Prometheus | Scrapes `/metrics` | Diagnostics | targets up; HTTP metrics live | ~46 MiB / 135 MiB vol | **OPTIONAL PROFILE** | R / RT |
| Grafana | Portal deep-links; human dashboards | Diagnostics | up; dashboards unverified | ~135 MiB / 117 MiB vol | **OPTIONAL PROFILE** | R / RT / U dashboards |
| Loki | None traced | Unused | ready 503 | ~55 MiB / no vol | **REMOVE CANDIDATE** | R / RT |
| minio_setup | Bucket bootstrap | Required once per MinIO lifecycle | exited 0 | ephemeral | **KEEP REQUIRED** with MinIO | R / RT |
| Disposable PG leftovers | Acceptance/knowledge tests | Not daily Core | knowledge-b ~2.1 GiB | high | **Operational cleanup candidate** (owner-approved) | RT |

### Consequence of each recommendation type

- **KEEP REQUIRED** — omitting breaks daily engineer operation or data path for in-scope features.
- **KEEP OPTIONAL** — product can run without it under an explicit mode (e.g. soft-deps).
- **OPTIONAL PROFILE** — keep in repo; do not start for daily Core; start for diagnostics.
- **REPLACE WITH EXISTING CAPABILITY** — not used here; no filesystem storage replacement exists for MinIO.
- **REMOVE CANDIDATE** — stop/remove only after owner approval + connection/path sweep.
- **INSUFFICIENT EVIDENCE** — do not decide yet (Grafana dashboard value).

---

## 5. Three recommended deployment profiles

> Prefer adding Compose `profiles:` (or selective `docker compose up` service lists) in a **later** implementation phase. None exist today.

### Profile A — Minimal Core (daily local operation)

**Exact services:** PostgreSQL, Redis, MinIO (+ `minio_setup`), Core API, Portal.

**Dependencies:** API → PG + Redis + MinIO; Portal → API.

**Startup order:** Docker Desktop → PG/Redis/MinIO healthy → minio_setup exit 0 → alembic → API `/ready` → Portal `:3001`.

**Expected RAM (compose subset, measured peers):** postgres+redis+minio ≈ **23+8+103 ≈ 134 MiB** RSS (**RT**). Host API+Portal additional (**U**).

**Disk volumes:** PG + Redis AOF + MinIO (small today).

**Complexity:** Matches `start_eims.bat` readiness probes (already waits only on these three containers) but script currently still starts *all* compose services.

**Unavailable:** Grafana/Prometheus UI; PgBouncer path; Loki; live metrics history beyond scraping `/metrics` ad hoc.

**Failure/recovery:** PG/MinIO volumes survive restart; Redis AOF survives; workers reclaim streams on restart (**R** comments in main).

**Enable/disable today:** Manual `docker compose up -d postgres_db redis_cache minio_s3` (+ setup) — **not** wired into bat (**REC**).

### Profile B — Core + Engineering Observability

**Exact services:** Profile A + Prometheus + Grafana.

**Dependencies:** Prometheus → Core `/metrics` via `host.docker.internal:8000` (API must be up for EIMS series).

**RAM delta:** +~46 MiB Prometheus + ~135 MiB Grafana ≈ **+181 MiB** (**RT**).

**Disk delta:** +~135 MiB prom vol + ~117 MiB grafana vol.

**Unavailable vs Full:** Loki (intentionally omitted until a log shipper exists).

**Features gained:** Time-series of FastAPI HTTP metrics; Grafana exploration **if** datasources/dashboards configured (dashboard quality **U**).

### Profile C — Full Development Environment

**Exact services:** All compose services (current default) + host API/Portal + disposable DBs when testing.

**Includes:** PgBouncer, Loki, full Observability, acceptance leftovers.

**RAM (compose only, approx):** grafana+prometheus+loki+minio+postgres+redis+pgbouncer ≈ **135+46+55+103+23+8+1 ≈ 371 MiB** (**RT**).  
**Plus** disposable containers can exceed **2 GiB** alone (**RT** knowledge-b).

**Use:** Integration tests, infra console demos, troubleshooting pooler path, log stack experiments.

---

## 6. Startup lifecycle recommendations (no script changes in this audit)

### Observed — **R**

1. `start_eims.bat` runs unconditional `docker compose up -d` → **all** services including Grafana/Prometheus/Loki/PgBouncer.
2. Readiness gate only requires `eims-postgres`, `eims-redis`, `eims-minio` + `eims-minio-setup` exit 0.
3. Backend poll uses `/api/v1/ready` (correct vs soft-deps `/health` 503 flicker).
4. Optional Observability failure does **not** block bat after compose up (no health wait on grafana/prometheus/loki/pgbouncer).
5. Restart policies `unless-stopped` keep infra up across reboots; PG/MinIO/Redis/Prom/Grafana volumes persist; Loki does not.

### Proposed minimal deterministic lifecycle — **REC** (implement later)

1. Profile A compose up (named services or `profiles: [core]`).
2. Health wait on PG/Redis/MinIO + setup.
3. Migrate → API → Portal.
4. Optional: `profiles: [observability]` for Prometheus/Grafana.
5. Never block Core on Observability.
6. Document disposable-container hygiene separately from Core.

---

## 7. Resource measurements

| Item | Value | Class |
|---|---|---|
| Compose RSS sum (7 services) | ~371 MiB | RT |
| Observability+Loki+PgBouncer subset | ~237 MiB (graf 135 + prom 46 + loki 55 + pgb 1.4) | RT |
| Core three (PG+Redis+MinIO) | ~134 MiB | RT |
| Volume use PG/Redis/MinIO | 65.5M / 84K / 392K | RT |
| Volume use Prom/Grafana | 135M / 117M | RT |
| Expected savings if Profile A vs current full compose | **~230–240 MiB RSS** + avoid growing Prom/Grafana volumes; startup fewer containers | RT / REC |
| Largest non-compose cost | disposable `eims-knowledge-b-pg-20261119` ~2.1 GiB | RT |

---

## 8. Security and data-persistence implications

| Topic | Finding | Class |
|---|---|---|
| Host ports | All compose ports bound `127.0.0.1` — good for local-first | R / RT |
| CORS | Includes `:3000` and `:3001` | R |
| Secrets | Compose defaults still embed demo passwords; rotation evidence lives outside git (`%TEMP%`) per prior checkpoint — **not re-printed here** | R |
| App login | Open-access by design — do not reintroduce | R |
| Persistent volumes | PG, Redis AOF, MinIO, Prom, Grafana | R |
| Backup/restore | PG runbooks exist under `docs/operations/`; MinIO/Redis backup not audited here | U partial |
| Health vs ready | `/ready` = PG only; `/health` includes Redis/MinIO | R |
| Restart policy | unless-stopped on long-lived services | R |
| LAN/Internet exposure | Avoid publishing beyond localhost; Grafana especially | REC |

---

## 9. Risks and rollback considerations

| Risk | Notes |
|---|---|
| Removing Redis while keeping default (non-soft) API | Process fails to start; workers/ingest broken | R |
| Removing MinIO while OCR/EVTX in use | Uploads fail; historical `s3://` URIs unreadable | R |
| Removing PgBouncer | Safe for default `:5432` path; break anyone on `:6432` | R / U envs |
| Removing Prometheus/Grafana | No product regression; lose scrapes/UI; Portal links  go dead until copy updated | R |
| Removing Loki | Likely safe; confirm no external shipper | U |
| Stopping containers without volume delete | Data preserved — preferred rollback | R |
| Volume delete | Data loss — **forbidden** without explicit owner approval | REC |
| Profile implementation | Must not silently change default until owner accepts | REC |

**Rollback:** Re-run full `docker compose up -d`; volumes untouched → prior state restored for persistent services.

---

## 10. Prioritized implementation plan (owner approval required — **not executed**)

1. **Accept this audit** — no infra changes yet.
2. **Introduce Compose profiles** (`core`, `observability`) without deleting service definitions.
3. **Teach `start_eims.bat`** to start Profile A by default; document how to enable Profile B.
4. **Leave PgBouncer in `observability` or `pooler` profile**; keep default `EIMS_DB_PORT=5432`.
5. **Stop Loki by default**; delete only after shipper confirmation.
6. **Authenticate Grafana inventory** — promote or demote based on real dashboards.
7. **Disposable container hygiene** — largest RAM win; separate from compose profile work.
8. **Only then** consider permanent removal of unused definitions.

---

## Unresolved uncertainty

- Grafana dashboard usefulness / datasource wiring (401 without session).
- Whether any private `.env` on this machine forces `EIMS_DB_PORT=6432`.
- Exact Prometheus retention days (defaults).
- Host RSS for Node Portal + uvicorn (not measured this pass).
- Whether any external Promtail/Alloy targets Loki.
- Long-term need for PgBouncer under multi-worker production-like load (out of single-user local scope).

---

## Audit integrity

- No `git reset/clean/stash/checkout/commit/push`.
- No Operational DB mutation; no container stop/remove for this audit.
- No secrets printed.
- Worktree modifications pre-existing; this audit adds documentation + checkpoint references only.
