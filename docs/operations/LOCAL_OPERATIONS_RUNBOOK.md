# EIMS Local Operations Runbook

Date: 2026-11-19  
Source of truth: `docs/architecture/LOCAL_FIRST_INFRASTRUCTURE_AUDIT.md` + Compose profiles.

## Normal Core startup

```bat
start_eims.bat
```

Starts Local Core **and Observability**: PostgreSQL `:5432`, Redis `:6379`, MinIO `:9000`/`:9001`, Prometheus `:9090`, Grafana `:3000`, then Core API `:8000` and Portal `:3001` on loopback.

Does **not** start PgBouncer (still optional).

## Observability stop / restart

```bat
stop_eims_observability.bat
start_eims_observability.bat
```

Grafana/Prometheus are part of default startup so System & Infra links stay usable. Stop them only when saving RAM; menu entries remain clickable.

Prometheus scrapes Core API `/metrics` via `host.docker.internal:8000` (`deployments/observability/prometheus.yml`).

## Optional PgBouncer

```bat
start_eims_pooler.bat
stop_eims_pooler.bat
```

Compose profile: `pooler` → `eims-pgbouncer` (`127.0.0.1:6432`).

**Default application path remains `EIMS_DB_PORT=5432` (direct PostgreSQL).**  
Only set `EIMS_DB_PORT=6432` when you intentionally want the API/workers to use PgBouncer (transaction pooling; SQLAlchemy already sets `prepared_statement_cache_size=0`). Migrations should stay on `:5432` unless you have verified pooler compatibility for your Alembic/asyncpg path.

## Full Development

```bat
start_eims_full.bat
```

Compose profile: `full` = Core + Observability + Pooler. Loki is **not** included.

Then run `start_eims.bat` for API/Portal if they are not already running (Core containers are already up).

## Prometheus proof queries

Open `http://127.0.0.1:9090` → Graph:

- `up{job="eims_fastapi"}` → expect `1` when Core API is up and scraped
- `up` → list scrape targets
- `sum(rate(http_requests_total[5m]))` → non-zero after API traffic

Grafana: provisioned datasource `Prometheus` → `http://prometheus:9090` (in-compose DNS). Dashboard folder **EIMS** → **EIMS Operations**.

## Settings vs Diagnostics

- Portal **Settings → Configuration**: Analyzer language, history sort, theme (localStorage; applied by Analyzer/ThemeProvider).
- Portal **Settings → Runtime Diagnostics**: read-only `/health` and `/ready` facts.
- Secrets and Compose targets are not editable in the browser — use this runbook / env files.

## Service status interpretation (Portal `/api/infra-status`)

| Status | Meaning |
|---|---|
| HEALTHY | Probe succeeded |
| DEGRADED | Reachable but impaired |
| UNAVAILABLE | Expected / required but unreachable |
| NOT_ENABLED | Optional profile not expected and unreachable — not a Core failure |
| UNKNOWN | No reliable observation |

Profile expectation flags: `deployments/local/active-profiles.env` (updated by profile scripts).

## Safe shutdown

- Stop optional profiles: `stop_eims_optional.bat` (or individual stop scripts).
- Close Backend / Dashboard terminal windows (Ctrl+C).
- Optional: `docker compose stop` for Core containers — **do not** use `docker compose down -v`.
- Persistent volumes: `eims_postgres_storage`, `eims_redis_storage`, `eims_minio_storage`, `eims_prometheus_storage`, `eims_grafana_storage`.

## Backup and restore (local)

See also `docs/operations/postgresql-offsite-backup-recovery-runbook.md`.

Minimal local checks (disposable target only — never restore onto operational `:5432` without explicit approval):

1. PostgreSQL: `docker exec eims-postgres pg_dump -U eims_user eims_registry > backup.sql` then verify file non-empty.
2. MinIO: mirror bucket with `mc` to a host folder; re-list object keys after copy.
3. Integrity: restore dump into a **new disposable** container and `SELECT 1` / spot-check Timeline tables.
4. Recovery: document which volume/backup file maps to which environment.

## Credentials

- Do not commit secrets. Rotation evidence for Grafana/MinIO lives outside git (operator `%TEMP%` secret file from prior task).
- Portal has no application login by design.
- Compose demo defaults remain for local-only loopback binds (`127.0.0.1`).

## Troubleshooting

| Symptom | Check |
|---|---|
| Portal up, Grafana link off | Expected on Core — run `start_eims_observability.bat` |
| `/ready` 503 | PostgreSQL down or wrong `EIMS_DB_*` |
| `/health` DEGRADED | Redis or MinIO down while soft-deps off |
| API not listening on LAN | Intentional — bound to `127.0.0.1` |
| Accidentally using PgBouncer | Unset `EIMS_DB_PORT` or set `5432`; stop pooler profile |
