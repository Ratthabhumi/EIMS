# Knowledge Foundation — Implementation Status (2026-11-19)

This is a status record, not an acceptance claim. It states what was verified in
the repository and what remains unimplemented.

## Verified facts about the current implementation

| Fact | Evidence |
|---|---|
| One loader reads both catalogs | `backend/domain/analyzer/services/operational_catalog.py`: `CATALOG_PATH = operational_event_catalog.json`, `VENDOR_CATALOG_PATH = diagnostic_knowledge_catalog.json` |
| Operational catalog is a list of 141 entries | parsed directly: `event_id, provider, title, category, severity, description, operator_context, related_events, keywords, source` |
| Diagnostic catalog is `{schema_version, entries}` with 22 entries | `diagnostic_knowledge_catalog.json` |
| Diagnostic entries already carry investigation, limitations, official references, compatibility scope | field inspection |
| Neither class has remediation, verification, `verified_at`, `source_kind` | field inspection |
| "Engineering Knowledge Base" is a **separate** module | `backend/api/routers/analyzer/knowledge.py` — proposals/review-queue/`KnowledgeEntry`, unrelated to the diagnostic catalogs |
| The Analyzer's knowledge path is `operational_catalog.py` | no dependency on the KnowledgeEntry module |
| Repository state | branch `demo/2026-11-24`, HEAD `3f2beea`, 168 working-tree entries, nothing staged |

## What this round did NOT implement

The P0 items require coordinated changes across data, API, migration and the
Next.js portal. They were **not** performed in this round:

1. `knowledge_class` separation in the API response and the UI counters.
2. Additive schema for `remediation`, `verification`, provenance, version scope.
3. Migration of the 22 records (and preservation of the 141).
4. Per-entry source verification of the 22 records.
5. Promotion workflow (context → diagnostic).
6. Retrieval/UI separation.

No record was promoted, no field was fabricated, and no database was modified.

## Why the split cannot be cosmetic

Adding the columns and copying `N/A` into them would satisfy a schema check but
not the engineering standard: a record is validated only when the sections are
substantive and sourced. The gate in `KNOWLEDGE_QUALITY_STANDARD.md` therefore
must be enforced by the loader/API, not by the presence of a column.

## Smallest safe implementation slice (next round)

1. `operational_catalog.py`: return `knowledge_class` per entry
   (`operational_context` | `diagnostic`) and expose two counters. Read-only,
   no data change, no migration.
2. `GET /api/v1/analyzer/knowledge/summary`: the two counts + per-product
   distribution + how many diagnostic entries have provenance/investigation.
3. Portal: replace the single `163` with the two counters and label the context
   tier "Context reference — not a complete diagnostic procedure".
4. Only then add the additive columns and migrate the 22 entries, marking every
   new field `not_verified` until a human verifies the source.

Steps 1–3 are additive and reversible; step 4 changes stored data and must be
accepted separately.

## Remaining limitations

- The 141 context records are not diagnostic procedures.
- The 22 diagnostic records are not source-verified in this round.
- No remediation or verification guidance exists for any record.
- The KnowledgeEntry (human review) module is a separate, unrequested feature and
  must be assessed for removal from the portal navigation before it is deleted.
