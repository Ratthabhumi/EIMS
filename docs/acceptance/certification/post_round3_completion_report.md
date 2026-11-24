# Post Round 3 — Integrated Knowledge & Certification Completion Report (2026-11-22)

No stage, commit or push was performed; `EIMS_11-8-2026.md` and `clients/dashboard/src/app/analyzer/page.tsx` were not touched; no operational database was accessed; no migration was applied. Human review and approval fields are blank for all 911 records.

## 1. Repository baseline
Branch `demo/2026-11-24`, HEAD `3f2beea`. At the start of this round the working tree had 321 entries (recorded in the session scratchpad). The 90 tracked-modified files are the same set as before the round; this round added only new untracked files plus edits to files already untracked or already modified (listed in §13).
Round 3 was re-verified from the repository, not from the summary: 911 records / 911 unique keys; class counts A153 B39 C312 D4 E57 F346; committed register equals a fresh build (keys and hashes); matching evidence 119 cases, all hash-bound to current content and passing; PostgreSQL evidence 9 of 9 cases from PostgreSQL 16.16, hash-bound; no `eims-cert*` container, volume or network exists; 207 findings (163 unique records) came from that day's validator and were frozen in `baseline_round3_findings.json`; human review and approval 0.

## 2. Official-source research performed (pages opened, not recalled)
* 92 distinct Microsoft Learn / Support pages cited by Windows records were fetched; each page's title, `ms.date`, `updated_at`, git commit and origin were recorded.
* For the 42 records without a direct source, Microsoft Learn search was queried with two queries per record (6 results each, `/answers/` forum pages excluded) and every result page was fetched and tested for the Event ID in an event-like context and the provider name: **0 strong candidates**, 12 weak ones (Event ID present, provider absent; all irrelevant: training paths, a Sysmon page, a PowerShell cmdlet page).
* The six cited vendor pages of the risk-unresolved candidates were scanned; Cisco's page refuses automated access (HTTP 403) and was not bypassed.
* Three "always/never" statements were checked against Veeam KB1857 and the HAProxy 2.8 manual (see findings).
* FortiGate HA sources already cited by the records were re-read to produce the capture checklist (no new Fortinet page was fetched this round).

## 3. Windows 153 records (`windows_source_research_ledger.json/.csv`, 132 rows + 153 dispositions)
| Ledger disposition | Records | Meaning |
|---|---:|---|
| EXPLICIT_OS_STATEMENT_FOUND | 53 | the official page states the Windows releases (and, for Security audit pages, the event schema versions 0/1/2) — copied verbatim into a new catalog `applicability` block |
| PRODUCT_LEVEL_APPLICABILITY_ONLY | 47 | the page's "Applies to" names only a product-level scope (e.g. "Supported versions of Windows Server"); kept verbatim but **not** treated as an OS version |
| NO_APPLICABILITY_STATEMENT | 5 | page names the Event ID but states no applicability (4728, 4729, 4737, 4104, 1511) |
| SOURCE_DOES_NOT_NAME_EVENT_ID | 6 | the cited page does not name the Event ID in an event-like context: 1026 (.NET Runtime), 4000 and 4015 (DNS Server), 17 (WHEA-Logger), 1530 (User Profile), 5011 (WAS) — **a human must check whether the citation is wrong** |
| NO_DIRECT_SOURCE_FOUND | 42 | no direct official source found (same 42 records as before; indirect/needs-review sub-dispositions unchanged) |
Kept apart as required: documentation publication data (`pub_*`, in the ledger and the catalog's `applicability.publication`), OS statement, product-level statement, event schema versions, build. **No record states a Windows build as supported**; the single build mention found (KB5044284, OS Build 26100.2033, on the OpenSSH page) belongs to one update and is recorded only as `build_mention`.
Catalog change: 100 records gained an `applicability` block through `tools/apply_windows_applicability.py` (text-level, CRLF preserved; removing the 100 blocks restores the previous file byte for byte; tested). Content hashes of those 100 records changed accordingly; class A has no bound evidence, so none went stale.
Status after the research (register): explicit official OS statement 53; product-level only 47; page-scope sentence only 11; no source or scope 42. All remain `SOURCE_UNVERIFIED`.

## 4. Class B (39) — human review readiness
`class_b_human_review_package.md/.json`: all 14 requested items per record, evidence rows with expected and actual results, hashes equal to the register's, a blank reviewer table per record (39 tables, no names, decisions or dates).
Readiness facts the package exposes: 32 of 39 records lack at least one operational field; only **3 of 39** carry every operational section and pass the existing `KnowledgeEntry` contract; recovery verification is stated for 14, risk for 17, rollback for 14. The 11 newly linked candidates (PostgreSQL ×9, Fortinet ×2) have **no recovery verification at all**.
Governance: a human decision is now enforced in code at the gate (§9), but **there is no authenticated API or UI that records a catalog-record decision and no reviewer role/authority model**, so decisions made on the package are notes, not governance records. This is the Gate 1 blocker.

## 5. Findings (validator re-run on the final register; dispositions reconciled)
| Measure | Count |
|---|---:|
| Round 2 baseline findings dispositioned | 132 |
| Round 3 findings dispositioned | 162 |
| Round 4 new findings (product-level scope) | 47 |
| Disposition rows in total | 341 |
| **Actionable findings now (fresh validator run)** | **154** |
| **Unique records with an open finding** | **110** |
| Resolved by evidence (incl. 53 Windows applicability statements) | 135 |
| BLOCKED / NEEDS_HUMAN_REVIEW / ACCEPTED_LIMITATION / NOT_APPLICABLE (open or closed rows) | 181 / 21 / 2 / 2 |
Current 154 by type: version_scope_product_level_only 47; source_url_missing 42; version_scope_missing 42; version_scope_not_explicit 11; destructive_remediation_risk_unresolved 6; unqualified_always_never 3 (dispositioned: 2 accepted, 1 not applicable); state_real_evidence_* 2; evaluator_not_mapped 1.
No finding was hidden: Round 3's 207 → 154 only because 53 Windows version-scope findings now have explicit official statements; 47 became the more precise product-level finding. No rule was relaxed.
Rule defects found: none new this round; the Round 3 "not explicit"/"Not stated" rules stand.
Windows 42 missing direct source and 111 → 53 explicit / 47 product-level / 11 page-scope: see §3.

## 6. Legacy 22 `official_documentation_verified` (plus 6 `code_supported_with_contextual_reference`)
The label is unchanged in the catalog (an existing test asserts it and the UI already renders it as "Documented reference"). The register now carries `legacy_verification` for all 28 legacy entries with `human_source_verified: false` and the interpretation "legacy label, no recorded human reviewer, not equivalent to SOURCE_VERIFIED"; `readiness.source` stays `SOURCE_UNVERIFIED` for every one; nothing was promoted.

## 7. FortiGate HA blockers
`fortigate_ha_capture_checklist.md`: commands, scenarios (positive and negative), acceptance rules from the cited Fortinet pages. Both records stay `TECHNICAL_UNVALIDATED`: no device output exists; the evaluator for `failover-reason-from-ha-status` is tested with authored strings only (not counted), and `unexpected-failover-causes` has no evaluator. Version applicability of the articles to FortiOS 6.2.x is not established.

## 8. Class C / D / E / F
* C (312): unchanged and re-verified — 310 resolve through the parser, 2 success-status references (`postgresql:sqlstate:00000`, `systemd:exit_status:0`) are expected non-emission; no mismatch.
* D (4): PostgreSQL slot and lag have real PostgreSQL 16.16 evidence (9/9); both Fortinet HA records blocked (§7).
* E (57): remain reference-only; schema-complete; no parser claimed. Risk stated for 37 of 57, recovery verification for 18, rollback for none; **6 of 57** are engineer-ready.
* F (346): reference-only semantics unchanged; 8 records have no `name`/`code` symptom field (338 of 346).

## 9. Governance implemented
`backend/domain/knowledge/gates.py` and `service.py`: `actor_kind` is required and must be exactly `human` for source_verified, validated, approved, deprecated and superseded (fail closed for `ai_assist`, `automation`, empty, unknown); AI/automation may still reopen (`candidate`) or reject; prior decisions not recorded by a human no longer satisfy prerequisites; the actor kind is stored in the existing append-only event evidence. The free-text `verifier` field never counts. 42 new gate test cases + 1 PostgreSQL-backed service test; existing tests were updated to pass `actor_kind="human"` where they model a human decision. No migration was needed (JSONB); a column/CHECK would be a separate, owner-approved migration.

## 10. Knowledge model and database
`knowledge_model_gap_analysis.md` and `knowledge_model_mapping.json` (computed). Headline: the engineer-facing model already exists as `KnowledgeEntry` (root cause, solution, risk, validation, rollback, references); the catalogs have no converter into it; only **9 of 100 diagnostic candidates** are engineer-ready; the existing contract rejects 28 candidates' destructive remediation for lack of rollback/validation; no catalog carries a risk level. **No schema or migration was created** (no consumer would use it). Nothing was applied to any database.

## 11. End-to-end integration
Verified in tests: source catalog → resolver/parser → Analyzer summary for the 42 evidence records; catalog record → `KnowledgeProposalContent` contract (committed mapping equals a fresh computation); Analyzer output exposes causes, investigation steps, risk text and next-evidence commands. **Not achievable today:** recovery verification and rollback do not reach the Analyzer output (no backend code reads them), and no import path exists from catalogs to `KnowledgeEntry`. These are recorded as blockers, not faked.

## 12. Tests
See `certification_readiness_report.md` (final run). New this round: `tests/test_certification_round4.py` (extraction rules, ledger/catalog consistency, byte-preserving catalog edit, resolved-row traceability, Class B package, risk evidence, legacy label, knowledge model and contract) and 42 governance test cases; focused knowledge suites on a disposable PostgreSQL: 198 passed, 0 skipped.

## 13. Files
Added: `tools/build_windows_source_ledger.py`, `tools/apply_windows_applicability.py`, `tools/scan_remediation_risk_sources.py`, `tools/build_class_b_review_package.py`, `tools/analyze_knowledge_model.py`, `tests/test_certification_round4.py`; certification artifacts `windows_source_research_ledger.json/.csv`, `class_b_human_review_package.md/.json`, `risk_warning_evidence.json`, `knowledge_model_mapping.json`, `knowledge_model_gap_analysis.md`, `fortigate_ha_capture_checklist.md`, `baseline_round3_findings.json`, this report.
Modified: `tools/build_certification_register.py`, `tools/validate_knowledge_certification.py`, `tools/build_findings_disposition.py`, `register.json/.csv`, `findings_disposition.json/.csv`, `validator_report.json`, `backend/domain/analyzer/services/operational_event_catalog.json` (100 `applicability` blocks, previously modified file), `backend/domain/knowledge/gates.py`, `backend/domain/knowledge/service.py`, `tests/test_knowledge_gates.py`, `tests/test_knowledge_service.py`, `tests/test_knowledge_retrieval_pg.py`, `tests/test_certification_round3.py`.
Preserved: all earlier dirty and untracked files; Round 2/3 outputs kept as `register_round2_baseline.*`, `baseline_round2_findings.json`, `baseline_round3_findings.json`.

## 14. Human decisions still needed
1. Reviewers, roles and authority; an authenticated API/UI to record decisions on catalog records (Gate 1).
2. For the 6 Windows records whose cited page does not name the Event ID: is the citation wrong?
3. For the 47 product-level and 11 page-scope Windows records: accept the product-level statement as sufficient, or find an OS/build source.
4. Risk wording for the 6 unresolved-risk candidates (Cisco's page needs manual reading).
5. Whether to build the catalog → `KnowledgeEntry` proposal-draft path and the schema additions in `knowledge_model_gap_analysis.md` §6.
6. Real FortiGate HA output and a Fortinet reviewer.
7. Table-level vs per-row review for the 312 parser-mapped references (still open from Round 1).

## 15. Gates
| Gate | Verdict | Evidence |
|---|---|---|
| 1 — Human Class B Review Ready | **PARTIAL.** Package, hash-bound evidence and the human-only gate are ready; **no authenticated decision-recording path or reviewer authority model**, so no review can be recorded as governance | §4, §9 |
| 2 — Controlled Technical Pilot Ready | **NOT MET.** Only 3 of 39 class B (9 of 100 candidates) are engineer-ready; recovery verification/rollback do not reach the Analyzer; 2 class D blocked | §4, §8, §11 |
| 3 — Production Diagnostic Ready | **NOT MET.** No source verification, no independent review, no approval, no operational-safety or monitoring evidence | whole report |
Tests passing never moves a gate.
