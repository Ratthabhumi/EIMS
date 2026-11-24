# Knowledge Architecture Decision (ADR-001, 2026-11-19)

Status: **Accepted (design) — implementation pending (Gate 2b)**.

## Context

The repository holds 163 knowledge records in two version-controlled JSON
catalogs:

| File | Records | Nature |
|---|---|---|
| `operational_event_catalog.json` | 141 | Windows event context |
| `diagnostic_knowledge_catalog.json` | 22 | diagnostic intent, with investigation/limitations/references |

Gate 1 already classifies them (`operational_context` / `diagnostic_candidate`
with lifecycle `candidate`) inside the loader. There is no persisted governance
state, so nothing can be verified, validated or approved, and the UI shows one
misleading total.

## Decision

**JSON remains the canonical source of content. PostgreSQL stores a sparse,
governance-only overlay.**

1. **No content duplication.** The 163 records are resolved from the catalogs at
   runtime by `catalog_id`. PostgreSQL never stores the event text, signatures,
   investigation steps or references.
2. **Sparse overlay.** A row exists only when a record actually needs governance
   state. Defaults are derived from the catalog: 141 records stay
   `operational_context` with lifecycle `not_applicable`; the 22 candidates
   default to `candidate`.
3. **Current state and history are separate objects.**
   - `knowledge_review` — latest effective projection (catalog_id, source,
     content hash, lifecycle, revision, review_required, supersedes,
     timestamps, optimistic version).
   - `knowledge_review_event` — append-only decisions (event id, catalog_id,
     type, from→to, actor, rationale, evidence ref, content hash at decision
     time, timestamp, correlation id).
   A JSONB column inside the mutable row is **not** used for history: editing it
   would rewrite the past.
4. **Classification is not lifecycle.** Operational context is never forced
   through `candidate → source_verified → validated → approved`, and is never
   counted as a diagnostic candidate.
5. **Source-hash invalidation.** If the canonical content hash for a reviewed
   record changes, the effective state must not remain verified: append a
   `review_required` event, retain the prior decision and hash as history, and
   stop treating the record as currently verified until new evidence arrives.

## Lifecycle transitions (enforced server-side)

```
candidate        → source_verified | rejected
source_verified  → validated | rejected | review_required
validated        → approved  | rejected | review_required
approved         → deprecated | superseded
```

Forbidden: `candidate → approved`, URL-only verification, validation without a
documented method, approval without authorization, any transition on a stale
content hash, and self-approval where separation of duties applies.

## Why not the alternatives

| Alternative | Rejected because |
|---|---|
| Copy all 163 records into a DB table | two sources of truth; drift between Analyzer and Portal |
| History as JSONB in the review row | mutable row ⇒ rewriteable history; not append-only |
| A new standalone knowledge service | duplicates the existing loader and retrieval path |
| Forcing operational context through the diagnostic lifecycle | category error; inflates diagnostic counts |

## Consequences and obligations

- All 163 `catalog_id`s must remain resolvable; synchronization is idempotent.
- Counts are computed as catalog defaults ⊕ overlay (sparse), never as one
  number mixing both classes.
- The summary endpoint stays `/api/v1/analyzer/catalog/summary` (Gate 2a).
- Because `start_eims.bat` runs `alembic upgrade head` at boot, the migration is
  deployment-critical: it must be proven on a disposable database from both the
  previous and the new schema before the Local stack is restarted.

## Unresolved before implementation

- Alembic graph must be verified (the historical `f7a1c3d9e502` head is not
  assumed).
- Whether the existing audit infrastructure satisfies the append-only event
  requirement (reuse preferred over a new table).
- Actor identity must come from the authenticated principal; self-approval
  enforcement needs the contributor recorded on the record.

## Status of the foundation

Gate 1 and Gate 2a are accepted. This ADR is design only: no table, migration or
service exists yet. `NOT ACCEPTED` for the Knowledge Foundation until Gate 2b–8
are implemented and tested.
