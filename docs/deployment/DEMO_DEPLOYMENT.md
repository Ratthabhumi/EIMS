# EIMS Demo Deployment (2026-11-24)

## Status

**PREPARED, NOT DEPLOYED.** No Render or Neon resource exists yet, because no
authenticated browser session was available (the browse relay reported
`paired-offline`). Nothing was published and no URL is claimed.

Everything below is the exact procedure to execute once the accounts are
authorized. Do not treat this document as evidence of a live deployment.

## Architecture (chosen)

| Layer | Provider | Plan | Notes |
|---|---|---|---|
| API + demo console | Render Web Service (Python) | Free | HTTPS, public URL, spins down after 15 min idle, ~1 min cold start, ephemeral disk |
| Database | Neon PostgreSQL | Free | direct (non-`-pooler`) hostname, small bounded pool |
| Frontend | **none separate** | — | the repo dashboard is Next.js app-router with server routes and no incidents page; a static export is not possible without changing it. The API serves a same-origin console at `/demo` that calls the real endpoints. |
| Pooler | **not used** | — | the local PgBouncer failed acceptance; the demo uses a direct connection |

Single origin = no CORS surface, no mixed content, one URL to hand over.

## Prerequisites

1. Neon project (`eims-demo-2026`) with a database `eims_demo`.
2. Render account connected to `github.com/Ratthabhumi/EIMS`.
3. The demo branch `demo/2026-11-24` pushed (see "Source snapshot").
4. Two generated secrets held locally only: the demo reviewer password and the
   demo engineer password (`EIMS_DEMO_PASSWORD` is used at seed time).

## Database provisioning (in order)

```bash
# 1. Identity check (must print eims_demo)
psql "$NEON_ADMIN_URL" -c "select current_database(), current_user;"

# 2. Roles + schema access (bootstrap/admin role)
psql "$NEON_ADMIN_URL" -f deploy/sql/01_roles.sql
#    then set passwords out-of-band:
#    ALTER ROLE eims_migrator PASSWORD '...';  ALTER ROLE eims_runtime PASSWORD '...';

# 3. Migrations with the MIGRATION role on the DIRECT host (never -pooler)
EIMS_DB_USER=eims_migrator EIMS_DB_PASSWORD=... EIMS_DB_HOST=<direct-host> \
EIMS_DB_NAME=eims_demo EIMS_DB_PORT=5432 alembic upgrade head
# expect a single head: f7a1c3d9e502

# 4. Runtime grants (AFTER every migration)
psql "$NEON_ADMIN_URL" -f deploy/sql/02_runtime_grants.sql

# 5. Verify guards + ownership
psql "$NEON_ADMIN_URL" -c "select tgname from pg_trigger where tgname like 'trg_incident_%' and not tgisinternal;"
psql "$NEON_ADMIN_URL" -c "select pg_get_userbyid(relowner) from pg_class where relname='incidents';"
```

Then seed with the runtime role:

```bash
EIMS_DEMO_SEED_DATABASE_URL="postgresql+asyncpg://eims_runtime:***@<direct-host>/eims_demo" \
EIMS_DEMO_DATABASE_NAME=eims_demo \
EIMS_DEMO_PASSWORD="<demo password>" \
python tools/seed_demo_2026.py
```

The seed refuses to run unless the live connection reports exactly
`eims_demo`, never truncates, is idempotent, and uses the real
`IncidentService` (including the verification gate).

## Render service

`render.yaml` (repo root) defines one free Python web service:

- build: `pip install --upgrade pip && pip install -r requirements.txt`
- start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT --proxy-headers`
- health check: `/api/v1/health`
- `PYTHON_VERSION=3.12.7` (the local venv is 3.14; Render runs 3.12)

Required environment (names only):

```
EIMS_ENVIRONMENT=production
EIMS_AUTH_MODE=secure
EIMS_DB_HOST / EIMS_DB_PORT / EIMS_DB_NAME=eims_demo
EIMS_DB_USER=eims_runtime
EIMS_DB_PASSWORD=<secret>
EIMS_DB_IDENTITY=eims_demo|eims_runtime
EIMS_DB_IDENTITY_REQUIRED=1
EIMS_JWT_SECRET_KEY / EIMS_ADMIN_TOKEN / EIMS_ADMIN_PASSWORD  (generated)
EIMS_DEMO_SOFT_DEPS=1
```

`EIMS_DEMO_SOFT_DEPS=1` makes Redis, MinIO and the background workers optional
(they are not provisioned on the free demo). In that mode the API starts with
the database only, logs a warning, and skips the workers; the incident workflow
does not depend on them. **This mode must never be used in production.**

Pool sizing: the app sets `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` from settings.
For the demo set them small (for example `DB_POOL_SIZE=2`,
`DB_MAX_OVERFLOW=1`) so the whole service uses at most 3 direct connections,
well inside the Neon free compute limit. Verify the current quota in the Neon
console before raising them.

## Source snapshot

`demo/2026-11-24` is created from the reviewed working tree. It must not contain
`.env`, databases, logs, `.recovery/`, `test-results/`, caches, or the local
compose credentials. The original `integration/eims-consolidated` branch and
HEAD `85493b2` are preserved; the demo branch is never merged back.

## Redeploy

Push to `demo/2026-11-24` (auto-deploy is disabled in `render.yaml`; trigger the
deploy manually) → Render rebuilds → hit `/api/v1/health` → sign in at `/demo`.

## Health and readiness

- `/api/v1/health` reports database/cache/storage probes. With
  `EIMS_DEMO_SOFT_DEPS=1` and no Redis/MinIO it reports `DEGRADED` while the
  database is healthy; that is expected for the demo.
- Startup identity is fail-closed: a wrong `EIMS_DB_IDENTITY` aborts boot.
- `/demo` is the interactive console (same origin, no CORS).

## Deployment record (2026-11-19)

| Item | Value |
|---|---|
| Public service | `https://eims-demo-api.onrender.com` |
| Demo console | `https://eims-demo-api.onrender.com/demo` |
| Readiness (required tier) | `/api/v1/ready` -> `{"status":"ready","database":true}` |
| Health (all tiers) | `/api/v1/health` -> 503 `DEGRADED` because cache/storage are absent by design |
| Render service | `eims-demo-api` (free, Python 3.12.7, Ohio), service id `srv-dbvchv56e07s73be9i60` |
| Neon | project `eims-demo-2026`, database `eims_demo`, PG 17, AWS us-east-2 |
| Connection | direct (no `-pooler`), pool 2 + overflow 1 |
| Migration head | `f7a1c3d9e502` |
| Runtime role | `eims_runtime`; `rolsuper=false`, `rolbypassrls=false`, owns 0 relations, 0 memberships |
| Table ownership | `eims_migrator` owns incidents / incident_evidence / incident_verification |
| Guards | 5 triggers present |
| Deployed commit | `2351fdc` on `demo/2026-11-24` |

### Public E2E result (2026-11-19)

```
health=503 DEGRADED (expected)   ready=200 {"status":"ready","database":true}
unauthenticated GET /api/v1/incidents -> 401
login demo.engineer -> ok; demo.reviewer -> ok
incidents=3  states: open/cycle0, resolved/cycle0, investigating/cycle1
stale evidence resolve attempt -> 422 resolution_blocked:evidence_stale
attach current-cycle analysis evidence -> 200
resolve as demo.reviewer -> 200, status=resolved, verifications=2, latest cycle=1
persisted read-back -> status=resolved, verifications=2
```

No secret is present in `/demo` HTML (checked) and no credential is in this
repository.
