# Diagnostic Knowledge Quality Standard (v1, 2026-11-19)

An entry is **validated** only when all required sections are present and
internally consistent. Sections marked *optional* may be explicitly `N/A` with a
reason; an empty string is not acceptable.

## Required sections

| # | Section | Rule |
|---|---|---|
| 1 | Observed signal | Event id / code, provider, and the exact fields that carry it |
| 2 | Interpretation | What the signal means — and what it does **not** prove |
| 3 | Applicability | Product, vendor, version or version range, platform, preconditions |
| 4 | Possible causes | Labelled as *possible*, never as confirmed root cause |
| 5 | Investigation | Concrete next checks; read-only commands distinguished from state-changing ones |
| 6 | Remediation | Preconditions, action, permissions, expected effect, rollback, risk — or `N/A` + reason |
| 7 | Verification | Objective evidence that the problem is gone (event stops, state healthy, success recorded) |
| 8 | Limitations | False positives, version quirks, missing context, when not to apply |
| 9 | Provenance | Publisher, title, URL/document id, version, section, verification date |

## Hard rules

- **No root-cause claim** from a single signal. The catalog supplies context; the
  incident's root cause must be established from event + asset + timeline +
  correlation evidence.
- **No fabricated identifiers or citations.** Unknown values are omitted, not
  invented.
- **No parser metadata** dressed up as knowledge. Parser capability is a separate
  taxonomy.
- Remediation may be `N/A` only when observation/investigation is the correct
  engineering response; it must say why.
- Duplicates are merged by keeping one canonical ID and recording the merged IDs
  as aliases; nothing is deleted silently.

## Quality gates (automated)

1. Unique `id` across the whole knowledge store; aliases declared explicitly.
2. Required sections non-empty (or `N/A` + reason).
3. `applicability.version` present, or `version_scope: "any"` with justification.
4. Every validated entry has at least one reference with `source_kind` and
   `verified_at`.
5. No reference URL outside the approved vendor/test domains.
6. No phrase asserting certain root cause (`is the root cause`, `caused by`)
   outside an explicit `possible_causes` field.
7. Parser-only records live in a separate collection and are excluded from the
   validated count.
8. Search/filter tests: exact code, provider, product, version, free text, no-match.
