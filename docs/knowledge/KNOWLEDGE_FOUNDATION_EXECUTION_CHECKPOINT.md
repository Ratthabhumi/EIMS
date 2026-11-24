# Knowledge Foundation — Execution Checkpoint (2026-11-19)

## Accepted

| Gate | Evidence |
|---|---|
| 1 taxonomy | 141 context / 22 candidate / 0 validated; JSON hashes unchanged |
| Router | CLOSED — deferred inclusion; `app.openapi()` 66 paths |
| 2a HTTP | `tests/test_catalog_summary_http.py` + registration → **7 passed** |
| **2b overlay + migration** | `tests/test_knowledge_overlay_pg.py` → **1 passed, exit 0, 12.2s** |

## Gate 2b — what was implemented and proven

Files:
- `backend/domain/knowledge/models.py` — `KnowledgeReview` (sparse current state)
  + `KnowledgeReviewEvent` (append-only history).
- `migrations/versions/a1c4e7b9d201_add_knowledge_review.py` —
  `down_revision = "f7a1c3d9e502"` (verified head), additive, with a
  `BEFORE UPDATE OR DELETE` row trigger and a `BEFORE TRUNCATE` statement
  trigger, mirroring the `incident_verification` protection pattern.
- `tests/test_knowledge_overlay_pg.py` — runs the **real Alembic chain** on a
  throw-away schema in the disposable instance.

Proven by that test:

```
alembic_version            = a1c4e7b9d201   (single head reached)
tables                     = knowledge_review, knowledge_review_event
insert decision + state    = OK
UPDATE knowledge_review_event  -> rejected ("append-only")
DELETE FROM knowledge_review_event -> rejected
TRUNCATE knowledge_review_event    -> rejected
history after attempts     = 1 row (intact, readable)
```

No content was copied into PostgreSQL: the tables store `catalog_id`,
governance state, hashes, revision and decisions only.

## Not started

| Gate | Remaining work |
|---|---|
| 3 | sync service (catalog resolve, sparse upsert, hash invalidation), quality gate, transition table, authorization/self-approval, negative tests |
| 4 | Analyzer retrieval match classes from catalog + overlay |
| 5 | Analyzer Portal (owned files) + API summary merge |
| 6 | per-record verification of the 22 candidates |
| 7 | expansion |
| 8 | full acceptance incl. startup-path Scenario A/B |

## Exact next actions

1. `backend/domain/knowledge/service.py`: `resolve()`, `sync()`, `effective_state()`,
   `promote()`, `record_event()`, `history()`; idempotent, hash-change →
   `review_required` event, never auto-approve.
2. Tests: `test_knowledge_sync.py` (163 ids resolve, 141/22 defaults, idempotent,
   hash change, duplicate review_required prevented).
3. Merge overlay counts into `/api/v1/analyzer/catalog/summary`.
4. Analyzer retrieval match classes; Portal split.
5. Startup Scenario A/B on disposable PG before touching the Local DB.

## Regression commands

```powershell
pytest tests/test_knowledge_overlay_pg.py -q                    # 1 passed
pytest tests/test_app_router_registration.py tests/test_catalog_summary_http.py -q  # 7 passed
```

Cursor-owned files (`observability/page.tsx`, `SidebarNav.tsx`) untouched.
Legacy `clients/dashboard/src/app/knowledge/` still requires a documented
disposition; no deletion performed.

## 2026-11-19 — Root cause of Knowledge API `UndefinedTableError` (Workstream B, milestone 1)

**Root cause (proven): A (different database) caused by G (import/fixture ordering).**
`tests/conftest.py` imports `backend.main` at collection time, so the global
`settings` object — and `settings.database_url`, which the global `database_engine`
uses in lifespan — is built from defaults (`localhost:5432/eims_registry`, the
*operational* database) before any test module can set `EIMS_DB_*`. The old tests
set those variables at module level (`os.environ.setdefault`), which was a no-op
for the application. Table creation ran on the disposable DB; the HTTP request ran
on the operational DB. Evidence: lifespan log line `Connecting to Postgres
Relational Pool at: localhost:5432` while `EIMS_TEST_DATABASE_URL` pointed at the
disposable instance (127.0.0.1:56470). Not `search_path`, not the SQL, not the
`summary(db)` signature; production code is unchanged and correct.

**Fix (test layer only, no production change):**
- `tests/test_catalog_summary_http.py`: `disposable_app` fixture pins the already-built
  `settings` (monkeypatch, auto-restored) to the disposable DB, refuses an operational
  target, and a test-only `/__test__/db-identity` route proves `current_database()`
  and `to_regclass('knowledge_review[_event]')` on the connection that serves the
  request. Setup now resets with `DROP TABLE` (append-only triggers correctly reject
  DELETE/TRUNCATE) and no longer swallows trigger-install errors; rerun-safe.
- `tests/test_knowledge_overlay_pg.py` scenario B had the same defect (lifespan hit
  `localhost:5432`, masked by `status in (200, 401, 403)`); now pinned and asserts a
  missing overlay never yields fabricated counts.

**Evidence (disposable container `eims-knowledge-b-pg-20261119`, pgvector/pg16,
127.0.0.1:56470, role `eims_incident_test` non-superuser):**
`pytest tests/test_catalog_summary_http.py tests/test_knowledge_service.py tests/test_knowledge_overlay_pg.py`
→ **8 passed, exit 0** (HTTP 2, service 4, overlay/migration 2). Lifespan logs show
`127.0.0.1:56470` in every scenario. HTTP assertions: approved=1, then stale →
approved=0, stale_review=1, total 163 / 141 / 22.

**Operational-DB exposure (disclosure):** before the fix, every run of these two tests
(including one of mine at 2026-11-19 19:51 +07) executed the application lifespan
against `localhost:5432/eims_registry`: `seed_users()` bootstrap and a read-only
`SELECT` on `knowledge_review`. The Operational DB was not inspected by this work, so
whether the seed changed anything is NOT verified. Owner should review.

**Not done yet:** quality gates, analyzer retrieval, portal integration, 22-candidate
source verification, capacity review (milestones 2–5). Verdict so far: NOT ACCEPTED
(Knowledge Foundation); API integration blocker closed.

## 2026-11-19 — Milestone 2: lifecycle quality gates (destination-state completeness)

**Implemented**
- `backend/domain/knowledge/gates.py`: pure `evaluate_gate()` returning (content problems, permission problems); no I/O, so validation happens before any mutation.
  - `source_verified`: source title, https URL, supporting section, claim evidence, ISO verification timestamp, verifier (must be the authenticated actor), vendor/product scope, limitations.
  - `validated`: product/version scope, applicability, validation basis, verification criteria, investigation steps, limitations, and a prior `source_verified` event for the *current* content hash.
  - `approved`: prior validated + source_verified for the current hash, not stale, approver independent of verifier/validator/contributor.
  - `rejected`/`deprecated`/`superseded`: actor + rationale + provenance hash; `superseded` needs a known, distinct `replacement_catalog_id`.
- `service.promote(..., review=dict)`: gate runs before any state change; row update and append-only event are written in the caller's single transaction. Only decisions since the last reset (reject/reopen) count as provenance. The old `evidence` string no longer satisfies a gate.
- Migration `b2d5f8c0e301` (additive, nullable `knowledge_review_event.evidence JSONB`); `a1c4e7b9d201` is untouched because it may already be applied elsewhere. Model and `history()` carry the new field.

**Tests (disposable `eims-knowledge-b-pg-20261119`, non-superuser role)**
`pytest tests/test_knowledge_gates.py tests/test_catalog_summary_http.py tests/test_knowledge_service.py tests/test_knowledge_overlay_pg.py` → **23 passed, exit 0** (gates 15, HTTP 2, service 4, overlay/migration 2). Adjacent `tests/test_incident_migration.py` → 4 passed after its pinned head was moved from `f7a1c3d9e502` (already stale since `a1c4e7b9d201`) to `b2d5f8c0e301`.
Service test now proves: incomplete submission leaves no row and no event; verifier and validator cannot approve; contributor cannot approve; evidence persists on the event.

**Not yet covered**: API route for `promote` (only `summary` is exposed here), pagination/indexing review, real source verification of the 22 candidates. Verdict remains NOT ACCEPTED.

## 2026-11-19 — Milestone 3: deterministic Analyzer retrieval

**Implemented**
- `backend/domain/knowledge/retrieval.py`: pure `classify()` + `retrieve()` returning one of `context_match`, `diagnostic_candidate_match`, `source_verified_match`, `validated_diagnostic_match`, `approved_diagnostic_match`, `version_compatible_match`, `no_verified_match`.
  Trust comes only from catalog class + persisted overlay. Stale review, unavailable overlay, rejected/deprecated/superseded all lower trust; an approved record is `version_compatible_match` only when a parseable detected version matches the recorded scope, and `no_verified_match` when it provably does not. Free text never changes classification.
- `retrieve()` reads the overlay inside a SAVEPOINT so a missing overlay cannot abort the caller's transaction (history insert follows); on failure it returns `overlayAvailable: false` at candidate trust.
- `KnowledgeMatch` schema + `SolutionSummary.knowledgeMatch` (optional, older rows unaffected). `analyze.submit_analysis` assigns it after synthesis, unconditionally overwriting anything the LLM path set. Windows lookups fall back to the official event id (`entry_for_metadata` keys on the EIMS diagnostic code, so 1129 was initially `no_verified_match`; fixed and regression-tested).

**Tests**: gates 15 + retrieval 24 (incl. route helper on Windows 1129) + retrieval PG 2 + HTTP 2 + service 4 + overlay 2, plus adjacent `test_diagnostic_catalog.py` / `test_analyzer_reliability.py` (see run output in session). PG tests cover the real lifecycle chain, stale downgrade, version compatibility, and a schema with no knowledge tables (fails closed, transaction still usable).

**Not done**: single-text/file path only — the bundle path (`/analyze/bundle`) does not yet set `knowledgeMatch`; no remediation/verification-outcome workflow yet (milestone 3D); Portal display (milestone 4). Verdict remains NOT ACCEPTED.

## 2026-11-19 — Milestone 4: Analyzer Portal integration and `/knowledge` route disposition

**Implemented (display only; the client never derives or upgrades trust)**
- New `clients/dashboard/src/components/KnowledgeMatchBadge.tsx`: renders the server-assigned `solutionSummary.knowledgeMatch` (EN/TH label, stale / overlay-unavailable / version notes) and exports `knowledgeMatchMarkdown()`.
- `AnalysisResultDetail.tsx` (shared by the live Analyzer result and reopened History): type field + badge in the header box. This file is outside the brief's two named files, but it is the single shared renderer for both views; edit is 3 additive lines. Other workstreams have uncommitted changes in it and in `AnalyzerHistoryList.tsx` (the tool reported a concurrent on-disk change on the latter); my edits applied cleanly and nothing was reverted.
- `analyzer/page.tsx` and `AnalyzerHistoryList.tsx`: Markdown export now includes a `Knowledge trust:` line. PDF export HTML templates were NOT changed.

**Verification**: `npx tsc --noEmit` exit 0; `eslint` on the new component exit 0. **Not verified**: no browser render, no Playwright run (the HTTPS acceptance runtime is not up; cert trust import still pending), no unit test of the component (the dashboard has no component-test harness, only Playwright e2e).

**`/knowledge` route disposition: KEEP, no change.** Evidence: `src/app/knowledge/page.tsx` (407 lines) is the engineer-proposal / human-review system backed by `backend/api/routers/analyzer/knowledge.py` (`/api/v1/knowledge/*`: entries, review queue, source candidates, lifecycle active/revalidation_required/superseded/withdrawn). It is used by `KnowledgeProposalForm.tsx` and covered by `e2e/reviewer-source-catalogue.spec.cjs`. It is a different system from the catalog governance overlay (`knowledge_review*`, catalog_id-keyed). Two parallel lifecycle models now exist; consolidating them is an architectural decision for the owner, not something to delete or merge blindly.

**Remaining**: bundle path does not set `knowledgeMatch`; PDF export templates; Observation→Resolution workflow (3D); 22-candidate source verification (G); capacity review (H).

## 2026-11-19 — Milestone 5 (part G): 22-candidate source verification

Evidence file: `docs/knowledge/CANDIDATE_SOURCE_VERIFICATION_20261119.md`. **No candidate promoted; nothing written to any database.** Sources were read through a fetch tool that returns model-extracted page text, so a human verifier must re-read before any `source_verified`.

Disposition of 22: Cisco ASA 6 evidence collected (version scope not on page; 113005 variants and 113019 title need wording review); OpenSSH 1 collected (unpinned master source); PAN-OS 4 partial ("default CSV" and a single version not stated by the pages); Broadcom KB 424591 supports a narrow vCenter-revert claim for the 2 snapshot records; 2 CBT records only loosely related (Broadcom 339974, Veeam KB1113); 2 Veeam records rest on KB1832 (log collection only); **5 FortiOS records NOT verified** (cited PDF is image-only; HTML truncated), so their existing `official_documentation_verified` status could not be reproduced.

Still outstanding: human verifier/validator/approver for all 22; lab validation; part H (capacity review); bundle-path `knowledgeMatch`; PDF export; Observation→Resolution workflow. Verdict: **NOT ACCEPTED**.

## 2026-11-19 — Milestone 5 (part H): capacity review
Full write-up: `docs/knowledge/KNOWLEDGE_CAPACITY_REVIEW_20261119.md`. Measured on a scratch DB with 1,000,000 synthetic events: `history()` 18 ms for 500 rows, overlay summary read 0.5 ms, pk lookup 0.08 ms; events ~1 KB/row (977 MB heap + 142 MB indexes). No index, partitioning, retention-delete or schema change is justified; a redundant single-column index exists (10 MB/M rows) and was left; `history()` needs a limit only if exposed by a route. Backup drill: pg_dump 34 s / 73 MB, pg_restore 92 s, counts equal, append-only triggers intact and still enforced. PITR, backup schedule and RPO/RTO untested. Scratch DBs left in the disposable container (~2.2 GB).

## 2026-11-19 — Bundle path `knowledgeMatch` + route-level proof

- `analyze.submit_bundle` now sets `solution.knowledgeMatch` from the bundle's **primary** diagnostic identity (the same identity that selects the headline diagnosis), overwriting anything synthesis produced. Other files in a bundle are not individually classified.
- Route-level tests added to `tests/test_analyzer_postgres_integration.py` (real PostgreSQL, real routes, History round-trip): single analysis of Windows 1129 → `context_match` persisted and identical after reopen; bundle → `knowledgeMatch` present, never a trusted class for unreviewed catalog candidates, identical after reopen. The bundle test failed first (red), then passed. This is also the first HTTP-level proof of the single-input wiring from milestone 3.
- Harness note: the integration fixture assumes a pre-provisioned DB. On the scratch DB `eims_integration_test` (eims-knowledge-b-pg-20261119) I installed `vector`/`pg_trgm` and ran `create_all` for the registered models so its `checkfirst` table creation could succeed.
- Results on that DB: `test_analyzer_postgres_integration.py` **52 passed, 21 failed**. All 21 failures are authentication-mode assertions (200 where 401/403 expected, or `410 "Application login is not used…"`); the working tree has uncommitted changes to `backend/api/routers/analyzer/auth.py` and `backend/domain/analyzer/auth.py` retiring application login. They are unrelated to Knowledge, but a clean-baseline run was NOT performed, so "pre-existing" is inferred from the cause, not proven.
- Knowledge/adjacent group (gates, retrieval, retrieval PG, HTTP, service, overlay, diagnostic catalog, analyzer reliability) re-run with the allowlisted incident role.

## 2026-11-19 — Milestone 3D: engineering workflow (reuse, no new code)
See `docs/knowledge/ENGINEERING_WORKFLOW_MAPPING_20261119.md`. The Incident Core already implements Observation → Resolution with verification-gated resolution (58 existing tests passed, 1 failed on the unrelated auth-mode symptom). No duplicate workflow was built. Real gaps recorded for an owner decision: no API to record hypothesis/confirmed root cause (`root_cause_state` is only ever written as "unknown"), no remediation record, no incident↔knowledge link, no incident UI.

## 2026-11-19 (later) — Completion round, part 1

**State re-inspected**: branch `demo/2026-11-24`, HEAD `3f2beea`, 208 changed/untracked paths from several workstreams; none of my files were overwritten. Existing docs from another workstream (`KNOWLEDGE_COVERAGE_MATRIX.md`, `KNOWLEDGE_EXPANSION_PLAN.md`, `KNOWLEDGE_CATALOG_AUDIT.md`, `KNOWLEDGE_QUALITY_STANDARD.md`, `KNOWLEDGE_SOURCE_REGISTER.md`, `KNOWLEDGE_FOUNDATION_STATUS.md`) are kept and not duplicated; they call the 22 vendor records "validated", which contradicts the lifecycle (they are candidates). Correction recorded in the new assessment.

**Done**
- `KNOWLEDGE_COVERAGE_ASSESSMENT.md`: measured depth/breadth from `load_catalog()`. Key facts: all 141 Windows records have zero investigation steps/limitations/references/remediation/verification (mean description 77 chars); the 22 vendor candidates have steps and limitations but **zero remediation_guidance and zero verification_criteria**; no records at all for PostgreSQL, Redis, MinIO or EIMS's own components. Prioritised gaps recorded. No catalog records were added (no per-record verified sources exist for new content).
- **PDF export** (both live and History templates) now includes a "Knowledge Trust" block (classification, meaning, stale/overlay/version warnings, version scope, catalog id) via `knowledgeMatchHtml()`, fed only from `escapeReportData()` output. `tsc --noEmit` exit 0, eslint exit 0. **Not rendered or visually checked**; English only (the PDF templates are English).
- **Failure analysis with a controlled baseline**: a copy of the working tree with only `backend/api/routers/analyzer/auth.py` and `backend/domain/analyzer/auth.py` restored to HEAD reduces `test_analyzer_postgres_integration.py` from **21 failures to 4**. So 17 failures are caused by the uncommitted application-login retirement (expected-behaviour change; the tests assert the old 401/410 behaviour). Plain HEAD is not a valid baseline (its tests reference code that only exists in the working tree; 59 AttributeErrors). The remaining 4: `orgwide_search_requires_current_admin…` (200 vs 403) and `demo_mode_remains_shared_without_login` (likely the same login-retirement theme in other files, not isolated); `actual_auth_migration…` (`MutationTargetError: not marked disposable`, a DB-identity guard on my scratch DB, environment) and `populated_parent_upgrade…` (history row dict differs, probably the incident-ingest `asset_id` column; not isolated). No test was edited or rewritten.

**Identity facts for the diagnosis/remediation design** (`backend/domain/analyzer/auth.py`): with no credentials `get_current_user` returns `OPEN_ACCESS_IDENTITY`; the shared `ADMIN_TOKEN` yields the literal identity `"admin"` (a shared secret, not a person); a JWT for a DB user is still honoured; `require_knowledge_reviewer` rejects open-access and requires a DB user that is admin or reviewer. So in open-access mode nothing can currently satisfy the incident verifier/closure capability.

**Not started / outstanding**: browser verification of the badge and PDF; Incident Core diagnosis/remediation/knowledge-link extension (blocked on the actor-provenance decision below); remediation/verification fields in the catalog schema; sourced catalog expansion batches; human review of the 22 candidates; Hyper-V/Windows gap research; capacity/backup (PITR, RPO/RTO) items.

## 2026-11-19 (later) — Incident Core: diagnosis, remediation and actor assurance

**Owner decision applied**: "honest assurance tiers" (no application login; no invented identities; unattributed/shared-token can never confirm, verify, resolve or close).

**Changed files (this extension)**
- New: `migrations/versions/c3e6a9d1f402_add_incident_diagnosis_remediation.py` (down_revision `b2d5f8c0e301`), `backend/domain/incident/workflow_models.py`, `workflow.py`, `workflow_schemas.py`, `tests/test_incident_workflow_records_pg.py`.
- Edited: `backend/domain/incident/controller.py` (`get_actor`, resolve/close assurance guard, 7 routes), `backend/domain/incident/service.py` (reopen resets `root_cause_state`), `tests/incident_db_support.py` (workflow tables added to `INCIDENT_TABLES`), pinned head in `tests/test_incident_migration.py` and `tests/test_knowledge_overlay_pg.py`.
- Migration `c3e6a9d1f402` was amended in place after review because it had never been applied outside disposable schemas; once applied anywhere, further changes need a new revision.

**Review**: a separate read-only AI reviewer (no human review) examined the diff. Defects it reported and that were verified/fixed: stale `root_cause_state='confirmed'` surviving a reopen (real; fixed, tested); DB constraints that allowed a confirmed diagnosis without verified assurance (real; fixed with `COALESCE` because a plain equality passes on NULL under SQL three-valued logic — the reviewer's suggested form had that hole, caught by a new test), confirmer ≠ proposer check, one confirmed diagnosis per cycle (partial unique index); unbounded array items (fixed); unverified `analysis_history_id` (existence now required); confirmation event digest now binds confirmer/assurance/rationale; `verification_state` restricted to `succeeded` executions and documented as an incident-level signal; reserved identifiers "demo"/"shared-admin-token" cannot masquerade; weak tests strengthened (legal-edge resolve guard with explicit `verified-identity` message and `missing_verification`; collision users; DB-constraint test; reopen-cycle test; failed-outcome test).
**Not fixed / owner decisions**: the reviewer-capability check lives in the controller, not in `IncidentWorkflow.confirm_diagnosis` (a future non-HTTP caller must enforce it); an unattributed caller can still reopen a resolved incident (pre-existing); diagnosis/remediation rows (unlike events and verifications) are not append-only at DB level; no composite FK tying `remediation.diagnosis_id` to the same incident; no concurrency test for simultaneous confirms; no reject/supersede for hypotheses; no pagination on new list routes; no incident UI.

**Tests (disposable PostgreSQL, role `eims_incident_test`)**: `tests/test_incident_workflow_records_pg.py` 19 passed. Combined run of workflow + existing incident suites + migration pins + knowledge group + diagnostic catalog + analyzer reliability: **354 passed, 1 failed, exit 1**. The failure is `test_incident_api.py::test_unauthenticated_requests_are_rejected` asserting the retired 401 behaviour (open access now returns 200); it is obsolete, not edited. A mutation check (resolve/close guard disabled) failed the guard tests; restored and re-passed.

**Controlled baseline for the 21 integration failures** (see earlier entry): 17 are caused by the uncommitted login retirement (isolated by restoring two auth files to HEAD); 4 remain unisolated (two probable login-theme, one DB-identity guard on the scratch DB, one probable `asset_id` row diff). `tests/test_analyzer_postgres_integration.py` was not re-run after the incident change.

## 2026-11-19 (later) — Portal incident view

New route `clients/dashboard/src/app/incidents/page.tsx` (client page; no other file changed). It is the first incident UI; no existing incident page existed to extend. It uses the existing BFF path `apiUrl('/api/v1/incidents…')`; the proxy has no path allow-list, so no proxy change was needed.
Shows: incident list; summary with status, severity, remediation cycle and root-cause state, with an explicit note that correlation confidence is not causality; evidence; verification records; diagnosis hypotheses (stated confidence, supporting/contradicting evidence, proposer and confirmer with a plain-language assurance label, and the knowledge classification captured at the time); remediation proposed vs executed (risk, impact, rollback, expected verification, outcome, and a derived verification line worded as an incident-level signal); the append-only audit trail with assurance. Forms: record a hypothesis (optional `catalog_id`; trust is looked up by the server), propose a remediation (risk, rollback and verification criteria required), record an execution. Forms are hidden once an incident is resolved/closed.
Deliberately absent (no safe backend path from an open-access Portal): confirm root cause, verify, resolve, close. The page says so.
Verification: `tsc --noEmit` exit 0; `eslint` clean. **Not rendered in a browser, not exercised against a live backend, no Playwright test** (the HTTPS acceptance runtime is not up and `next build` was not run to avoid disturbing another workstream's `.next`). Not linked from navigation: `SidebarNav.tsx` is owned by another workstream, so the page is reachable only at `/incidents` until that owner adds a link.

## 2026-11-19 (later) — Browser verification (real Chromium via Playwright)

**Setup**: dashboard = the dev server already running on port 3001 (another workstream's; I only loaded pages from it). Backend = my own `uvicorn backend.main:app` on port 8021 against the disposable PostgreSQL (`127.0.0.1:56470/eims_integration_test`, confirmed by the lifespan log). The browser routed only `/api/eims/**` calls to port 8021 so nothing reached the other backend on port 8000 (database unknown). The 8021 process was stopped afterwards. Evidence files: `docs/knowledge/browser-evidence-20261119/` (screenshots, exported PDF).

**Verified in the browser**
- `/incidents`: list, summary, evidence, hypothesis (shown as "Hypothesis (not confirmed)"), proposer assurance rendered as "Unattributed (open access: individual not proven)", knowledge snapshot ("diagnostic_candidate_match (review stale)"), remediation proposed/executed, "not verified" line, append-only audit trail with assurance, absence of any confirm/verify/resolve/close control.
- Forms through the UI against the real backend: record hypothesis (2 hypotheses listed), propose remediation, record execution (outcome `partial` shown), and a server-side validation error ("risk is required") displayed in an alert.
- Analyzer live result: `knowledgeMatch` badge shown, Thai ("ความรู้: บริบทอ้างอิงเท่านั้น") and English ("Knowledge: Reference context only").
- Reopened History item: badge present.
- Markdown export (`Log_Analysis_1129.md`): contains `**Knowledge trust:** Reference context only`.
- PDF export (`Diagnostic_Report_1129.pdf`, valid `%PDF-`, 227,589 bytes): the page image was decoded and viewed; it shows a "Knowledge Trust" block with "Reference context only", its meaning and the catalog record `windows_event:official_event_id:1129`.

**Observations (not defects of the new code)**: the "(review stale)" label was correct data — an earlier test left an approved row with `review_required` for that catalog record in the scratch DB, and the server downgraded it to candidate. The one console error is the shell's `/api/v1/health` returning 503 from my soft-dependency backend (no Redis).

**Not verified in the browser**: the bundle path (a real bundle analysis hung on the live web-search tier and was abandoned); the stale / overlay-unavailable / version-mismatch warnings inside the Analyzer result and PDF (covered by unit/HTTP tests and seen only on the incidents page); the PDF for a candidate-level classification; the History-list PDF/Markdown export; mobile layout; keyboard/accessibility audit. The PDF text is an image, so its wording cannot be machine-searched. `.playwright-mcp/` (tool downloads and console log) was created in the repository root and is untracked.

## 2026-11-19 (later) — Architecture alignment round

Owner direction: keep the canonical Diagnostic Knowledge Catalog as the only reusable-knowledge store; Incident Core stays case-specific; incident learning goes through the existing Knowledge review lifecycle. Detail and diagram: `docs/knowledge/ARCHITECTURE_ALIGNMENT_20261119.md`; snapshot `docs/engineering-memory/2026-11-19-knowledge-incident-architecture-alignment.md` (linked from `INDEX.md`).

**Changed files**
- Migration: `migrations/versions/d4f7b0a2c503_incident_hypothesis_closure_and_knowledge_links.py` (new).
- Backend: `backend/domain/incident/workflow.py` (rewritten, adds reject/supersede, domain-level reviewer authorisation, pagination, remediation catalog snapshot, knowledge proposals), `workflow_models.py`, `workflow_schemas.py`, `controller.py` (new/changed routes, `X-Total-Count`), `service.py` (reopen resets `root_cause_state` to `unknown`), `backend/domain/knowledge/service.py` (`current_record`), `backend/api/routers/analyzer/catalog.py` (`GET /record`), `backend/api/routers/analyzer/knowledge.py` (proposal creation extracted into `create_knowledge_proposal`, shared with the incident path; `KnowledgeProposalContent` base model; route behaviour unchanged).
- Portal: `clients/dashboard/src/app/incidents/page.tsx` (rewritten), `src/components/SidebarNav.tsx` (one "Incidents" link + one icon import added to another workstream's uncommitted file; nothing else touched).
- Tests: `tests/test_incident_workflow_alignment_pg.py` (new, 10), updated `test_incident_workflow_records_pg.py`, `incident_db_support.py` (new tables in the shared schema), head pins in `test_incident_migration.py` / `test_knowledge_overlay_pg.py`.

**Results (disposable PostgreSQL `eims-knowledge-b-pg-20261119`)**
- Combined run of alignment + workflow + all incident suites + migration + knowledge/retrieval/overlay/catalog/diagnostic/reliability: **364 passed, 1 failed, exit 1** (`test_incident_api.py::test_unauthenticated_requests_are_rejected`, obsolete login assertion, not edited).
- `test_analyzer_postgres_integration.py` + knowledge source/safety suites after the proposal refactor: 21 failures, the same count and the same login-retirement cause as the earlier controlled baseline; none involve knowledge or proposals.
- Migration `d4f7b0a2c503` upgrade and downgrade to `c3e6a9d1f402` and back verified by test. A new constraint test caught partial `closed_*` fields on open rows; fixed with exclusivity checks.

**Browser (real Chromium; dashboard dev server on 3001 from another workstream; my own backend on 8022 → disposable DB `eims_browser_test`; only `/api/eims/**` routed to it; process stopped afterwards)**
- Sidebar "Incidents" link present. Pagination: 55 hypotheses show "showing 50 of 55", Load more yields 55. Snapshot ("Recorded at the time") and "Current canonical record … content unchanged since" displayed. Reject through the UI keeps the row with who/why and assurance. Completed incident: confirmed root cause with verified reviewer, no record/confirm/resolve controls, "Incident-specific action" labelling, proposal submitted through the UI → DB shows `knowledge_entries` status `pending`, no reviewer, and one `incident_knowledge_proposal` link with `unattributed`. Screenshots in `docs/knowledge/browser-evidence-20261119/`.

**Not done / still open**: bundle-path browser E2E and Analyzer stale/overlay/version warnings in the browser (the live web-search tier stalls my backend); not tested against the other workstream's running backend/database (unknown target, deliberately not written to); changed-hash display only unit-tested (the browser data had unchanged content); no human review of this diff (an AI reviewer examined the earlier round only); catalog remediation/verification fields intentionally not added (needs source schema, lifecycle semantics, loader/retrieval compatibility); human sign-off for the 22 candidates; reopen by unattributed callers unchanged; verdict **NOT ACCEPTED**.

## 2026-11-19 (later) — Independent AI review of the alignment round, and fixes

A separate read-only AI reviewer (not a human) examined the round. Each finding was traced in code before acting.

**Confirmed and fixed**
1. **Shared token could approve knowledge** (pre-existing `require_knowledge_reviewer` accepted the shared `ADMIN_TOKEN`, which resolves to the seeded "admin" user; my incident proposal path made a self-approval chain reachable: propose as `shared-admin-token`, approve as `admin`). `require_knowledge_reviewer` now rejects the shared token (403); the two direct controller calls pass `credentials=None`. Test `test_shared_token_cannot_approve_knowledge_it_caused_to_be_proposed` covers token, verified non-reviewer, open access, and that an independent reviewer still can approve. Mutation check: guard disabled → test fails; restored → passes.
2. **Dashboard proxy dropped `X-Total-Count`**, so "Load more" never appeared (my earlier browser run routed around the proxy and missed it). `route.ts` now forwards a numeric `X-Total-Count`; the page also falls back to "a full page may have more" when the header is absent and shows a total only when the server supplied it. Browser-verified in both modes (header dropped: "Load more (showing 50)" → 55 rows; header present: "showing 50 of 55" → 55). **Not verified through the real proxy** (the shared backend on port 8000 runs older code without the new routes).
3. **Shared-token and verified proposers failed** (ownership filter compared `AnalysisHistory.username` with the proposer identifier). The incident path now allows analyses owned by the proposer or by the open-access principal; foreign-owned analyses are refused with no rows left behind. Tests cover shared-token, verified and foreign-owned proposers, duplicate proposals (409) leaving exactly one entry/link/event.
4. **Portal stale-state bugs**: per-incident form state is reset on selection; async loads are guarded by a request token; "Load more" merges by id into the current list only if it still belongs to the incident that asked. Browser-verified: text typed for one incident is gone after switching.
5. **Service-level assurance for resolve/close**: `IncidentService.change_status` takes `assurance` (default `verified-identity` for trusted internal callers such as tests and seed tools); the controller passes the real value; non-verified resolve/close is rejected in the service too.
6. Low items fixed: `list_knowledge_proposals` bounded; the ORM unique constraint now has an explicit name matching the migration; `incident_knowledge_proposal.knowledge_entry_id` gained a foreign key to `knowledge_entries` (both in the still-unreleased `d4f7b0a2c503`).
**Not changed / decisions for the owner**: unattributed and shared-token callers can still reopen a resolved incident (pre-existing; behaviour documented); offset paging with client-set `created_at` can skip/duplicate under concurrent inserts (keyset paging not done); the downgrade of `d4f7b0a2c503` fails opaquely if rejected/superseded rows exist (rolls back safely). The reviewer's note that my SidebarNav edit also changes imports is the other workstream's uncommitted edits; my change is the one link and one icon import.

**Tests (disposable PostgreSQL)**: alignment file 15 passed; combined incident + knowledge + migration + retrieval + overlay + catalog + diagnostic + reliability run **369 passed, 1 failed** (`test_incident_api.py::test_unauthenticated_requests_are_rejected`, obsolete login assertion); analyzer integration + knowledge source/safety suites: the **identical set of 21 failures** as before (login retirement), so the reviewer-guard change introduced none. `tsc --noEmit` and eslint clean.

**Environment note**: my disposable container `eims-knowledge-b-pg-20261119` disappeared mid-session (not removed by me; `docker ps -a` no longer listed it). I recreated it with the same role, databases and extensions; earlier scratch databases and their seeded data are gone.

## 2026-11-19 (later) — Incident Workspace: summary-first UI (presentation only)

**Scope kept**: only `clients/dashboard/src/app/incidents/page.tsx` was rewritten. No backend, schema, migration, authorization or audit change; `SidebarNav.tsx` untouched this round (the link already existed); no new store, proposal workflow or API.

**What changed**
- List: title, status, severity, root-cause state, last-updated only.
- Detail first screen: status / severity / root-cause badges and updated time; a factual one-paragraph summary assembled from recorded data (evidence count and sources, correlation confidence explicitly "not what caused it", reopen cycle); three at-a-glance cells (current diagnosis, remediation, verification); a knowledge-warning line when a snapshot or current record is stale, unavailable, version-mismatched or changed; "Next steps" built only from recorded state (no hypothesis yet, open hypotheses need a verified reviewer, proposed remediation not executed, executed but unverified, completed with a confirmed cause and no proposal) plus up to four investigation steps from the linked Diagnostic Knowledge record, each labelled as a reference, not a confirmed procedure. When nothing is indicated it says so.
- Six native `<details>` disclosures, all collapsed by default, each header carrying counts and status badges: Diagnosis & Evidence, Remediation & Rollback, Verification, Diagnostic Knowledge Reference, Knowledge Proposal, Audit Trail (headers show per-assurance counts). Within them, per-hypothesis and per-remediation details (reasoning, proposer/confirmer with the full assurance sentence, evidence references, timestamps, risk, rollback, verification criteria, snapshot vs current record) open on demand; all original actions and validation (record/reject/supersede hypothesis, propose/execute remediation, knowledge proposal, Load more) are unchanged.
- Hypothesis, confirmed root cause, rejected and superseded are separate labelled states; stated confidence is shown as "not proof". Remediation is always labelled incident-specific unless a catalog record carries canonical guidance (none does today). Knowledge proposal state is read from `/api/v1/knowledge/proposals/mine`, which only returns the caller's own entries; otherwise the page says the state is unavailable from this view and links to Knowledge review.

**Verification**: `tsc --noEmit` exit 0, eslint clean. Real Chromium against my own backend (port 8022 → disposable DB `eims_workspace_test`; only `/api/eims/**` routed to it; stopped afterwards) with a seeded open incident (stale knowledge link, one executed-partial and one proposed remediation, one shared-token action), a completed incident (confirmed + rejected + superseded hypotheses, verification record, pending proposal) and an empty one. Observed: list of three scannable items; open and completed summaries; all six sections collapsed on load with correct header badges ("review stale", "4 unattributed 1 shared token", "pending"); Enter and Space toggle a disclosure from the keyboard; expanded content retains snapshot-vs-current, assurance sentences and the full audit; the completed view offers no record, confirm, resolve or verify controls; proposal state shows "pending"; empty incident shows "None recorded" and a data-backed next step; at 390 px width the page content stays inside the viewport (the shell header is 499 px wide on its own and causes document-level horizontal scroll; it belongs to another workstream). Screenshots: `docs/knowledge/browser-evidence-20261119/workspace/` (`ws-*.png`).

**Limitations**: no component-test harness exists, so no automated UI tests were added; the "canonical content changed" and version-mismatch warnings are rendered from the same logic but were not triggered in the browser (the seeded data had unchanged content and no version scope); not run through the real dashboard proxy to the shared backend (it runs older code); proposal status for other users' entries is deliberately unavailable; backend suites were not re-run because no backend file changed this round; Next-steps wording is mine and should be reviewed for tone by the owner. **Verdict for this task: ACCEPTED WITH LIMITATIONS** (overall Knowledge Foundation remains NOT ACCEPTED).

## Round: Analyzer-centric incident integration (2026-11-19)
- Backend contract: `GET /api/v1/incidents/by-evidence`, `created`/`match` on `POST /incidents`; no migration (head `d4f7b0a2c503`).
- Components: `EventIncidentLink`, `IncidentWorkspace` (embeddable), `/incidents` kept as compat page. Contract for the Analyzer owner: `docs/knowledge/ANALYZER_INCIDENT_INTEGRATION_CONTRACT.md`.
- Browser E2E (disposable DB, harness since deleted): create/link/no duplicate, hypotheses, remediation, completed incident (verified reviewer), knowledge proposal pending in existing flow, audit 7 events, collapse/expand, compat deep link, back nav. Evidence: `browser-evidence-20261119/link-*.png`.
- Tests: 48 passed (incident link/alignment/records/api/migration + knowledge overlay); knowledge/catalog subset 121 passed, 1 stale route-count guard updated (`/record` added), 8 errors in `test_analyzer_postgres_integration.py` (need their own DB; not isolated here).
- Not done (Cursor-owned): embedding in Analyzer right panel, mojibake source fix, `/incidents` redirect, SidebarNav entry removal; global top bar overflows at 390 px.

## 2026-11-19 (later) — Cursor P0: Analyzer History restore + right-side Incident embed + Infra nav

- Analysis History / Diagnostic Knowledge Catalog preserved; mojibake fixed at source (`·` / `—`).
- `EventIncidentLink` in history Event Detail; `IncidentWorkspace` docked on Analyzer right; `/incidents?id=` → `/analyzer?incident=`; Incidents sidebar entry removed.
- System & Infra links restored as normal clickable entries; Observability (Grafana/Prometheus) starts with Core by default.
- Observability card label clarified: PostgreSQL probe ≠ PgBouncer path.
- Static/focused tests: `tests/test_system_infrastructure_consoles.py` **10 passed**.
- Full shared-backend Browser E2E of create/link/diagnose still **NOT ACCEPTED** (P0 UI correction only).

## Round: provider-aware retrieval + second-store reconciliation (2026-11-20)
- Windows retrieval is provider-aware (`matchKind`/`matchBasis`); 163 baseline IDs unchanged and pinned (`tests/data/knowledge_baseline_ids_20261119.json`); catalog now 175 (153 context + 22 candidates) after migrating 12 curated records; `event_knowledge.json` kept (provider_names added). Details, retirement criteria and next gaps: `PROVIDER_AWARE_RETRIEVAL_AND_RECONCILIATION_20261120.md`.
- Next highest gap: approved-knowledge lookup is provider-blind (needs `knowledge_entries.provider` migration), then cutover of curated reads to the canonical records.

## Round: Automatic Incident Intelligence — backend closure (2026-11-20, later)
- Evidence identity (`incident/evidence_identity.py`), strong-only correlation with `ambiguous_not_merged`, Engineer Notes (migration `a7d2c5e8f604`), Event 1026 evidence contract (`incident.evidenceRefs`, `.NET` attributes, record id) and a real-HTTP end-to-end driver (`tools/e2e_incident_intelligence.py`, 41/41 main + 8/8 after hard restart on a disposable PostgreSQL). Details: `docs/acceptance/2026-11-20-consolidated-claude-backend-acceptance.md`.
- Knowledge: structured `diagnostic_guidance` added to 3 more candidates (Cisco 113005, 113019, OpenSSH AUTH-FAIL) from the 2026-11-19 source collection; nothing promoted.
- The end-to-end run found and fixed a real defect: occurrence-fingerprint digests broke verification (`evidence_digest_mismatch`, then a DB check violation). Verification now revalidates the fingerprint server-side.
