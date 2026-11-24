# End-to-end acceptance report (2026-11-22)

Flow tested: `Catalog → Adapter → Candidate → Draft proposal → Human review → Decision API → Governance overlay → Analyzer → Operational guidance (rendered by the UI component)`. Database: disposable PostgreSQL, real authentication dependencies. Tests: `tests/test_draft_proposal_workflow_pg.py`, `tests/test_knowledge_governance_api_pg.py`, `tests/test_catalog_adapter.py`, `tests/test_analyzer_guidance_ui.py`.

| Required case | Result | Evidence |
|---|---|---|
| Eligible candidate | ASA 113005: ELIGIBLE, registered in the overlay (idempotent, automation-attributed), analyzer returns complete guidance (`missing == []`), UI renders 12 rows | adapter, registration and UI tests |
| Blocked candidate | PostgreSQL deadlock: BLOCKED (recovery verification missing); draft → human review → independent approval makes it complete **only** through the approved supplement | `test_blocked_record_becomes_active_guidance_only_after…` |
| Stale source | draft becomes STALE, old base hash refused, re-based draft accepted; approved supplement stops applying after a content change | two PostgreSQL tests |
| Missing recovery evidence | guidance says `not_stated` and lists `recovery_verification`; unverified fields never complete a record | adapter + draft tests, UI test |
| Reference-only record | no guidance object (Analyzer) and nothing rendered (UI); no proposal path | tests |
| AI / automation decision rejection | gate, service and API refuse non-human actors; shared admin token 403; an AI-prepared draft cannot be submitted by AI | 42 gate cases + PostgreSQL tests |
| Unauthorized human decision | non-reviewer 403; anonymous 401 | PostgreSQL tests |
| Approved record | three humans (verifier, validator, approver) + approval scope; supplement stored with digest; history readable | PostgreSQL tests |
| Draft not active guidance | DRAFT and HUMAN_REVIEW never reach `operationalGuidance`; draft events do not reset or satisfy decision prerequisites | PostgreSQL tests |
| Author cannot approve own supplement | 403 `author_cannot_approve` | PostgreSQL test |

## Regression
Final run of the finished code on disposable PostgreSQL: **2106 passed, 51 skipped, 0 failed** (889 s); analyzer-PG suite **75 passed, 0 failed**; `tsc --noEmit` clean. Details in `final_workflow_closure_report.md`.

## Gaps (stated)
* Counts: **1** record is eligible and **0** are approved; the end-to-end approval path was exercised with synthetic reviewers on a disposable database only. No real reviewer has acted.
* Only one blocked record (PostgreSQL deadlock) was driven through draft → approval in tests; the other 41 blocked records are blocked by missing vendor evidence (rollback, permission, recovery verification), not by the workflow.
* The UI was verified by server-side rendering and typecheck, not in a live browser.
