# A17 Phase 1 — Security Gap Report

Date: 2026-11-19 · Read-only.

## G-1 (HIGH) Application engine has no identity check
`backend/infrastructure/database.py:68` builds the only application engine from `settings.database_url`. Nothing reads `current_database/current_user/current_schema` after connecting. If the environment points at an operational database, every runtime mutation proceeds. This is the root of A16 HIGH-4 rather than a per-script bug.

## G-2 (HIGH) Test fixture can target the operational database
`tests/test_global_search_integration.py:42-45` creates an engine from `settings.database_url` and writes (`:105`). No allowlist, no marker, no identity check. Running the suite with the operational stack up mutates it.

## G-3 (HIGH) Maintenance CLI deletes without any guard
`tools/maintain_analyzer_sessions.py:20` resolves `EIMS_MAINTENANCE_DATABASE_URL`; `:27` creates the engine; `--apply` commits deletion. No URL allowlist, no identity check, no dry-run enforcement beyond the flag.

## G-4 (HIGH) Seed script contradicts its own documentation and deletes
`tools/seed_analyzer_incident.py:13` claims it never deletes; `:443` executes `DELETE FROM analysis_history WHERE parse_method = :pm`. No guard. Either the claim or the code must change; the code is what runs.

## G-5 (MEDIUM) Benchmark measures a different database than it seeds
`tools/sprint11_benchmark.py` truncates/seeds `engine` (`:256`) but measures through `TestClient(app)` (`:262`), which uses `settings.database_url`. No equality assertion. Latency evidence can come from an unseeded database.

## G-6 (HIGH) Chat_HAND journal/policy are not wired
`gateway/lib/execution-journal.mjs` and `risk-policy.mjs` are imported by 0 gateway files. No execution path enforces them.

## G-7 (HIGH) Completion proof remains caller-asserted
`record()` accepts a `proof` object whose `observedBy` is a caller string; the chain is unkeyed; `verify()` does not persist or check proof; `recover()` is public. Under ADR-01 L1 this must be downgraded to "local integrity, not authenticity", and SUCCEEDED must require an executor-observed result.

## G-8 (MEDIUM) Authorization is caller-authoritative
`authorize({action, approver, approverVerified})` accepts a caller boolean. There is no server principal and no action registry.

## G-9 (LOW) Missing referenced document
`docs/V12_A16_CHAT_HAND_TRUST_BOUNDARY.md` is referenced by the journal comment and does not exist.

## G-10 (LOW) Migration path is correctly isolated
`migrations/env.py` is not referenced from `backend/`. No change needed; recorded to prevent a false positive.

## Severity summary

| Sev | Count | IDs |
|---|---:|---|
| HIGH | 6 | G-1, G-2, G-3, G-4, G-6, G-7 |
| MEDIUM | 2 | G-5, G-8 |
| LOW | 2 | G-9, G-10 (no action) |

## Limits of this report

Files were traced by search plus targeted reads of the seven named targets. The remaining runtime files were classified by path and role, not by full call-graph walk. Any claim of "complete coverage" would be unsupported until each runtime file is traced from its router to its session.
