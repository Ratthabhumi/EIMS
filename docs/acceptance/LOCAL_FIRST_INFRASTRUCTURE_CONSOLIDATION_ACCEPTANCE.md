# Local-First Infrastructure Consolidation — Acceptance

**Date:** 2026-11-19  
**Branch:** `demo/2026-11-24`  
**HEAD:** `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de` (unchanged; no commit)  
**Verdict:** **ACCEPTED WITH LIMITATIONS**

## Decisions implemented

| Service | Decision | Result |
|---|---|---|
| Portal / Core API / PG / Redis / MinIO | KEEP REQUIRED | Default Core startup |
| Prometheus / Grafana | OPTIONAL PROFILE `observability` | Not started by `start_eims.bat` |
| PgBouncer | OPTIONAL PROFILE `pooler` | Not started by default; API still `EIMS_DB_PORT=5432` |
| Loki | REMOVE CANDIDATE | Removed from `docker-compose.yml`; container stopped+removed; no volume |

## Compose profiles

- Default (no profile): `postgres_db`, `redis_cache`, `minio_s3`, `minio_setup`
- `observability` / `full`: `prometheus`, `grafana`
- `pooler` / `full`: `pgbouncer`
- Verified: `docker compose config --services` (no profile) lists only Core services

## Scripts

- `start_eims.bat` → `scripts\eims-compose.bat up-core` + API `127.0.0.1:8000` + Portal `127.0.0.1:3001`
- `start_eims_observability.bat` / `stop_eims_observability.bat`
- `start_eims_pooler.bat` / `stop_eims_pooler.bat`
- `start_eims_full.bat` / `stop_eims_optional.bat`
- Profile expect flags: `deployments/local/active-profiles.env` via `scripts/set_active_profiles.py`

## Health / NOT_ENABLED

- `/api/infra-status` returns `NOT_ENABLED` for Grafana/Prometheus when profile not expected and unreachable
- Expected-but-down → `UNAVAILABLE`
- Optional links use `OptionalInfraLink` (no dead href when NOT_ENABLED)
- Five System & Infra menu labels preserved

## Runtime evidence

### Before → after (RSS, approximate)

| Item | Before | After Core |
|---|---|---|
| knowledge-b disposable PG | ~2.17 GiB | removed |
| grafana+prom+loki+pgbouncer | ~236 MiB | stopped (not in Core) |
| Core PG+Redis+MinIO | ~127 MiB | ~127 MiB healthy |

### Core

- `eims-postgres`, `eims-redis`, `eims-minio` healthy; ports `127.0.0.1` only
- PG `information_schema` public tables count = 30 after consolidation
- MinIO data dirs `eims-ocr-manifests`, `eims-integration-test` present

### Observability (smoke)

- Profile up → Prometheus `/-/ready` OK; targets `eims_fastapi=up`, `prometheus=up` (with Core API `/metrics` 200)
- Grafana `/api/health` `database=ok`
- Profile stop → Core remains up; expect flags return to 0

### Pooler (smoke)

- Profile up → `eims-pgbouncer` running on `127.0.0.1:6432`
- `backend/core/config.py` still defaults `DB_PORT=5432`
- Profile stop leaves Core up

### Loki

- Repo consumers: only former `docker-compose.yml` + historical evidence/docs (no app client)
- Container `eims-loki` stopped and removed; no named Loki volume existed

### Disposable PG cleanup

- `eims-knowledge-b-pg-20261119`: labels `eims.purpose=synthetic-integration-test`, `eims.workstream=knowledge-b`; host port `56470` (not `:5432`); anonymous data mount → **stopped + `docker rm -v`**
- Left untouched (no positive disposable labels / still useful context): `eims-portal-accept-pg-20261119`, `eims-recovery-pg-20261119` (~398 MiB) — **deferred**

## Tests

```
.\venv\Scripts\python.exe -m pytest tests/test_system_infrastructure_consoles.py -q
```

**9 passed**, exit **0** (includes compose profile, start bat, NOT_ENABLED, profile helper roundtrip)

Also previously green in same session: `tests/test_cache_ping.py` with infra suite.

## Docs

- `docs/operations/LOCAL_OPERATIONS_RUNBOOK.md`
- Audit header updated; this acceptance record; operational handoff pointer

## Limitations

1. Full `start_eims.bat` end-to-end from cold boot not re-run in this session (compose Core + optional smokes + unit/static tests done; API/Portal already running from prior work).
2. Grafana dashboard inventory still not fully validated (login UX); Grafana health OK.
3. Remaining disposable PG containers deferred without labels.
4. Reported RAM savings are session measurements, not a guarantee across machines.
5. No `docker compose down -v` and no credential rotation in this task.

## Rollback

- Restore prior `docker-compose.yml` (with Loki) from VCS history if needed
- `docker compose --profile full up -d` restores optional containers; named volumes intact
- Revert Portal/script/docs diffs listed in the working tree
