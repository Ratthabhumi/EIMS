# Knowledge Model Gap Analysis (2026-11-22)

Computed by `tools/analyze_knowledge_model.py` (numbers below are copied from `knowledge_model_mapping.json`, never typed by hand). "Stated" means a field is present and is not a "Not stated…/None" placeholder.

## 1. What already exists (checked in code, not assumed)
| Layer | What it is | Consumer today |
|---|---|---|
| Four JSON catalogs (911 records) | Windows context 153; legacy diagnostic entries 28; vendor candidates 72; vendor references 658 | Analyzer only: `parse_event_metadata` → `entry_for_metadata` / `catalog_summary`; the 181 loaded records also feed `GET /api/v1/history/catalog` |
| `KnowledgeEntry` (+ lifecycle, usage, review) | **The engineer-facing operational model**: title, root cause, solution steps, impact, prevention, product/version/environment, prerequisites, `risk_level`, `validation_steps`, `rollback_steps`, evidence notes, references, status, reviewer | `/knowledge` page and `/api/v1/knowledge/*`; filled only by human proposals that require a `history_id` |
| `KnowledgeSourceCandidate` | 20 vendor-source candidates imported from a separate file | `/api/v1/knowledge/sources` |
| `knowledge_review` / `knowledge_review_event` (governance) | lifecycle candidate → source_verified → validated → approved with gates, content-hash binding, append-only events | **No API or UI**; used by tests and `knowledge.service` only; covers the 181 records returned by `load_catalog()` |

Key consequence: the operational model the owner describes (what happened, why, what to check, how to fix, risk, rollback, proof of recovery) **already exists as `KnowledgeEntry`**. The catalogs are *source material*, not that model, and nothing converts one into the other.

## 2. Measured coverage of the seven sections (per class)
| Section → indicator | A Windows (153) | B parser-linked (39) | D state (4) | E unmapped (57) | C refs (312) | F refs (346) |
|---|---:|---:|---:|---:|---:|---:|
| Symptom stated | 153 | 39 | 4 | 57 | 312 | 338 |
| Applicability (version/product) | 100 | 39 | 4 | 57 | 312 | 346 |
| Cause listed | 153 | 39 | 4 | 56 | 312 | 346 |
| Alternative causes | 0 | 11 | 4 | 47 | 0 | 0 |
| False-positive risks | 0 | 2 | 4 | 0 | 0 | 0 |
| Investigation | 39 | 39 | 4 | 57 | 0 | 0 |
| Commands with expected output | 0 | 11 | 4 | 57 | 0 | 0 |
| Remediation | 0 | 16 | 4 | 57 | 0 | 0 |
| **Risk stated** | 0 | 17 | 1 | 37 | 0 | 0 |
| **Rollback stated** | 0 | 14 | 0 | 0 | 0 | 0 |
| **Recovery verification stated** | 0 | 14 | 1 | 18 | 0 | 0 |
| Source | 111 | 39 | 4 | 57 | 312 | 346 |

(Class A applicability 100 = 53 explicit OS statements + 47 product-level statements; classes C and F are references by design and need none of the operational sections.)

**Engineer-ready records** (every core section stated, and the record passes the existing `KnowledgeEntry` contract without a high-risk rollback/validation failure): **B 3 of 39, D 0 of 4, E 6 of 57 — 9 of 100 diagnostic candidates.** Having a parser (class B) does not mean the record is usable by an engineer: 25 of 39 class B records have no recovery verification, 22 no stated risk and 25 no stated rollback.

## 3. Structural gaps (fields no catalog has)
rollback_steps (candidates keep it inside free-text risk), required_permission, operational_impact / downtime_risk (merged into one `operational_risk` string), human_approval_required, preconditions, expected_healthy_state, escalation_conditions, structured abnormal output, evidence per cause, Windows build/range (no source states a build; the one "build" mention found is tied to a single update), review history on catalog records beyond the 181 loaded ones.

## 4. Contract finding (catalog → `KnowledgeEntry`)
Mapping each class B/D/E record onto `KnowledgeProposalContent` (no invented values; `risk_level` high only when remediation names a state-changing action; `product_version` left empty):
| Class | Records | Validates as-is | Rejected by the contract's high/critical rule |
|---|---:|---:|---:|
| B | 39 | 35 | 4 |
| D | 4 | 2 | 2 |
| E | 57 | 35 | 22 |

Observations: (1) the contract demands validation and rollback only for high/critical risk, and the **risk level exists in no catalog**, so a human must choose it; (2) `product_version` allows 64 characters while most catalog version scopes are longer and cannot be truncated without changing meaning; (3) proposals require a `history_id` of an analysed case, so there is no bulk path; (4) "validates as-is" is weaker than "engineer-ready" (35 of 39 class B pass, only 3 are complete).

## 5. Decisions taken (and not taken) — database
* **No new table or migration.** `KnowledgeEntry` already models the operational answer and has no catalog consumer to justify another table; a second store would duplicate it. Creating one now would be a dead table.
* **Governance: implemented without a migration.** `evaluate_gate`/`promote` now take `actor_kind`; source_verified, validated, approved, deprecated and superseded require `actor_kind == "human"` (fail closed for `ai_assist`, `automation`, empty or unknown); earlier decisions not recorded by a human no longer satisfy prerequisites; the kind is stored in the existing append-only event `evidence` JSONB. A queryable column/CHECK constraint would need an Alembic migration — deferred until an API exists to record decisions.
* **Not done, needs an owner decision:** (a) an import path from catalogs into `KnowledgeEntry` (proposal drafts for a human to complete); (b) exposing the governance transitions through an authenticated API with reviewer roles/authority; (c) extending governance to all 911 records (Round 1 problem P1).

## 6. Recommended order of work (smallest first, each with a consumer)
1. Fill the stated gaps for the 100 diagnostic candidates from vendor text only (risk, rollback, recovery verification) — research per record; unfillable fields stay "not stated".
2. Add `rollback_steps` and `verification_steps` as separate fields in the candidate schema (additive, loader-validated) so the Analyzer can show them.
3. Decide (a)–(c) above; only then add columns (`catalog_id`, `catalog_content_hash` on `KnowledgeEntry`; `actor_kind` column) through an additive, reversible migration tested on a disposable database.
4. Show recovery verification and rollback in the Analyzer summary (today `catalog_summary` shows causes, steps, risk text and next-evidence commands; a code search finds **no backend reader of `verification_steps`, `verification_criteria` or `rollback`**, so recorded recovery text cannot reach the Analyzer output, and for the 11 newly linked candidates `verification_steps` is "Not stated" in every case).
