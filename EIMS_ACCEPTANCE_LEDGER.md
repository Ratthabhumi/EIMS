# EIMS Acceptance Ledger

Last verified: 2026-11-15 (finalization checkpoint; see latest dated section)
Repository: `C:\Users\MewMew\Desktop\Co-op\EIMS`
Branch: `integration/eims-consolidated`
HEAD: `85493b2131d3e353453072559a5dfc301d75dd06`

## Rules
- PASS requires a completed command, exit code 0, and a retained test report or direct database/service evidence.
- SKIP is never PASS. Historical results are labelled historical and are not current acceptance.
- Integration tests must use only the dedicated disposable endpoints: PostgreSQL 127.0.0.1:56441 / DB eims_evtx_acceptance, Redis 127.0.0.1:56379, MinIO 127.0.0.1:59000.
- Do not run migrations/tests against ports 5432, 6379, 9000, 9001 or PgBouncer 6432.
- Never drop schemas, volumes, containers, operational data, or run git clean/reset.
- Credentials must not be copied into this ledger or handoff.

## Current repository state
- Modified tracked files: 32
- Untracked paths: 30
- Total porcelain entries: 62
- `git diff --check`: PASS (line-ending warnings only)
- HEAD unchanged; no commit/push performed.
- Preserve every existing Modified and Untracked path.

## Acceptance status

| Gate / Test | Status | Evidence / Notes |
|---|---|---|
| Disposable PostgreSQL / Redis / MinIO online | PASS | Containers `eims-evtx-e2e-pg-20261114`, `eims-evtx-e2e-redis-20261114`, `eims-evtx-e2e-minio-20261114`; ports 56441/56379/59000; PG and Redis healthy; MinIO /minio/health/ready HTTP 200 |
| Project Python environment | PASS | `venv\Scripts\python.exe`, Python 3.14.3; Alembic available |
| Alembic graph | PASS | Single head `a3d6f1e8c295`; chain e1a202610250 -> e4a9c8b12d77 -> f7b3d91c4a58 -> a3d6f1e8c295 |
| Disposable migration from empty schema | PASS | Alembic upgraded to a3d6f1e8c295 in schema `eims_full_lineage_4ee389da31e64a669eda8532c250f9fb` |
| Migration indexes | PASS | Both source-event unique indexes, 4625 functional index, and outbox pending index verified in that schema |
| EVTX real E2E + ACK failure/replay | PASS | JUnit: 1 test, 0 failures/errors/skips; real MinIO + Redis + PostgreSQL |
| Telemetry lease refresh | PASS | JUnit: 1 test, 0 failures/errors/skips; real Redis |
| Outbox concurrent dispatch | PASS | JUnit: 1 test, 0 failures/errors/skips; real disposable PostgreSQL + Redis |
| Redis + MinIO restart recovery | PASS | JUnit: 1 test, 0 failures/errors/skips; both named disposable containers restarted and recovered |
| Combined focused integrations | PASS | JUnit: 3 tests, 0 failures/errors/skips |
| Reliability / fault-contract batch | PASS | JUnit: 155 tests, 0 failures, 0 errors, 0 skips; `%TEMP%\\eims-reliability-focused.xml`; process exited successfully |
| Browser security config guard | PASS | Runtime config rejected plaintext HTTP, URL credentials/path and TLS bypass; guard passed in the Playwright run |
| Full Browser Acceptance | FAIL / BLOCKED | Actual run failed at `signIn:synthetic-browser-review:initial-session`: `net::ERR_CONNECTION_REFUSED` for `https://localhost:3449/analyzer`; no listener on 3449 and no backend on 8000; Next dev listener exists on 3000. A config-only placeholder was used in process environment, not a real login credential |
| Analyzer unit regression | PARTIAL | JUnit: 249 tests, 0 failures, 0 errors, 1 skip; 248 passed. Skip: Windows host refused symlink creation. `%TEMP%\\eims-analyzer-unit-20261114.xml` |
| Analyzer export content builders | PASS | Node test: 16 assertions passed; PDF rasterization / browser download not covered |
| Analyzer rule-only evaluation | INSUFFICIENT_DATA | 12 DEV draft cases executed; 0 reviewed cases. All 17 manifest cases remain DRAFT; no accuracy certification or heldout claim |
| Migration downgrade / upgrade / interrupted index retry | PASS | Fresh disposable DB round-trip reached `a3d6f1e8c295`; forced invalid unique indexes (`indisvalid=false`) on both telemetry tables were dropped/rebuilt successfully on retry; all three key indexes valid/ready afterward |
| Disposable PostgreSQL backup / restore | PASS | Custom-format `pg_dump` (36 KB) restored into `eims_restore_drill_20261114`; Alembic head and synthetic row counts matched; 0 invalid indexes |
| Idempotency constraint behavior | PASS | Duplicate `source_event_key` rejected by unique index; two NULL keys accepted as PostgreSQL semantics require |
| Full regression | NOT RUN | Wait until focused blockers are resolved |
| Commit / PR / release | NOT AUTHORIZED | User has not approved commit/push |

## Disposable environment details
- PostgreSQL image: pgvector/pgvector:pg16; DB eims_evtx_acceptance; user eims_test.
- Redis image: redis:7-alpine.
- MinIO image: minio/minio:latest.
- Disposable containers were initially exited, then started explicitly. All three are currently running; PostgreSQL and Redis report healthy. MinIO readiness endpoint returned HTTP 200.
- Volumes are anonymous Docker volumes. Do not remove them.
- The database search_path was set to the active rehearsal schema plus public. pgvector and pg_trgm extensions were moved to public in this disposable DB because prior extension installs were in an unrelated schema and not visible to the migration search_path.
- Do not copy any disposable DB settings into the operational .env.

## Known warnings / defects
1. The first disposable migration attempts exposed extension placement problems: vector and pg_trgm existed but their extension objects were installed in another schema. Corrected only in the disposable database; no project migration source was changed.
2. Reliability batch is now complete: JUnit records 155 tests, 0 failures/errors/skips, exit code 0. The earlier apparent hang was output polling while the process was still running; no process kill was needed.
3. Browser E2E test imports a helper that requires EIMS_TEST_LOGIN_CREDENTIAL at module load, and runtimeConfig requires EIMS_TEST_BROWSER_BASE_URL. Supply only the approved synthetic test credential; do not invent one.
4. README.md Project Status section is stale relative to the current V6 work and recent acceptance tests. Do not silently overwrite; reconcile after current release-gate review.
5. Existing deprecation warnings observed: Starlette TestClient/httpx integration and pythonjsonlogger import path. Not current blockers, but track for dependency maintenance.

## Next acceptance actions
1. Browser Acceptance: establish an isolated synthetic DB/runtime, provide an approved synthetic login credential, start the backend and trusted HTTPS origin on 3449, then rerun the full flow. Current failure is connection refused, not an Analyzer assertion failure.
2. Gold evaluation: independently review/annotate the 17 DRAFT cases, create hash-bound manual claim/citation reviews, then execute DEV reviewed evaluation. Keep the 5 held-out cases sealed until review protocol is complete.
3. Complete Analyzer end-to-end browser journey including actual PDF rendering/download; the current 16 assertions cover content builders only.
4. Extend DB operations acceptance beyond logical pg_dump/restore: WAL archiving/PITR, backup retention, restore-point selection, RPO/RTO measurement, recovery drills, monitoring/alerting and capacity/load evidence.
5. Complete application acceptance, security review, and full regression only after service/runtime isolation is established.
6. Reconcile README Project Status and release documentation after all gates have evidence.
7. Only after all gates pass: source/diff review, release ledger update, then request explicit commit/PR approval.

## Evidence artifacts
- JUnit focused integration: %TEMP%\eims-acceptance-junit.xml
- JUnit Redis/MinIO restart: %TEMP%\eims-restart-acceptance.xml
- Reliability batch partial output: %TEMP%\eims-reliability-focused.out
- Alembic upgrade log: repository root acceptance-alembic-upgrade.log
- Browser config run output: %TEMP%\eims-browser-config2.out
- No credential values are stored here.

## 2026-11-14 follow-up acceptance evidence (21:15 ICT)

### Newly completed
- Reliability / fault-contract suite: 155 tests, 0 failures, 0 errors, 0 skips; JUnit %TEMP%\eims-reliability-focused.xml; exit code 0. No process kill required.
- Analyzer unit suites (test_analyzer_reliability.py, test_analyzer_investigation.py, test_analyzer_evaluation.py): 249 tests, 0 failures, 0 errors, 1 skip; 248 passed. Skip is Windows symlink creation refused by host policy. JUnit %TEMP%\eims-analyzer-unit-20261114.xml.
- Analyzer export content builders: 16 assertions passed; node tools\test_analyzer_exports.cjs. This does not cover PDF rasterization or browser downloads.
- Migration round-trip and failure recovery: separate DB eims_migration_roundtrip_20261114; upgrade from empty to head, downgrade and re-upgrade; manually seeded duplicate synthetic keys caused concurrent unique-index builds to leave INVALID indexes (indisvalid=false, indisready=false); after removing only duplicate fixture rows, Alembic retry dropped/rebuilt both indexes and reached head. Both unique indexes and idx_winlog_4625_src_ip_time report valid/ready.
- PostgreSQL backup/restore drill: custom-format pg_dump created /tmp/eims-roundtrip-20261114.dump inside the disposable PG container (36 KB); restored into eims_restore_drill_20261114; restore exit code 0, Alembic head a3d6f1e8c295, 1 asset / 1 telemetry metric / 1 Windows event, 0 invalid indexes.
- Idempotency constraints: duplicate source_event_key insert rejected with unique violation; two NULL source keys accepted.

### Analyzer evaluation boundary
- Manifest has 17 cases: 12 DEV and 5 HELDOUT; all 17 have review_status=DRAFT.
- Rule-only DEV exploratory run executed 12 draft cases but correctly reported INSUFFICIENT_DATA; reviewed_executed=0. No accuracy certification. Heldout run executed zero cases and is not considered evidence.
- Output directories: test-results\analyzer-rule-only-dev-20261114.json and test-results\analyzer-rule-only-heldout-20261114.json (these are directories containing metrics/config/prediction artifacts, not single JSON files).

### Browser acceptance boundary
- Browser config guard passed (5 invalid runtime configurations rejected; HTTPS-only accepted).
- Full secure-dashboard browser test was attempted and failed before login: net::ERR_CONNECTION_REFUSED navigating to https://localhost:3449/analyzer. test-results\secure-browser-acceptance.json records failedStage signIn:synthetic-browser-review:initial-session; no API events were observed.
- A Next development listener exists on port 3000, but no HTTPS listener on 3449 and no backend listener on 8000. The browser test used a process-local config placeholder only; it was not a real login credential. No database login was attempted because navigation failed.

### Current repository state after generated evidence
- HEAD remains 85493b2131d3e353453072559a5dfc301d75dd06.
- 32 modified tracked paths, 30 untracked paths, 62 total porcelain entries.
- git diff --check passes; only line-ending conversion warnings were printed.
- No commit/push, no operational DB access, no cleanup/deletion.

### Operational database scope not yet proven
Logical dump/restore is not PITR. Still not accepted: WAL archiving, point-in-time recovery to a chosen timestamp, retention enforcement, restore-point inventory, measured RPO/RTO, failover, capacity/load, alert thresholds, and recovery runbooks.
### Additional Analyzer stability regression
- tests/test_analyzer_integration_stability.py: 71 tests, 0 failures, 0 errors, 0 skips; JUnit %TEMP%\eims-analyzer-stability-20261114.xml; exit code 0.
- Combined verified pytest totals for this continuation: 479 tests, 478 passed, 0 failed, 0 errors, 1 environment skip. This total includes 4 focused integrations, 155 reliability/fault-contract tests, 249 Analyzer unit/evaluation tests, and 71 Analyzer integration-stability tests. Export builder checks are 16 additional assertions, not pytest cases.
 
## 2026-11-15 database health-probe continuation

### Confirmed implementation correction
- `AsynchronousDatabaseEngine.ping()` previously bounded only `SELECT 1`; pool checkout and connection cleanup were outside the timeout.
- The probe now uses one `asyncio.timeout(2.0)` cancellation deadline around checkout, `SELECT 1`, and context exit. It validates scalar result 1 and logs phase timings, total elapsed time, `deadline_expired`, sanitized exception class, and pool status.
- Caller `CancelledError` is not swallowed.
- Important: SQLAlchemy intentionally completes safe connection cleanup before propagating cancellation. Cleanup can extend wall-clock duration beyond the 2-second cancellation deadline; this is measured and logged. Do not replace it with detached cleanup or abandon a connection.
- Dependency declarations now match the tested runtime: SQLAlchemy `>=2.0.57,<2.1.0`; asyncpg `>=0.31.0,<0.32.0`. The previous asyncpg upper bound below 0.30 conflicted with the active 0.31 runtime and Python 3.14 support.

### Focused verification
- `test_database_ping_diagnostics.py`: 12 PASS.
- `test_health_probe_concurrency.py`: 1 PASS.
- `test_synthetic_health_contract.py`: 2 PASS.
- Combined targeted run: **15 PASS, 0 FAIL, 0 ERROR, 0 SKIP**; two existing dependency deprecation warnings.
- Ruff on `backend/infrastructure/database.py` and `tests/test_database_ping_diagnostics.py`: PASS.
- `pip check`: PASS, no broken requirements.
- `git diff --check`: PASS; only existing LF-to-CRLF warnings.

### Real disposable PostgreSQL lifecycle verification
- Target: clone container `eims-history-repro-pg-20261114`, loopback port 56442, DB `eims_history_repro_20261114`. Only `SELECT 1` was issued; no row/schema changes. This is not an Operational DB.
- Pool exhaustion with pool_size=1: probe returned False at the 200 ms deadline, phase=checkout, checkout=212.1 ms, deadline_expired=True. After releasing the held connection, the next probe returned True and checked-out count returned to zero.
- Deliberately delayed `AsyncConnection.close()`: task remained pending after deadline until safe cleanup was released; probe then returned False with phase=cleanup, cleanup=263.7 ms, total=266.2 ms. Pool checked-out count was zero and the next probe returned True.
- External caller cancellation during delayed cleanup propagated `CancelledError`; pool checked-out count returned to zero and the next probe passed.
- Latest retained process output: `%TEMP%\eims-ping-live-lifecycle-final.log`; exit code 0.

### Browser Acceptance boundary
- Browser Acceptance remains **NOT PASSED**. No Browser Acceptance attempt was run in this continuation.
- Earlier attempts recorded Analyzer/History 502/503 and `net::ERR_NETWORK_CHANGED`; the health-probe correction closes a confirmed lifecycle gap but does **not** prove that it caused those failures.
- Continue correlating browser request IDs, HTTPS proxy/BFF timings, backend health/analyzer logs, SQLAlchemy pool state, and PostgreSQL activity before claiming root cause or reopening full Browser Acceptance.

### Engineering memory and orchestration
- Added immutable snapshot: `docs/engineering-memory/2026-11-15-database-health-probe.md`.
- Added current pointer: `docs/engineering-memory/INDEX.md`.
- Added root `AGENTS.md` and Cursor rule pointer `.cursor/rules/eims-engineering-memory.mdc`.
- Claude Code completed a read-only audit; its cleanup/cancellation challenge was checked against installed SQLAlchemy 2.0.57 source and real disposable-PostgreSQL tests.
- Parallel research was used for current SQLAlchemy and asyncpg release notes.
- OpenCode provider credentials are stored for Google, OpenAI, OpenRouter, xAI, DeepSeek, Groq and Cloudflare, but run-bridge attempts for Gemini/OpenAI returned failed outcomes with zero tokens; these are not counted as reviews.
- Work Mode remains excluded. Remote Desktop Commander on Mew is the execution path. No commit/push or Operational DB access.
- Final Git state at the database-probe checkpoint: 34 modified tracked paths, 32 untracked paths, 66 total porcelain entries. The original 32 modified and 30 untracked paths remain preserved; two dependency files were additionally modified and two new untracked paths were added for AGENTS/engineering memory.

## 2026-11-15 Analyzer pool-starvation correction

### Confirmed before/after reproduction
- Disposable clone: `eims-history-repro-pg-20261114`, loopback port 56442; Operational DB untouched.
- Before fix: two concurrent `build_summary()` requests each held one of two pool connections while blocked in external summary work. Pool checked out=2, available=0; Health Probe failed at checkout under a 200 ms test deadline. Releasing external work restored the pool.
- After fix: two concurrent Analyzer summary tasks reached external work with pool checked out=0; Health Probe passed during and after external work.
- During deliberately blocked vector embedding, pool checked out=0 and Health Probe passed. Caller cancellation propagated; pool returned to zero.
- Read-only SELECT transaction rollback released a real checked-out connection from 1 to 0; subsequent checkout succeeded.
- PostgreSQL INSERT RETURNING populated id and created_at without a second refresh SELECT; the synthetic insert was rolled back in an outer transaction.

### Root-cause changes
- `summary.build_summary()` now runs RAG in a dedicated short-lived AsyncSession for engine-bound request sessions; it closes before external summary/translation. Caller session is not committed or closed. Connection-bound sessions remain caller-owned.
- Added `rollback_read_only_transaction()`: only engine-bound clean read-only transaction; refuses pending ORM state; uses rollback, never commit. Used before external work in offline import and vector export.
- Vector embedding runs before vector-table checkout; no-op paths release the read-only lookup transaction.
- Offline import releases the clean dedup SELECT transaction before external search/summary.
- Removed post-commit `db.refresh()` from Analyzer history insert; evaluation MemoryHistory now models INSERT RETURNING id/created_at defaults.

### Regression evidence
- Six-file focused pytest suite: **280 PASS, 0 FAIL, 0 ERROR, 0 SKIP**, exit code 0. JUnit: `%TEMP%\eims-analyzer-lifecycle-20261115-rerun.xml`; log: `%TEMP%\eims-analyzer-lifecycle-20261115-rerun.log`.
- Files: database ping diagnostics, health concurrency, synthetic health contract, Analyzer reliability, Analyzer integration stability, Sprint 13 evidence ingestion.
- A first run found one evaluation MemoryHistory mismatch after refresh removal; fixture was corrected to emulate commit-returned defaults, then the full six-file rerun passed. Earlier failure log retained.
- Targeted Ruff correctness rules and compileall passed. Broad all-rules Ruff still reports legacy style/deprecation findings in unrelated lines; do not claim full-file Ruff clean.
- `git diff --check` passes; line-ending warnings only.

### Acceptance boundary
- Browser Acceptance remains **NOT PASSED** and was not rerun.
- This proves and fixes Analyzer-induced pool starvation. It does not yet prove this was the sole cause of historical Browser 502/503. Correlate browser, proxy/BFF, backend, pool, and PostgreSQL evidence on a separately launched disposable stack before acceptance.
- Current immutable snapshot pointer: `docs/engineering-memory/2026-11-15-analyzer-pool-starvation.md`; previous health-probe snapshot remains preserved.
- Git state at checkpoint: 35 modified tracked, 32 untracked, 67 total; no reset/clean/stash/commit/push. All direct SQL used the disposable clone; one GET to the live health endpoint may have invoked a DB ping before its target was confirmed (no write endpoint called; see audit note).
- Final smoke after the last defensive session-bind change: Analyzer reliability + Analyzer integration stability **224 PASS / 0 FAIL / 0 ERROR / 0 SKIP**, exit 0; JUnit `%TEMP%\eims-analyzer-final-smoke-20261115.xml`.
- Audit note: one read-only GET was sent to the existing backend `/api/v1/health` listener before its configured DB target was confirmed. It may have invoked a DB ping; no mutation endpoint was called. The PowerShell client stalled and could not be stopped due Access Denied. No further requests were sent to live listeners. All subsequent DB verification used only the disposable clone.




## 2026-11-15 health-monitor coalescing continuation

### Confirmed request amplification
- The dashboard mounted `NotificationBell` globally (15-second health polling), `SystemStatusCard` on the Analyzer page (30-second polling), and the Observability page had its own 15-second polling. These consumers independently called the same `/api/v1/health` endpoint.
- The endpoint previously ran PostgreSQL, Redis, and MinIO probes on every request. Each infrastructure probe had its own in-flight coalescing, but the aggregate endpoint had no shared snapshot/cache.

### Root-cause correction
- Added a browser-wide, per-tab health monitor in `clients/dashboard/src/lib/health-monitor.ts`: one shared in-flight fetch, one 15-second polling interval, 5-second request abort, one shared snapshot and 40-sample history for NotificationBell, SystemStatusCard, and Observability.
- Removed independent health polling from those three UI consumers. API reachability is distinguished from dependency degradation; HTTP 503 with a valid degraded payload remains a reachable API with component-level DOWN states.
- Added backend aggregate single-flight plus a 5-second monotonic snapshot in `backend/main.py`. Concurrent `/api/v1/health` requests share one set of dependency probes; requests inside the short TTL reuse the last actual result. Any failed dependency remains `DEGRADED`/HTTP 503; no status is fabricated as healthy.
- Added regression coverage for concurrent request coalescing, short-cache reuse, TTL expiry, and degraded-state preservation in `tests/test_health_probe_concurrency.py`.

### Verification
- Focused pytest command: `venv\\Scripts\\python.exe -m pytest -q --junitxml="$env:TEMP\\eims-health-snapshot-20261115.xml" tests\\test_health_probe_concurrency.py tests\\test_database_ping_diagnostics.py tests\\test_synthetic_health_contract.py`.
- Result: **24 passed, 0 failed, 0 errors, 0 skipped**, exit code 0; JUnit `%TEMP%\\eims-health-snapshot-20261115.xml`.
- Dashboard TypeScript `tsc --noEmit`: exit 0.
- ESLint on `health-monitor.ts`, `NotificationBell.tsx`, `SystemStatusCard.tsx`, and `observability/page.tsx`: exit 0.
- Next.js production build: exit 0; `.next/BUILD_ID` generated.
- `git diff --check`: exit 0; only existing LF-to-CRLF warnings remain.

### Acceptance boundary and safety
- Secure Browser Acceptance remains **NOT PASSED** and was not rerun in this continuation. These checks prove the health-polling coalescing logic and frontend compilation, not end-to-end recovery under concurrent Analyzer/History/Export load.
- Next: use a separately launched disposable application stack, correlate browser/proxy/BFF/backend request IDs and dependency probe timings, then run the full secure Browser Acceptance with JUnit. Do not touch Operational DB or reuse live listeners with an unverified target.
- Branch/HEAD unchanged: `integration/eims-consolidated` / `85493b2131d3e353453072559a5dfc301d75dd06`. Current observed Git state: 42 modified tracked paths and 34 untracked paths (76 total status entries). No reset, clean, stash, commit, push, or destructive cleanup.


## 2026-11-15 verification refresh — degraded-cache regression

- Added `test_degraded_health_snapshot_is_cached_without_reporting_healthy`: repeated reads of a cached degraded snapshot must both remain HTTP 503 / `DEGRADED`, with PostgreSQL DOWN, and execute only one dependency probe batch.
- Re-ran the same focused suite. Final result: **25 passed, 0 failed, 0 errors, 0 skipped**, exit code 0. JUnit path unchanged: `%TEMP%\\eims-health-snapshot-20261115.xml`.
- Historical Browser evidence clarification: `test-results/secure-browser-acceptance-20261115-isolated/secure-browser-acceptance.json` records 25 Browser checks before this health-monitor fix, then FAIL at `signIn:synthetic-expiry:authenticated-ui`; 24 correlated HTTP 503 `/api/eims/api/v1/health` responses among 518 correlated records. This is the 25-check / 24-health-503 run and remains valid pre-fix evidence.
- A later retained attempt, `test-results/secure-browser-acceptance-20261115-session-readonly/`, reached 3 checks then failed at the source-evidence keyboard locator (`details summary` focus timeout), not a health 503. `session-readonly2` failed before checks during initial navigation. These are separate harness/runtime failures and must not be conflated with the 25-check health run.
- No Browser Acceptance has been rerun against the new shared monitor and backend snapshot. Acceptance remains NOT PASSED.


## 2026-11-15 — final integrated acceptance refresh

### Verified results
- Secure Browser Acceptance final10: **PASS 33/33**; Playwright **2/2**; zero correlated HTTP 502/503 responses.
- Full pytest: 748 collected, zero failures; six opt-in infrastructure tests were intentionally skipped in the full run and then executed separately against dedicated disposable PostgreSQL/Redis/MinIO services: **6/6 PASS**. Combined distinct suite: **748/748 passed**.
- Analyzer/PostgreSQL integration **67/67 PASS** on a clean isolated DB.
- Health-probe suite **46/46 PASS**; focused Analyzer/auth/investigation suite **186/186 PASS**; diagnostic catalogue suite **48/48 PASS** after the Event 1129 correction.
- Targeted Ruff checks, Python compilation, JSON validation, and `git diff --check` pass.
- Dedicated EVTX/telemetry tests cover the 1,601-record EVTX fixture, MinIO persistence, Redis Streams replay, ACK-failure recovery, lease refresh, concurrent outbox dispatch, and Redis/MinIO restart recovery. All six opt-in tests passed.

### Knowledge and evaluation boundary
- Static reference catalogue: 141 Windows Event definitions + 22 vendor/syslog definitions = **163 entries**.
- Vendor verification states: 16 official-documentation verified, 4 code-supported with contextual reference, 2 code-supported.
- Knowledge proposal/independent approval/retrieval/provenance/reuse is browser-verified. Synthetic test entries are not production incident knowledge.
- Gold manifest: 17 cases (12 dev, 5 held-out), all still DRAFT. Independent human review remains mandatory before authoritative quality claims or held-out scoring.
- Event 1129 catalogue wording was corrected so DNS is a hypothesis, not an asserted root cause without corroborating evidence.

### Remaining gates — project not declared closed
1. Independent domain review of the 17 gold cases and their evidence/diagnosis/resolution claims.
2. Curated initial approved knowledge set from official documentation and authorized real incidents, with independent approval; do not auto-promote AI output.
3. Explicit JWT-expiry acceptance separate from the already-proven database-session expiry boundary.
4. Witnessed production-like backup/restore and rollback, TLS/secrets, retention, monitoring, and operational ownership sign-off.

### Preservation
- Branch/HEAD remain `integration/eims-consolidated` / `85493b2`.
- No reset, clean, stash, commit, push, or destructive cleanup. Existing modified and untracked work is preserved.
- Detailed snapshot: `docs/engineering-memory/2026-11-15-final-readiness.md`.

## 2026-11-15 — final16 runtime alignment and production-path smoke

### Browser and Playwright
- Browser Acceptance final14: **PASS 33/33**; artifact `test-results/secure-browser-acceptance-20261115-final14/secure-browser-acceptance.json`; correlated HTTP 502/503 = 0.
- Full Playwright final16: **2/2 PASS**; browser artifact `test-results/secure-browser-acceptance-20261115-final16/secure-browser-acceptance.json` = PASS 33/33; `playwright/.last-run.json` = passed, failedTests 0; runner exit file `%TEMP%\eims-playwright-final16-exit-20261115.txt` = 0.
- final14 verifies Follow-up owner isolation: a real `POST /api/v1/analyze/followup` against another user's History returns 404 from the owner guard. final16 verifies other-user History DELETE returns 404 and owner History remains intact.
- final15 failed at duplicate Knowledge title because a prior synthetic fixture remained in the still-running harness. The title is now unique per run and final16 used a fresh synthetic harness process.
- A non-blocking login-request-body observer warning remains; cookie and authenticated-session checks are authoritative. Session expiry proof is server-side DB session expiry with a still-unexpired JWT, not JWT `exp`.

### Production application-path smoke
- Ran `backend.main:app` against dedicated full-migration synthetic DB `eims_browser_acceptance_20261115`, not Operational DB.
- Synthetic login, Analyzer, Follow-up, History, and Stats all returned HTTP 200. Current Health endpoint returns HTTP 200 / HEALTHY with PostgreSQL-PgBouncer, Redis, and MinIO UP.
- Synthetic Windows Event 1129 case persisted to History and supported owner Follow-up. This is a production application-path smoke, not a production deployment or a multi-case quality certification.
- Full schema clone is at Alembic head `c9a4e7b2d610`, 16 public base tables. Main smoke DB currently has 6 History rows, 0 KnowledgeEntry rows, and 5 synthetic users.
- Browser harness uses a separate `eims_regression_test_20261115` DB. Original `eims_integration_test` was preserved; no rename/drop/truncate of that DB.

### Focused tests and code hygiene
- Focused pytest: **88 passed**, 0 failures/errors/skips across Analyzer Investigation, ORM Models, API Controllers, and Global Search.
- Targeted Ruff import-order checks, Python compilation, logger import, and `git diff --check`: PASS.
- Full Ruff is not clean; an all-rules check reported legacy findings in `summary.py` and `stats.py`. Do not claim full lint cleanliness.
- Replaced deprecated `duckduckgo-search` import/dependency with `ddgs>=9.16.1,<10.0.0`; import/context/text interface verified. Live search remains best-effort enrichment, not authoritative evidence.
- Removed `datetime.utcnow()` usage from History defaults and Stats; preserve legacy UTC-naive `analysis_history.created_at` column without schema migration.
- Updated JSON logger import to `pythonjsonlogger.json.JsonFormatter`; production backend restarted without the previous import/deprecation warnings.

### Knowledge and evaluation boundary
- Static vendor catalogue includes seven official Broadcom VMware references plus network/Linux operational catalog entries. These are code-based references, not a populated production Knowledge database.
- Browser Acceptance proves the Knowledge proposal, independent approval, provenance, and exact-identity reuse lifecycle with synthetic data.
- Main synthetic application DB has 0 approved KnowledgeEntry rows. The Browser Acceptance DB's synthetic approved entry is not production knowledge.
- Gold manifest remains 17 DRAFT cases: 12 DEV and 5 HELDOUT; zero human-reviewed. AI agents must not create human review status.
- Knowledge UI/API still lacks full-text symptom/root-cause search, structured Product/Version/Environment applicability, prerequisites, risk, validation/rollback, usage feedback, and stale/revalidation lifecycle.

### Remaining release gates
1. Independent human review of all 12 DEV gold cases, followed by freeze and final 5-case HELDOUT evaluation.
2. Curated initial approved Knowledge corpus from official vendor documents and authorized/sanitized incidents; then add full-text search and structured applicability/safety metadata.
3. Explicit JWT `exp` boundary acceptance separate from server-side session-row expiry.
4. Witnessed WAL/PITR, retention, measured RPO/RTO, failover/recovery, capacity/load, TLS/secrets, monitoring, and operational ownership sign-off.
5. Controlled Engineer pilot with authorized sanitized incidents and feedback on correctness/safety/usefulness.

### Preservation
- Branch/HEAD remain `integration/eims-consolidated` / `85493b2`.
- No commit/push/reset/clean/stash, no Operational DB access, and no destructive cleanup.
- Current authoritative snapshot: `docs/engineering-memory/2026-11-15-final16-runtime-alignment.md`.


## 2026-11-15 — finalization delta: Knowledge search and deterministic tests

### New verified work
- Replaced deprecated `duckduckgo_search` with `ddgs>=9.16.1,<10.0.0` in both requirements and project metadata; maintained import/API smoke passed.
- Removed deprecated `datetime.utcnow()` usage from AnalysisHistory defaults and Stats. Preserved legacy UTC-naive DB timestamp semantics; added a UTC-naive default regression test.
- Fixed test contamination: PostgreSQL integration fixture now deletes pre-existing synthetic KnowledgeEntry rows inside its outer transaction and rolls the transaction back. Existing reviewed entries are preserved after each test.
- Added approved-only literal full-text search to Knowledge API and UI across title, identity, root cause, resolution steps, impact, prevention, evidence and references. LIKE metacharacters are escaped; pending/rejected entries remain private.
- Added integration assertions: pending knowledge is not discoverable; approved knowledge is searchable by resolution text. Knowledge lifecycle/search integration test: **PASS**.

### Verification
- Browser Acceptance final16: **33/33 PASS**; Full Playwright: **2/2 PASS**, exit 0.
- Production application-path synthetic smoke: Login, Analyzer, History, Follow-up, Stats and Health passed; PostgreSQL/Redis/MinIO healthy. This is not a production deployment certification.
- Focused Analyzer Reliability + PostgreSQL Integration + UTC timestamp suite: **100% complete, exit 0**.
- PostgreSQL round-trip subset: **6/6 PASS**.
- Dashboard production build: **PASS**, TypeScript PASS, static pages 15/15.
- Targeted Ruff F401/UP017, Python compilation, and `git diff --check`: **PASS**. Full all-rules Ruff remains not clean; no global lint-clean claim.

### Remaining closure gates
1. Independent human review of 12 DEV gold cases and then frozen 5 HELDOUT evaluation.
2. Curated initial approved knowledge corpus from authoritative vendor docs and authorized/sanitized incidents.
3. Structured product/version/environment applicability, prerequisites, risk level, validation/rollback steps, usage outcomes and stale/revalidation lifecycle.
4. Explicit JWT `exp` boundary acceptance separate from DB-session expiry.
5. Witnessed backup/restore, rollback, WAL/PITR, retention, measured RPO/RTO, failover/recovery, load/capacity, TLS/secrets, monitoring and operational ownership.
6. Controlled Engineer pilot with sanitized incidents and usefulness/safety feedback.

### Preservation
- Branch/HEAD unchanged: `integration/eims-consolidated` / `85493b2`.
- No Work Mode, commit, push, reset, clean, stash, or operational DB access.
- Detail: `docs/engineering-memory/2026-11-15-finalization-search-and-tests.md`.


## 2026-11-15 — structured Knowledge applicability, remediation safety and usage feedback

### Delivered
- Alembic `d1e5a7c9b204`: product, version, environment, prerequisites, risk level, validation and rollback fields; migrated both synthetic DBs.
- High/Critical risk proposals require validation and rollback at request validation, after sensitive-data redaction, and again at approval.
- Approved Knowledge search now includes applicability and safety metadata while preserving approved-only visibility and exact-identity reuse.
- Alembic `d2f6b8c1e305`: append-only `knowledge_usage` table, tied to an approved Knowledge Entry and a new History record owned by the reporting Engineer. Records include History SHA-256, outcome, reporter and timestamp.
- Added usage outcomes (resolved/partial/not resolved/not attempted), duplicate protection, cross-user ownership checks and aggregate usage summary. Feedback does not automatically change AI confidence.
- Knowledge UI now captures applicability, prerequisites, risk, validation/rollback and reports usage outcomes. Existing proposal/approval flow remains independent-review gated.

### Verification
- Both synthetic DBs migrated to Alembic head **d2f6b8c1e305**.
- Knowledge safety/search/usage/migration integration suite: **7 passed**, exit 0.
- Dashboard production build: TypeScript passed; static pages 15/15.
- Targeted Ruff F401/UP017, Python compilation, and `git diff --check`: PASS.
- Live synthetic backend on port 8001: Login 200, Knowledge search 200, Stats 200, Health 200/HEALTHY; PostgreSQL/Redis/MinIO UP.
- Full Browser Acceptance final16 remains 33/33 and Playwright 2/2; it predates the new Knowledge UI usage form. New Knowledge changes are verified separately by integration tests and production build, not by a new full browser run.

### Remaining closure gates
1. Independent human review of 12 DEV gold cases, then frozen 5 HELDOUT evaluation.
2. Curated authoritative approved Knowledge corpus from official vendor sources and authorized/sanitized real incidents.
3. Domain-approved stale/revalidation policy and lifecycle (interval, version support, superseded/withdrawn state, ownership).
4. Explicit JWT `exp` boundary acceptance.
5. Witnessed backup/restore, rollback, WAL/PITR, retention, RPO/RTO, failover/recovery, capacity/load, TLS/secrets, monitoring and operational ownership sign-off.
6. Controlled Engineer pilot with sanitized incidents and usefulness/safety feedback.

### Preservation
- Branch/HEAD unchanged: `integration/eims-consolidated` / `85493b2`.
- No Work Mode, commit, push, reset, clean, stash, or operational DB access.
- Detail: `docs/engineering-memory/2026-11-15-knowledge-safety-usage-feedback.md`.


## 2026-11-15 — finalization delta: Knowledge revalidation, JWT expiry and PostgreSQL PITR

### New implementation
- Added Alembic revision `e5a7c9d2f416` after `d2f6b8c1e305`.
- Added Knowledge lifecycle states: active, revalidation_required, superseded, withdrawn; lifecycle reason/time; superseding entry reference; lifecycle event history.
- Added admin lifecycle transition API, revalidation queue and event-history API. Proposer self-review is blocked; superseding requires same source family and diagnostic identity.
- Inactive Knowledge is excluded from search, exact-identity reuse and new usage reports. Historical usage summaries remain available.
- No review interval was invented. Time-based stale automation remains blocked pending Domain Owner policy.
- JWT validation now requires exp and explicitly uses leeway=0; JWT creation uses datetime.now(UTC).

### Verification
- Focused Knowledge/migration/JWT suite: **8 passed, 0 failed, 0 errors, 0 skipped**, exit 0.
- JWT tests prove future exp accepted; exp at boundary, expired exp, and missing exp rejected while DB session remains valid.
- Migration tests prove empty-schema lineage and populated-parent preservation.
- Alembic head: **e5a7c9d2f416**.
- Synthetic DBs upgraded and verified at e5a7c9d2f416: eims_browser_acceptance_20261115, eims_regression_test_20261115, eims_finalization_migration_20261115.
- Targeted Ruff F401/UP017: PASS; compileall: PASS; git diff --check: PASS (line-ending warnings only).

### PostgreSQL recovery rehearsal
- Added reproducible synthetic-only harness: tools/rehearse_postgres_pitr_synthetic.ps1.
- PostgreSQL 16 pg_basebackup (-X stream): PASS; pg_verifybackup: PASS; WAL segment archived: 000000010000000000000004.
- Named restore point eims_pitr_target restored successfully from the base backup.
- Restored probe rows were exactly before_backup,before_target; post-target transaction was excluded.
- Harness exit code 0; output %TEMP%\eims-pitr-rehearsal-20261115-v5.log.
- This is synthetic local-Docker PITR evidence only. It does not prove offsite durability, production retention, production failover, or measured RPO/RTO. Existing Homelab auto_backup.sh is a /data/docker tar archive, not PostgreSQL WAL/PITR.

### Acceptance boundaries and remaining gates
- Latest Browser Acceptance remains final16 33/33 and Playwright 2/2, but final16 predates the recent Knowledge usage UI form and the lifecycle API. No new full Browser Acceptance was run in this checkpoint; new lifecycle/JWT changes were covered by PostgreSQL integration tests.
- Gold queue still has 17 AI-authored DRAFT proposals (12 DEV, 5 HELDOUT), with no independent human review.
- Initial approved production Knowledge corpus remains insufficient; no synthetic incidents were promoted.
- External/offsite backup target, retention/encryption policy, BIA-approved RPO/RTO, failover and witnessed production-like recovery remain outstanding.
- Controlled Engineer pilot and operational ownership sign-off remain outstanding.

### Preservation
- Branch/HEAD unchanged: integration/eims-consolidated / 85493b2.
- No commit, push, reset, clean, stash, operational DB access, or destructive cleanup.
- Detailed snapshot: docs/engineering-memory/2026-11-15-finalization-lifecycle-jwt-pitr.md.


## 2026-11-15 — Knowledge UI, vendor candidate corpus and static event safety

### Knowledge Lifecycle Dashboard
- Added Admin-only revalidation queue and actions: revalidate/reactivate, supersede with replacement ID, withdraw.
- Added required lifecycle reason/reviewer note and Admin-only audit history.
- Engineer users do not see Admin lifecycle history/actions.
- Next.js production build after UI changes: compile PASS, TypeScript PASS, static pages 15/15, exit 0.
- No Browser Acceptance rerun after lifecycle UI changes; UI acceptance remains outstanding.

### Official vendor source candidates
- Added `docs/knowledge-source-candidates/official-vendor-candidates.v1.json` and README.
- 12 candidates across Microsoft (3), Broadcom VMware (3), Veeam (3), Fortinet (3).
- Each record includes product/version scope, applicability, prerequisites, evidence, limitations, validation, rollback and risk.
- All remain candidate-only / pending domain review. No candidate was imported as approved Knowledge or enabled for retrieval.

### Static Event Knowledge safety
- Added `tools/harden_static_event_knowledge.py`, dry-run by default and explicit `--apply`.
- 21 targeted event entries updated to evidence-first guidance; causes across all 39 entries are qualified as hypotheses.
- Hardened unsafe blanket actions: IP blocking/password reset, profile key deletion, global endpoint protection disable, repair-mode CHKDSK, registry/DCOM changes, cluster threshold changes, firmware/rebuild/replacement instructions and external upload of customer data.
- Corrected related high-risk operator context for operational catalog Events 4625, 7, 51, 55 and 98.

### Verification
- Candidate JSON, event knowledge JSON and operational event catalog JSON: valid.
- Focused tests: **53 passed, 0 failed**, exit 0.
- Targeted Ruff F401/UP017: PASS, exit 0.
- Python compileall: PASS, exit 0.
- Git diff --check: PASS, exit 0 (line-ending warnings only).

### Acceptance boundaries
- Vendor source candidates are not incident-backed approved Knowledge.
- No human reviewer was impersonated; no Gold cases were approved or frozen.
- No operational database was accessed or modified.
- External/offsite backup, BIA RPO/RTO, failover and witnessed restore remain open.
- Browser Acceptance for the new Lifecycle UI remains open.
- Branch/HEAD preservation continues: integration/eims-consolidated / 85493b2; no commit or push.

## 2026-11-15 — source-candidate corpus expanded against exact Gold fixture signatures

Research of the actual synthetic Gold input files (read-only; no annotation changes) showed exact signatures that were not covered by the initial 12-candidate source pack. Expanded the candidate corpus to **20** while preserving candidate-only status:

- Microsoft (5): Event 4625, Event 4740, Advanced Audit Policy, Event 1129 Group Policy network failure, Event 6005 EventLog service start/reboot correlation.
- Broadcom VMware (6): KB 450303, 324542, 309348, 442155 (CTK unlink/result 2620), 424591 (InvalidSnapshotFormat/missing snapshot file), 343510 (snapshot consolidation).
- Veeam (4): VBR 13 backup health check, SureBackup, backup verification, REST API session/task logs for generic Failed outcomes.
- Fortinet (5): event logs, debug flow, IPsec HA, traffic log ID 0000000013, config-object event ID 0100044547.

Exact fixture mapping:
- DEV Windows 1129 and 6005 have matching Microsoft references.
- DEV Veeam/ESXi CTK delete text maps to Broadcom KB 442155's CTK unlink/result 2620 pattern. The underlying evidence is a VMware/vSAN CTK file issue, not proof that Veeam itself is the root cause.
- HELDOUT ESXi InvalidSnapshotFormat / required-file-missing maps to Broadcom KB 424591; KB 343510 provides a broader consolidation diagnostic matrix.
- Fortinet logid 0000000013 is a forward traffic log ID; the action field distinguishes accepted/denied/session-close semantics. The log ID alone is not an allow/deny verdict.
- Fortinet 0100044547 is an object-attribute configuration event; inspect user/UI/action/cfgpath/cfgobj/cfgattr and approved change context. It does not prove unauthorized change.

All 20 records remain pending_domain_review and are not imported as approved Knowledge. The 17 Gold proposals remain DRAFT; the mapping does not validate Gold truth or authorize opening HELDOUT.

New sources:
- Microsoft Event 1129: https://learn.microsoft.com/en-us/troubleshoot/windows-server/group-policy/applying-group-policy-troubleshooting-guidance
- Microsoft reboot correlation/Event 6005: https://learn.microsoft.com/en-us/troubleshoot/windows-server/performance/troubleshoot-unexpected-reboots-system-event-logs
- Broadcom KB 442155: https://knowledge.broadcom.com/external/article/442155/snapshot-usage-on-esa-cluster-is-very-hi.html
- Broadcom KB 424591: https://knowledge.broadcom.com/external/article/424591/reverting-a-virtual-machine-snapshot-fai.html
- Broadcom KB 343510: https://knowledge.broadcom.com/external/article/343510
- Veeam VBR 13 REST API sessions/logs: https://helpcenter.veeam.com/references/vbr/13/rest/1.3-rev2/tag/Sessions/index.html
- Fortinet FortiOS 7.6.0 log fields: https://docs.fortinet.com/document/fortigate/7.6.0/fortios-log-message-reference/357866/log-message-fields
- Fortinet configuration object log IDs: https://community.fortinet.com/fortigate-3/technical-tip-difference-between-logid-0100044547-and-logid-0100044546-which-are-generated-when-configuration-is-changed-in-the-fortigate-203472

## 2026-11-15 — Operations readiness artifacts prepared

Added:
- `docs/operations/postgresql-offsite-backup-recovery-runbook.md`: failure-domain requirement, security controls, PostgreSQL base-backup/WAL architecture, acceptance checks, isolated PITR drill, failover/failback and evidence package.
- `docs/operations/eims-bia-rpo-rto-decision-record.md`: owner worksheet for business impact, data criticality, workload-specific RPO/RTO, dependencies, scenarios, measurement and approvals.

No external target/provider was selected, no production backup credentials were configured, and no operational backup was initiated. The runbook is prepared but external/offsite backup remains NOT IMPLEMENTED until Operations selects an independent target and approves encryption, retention, access and key recovery. RPO/RTO remain TBD until Business/Data/Operations Owners sign the BIA.

## 2026-11-15 — Database-backed Knowledge Source Catalogue

### Implemented
- Added separate `knowledge_source_candidates` and `knowledge_source_events` tables via Alembic `f3c8a1d6b902` (parent `e5a7c9d2f416`).
- Added ORM models, Admin-only source listing/filtering, review state transitions (verify reference, reject, require revalidation, withdraw), and append-only source audit history.
- Added Admin Dashboard catalogue view with vendor/product/version scope, applicability, prerequisites, evidence, limitations, next checks, validation, rollback, risk, official URL and SHA-256.
- Added dry-run-first, idempotent catalogue importer with source-hash change detection. Apply requires an explicit loopback synthetic PostgreSQL URL, exact database allowlist, `eims_test` user and non-operational port; application DATABASE_URL is never used.
- Added PostgreSQL integration test coverage for Admin-only source review and the invariant that a verified reference never becomes a KnowledgeEntry.
- Extended secure browser harness for Admin lifecycle revalidation/reactivation/audit/withdrawal and Engineer visibility isolation.
- Updated source-catalogue README, Engineering Memory index and this ledger.

### Verification
- Candidate catalogue dry-run: 20 candidates, 4 vendor families.
- Python compile: PASS.
- Targeted Ruff `F401,F841,E402`: PASS on changed implementation and test files.
- Alembic offline SQL generation through `f3c8a1d6b902`: PASS.
- Dashboard production build: PASS; TypeScript passed; Static Generation 15/15.
- Focused tests: 10 passed; 2 PostgreSQL integration/migration tests skipped because no explicit `EIMS_TEST_DATABASE_URL` was configured.
- Browser harness syntax check: PASS.

### Boundaries / pending
- Migration not applied to any existing database in this run.
- Catalogue not imported into a database in this run.
- PostgreSQL API integration and full migration-lineage test remain unexecuted (missing explicit synthetic test DB URL).
- Browser Acceptance not run (synthetic browser base URL, login credential and DB URL were not configured).
- No operational database, production backup, or customer data accessed.
- `verified_reference` is not incident proof or approved remediation; only approved active KnowledgeEntry records remain eligible for exact-identity retrieval.

### Next gate
Provision an explicitly allowlisted synthetic PostgreSQL target, apply the migration there, import the 20 candidates, verify row/hash/audit counts, and run Admin/Engineer Browser Acceptance using separate synthetic accounts. Production rollout remains subject to the organization's migration and change-management process.



## 2026-11-15 — Reviewer Capability / Source Provenance Correction

### Implemented in Repository

- Added additive `users.knowledge_reviewer` capability via Alembic revision `a4b7c9d2e601` (parent `f3c8a1d6b902`).
- Added `require_knowledge_reviewer`; legacy Admin accounts remain reviewers for compatibility, while ordinary Engineer accounts can be granted the capability.
- Added capability information to `/auth/session`; Admin user API can create or update a reviewer-capable account.
- Knowledge approval, Source review and Lifecycle mutation now require Reviewer capability rather than Admin role.
- Authenticated Engineers can read/search Source Catalogue and inspect Source/Lifecycle event histories.
- Existing proposer != reviewer rule remains enforced.
- Dashboard now bases reviewer controls on the session capability. The source catalogue is a read-only Engineer surface.
- API/Dashboard label the stored fingerprint as Catalogue Record SHA-256. It hashes canonical catalogue JSON, not current Vendor webpage/document bytes.
- Settings page is explicitly marked preview-only; its non-persistent Save action is disabled rather than showing false success.

### Verification

- Python compile: PASS.
- Targeted Ruff F401/F841/E402: PASS.
- Focused tests: 14 passed.
- Alembic heads: one head, `a4b7c9d2e601`.
- Dashboard production build: PASS; TypeScript and 15/15 static pages.
- Browser harness syntax: PASS.
- PostgreSQL integration tests: NOT RUN; `EIMS_TEST_DATABASE_URL` absent.
- Migration `a4b7c9d2e601`: NOT APPLIED to any DB.
- 20 Source Candidates: NOT IMPORTED into any DB.
- Browser Acceptance: NOT RUN for this code version; test URL and credentials absent. Prior final16 33/33 is historical evidence only.

### Remaining Gates

1. Provision an explicitly authorized synthetic DB URL; apply migration and import candidates.
2. Run PostgreSQL capability/API integration tests.
3. Run current Browser Acceptance for Reviewer and Engineer surfaces.
4. Domain-review all 20 Vendor candidates and 17 DEV/HELDOUT fixtures.
5. Complete witnessed offsite restore and owner-approved RPO/RTO.
6. Run Engineer pilot with incident provenance and independent validation evidence.

No operational DB access, commit, push, reset, clean or stash was performed in this work segment.


## 2026-11-15 — AI Tooling Inventory and New-Chat Continuity

### Added
- `AI_TOOLING_INVENTORY.md`: machine-backed AI client inventory, 15 live Claude MCP connections, auth-required/failed/not-configured MCP endpoints, Codex/OpenCode/Gemini/Antigravity config discrepancies, historical EIMS role assignments, safety boundaries, and refresh procedure.
- `docs/engineering-memory/NEW_CHAT_CONTINUATION_PROMPT.md`: reusable complete startup prompt for new ChatGPT conversations.
- Root `CLAUDE.md` and `GEMINI.md`: lightweight client-specific pointers to canonical `AGENTS.md`, tooling inventory, and handoff. They intentionally avoid duplicating full project rules.
- Updated `AGENTS.md`, `docs/engineering-memory/INDEX.md`, and `EIMS_OPERATIONAL_HANDOFF.md` to make these artifacts mandatory continuity sources.

### Verification evidence
- Claude Code 2.1.323; `claude mcp list` live status: 15 CONNECTED services; separate auth-required, failed, and unconfigured states recorded in inventory.
- Codex config: `node_repl` and FableCut entries; Codex command unavailable in inspected PATH, therefore not live-verified.
- OpenCode 2.3.0: FableCut/Browse present in `opencode.jsonc`; live `opencode mcp list` reported no configured servers. Discrepancy recorded, not silently reconciled.
- Gemini/Antigravity MCP config files inspected and empty; Gemini CLI not found in inspected PATH.
- Cursor 3.30.14 and EIMS project rules verified; 33 Claude EIMS session files present.
- No credentials were copied into documentation. No code, DB, container, or operational service was changed.
- Git verification after edits and `git diff --check` remain to be completed before this documentation task is closed.


## 2026-11-16 — Reviewer capability audit and non-superuser PostgreSQL acceptance

### Implementation delta
- Reused existing `audit_logs`; no new audit subsystem or schema migration.
- Grant/revoke of `knowledge:review` records `GRANT_KNOWLEDGE_REVIEWER` / `REVOKE_KNOWLEDGE_REVIEWER` with actor username, target user ID/name, previous/new state and capability.
- Capability update and audit row are committed atomically; target user row is locked for concurrent state transitions.
- Repeated no-op update produces no duplicate event.
- Account creation with Reviewer capability records a create-time grant event.
- Legacy Admin accounts retain implicit review capability; attempted revoke returns 409.
- Regression test covers all of the above.

### Accepted PostgreSQL evidence
- Disposable container: `eims-reviewer-source-nonsuper-pg-20261116`, port 56446, DB `eims_integration_test`.
- Role `eims_test`: verified NOSUPERUSER / NOCREATEDB / NOCREATEROLE.
- Alembic head: `a4b7c9d2e601`.
- Importer: 20 created, 0 updated, 0 unchanged.
- DB counts: 20 source candidates, 20 `catalogue_imported` events, 0 KnowledgeEntry rows.
- Focused PostgreSQL suite: **5 passed, 0 failed, 0 errors, 0 skipped**, exit 0.
- JUnit: `test-results/reviewer-source-nonsuper-postgres-20261116.xml`.
- Python compile, targeted Ruff F401/F841/E402 and `git diff --check`: PASS. Diff check only reports line-ending conversion warnings.
- Browser config guard: 5 invalid configurations rejected, exit 0; not a browser acceptance result.

### Browser Acceptance status
**BLOCKED / NOT RUN for this checkpoint.** HTTPS 3449 currently serves EIMS Core Gateway, not the isolated analyzer test harness; the harness-only diagnostics endpoint is unavailable. No synthetic login or test mutation was sent to this gateway. A separate trusted-HTTPS isolated browser stack is required.

### Evidence caveats
- An earlier disposable container was initialized with `POSTGRES_USER=eims_test`, making that role a superuser. Its run was discarded as least-privilege acceptance evidence. It was not cleaned up or modified further.
- The accepted run used a separate container with a postgres bootstrap administrator only for disposable role/database/extension provisioning. Migration, importer and tests ran as the verified non-superuser `eims_test`.
- Claude Code read-only review returned no content; independent review is still outstanding.
- No human Domain Review was performed. All 20 imported candidates remain pending review; all 17 Gold cases remain DRAFT.

### Next critical gates
1. Isolated trusted-HTTPS Browser Acceptance for Engineer-readable catalogue and Reviewer actions.
2. Human Domain Review for source candidates and Gold cases.
3. External/offsite backup + witnessed restore + owner-approved RPO/RTO.
4. Controlled Engineer pilot and incident resolution outcome evidence.

Branch/HEAD unchanged: `integration/eims-consolidated` / `85493b2131d3e353453072559a5dfc301d75dd06`. Worktree count after this snapshot 161. No commit/push/reset/clean/stash/rebase and no Operational DB access.


## 2026-11-16 — Incident Core v1 (backend-only)

### Implemented in Repository
- Added `backend/domain/incident/` with `models.py`, `schemas.py`, `correlation.py`, `service.py`, `controller.py`, `__init__.py`.
- Schema revision `b8d3f5c1a720` (parent `a4b7c9d2e601`, single head) adds `incidents`, `incident_evidence` and nullable `analysis_history.asset_id` (FK RESTRICT, indexed). No backfill and no guessed identity.
- Evidence is reference-only: `(source_type, source_id)` unique plus SHA-256 digest; no source payload is copied into the incident domain.
- Correlation is pure and deterministic: strong/medium/weak/none with a 900 s default window, 2x expanded weak window and a SHA-256 `dedupe_key` of `asset-or-unresolved:signature:window_bucket`. Different concrete asset ids never merge. `root_cause_state` remains `unknown`.
- Service commits incident + evidence + audit atomically, upserts by `dedupe_key`, is idempotent on evidence identity and recovers from `IntegrityError` under concurrency.
- Lifecycle: `open -> triage -> investigating -> resolved -> closed`, plus `resolved -> investigating` reopen; all other edges rejected.
- API: `GET/POST /api/v1/incidents`, `GET /api/v1/incidents/{id}`, `POST/GET /api/v1/incidents/{id}/evidence`, `PATCH /api/v1/incidents/{id}/status`. Reads require authentication; writes require an authenticated Engineer; close requires `require_knowledge_reviewer`.
- Audit reuses `audit_logs` with `INCIDENT_CREATED`, `INCIDENT_EVIDENCE_ADDED`, `INCIDENT_STATUS_CHANGED` and `incident_id` inside `immutable_payload`. No new audit table.
- No dashboard/UI and no automatic closure, remediation or AI root cause.

### Accepted Disposable PostgreSQL Evidence
- Container `eims-incident-core-pg-20261116`, image `pgvector/pgvector:pg16`, loopback port 56448.
- Database `eims_incident_test`; role `eims_incident_test` verified `rolsuper=false`, `rolcreatedb=false`, `rolcreaterole=false`.
- Ephemeral password generated in-process and passed only via environment variables; no credential stored in a file, artifact or document.
- Bootstrap `postgres` provisioned only the role/database and preinstalled `vector`/`pg_trgm`. Alembic and tests ran as the non-superuser role.
- Alembic `upgrade head` completed as that role; `alembic current` = `b8d3f5c1a720 (head)`; `alembic heads` = one head.
- Migration test proves empty-schema upgrade, populated parent upgrade preserving rows with `asset_id` NULL, safe downgrade/re-upgrade, unique/FK/check behavior and asset `RESTRICT` plus evidence `CASCADE`.

### Verification
- Incident suite: **60 passed, 0 failed, 0 errors, 0 skipped**, exit 0.
- JUnit: `test-results/incident-core-20261116.xml`.
- Focused regressions (`tests/test_timeline.py` plus analyzer unit tests): **261 passed, 0 failed, 0 errors, 1 skipped**, exit 0.
- JUnit: `test-results/incident-core-regressions-20261116.xml`.
- Skip reason: existing `test_analyzer_evaluation.py` Windows-host symlink limitation, unrelated to Incident Core.
- Python compile: PASS for changed/new files. Ruff F401/F841/E402: PASS for new files; modified `backend/main.py`/`migrations/env.py` only retain pre-existing findings.
- `git diff --check`: exit 0, line-ending warnings only.
- Branch/HEAD unchanged: `integration/eims-consolidated` / `85493b2131d3e353453072559a5dfc301d75dd06`. Worktree after this snapshot: 126 entries (57 modified preserved, 69 untracked).

### Boundaries / pending
- Browser Acceptance: NOT RUN; this deliverable is backend-only and no browser claim is made.
- Independent review, human acceptance of correlation semantics and Operational DB rollout remain outstanding.
- No Operational DB/Redis/MinIO access, commit, push, reset, clean, checkout, stash or rebase. Containers were not deleted.

## 2026-11-16 - DWB orchestration + Incident Core review fixes

- DWB agent orchestration accepted at the code/test level: registry verification, local single-use approval with complete prompt preview, role/scope enforcement, single-writer locks, cancellation/timeout/orphan recovery, sensitive-output withholding, per-project jobs/artifacts (22/22 synthetic checks).
- Real read-only smoke: Claude Code 2.1.323 and OpenCode 2.3.0 succeeded; Codex BLOCKED (no CLI).
- Incident Core review fixes: terminal incidents excluded from candidates; recurrence uses a per-bucket dedupe key; terminal incidents reject new evidence; recovery never merges into closed incidents. Incident suite 61/61; regressions 261 passed, 1 skipped.
- Independent read-only review (Claude Code) final result: no high-severity findings; two low recurrence/race edges documented.
- ChatGPT plugin catalog refresh remains a UI step; local MCP discovery shows 14 tools.
## 2026-11-16 - EIMS Auto Job Relay (Chat_HAND V6)

### Scope
- Chat_HAND only: `gateway/lib/job-store.mjs`, `gateway/lib/job-monitor.mjs`, `gateway/lib/agent-runner.mjs`, `gateway/control-plane.mjs`, `gateway/policy.json`, tests, docs, evidence.
- No EIMS application code, no Incident Core change, no database, Redis or MinIO access.

### Capability
- Detached execution: the runner owns the agent and writes stdout/stderr straight to files, so MCP restarts adopt instead of destroy.
- Durable store: atomic job records, split artifacts with per-stream SHA-256, separate result envelopes and a delivery ledger (collected / retrieved / acknowledged).
- Background monitor: bounded 1 s scan, exit-metadata finalization, restart adoption, 5-minute reconcile window, identity-checked interruption with three deferrals.
- Delivery tools: `jobs.list`, `jobs.wait` (default 30 s, hard max 40 s, optional), `jobs.get_result`, `jobs.ack_result`. Surface is 18 tools.

### Verification
- `node scripts/test-job-relay.mjs`: **25 passed, 0 failed**, exit 0 (`evidence/v6-job-relay-acceptance.json`).
- `node scripts/test-orchestration.mjs`: **22 passed, 0 failed**, exit 0 (`evidence/v5-orchestration-acceptance.json`).
- `node scripts/test-control-plane.mjs`: **40 passed, 0 failed, 1 not tested**, exit 0 (`evidence/v4-control-plane-acceptance.json`).
- `node scripts/Smoke-EimsAgentRelay.mjs`: **7 passed, 0 failed** (`evidence/v6-real-relay-e2e.json`): approved read-only Claude Code job; `jobs.wait` returned `still_running` at the 40 s bound; `jobs.get_result` retrieved the completed result, exit 0, 231 bytes, `sha256 1cdff417…`; acknowledged; worktree unchanged. Archived OpenCode run records a provider-credit failure correctly (exit 1, stderr retrievable).
- Independent read-only review: 3 rounds, final verdict NO HIGH-SEVERITY FINDINGS (`evidence/v6-review.json`).

### Boundaries / pending
- Unsolicited ChatGPT message injection is not supported; delivery is on demand. Scheduled-task cadence is unverified.
- Machine-restart survival is not claimed; such jobs are `interrupted`.
- Real writer-mode acceptance through the relay is not claimed.
- Browser Acceptance NOT RUN. No commit, push, reset, clean, checkout, stash or rebase; 57 modified EIMS files preserved.

## 2026-11-16 - Incident Core v1.1 event-to-incident ingestion (IMPLEMENTED, NOT VERIFIED)

| Item | Status | Evidence |
|---|---|---|
| Source implementation (outbox model, migration `c4e8a1f7b932`, emitters, dispatcher, consumer, lifespan) | WRITTEN | file list in `docs/engineering-memory/2026-11-16-incident-core-v11-ingestion-implementation.md` |
| Migration chain / single head (static file inspection) | head `c4e8a1f7b932`, parent `b8d3f5c1a720` | read from `migrations/versions/*.py`; no DB queried |
| `git diff --check` | PASS (exit 0; CRLF warnings only) | command output |
| Unit tests `tests/test_incident_ingest_unit.py` | NOT RUN | interpreter execution required unavailable approval |
| Existing focused regressions (`test_telemetry_reliability_fixes`, `test_telemetry_outbox_and_db_unavailable`, `test_sprint13_evidence_ingestion`, `test_incident_migration` head constants) | NOT RUN | same |
| Disposable PostgreSQL + Redis integration (atomicity, RETURNING replay, dispatch/ACK crash windows, outage, DLQ cap, lease refresh, isolation, NULL key/asset, races) | NOT RUN | containers NOT CREATED (`docker run` refused) |
| Migration empty/populated upgrade, downgrade/re-upgrade, non-superuser | NOT RUN | same |
| Python compile / ruff | NOT RUN | same |
| Independent read-only review of the exact diff | OPEN | no distinct reviewer executed |

No PASS is claimed for any v1.1 behaviour. Writer mode: this task wrote files through the approved path, but acceptance of writer mode additionally requires the independent review. Browser Acceptance NOT RUN. No Operational DB/Redis/MinIO access; no commit, push, reset, clean, checkout, stash or rebase.

## 2026-11-16 - Incident Ingestion v1.1 acceptance

- Verdict: **COMPLETE** (code, unit, migration, isolated PostgreSQL/Redis integration, independent review ACCEPTED). No commit, push, deployment or operational-service access.
- Branch `integration/eims-consolidated` @ `85493b2`; migration `c4e8a1f7b932` (parent `b8d3f5c1a720`, single head).
- Files changed by this task: `backend/domain/incident_ingest/{models,outbox,consumer}.py` (fixes + wording), `tests/test_incident_ingest_unit.py`, `tests/test_incident_ingest_v11_recovery_unit.py` (stubs + 2 new tests), `tests/test_incident_ingest_migration.py` (asset insert columns), plus append-only documentation.
- Tests: **113 passed / 0 failed / 0 skipped**, exit 0, 28.6 s; focused unit **95 passed**; correlation regression PASS; `git diff --check` exit 0.
- Isolation: new containers `eims-ingest-v11-pg-20261116c` / `eims-ingest-v11-redis-20261116c`; role NONSUPERUSER verified; DB comment + Redis sentinel verified before any write; credentials via environment only.
- Review: Claude Code read-only, 3 rounds; round 1 no HIGH + 2 MEDIUM, round 2 NOT ACCEPTED (missing tests), round 3 **ACCEPTED**.
- Deferred with reasons: XAUTOCLAIM attempt counting, log/drain backpressure, F8 offline dedupe race, F10 asset FK retention.
- Prerequisite: apply `c4e8a1f7b932` before deploying outbox-writing code.

## 2026-11-17 - Model routing + Agent Monitor TUI

- Group A (Chat_HAND): **COMPLETE**, independent review **ACCEPTED** (round 2). Routing manifest + fail-closed argv check; writer model pinned; preflight 17 checks PASS; live smoke PASS (both roles); routing 17/17, orchestration 22/22, relay 25/25, control plane 40 pass + 1 not tested.
- Group B (EIMS): **COMPLETE**, independent review **ACCEPTED** (round 3). `-Dashboard` TUI on the existing data layer; 96 assertions pass on Windows PowerShell 5.1; empty-root and real-root plain-mode runs verified.
- Root causes closed: unpinned OpenCode writer model (job `2656de34`); dashboard crashed with zero jobs; rounded hours; bare folder reported as Running; unbounded tail reads; control/ANSI leakage; frame overflow.
- Deferred/documented: PEM body masking header-only, classic `-Watch` squashed tail lines, optional live smoke cost.
- No commit/push/deploy; no operational service access; `scripts/agent-monitor/` untracked and preserved.

## 2026-11-19 - Portal Correction (Cursor workstream A)

- Verdict: **ACCEPTED WITH LIMITATIONS**. Evidence: `docs/acceptance/PORTAL_CORRECTION_ACCEPTANCE.md`.
- Branch `demo/2026-11-24` @ `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de` (pre-existing dirty tree preserved; no commit/push).
- Focused pytest: `tests/test_timeline.py` + `tests/test_timeline_portal_correction.py` ? **15 passed**, exit 0.
- Browser: Next portal on `localhost:3001` � Settings read-only Runtime Configuration (no Gemini/Save inputs), nav hides Client Agents / Knowledge / Sticker OCR, USB Auditor reachable. Backend `:8000` was not running; live health/timeline event proof deferred (Operational DB not used).
- Missing contracts documented: database identity + recovery/replica for Settings; correlation_id on timeline sources.
- Knowledge Foundation / migrations / Incident Core rules untouched.

## 2026-11-19 - Portal Correction runtime close-out

- Verdict: **ACCEPTED WITH LIMITATIONS**. Full evidence: `docs/acceptance/PORTAL_CORRECTION_ACCEPTANCE.md`.
- Disposable PG only: container `eims-portal-accept-pg-20261119`, `127.0.0.1:56456`, db/role `eims_portal_accept`, comment `EIMS-DISPOSABLE-portal-accept-20261119`. Operational `:5432/:6432` unused.
- Alembic `upgrade head` ? `a1c4e7b9d201`; focused pytest timeline suites **15 passed** exit 0.
- Backend `127.0.0.1:8000` soft-deps: health HTTP 503 DEGRADED (PG UP, Redis/MinIO DOWN); ready HTTP 200 `database:true`.
- Timeline API real rows + pagination `limit=2`; browser Portal `localhost:3001` Settings/Timeline/Home/USB verified. Home cards no longer link Client Agents/OCR.
- No Knowledge Foundation edits; no commit/push; secrets not written to repo.

## 2026-11-19 - Analyzer UX + open-access (no application login)

- Verdict: **ACCEPTED WITH LIMITATIONS**. Evidence: `docs/acceptance/ANALYZER_UX_AND_WEBSITE_COPY_ACCEPTANCE.md`.
- Application login removed at FastAPI `get_current_user` / `require_admin_or_token` (open-access identity); `/api/v1/auth/login` and BFF session login return 410.
- Analyzer login/session UI removed; product name **Log Analyzer**; home/nav copy updated.
- Pytest: `test_auth_modes` + `test_analyzer_open_access_ui` (+ timeline portal subset earlier) **passed**.
- Knowledge Foundation migrations/schema not modified. No Operational DB. No commit/push.

## 2026-11-20 - UX Correction + Evidence Presentation (Cursor)

- Verdict: **ACCEPTED WITH LIMITATIONS**. Evidence: `docs/acceptance/2026-11-20-ux-evidence-integrity-cursor.md`.
- Incident X returns to Incident list landing; Incident Workspace tab stays selected; URL clears `?incident=`.
- Settings: Theme preference + Runtime Health link only.
- Evidence UI: display-only duplicate collapse; chronology honesty; excerpt/offset labels (not fabricated file lines).
- Knowledge expansion + evidence pipeline root cause: Claude handoff `docs/acceptance/2026-11-20-claude-handoff-knowledge-evidence.md`.
- `npx tsc --noEmit` PASS. No commit/push. No Operational DB. HEAD remains `3f2beea`.

## 2026-11-20 - Automatic Incident Intelligence (Cursor frontend)

- Verdict: **ACCEPTED WITH LIMITATIONS**. Evidence: `docs/acceptance/2026-11-20-automatic-incident-intelligence-cursor.md`.
- FE uses existing `GET /by-evidence` + `POST /incidents` (`create_from_evidence`); no invented API; no frontend-only dedupe.
- Browser `:3001`: analyze Event 1026 ? automatic association ? Review Incident Workspace (`analysis:156` / incident `58a8c0b1-�`).
- Engineer Notes: gap only (Claude contract in `docs/acceptance/2026-11-20-automatic-incident-backend-gaps-claude.md`).
- `check-incident-orchestration.mjs` PASS; `tsc --noEmit` PASS. No commit/push. No backend edits.

## 2026-11-20 - Cursor parallel FE (Acceptance + Integration Readiness)

- Verdict: **ACCEPTED WITH LIMITATIONS**. Evidence: `docs/acceptance/2026-11-20-cursor-parallel-frontend-acceptance.md`; handoff `docs/acceptance/2026-11-20-cursor-backend-integration-readiness.md`.
- Removed unsafe FE evidence text-collapse; chronology gated on timestamps; auto-open Workspace only on clear association outcomes; Notes integration stub `EngineerNotes.tsx` (apiEnabled=false).
- `check-incident-orchestration.mjs` PASS; `tsc --noEmit` PASS. Browser re-run blocked (Portal/API down). No backend edits. No commit/push. HEAD `3f2beea`.

## 2026-11-20 - Frontend Integration Closure (Cursor)

- Verdict: **ACCEPTED WITH LIMITATIONS**. Evidence: `docs/acceptance/2026-11-20-cursor-frontend-integration-closure.md`.
- Disposable browser on Portal `:3001` + API `:8021` (PG `eims-portal-accept` / `:56456`); did not use `start_eims.bat` or Operational DB.
- Event 1026 Analyze -> incident `48eb0b9d-...`; already_linked on re-open; Workspace partial-load when diagnoses/etc return 500.
- Catalog runtime `total_records=175`; Notes `apiEnabled=false` (runtime 404); ambiguous match browser blocked.
- `tsc --noEmit` PASS; orchestration + evidence scripts PASS. No backend edits by Cursor. No commit/push. HEAD `3f2beea`.

## 2026-11-20 - Incident Notes Integration (Cursor)

- Verdict: **ACCEPTED WITH LIMITATIONS**. Evidence: `docs/acceptance/2026-11-20-cursor-incident-notes-integration.md`.
- Wired `EngineerNotes` to real `GET/POST /api/v1/incidents/{id}/notes` against Claude disposable `56470/eims_e2e_test` (alembic `a7d2c5e8f604`) via API `:8022` + Portal `:3001`.
- Browser: add note + reload persistence; unattributed actor/assurance; Workspace lifecycle panels populate; catalog 175.
- Ambiguous auto-open still mapping-proven only (no live browser ambiguous response this pass).
- `tsc` + orchestration/evidence/notes scripts PASS. No backend edits. No commit/push. HEAD `3f2beea`.

## 2026-11-20 - Analysis / Incident Workspace / USB UX (Cursor)

- Verdicts: WS1 Analyze journey **ACCEPTED**; WS2 Incident Workspace IA **ACCEPTED WITH LIMITATIONS**; WS3 USB remove **ACCEPTED WITH LIMITATIONS**. Evidence: `docs/acceptance/2026-11-20-cursor-analysis-incident-usb-ux-closure.md`.
- Analyze no longer auto-opens Incident Workspace; association stays background; explicit Review CTA. Event 41 fact vs diagnostic-possibility labels corrected.
- Workspace IA: Overview → Evidence & Timeline → Notes → Findings → … with honest empty states.
- USB Remove by `asset_id` + confirm; soft-archive only when Core Law 3 allows Decommissioned; Discovered e2e hosts blocked — Claude handoff. Redis 503 not weakened on FE.
- Runtime: API `:8022` / PG `56470/eims_e2e_test` / Portal `:3001`. Scripts orchestration+evidence+notes EXIT 0. No commit/push. HEAD `3f2beea`.

## 2026-11-20 - Final Full Browser E2E Acceptance (Cursor)

- Verdict: **ACCEPTED WITH LIMITATIONS**. Product Acceptance **NOT claimed**. Evidence: `docs/acceptance/2026-11-20-final-browser-e2e-acceptance.md`; artifacts `docs/acceptance/evidence/browser-e2e-2026-11-20/`.
- Integrated runtime: Portal `:3001` → API `:8031` → disposable PG `56470/eims_cursor_accept` (role `eims_incident_test`, Alembic head `c9f4a7b0d826`).
- Browser PASS: Analyze stays on Details; association background; ambiguous UI with candidates (no auto-open); Workspace IA; Notes `demo/unattributed` survive hard API restart; Knowledge catalog 175 / 0 approved; USB remove-by-`asset_id` honest Discovered block; resolve as open-access → 403.
- FE fix this pass: optional `asset_id` on ensure via `?asset=` (never invent from hostname). Scripts orchestration/evidence/notes EXIT 0. No commit/push. HEAD `3f2beea`.

## 2026-11-22 - Unified Knowledge Catalog delivery pass (Cursor)

- Verdict: **PARTIAL / delivery-ready for catalog contract**. Package: `docs/acceptance/certification/final_delivery_2026-11-24/`.
- Identity proven: 911 governed, 181 Analyzer-matchable strict subset, 730 other, Class B 39 = 28 matchable + 11 not in load_catalog; eligibility 1/42/868; human-approved 0. Evidence JSON + `GET /api/v1/knowledge/catalog/identity-evidence`.
- Implemented unified projection API + Portal Knowledge Catalog KPIs/facets. Focused pytest **5 passed** (exit 0). Full suite / live browser re-acceptance **NOT re-run**. PPTX ready; slide PDF **NOT VERIFIED** (no soffice).
- Gates unchanged: Engineering PASS (inherited), Human Certification NOT RUN, Production PARTIAL. No commit/push. HEAD `3f2beea`.

## 2026-11-22 - Unified Catalog browser closure (Cursor)

- Catalog UI browser **PASS** against live Portal `:3001` + restarted API `:8031` (disposable `eims_cursor_accept`). KPI 911/181/730, Class B 39, Eligible 1, Human-approved 0; ASA 113005 on Eligible facet.
- Evidence: `docs/acceptance/certification/final_delivery_2026-11-24/05_BROWSER_VERIFICATION.md` + `evidence/`. Focused unified tests re-check **3 passed**. Product Acceptance still **not claimed**. No commit/push. HEAD `3f2beea`.

## 2026-11-22 - Engineering closure (Catalog closed; knowledge quality audit)

- Unified Catalog delivery **closed** (no identity rebuild). Live totals 911/181/730; labels All Analyzer products (181); tests 4 passed; label script OK.
- Knowledge quality audit: engineer-ready partial **77/911**, full verify chain **19/911** (`tools/audit_knowledge_quality.py` ? `final_delivery_2026-11-24/evidence/knowledge_quality_audit.json`).
- Investigation gap: Verify/human reviewer path **NOT RUN**; Product Acceptance **not claimed**; Production **PARTIAL**. Closure report: `07_ENGINEERING_CLOSURE_REPORT.md`. No commit/push. HEAD `3f2beea`.

## 2026-11-22 - Report evidence register + presentation export

- Re-verified against HEAD `3f2beea` working tree: catalog 911/181/730, Class B 39, Eligible 1, HA 0, quality 77/911 & 19/911; unified tests 4 passed; live API match.
- Evidence Register: `docs/acceptance/certification/final_delivery_2026-11-24/08_REPORT_EVIDENCE_REGISTER.md`. PPTX rebuilt; PDF exported `02_EIMS_Presentation.pdf`. Canva MCP auth rejected � change plan only. DOCX not edited. No commit/push.
