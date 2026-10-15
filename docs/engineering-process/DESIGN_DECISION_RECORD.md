# Engineering decision record

| ID | Trigger / user need | Decision and rationale | Verification / trade-off |
|---|---|---|---|
| DD-01 | Preserve working demo and private files | Separate worktree from verified supervision baseline | Original checkout unchanged; no broad staging |
| DD-02 | Investigate rather than guess | Narrow deterministic evidence gates for Windows 1129/41 before optional synthesis | Regression-first; uncertain causes remain empty, not replaced by generic hardware/network guesses |
| DD-03 | Avoid cross-domain contamination | Scope incident unknowns to actual source/signatures | Non-VMware negative controls; no global CTK/VMDK fallback |
| DD-04 | Confidence clarity | Remove automatic medium fallback and clarify diagnostic versus association meaning in UI | Keep old API field for compatibility; legacy records may retain older conventions |
| DD-05 | Secure input without rewriting pipeline | Reuse bounded reads and safe name/type rules; reject invalid uploads before parsing/persistence | Auth remains existing demo/secure policy; content validation is layered, not perfect |
| DD-06 | Preserve real scope | Log investigation is evaluation core; USB endpoint import stays separate | As-built diagrams reflect distinct pipelines; broader modules retained |
| DD-07 | Evidence before improvement claims | Prepare task evaluation with blank outcomes and anonymized data | Real participants arranged by student; no simulated human results |
| DD-08 | Public credential exposure | Prepare environment-driven configuration; do not rotate or restart | Publication gate records unresolved owner action; history remains exposed |
| DD-09 | Missing evidence must remain missing | Display Not supplied for absent metadata; remove the fixed event count in UI/PDF | Browser regression with omitted metadata; retain original API data |

Alternatives rejected: wholesale architecture rewrite, deleting old modules, guessing exfiltration from access events, treating catalog entries as validated incidents, and publishing all local files. Revisit only with specific evidence and bounded acceptance criteria.

## Follow-up decisions

| Decision | Problem / evidence | Implementation | Verification |
|---|---|---|---|
| DD-10 | Three original demo deletions and many private assets prevent clean branch transfer | Preserve deletion state in stash; detach old checkout; Git-switch original EIMS; move only untracked private assets with hashes | Ancestor/status/hash/ignore checks; SAFE_CLEANUP_PLAN.md |
| DD-11 | Provider was inferred from reused numeric IDs; 1074/6008/1001 could reach generic causes | Explicit provider gate and bounded Event Viewer blocks; unqualified IDs return insufficient evidence | Red regressions then test_windows_shutdown_context.py |
| DD-12 | Mock history could not prove persistence; full startup previously touched operational DB | Guarded file SQLite, actual History ORM/routes, no production lifespan, blocked network DB entry points | test_history_sandbox.py; history_persistence_ui.cjs |
| DD-13 | History had a separate unsafe PDF interpolation path and stronger wording | Reuse escapeReportData, uncertainty labels, absent metadata disclosure, keyboard activation | Actual History MD/PDF DOM/download and keyboard browser checks |
| DD-14 | Narrow image resize could expand 8,000 pixels to 8 billion pixels | Cap preprocessing to 8 MP and Tesseract runtime to 30 seconds per attempt | Failing extreme-aspect-ratio test before fix; bounded mocked resize/OCR regression |
| DD-15 | Engineer suggested file upload over paste-only text (student-reported) | Support single-file, bundle and HTML uploads with the same bounded pipeline | Upload/security regression tests; engineer confirmation of need still pending |
| DD-16 | Unreliable answers plus limited API budget (student-reported motivation) | Knowledge-first offline design: static catalogs, deterministic matching, local-first synthesis; cloud AI only via explicit per-request key; UI labels report verified runtime capabilities | test_offline_knowledge_first.py (network-denied); /api/v1/analyze/capabilities |
| DD-17 | Student-initiated multi-file and vendor expansion | Bounded formats only (Veeam/Fortinet/Cisco/PAN-OS subsets, Linux/JSON); unsupported input stays explicitly unsupported | Format-scoped regression tests; deployed product/version confirmation still pending |
