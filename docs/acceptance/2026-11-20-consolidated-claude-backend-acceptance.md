# Consolidated backend acceptance — Automatic Incident Intelligence (Claude, 2026-11-20)

Branch `demo/2026-11-24`, HEAD `3f2beea`, 257+ uncommitted paths preserved; nothing staged, committed or pushed; `integration/eims-consolidated` untouched; operational database never accessed (disposable PostgreSQL in container `eims-knowledge-b-pg-20261119`, port 56470, role `eims_incident_test`, non-superuser).

## Verdict
**ACCEPTED WITH LIMITATIONS** for the Claude-owned backend scope (evidence identity, correlation, Notes, evidence contract, provider-aware retrieval, Knowledge reconciliation). **EIMS is NOT declared PRODUCT ACCEPTED**: the browser leg of the end-to-end acceptance was not proven against the current backend (see "Not proven"), Knowledge has 0 source-verified/validated/approved records, and the Notes UI is Cursor's open item.

## What was already accepted (not re-run without reason)
Incident Core lifecycle and assurance tiers, diagnosis/remediation workflow, verification policy, Knowledge review lifecycle, hash/stale detection, summary-first workspace, Analyzer three-tab shell (Cursor), proxy `X-Total-Count`.

## Newly implemented
| Area | Change |
|---|---|
| Evidence identity | `incident/evidence_identity.py`: provider-qualified event key `<id>@<provider>`; occurrence fingerprint (SHA-256 over family/provider/event/record id/time/channel/host/message hash) produced **only** when a record id or event time exists; text alone is never an identity. `IncidentService.enrich_evidence` derives these server-side from the persisted analysis row (caller digests for analysis evidence are ignored). Digest-twin lookup makes the same occurrence submitted twice `event_already_linked`. |
| Correlation | Only a **strong** match (same concrete asset + same provider-qualified signature inside the window, open incident) merges automatically. Anything weaker => new incident with `match: ambiguous_not_merged` and `summary.correlation.candidates`. Unresolved-asset dedupe keys are bound to the source record, so unrelated events with the same Event ID cannot merge by key. Resolved/closed incidents are never merged into. Two strong candidates => ambiguous. |
| Engineer Notes | Migration `a7d2c5e8f604` (additive): `incident_note` (append-only trigger incl. TRUNCATE), `POST/GET /incidents/{id}/notes` (only `text` accepted; actor/assurance server-derived; oldest-first; `X-Total-Count`), audit event `record_type: note`. Notes have no state fields and cannot confirm/verify/resolve. |
| Evidence contract (Event 1026) | Parser: `Application`, `Framework Version`, `Exception Info`, verbatim `stackFrames` (<=40), `exceptionBlockCount`, `recordId`. `incident.evidenceRefs[]` groups exact repeats (same source, same stated time, same text) keeping every line number and the count; `lineBasis` states positions are in the submitted text. Raw text untouched. |
| Retrieval | Provider-aware Windows retrieval (`matchKind` direct/contextual/none, `matchBasis`), 163 stable IDs unchanged (pinned fixture), 12 migrated records, curated-summary provider guard (previous tranche, re-verified here by the end-to-end run). |
| Knowledge guidance | `diagnostic_guidance` now on 7 candidates (Cisco 106023/106024/302013/302014 earlier; 113005, 113019 and OpenSSH AUTH-FAIL added) strictly from the 2026-11-19 source collection; inferences labelled; all stay `candidate`. |

## Defect found by the end-to-end run (fixed)
Occurrence-fingerprint digests made verification fail (`evidence_digest_mismatch`, then DB check violation `cannot be resolved without verification`) because verification recomputed only the source-identity digest. Verification now revalidates the fingerprint server-side from the analysis row and stores the digest the row carries (`verification.py`). Regression: `test_14_occurrence_fingerprint_is_recomputable_for_verification` plus the E2E resolve step.

## Behaviour change to be aware of
Previously same-asset/different-signature and same-signature/unresolved-asset evidence merged as "medium". It is now ambiguous (not merged). Test `test_core_correlation_is_surfaced_...` was updated for this changed contract; no assertion was weakened elsewhere. Head-revision pins for `a7d2c5e8f604` were updated in the 4 test files that pin this chain.

## Correlation / identity matrix (tests/test_incident_identity_correlation_pg.py, real PostgreSQL)
| # | Case | Expected = actual |
|---|---|---|
| 1 | same asset, provider, event, close in time | merged (`correlated_with_open_incident`), 2 distinct occurrences kept |
| 2 | same asset, different event signature | `ambiguous_not_merged`, candidate recorded |
| 3 | different asset, same signature | separate, not even a candidate |
| 4 | same Event ID, different providers | separate (`ambiguous_not_merged`), signatures differ |
| 5 | same provider+event, different record ids | one incident, 3 evidence, 3 fingerprints (identical text not collapsed) |
| 6 | missing asset | never merged automatically |
| 7 | missing provider | not matched to a provider-qualified signature |
| 8 | no record id / no event time | no fingerprint; two evidence refs, no false identity |
| 9 | out-of-order evidence | merged, `first_seen` extended backwards |
| 10 | same evidence repeated (same row / same occurrence in another row) | `event_already_linked`, 1 fingerprint |
| 11 | resolved incident then new evidence | new incident |
| 12 | several related events in one request | one incident, N evidence |
| 13 | similar messages, different assets/records | separate incidents |
| 14 | fingerprint recomputable for verification; tamper detected | yes |

## Real end-to-end acceptance (HTTP, no mocks)
`tools/e2e_run_local.sh --restart` (driver `tools/e2e_incident_intelligence.py`): rebuilds disposable DB `eims_e2e_test`, runs the **real Alembic chain from empty to `a7d2c5e8f604` as the non-superuser role**, starts uvicorn (`EIMS_DEMO_SOFT_DEPS=1`), runs Scenarios 1-8, hard-kills and restarts the backend, then Scenario 9.
Result: **41/41 checks** (main) and **8/8** (after hard restart). Evidence JSON: `docs/acceptance/evidence/e2e_main_*.json`, `e2e_after-restart_*.json`. Highlights: .NET Runtime 1026 parsed, stack preserved, repeat grouped (lines 14,18), knowledge `direct/provider_and_id` context match (never approved); automatic incident created; duplicate submission idempotent; same-asset correlation; ambiguous cases not merged; `.NET Runtime` 1000 gets no `Application Error` knowledge; notes persisted with `demo/unattributed`; forged actor rejected (422); hypothesis stays hypothesis; unattributed cannot confirm/resolve (403); reviewer confirms with supporting evidence; remediation executed does not resolve; resolution without verification rejected (409); resolved with verification evidence; knowledge proposal pending, 0 approved; everything survives restart; migration head `a7d2c5e8f604`; health honestly `DEGRADED` (Redis down) with 503.

## Event 1026 and the second knowledge store
See `2026-11-20` Knowledge reports: `PROVIDER_AWARE_RETRIEVAL_AND_RECONCILIATION_20261120.md`, `EVENT_KNOWLEDGE_RECONCILIATION_20261120.md`. The 12 IDs missing from the catalog: 10 migrated as new records (11, 17, 20, 109, 134, 1069, 1135, 1511, 1530, 5009); 2 (`KAVT0000`, `KAVT0245-E`, Hitachi JP1) are not Windows events and stay outside the canonical catalog until a vendor family and source exist. 5011 and 1001 were provider conflicts (new provider-qualified records). `event_knowledge.json` is **not retired** (retirement criteria in the reconciliation report).

## External sources behind Knowledge changes
Microsoft KB 3036113 and Learn failover-cluster system events (1135); Microsoft KB 947238 and Learn TechNet archive (1530, 1511); Learn IIS process-termination guidance (5011); Learn WHEA page (provider name only); KB 911816 (ASP.NET unhandled-exception policy, 1026 context); Cisco ASA syslog reference (106023/106024/113005/113019/302013/302014); OpenSSH `auth.c`. Sources were read through search/fetch extraction; **human re-read is pending for every one**. No official page was found for 11, 20, 109, 134, 1069, 5009 and BugCheck 1001; those records say so.

## Tests
See the final run recorded in the closing report (counts filled from the last full run). New/changed test modules: `test_incident_identity_correlation_pg.py` (14), `test_incident_notes_pg.py` (8), `test_event_1026_evidence.py` (7), `test_event_knowledge_parity.py`, `test_knowledge_provider_retrieval.py`, `test_knowledge_guidance.py`; updated pins in `test_incident_migration.py`, `test_incident_workflow_*`, `test_knowledge_overlay_pg.py`, count pins in catalog tests.

## Files and migrations
Migration: `migrations/versions/a7d2c5e8f604_add_incident_note.py` (head). Backend: `incident/{evidence_identity,service,controller,schemas,verification,workflow,workflow_models,workflow_schemas}.py`, `analyzer/services/{parser,incident_extract,operational_catalog,event_knowledge,summary}.py`, catalog/curated JSON, `analyzer/schemas/analyze.py`, `routers/analyzer/analyze.py`, `knowledge/retrieval.py`. Tools: `e2e_incident_intelligence.py`, `e2e_run_local.sh`, `apply_*`, `migrate_curated_to_catalog.py`, `reconcile_event_knowledge.py`, `knowledge_inventory.py`. Fixtures: `tests/fixtures/dotnet_runtime_1026_gcm.txt`, `tests/data/knowledge_baseline_ids_20261119.json`.

## Not proven / remaining limitations
1. **Browser E2E against the current backend is NOT proven.** The portal on :3001 is wired to a different, older backend (:8021, no workflow/notes endpoints: panels returned 502 "Analysis service unavailable"). Through it I observed only that the UI creates an incident automatically after Analyze and opens the Incident Workspace; Notes UI is still the "API not enabled" panel. Re-run the UI scenarios after the :8021 backend is restarted on current code (or repoint `EIMS_BACKEND_URL`), owner: Cursor/whoever runs that process. I did not stop or modify that process.
2. Approved-knowledge lookup is still provider-blind (no `provider` column in `knowledge_entries`).
3. Knowledge: 0 source-verified/validated/approved; 15 of 22 candidates still lack structured guidance; FortiOS (5) has no readable source; 4 stale older-head pins in other owners' tests remain failing.
4. Correlation time basis is the request's `observed_at` unless the caller sets it; event timestamps in free text are kept as written but not parsed into correlation time.
5. `analysis` evidence correlation without an asset never auto-merges: repeated issues on an unregistered host stay separate (ambiguous) until a human links them.
6. Cycle-based "reopen by unattributed callers" and keyset pagination remain as before.
7. No human has reviewed any of this code.
