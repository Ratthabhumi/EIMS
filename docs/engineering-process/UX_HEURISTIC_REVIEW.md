# Source-based UX heuristic review

This is a code/heuristic inspection, not a human usability study. Integrated dashboard components are the core; standalone client is preserved as legacy/needs review. Browser checks, if available, are recorded in the engineering test report.

| Area | Source observation | Action / status | Need |
|---|---|---|---|
| Input modes / analyze action | Analyzer page offers text, file and bundle paths | Retain modes; inspect labels and file selection during T1/T2 | FR-01 |
| File feedback / error state | Client and server can disagree on accepted type; malformed single-file errors | Tighten server rules with actionable 4xx; keep clear allowed types | NFR-E01/S01 |
| Source / catalog navigation | History and catalog already have separate tabs and source filtering | Preserve improvements from supervision branch | FR-02/06 |
| Evidence versus explanation | Generic possible causes can appear beside original evidence | Explicit possible-cause disclaimer and evidence-grounded gates | FR-03/05 |
| Confidence | Bare confidence label; route can supply medium without evidence match | Clarify diagnostic match versus cross-file association; remove fallback | FR-05 |
| Missing metadata / counts | UI and PDF filled absent channel/computer/severity with plausible defaults and displayed a hardcoded one-event count | Show Not supplied; remove unmeasured count; browser negative assertions | FR-03/05 |
| Original source | Existing evidence items show filename and line | Preserve; test T3 discoverability and keyboard traversal | FR-04 |
| History/search | Existing history IDs, sort/search and saved details | Regression checks; T4 measures retrieval with real user | FR-06 |
| Export | Existing JSON/Markdown download callbacks | Do not claim privacy-safe export automatically; review identifiers | NFR-S01 |
| Responsive/accessibility | Existing responsive classes and form labels | Automated viewport/keyboard checks where supported; full audit not claimed | NFR-A01 |

User needs link through REQUIREMENTS_TRACEABILITY_MATRIX.md. Cosmetic changes unrelated to investigation are out of scope. No new user success/time results are inferred from code inspection.
