# Engineering verification — stabilization continuation, 15 October 2026

Fresh local verification from `57b78c1` (branch `work/eims-engineering-process-2026-10`). Results are local, not GitHub CI. Windows, Python3.14 venv, Node24.18, Next16.3, msedge 155.0.4283.45; no operational application lifespan or database access.

Continuation round (second machine, same branch): targeted suites rerun green (259 passed, §Second-machine appendix below); the 238-test selection, TypeScript, webpack build and export-safety check from the pushed report are adopted unchanged, not re-claimed as fresh runs except where re-executed here.

| Check | Fresh result | Evidence / boundary |
|---|---|---|
| Selected isolated Python suites | **238 passed**, 0 failures, 0 errors; 10.26s | 5 existing deprecation warnings; not an unrestricted suite |
| TypeScript noEmit | PASS | noEmit, incremental false |
| Production build | PASS | webpack, 12 routes, exit 0 |
| Actual export escaping helper | PASS | node tests/report_export_safety.cjs |
| Facilitator T1–T4 tasks-only (headless) | **PASS** | receipt: tasks=PASS, exports=NOT RUN, headed=false; 3 consistent runs |
| Facilitator T1–T4 tasks-only (headed) | **PASS** | receipt: tasks=PASS, exports=NOT RUN, headed=true |
| Full export regression (without --tasks-only) | **PASS** | receipt: tasks=PASS, exports=PASS, headed=false; 3 consecutive consistent passes |
| Analyzer Markdown export | **PASS** | analysis-export.md saved, contains 6008 |
| Analyzer PDF export | **PASS** | analysis-export.pdf saved, header %PDF-1.3, 9.4 MB |
| History Markdown export | **PASS** | history-export.md saved, contains expected sections |
| History PDF export | **PASS** | history-export.pdf saved, header %PDF-1.3, 9.3 MB |
| Human testing / PostgreSQL / real OCR / production deployment | NOT RUN | No participant results, live database queries or production-readiness claim |

**Root cause of previous export instability identified:** msedge with `--headless` (legacy mode) caused browser disconnection before downloads completed. Adding `--headless=new` to the launch args resolves this. The `open_history_evaluation.cjs` launcher now automatically adds `--headless=new` when headless mode is requested. The Playwright module is also auto-discovered from the codex runtime path if not installed globally.

## Verified defects and decisions

The old reconstructed-request forwarder sent the two-file Veeam upload as empty content. Their original sizes are 85 and 100,030 bytes. The launcher now preserves native browser multipart bytes with a URL rewrite to the guarded test API. Test-only CORS allows only http://127.0.0.1:3115; assertions also reject an unrelated origin. Actual browser T2/T3 now finds the original line 1001 and correlation `none`. No shared job identifier was invented.

The launcher is now importable by its own regression, has explicit close handling with routes retained until context teardown, and the test records a result receipt plus a 120-second deadline. An observable React mode transition precedes language selection to avoid selecting server-rendered HTML before hydration. An early probe text was incorrectly placed outside an event block; it was corrected without changing original fixtures.

Markdown download lifecycle now follows the asynchronous click/delayed Blob URL release strategy present in the installed jsPDF/FileSaver code. A shorter delay did not resolve the full application regression. **Historical note:** an earlier revision of this paragraph described export reliability as unverified because the full export regression was still failing at that time. That state is superseded: with `--headless=new`, the full export regression (Analyzer MD/PDF, History MD/PDF) passed 3 consecutive runs (see table above). The 3-run local Edge result is the measured evidence; it is not a universal cross-environment guarantee. No browser/endpoint security policy was changed.

## Minimal reproduction

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_investigation_quality.py tests/test_upload_security.py tests/test_repository_config_policy.py tests/test_analyzer_reliability.py tests/test_diagnostic_catalog.py tests/test_auth_modes.py tests/test_windows_shutdown_context.py tests/test_history_sandbox.py -q -o addopts= --junitxml=test-results/stabilization-engineering.xml
node tests/report_export_safety.cjs
```

From clients/dashboard: `node node_modules/typescript/bin/tsc --noEmit --incremental false` and `npm run build -- --webpack`. Start only the dedicated preview 3115 and guarded API 3116, using [the existing runbook](ISOLATED_HISTORY_RUNBOOK.md). With installed Playwright/Edge environment variables and EIMS_PREFLIGHT_HEADED=1, run `node tests/history_persistence_ui.cjs --tasks-only`. Omit --tasks-only to include the Markdown/PDF export regression checks (passing since the `--headless=new` fix). A receipt with RUNNING or exports=NOT RUN is not evidence of successful export. Keep failed attempt logs private/synthetic.

## Traceability and limits

| Requirement / decision | Current acceptance evidence | Remaining boundary |
|---|---|---|
| FR-01; DD-12; NFR-S01 | Native two-file UI upload reaches actual isolated API; CORS allow/deny assertions; existing bounds/OCR tests | No operational deployment/privacy clearance |
| FR-02/03/05; DD-11 | Provider-qualified41/6008 fixture, no inferred power-loss cause, original timestamp/zone strings; selected Windows regressions | Permitted workplace formats and engineer needs unconfirmed |
| FR-04; DD-12 | Original negative Veeam fixture and original source/line 1001 shown and retained | No causal association inferred |
| FR-06; DD-12/13; NFR-A01 | Exact saved Windows/Veeam IDs reopened by keyboard through real SQLite History | PostgreSQL/vector fidelity remains unverified |
| NFR-U01 | Neutral T1–T4, consent/metrics and requirement confirmation remain blank | Software preflight is not human usability evidence |

The earlier213/238-test reports remain historical; do not add preliminary subsets or repeated runs to the current 238 count. Unchanged catalog-only mock UI checks were not rerun in this minimal pass. The historical three-row auth incident remains open for owner review; no affected row was queried or changed here.

## Second-machine appendix (15 Oct 2026 continuation, this checkout)

Hermetic suites rerun here: **259 passed, 0 failed** (238 pushed selection + 7 network-denied offline + 6 sandbox E2E + 8 KB-quality, including a new Veeam causality-disclaimer guard). `GET /api/v1/analyze/capabilities` unit-verified (keys, 163 entries, honest vector/external-AI states). Dashboard `tsc --noEmit` and webpack production build pass with runtime capability labels.

Browser findings on this machine (Edge 155 headless=new, Playwright 1.62.1):
- T1–T4 tasks-only preflight: **PASS** (second environment; sandbox + preview in one process scope).
- Narrow controls (launch+load, bundle-tab file attach without submit): **PASS**; page console shows only backend-unreachable fetch errors (no backend running here).
- Full export regression (4 workflows): **BLOCKED — BROWSER ENVIRONMENT**. Reproducible 2/2 here: the browser context dies at the download step (`download.saveAs` / teardown), while a minimal data-URL download in the same browser passes and the identical HEAD passed 3× on the Codex machine. No product code path is implicated (tasks pass; download primitive works); do not present this box's export result as a product regression. Last known passing evidence (Codex machine, pushed commit) is preserved, not replaced.
