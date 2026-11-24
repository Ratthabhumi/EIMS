# Final workflow closure report (2026-11-22)

No stage, commit or push. `EIMS_11-8-2026.md` and `clients/dashboard/src/app/analyzer/page.tsx` untouched. No operational database used; no migration created or applied. Human review and approval: none exist (0 approved records).
Companion reports: `candidate_schema_report.md`, `draft_proposal_workflow_report.md`, `remediation_evidence_final_report.md`, `analyzer_ui_integration_report.md`, `end_to_end_acceptance_report.md`; earlier reports are preserved.

## 1. Baseline verified from files
911 governed records, eligibility artifact equal to a fresh computation (before this round: 3 eligible / 40 blocked / 868 ineligible), Human Decision API and `operationalGuidance` present, previous suite 2077 passed / 51 skipped / 0 failed and analyzer-PG 75 passed. Working tree: 333 entries at the start; the tracked-modified set is unchanged; only new untracked files were added this round.

## 2. What was closed
| Gap | Closure |
|---|---|
| Missing operational fields | one optional `operational_fields` block (8 fields, 3 states, source+quote+date for `stated`), loader-validated, hash-bound; existing fields reused |
| No draft path without fake history | proposals as append-only events in the governance store (CANDIDATE → DRAFT → HUMAN_REVIEW → APPROVED, plus STALE/REJECTED); preview/dry-run; idempotent; stale-aware; never read by the Analyzer until a human approves |
| Remediation evidence | PostgreSQL ×4 researched from official pages with verbatim, re-verified quotes; 5 Cisco manual; 16 not researched further; 0 became eligible |
| UI | additive panel with 12 STATED / NOT STATED / UNVERIFIED sections inside the existing result view; typecheck clean; server-rendered tests with real backend data |
| Human review integration | decision API unchanged in security; now merges the reviewed supplement; author cannot approve it |

## 3. Counts (computed)
| | Records |
|---|---:|
| Governed catalog records | 911 |
| ELIGIBLE (class B, every required item stated, evidence current) | **1** (`cisco_asa:official_message_id:113005`) |
| BLOCKED | 42 (class B 38, class D 4) |
| INELIGIBLE (A 153, C 312, E 57, F 346) | 868 |
| Approved by a human | **0** |
| Records with a draft proposal | 0 outside tests |
Why 3 became 1: the contract now also requires a stated permission for destructive steps (human approval comes from EIMS policy). Two former eligible records have destructive steps with no stated permission. Remaining class B missing items: recovery verification 24, recommended action 23, risk 22, permission for a destructive action 5, rollback for a destructive action 4.
Records usable in a controlled pilot today: **1**, pending a human's source verification, validation and approval. Drafts and blocked records are not counted as usable.

## 4. Tests (commands run, project venv, disposable PostgreSQL)
| Command | Passed | Failed | Skipped |
|---|---:|---:|---:|
| `pytest tests --ignore=tests/test_analyzer_postgres_integration.py` (finished code) | **2106** | **0** | 51 |
| `pytest tests/test_analyzer_postgres_integration.py` | **75** | **0** | 0 |
| `npx tsc --noEmit` (`clients/dashboard`) | clean | — | — |
New this round: `tests/test_draft_proposal_workflow_pg.py` (9), `tests/test_analyzer_guidance_ui.py` (5), extensions of `tests/test_catalog_adapter.py` and the governance API tests. Skips are the usual environment-gated tests and are not passes. Not run: `next build`, a live-browser session. A mutation check on the decision API (removing the server-set verifier and the forbidden-key list) failed five tests last round; it was not repeated for the draft code.

## 5. Files
Added: `backend/domain/knowledge/proposals.py`, `clients/dashboard/src/components/OperationalGuidancePanel.tsx`, `tools/apply_remediation_fields.py`, `tests/test_draft_proposal_workflow_pg.py`, `tests/test_analyzer_guidance_ui.py`, `tests/analyzer_guidance_ui.cjs`, the five companion reports and this report, `docs/acceptance/certification/remediation_fields_curated.json`.
Modified: `backend/domain/knowledge/catalog_adapter.py`, `remediation_safety.py`, `service.py` (draft events excluded from decision prerequisites), `backend/api/routers/analyzer/knowledge_governance.py`, `analyze.py` (supplement hook, two call lines), `schemas/analyze.py`, `catalog_diagnostics.py`, `vendor_diagnostics.py` (loader validation), `vendor_diagnostic_catalog.json` (four records gained `operational_fields`), `clients/dashboard/src/components/AnalysisResultDetail.tsx` (3 inserted lines in an already-dirty file), regenerated register, evidence, eligibility, class B package, knowledge-model mapping, remediation ledger, and tests updated for the new eligible set.
Preserved: every earlier dirty and untracked file and all historical reports.

## 6. Remaining human decisions and blockers
1. Reviewers must use the API on the one eligible record (source verification → validation → approval) and on any draft.
2. Rollback, required permission and recovery verification for the remaining blocked records need vendor statements that were not found; 16 records still need a research pass, 5 Cisco pages need manual reading.
3. Whether approved supplements should also be written back into the catalog file.
4. Whether to build a reviewer UI for drafts and decisions.
5. A live-browser acceptance run of the new panel against a running stack.
6. FortiGate HA device output (unchanged), the 42 Windows records without a direct source, and the Windows product-level scope question (unchanged).

## 7. Verdicts
| Area | Verdict |
|---|---|
| Catalog / governance foundation | **MET**: 911 records governed with identity, hash and state; adapter eligibility by class; no auto approval |
| Candidate draft workflow | **MET (API level)**: separate from active knowledge, human-only submission and approval, idempotent, stale-aware; no UI |
| Human decision governance | **MET (mechanism)**: authenticated reviewer principal, server-set actor and kind, hash binding, scope by class, author ≠ approver; no real reviewer has acted |
| Analyzer operational guidance | **PARTIAL**: returned and rendered with honest statuses for every record that has a catalog match; only 1 record is complete; UI verified at component/type level, not in a live browser |
| Controlled pilot | **PARTIAL**: 1 record passes the technical contract; acceptance criteria are defined in the previous report; needs human decisions first |
| Production readiness | **NOT MET**: no human review, approval or operational acceptance exists |
Engineering of the data flow is closed for the cases tested; what remains is human certification, vendor evidence that does not exist or was not found, and a live-stack acceptance run.
