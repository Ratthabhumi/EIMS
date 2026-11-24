# EIMS V12 — Track C Execution Package (Prepared, Not Run)

Date: 2026-11-18 (Asia/Bangkok)
Status: **NOT RUN.** This document is a ready-to-execute package for Gate C.
Baseline: frozen working-tree manifest `53EE6A4093ECB50FEC25F746200F9BBCD10ABAFC17BCA41F567B2FD521BC2356`
Snapshot: `%TEMP%\v12-snapshot\EIMS-20261118-204324` (1,063 files, changed 0 / missing 0 / added 0)

## 0. Preconditions

1. Run only from the disposable snapshot, never from the main working tree.
2. Record the frozen manifest SHA-256 in every result record.
3. No source or test edit is permitted. If a test needs a change to pass, stop.
4. Chat_HAND runtime is **not** required for C1–C9.
5. Containers are required only for C2, C3, C4. They are currently stopped.
6. Credentials are supplied locally by the user as environment variables; never committed, never pasted into a chat.

Collected inventory (not executed): **938 tests / 57 files**, 0 collection errors.

| Step | Scope | Tests | Files | External dependency |
|---|---|---:|---:|---|
| C1 | Dependency-free unit/component | **770** | 37 | none declared |
| C2 | Telemetry / EVTX service-dependent | **8** | 7 | PG 56441, Redis 56379, MinIO 59000 |
| C3 | Incident / event processing | **60** | 6 | PG 56440/56460, Redis 56461, `EIMS_TEST_DATABASE_URL` |
| C4 | Analyzer PostgreSQL integration | **71** | 1 | `EIMS_TEST_DATABASE_URL` |
| C5 | Client-fixture surface (API/search/timeline/OCR/telemetry) | **29** | 6 | full app lifespan (see risk R1) |
| C6 | Evidence / audit / data integrity | subset of C1 | — | none |
| C7 | Agent Monitor (PowerShell) | 169 + 171 | 2 suites | none |
| C8 | Remaining service-dependent integration | 0 new | — | covered by C2–C4 |
| C9 | Operational acceptance | manual | — | services optional |

770 + 8 + 60 + 71 + 29 = **938**. The groups are disjoint.

---

## C1 — Dependency-free unit / component (770 tests, 37 files)

Command:

```powershell
cd $env:TEMP\v12-snapshot\EIMS-20261118-204324
$env:PYTHONDONTWRITEBYTECODE = '1'
& C:\Users\MewMew\Desktop\Co-op\EIMS\venv\Scripts\python.exe -m pytest `
  tests/test_analyzer_evaluation.py tests/test_analyzer_integration_stability.py `
  tests/test_analyzer_investigation.py tests/test_analyzer_reliability.py `
  tests/test_analyzer_timestamp_contract.py tests/test_auth_modes.py `
  tests/test_benchmark_safety.py tests/test_cache_ping.py `
  tests/test_compose_security_audit.py tests/test_core_exceptions.py `
  tests/test_database_ping_diagnostics.py tests/test_diagnostic_catalog.py `
  tests/test_event_knowledge_safety.py tests/test_evtx_parser.py `
  tests/test_evtx_queue_fail_closed.py tests/test_evtx_worker_fault_contracts.py `
  tests/test_global_search_integration.py tests/test_health_probe_concurrency.py `
  tests/test_incident_correlation.py tests/test_incident_ingest_unit.py `
  tests/test_incident_ingest_v11_recovery_unit.py tests/test_knowledge_safety_contract.py `
  tests/test_knowledge_source_candidates.py tests/test_object_store_ping.py `
  tests/test_orm_models.py tests/test_sprint10_migrations.py `
  tests/test_sprint13_evidence_ingestion.py tests/test_state_machine.py `
  tests/test_telemetry_broker.py tests/test_telemetry_controller_idempotency.py `
  tests/test_telemetry_fail_closed.py tests/test_telemetry_nogroup_asset_lock_index.py `
  tests/test_telemetry_outbox_and_db_unavailable.py tests/test_telemetry_recovery_contracts.py `
  tests/test_telemetry_reliability_fixes.py tests/test_telemetry_schemas_and_mtls.py `
  tests/test_telemetry_worker.py `
  -q -p no:cacheprovider --junitxml="$env:TEMP\v12-track-c\c1.xml"
```

- Expected exit code: `0`. Skips are allowed only if recorded and explained.
- Expected collected: 770.
- Estimated runtime: 3–8 min. Resource: low (CPU-bound bursts).
- Data mutation: none expected; no service declared.
- Cleanup: delete `%TEMP%\v12-track-c` only after hashing the XML.
- Stop condition: any failure, any collection error, or any test contacting a non-disposable service.

**Caveat (review finding F1):** "dependency-free" means *no declared external dependency* (no `client` fixture, no `EIMS_TEST_*` variable). A few files (`test_object_store_ping`, `test_cache_ping`, `test_database_ping_diagnostics`) probe localhost and are expected to fail closed. If any of them connect to a live service, stop and report.

---

## C2 — Telemetry / EVTX service-dependent (8 tests)

Required: PG 56441 (`eims_evtx_acceptance`), Redis 56379, MinIO 59000/59001, credentials.

```powershell
$env:EIMS_TEST_DATABASE_URL      = 'postgresql+asyncpg://<user>:<pw>@127.0.0.1:56441/eims_evtx_acceptance'
$env:EIMS_TEST_REDIS_URL         = 'redis://127.0.0.1:56379/0'
$env:EIMS_TEST_MINIO_ENDPOINT    = '127.0.0.1:59000'
$env:EIMS_TEST_MINIO_ACCESS_KEY  = '<local>'
$env:EIMS_TEST_MINIO_SECRET_KEY  = '<local>'
$env:EIMS_TEST_SCHEMA            = 'eims_full_lineage_<32 hex>'
& $py -m pytest tests/test_evtx_minio_postgres_e2e_acceptance.py `
  tests/test_evtx_redis_recovery_integration.py `
  tests/test_redis_minio_restart_recovery_integration.py `
  tests/test_synthetic_health_contract.py `
  tests/test_telemetry_end_to_end_recovery.py `
  tests/test_telemetry_lease_refresh_integration.py `
  tests/test_telemetry_outbox_concurrent_dispatch_integration.py `
  -q -p no:cacheprovider --junitxml="$env:TEMP\v12-track-c\c2.xml"
```

- Expected exit code: `0`. These tests **skip** when configuration is absent, so a skipped result is **not** a pass.
- Estimated runtime: 2–6 min. Mutation: disposable DB/schema and MinIO bucket only.
- Stop condition: any test that would target a non-disposable host (the tests are designed to fail closed; do not bypass).

## C3 — Incident / event processing (60 tests)

```powershell
& $py -m pytest tests/test_incident_api.py tests/test_incident_idempotency.py `
  tests/test_incident_ingest_integration.py tests/test_incident_ingest_migration.py `
  tests/test_incident_lifecycle.py tests/test_incident_migration.py `
  -q -p no:cacheprovider --junitxml="$env:TEMP\v12-track-c\c3.xml"
```

- Requires PG 56460 / Redis 56461 for ingest support, plus `EIMS_TEST_DATABASE_URL` for DB-backed incident tests.
- Expected: 60 collected, exit `0`; skips must be explained.
- Estimated: 3–8 min. Mutation: disposable only.

## C4 — Analyzer PostgreSQL integration (71 tests)

```powershell
& $py -m pytest tests/test_analyzer_postgres_integration.py `
  -q -p no:cacheprovider --junitxml="$env:TEMP\v12-track-c\c4.xml"
```

- Requires `EIMS_TEST_DATABASE_URL` pointing at the disposable instance.
- Expected: 71 collected, exit `0`.
- Estimated: 4–10 min. Mutation: dedicated schema only.

## C5 — Client-fixture surface (29 tests) — run with explicit isolation

```powershell
& $py -m pytest tests/test_api_controllers.py tests/test_global_search.py `
  tests/test_ocr_upload_pipeline.py tests/test_telemetry_controllers.py `
  tests/test_telemetry_e2e_pipeline.py tests/test_timeline.py `
  -q -p no:cacheprovider --junitxml="$env:TEMP\v12-track-c\c5.xml"
```

**Risk R1 (review finding F1).** The shared `client` fixture starts the real app lifespan (`tests/conftest.py:94-98` → `backend/main.py` lifespan), which starts OCR/EVTX/telemetry workers and a Redis pub/sub listener using **default** settings. There is no disposable-target guard.

Required mitigation before running C5: either

- (a) run with the operational stack **stopped** and all default ports unbound, or
- (b) add an approved isolation guard — that requires a source change and therefore a **new freeze revision**.

Do not run C5 while an operational PostgreSQL/Redis/MinIO is reachable on the default ports.

## C6 — Evidence / audit / data integrity (subset of C1)

No additional tests. The evidence-relevant assertions live in `test_sprint13_evidence_ingestion.py` (37), `test_state_machine.py` (3) and `test_incident_*` (C3). Report them as part of C1/C3; do not double count.

Missing coverage to record as an acceptance gap: no test asserts tamper-evidence of `AuditLog` (review finding F4 — no trigger, no hash chain).

## C7 — Agent Monitor

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\agent-monitor\tests\Test-WatchEimsAgentJobs.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\agent-monitor\tests\Test-LaunchEimsAgentMonitor.ps1
```

- Expected: watcher 169/169, launcher 171/171 — **two separate suites, never combined**.
- Estimated: 1–2 min each. Mutation: `%TEMP%` only.
- Known untested: real `taskkill` graceful-then-forced path, GUI rendering, raw-key navigation, long-running survival.

## C8 — Remaining service-dependent integration

None beyond C2–C4. If a suite is discovered later, add it explicitly; do not fold it into an existing step.

## C9 — Operational acceptance (manual)

Record: readiness endpoint behaviour, health checks, dependency-failure behaviour (stop Redis, observe fail-closed), restart safety, operator visibility. No automation substitutes for this.

---

## Analyzer accuracy — explicit gap

- Reviewed cases: **0**. Status: `INSUFFICIENT_DATA`.
- No accuracy percentage may be claimed from C1–C9.
- Proposed path (separate, needs approval): build a synthetic, labeled evaluation set from sanitized fixture text — never customer data — with a documented labeling protocol, a held-out split, and a recorded confusion matrix. Until that exists, the final report must state accuracy as not certified.

## Credentials

Do not send secrets to the assistant or store them in the repository. Set them in your own terminal session (or a local `.env` that is git-ignored) before running C2–C5. The tests fail closed if the target is not the disposable loopback instance.

## Evidence format

Per step, write into `evidence/v12-track-c-results/<step>/`:

```json
{
  "step": "C1",
  "command": "...",
  "revision": { "head": "85493b21…", "frozenManifestSha256": "53EE6A40…" },
  "collected": 770,
  "passed": 0, "failed": 0, "skipped": 0,
  "exitCode": 0,
  "startedAt": "...", "finishedAt": "...",
  "junitSha256": "..."
}
```

No step in this package has been executed.
