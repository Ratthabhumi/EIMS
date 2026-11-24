# EIMS Engineering Memory — 2026-11-16 Incident Core v1.1 Ingestion (implementation written, NOT verified)

**Status: IMPLEMENTED IN SOURCE — NOT EXECUTED.** In the session that wrote this code, every Python
interpreter invocation beyond a bare version check (`python -m pytest`, `python -m py_compile`) and
every `docker run` required interactive approval that was unavailable (non-interactive session).
No test, compile, lint, migration or container step has run. Nothing below is a PASS claim.

## Baseline (verified before and after)

- Branch `integration/eims-consolidated`, HEAD `85493b2131d3e353453072559a5dfc301d75dd06`.
- Before: 57 modified + 69 untracked. After: 57 modified + 75 untracked (new: `backend/domain/incident_ingest/`,
  one migration, four test files). No existing modified/untracked file was reset, cleaned, stashed or removed.
- Alembic (repository files only; operational DB never queried): single linear head was `b8d3f5c1a720`; the new
  revision `c4e8a1f7b932` has `down_revision = "b8d3f5c1a720"`, making `c4e8a1f7b932` the single head.

## Architecture (as implemented)

- Package `backend/domain/incident_ingest/` is a **sibling** of `backend/domain/incident/` (that package's
  `__init__` imports the HTTP controller/auth chain; emitters must not import it). Modules: `models.py`
  (`IncidentIngestOutbox`), `envelope.py` (typed validated envelope, keys, allow-listed provenance),
  `outbox.py` (in-transaction emission helpers + non-blocking `nudge_dispatch`), `dispatcher.py`,
  `consumer.py`.
- Table `incident_ingest_outbox`: UUID PK; `source_type` CHECK in (`analysis`,`winlog`) only (telemetry/audit are
  unused, so not added); `source_id` ≤64; nullable `source_event_key` ≤160; nullable `asset_id` FK
  `infrastructure_assets` ON DELETE RESTRICT; `observed_at` timestamptz; `provenance` JSONB with
  `octet_length(provenance::text) <= 1024` CHECK; `created_at`; `published_at`; partial pending index;
  `UNIQUE(source_type, source_id)`. No other table touched. `telemetry_alert_outbox`, its stream and PubSub
  channel are unchanged.
- Emission, same transaction as the source row:
  - Telemetry worker: `_insert_rows` now returns `INSERT … ON CONFLICT DO NOTHING … RETURNING` rows for
    `windows_event_logs`; only returned rows with severity Critical/Error/Warning are enqueued (replayed
    transient uuid4 PKs are never returned). Heartbeats never emit. Post-commit best-effort dispatch.
  - Analyzer submit/bundle/offline import: `enqueue_analysis_history` flushes (no extra commit), uses the
    persisted `analysis_history.id`/`created_at`, then the existing single commit. Submit/bundle `asset_id` stays
    NULL; offline import sets `AnalysisHistory.asset_id` only from the verified registry UUID (non-UUID → NULL).
  - Offline USB winlog batch: `source_id` = persisted `log_id`, NULL `source_event_key`, same severity policy,
    enqueued before the existing batch commit. If a report event has no `occurrence_time`, `observed_at` is the
    ingest-time UTC (the stored fallback is computed independently in `_persist_event`; difference is microseconds).
  - `enqueue_analysis_history` only emits for a real SQLAlchemy `AsyncSession`; in-memory session doubles
    (evaluation `MemoryHistory`, hermetic fakes) are skipped by design so out-of-scope harnesses are untouched.
- Dispatcher: claim `FOR UPDATE SKIP LOCKED` in a short tx → XADD with no DB tx open → separate network-free stamp tx
  only after confirmed XADD; crash window republishes. Trigger: post-commit (telemetry), `nudge_dispatch()` wakeup
  (analyzer/offline) and the consumer loop cadence. `dispatch_pending_safely` never raises.
- Consumer: stream `eims:jobs:incident-ingest:stream`, group `eims:jobs:incident-ingest:workers`, DLQ
  `eims:jobs:incident-ingest:dead-letter` (approved `eims:jobs:` prefix; separate from `eims:events:alerts*`).
  `XAUTOCLAIM` reclaim, `XCLAIM JUSTID idle=0` lease refresh (no delivery-count increment), bounded batch and
  `asyncio.Semaphore` concurrency, one dedicated session per entry, `IncidentService.create_from_evidence`
  with actor `system:incident-ingest`, ACK only after it returns (it commits internally). Failure classes:
  transient (DB/Redis/OS/timeout/conflict) never ACK/DLQ; poison (invalid envelope, `IncidentError`,
  `IntegrityError`/`DataError`, unclassified) is DLQ'd only when the Redis delivery count reaches 5 with a stable
  reason. No new processed-state table: the durable processed state is `incident_evidence UNIQUE(source_type,source_id)`.
- Lifecycle: `backend/main.py` starts the consumer after the telemetry worker and stops it first on shutdown
  (bounded grace, then cancel; unacked entries remain pending for reclaim).
- No atomicity is claimed between the source transaction and the incident transaction: durable intent,
  at-least-once delivery, idempotent sink.

## Files

Added: `backend/domain/incident_ingest/{__init__,models,envelope,outbox,dispatcher,consumer}.py`,
`migrations/versions/c4e8a1f7b932_add_incident_ingest_outbox.py`, `tests/incident_ingest_support.py`,
`tests/test_incident_ingest_unit.py`, `tests/test_incident_ingest_integration.py`,
`tests/test_incident_ingest_migration.py`.
Modified: `backend/domain/telemetry/worker.py`, `backend/api/routers/analyzer/analyze.py`,
`backend/domain/analyzer/services/import_pipeline.py`, `backend/main.py`,
`tests/test_incident_migration.py` (head constants only: single head is now `c4e8a1f7b932`).
`migrations/env.py` was NOT changed (the migration uses explicit `op.*`; metadata registration for
autogenerate would need one import line — deferred as out of the named scope).

## Disposable test services — NOT CREATED

`docker run` was refused by the permission layer. The integration/migration tests require NEW services (never an
existing container). Suggested provisioning (run by a human; choose your own password, do not commit it):

```
docker run -d --name eims-incident-ingest-v11-pg-20261116 --label eims.disposable=incident-ingest-v11 \
  -e POSTGRES_USER=ingest_admin -e POSTGRES_PASSWORD=<choose> -e POSTGRES_DB=eims_ingest_v11_admin \
  -p 127.0.0.1:56460:5432 pgvector/pgvector:pg16
docker run -d --name eims-incident-ingest-v11-redis-20261116 --label eims.disposable=incident-ingest-v11 \
  -p 127.0.0.1:56461:6379 redis:7-alpine
# then, as ingest_admin: CREATE ROLE eims_ingest_v11_app LOGIN NOSUPERUSER PASSWORD '<choose>';
#   CREATE DATABASE eims_ingest_v11_test OWNER eims_ingest_v11_app;
#   COMMENT ON DATABASE eims_ingest_v11_test IS 'EIMS-DISPOSABLE-INGEST-V11:<sentinel>';
#   (in that DB, as ingest_admin) CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;
# Redis: SET eims:disposable:incident-ingest-v11 <sentinel>
# env: EIMS_INGEST_TEST_DATABASE_URL=postgresql+asyncpg://eims_ingest_v11_app:<pw>@127.0.0.1:56460/eims_ingest_v11_test
#      EIMS_INGEST_TEST_REDIS_URL=redis://127.0.0.1:56461/0   EIMS_INGEST_TEST_SENTINEL=<sentinel>
```

The helper refuses any other host/port/database/role, a missing/mismatched sentinel, or a superuser role.
Run (retain JUnit and exit code):
`python -m pytest tests/test_incident_ingest_unit.py tests/test_incident_ingest_integration.py tests/test_incident_ingest_migration.py tests/test_incident_migration.py tests/test_telemetry_reliability_fixes.py tests/test_telemetry_outbox_and_db_unavailable.py tests/test_sprint13_evidence_ingestion.py --junitxml=<path>`.
Note `tests/test_incident_migration.py` still needs its own pre-existing `eims_incident_test` target.

## Verification state (actual)

| Item | State |
|---|---|
| Source implementation | WRITTEN |
| `git diff --check` | exit 0 (CRLF warnings only) |
| Unit tests (`test_incident_ingest_unit.py`) | NOT RUN |
| Existing focused regressions (telemetry fakes, sprint13, incident migration) | NOT RUN |
| Integration + migration tests on disposable PG/Redis | NOT RUN (services not created) |
| Python compile / ruff | NOT RUN |
| Independent read-only review | OPEN — no distinct reviewer was run |

## Known risks / impacts (unverified)

- Asset deletion is now blocked while an outbox row references the asset (FK RESTRICT per decision), whereas
  telemetry rows previously cascaded.
- Any harness that builds analyzer tables by hand against real PostgreSQL (e.g. `tests/analyzer_synthetic_demo_app.py`,
  `tests/test_analyzer_postgres_integration.py`) must also create `incident_ingest_outbox`; not updated, not run.
- A failure of the outbox INSERT fails the source transaction (atomicity over availability); an unpopulated history
  id is an error, never a silent skip.
- `ingest_report_events` offline severity filter uses the report's `severity` string (Critical/Error/Warning).
- Metrics are in-memory counters on the consumer only (no Prometheus registration).
- Outbox rows are never pruned (published rows accumulate); retention is out of scope.

## Boundaries

No commit/push/reset/clean/checkout/stash/rebase. No operational DB, Redis or MinIO access. No existing container,
volume, schema or artifact touched. Chat_HAND, Dashboard and `telemetry_alert_outbox` untouched.
