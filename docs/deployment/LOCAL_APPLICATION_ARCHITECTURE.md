# EIMS Local Application Architecture (verified from `start_eims.bat`)

Date: 2026-11-19. Source of truth: `start_eims.bat`, `docker-compose.yml`,
`clients/dashboard/`, `backend/`.

## What the launcher actually starts

```
start_eims.bat
 1. docker version (fails if Docker Desktop is down)
 2. scripts\eims-compose.bat up-core  (postgres, redis, minio only — no observability/pooler)
 3. poll eims-postgres / eims-redis / eims-minio until healthy; wait for eims-minio-setup exit 0
 4. check venv\Scripts\python.exe
 5. alembic upgrade head
 6. start "EIMS Backend (FastAPI)"  uvicorn … --host 127.0.0.1 --port 8000 --reload
    poll http://127.0.0.1:8000/api/v1/ready (max ~90 s)
    start "EIMS Dashboard (Next.js)"  npm run dev -- -H 127.0.0.1 -p 3001
```

Printed URLs: **Portal `http://127.0.0.1:3001`**, API `http://127.0.0.1:8000`.  
Optional: `start_eims_observability.bat` (Grafana `:3000`, Prometheus `:9090`), `start_eims_pooler.bat` (PgBouncer `:6432`).  
See `docs/operations/LOCAL_OPERATIONS_RUNBOOK.md`.

## Component table

| Component | Entrypoint | Port | Required for portal | Cloud requirement |
|---|---|---|---|---|
| EIMS Portal (frontend) | `clients/dashboard` (Next.js 16 app router, `npm run dev`) | 3001 | **yes** | **Node runtime required** — cannot be a static export (app router + `app/api` proxy routes) |
| Backend API | `uvicorn backend.main:app` | 8000 | **yes** | Python web service (already deployed) |
| PostgreSQL | `postgres_db` (pgvector/pg16) | 5432 | yes | Neon (deployed) |
| PgBouncer | `pgbouncer` | 6432→5432 | optional | **not used** in demo (direct connection) |
| Redis | `redis_cache` | 6379 | for workers/pubsub | not deployed in demo (`EIMS_DEMO_SOFT_DEPS=1`) |
| MinIO | `minio` | 9000/9001 | for OCR artifacts | not deployed in demo |
| Prometheus | `prometheus` | 9090 | observability only | not deployed |
| Grafana | `grafana` | 3000 | admin console link | **must not be exposed publicly** |
| Loki | *(removed from active Compose runtime)* | — | not started | not deployed |

## Frontend facts that matter for deployment

- Real portal root: `clients/dashboard` (Next.js 16, React 19, Tailwind 4).
- Pages under `src/app`: `agents`, `analyzer`, `knowledge`, `observability`,
  `evaluations`, `timeline`, `ocr-history`, `endpoints`, `settings`,
  `evaluate`, plus an `api` route (server-side proxy).
- API base URL: `NEXT_PUBLIC_EIMS_API_URL` (default `http://localhost:8000`) and
  `EIMS_BACKEND_URL` for the server-side session proxy.
- The dashboard is **not** a static site: it has server routes and dynamic
  rendering, so a Render Static Site cannot host it.
- QR codes are generated client-side (`qrcode.react`); the backend has no QR
  endpoint.
- "Launch Agent" calls `POST /agents/launch` (admin/token protected) which runs
  `clients/usb_auditor/run.bat` **on the machine running the backend**. On a
  cloud host there is no Windows session to launch into, so this action is
  Local-only by construction.

## Module classification (Local)

| Module | Implementation | Depends on |
|---|---|---|
| Home Portal | Next.js page | API |
| AI Log Analyzer | `analyzer` pages + `backend/api/routers/analyzer/*` | DB; deterministic pipeline (no LLM) |
| Engineering Knowledge | `knowledge` page + knowledge routers | DB |
| Observability & Alerts | `observability` page + telemetry routers | Redis/telemetry workers for live data |
| Service Evaluations | `evaluations` page + `evaluations` router | DB; QR generated client-side |
| Timeline | `timeline` page + timeline router | DB |
| Client Agents | `agents` page + `/agents/launch` | **local process launch** |
| USB Auditor | `clients/usb_auditor` + import-report + endpoint inventory | local agent or offline report |
| Sticker OCR | `ocr-history` page + OCR routers | MinIO + OCR worker |
| Grafana / MinIO / Prometheus / API docs | external consoles / docs links | those services |

## Consequence for the cloud deployment

The public site must run the **same Next.js portal** (a Node web service) with
`NEXT_PUBLIC_EIMS_API_URL` pointing at the API, plus CORS/inter-service routing.
The simplified `/demo` page is a separate, subordinate read-only surface and is
**not** the product. Until the Node service exists, Local/Cloud parity is not
achieved.
