# EIMS — 2026-11-15 Final16 Runtime Alignment and Release Gates

Date: 2026-11-15  
Machine: Mew (Windows 11)  
Repository: `C:\Users\MewMew\Desktop\Co-op\EIMS`  
Branch / HEAD: `integration/eims-consolidated` / `85493b2`  
Execution path: Remote Desktop Commander on Mew only. Work Mode was not used.

## 1. Executive status

The latest synthetic Browser Acceptance is PASS and the production application path has a successful synthetic smoke. The project is **not yet release-closed** because diagnostic quality still lacks independent human-reviewed gold data, the production knowledge database has no approved incident entries, and operational recovery sign-off remains incomplete.

Do not describe the synthetic acceptance stack as a production deployment. No customer data was used and no Operational DB was accessed.

## 2. Runtime alignment and root causes

### Dedicated services

- Dashboard Next server: loopback port 3009.
- HTTPS reverse proxy: loopback port 3449.
- Backend: loopback port 8000.
- Disposable PostgreSQL container: `eims-acceptance-pg-20261115`, host port 56443.
- Disposable Redis: host port 56380, Redis DB index 5.
- Disposable MinIO: host port 59002, dedicated acceptance bucket.
- Browser Acceptance app: `tests.analyzer_synthetic_demo_app:app`, using `eims_regression_test_20261115`.
- Production application smoke: `backend.main:app`, using `eims_browser_acceptance_20261115`.

The Browser Acceptance and production application smoke deliberately used separate databases. The production smoke database was cloned from the fully migrated regression database and received only the synthetic user rows needed for login. The original `eims_integration_test` database was preserved; it was not renamed, dropped, or truncated.

### Confirmed corrections

- Earlier 401 behavior was caused by a stale backend/runtime configuration pointing at a different synthetic DB/service set than the Browser Acceptance stack.
- Starting `backend.main` for the browser harness caused a Diagnostics 404 because the browser contract belongs to `tests.analyzer_synthetic_demo_app:app`. The correct harness was restored; production backend smoke was then tested separately.
- The synthetic harness resets its synthetic fixtures at startup. A Playwright rerun without restarting it reused a prior approved Knowledge fixture and created duplicate title matches. The harness now generates a unique Knowledge title per run, and final16 used a fresh harness process.
- The final14 404 from `POST /api/v1/analyze/followup` was the intended owner check: the route exists and returns 404 when the requested History belongs to another user. It was not a missing route.
- Health probe tuning remains in place: dedicated health pool avoids duplicate pre-ping, MinIO read budget aligns with the health-fetch budget, healthy snapshots live 20 seconds, and degraded snapshots retry within 3 seconds. A degraded result remains degraded/503; it is never relabeled healthy.

## 3. Acceptance evidence

### Browser Acceptance final14

- Status: PASS, 33/33 checks.
- Artifact: `test-results/secure-browser-acceptance-20261115-final14/secure-browser-acceptance.json`.
- Includes actual login, Secure/HttpOnly cookie, Thai/English Analyzer paths, paste/file upload, four concurrent Analyzer requests, provenance/history, Markdown/PDF downloads, Knowledge proposal, independent admin approval, exact-family/exact-diagnostic reuse, cross-user restrictions, logout, cookie replay, and server-side session expiry.
- Correlated HTTP 502/503: 0.
- Unauthorized Authorization-header injection: 0.
- The expiry assertion proves server-side session-row expiry while the JWT remains unexpired. It does **not** prove the JWT `exp` boundary.

### Full Playwright final16

- Status: PASS, 2/2 Playwright tests.
- Browser report: `test-results/secure-browser-acceptance-20261115-final16/secure-browser-acceptance.json` — PASS, 33/33.
- Playwright last run: `test-results/secure-browser-acceptance-20261115-final16/playwright/.last-run.json` — `status: passed`, `failedTests: 0`.
- Runner exit: `%TEMP%\eims-playwright-final16-exit-20261115.txt` = 0.
- final15 failed at the Admin Knowledge title locator because old synthetic fixture data remained in the already-running harness. This was corrected by unique per-run titles and a fresh harness process; final16 passed.
- A non-blocking harness warning says the Login POST body was not available within its observation window; the Secure cookie and authenticated-session checks remain authoritative.

### Production application smoke

Using `backend.main:app` on the fully migrated synthetic database:

- Backend startup completed without the prior Undefined Table/background-worker errors.
- Synthetic login: HTTP 200.
- Production Analyzer on the synthetic Windows Event 1129 fixture: HTTP 200.
- Follow-up against the saved History: HTTP 200.
- History retrieval: HTTP 200.
- Stats endpoint: HTTP 200.
- Current health endpoint: HTTP 200, status HEALTHY, PostgreSQL/PgBouncer, Redis, and MinIO all UP.
- The initial Node multipart probe produced a client-side body-serialization 400; it was corrected to an explicit URL-encoded Form request to the canonical trailing-slash route, after which the production Analyzer returned 200. Browser file-upload acceptance remains independently covered by final14/final16.

This is a production application-path smoke against synthetic data, not a production deployment or broad diagnostic-accuracy certification.

## 4. Focused regression and dependency updates

- Focused pytest: **88 passed**, 0 failures, 0 errors, 0 skips across Analyzer Investigation, ORM Models, API Controllers, and Global Search.
- Targeted Ruff import-order checks: PASS for the modified Python files.
- Python compilation and logger import smoke: PASS.
- `git diff --check`: PASS; Git reports existing LF-to-CRLF working-copy warnings only.
- Full Ruff is not clean: the earlier all-rules check reported legacy findings in `summary.py` and `stats.py`. Do not claim full-repository or full-file lint cleanliness.
- Replaced the deprecated `duckduckgo-search` import/dependency with `ddgs>=9.16.1,<10.0.0`; verified import, context-manager and text interface. Live search is optional enrichment; official static references and independently approved knowledge remain the authoritative basis.
- Replaced `datetime.utcnow()` uses in History defaults and Stats calculations. The legacy `analysis_history.created_at` column is PostgreSQL `timestamp without time zone`; code now creates explicit UTC-naive values to preserve the existing schema without an unnecessary migration.
- Updated the JSON logger import to `pythonjsonlogger.json.JsonFormatter`; production backend startup no longer emits the old import-path warning.
- Test framework still emits an httpx/TestClient deprecation warning; this is not a test failure.

## 5. Current knowledge coverage and gaps

### What exists

- Incident-derived Knowledge lifecycle: proposal, independent Admin review, source-history hash validation, reviewer rationale, approved-only retrieval, exact Source Family + Diagnostic Identity matching.
- The auto-reuse path intentionally remains exact-match only; do not broaden automatic remediation to fuzzy matches.
- Static deterministic catalog includes seven Broadcom official VMware articles plus network/Linux/vendor operational catalog entries. These are code-based references, not database rows.
- Browser Acceptance proves the Knowledge lifecycle and reuse with synthetic entries.

### What is still missing

- The dedicated production application smoke database `eims_browser_acceptance_20261115` currently has **6 History rows, 0 KnowledgeEntry rows, and 5 synthetic users**. The one approved entry in the Browser Acceptance database is synthetic test data, not a production seed.
- Knowledge search is filter-based (Source Family / Diagnostic Identity); it does not yet provide full-text search across symptoms, title, root cause, resolution, impact, prevention, and evidence.
- Knowledge schema lacks structured Product/Version/Environment applicability, prerequisites, risk level, validation steps, rollback steps, usage outcome, revalidation date, and stale/deprecation lifecycle.
- Current KnowledgeEntry provenance requires an originating History record. A standalone official-reference library cannot be curated independently without a separate reference-catalog model or a deliberate schema extension.
- No real Engineer pilot has yet established which knowledge entries are useful, safe, current, and reusable.

## 6. Analyzer quality gate

- Gold manifest: 17 cases total — 12 DEV and 5 HELDOUT.
- All 17 remain DRAFT; there are zero human-reviewed cases.
- The gold protocol explicitly forbids AI agents from creating human review status. Do not run review tooling to self-certify.
- Required sequence: independent domain reviewer annotates all DEV cases and binds reviews to exact fixture/prediction hashes; freeze Analyzer rules; only then unlock HELDOUT for final scoring.
- Until then, do not claim accuracy, precision, recall, or authoritative root-cause quality.

## 7. Remaining release gates

1. Independent human/domain review of the 12 DEV gold cases; then freeze and evaluate the five HELDOUT cases.
2. Curate an initial approved knowledge corpus from official vendor documentation and authorized/sanitized incidents. Add full-text search and structured applicability/safety metadata before broad Engineer rollout.
3. Add explicit JWT `exp` boundary tests separately from database session-row expiry and cookie replay.
4. Complete witnessed operational backup/restore, WAL/PITR, retention, measured RPO/RTO, failover/recovery, capacity/load, TLS/secrets, monitoring, and ownership sign-off. Earlier logical backup/restore evidence is historical and does not establish PITR.
5. Run a controlled Engineer pilot using authorized sanitized incidents; capture whether recommendations were correct, safe, and successful.
6. Reconcile README release claims only after the above gates are complete.

## 8. Preservation and safety

- Branch/HEAD remain `integration/eims-consolidated` / `85493b2`.
- No commit, push, reset, clean, stash, destructive cleanup, or Operational DB access.
- Preserve all existing modified and untracked paths; the working tree contains substantial pre-existing EIMS work.
- Current dashboard/backend processes use synthetic acceptance data. Do not point them at Operational DB.
- Keep Work Mode excluded; continue on Mew through Remote Desktop Commander.
