# Engineering test report — 15 October 2026

## Environment and claim boundary

Windows; Python 3.14 via the existing repository virtual environment; Node 24.18.0; Next.js 16.3.0; Edge/Playwright for browser checks. Development worktree starts at 8c26f03. Dependencies are reused from the original checkout; no workplace service restart or database reset was performed. Results are local, not CI on the eventual commit SHA. Historical 176-test and field metrics are not presented as new results.

## Measured checks

| Check | Result | Evidence |
|---|---|---|
| New evidence-boundary tests before fix | 10 failed, 1 passed | Actual initial pytest run: generic 1129 causes, CTK contamination, Event 41 cause and AI-gate failures |
| Final combined isolated Analyzer/catalog/investigation/upload/config/auth suite | 213 passed, 0 failures, 0 errors; 10.080 s | Local ignored test-results/engineering-delivery.xml; 3 dependency deprecation warnings |
| Corrected isolated auth suite | 4 passed, 0 failures, 0 errors; 1.039 s | Local ignored test-results/auth-isolated-final.xml; startup and direct DB calls replaced by memory stubs |
| Actual TS export helper | PASS | node tests/report_export_safety.cjs; nested HTML payload escaped, original evidence preserved |
| TypeScript no emit | PASS | node node_modules/typescript/bin/tsc --noEmit --incremental false; exit 0 |
| Next.js production build | PASS (final metadata revision; webpack and TypeScript; 12 routes) | npm run build -- --webpack; all 12 routes generated in initial successful build; final refreshed status above |
| Catalog/history browser workflow | PASS (Edge; intercepted synthetic API; successful retry) | tests/analyzer_catalog_ui.cjs; real browser with intercepted synthetic API |
| Investigation browser workflow | PASS (Edge; intercepted synthetic API; keyboard bundle selection and missing-metadata assertions; successful retry) | tests/investigation_workflow_ui.cjs; keyboard bundle selection, evidence and uncertainty labels |
| Compose static syntax | PASS | docker compose config --no-interpolate --quiet; no values resolved and no service started; obsolete version warning |
| Python syntax / added-content screen / diff whitespace | See final review receipt | Private DELIVERY_REVIEW_PRIVATE.json; candidates are reviewed without printing secret values |
| Human usability tasks | NOT RUN | Student must arrange eligible participants; templates remain empty |
| Physical USB scan/import on target | NOT RUN | Separate supporting workflow |
| Live Analyzer API/database integration | NOT RUN | No new Analyzer persistence claim; legacy auth incident is not Analyzer validation |
| Latency benchmark / production certification / full accessibility audit | NOT RUN | No controlled measurement or certification performed |

Final combined isolated Python evidence is **213 tests in one run**, with 0 failures and 0 errors. The earlier 207-test repaired run and 4-test isolated auth run are preliminary subsets, not extra tests to add to this count. Tests cover synthetic inputs and fake session storage. Browser API interception cannot establish live backend/database integration or human task success. The unrestricted whole-repository suite was not run; other operational integration fixtures still require isolation review.

## Reproduction

From the isolated repository root, with the project's Python interpreter:

```powershell
python -m pytest tests/test_investigation_quality.py tests/test_upload_security.py tests/test_repository_config_policy.py tests/test_analyzer_reliability.py tests/test_diagnostic_catalog.py tests/test_auth_modes.py -q -o addopts= --junitxml=test-results/engineering-delivery.xml
python -m pytest tests/test_auth_modes.py -q -o addopts= --junitxml=test-results/auth-isolated-final.xml
node tests/report_export_safety.cjs
docker compose config --no-interpolate --quiet
git diff --check
```

From clients/dashboard: `node node_modules/typescript/bin/tsc --noEmit --incremental false` and `npm run build -- --webpack`. Use a separate local preview, never an active operator port. Set EIMS_UI_URL to that preview, EIMS_PYTHON to the chosen interpreter, EIMS_PLAYWRIGHT_MODULE if needed, and EIMS_UI_BROWSER=msedge; run both browser scripts from the repository root. They intercept synthetic API data and must not reach operational endpoints. Raw output/screenshots/JUnit files remain local because they can contain machine identifiers; publish only sanitized summaries.

## Traceability

| Requirement | Evidence | Acceptance / remaining gap |
|---|---|---|
| FR-01 / NFR-E01/S01/P01 | test_upload_security.py; test_repository_config_policy.py; existing bounded-read tests | Type/name/content/size rejection and 4xx pass; no throughput/latency conclusion; text encoding is bounded to UTF-8 |
| FR-02 | test_diagnostic_catalog.py and source-classification regressions | Source isolation and documented vendor formats pass; no universal format claim |
| FR-03 | test_investigation_quality.py | 1129/41 evidence gates and non-vendor negative controls pass; not a universal diagnostic accuracy score |
| FR-04 | existing long-file/bundle route tests | Original source and line 1001 retained under compaction and reordered uploads |
| FR-05 | confidence route regression; UI scripts; legacy-schema test | No unsupported medium fallback; diagnostic and cross-file meaning distinguished; old stored conventions disclosed |
| FR-06 / NFR-R01 | history helper/route regressions; catalog/history browser script | Fake storage/legacy reading checks; live persistence NOT RUN |
| NFR-U01/A01 | Prepared T1–T4 package; keyboard/viewport browser checks where passed | Human evaluation and full accessibility audit pending |
| NFR-M01 | Syntax, diff review, small modules and linked requirements | No architecture rewrite or source module deletion |

## Failed checks and repairs

An early upload parametrization embedded the 5 MiB payload into pytest's automatic test ID, exceeding Windows' environment-variable limit during setup/teardown. Explicit short IDs fixed the harness. A configuration policy check incorrectly treated token expiry minutes as a secret; that non-secret setting is now excluded. These are harness repairs, not product accuracy claims.

The first browser attempt timed out on initial navigation; subsequent inspection also detected that the production snapshot preceded the last keyboard-label change. The build was refreshed. One later catalog attempt failed during Edge launch before reaching the page, while the new investigation UI script passed. The investigation file-chooser check also timed out on one attempt; a diagnostic run and unchanged final script retry passed, so intermittent browser automation remains a limitation. Record only final results above, including the catalog retry outcome; do not treat stale-build or browser-launch failures as successful checks.

An overly broad run of the legacy auth suite started the real application lifespan and wrote **three synthetic service-session rows**. It is excluded from isolated results. The corrected auth fixture now removes operational startup and session access; the first isolation attempt also exposed a direct auth-module DB lookup, which was then replaced with a memory session generator. See [test safety incident](TEST_SAFETY_INCIDENT.md). No automatic database rollback/deletion was performed; exact identifiers are private and owner review is required.
