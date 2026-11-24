# EIMS Engineering Memory — 2026-11-16 Reviewer Audit and Synthetic DB Acceptance

## Scope

Continued the existing repository on Mew. This checkpoint closes the missing security audit trail for Knowledge Reviewer capability changes and proves the source-candidate migration/import/API behavior on an isolated PostgreSQL instance using a non-superuser application identity.

## Implementation

- Reused the existing `audit_logs` journal; no duplicate audit subsystem or migration was introduced.
- `PATCH /admin/users/{id}/knowledge-reviewer` now writes `GRANT_KNOWLEDGE_REVIEWER` / `REVOKE_KNOWLEDGE_REVIEWER` records in the same transaction as the capability mutation.
- The payload records event type, actor username, target user ID/name, capability name, previous state and new state.
- User row is locked with `SELECT ... FOR UPDATE` before state comparison, preventing concurrent requests from recording duplicate or contradictory transitions.
- Repeating the same capability state is idempotent and does not create another audit event.
- Creating an account with `knowledge_reviewer=true` writes a create-time grant event in the same transaction.
- Legacy Admin accounts retain review capability for compatibility. Attempting to revoke that implicit capability now returns HTTP 409 instead of silently leaving the effective capability enabled.
- The new PostgreSQL integration test verifies grant, revoke, create-time grant, idempotence, Admin compatibility and denial to non-Admin callers.

## Synthetic PostgreSQL acceptance

Final accepted test environment:

- Container: `eims-reviewer-source-nonsuper-pg-20261116`
- Image: `pgvector/pgvector:pg16`
- Loopback port: `56446`
- Database: `eims_integration_test`
- Application identity: `eims_test`
- Role proof: `rolsuper=false`, `rolcreatedb=false`, `rolcreaterole=false`
- Alembic head: `a4b7c9d2e601`
- Catalogue import: 20 created, 0 updated, 0 unchanged
- `knowledge_source_candidates`: 20 rows
- `knowledge_source_events` import events: 20
- `knowledge_entries`: 0 rows
- Candidate state remains candidate-only / pending domain review; no Approved Knowledge was created.

The PostgreSQL superuser was used only to provision the disposable role, database and preinstalled extensions. Alembic migration, catalogue import and application integration tests ran using the non-superuser `eims_test` identity. No existing shared test password was changed.

An earlier disposable container created with `POSTGRES_USER=eims_test` was rejected as final acceptance evidence because that bootstrap role was a superuser. It remains untouched and must not be used as the least-privilege proof. No container or volume cleanup was performed.

## Verification

- Focused PostgreSQL integration/migration suite: **5 passed, 0 failed, 0 errors, 0 skipped**, exit 0.
- JUnit: `test-results/reviewer-source-nonsuper-postgres-20261116.xml`.
- Covered tests:
  - `test_full_migration_lineage_from_empty_isolated_schema`
  - `test_populated_parent_upgrade_preserves_history_ownership_and_sessions`
  - `test_vendor_source_candidates_are_engineer_readable_and_reviewer_writable`
  - `test_non_admin_knowledge_reviewer_capability_is_additive_and_self_review_stays_blocked`
  - `test_knowledge_reviewer_grant_revoke_are_audited_atomically`
- Python compile: PASS for changed backend and integration-test files.
- Ruff F401/F841/E402: PASS for changed backend and integration-test files.
- Browser acceptance configuration guard: **5 invalid configurations rejected**, exit 0. This is a config guard only, not browser acceptance.
- `git diff --check`: exit 0; only existing LF-to-CRLF warnings.
- Branch/HEAD preserved: `integration/eims-consolidated` / `85493b2131d3e353453072559a5dfc301d75dd06`.
- Worktree status count after this snapshot: 161 entries; preserve all existing modified and untracked work.

## Browser Acceptance boundary

Full Browser Acceptance was **NOT RUN** in this checkpoint. The currently reachable `https://localhost:3449` endpoint identifies itself as `EIMS Core Gateway`; its health endpoint is healthy, but the synthetic harness-only `/__test__/diagnostics` endpoint is unavailable. It is not safe to submit synthetic login or test mutations through that gateway. No browser login or operational data mutation was attempted.

Next browser gate: bring up a separate isolated backend, dashboard/BFF and trusted HTTPS origin on dedicated ports, pointing only at the disposable non-superuser database and isolated Redis/MinIO resources. Then execute the complete Reviewer/Engineer browser journey and retain JUnit, exit code, request IDs and runtime evidence.

## Independent review status

A read-only Claude Code review was attempted, but no review content was returned. Do not record an independent AI review as completed. A separate reviewer must inspect the exact final diff before this change is considered independently reviewed.

## Remaining project gates

- Current Browser Acceptance for the latest Reviewer/Source UI.
- Human Domain Review of 20 source candidates and 17 DEV/HELDOUT Gold cases; AI must not approve these.
- External/offsite backup and witnessed restore, owner-approved RPO/RTO, retention and failover evidence.
- Controlled Engineer pilot with incident provenance and post-remediation validation evidence.

No Operational DB access, commit, push, reset, clean, stash, rebase or destructive cleanup was performed.
