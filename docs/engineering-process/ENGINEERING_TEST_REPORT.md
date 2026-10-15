# Engineering test report — consolidated EIMS, 15 October 2026

## Current environment and results

All fresh checks below ran from the canonical `C:\Users\Ratthabhumi\Desktop\CO-OP_Project\EIMS` checkout. Windows; existing Python 3.14 venv; Node 24.18.0; Next.js 16.3.0; Edge/Playwright. Optional aiosqlite 0.22.1 was installed into the existing venv; no new environment/worktree was created. No operational app lifespan, database query, service restart or credential change was performed in this continuation. The prior auth incident remains documented separately.

| Check | Fresh result | Evidence / boundary |
|---|---|---|
| Selected isolated Python suites | **238 passed**, 0 failures, 0 errors, 17.781 seconds | test-results/consolidated-engineering.xml; 5 deprecation warnings; not the unrestricted repository suite |
| Windows regressions before implementation | 7 failed, 6 passed | windows-context-before.xml; actual missing provider/multi-event/1074 evidence gaps |
| Additional negative-provider/OCR regressions before repair | 5 failed, 27 passed | consolidation-additional-before.xml; wrong-provider curated causes and 8-billion-pixel resize request reproduced without allocating that image |
| Actual isolated DB integration | 7 passing cases included in the combined count | test_history_sandbox.py: 5 refusal/identity cases and 2 actual API/persistence cases; on-disk SQLite, not mocks or PostgreSQL |
| TypeScript | PASS | noEmit, incremental false, exit 0 before production build |
| Next.js production build | PASS | webpack; compilation 80 s, TypeScript 10.5 s; all 12 routes generated; exit 0 |
| Report export helper | PASS | node tests/report_export_safety.cjs; actual recursive escape helper; original values preserved |
| Catalog/history UI with synthetic responses | PASS | analyzer_catalog_ui.cjs; 163 catalog entries, Windows141, source filtering, duplicates, sorting, references, 1024/1366 layouts |
| Investigation UI with synthetic responses | PASS | investigation_workflow_ui.cjs; keyboard two-file selection, provenance line1001, uncertainty, missing metadata, 1024 layout |
| Real UI → isolated API → DB → History | PASS after retry | history_persistence_ui.cjs; real submitted analysis and exact History ID; keyboard retrieval; actual MD/PDF downloads, PDF header and escaped HTML DOM; responses forwarded, not invented |
| Compose syntax / Git diff / privacy screen | PASS where recorded in local review receipt | config --no-interpolate --quiet; obsolete Compose version warning; no values resolved/services started |
| Facilitator headed launcher | Syntax PASS only | open_history_evaluation.cjs; preflight required before actual participants |
| Formal UML Use Case | PlantUML source reviewed | ANALYZER_USE_CASE.puml; rendered visual verification NOT RUN |
| Human evaluation | NOT RUN | All participant metrics, consent and requirement responses blank |
| PostgreSQL-specific persistence, vectors, deployment auth and physical USB | NOT RUN | SQLite and overridden test identity do not establish these capabilities |
| Real Tesseract recognition / full accessibility / latency benchmark | NOT RUN | OCR resize/timeout calls are mocked for safe resource assertions; no certification or measured UX improvement |

The earlier 213-test baseline and intermediate 233-test run are historical/subsets; do not add them to the final 238 count. Five warnings are dependency/TestClient and existing naive-UTC ORM timestamp deprecations. The first live-UI attempt timed out before a submit response; the later retry completed successfully. The intermittent browser automation limitation is retained, not hidden as a product fix.

## Reproduction

```powershell
python -m pytest tests/test_investigation_quality.py tests/test_upload_security.py tests/test_repository_config_policy.py tests/test_analyzer_reliability.py tests/test_diagnostic_catalog.py tests/test_auth_modes.py tests/test_windows_shutdown_context.py tests/test_history_sandbox.py -q -o addopts= --junitxml=test-results/consolidated-engineering.xml
node tests/report_export_safety.cjs
docker compose config --no-interpolate --quiet
git diff --check
```

From clients/dashboard: `node node_modules/typescript/bin/tsc --noEmit --incremental false`, then `npm run build -- --webpack`. Use a separate preview on loopback3115; EIMS_UI_URL selects that preview. EIMS_PYTHON selects the existing venv for the catalog script; EIMS_PLAYWRIGHT_MODULE and EIMS_UI_BROWSER=msedge select installed Playwright/Edge. Run the two original browser scripts. For history_persistence_ui.cjs first start the guarded API with `python -m tools.history_sandbox --port 3116`; see [runbook](ISOLATED_HISTORY_RUNBOOK.md). Its test DB path is generated, owned and checked; operational DB URLs cannot pass the SQLite-only guard. No operational records were read to compare counts: write-target enforcement and blocked operational entry points provide the isolation evidence.

## Requirement evidence

| Requirement | Test / observed acceptance | Remaining limit |
|---|---|---|
| FR-01; NFR-E01/P01/S01 | upload size/count/type/name/encoding, 4xx, extreme OCR aspect ratio and 30 s timeout | No real OCR executable/production proxy throughput proof |
| FR-02 | existing source/vendor/catalog tests; explicit missing Windows provider remains Unknown | Bounded demonstrated formats; no all-version claim |
| FR-03/05 | shutdown-context tests: 41,6008,1074,WER1001; supplied bugcheck; original order/zones; unrelated providers; no unsupported causes | Not a general incident correlator, calibrated causal probability or normalized cross-host timeline |
| FR-04 | long-file regressions and real negative-bundle persistence retain original file and line1001 | Binary/XML conversion provenance remains adapter-specific |
| FR-06; NFR-R01 | real SQLite write/query, same History ID through UI and API; original negative Veeam association stays none | PostgreSQL/vector/storage deployment behavior not exercised |
| NFR-A01/U01 | keyboard upload and History open; responsive checks; neutral T1–T4/blank confirmation package | Full WCAG and actual participant outcomes pending |
| NFR-M01 | Narrow changes, existing components, formal UML source, canonical report updates | No architecture rewrite or unrelated-module cleanup |

The [historical safety incident](TEST_SAFETY_INCIDENT.md) remains open for owner review: three prior operational synthetic session rows, no automatic deletion and uncertain earlier startup side effects. Corrected auth tests use a no-op lifespan and memory sessions; new DB tests use a separate minimal app and guarded local database.
