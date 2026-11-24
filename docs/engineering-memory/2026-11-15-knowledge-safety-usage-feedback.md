# EIMS finalization delta — Knowledge Base safety and usage feedback (2026-11-15)

## Verified runtime and preservation
- Work performed on Mew via Remote Desktop Commander only.
- Branch/HEAD unchanged: `integration/eims-consolidated` / `85493b2`.
- No commit, push, reset, clean, stash, destructive cleanup, or operational DB access.
- Last full Browser Acceptance remains final16: 33/33; Playwright 2/2 PASS, exit 0. New Knowledge UI/API additions below were separately verified by PostgreSQL integration tests and a production build; final16 was not rerun after these additions.
- Production-path smoke backend running on port 8001 against synthetic DB `eims_browser_acceptance_20261115`: Login 200, Knowledge search 200, Stats 200, Health 200/HEALTHY; PostgreSQL, Redis and MinIO UP. This is synthetic application-path verification, not production deployment certification.

## Knowledge Base improvements
- Full-text approved-only search across title, source family, diagnostic identity, root cause, solution steps, impact, prevention, product applicability, prerequisites, validation/rollback, evidence notes and references. Query is parameterized and LIKE wildcard characters are escaped. Pending/rejected records are excluded.
- Added structured applicability: product, product version, environment and prerequisites.
- Added remediation safety metadata: risk level (low/medium/high/critical), validation steps and rollback steps.
- High/Critical proposals are rejected unless both validation and rollback steps are present. This is checked by Pydantic, after sensitive-data redaction, and again before approval.
- Exact diagnostic identity matching remains the only path for automated reuse. Product/environment applicability is surfaced as a caution for Engineer confirmation; no approximate match becomes an authoritative fix.
- Added append-only Knowledge Usage feedback tied to an approved Knowledge Entry and a new History record owned by the reporting user. Each record includes a source-history SHA-256, reporter, outcome and timestamp.
- Outcomes: resolved, partially_resolved, not_resolved, not_attempted. Duplicate reports for the same knowledge/history/reporter are rejected. Cross-user History cannot be used. Usage summary exposes counts, not reporter notes.
- Feedback does not automatically raise AI confidence or alter the approved Knowledge Entry.

## Database and migrations
- Alembic head is now `d2f6b8c1e305`.
- `d1e5a7c9b204`: structured applicability and safe-remediation fields.
- `d2f6b8c1e305`: append-only Knowledge Usage feedback table.
- Both synthetic DBs migrated successfully: `eims_browser_acceptance_20261115` and `eims_regression_test_20261115`.
- Existing Knowledge rows are preserved; new JSON columns have safe empty-list defaults and existing risk defaults to medium.
- Integration fixture clears usage then knowledge rows only inside an outer rollback transaction, so prior synthetic approved entries do not contaminate test results or get deleted persistently.

## Verification
- Knowledge lifecycle/search/safety/usage/migration tests: **7 passed**, exit 0.
- Test coverage includes pending-not-searchable, approved full-text search, applicability round-trip, High-risk missing rollback rejection, validation/rollback reuse, usage outcome recording, source-history hash, cross-user owner isolation, duplicate-report rejection, migration lineage and table presence.
- Dashboard Production Build: compiled, TypeScript passed, static pages generated 15/15.
- Targeted Ruff F401/UP017, Python compilation and `git diff --check`: PASS. Full all-rules Ruff remains not clean due legacy findings outside the targeted scope.

## Remaining closure gates
1. Independent human domain review of 12 DEV gold cases and evidence/diagnosis/resolution claims; freeze the gold set; then run 5 HELDOUT cases without tuning against them.
2. Curate the initial approved knowledge corpus from official vendor sources and authorized/sanitized real incidents. Synthetic entries are not a production knowledge corpus.
3. Define and implement a domain-approved stale/revalidation policy (review interval, version support window, superseded/withdrawn state and who owns revalidation). Do not invent the policy interval.
4. Explicit JWT `exp` boundary acceptance separate from server-side DB-session expiry.
5. Witnessed backup/restore and rollback, WAL/PITR, retention, measured RPO/RTO, failover/recovery, capacity/load, TLS/secrets, monitoring and operational ownership.
6. Controlled Engineer pilot with authorized sanitized incidents and feedback on correctness, safety and usefulness.

## Interpretation
- EIMS is not closed yet. Engineering Incident Management has strong synthetic/browser and production-path evidence, but independent domain validation and operational recovery sign-off remain.
- Knowledge Base now has search, applicability, safe-remediation metadata and usage feedback, but it still needs a curated authoritative corpus and an approved stale/revalidation policy.
- Do not describe synthetic tests as production incident outcomes or production certification.
