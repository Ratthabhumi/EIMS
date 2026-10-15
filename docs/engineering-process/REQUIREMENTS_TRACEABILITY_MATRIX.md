# Requirements traceability

All needs below originate in student-reported observations/design hypotheses and await engineer confirmation. First-hand project background is recorded as testimony (not formal data) in USER_PERSONA_AND_CONTEXT.md; related student/engineer inputs are logged as DD-15–DD-17 in DESIGN_DECISION_RECORD.md. Implementation evidence is source-based; automated acceptance results are reported separately in ENGINEERING_TEST_REPORT.md. No human task acceptance has been measured. Paths below are service/component basenames under the existing backend or integrated dashboard.

Current user-need status: **PROVISIONAL — AWAITING USER CONFIRMATION**. The facilitator preflight uses the same guarded launcher as participants; `tests/history_persistence_ui.cjs` connects FR-01/03/05 to the supplied 41/6008 fixture, FR-02/04 to the unchanged negative Veeam bundle and original line1001, and FR-06 to exact saved IDs retrieved through real SQLite-backed History. This is automated software acceptance, not user acceptance; fresh results are in [the test report](ENGINEERING_TEST_REPORT.md).

| ID | Pain point | User goal | UX decision | Technical component | Test case/file | Acceptance criterion | Result / evidence |
|---|---|---|---|---|---|---|---|
| FR-01 | Scattered inputs | Submit supported logs | Clear text/file/bundle modes and bounds | analyze.py; bundle.py | test_investigation_quality.py; test_upload_security.py; test_analyzer_reliability.py | Allowed input accepted; invalid name/type/size rejected without DB write | See engineering test report; user confirmation pending |
| FR-02 | Cross-vendor numeric ambiguity | Know the actual emitting product | Source-qualified identity; honest unknown | source_classify.py; parser.py; operational_catalog.py | test_diagnostic_catalog.py; test_analyzer_reliability.py | Windows/vendor identity remains isolated; unknown does not become Windows | See engineering test report; user confirmation pending |
| FR-03 | Unsupported suggestions | Read observed errors first | Separate evidence and possible causes | investigation.py; incident_extract.py | test_investigation_quality.py | 1129/41 do not gain unsupported causes; no unrelated CTK unknowns | See engineering test report; user confirmation pending |
| FR-04 | Cannot verify excerpts | Locate original evidence | File/line evidence view | evidence.py; bundle.py; AnalysisResultDetail.tsx | test_analyzer_reliability.py | Original task-log line 1001 survives long-file and bundle processing | See engineering test report; user confirmation pending |
| FR-05 | Confidence mistaken for cause | Understand limits and next checks | Diagnostic confidence and association labels; hypotheses disclaimer | summary.py; analyze.py; AnalysisResultDetail.tsx | test_investigation_quality.py; UI check | No unsupported medium fallback; no confirmed root-cause claim | See engineering test report; user confirmation pending |
| FR-06 | Repeated investigation | Retrieve same analysis | Preserve existing IDs and saved result view | history.py; models/history.py; AnalyzerHistoryList.tsx | test_analyzer_reliability.py; analyzer_catalog_ui.cjs; T4 human task | Legacy JSON remains readable; no new live DB claim | See engineering test report; user confirmation pending |

## Non-functional requirements

| ID | Need / design decision | Acceptance and verification |
|---|---|---|
| NFR-U01 Usability | T1–T4 tasks; neutral instructions | Collect success/time/assistance/errors and post-task ease; no numeric improvement claim before study |
| NFR-E01 Error handling | Actionable bounded errors | Invalid upload returns 4xx with no analysis or persistence; regression tests |
| NFR-P01 Performance | Bounded memory/input and responsive feedback | 5 MiB file/30 MiB bundle/12 files; latency benchmark NOT RUN; collect timing in isolated environment |
| NFR-A01 Accessibility | Explicit labels, keyboard operation, readable text | TypeScript/build plus keyboard/responsive browser checks where run; full WCAG audit NOT RUN |
| NFR-S01 Security/privacy | Env-based credentials, untrusted uploads, private evidence | Config checks + upload tests + staged secret/privacy screening; live rotation owner action |
| NFR-R01 Reliability | Synthetic reproducibility and backward compatibility | Regression suite; no workplace DB; source provenance stable; live persistence NOT RUN |
| NFR-M01 Maintainability | Narrow changes, existing modules, editable diagrams | Diff review; named tests linked to FRs; no module deletions |

Status vocabulary: observed student report / design hypothesis / awaiting engineer confirmation / implemented in source / verified by named automated check / NOT RUN. These are independent dimensions, not a fabricated maturity score.

## Follow-up acceptance evidence

All user needs remain **PROVISIONAL — AWAITING ENGINEER CONFIRMATION**; use evaluation/REQUIREMENT_CONFIRMATION_SHEET.md. FR-03/05: test_windows_shutdown_context.py requires matching provider, no invented bugcheck/cause, and preserved input timestamp/zone strings; it does not normalize absent zones or infer incident relatedness. FR-01 / NFR-P01/S01: test_upload_security.py includes extreme-aspect-ratio OCR allocation and timeout enforcement. FR-04/06: test_history_sandbox.py persists/retrieves the original negative Veeam bundle, including source line 1001, through actual routes and a guarded on-disk SQLite DB. history_persistence_ui.cjs verifies real frontend submission, exact saved ID, keyboard retrieval and History MD/PDF export. NFR-A01: keyboard History activation is covered. PostgreSQL compatibility and actual participant acceptance remain NOT RUN. Test evidence is centralized in ENGINEERING_TEST_REPORT.md.
