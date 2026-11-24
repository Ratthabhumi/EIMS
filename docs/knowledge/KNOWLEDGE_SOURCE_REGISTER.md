# Knowledge Source Register (2026-11-19)

Policy: only verified, attributable sources may support a *validated* entry.

## Register rules

1. Prefer vendor documentation / vendor KB / release notes / protocol specs.
2. Record: publisher, title, URL or document ID, product+version, section,
   verification date.
3. A source that cannot be opened and matched to the claim is marked
   **unverified** and excluded from the validated count.
4. Never invent URLs, KB numbers or support statements.

## Current state

| Tier | Entries | Entries carrying an official reference | Notes |
|---|---|---|---|
| Diagnostic (`diagnostic_knowledge_catalog.json`) | 22 | 20 contain a URL; 2 have none | `official_references` is a structured field |
| Operational (`operational_event_catalog.json`) | 141 | 0 official references | only a short `source` label (e.g. provider name) |

No source in this repository was re-fetched and re-verified in this round. The
register therefore records the **existing** provenance only; it does not assert
that every URL was re-checked today.

## Required additions before the next expansion

- A verification date per entry (field does not exist yet).
- A `source_kind` discriminator: `vendor_doc | vendor_kb | release_note | spec | reproducible_test`.
- A gate that rejects an entry whose reference host is not a known vendor domain
  or a recorded reproducible test id.
