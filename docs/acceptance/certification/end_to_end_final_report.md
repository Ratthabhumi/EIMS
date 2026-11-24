# End-to-end final report (2026-11-22, updated)

Flow: Catalog → Adapter → Draft → Human review → Decision API → Governance overlay → Analyzer → Dashboard. Disposable PostgreSQL only (`eims_incident_test`, `eims_analyzer_it` in a disposable container); no operational database; no migration applied.

## Baseline reconciliation
Repository `C:\Users\MewMew\Desktop\Co-op\EIMS`, branch `demo/2026-11-24`, HEAD `3f2beea`, 338 working-tree entries (pre-existing dirty and untracked files preserved; nothing staged, committed or pushed; the forbidden file was not touched). Figures re-derived from artifacts regenerated this pass: **911 governed records; 1 ELIGIBLE; 42 BLOCKED; 868 INELIGIBLE; 0 human approvals** (class A 153, B 39, C 312, D 4, E 57, F 346). No count changed: the seven records that gained evidence are class E, which the adapter rules out by design. Content hashes of those seven changed (so any evidence bound to them would be stale; none existed).

## Lifecycle checks
| Case | Result | Evidence |
|---|---|---|
| Eligible record | PASS | ASA 113005: ELIGIBLE (operational completeness; evidence freshness is checked offline and is stated as the basis) |
| Blocked record → draft → human review | PASS | PostgreSQL deadlock record: DRAFT → HUMAN_REVIEW in the browser; an UNVERIFIED draft never completes the record |
| Reference/unmapped suppression | PASS | no guidance for unmatched input (browser); no proposal path (tests) |
| Missing rollback / verification visible | PASS | NOT STATED / UNVERIFIED rows and a "Missing for operational use" list (browser) |
| Stale hash / source change, stale approval | PASS in tests and now in the browser: draft and approved supplement become STALE, submit refused, re-approval refused, Analyzer stops using the approved supplement |
| AI cannot decide or submit; author cannot approve own supplement; unauthorized human refused | PASS | 42 gate cases, PostgreSQL tests (403/401) |
| Access policy (open reads, protected writes) | PASS | `test_reads_follow_open_access_but_every_write_requires_the_reviewer_capability` (reads open by owner policy; all writes 401/403 for anonymous, non-reviewer, shared token, expired and unknown identities) |
| Append-only history, idempotent drafts | PASS | PostgreSQL tests |
| No synthetic-to-human promotion | PASS | events by `synthetic-browser-review` exist only in the disposable DB; certification counts come from repository artifacts (0 approvals) |

## Test counts (finished code, this pass)
| Command | Passed | Failed | Skipped |
|---|---:|---:|---:|
| `pytest tests --ignore=tests/test_analyzer_postgres_integration.py` | **2107** | **0** | **51** |
| `pytest tests/test_analyzer_postgres_integration.py` | **75** | **0** | 0 |
| `npx tsc --noEmit` (`clients/dashboard`) | clean | | |
| `next build --webpack` (copy of the latest source) | built, routes compiled | | |
Targeted runs before the full run: draft + governance + adapter 23/23 after the read gate; certification, adapter, catalog, overlay, guidance-UI group failed only on regenerated artifacts and a hard-coded URL assertion, then passed.
**Infra note:** the first analyzer-PG run failed 12 tests because my own browser acceptance had left three synthetic analysis rows (ids 1095–1097, usernames `demo` and `synthetic-browser-other`, created during this session) in the shared disposable database; I deleted exactly those rows and the suite passed (75/0/0). This was test-data contamination, not a code defect. Skips are environment-gated (for example Redis-backed tests) and are not passes. Not run: the Turbopack build inside the repository.

## Changed files this pass
Backend: `backend/api/routers/analyzer/knowledge_governance.py` (reads require reviewer), `backend/domain/knowledge/proposals.py` (eligibility basis), `backend/domain/analyzer/services/vendor_diagnostic_catalog.json` (`operational_fields` on 7 more candidates, applied by `tools/apply_remediation_fields.py` after live quote verification). Frontend: `clients/dashboard/src/app/knowledge/review/page.tsx` (new page and fixes). Tests: `tests/test_draft_proposal_workflow_pg.py` (read-gate test), `tests/test_knowledge_governance_api_pg.py`, `tests/test_catalog_adapter.py`. Regenerated artifacts: register, findings disposition, eligibility (JSON/CSV), knowledge-model mapping, class B package, remediation ledger, `remediation_fields_curated.json`. Reports and `screenshots/` under `docs/acceptance/certification/`.
Commands: see the table above; research used `tools/apply_remediation_fields.py --cache <dir>` (dry run, then `--apply`), then `tools/build_certification_register.py`, `build_findings_disposition.py`, `catalog_import.py` (dry run), `analyze_knowledge_model.py`, `build_class_b_review_package.py`, `build_remediation_ledger.py`.

## Cleanup
Stopped the backend and dashboard test servers; the user's own dev server was left alone. The isolated dashboard copy and cached vendor pages live in the session scratch directory outside the repository. No repository files were removed.

## Addendum (third pass)
Changed: `knowledge_governance.py` (reads open), `tests/test_draft_proposal_workflow_pg.py`, `review/page.tsx`; added `reviewer_sourcing_and_qualification_report.md`, `asa_113005_review_package.md`, `cisco_five_page_review_assignments.md`, `screenshots/reviewer_stale_state.jpg`. Affected tests: 23 passed (draft workflow and governance API). Full-suite counts above are from the previous code; analyzer-PG unchanged (75 passed then). Synthetic evidence left in the disposable DB: stale-test users, a supplement approved by synthetic reviewers, drafts; all labelled synthetic and excluded from certification counts. The synthetic stale harness lives in the session scratch directory, not in the repository.
