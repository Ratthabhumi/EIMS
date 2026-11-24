# EIMS V12 — Container Dependency Preflight

Date: 2026-11-18 (Asia/Bangkok)
Status: **REPORT ONLY — no container was started, stopped, removed or pruned.**

## 1. Current state

| Container | Image | State | Exit | Finished (UTC) | RestartPolicy | AutoRemove |
|---|---|---|---|---:|---|---|
| `eims-evtx-e2e-pg-20261114` | `pgvector/pgvector:pg16` | exited | 255 | 2026-11-18T11:32:57Z | `no` | false |
| `eims-evtx-e2e-redis-20261114` | `redis:7-alpine` | exited | 255 | 2026-11-18T11:32:57Z | `no` | false |
| `eims-evtx-e2e-minio-20261114` | `minio/minio:latest` | exited | 255 | 2026-11-18T11:32:57Z | `no` | false |
| `eims-ingest-v11-pg-20261116c` | postgres | exited | 255 | (same window) | `no` | false |
| `eims-ingest-v11-redis-20261116c` | redis | exited | 255 | (same window) | `no` | false |
| `eims-pgbouncer` | pgbouncer | **running (Up ~2 h)** | — | — | — | false |

All exits share the same `FinishedAt` (11:32:57Z = 18:32:57 local), which is consistent with the Docker engine stopping, not with six independent application failures. Exit 255 is the container-runtime stop code, not a workload assertion failure.

## 2. Data preservation

| Container | Volume | Mount |
|---|---|---|
| pg (56441) | anonymous volume `e42a4fe0…` | `/var/lib/postgresql/data` |
| redis (56379) | anonymous volume `1d675dbd…` | `/data` |
| minio (59000) | anonymous volume `ca993e79…` | `/data` |

`AutoRemove=false` and the volumes still exist, so **no data has been lost**. The database is `eims_evtx_acceptance`, user `eims_test` (per ledger).

Healthchecks: PostgreSQL `pg_isready -U eims_test -d eims_evtx_acceptance`, Redis `redis-cli ping`. MinIO has **no** healthcheck; readiness must be probed over HTTP (`/minio/health/ready`).

## 3. Ports

| Port | Purpose | Currently listening |
|---|---|---|
| 56441 | disposable PostgreSQL (EVTX/telemetry) | **no** |
| 56379 | disposable Redis (telemetry) | **no** |
| 59000 | disposable MinIO API | **no** |
| 59001 | disposable MinIO console | **no** |
| 56460 | disposable PostgreSQL (incident ingest) | not started |
| 56461 | disposable Redis (incident ingest) | not started |

No port conflict exists right now, which means a start would not collide with another process.

## 4. Which tests need which service

| Test group | Requires |
|---|---|
| `test_evtx_minio_postgres_e2e_acceptance.py` | PG 56441 (`eims_evtx_acceptance`), Redis 56379, MinIO 59000 |
| `test_telemetry_outbox_concurrent_dispatch_integration.py` | PG 56441 (`eims_evtx_acceptance`) |
| `test_telemetry_lease_refresh_integration.py` | Redis 56379 |
| `test_redis_minio_restart_recovery_integration.py` | Redis 56379, MinIO 59000 |
| `test_incident_ingest_*` | `incident_ingest_support.py` constants PG 56460, Redis 56461 |
| `test_analyzer_postgres_integration.py` | `EIMS_TEST_DATABASE_URL` (disposable only) |
| `test_incident_*` (DB-backed) | `EIMS_TEST_DATABASE_URL` via `incident_db_support.py` |

The tests **fail closed**: they refuse to run unless the target host is local and the port/database match the disposable values. This is a safety property, not an obstacle.

## 5. Proposed start commands (NOT EXECUTED — approval required)

```powershell
docker start eims-evtx-e2e-pg-20261114
docker start eims-evtx-e2e-redis-20261114
docker start eims-evtx-e2e-minio-20261114
docker start eims-ingest-v11-pg-20261116c
docker start eims-ingest-v11-redis-20261116c
```

`docker start` on an existing container preserves its volumes. Nothing is recreated, so no data is reset.

## 6. Preflight checks before starting

1. `docker ps -a` confirms the container IDs and that none are already running.
2. `docker volume ls` confirms the three volume IDs from §2 still exist.
3. `Get-NetTCPConnection -LocalPort 56441,56379,59000,59001,56460,56461` confirms the ports are free.
4. Host resources: Docker Desktop running; free RAM above 2 GB after start.
5. Confirm no one else depends on `eims-pgbouncer` during the window.

## 7. Post-start verification (after approval)

```powershell
docker inspect eims-evtx-e2e-pg-20261114 --format '{{.State.Health.Status}}'
docker inspect eims-evtx-e2e-redis-20261114 --format '{{.State.Health.Status}}'
docker exec eims-evtx-e2e-redis-20261114 redis-cli ping
Invoke-WebRequest http://127.0.0.1:59000/minio/health/ready -UseBasicParsing
```

Expected: `healthy`, `healthy`, `PONG`, HTTP 200. If any check fails, stop and report — do not recreate containers.

## 8. Prohibited actions

- `docker compose down -v`
- `docker volume rm`, `docker volume prune`, `docker system prune`
- `docker rm` on the acceptance containers
- Recreating a container with a new volume
- Resetting or re-seeding the database
- Changing container environment variables, ports or passwords
- Touching `eims-pgbouncer` without a separate decision

## 9. Risk assessment

| Risk | Assessment |
|---|---|
| Data loss on start | **Low** — `docker start` reuses the existing volume; nothing is recreated |
| Port conflict | **Low** — all six ports are free now |
| Health not reached | **Medium** — MinIO has no healthcheck; verify over HTTP |
| Image drift | **Low** — images are pinned locally; `minio/minio:latest` is a moving tag, already resolved locally |
| Docker engine restart repeats | **Medium** — the 18:32 stop affected every container; check Docker Desktop stability before a long run |
| Test pointing at wrong DB | **Low** — tests hard-fail on non-disposable targets |

## 10. Status

**BLOCKED pending user approval.** No container was started in this phase.
