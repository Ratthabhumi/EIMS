# Final Operational Knowledge Report — Post Round 4 (2026-11-22)

No stage, commit or push. `EIMS_11-8-2026.md` and `clients/dashboard/src/app/analyzer/page.tsx` untouched. No operational database accessed; every database used was a disposable local PostgreSQL. No migration was created or applied. Human review and approval fields: blank for all 911 records.
Companion files: `catalog_import_eligibility.json/.csv`, `remediation_research_ledger.json` (+ `remediation_research_candidates.json`), `human_decision_api_security_report.md`, `analyzer_knowledge_integration_report.md`, `final_test_report.md`, `final_blockers.md`.

## 1. Baseline
Branch `demo/2026-11-24`, HEAD `3f2beea`; 327 working-tree entries recorded at the start (same tracked-modified set as before this round). Round 4 verified from files, not the summary: 911 records and a register identical to a fresh build; Windows ledger 53 explicit / 47 product-level / 5 no statement / 6 citation without Event ID / 42 no direct source over 92 pages; matching evidence 119 cases and PostgreSQL evidence 9/9 (PostgreSQL 16.16), both hash-bound to current content; engineer-ready 9 of 100 candidates; contract rejections 28; findings 154 over 110 records; review and approval 0.

## 2. What changed from Round 4 (root causes)
| Finding | Root cause | Fix |
|---|---|---|
| 28 candidates "destructive without rollback" | keyword rule counted prohibitions ("Do not delete…", "not necessary to stop…") as instructions | negation-aware rule `remediation_safety.py` (one verb list for register, validator, adapter); 3 of 28 resolved, **25 remain** |
| No catalog→KnowledgeEntry converter | `KnowledgeEntry.source_history_id` is NOT NULL → a catalog row has no case; the Analyzer already reads the catalog and the governance overlay | adapter + overlay registration instead of a copy (see the integration report); no dead table |
| Governance covered 181 of 911 records | `_catalog()` used the legacy loader only | now 911; hashes identical to the register for all 911 |
| Recovery/rollback invisible to engineers | no backend code read `verification_*`/`rollback` | `operationalGuidance` on the Analyzer result with explicit stated / not_stated |
| No way to record a human decision | gates existed with no API or trusted principal | decision API on the existing reviewer principal; server-set actor and kind |
Side effect to know: hashes of the 181 Windows/legacy records changed (the key `catalog_id` is no longer part of the hash); the matching evidence was re-run (119/119 pass) and the register rebuilt. No stored governance data existed to invalidate.

## 3. Catalog adapter and import results
Dry-run for all 911 (`catalog_import_eligibility.*`): **ELIGIBLE 3, BLOCKED 40, INELIGIBLE 868**, NEEDS_HUMAN_REVIEW 0, ALREADY_IMPORTED 0, STALE_SOURCE 0 on a fresh database. By class: A 153 ineligible; B 3 eligible + 36 blocked; C 312 ineligible; D 4 blocked; E 57 ineligible; F 346 ineligible — reference-only and unmapped records are never importable as diagnostic capabilities. Blocked class B missing items: recovery verification 25, recommended action 23, risk 22, rollback for a destructive action 4.
Apply (disposable PostgreSQL, since removed): 3 overlay rows + 3 automation-attributed `catalog_import` events; second run created nothing; refusals for the standard port and a non-allowlisted database verified. Nothing is approved, verified or validated by import.

## 4. The 28 remediation records
`remediation_research_ledger.json`: **3 resolved** (rule defect: the text only prohibits the action), **5 manual review** (cisco.com refuses automated access; not bypassed), **20 blocked** (the cited page was fetched and scanned; no explicit rollback or post-action verification statement). Vendor sentences noted for human review: Hyper-V VM page "Back up and, if needed, delete or rename the .vmcx and .vmrs files" (a backup step, still no rollback or check); PostgreSQL and Fortinet cautions already reflected in the records. No rollback, verification or command was written from memory; no catalog record changed; none of the 25 was made eligible.

## 5. Human decision API
See `human_decision_api_security_report.md`. Authenticated reviewer principal only; actor and actor kind set by the server; hash-bound; scope checked by class; automation/AI/anonymous/shared-token refused; 13 PostgreSQL-backed API scenarios + 42 gate cases + service test; mutation check performed.

## 6. Database changes
**None.** `actor_kind`, approval scope and evidence references live in the existing append-only event JSONB. No migration, so no upgrade/downgrade test was applicable; a queryable `actor_kind` column or `User.account_kind` would be an additive migration after an owner decision (listed in `final_blockers.md`).

## 7. Analyzer end-to-end
Tested through the real parser/Analyzer path: for the 3 eligible records the result returns what happened, why, what to inspect, action, risk, rollback, recovery verification (equal to the catalog's criteria), sources, version scope and limitations, with review state "PENDING_HUMAN_REVIEW". For a class B record lacking recovery verification the result says "not stated". For reference-only lookups there is no guidance. Backward compatible: `operationalGuidance` is optional and every previous field is unchanged.

## 8. Windows, FortiGate, classes C–F
Windows research from Round 4 is preserved (no new inference; no build or OS version was inferred). FortiGate HA: both records stay `TECHNICAL_UNVALIDATED`; the capture checklist is in `fortigate_ha_capture_checklist.md`. Class C: 312 re-verified in the previous round, unchanged (310 parser-resolved, 2 intentional non-emission). E and F cannot be imported or shown as diagnostic capabilities (enforced in the adapter and tested).

## 9. Operational acceptance criteria for a controlled pilot (3 records)
A record may be used in a controlled pilot only if: (1) a human reviewer, authenticated through the decision API, has recorded source_verified and validated for the current content hash; (2) a different human has approved it with scope `approved_as_diagnostic`; (3) its technical evidence is current (119-case suite green for that hash); (4) in a lab, an engineer follows the returned guidance for a synthetic occurrence and the recovery-verification criteria pass; (5) any content change returns the record to review (hash mismatch); (6) blocked or ineligible records are never offered as workflows; (7) every decision is visible in the governance history. Until (1)–(2) happen, the three records are *registerable and reviewable*, not approved.

## 10. Remaining human decisions
See `final_blockers.md` (16 items).

## 11. Gate verdicts
| Gate | Verdict | Evidence |
|---|---|---|
| A — Knowledge Foundation | **MET (mechanism)**: adapter works, eligibility by class, import idempotent and audited, source/hash/evidence linked, no auto approval. Coverage is small: 3 of 39 class B records are eligible | adapter tests, CLI run, hashes equal register for 911 |
| B — Engineer operational workflow | **PARTIAL**: the Analyzer returns full guidance for 3 records; for the other 36 class B records items are honestly "not stated" (25 lack recovery verification; no vendor source states rollback for the 25 destructive candidates) | integration report, ledger |
| C — Human governance | **MET (mechanism)**: authenticated human decision API, AI/automation refused, history, hash binding. Not exercised by any real reviewer; no UI; residual risks stated | security report, 13 + 42 tests |
| D — Controlled pilot | **PARTIAL**: 3 records pass the technical contract with current evidence and acceptance criteria are defined; no human decision exists and Windows/E/F/blocked records stay outside the pilot | §9 |
| E — Production readiness | **NOT MET**: no source verification, independent review, approval, operational acceptance, monitoring evidence | whole report |
**Production readiness verdict: NOT READY.** Engineering of the data flow is complete for the 3 eligible records; what remains is human certification, vendor evidence that does not exist yet, and owner decisions.

## 12. Files
Added: `backend/domain/knowledge/catalog_adapter.py`, `backend/domain/knowledge/remediation_safety.py`, `backend/api/routers/analyzer/knowledge_governance.py`, `tools/catalog_import.py`, `tools/research_remediation_sources.py`, `tools/build_remediation_ledger.py`, `tests/test_catalog_adapter.py`, `tests/test_knowledge_governance_api_pg.py`, the report files above, `catalog_import_eligibility.json/.csv`, `remediation_research_candidates.json`, `remediation_research_ledger.json`.
Modified: `backend/domain/knowledge/service.py`, `backend/domain/knowledge/gates.py` (earlier this day: actor_kind), `backend/api/routers/analyzer/knowledge.py` (two lines mounting the governance router), `backend/domain/analyzer/schemas/analyze.py` (optional guidance models), `backend/domain/analyzer/services/catalog_diagnostics.py`, `backend/domain/analyzer/services/summary.py` (Veeam guidance attachment), `tools/build_certification_register.py`, `tools/validate_knowledge_certification.py`, `tools/analyze_knowledge_model.py`, regenerated register/evidence/dispositions/validator report/class B package/knowledge model mapping.
Preserved: all pre-existing dirty and untracked files; Round 2–4 reports and baselines.
