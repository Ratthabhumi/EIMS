# Analyzer ↔ knowledge integration report (2026-11-22)

## Architecture finding (evidence from code)
The planned flow "catalog → KnowledgeEntry → Analyzer" cannot be implemented as written, and does not need to be:
* `KnowledgeEntry.source_history_id` is `NOT NULL` with a foreign key to `analysis_history` (RESTRICT) and unique; `/api/v1/knowledge/proposals` requires a `history_id`. A catalog row has no analysed case, so importing it would require a fabricated case.
* The Analyzer already consumes the **catalog directly** (`parse_event_metadata` → `entry_for_metadata` / `catalog_summary`) and consults the **governance overlay** (`knowledge_review`) through `retrieve()` for trust level.
So the implemented flow is: `Source Catalog → Catalog Adapter (eligibility + operational view) → Governance overlay (registration, human decisions) → Analyzer / Parser → Diagnostic Result with operational guidance`. `KnowledgeEntry` stays the store for human-written case knowledge; a catalog record can be turned into a *proposal draft* for it later (contract check below) once an owner decides a path.

## What was implemented
* `backend/domain/knowledge/catalog_adapter.py`: `classify`, `operational_view` (what happened / why / inspect / action / risk / rollback / recovery verification / evidence+source / version / limitations), `operational_problems`, `evaluate` (ELIGIBLE, INELIGIBLE, BLOCKED, NEEDS_HUMAN_REVIEW, ALREADY_IMPORTED, STALE_SOURCE).
* `backend/domain/knowledge/remediation_safety.py`: negation-aware destructive-action detection (single verb list for register, validator, adapter).
* `backend/domain/knowledge/service.py`: the governance catalogue now covers all 911 records (`candidate:<id>`, `reference:<id>` added; hash excludes only `catalog_id`, so register and overlay hashes agree for all 911); `register_catalog_records` (idempotent, audited, automation-attributed).
* `SolutionSummary.operationalGuidance` (optional, backward compatible) filled by `catalog_summary` and, for Veeam/VMware diagnostics, by `build_summary`, for legacy diagnostics, field-linked, message-linked and SQLSTATE-linked candidates. Each item is `stated` or `not_stated`; missing items are listed in `missing`; `reviewState` is never "approved".
* `tools/catalog_import.py`: dry-run preview (artifacts `catalog_import_eligibility.json/.csv`) and `--apply` (loopback, non-standard port, allowlisted disposable database only; refuses everything else — verified).

## Results (computed, 911 records)
| Class | Records | ELIGIBLE | BLOCKED | INELIGIBLE |
|---|---:|---:|---:|---:|
| A Windows context | 153 | 0 | 0 | 153 |
| B parser-linked | 39 | **3** | 36 | 0 |
| C parser-mapped references | 312 | 0 | 0 | 312 |
| D state/telemetry | 4 | 0 | 4 | 0 |
| E unmapped candidates | 57 | 0 | 0 | 57 |
| F reference-only | 346 | 0 | 0 | 346 |
| **Total** | 911 | **3** | 40 | 868 |
Eligible: `cisco_asa:official_message_id:106024`, `cisco_asa:official_message_id:113005`, `veeam_vbr:eims_diagnostic:VEEAM-REPLICA-SNAPSHOT-CHAIN`. Missing items across the 36 blocked class B: recovery verification 25, recommended action 23, risk statement 22, rollback for a destructive action 4. NEEDS_HUMAN_REVIEW: 0 (the three eligible records have no open validator finding).
Registration demonstrated on a throw-away PostgreSQL 16 (removed afterwards): first run created 3 overlay rows and 3 `catalog_import` events attributed to automation; second run created nothing (all `ALREADY_IMPORTED`); refusal checks for the standard port and a non-allowlisted database passed. The same behaviour is covered by tests.

## End-to-end diagnostic result contract (tested through the real parser/Analyzer path)
For the two ASA eligible records the result carries every required item with stated content (`missing == []`), the recovery-verification items equal the catalog's `verification_criteria`, risk and rollback are present, source URLs and version scope are present, and the review state starts with `PENDING_HUMAN_REVIEW`. The Veeam eligible record is served by the vendor adapter; `build_summary` now attaches its guidance too (`guidance_for_entry`), and a test drives it through `build_summary` with a synthetic Veeam log.
For a class B record that lacks recovery verification (PostgreSQL deadlock) the result says so: `recoveryVerification.status == "not_stated"`, `missing` lists it, nothing is invented. For a reference-only lookup (SQLSTATE 23505) there is no guidance at all, so a reference is never presented as a diagnostic capability.

## Contract with `KnowledgeEntry` (unchanged)
Columns (32) and `KnowledgeProposalContent` are unchanged and pass their existing tests. Mapping the 100 diagnostic candidates onto that contract: **25 are rejected** by the high/critical rule (destructive remediation without rollback and validation), down from 28 after the negation-aware rule showed three records only prohibit the action. Catalog version scopes (often > 64 characters) do not fit `product_version`, and no catalog carries a risk level, so a human must set it. This is why a bulk import into `KnowledgeEntry` was not built.

## Not achieved (blockers)
* Only 3 of 39 class B records are complete; 25 lack recovery verification, and no source for the 25 rejected remediation records states rollback/verification (see `remediation_research_ledger.json`).
* No frontend change: the new field is returned by the API but the dashboard does not render it yet. No dashboard was built before the data flow existed, as instructed.
