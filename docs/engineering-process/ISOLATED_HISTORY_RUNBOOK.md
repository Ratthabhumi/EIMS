# Synthetic History evaluation environment

Run only from the canonical `EIMS` directory. This optional harness uses a real on-disk **SQLite** database and the actual Analyzer/History routes and ORM History table. It does not start `backend.main`, workers, migrations, PostgreSQL, MinIO or seeders. It overrides identity with `synthetic-evaluation`; auth enforcement is tested separately. It disables external search, AI, translation, embedding retrieval and vector export. It is not PostgreSQL compatibility or production validation.

## Isolation proof and startup

Install the optional `tests/requirements-integration.txt` into the existing Python environment. Start `python -m tools.history_sandbox --port 3116`. It creates one uniquely named local directory under `.local-private/test-environments/eims-test-*` with an ownership marker and `history-test.sqlite3`. The guard checks marker purpose, resolved directory identity, local path and exact database filename before engine construction and before session access. Network database dialects, credentials/hosts, undeclared files, URI query options, memory databases and UNC roots are refused. SQLite has no database password; access relies on local filesystem permissions. A separate PostgreSQL username is not reused or needed. Run on a trusted local account and do not expose the server beyond loopback.

The tests actively check that operational engine initialization and asyncpg connection attempts fail. Only `AnalysisHistory.__table__` is created. Test teardown disposes that engine; it never deletes data outside disposable pytest resources. The evaluation server leaves its synthetic database in the ignored private directory for later review. No operational database was queried to assert absence of new records; isolation is established by the enforced write target and blocked operational entry points.

Build the UI using `npm run build -- --webpack` from `clients/dashboard`, then start a separate preview on `127.0.0.1:3115`. For automated end-to-end checking run `node tests/history_persistence_ui.cjs` with `EIMS_PLAYWRIGHT_MODULE` set if needed and `EIMS_UI_BROWSER=msedge`. Its shared facilitator launcher rewrites the native browser request URL to the actual test API; it does not reconstruct multipart bodies or invent responses. The sandbox permits CORS only from http://127.0.0.1:3115. Operational configuration is unchanged. It checks actual UI submission, matching stored History ID, keyboard retrieval and MD/PDF export. The two earlier UI scripts still use mocked APIs and remain a different verification layer.

## Human sessions

For a manual session, the default production UI API address is operational and **must not be used**. With the sandbox and preview running, use `node tools/open_history_evaluation.cjs` (same Playwright module/browser environment variables). It checks the test API's `/__sandbox` identity before opening a fresh visible browser and forwards API calls only to port 3116. Other external requests are blocked. Keep that process open during T1–T4; close its browser to finish. Do not use an ordinary browser tab or replace operational `.env` values. The exact launcher is exercised by tests/history_persistence_ui.cjs. Use --tasks-only for T1–T4; omit that flag to include Markdown/PDF regression checks. Set EIMS_PREFLIGHT_HEADED=1 to run the automated preflight in a visible browser. No participant session was conducted; the current measured outcome is recorded in ENGINEERING_TEST_REPORT.md.

Use synthetic fixtures only and the prepared T1–T4 scripts. Record actual build, session, fixture and viewport privately. Do not invite participants or fill metrics/results on their behalf. Do not manipulate the three historical operational service-session rows.

## Exact local facilitator startup

Open three terminals, all using the original EIMS checkout. Keep the first two running until the session ends. Wait for the dedicated services to start; the launcher refuses an unavailable or mismatching sandbox.

1. From EIMS: `.\venv\Scripts\python.exe -m tools.history_sandbox --port 3116`.
2. From EIMS/clients/dashboard, after the verified build: `node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3115`.
3. From EIMS, configure the installed Playwright/Edge and open the participant browser:

```powershell
$env:EIMS_PLAYWRIGHT_MODULE="$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\playwright"
$env:EIMS_UI_BROWSER="msedge"
node tools/open_history_evaluation.cjs
```

Before each human session, use the neutral task sheet and confirm synthetic fixtures. The automated equivalent is `node tests/history_persistence_ui.cjs --tasks-only`; this does not collect human metrics. Close the evaluation browser to end its session; stop only the dedicated test servers afterward. Do not run a database reset or delete private evaluation evidence. The deployment health panel may show unavailable services because this sandbox deliberately omits operational health/cache/vector services; do not interpret it as a PostgreSQL or production health check. Human requirement confirmation and consent remain necessary.

Current readiness is **READY** for synthetic T1–T4 including exports: the latest headed tasks-only preflight passed, and the full export regression (Analyzer MD/PDF, History MD/PDF) passed in 3 consecutive runs. The launcher automatically adds `--headless=new` when running headlessly, resolving previous msedge disconnections. Run tasks-only preflight before each participant session. If browser closure recurs, classify as environment failure, not participant error.
