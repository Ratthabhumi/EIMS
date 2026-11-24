# Knowledge canonical cutover (curated Windows guidance) — 2026-11-20

Scope: the 39 curated summaries in `backend/domain/analyzer/services/event_knowledge.json` and the canonical operational catalog (recomputed: **175 records = 153 `operational_context` + 22 `diagnostic_candidate`**).

## Outcome
`summary.py` no longer reads curated guidance from `event_knowledge.json` for any identity that the canonical catalog carries. `event_knowledge.get_curated_summary()` now resolves through `operational_catalog` (`diagnostic_guidance.localized_summary`), provider-aware, and falls back to the legacy reader only for identities with no canonical record (the two Hitachi JP1 IDs). The legacy file is **not deleted**: it is the reference for the parity tests, the source for the two exceptions, and the reversible compatibility layer (`_legacy_curated_summary`). **Nothing was promoted**; all migrated records remain `operational_context`.

## Field-level parity (tools/knowledge_parity_audit.py -> `docs/acceptance/evidence/knowledge_parity_matrix_20261120.json`)
Legacy records carry only: `provider_names`, and per language `overview`, `causes`, `steps`. Everything else (risk, rollback, verification criteria, expected findings, diagnostic checks) is **missing in legacy** by construction; the canonical catalog carries those only where a source supports them and never invents them.

| Verdict | Count | Records |
|---|---|---|
| EXACT (all 6 legacy fields identical, th+en) | 35 | every other record in the matrix |
| EQUIVALENT_WITH_CORRECTION | 2 | `5011`, `109`: canonical text deliberately replaces unsupported legacy wording (marked `CORRECTED` in `evidence_basis`); the corrected text is what is now served |
| UNRESOLVED_EXCEPTION | 2 | `KAVT0000`, `KAVT0245-E` (Hitachi JP1): vendor family/product/source not established; **not migrated, not fabricated**; still answered by the legacy layer |
| CONFLICT / MISSING_IN_CANONICAL | 0 | — |

Provider behaviour is identical to the legacy rule and not broader: a stated provider must be one of the record's verified provider names (or its provider label when no names are listed); another provider returns nothing; an unstated provider never chooses between several providers' records (5011 and 1001 have provider-qualified records). All 37 Windows records report `foreign_provider_blocked = true`.

Provenance/status of the 37: lifecycle `operational_context`; `official_references`: 32 records have **0** references, 4 have 1, 1 has 2. Migration therefore did not add trust; these remain reference context, never approved diagnoses.

## Before/after regression
`tests/test_knowledge_canonical_cutover.py`: for every one of the 39 records x languages (`th`, `en`, unknown) x provider scenarios (unspecified, empty, "Unknown", a foreign provider, each declared name, upper-cased) the canonical-backed answer equals the legacy answer except the two corrected records; no identity is lost or broadened; callers never receive a shared template; DCOM aliases (10005/10009/10028 -> 10016) unchanged. Existing `tests/test_event_knowledge_parity.py` (verbatim carry-over, corrected markers, provider guard) still passes.

## What this does not claim
* `event_knowledge.json` is still shipped and read for 2 identities; it can be retired only after the JP1 IDs get a vendor family and an official source.
* Single source of truth is now true for the 37 Windows records; the two exceptions are explicit, not silent.
* No record became source-verified, validated or approved.
