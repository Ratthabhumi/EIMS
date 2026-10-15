# Engineering verification — stabilization, 15 October 2026

Fresh local verification started from `552cf57` in the canonical EIMS directory, with the reviewed stabilization changes. Results are local, not GitHub CI. Windows, existing Python3.14 venv, Node24.18, Next16.3, installed Playwright/Edge; no operational application lifespan or database access.

| Check | Fresh result | Evidence / boundary |
|---|---|---|
| Selected isolated Python suites | **238 passed**, 0 failures, 0 errors; 10.396s | test-results/stabilization-engineering.xml; 5 existing deprecation warnings; not an unrestricted suite |
| TypeScript noEmit | PASS | noEmit, incremental false; executed before successful build |
| Production build after final client change | PASS | webpack, 44s compile, 32.4s TypeScript, 12 routes; process exit0 |
| Actual export escaping helper | PASS | node tests/report_export_safety.cjs; unchanged nested escape behavior; not proof of successful browser export |
| Facilitator T1–T4, actual API/SQLite | **PASS, headed** | Latest facilitator-preflight.json: tasks=PASS, exports=NOT RUN, headed=true, humanEvaluation=false; exact launcher path, original fixtures and stored History IDs |
| Full workflow including exports | **FAIL / not revalidated** | Browser disconnected during Markdown download; other attempts also closed during startup. Do not carry forward the previous export PASS as a fresh result |
| Independent download controls | Mixed | Plain-text download passed; immediate-release Markdown control failed; delayed-release Markdown control passed. This does not prove the application failure's sole root cause |
| Syntax, Compose, diff and added-content screen | PASS where recorded | Static checks only; no secret values resolved or service started |
| Human testing / PostgreSQL / real OCR / production deployment | NOT RUN | No participant results, live database queries or production-readiness claim |

## Verified defects and decisions

The old reconstructed-request forwarder sent the two-file Veeam upload as empty content. Their original sizes are 85 and 100,030 bytes. The launcher now preserves native browser multipart bytes with a URL rewrite to the guarded test API. Test-only CORS allows only http://127.0.0.1:3115; assertions also reject an unrelated origin. Actual browser T2/T3 now finds the original line 1001 and correlation `none`. No shared job identifier was invented.

The launcher is now importable by its own regression, has explicit close handling with routes retained until context teardown, and the test records a result receipt plus a 120-second deadline. An observable React mode transition precedes language selection to avoid selecting server-rendered HTML before hydration. An early probe text was incorrectly placed outside an event block; it was corrected without changing original fixtures.

Markdown download lifecycle now follows the asynchronous click/delayed Blob URL release strategy present in the installed jsPDF/FileSaver code. A shorter delay did not resolve the full application regression. **The mitigation is implemented and builds, but export reliability remains unverified.** Do not describe it as a confirmed root-cause fix. No browser/endpoint security policy was changed.

## Minimal reproduction

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_investigation_quality.py tests/test_upload_security.py tests/test_repository_config_policy.py tests/test_analyzer_reliability.py tests/test_diagnostic_catalog.py tests/test_auth_modes.py tests/test_windows_shutdown_context.py tests/test_history_sandbox.py -q -o addopts= --junitxml=test-results/stabilization-engineering.xml
node tests/report_export_safety.cjs
```

From clients/dashboard: `node node_modules/typescript/bin/tsc --noEmit --incremental false` and `npm run build -- --webpack`. Start only the dedicated preview 3115 and guarded API 3116, using [the existing runbook](ISOLATED_HISTORY_RUNBOOK.md). With installed Playwright/Edge environment variables and EIMS_PREFLIGHT_HEADED=1, run `node tests/history_persistence_ui.cjs --tasks-only`. Omit --tasks-only for the currently failing export regression. A receipt with RUNNING or exports=NOT RUN is not evidence of successful export. Keep failed attempt logs private/synthetic.

## Traceability and limits

| Requirement / decision | Current acceptance evidence | Remaining boundary |
|---|---|---|
| FR-01; DD-12; NFR-S01 | Native two-file UI upload reaches actual isolated API; CORS allow/deny assertions; existing bounds/OCR tests | No operational deployment/privacy clearance |
| FR-02/03/05; DD-11 | Provider-qualified41/6008 fixture, no inferred power-loss cause, original timestamp/zone strings; selected Windows regressions | Permitted workplace formats and engineer needs unconfirmed |
| FR-04; DD-12 | Original negative Veeam fixture and original source/line 1001 shown and retained | No causal association inferred |
| FR-06; DD-12/13; NFR-A01 | Exact saved Windows/Veeam IDs reopened by keyboard through real SQLite History | PostgreSQL/vector fidelity and export regression remain open |
| NFR-U01 | Neutral T1–T4, consent/metrics and requirement confirmation remain blank | Software preflight is not human usability evidence |

The earlier213/238-test reports remain historical; do not add preliminary subsets or repeated runs to the current 238 count. Unchanged catalog-only mock UI checks were not rerun in this minimal pass. The historical three-row auth incident remains open for owner review; no affected row was queried or changed here.
