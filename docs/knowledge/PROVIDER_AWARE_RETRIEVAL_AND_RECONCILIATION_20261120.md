# Tranche 2 — Provider-aware retrieval and second-store reconciliation (2026-11-20)

**Verdict: ACCEPTED WITH LIMITATIONS for tranche 2A/2B as scoped. Knowledge Foundation overall: NOT ACCEPTED** (0 source-verified/validated/approved; provider names and migrated texts await human verification).

## 2A. Provider-aware retrieval
- `resolve_windows_entry(event_id, provider)` (`operational_catalog.py`) matches normalised provider + Event ID. Outcomes (`matchBasis`): `provider_and_id` (direct), `provider_unspecified` (single record, contextual), `provider_ambiguous` (several providers share the ID, nothing selected), `provider_unverified` (record has no verified provider names; contextual), `provider_mismatch` (record has verified provider names and none is the event's; **not applied**), `no_record`.
- `KnowledgeMatch` gained `matchKind` (`direct` | `contextual` | `none`) and `matchBasis`; set only by the server. `retrieve_windows` (`knowledge/retrieval.py`) is used by `_knowledge_match` for Windows events; non-Windows retrieval is unchanged (`matchKind direct`, `matchBasis identity`). Context records are never upgraded to a diagnosis.
- Optional `provider_names` on Windows records (80 records: Security-Auditing audit events, Defender, SCM, Application/Kernel-Power/EventLog/User32 ids, DNS-Client, and the 12 migrated). Only records WITH verified names can ever yield a "mismatch"; label-only records fall back to "unverified" so sloppy labels (e.g. "DNS Server", "TCP/IP") cannot cause false rejections.
- Stable IDs: all 163 baseline `catalog_id`s unchanged (`tests/data/knowledge_baseline_ids_20261119.json`, enforced). Provider-qualified identities (`<id>:<provider>`) exist only for the two migrated records whose plain ID was already taken: `5011:Microsoft-Windows-WAS`, `1001:Microsoft-Windows-WER-SystemErrorReporting`. No ID migration was needed.
- The curated-summary path is provider-guarded too (`get_curated_summary(event_id, lang, provider)`): wrong provider or ambiguous unspecified provider returns nothing; legacy calls without provider are unchanged.
- Regression tests (`tests/test_knowledge_provider_retrieval.py`, parametrised, incl. 1000/1001/1026 across providers, 5011 ambiguity, analyzer entry point `_knowledge_match`, non-Windows unchanged).

## 2B. Second-store reconciliation
Matrix for all 39 records: `EVENT_KNOWLEDGE_RECONCILIATION_20261120.md` (regenerate with `tools/reconcile_event_knowledge.py`).
- 39 records: 25 already had a baseline record (topic duplicated; causes/steps were **unique**), 12 had none, 2 are not Windows (Hitachi JP1 `KAVT0000`, `KAVT0245-E`).
- **The 12 missing IDs, all accounted for:** 11, 17, 20, 109, 134, 1069, 1135, 1511, 1530, 5009 (new records), plus 5011 and 1001, which are NOT missing but **conflict**: the baseline's 5011 is Windows Defender and 1001 is Windows Error Reporting; the curated texts describe IIS/WAS 5011 and BugCheck 1001. Before this work the Analyzer showed the IIS text for a Defender 5011 event and a BSOD text for a WER 1001 event.
- Migration (`tools/migrate_curated_to_catalog.py`, idempotent) wrote `diagnostic_guidance.localized_summary` (th/en verbatim) onto 25 existing records and created 12 new records through the existing loader. Nothing was deleted; `event_knowledge.json` only gained `provider_names`. Everything remains `operational_context`; no review state touched.
- **Two curated claims were not supported and were corrected on migration** (marked `CORRECTED` in evidence_basis): 5011 "hung / failed to ping WAS" (that is a different WAS event; Microsoft's guidance treats 5011 as a crash indicator) and 109 "shutdown transition" (sources say power-state transition). The curated store still contains the old text until cutover.
- Sources seen (search results, pages not read in full): official Microsoft pages for 1135, 1511, 1530, 5011, and 17 (provider name only). **No official page found** for 11, 20, 109, 134, 1069, 5009, 1001-BugCheck; 134's Event-ID-to-provider mapping could not be confirmed at all. Those carry no `official_references` and say so.
- JP1 `KAVT*` deferred: they need a vendor family and a Hitachi source; they remain only in the second store.
- Parity: `tests/test_event_knowledge_parity.py` proves for all 37 Windows entries that a canonical record for the same provider carries the curated text verbatim (35) or its marked correction (2), and that provider-guarded curated lookup behaves as specified.

## Decision: when may `event_knowledge.json` be retired?
Not yet. All of the following must hold first:
1. Cutover: `summary.py` reads curated text from the canonical record (provider-aware) instead of `event_knowledge.json`; parity tests then run against the live path.
2. The two corrected texts and all `provider_names` are verified by a named human (they are currently from general Windows knowledge and secondary sources).
3. JP1 `KAVT*` relocated (or consciously dropped by the owner).
4. A release containing the cutover has run without parity regressions, then the file is removed in its own change.

## Limitations / next gaps (highest priority first)
1. **Approved-knowledge lookup is provider-blind** (`verified_knowledge.search_approved_knowledge` keys on family + identity; `knowledge_entries` has no provider column). A human-approved Windows 1000 entry could apply to a `.NET Runtime` 1000 event. Needs a nullable `provider` column filled from the source analysis at proposal time (migration) and a "contextual only" rule for NULL — not done.
2. Cutover to canonical reads (above).
3. `history.py` category lookup and the DCOM alias (10005/10009/10028 → 10016) remain Event-ID-only.
4. Provider names/labels for the other ~70 Windows records are unverified (their matches are "contextual", never "mismatch").
5. Frontend badge does not yet display `matchKind` (backend contract is ready).
6. Tests: 149 knowledge/catalog/provider/parity tests pass. Full suite (excluding `test_analyzer_postgres_integration.py`, which needs its own DB) shows 10 failures **not caused by this work**: 3 secure-mode websocket/history tests, `test_system_infrastructure_consoles` (2, Cursor-owned UI), `test_compose_security_audit`, and 4 stale pins of older migration heads/identity boundary (`test_incident_ingest_unit`, `test_incident_ingest_v11_recovery_unit`, `test_telemetry_outbox_and_db_unavailable`, `test_api_identity_pg`) that broke when earlier rounds advanced the head to `d4f7b0a2c503`. They were not touched. No human has reviewed the diff.

## Changed files
`backend/domain/analyzer/services/{operational_catalog.py, event_knowledge.py, summary.py, operational_event_catalog.json, event_knowledge.json}`, `backend/domain/knowledge/retrieval.py`, `backend/api/routers/analyzer/analyze.py`, `backend/domain/analyzer/schemas/analyze.py`; tools `apply_provider_names.py`, `apply_curated_providers.py`, `migrate_curated_to_catalog.py`, `reconcile_event_knowledge.py`; tests `test_knowledge_provider_retrieval.py`, `test_event_knowledge_parity.py`, `test_knowledge_guidance.py`, count pins in `test_diagnostic_catalog.py`, `test_knowledge_service.py`, `test_catalog_summary_http.py`, `test_knowledge_overlay_pg.py` (141→153 context, 163→175 total; baseline pinned separately). No migration, no operational DB access, nothing staged or committed.
