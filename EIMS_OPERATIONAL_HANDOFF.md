# EIMS Operational Handoff

Last updated: 2026-11-16 — Reviewer audit and non-superuser PostgreSQL acceptance
Machine: Mew (Windows 11)
Repository: `C:\Users\MewMew\Desktop\Co-op\EIMS`
Branch: `integration/eims-consolidated`
HEAD: `85493b2131d3e353453072559a5dfc301d75dd06`

## 1. Project identity and architecture
EIMS is an academic prototype / engineering platform for infrastructure discovery and asset registry, hardware inventory, OCR registration, Windows Event Log / EVTX ingestion and diagnostics, telemetry, compliance analysis, Analyzer / EventIQ, service evaluation, and operational dashboard.

Architecture documented in README:
- Hybrid modular monolith with asynchronous event-driven ingestion.
- Windows / discovery agents send mTLS telemetry to FastAPI.
- Redis Streams decouple ingestion from workers.
- Workers persist telemetry / event evidence in PostgreSQL (with PgBouncer in the documented runtime architecture).
- MinIO stores object evidence such as uploaded EVTX/OCR objects.
- Next.js dashboard calls FastAPI and presents operational views.
- Analyzer uses PostgreSQL plus pgvector knowledge / retrieval structures.
- Dashboard has Demo and Secure authentication modes; Secure mode requires JWT and admin authorization for privileged writes.

Treat README as an architectural starting point, not proof of production readiness. Its Project Status section still describes the Oct 31 / PR #10 state and needs later reconciliation.

## 2. Historical decisions V4-V6
- Preserve existing operational and demo data; no destructive benchmark or migration rehearsal against Operational DB.
- Use synthetic/public fixtures for acceptance; do not use customer data.
- EVTX pipeline acceptance must cover real binary upload -> MinIO -> Redis -> EVTX worker -> telemetry worker -> PostgreSQL -> replay after ACK failure, with no duplicate persistence.
- Telemetry consumers must maintain leases during long processing; lease refresh must not increment delivery count.
- Outbox delivery is At-least-once, not Exactly-once. Downstream consumers must deduplicate by alert_id.
- Migrations using CREATE/DROP INDEX CONCURRENTLY require Alembic autocommit handling and must not be wrapped by an external transaction in a rehearsal harness.
- Disposable PostgreSQL, Redis, MinIO must be isolated from operational ports and explicitly configured via EIMS_TEST_*.
- SKIP is not PASS. Every acceptance result needs a test report and environment identity.
- Use targeted inspection, parallel independent delegation, compact reports, focused tests before full regression, one evidence ledger, and handoff before context exhaustion.
- One writer per file group; reviewers read-only unless explicitly assigned.
- Never commit/push, clean/reset, delete existing modified/untracked files, or touch Operational DB without explicit authorization.

## 3. Current Git state (verified 2026-11-14)
- Branch: integration/eims-consolidated
- HEAD: 85493b2131d3e353453072559a5dfc301d75dd06
- Latest verified status: 51 modified tracked paths, 44 untracked paths, 95 total status entries. Many are pre-existing EIMS work; preserve all and do not infer disposability.
- `git diff --check` passed (line-ending warnings only).
- No commit/push was performed.
- Preserve all existing Modified and Untracked paths. Do not infer which untracked files are disposable.

## 4. Completed work and current evidence
- Project venv is `venv\Scripts\python.exe`, Python 3.14.3; Alembic and pytest are installed.
- Alembic has one head: a3d6f1e8c295.
- Migration chain: e1a202610250 -> e4a9c8b12d77 -> f7b3d91c4a58 -> a3d6f1e8c295.
- Disposable DB migration upgrade from empty schema passed. Active rehearsal schema: eims_full_lineage_4ee389da31e64a669eda8532c250f9fb.
- Verified indexes: uq_telemetry_metrics_source_event_key, uq_windows_event_logs_source_event_key, idx_winlog_4625_src_ip_time, idx_telemetry_alert_outbox_pending.
- EVTX E2E, Telemetry lease refresh, and Outbox concurrency: 3/3 JUnit PASS.
- Redis + MinIO restart recovery: 1/1 JUnit PASS.
- Disposable services currently running:
  - PostgreSQL container eims-evtx-e2e-pg-20261114 on 56441 (healthy)
  - Redis container eims-evtx-e2e-redis-20261114 on 56379 (healthy)
  - MinIO container eims-evtx-e2e-minio-20261114 on 59000 (ready endpoint HTTP 200)
- The disposable DB needed pgvector and pg_trgm extension schema placement corrected to public. This was done only in the disposable DB.
- Historical V6 report: 45 focused worker/security-related tests and other earlier regressions passed; treat as historical, not as current run proof.

## 5. Acceptance ledger
The single source of truth is `EIMS_ACCEPTANCE_LEDGER.md` in this repository. Update it after each test batch with exact JUnit counts, exit code, environment, and artifact path. Never mark SKIP/incomplete as PASS.

## 6. Agent assignment
- Cursor/Grok: sole implementation writer for a specifically assigned source-file group.
- OpenCode: independent read-only review of diffs, migration correctness, failure modes.
- Claude Code Safe Mode: test coverage and reliability review; do not rely on normal mode until its stdin/startup issue is resolved.
- Antigravity IDE: read-only architecture review. Keep Antigravity Standalone distinct from Antigravity IDE.
- ChatGPT / technical lead: sequencing, targeted inspections, evidence verification, ledger/handoff maintenance.
- Do not wait on unavailable agents; no parallel writers on the same files.

## 7. Outstanding risks / blockers
1. A 13-file reliability test batch is not complete: 31 dots were emitted, but the pytest process tree remained alive and no JUnit XML was produced. Two Python processes were observed for that invocation. Inspect exact process/test before any rerun; avoid blind process termination.
2. Browser E2E: no service listening on port 3449 during inspection. The config guard test passed, but the full browser test failed during setup because EIMS_TEST_BROWSER_BASE_URL was absent. A real synthetic EIMS_TEST_LOGIN_CREDENTIAL is required; do not fabricate it.
3. README Project Status is stale and says external gates remain, based on Oct 31 state. Reconcile with actual current state only after gates are closed.
4. Downgrade/upgrade round-trip and interrupted concurrent-index retry still require explicit evidence.
5. Production database operations are not yet accepted: backup/restore, PITR, retention, capacity/load, failover, alerting, and recovery objectives have not been established in this turn.
6. Do not conflate disposable acceptance success with operational DB safety or production readiness.

## 8. Immediate next actions
1. Inspect the active pytest process tree for the reliability batch and identify the stalled test. Do not launch a duplicate.
2. Re-run that batch in small groups with JUnit XML; stop at first failure and isolate only that test.
3. Run Browser config guard alone with HTTPS origin; do not run full login workflow until the approved synthetic credential and test HTTPS service are available.
4. Review downgrade functions and migration index-retry logic, then test on a new disposable DB/schema only.
5. Expand DB readiness with real backup/restore and retention/recovery evidence, not just migration success.
6. Close Dashboard, Analyzer, and full regression gates; then reconcile README and release documentation.
7. Request explicit user approval before commit, PR, push, production migration, or operational data change.

## 9. Safety constraints
- Do not access or mutate Operational DB. Ports 5432/6379/9000/9001 and PgBouncer 6432 are operational services; never use them for tests.
- Current final16 disposable stack: PostgreSQL 56443 (databases eims_regression_test_20261115 and eims_browser_acceptance_20261115), Redis 56380 (DB index 5), MinIO 59002. Historical ports 56441/56379/59000 may still exist; inspect before use or cleanup.
- Do not remove Docker containers, anonymous volumes, schemas, buckets, or test artifacts unless each target is positively identified and user-approved.
- Do not use git clean, reset, checkout-overwrite, destructive rebase, commit, or push.
- Do not overwrite existing modified/untracked files.
- No purchases, subscriptions, paid credits, or account restore actions.
- Never put secrets, passwords, tokens, or connection strings containing credentials into source control or these documents.

## 10. Safe command baseline
From repository root:
```powershell
Set-Location 'C:\Users\MewMew\Desktop\Co-op\EIMS'
.\venv\Scripts\python.exe -m alembic heads
.\venv\Scripts\python.exe -m alembic history --verbose
git status --short
git diff --check
```

For integration tests, populate EIMS_TEST_* and EIMS_DB_* only within the disposable test process, retrieving credentials from the named disposable containers. Never write these values into .env or persistent shell profiles.

## 2026-11-15 final16 runtime alignment — current state supersedes earlier Browser blockers

### Verified current state
- Secure Browser Acceptance final14: 33/33 PASS; full Playwright final16: 2/2 PASS, 33/33 checks, exit 0. Artifacts and detailed caveats are in `EIMS_ACCEPTANCE_LEDGER.md` and `docs/engineering-memory/2026-11-15-final16-runtime-alignment.md`.
- Browser test app is `tests.analyzer_synthetic_demo_app:app` on port 8000 with `eims_regression_test_20261115`. Production application smoke is `backend.main:app` on port 8000 with `eims_browser_acceptance_20261115`. The currently running backend is the production application path on synthetic data.
- Current listener map: Dashboard 3009, HTTPS proxy 3449, Backend 8000, PostgreSQL 56443, Redis 56380, MinIO 59002.
- Production application-path smoke: synthetic login, Analyzer, Follow-up, History and Stats returned HTTP 200. Current Health endpoint is HTTP 200 / HEALTHY with PostgreSQL-PgBouncer, Redis, and MinIO UP. This is not a production deployment.
- Focused pytest: 88/88 pass. Targeted import-order Ruff, Python compile, logger import and `git diff --check` pass. Full Ruff remains non-clean with legacy findings; do not claim full lint pass.
- Runtime fixes: dedicated full-schema synthetic DB, correct test harness, unique Knowledge title per run, `ddgs` package migration, UTC-naive timestamp generation aligned to the legacy DB column, and updated JSON logger import.

### Superseded historical notes
- Earlier sections 7–8 correctly recorded Browser Acceptance as NOT PASSED at their checkpoint. Those Browser blockers are superseded by final14/final16 evidence above.
- The final15 Playwright attempt failed due duplicate synthetic Knowledge titles from a stale harness DB; final16 used a fresh harness process and unique per-run title and passed.
- final14's Follow-up 404 for another user's History is an intentional owner check in the real `/api/v1/analyze/followup` route, not a missing endpoint.

### Still open — do not declare project closed
1. Gold manifest remains 17 DRAFT cases (12 DEV, 5 HELDOUT), zero human-reviewed. Independent human review is mandatory; AI agents must not create review status.
2. Main synthetic application DB currently has zero KnowledgeEntry rows. Static vendor references exist in code, but the incident-derived DB is not seeded. Add full-text search, product/version/environment applicability, prerequisites, risk, validation/rollback, usage feedback and stale/revalidation lifecycle before broad Engineer rollout.
3. Explicit JWT `exp` boundary test is separate from the proven database session-row expiry.
4. Complete WAL/PITR, retention, measured RPO/RTO, failover/recovery, capacity/load, TLS/secrets, monitoring, and operational ownership sign-off. Earlier logical backup/restore evidence does not prove PITR.
5. Run a controlled Engineer pilot with authorized sanitized incidents and capture usefulness/safety feedback.

### Preservation
- Branch/HEAD: `integration/eims-consolidated` / `85493b2`.
- Git status: 51 modified tracked + 44 untracked = 95 entries. Preserve all.
- No commit/push/reset/clean/stash, no Operational DB access, no destructive cleanup, and no Work Mode.


## 2026-11-14 continuation update (21:15 ICT)
- Reliability suite completed: 155/155 PASS, no skip; JUnit in %TEMP%\eims-reliability-focused.xml. Earlier perceived hang was polling during execution.
- Analyzer unit suite: 249 total, 248 PASS, 0 FAIL/ERROR, 1 Windows symlink-policy SKIP; JUnit in %TEMP%\eims-analyzer-unit-20261114.xml.
- Analyzer export content builders: 16 assertions PASS. Does not certify rendered PDF or browser download.
- Migration round-trip and interrupted-index recovery completed on eims_migration_roundtrip_20261114. Forced invalid concurrent unique indexes on telemetry_metrics and windows_event_logs, removed only duplicate synthetic fixture rows, reran Alembic; both unique indexes and 4625 partial functional index valid/ready at head a3d6f1e8c295.
- PostgreSQL logical backup/restore drill passed: 36 KB custom-format dump restored to eims_restore_drill_20261114; head matches; synthetic counts 1 asset, 1 telemetry metric, 1 Windows event; zero invalid indexes. Dump retained inside disposable container at /tmp/eims-roundtrip-20261114.dump.
- Unique idempotency constraint rejects duplicate source_event_key; multiple NULL values remain allowed.
- Analyzer manifest has 17 cases, all DRAFT (12 DEV, 5 HELDOUT). Rule-only exploratory DEV executed 12 draft cases but reported INSUFFICIENT_DATA with zero reviewed cases; no accuracy claim. Do not use heldout for tuning.
- Browser guard passed, but full secure browser acceptance failed at connection setup: https://localhost:3449/analyzer refused connection. Next dev server exists at 3000; no backend listener at 8000; no 3449 listener. No actual login attempt or DB mutation occurred. Config-only placeholder was not a real credential.
- Current Git: HEAD 85493b2131d3e353453072559a5dfc301d75dd06; 32 modified tracked, 30 untracked, 62 total; diff check passes with line-ending warnings. No commit/push/clean/reset.

## Next critical work
1. Build/bring up a strictly isolated EIMS app acceptance runtime: dedicated synthetic DB, Redis namespace, MinIO bucket, backend, dashboard, trusted HTTPS origin. Never point it at operational ports.
2. Provision synthetic users only in the disposable DB using the project's supported auth/seed path; generate a random ephemeral credential and keep it in process environment only. Do not store it in files or source control.
3. Complete secure-dashboard browser acceptance: actual cookie login, HttpOnly/Secure/SameSite, BFF health, 12 Analyzer cases across languages and input modes, evidence provenance, history isolation, export download, logout/replay/expiry, no transient 502/503.
4. Independently annotate the 17 draft gold cases, bind reviews to exact fixture/prediction hashes, then evaluate DEV reviewed cases. Keep HELDOUT sealed.
5. Expand DB operations from logical backup/restore to WAL/PITR, retention, measured RPO/RTO, failover, capacity and recovery drill.
6. Run full regression and security review after all service acceptance gates close.
7. Update README release status and request explicit PR/commit approval only after evidence review.
- Additional Analyzer stability suite: 71/71 PASS, no skips, JUnit %TEMP%\eims-analyzer-stability-20261114.xml.
- Combined pytest evidence now totals 479 cases: 478 PASS, 0 FAIL, 0 ERROR, 1 Windows symlink-policy SKIP. Breakdown: 4 focused integrations + 155 reliability/fault contracts + 249 Analyzer unit/evaluation + 71 Analyzer stability. Separate 16 export-builder assertions passed.

## 2026-11-15 database health probe and orchestration update

### Repository and execution
- Branch and HEAD remain `integration/eims-consolidated` / `85493b2131d3e353453072559a5dfc301d75dd06`.
- Work Mode is explicitly excluded from EIMS. Continue repository work through Remote Desktop Commander on Mew.
- No commit/push, no reset/clean/stash, no Operational DB access.
- Engineering memory pointer: `docs/engineering-memory/INDEX.md`; current immutable snapshot: `docs/engineering-memory/2026-11-15-database-health-probe.md`.
- Root agent instructions: `AGENTS.md`; Cursor pointer: `.cursor/rules/eims-engineering-memory.mdc`.

### Database health probe correction
- `AsynchronousDatabaseEngine.ping()` now has one 2-second cancellation deadline over pool checkout, `SELECT 1`, and connection context exit. It validates scalar result 1 and records checkout/execute/cleanup/total time, deadline-expired state, sanitized error class, and pool status.
- Caller cancellation propagates. SQLAlchemy 2.0.57 waits for safe connection cleanup before propagating cancellation. The deadline triggers cancellation; cleanup can extend wall-clock time beyond 2 seconds and is measured.
- Project dependency constraints aligned with the tested runtime: SQLAlchemy `>=2.0.57,<2.1.0`, asyncpg `>=0.31.0,<0.32.0`. Runtime: Python 3.14.3 / SQLAlchemy 2.0.57 / asyncpg 0.31.0.
- SQLAlchemy 2.0.55 changelog specifically fixed async context-manager cleanup and pool cancellation leaks; 2.0.56 fixed AsyncConnection.close cancellation and a pool checkout cancellation race. asyncpg 0.31.0 adds Python 3.14 support.

### Verification
- Focused pytest: 15 PASS across database ping diagnostics (12), health concurrency (1), synthetic health contract (2); 0 failures/errors/skips. Two existing deprecation warnings.
- Ruff: PASS for the changed database implementation and ping tests.
- `pip check`: PASS.
- `git diff --check`: PASS; line-ending warnings only.
- Real disposable PostgreSQL clone `eims-history-repro-pg-20261114` on loopback port 56442: pool exhaustion deadline, recovery after checkout, delayed cleanup after deadline, recovery after cleanup timeout, external cancellation during cleanup, and final pool recovery all verified. Only `SELECT 1`; no data/schema writes. Log: `%TEMP%\eims-ping-live-lifecycle-final.log`.

### Browser Acceptance and root cause
- Browser Acceptance remains **NOT PASSED**. No new Browser run was started.
- Earlier attempts recorded 502/503 around Analyzer/History and `net::ERR_NETWORK_CHANGED`. The probe correction closes a confirmed lifecycle gap but does not prove it caused those failures.
- Next: controlled concurrent Analyzer workload on disposable services, capture SQLAlchemy pool state and PostgreSQL activity, correlate request IDs across browser / HTTPS proxy / BFF / backend, and reproduce before changing further settings. Only then reopen full Browser Acceptance with JUnit.

### Connected AI/tool status
- Claude Code CLI: read-only audit completed; its concern about safe cleanup was checked against installed SQLAlchemy source and a real disposable-PostgreSQL lifecycle test.
- Parallel research: used for current SQLAlchemy and asyncpg release notes.
- OpenCode auth inventory: stored providers include Google, OpenAI OAuth, OpenRouter, xAI, DeepSeek, Groq, and Cloudflare. OpenCode run bridge returned failed outcomes with zero tokens for Gemini and OpenAI attempts; these are not accepted as reviews.
- Gemini, Grok, Cursor, Antigravity, Manus, and Codex desktop processes were visible, but no directly callable output was obtained from those GUI sessions in this continuation. Do not attribute findings to them.
- Kilo config contains only the notebook-first Data agent for Jupyter-based data investigation; no Kilo CLI was available in PATH, so it was not used as a code implementer.
- OMC subagent tracking currently reports zero active agents; the replay file contains historical stop events without usable task output.
- Liner search-agent call returned payment required; do not retry without changed account state.
- ChatGPT remains the orchestrator. Keep implementer, independent reviewer, and evidence verifier distinct.
- Final Git state at database-probe checkpoint: 34 modified tracked paths, 32 untracked paths, 66 total porcelain entries. Original work remains intact; no commit, push, reset, clean, or stash.

## 2026-11-15 Analyzer pool-starvation correction
- Confirmed before fix on disposable PostgreSQL clone port 56442: two concurrent `build_summary()` requests held both pool connections during external summary work; Health Probe failed at checkout. After fix, two concurrent Analyzer tasks reached external work with zero checked-out connections and Health Probe passed during and after the work.
- `summary.build_summary()` now runs RAG in a short-lived AsyncSession for engine-bound sessions; caller session is preserved. Connection-bound test/savepoint sessions remain caller-owned.
- Added `rollback_read_only_transaction()` (rollback only, never commit) at explicit clean read-only boundaries in offline import and vector export; refuses pending ORM state.
- Vector embedding is completed before first DB checkout; no-op paths release read-only lookup transaction. Removed unnecessary post-commit `db.refresh()`; MemoryHistory test sink now emulates INSERT RETURNING id/created_at.
- Real clone checks: pool checked-out=0 during concurrent external summary work; Health Probe PASS; pool checked-out=0 during delayed embedding; caller cancellation propagated; read-only SELECT rollback returned checked-out 1→0; INSERT RETURNING produced id/created_at without refresh, inside rolled-back outer transaction.
- Focused six-file pytest: **280 PASS / 0 FAIL / 0 ERROR / 0 SKIP**, exit 0. JUnit: `%TEMP%\eims-analyzer-lifecycle-20261115-rerun.xml`. Targeted Ruff correctness checks and compileall PASS; broad Ruff still reports legacy style findings. `git diff --check` PASS.
- Browser Acceptance remains NOT PASSED; not rerun. This proves Analyzer pool-starvation mode and fix, not sole historical Browser 502/503 cause. Next: separately launched disposable application stack, correlated proxy/BFF/backend/pool/PostgreSQL evidence, then full Browser Acceptance with JUnit.
- Current snapshot: `docs/engineering-memory/2026-11-15-analyzer-pool-starvation.md`; previous health-probe snapshot retained.
- Git checkpoint: 35 modified tracked + 32 untracked = 67; HEAD unchanged. No commit/push/reset/clean/stash. All direct SQL used the disposable clone; one GET to the live health endpoint may have invoked a DB ping before its target was confirmed (no write endpoint called; see audit note).
- Final smoke after the last defensive session-bind change: Analyzer reliability + Analyzer integration stability **224 PASS / 0 FAIL / 0 ERROR / 0 SKIP**, exit 0; JUnit `%TEMP%\eims-analyzer-final-smoke-20261115.xml`.
- Audit note: one read-only GET was sent to the existing backend `/api/v1/health` listener before its configured DB target was confirmed. It may have invoked a DB ping; no mutation endpoint was called. The PowerShell client stalled and could not be stopped due Access Denied. No further requests were sent to live listeners. All subsequent DB verification used only the disposable clone.
- A fresh independent review of the final Analyzer diff was attempted through Claude Code CLI but did not return review content (stdin/terminal invocation stalled); do not count it as a completed review. The earlier Claude read-only review covered SQLAlchemy cancellation/cleanup semantics, not the entire final Analyzer diff.




## 2026-11-15 03:31 ICT — health-monitor coalescing

- Work Mode remains explicitly excluded. All repository and runtime work continues through Remote Desktop Commander on Mew.
- Re-read the root `AGENTS.md`, `.cursor/rules/eims-engineering-memory.mdc`, `.cursor/rules/ponytail.mdc`, Engineering Memory index/current snapshot, operational handoff, and acceptance ledger before implementation.
- Confirmed duplicate dashboard health polling: global NotificationBell every 15s, Analyzer SystemStatusCard every 30s, and Observability page every 15s. Each independently called the same backend endpoint.
- Implemented shared per-tab frontend monitor (`clients/dashboard/src/lib/health-monitor.ts`) consumed by all three UI surfaces. It coalesces in-flight fetches, owns one 15s interval, preserves a 40-sample shared history, times out at 5s, and distinguishes API reachability from dependency health.
- Implemented backend aggregate single-flight and 5s monotonic health snapshot in `backend/main.py`; concurrent callers share one dependency-probe batch, recent calls reuse its actual result, and any dependency failure remains HTTP 503 / DEGRADED.
- Added tests in `tests/test_health_probe_concurrency.py` for concurrent coalescing, cache reuse, TTL expiry, and degraded-state preservation.
- Verification: 24 pytest PASS / 0 FAIL / 0 ERROR / 0 SKIP (JUnit `%TEMP%\\eims-health-snapshot-20261115.xml`); dashboard `tsc --noEmit` PASS; targeted ESLint PASS; Next.js production build PASS; `git diff --check` PASS.
- Browser Acceptance remains NOT PASSED and was not rerun. This change is not evidence that the historical Browser 503s are fully resolved. Next action is a separately launched disposable app stack, followed by correlated HTTPS/BFF/backend/DB evidence and full Browser Acceptance.
- Git branch/HEAD unchanged: `integration/eims-consolidated` / `85493b2131d3e353453072559a5dfc301d75dd06`; 42 modified tracked and 34 untracked paths. Preserve all existing changes. No commit/push, reset/clean/stash, or Operational DB access.


## 2026-11-15 verification refresh

- Final focused health regression suite is **25 passed / 0 failed / 0 errors / 0 skipped**, exit 0, after adding explicit coverage that a cached DEGRADED snapshot stays HTTP 503 and does not trigger another dependency probe batch.
- Exact pre-fix 25-check Browser artifact identified: `test-results/secure-browser-acceptance-20261115-isolated/secure-browser-acceptance.json`; it failed at `signIn:synthetic-expiry:authenticated-ui` with **24 correlated HTTP 503 `/api/eims/api/v1/health` responses out of 518 correlated records**. This is historical pre-fix evidence.
- Later test attempts are separate: `session-readonly` failed at 3 checks on the evidence `<details><summary>` keyboard-focus selector; `session-readonly2` failed at 0 checks on initial navigation. Do not call these health-recovery evidence.
- The shared frontend health monitor/backend aggregate cache has not yet been exercised by a full Browser Acceptance. Keep status NOT PASSED. Next inspect and correct the evidence-disclosure test locator without weakening keyboard-accessibility assertions, then launch the known disposable synthetic stack and rerun complete Browser Acceptance with fresh JUnit and correlated runtime evidence.


## 2026-11-15 continuation — final integrated acceptance status

The latest retained Browser Acceptance report is `test-results/secure-browser-acceptance-20261115-final10/`: **PASS 33/33**, Playwright **2/2**, zero correlated HTTP 502/503. The expiry boundary proves PostgreSQL session-row expiry while the JWT is still unexpired; do not describe it as a JWT-expiry test.

Full repository regression collected 748 tests with zero failures. Six explicitly opt-in infrastructure tests were skipped in that run, then executed separately against the dedicated disposable EVTX PostgreSQL/Redis/MinIO stack and all six passed. Combined distinct coverage is 748/748 passed. Additional retained focused results: Analyzer/PostgreSQL 67/67, health probes 46/46, Analyzer/auth/investigation 186/186, diagnostic catalogue 48/48.

The reference catalogue currently contains 141 Windows Event entries and 22 vendor/syslog entries (163 total). Dynamic Knowledge Lifecycle is proven, but the 17-case gold manifest remains DRAFT (12 dev, 5 held-out). Do not claim comprehensive incident coverage or authoritative Analyzer quality until independent domain review is complete and a starter set of recurring incidents has been curated and independently approved.

Next gates: (1) human review of all 17 gold cases and evidence claims; (2) curate/approve initial high-value knowledge from official documentation and authorized incidents; (3) explicit JWT expiry/revocation acceptance separate from session-row expiry; (4) witnessed production-like backup/restore and rollback plus TLS/secrets, retention, monitoring, and operational ownership sign-off.

Latest authoritative snapshot: `docs/engineering-memory/2026-11-15-final-readiness.md`. Branch/HEAD remain `integration/eims-consolidated` / `85493b2`. Preserve the existing modified and untracked work; no reset, clean, stash, commit, push, or destructive cleanup has been performed.


## 2026-11-15 continuation — current capability and acceptance boundary

- Current branch remains `integration/eims-consolidated`; HEAD remains `85493b2`.
- New migration head in Repository: `a4b7c9d2e601`. It has not been applied to any database.
- Knowledge review is now capability-based: `knowledge_reviewer` on a normal Engineer account; legacy Admin accounts retain review capability. Admin-only user administration remains separate.
- Authenticated Engineers may read the Source Catalogue and Source/Lifecycle audit histories. Only Reviewers may approve Knowledge or mutate Source/Lifecycle state. Self-approval remains prohibited.
- Source hash semantics: Catalogue Record SHA-256 fingerprints canonical JSON metadata, not the current Vendor page or downloaded document bytes.
- Settings screen is preview-only and no longer reports fake successful persistence.
- Focused tests: 14 passed; Ruff and Python compile passed; Dashboard production build and Browser harness syntax passed.
- PostgreSQL integration, migration application, 20-source import and Browser Acceptance are still pending because the current process has no authorized synthetic test DB URL or Browser test credentials. Do not substitute the running application database or claim prior Browser Acceptance covers these changes.
- No operational DB access, commit, push, reset, clean or stash.

### Next execution sequence

1. Restore a dedicated synthetic test connection using an explicitly authorized identity and exact database allowlist.
2. Apply `a4b7c9d2e601` and import 20 candidates; verify rows, canonical catalogue-record hashes and import/review events.
3. Run PostgreSQL integration tests for Engineer read access, Reviewer write capability, Admin separation and self-review prevention.
4. Run Browser Acceptance against the current backend/dashboard; confirm source catalogue visibility and Reviewer-only actions.
5. Obtain Domain Review decisions for Vendor candidates and the 17 DEV/HELDOUT Gold fixtures.
6. Keep external backup/Witnessed Restore and RPO/RTO approval as Operations-owned gates.
7. Complete Engineer pilot and collect independently verifiable resolution evidence.

The target remains: What happened → Why → What to inspect → How to remediate → Risks → Validation evidence. User-reported KnowledgeUsage outcomes must not be presented as independent proof of resolution.


## 2026-11-15 — AI tooling registry and cross-chat continuity

### Durable continuity artifacts
- Added repository-root `AI_TOOLING_INVENTORY.md` as the evidence-backed inventory of Mew's AI clients, agents, MCP endpoints, provider/config state, role assignments, and verification rules.
- Added `docs/engineering-memory/NEW_CHAT_CONTINUATION_PROMPT.md` as the copy/paste startup prompt for a new ChatGPT conversation.
- Updated root `AGENTS.md` to require the AI inventory and continuation prompt, and to honor the user's explicitly selected execution mode. Remote Desktop Commander remains the direct machine-access channel for Mew.
- Added root `CLAUDE.md` and `GEMINI.md` adapter instructions so clients that do not automatically consume root `AGENTS.md` are pointed to the same canonical project contract rather than maintaining divergent copies.

### Machine-backed AI findings (2026-11-15)
- Claude Code 2.1.323 installed; 33 Claude EIMS project session JSONL files present.
- `claude mcp list` live health check reported 15 CONNECTED services: Claude Docs, Linear, Wispr Flow, Stripe, Microsoft Learn, Context7, Vercel, Supabase, Canva, Google Docs, Google Slides, Google Sheets, Gmail, Google Calendar, Google Drive.
- Claude MCP also reported 20 AUTH-REQUIRED entries, Black Diamond HTTP 503, Vanguard endpoint not found, and Snowflake not configured. Exact detail is in `AI_TOOLING_INVENTORY.md`.
- Codex Windows app configuration exists; `~/.codex/config.toml` defines bundled `node_repl` and external FableCut MCP. The `codex` command was not recognized in the inspected PowerShell PATH; do not call this live-connected.
- OpenCode 2.3.0 installed. `opencode.jsonc` contains FableCut and Browse definitions, but live `opencode mcp list` reported no configured servers. Preserve this discrepancy as unresolved.
- Gemini/Antigravity MCP config files inspected contain empty `mcpServers`; `gemini` and `agy` were not recognized in the inspected shell. Antigravity IDE/Standalone artifacts and browser profile are installed.
- Cursor 3.30.14 installed; EIMS always-on project rule exists. Kilo EIMS Data agent is notebook-first Jupyter only.
- Prior EIMS handoff records Cursor/Grok as implementation, OpenCode as independent read-only reviewer, Claude Safe Mode as test/reliability reviewer (startup/stdin caveat), Antigravity as read-only architecture reviewer, and ChatGPT as technical lead. These are historical role assignments, not proof of current agent execution.
- EIMS OMC tracking last recorded 0 spawned / 0 completed at 2026-11-13; verify before assuming active agents.

### Research-informed design decisions
- Keep a small always-read project contract (`AGENTS.md`) and separate detailed inventory and task continuation prompt. This reduces prompt duplication and drift.
- Add client-specific pointer files (`CLAUDE.md`, `GEMINI.md`) rather than copying the full rules into every client file. Not every client automatically loads the same instruction filename.
- Distinguish durable instructions, dated engineering memory, current operational handoff, acceptance evidence, and live tool status. No single chat transcript is the system of record.
- MCP inventory must include all endpoints, auth state, tool owner/client scope, and evidence timestamp; use least privilege and do not expose secrets.

### Execution note
- This was a documentation/continuity task only. No application code, database, container, volume, credential, or operational service was changed.
- The current inspected Git state before these documentation additions was branch `integration/eims-consolidated`, HEAD `85493b2131d3e353453072559a5dfc301d75dd06`, 115 status entries. Preserve all pre-existing modifications and untracked files.


## 2026-11-16 — Reviewer audit hardening and non-superuser PostgreSQL acceptance

### Repository / implementation
- Branch/HEAD unchanged: `integration/eims-consolidated` / `85493b2131d3e353453072559a5dfc301d75dd06`.
- Added Reviewer capability grant/revoke security events to the existing `audit_logs` journal; no duplicate audit subsystem or migration.
- Grant/revoke and audit event commit atomically. User row is locked before state transition. Repeated no-op state does not create another event.
- Account creation with `knowledge_reviewer=true` also records a create-time grant event.
- Legacy Admin review capability remains implicit. Revoke request against Admin now returns 409 instead of misleadingly returning effective Reviewer=true.
- Exact implementation/test details: `backend/api/routers/analyzer/admin.py`, appended test `test_knowledge_reviewer_grant_revoke_are_audited_atomically`.

### Final accepted synthetic DB
- Container `eims-reviewer-source-nonsuper-pg-20261116`, image `pgvector/pgvector:pg16`, loopback port 56446.
- Database `eims_integration_test`; role `eims_test`.
- Verified role flags: superuser=false, createdb=false, createrole=false.
- Alembic head `a4b7c9d2e601`.
- Import result: 20 created / 0 updated / 0 unchanged; 20 import audit events; 0 KnowledgeEntry rows.
- Migration, importer and integration tests ran as the non-superuser application identity. PostgreSQL superuser was used only to provision the disposable role/database/extensions.
- An earlier container whose bootstrap `eims_test` role was superuser is not accepted evidence and remains untouched. Do not use it for least-privilege claims.

### Verification
- Focused PostgreSQL migration/API suite: 5 passed, 0 failed, 0 errors, 0 skipped; exit 0.
- JUnit: `test-results/reviewer-source-nonsuper-postgres-20261116.xml`.
- Python compile: PASS.
- Ruff F401/F841/E402: PASS on changed backend/test files.
- Browser config guard: PASS (5 invalid configs rejected); this is not browser acceptance.
- `git diff --check`: exit 0, line-ending warnings only.
- Worktree count after this snapshot: 161; preserve all existing modifications/untracked files.

### Browser gate
- Full Browser Acceptance NOT RUN. The HTTPS endpoint on 3449 identifies as `EIMS Core Gateway`; health is healthy but the synthetic harness diagnostics endpoint is unavailable. No login or mutation was sent to that gateway.
- Next: stand up a separate synthetic backend + dashboard/BFF + trusted HTTPS origin on dedicated ports and use only isolated PostgreSQL/Redis/MinIO resources. Then run current Reviewer/Engineer Browser Acceptance with JUnit and correlated request/runtime evidence.
- A read-only Claude Code review was attempted but returned no review content; independent review remains outstanding.

### Remaining project gates
- Current Browser Acceptance for latest Reviewer/Source UI.
- Human Domain Review: 20 vendor candidates and 17 DEV/HELDOUT Gold cases.
- Offsite backup, witnessed restore, retention and owner-approved RPO/RTO.
- Controlled Engineer pilot with incident provenance and independent resolution validation.

No Operational DB access, commit, push, reset, clean, stash, rebase or destructive cleanup.


### Execution-mode correction (current)
- A previous dated note said Work Mode was explicitly excluded. That blanket exclusion is superseded by the user's later direction: use the execution mode the user explicitly requests; Work Mode may be used when explicitly requested. Remote Desktop Commander remains the channel for direct Mew machine operations.
- For the 2026-11-16 work segment, the user explicitly directed Remote Desktop Commander; all repository/runtime actions above were performed on Mew through that channel.


## 2026-11-16 — Incident Core v1 (backend-only)

### Repository / implementation
- Branch/HEAD unchanged: `integration/eims-consolidated` / `85493b2131d3e353453072559a5dfc301d75dd06`.
- New package `backend/domain/incident/` (models, schemas, pure correlation, service, controller).
- Additive migration `b8d3f5c1a720` (parent `a4b7c9d2e601`): `incidents`, `incident_evidence`, nullable `analysis_history.asset_id` (FK RESTRICT, indexed, no backfill).
- Existing `audit_logs` journal reused with `INCIDENT_CREATED` / `INCIDENT_EVIDENCE_ADDED` / `INCIDENT_STATUS_CHANGED` and `incident_id` in `immutable_payload`.
- Incident API registered at `/api/v1/incidents`; reads authenticated, writes Engineer, close requires `require_knowledge_reviewer`.
- No UI, automatic closure, remediation or causal root-cause inference.

### Disposable DB used
- Container `eims-incident-core-pg-20261116`, port 56448, database/role `eims_incident_test`.
- Role flags verified non-superuser. Alembic and tests ran with that role; bootstrap `postgres` was used only for role/database/extension provisioning.
- Ephemeral password generated in-process and passed via environment variables only; not persisted.
- Alembic head `b8d3f5c1a720` (single head).

### Verification
- Incident suite: 60 passed / 0 failed / 0 errors / 0 skipped, exit 0; JUnit `test-results/incident-core-20261116.xml`.
- Focused regressions: 261 passed / 0 failed / 0 errors / 1 skipped, exit 0; JUnit `test-results/incident-core-regressions-20261116.xml`.
- `git diff --check`: exit 0 (line-ending warnings only).
- Worktree after this snapshot: 126 entries (57 modified preserved, 69 untracked).

### Boundaries
- Browser Acceptance NOT RUN; backend-only deliverable, no browser claim.
- Do not reuse container `eims-incident-core-pg-20261116` for Operational data; it is a disposable synthetic target.
- No Operational DB/Redis/MinIO access, commit, push, reset, clean, checkout, stash or rebase; no container deletion.

## 2026-11-16 - DWB orchestration + Incident Core review

- DWB control plane now supports approved agent launch (`agent.list`, `agent.run`, `agent.cancel`) with registry verification, complete prompt preview at approval, role/scope enforcement, writer locks, cancellation, timeout, orphan recovery and sensitive-output withholding.
- Project profiles are generic; EIMS is the only enabled profile. Jobs, artifacts, approvals and locks are project-scoped.
- Incident Core v1 is implemented (migration `b8d3f5c1a720`) with terminal-incident recurrence protection. Incident tests 61/61; regressions 261 passed, 1 skipped.
- Independent review final: no high-severity findings. ChatGPT must refresh the plugin tool catalog to see 14 tools.
- Branch/HEAD unchanged; 57 modified preserved; no commit/push/reset/clean.

## 2026-11-16 - EIMS Auto Job Relay (Chat_HAND V6)

- Chat_HAND control plane now runs agent jobs through a detached runner (`gateway/lib/agent-runner.mjs`), so an MCP server restart no longer kills a healthy job. A background monitor (`gateway/lib/job-monitor.mjs`) finalizes jobs from runner exit metadata; a durable store (`gateway/lib/job-store.mjs`) keeps job records, split artifacts and result envelopes.
- New read-only tools: `jobs.list`, `jobs.wait` (bounded, default 30 s / hard max 40 s, optional), `jobs.get_result` (chunked, per-stream SHA-256), plus `jobs.ack_result` which records user acknowledgement separately from host retrieval. Tool surface is now 18.
- Delivery: an external gateway cannot inject an unsolicited message into a ChatGPT conversation, so delivery is on demand. A scheduled task inside the chat is a supported follow-up mechanism, but its cadence is unverified on this account and is not assumed.
- Verification: relay suite 25/25; orchestration 22/22; control plane 40 pass / 1 not tested; real approved read-only agent through the relay: Claude Code completed with `jobs.wait` returning `still_running` at the 40 s bound, `jobs.get_result` returned exit 0 with `sha256 1cdff417…`, worktree unchanged (126 entries, 57 modified, 69 untracked). An archived OpenCode run shows the relay correctly capturing a provider-credit failure.
- Independent read-only review (Claude Code, 3 rounds): round 1 found one HIGH (interruption could release a writer lock without proving the process dead); round 2 found a new HIGH introduced by that fix (unbounded pid kills with no identity proof). Both fixed; round 3 verdict: NO HIGH-SEVERITY FINDINGS. Residuals documented in `evidence/v6-review.json`.
- Boundaries: no EIMS application code changed; no Backend, Incident Core, Operational DB/Redis/MinIO access; no commit, push, reset, clean, checkout, stash or rebase. Browser Acceptance remains NOT RUN. The running Incident Core job was not touched.
- Next owner actions: refresh the ChatGPT plugin catalog to see 18 tools; verify scheduled-follow-up cadence in the owner account before claiming it; decide whether real writer-mode acceptance is in scope.


## 2026-11-16 - Relay finalization + Incident Core v1.1 prep

- Relay local surface re-verified on current code: **18 tools**, exact names asserted, all four `jobs.*` tools callable (`scripts/Verify-EimsMcpSurface.mjs`, `evidence/v6-mcp-surface.json`). ChatGPT host catalog refresh remains a **user action** and is not claimed.
- Relay suites re-run: 25/25 relay, 22/22 orchestration, 40 pass + 1 not tested control plane. Real read-only agent (Claude Code) passed end to end; worktree unchanged.
- The one `NOT TESTED` control-plane case is `deny.symlink_file_escape`: the host lacks `SeCreateSymbolicLinkPrivilege` (reproduced directly). Same reparse-point deny path is covered by the passing junction test. No security behaviour was changed to force it.
- New residual risk documented: a hard link inside the workspace to a file outside it is readable via `workspace.read_file` (read-only path; creating it needs local write access). Recorded in Chat_HAND `docs/CONTROL_PLANE.md` and `AUTO_JOB_RELAY.md` Â§13; not "fixed" with a rule that would reject legitimate files.
- **Writer mode remains NOT ACCEPTED.** OpenCode is BLOCKED by provider credits (direct probe exit 1). The substitute Claude Code writer approval (`5cbe12e0â€¦`) was never executed locally and stayed `pending`, so nothing ran and no file was written. One human approval is the only remaining step; `scripts/Smoke-EimsWriterRelay.mjs` does the rest.
- Incident Core v1.1 prepared, not started: prior trace job `3ef58a7dâ€¦` recovered into engineering memory; plan written. Decision: additive `incident_ingest_outbox` + dedicated async consumer, not an extension of `telemetry_alert_outbox`. No backend or Incident Core file changed.
- Open decisions before v1.1 implementation: emission policy, offline USB winlog inclusion, disposable test target.
- Boundaries: no commit, push, reset, clean, checkout, stash or rebase; no Operational DB/Redis/MinIO access; EIMS worktree back to 126 entries (57 modified, 69 untracked).

## 2026-11-16 - Incident Core v1.1 ingestion: implementation written, NOT verified (current)

- Authorized writer task executed by Claude Code (this is the first real writer-mode task; it is NOT a separate smoke and writer mode acceptance still depends on the independent review below).
- Implemented in source: additive `incident_ingest_outbox` (migration `c4e8a1f7b932`, `down_revision = b8d3f5c1a720`, single head), package `backend/domain/incident_ingest/` (model, envelope, in-transaction emitters, dispatcher, consumer), emitter hooks in the telemetry worker, analyzer submit/bundle/offline import and offline USB winlog batch, and consumer start/stop in `backend/main.py`. Actor `system:incident-ingest`; streams under `eims:jobs:incident-ingest:*`. Details: `docs/engineering-memory/2026-11-16-incident-core-v11-ingestion-implementation.md`.
- **Nothing was executed.** `python -m pytest`/`py_compile` and `docker run` required approval that was unavailable (non-interactive session). Unit, integration, migration tests: NOT RUN. Disposable PostgreSQL/Redis for this milestone: NOT CREATED (provisioning commands are in the snapshot). Independent read-only review: OPEN.
- Next actions: (1) a human provisions the two new disposable containers and exports the three `EIMS_INGEST_TEST_*` variables; (2) run the focused suites listed in the snapshot with JUnit + exit codes; (3) a separate read-only reviewer reviews the exact diff; (4) only then record acceptance. Do not apply the migration to the Operational DB without explicit authorization.
- Worktree: 57 modified + 75 untracked (six new paths). No commit/push/reset/clean/checkout/stash/rebase; no Operational DB/Redis/MinIO access.


## 2026-11-16 - Incident Ingestion v1.1 accepted (current)

- Status: **COMPLETE** for code, unit, migration and isolated PostgreSQL/Redis integration, plus independent review **ACCEPTED**. No commit or push.
- Branch `integration/eims-consolidated` @ `85493b2`; Alembic head `c4e8a1f7b932` (single head, parent `b8d3f5c1a720`).
- Root causes closed: three stale unit-test doubles (`fallback_time` kwarg, `severity` key), the populated-parent migration test missing four NOT NULL asset columns, outbox insert swallowing every error (now only a missing table is tolerated; other DB errors fail the source transaction), unbounded multi-row insert (chunked at 500), and atomicity wording.
- Evidence: 113 passed / 0 failed / 0 skipped, exit 0, 28.6 s (`/.omc/evidence/v11-ingest-full-junit.xml`); focused unit 95 passed (`v11-recovery-unit-junit.xml`); correlate regression PASS; `git diff --check` exit 0.
- Isolated infrastructure created by this task and left running: `eims-ingest-v11-pg-20261116c` (127.0.0.1:56460, DB `eims_ingest_v11_test`, role `eims_ingest_v11_app` NONSUPERUSER, sentinel `EIMS-DISPOSABLE-INGEST-V11:â€¦`) and `eims-ingest-v11-redis-20261116c` (127.0.0.1:56461, sentinel key verified). Credentials never written to disk.
- Independent review (Claude Code, read-only, 3 rounds): no HIGH; two MEDIUM (swallowed outbox errors, unbounded insert) fixed and covered by two new tests; deferrals documented (XAUTOCLAIM attempt counting, log/drain backpressure, F8 offline dedupe race, F10 asset FK retention).
- Deployment prerequisite: apply `c4e8a1f7b932` before deploying code that writes the outbox.
- Boundaries: no operational DB/Redis/MinIO/credential/listener access; no destructive cleanup; unrelated worktree files untouched.

## 2026-11-17 - Model routing + Agent Monitor TUI (current)

- **Group A (Chat_HAND) COMPLETE + reviewed:** `gateway/model-routing.json` is the single source of truth; `gateway/lib/routing.mjs` proves the argv the runner will execute matches it and rejects drift/injected `--model` before any approval. Writer model pinned to `opencode-go/deepseek-v4.1-flash` (root cause of job `2656de34` was an unpinned writer falling back to `qwen/qwen4-max`). Preflight 17 checks PASS, **live smoke PASS**, routing tests 17/17, orchestration 22/22, relay 25/25, control plane 40 pass + 1 not tested. Independent review round 2: **ACCEPTED**. Docs: `docs/AGENT_ROUTING.md`.
- **Group B (EIMS) COMPLETE + reviewed:** `scripts/agent-monitor/Watch-EimsAgentJobs.ps1 -Dashboard` (O/A/H/L/R/Q, alternate buffer, VT + plain fallback, terminal restored on every exit). Data layer corrected: explicit `State` (a bare folder is never Running), frozen/floor elapsed, Int64 exit codes, bounded 64 KiB tail reads, sanitised logs with explicit truncation, historical-vs-new alert watermark. **96 assertions pass on Windows PowerShell 5.1**; empty-root and real-root `-Dashboard -Plain` runs verified. Independent review round 3: **ACCEPTED**.
- Limitations: PEM body masking is header-only; classic `-Watch` prints one squashed line per chunk; live smoke is opt-in (spends credits, never retried on low credit).
- Boundaries: no commit/push/deploy; no operational DB/Redis/MinIO/credential access; `scripts/agent-monitor/` remains untracked; no tracked EIMS application file was edited by this task.

## 2026-11-19 - Local-First Infrastructure Necessity Audit (current, read-only)

- **Status:** AUDIT COMPLETE — **no** Compose/profile/script/removals implemented. Owner review required before any infrastructure change.
- Deliverable: `docs/architecture/LOCAL_FIRST_INFRASTRUCTURE_AUDIT.md`
- Branch/HEAD recorded in audit: `demo/2026-11-24` @ `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de`; worktree preserved; no commit/push/reset/clean/stash.
- Headline: Core daily = Portal + API + PostgreSQL + Redis + MinIO; PgBouncer unused on default `:5432` path; Prometheus/Grafana = optional engineering profile; Loki = removal candidate (no in-repo consumer; ready 503); largest RAM waste is disposable PG leftovers (~2 GiB), not Grafana alone.
- Next: owner decides per-service; prefer Compose profiles + bat default to Profile A; do not delete volumes.

## 2026-11-19 - Local-First Infrastructure Consolidation (current)

- **Status:** **ACCEPTED WITH LIMITATIONS** — implementation complete; see `docs/acceptance/LOCAL_FIRST_INFRASTRUCTURE_CONSOLIDATION_ACCEPTANCE.md` and `docs/operations/LOCAL_OPERATIONS_RUNBOOK.md`.
- Compose profiles: default Core (PG/Redis/MinIO); `observability` (Prometheus+Grafana); `pooler` (PgBouncer); `full` = Core+both. Loki removed from active Compose runtime (container removed; no named volume).
- `start_eims.bat` starts Core only (loopback API/Portal). Optional scripts: `start_eims_observability.bat`, `start_eims_pooler.bat`, `start_eims_full.bat`, matching stops.
- Portal `/api/infra-status` adds **NOT_ENABLED** for optional Observability when profile not expected.
- Disposable `eims-knowledge-b-pg-20261119` (~2.17 GiB) removed after label verification; portal-accept + recovery PG deferred.
- Tests: `tests/test_system_infrastructure_consoles.py` **9 passed**, exit 0. No commit/push; no `down -v`; Operational DB untouched.

## 2026-11-19 - Analyzer P0 UI + Incident embed (current)

- **Status:** **ACCEPTED WITH LIMITATIONS** for P0 UI correction — see `docs/acceptance/ANALYZER_INCIDENT_UI_P0_ACCEPTANCE.md`. Full Analyzer↔Incident E2E on shared runtime still open.
- History was not deleted; standalone `/incidents` list misled the normal workflow. Cursor embedded Claude's `EventIncidentLink`/`IncidentWorkspace` into Log Analyzer; redirects `/incidents?id=` → `/analyzer?incident=`; removed Incidents sidebar entry; fixed History mojibake; restored Infra nav; Observability starts with Core by default.
- Tests: `test_system_infrastructure_consoles.py` **10 passed**. Portal was not running on `:3001` during this pass (API `/ready` OK).

## 2026-11-19 - Settings + Prometheus proof + Incident CTA (current)

- **Status:** **ACCEPTED WITH LIMITATIONS** — `docs/acceptance/SETTINGS_PROMETHEUS_INCIDENT_CTA_ACCEPTANCE.md`
- Settings: Configuration tab (language/sort/theme) + Runtime Diagnostics tab (former read-only health).
- Incident: Create/Open/Link CTA at top of Event Detail + post-analyze modal.
- Prometheus: `eims_fastapi` target **up**, `up{job="eims_fastapi"}=1`, HTTP rate query non-zero after synthetic traffic; Grafana provisioning + EIMS Operations dashboard mounted.
- Tests: `test_system_infrastructure_consoles.py` **12 passed**.

