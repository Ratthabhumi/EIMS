# 2026-11-15 — Database-backed vendor source candidates

## Change summary

Introduced a first-class source-reference workflow without conflating vendor documentation with incident-derived, approved Engineering Knowledge.

- ORM: `KnowledgeSourceCandidate` in `knowledge_source_candidates`.
- Append-only event model: `KnowledgeSourceEvent` in `knowledge_source_events`.
- Alembic revision: `f3c8a1d6b902`, parent `e5a7c9d2f416`.
- Admin API: list/filter source candidates, review state transitions, and inspect source event history.
- Dashboard: Admin-only catalogue with vendor/product/version scope, applicability, prerequisites, evidence, limitations, next checks, validation, rollback, risk, source hash and audit events.
- Importer: `tools/import_knowledge_source_candidates.py`, dry-run by default, idempotent, source-hash aware, and explicitly restricted to an allowlisted loopback synthetic PostgreSQL URL. It does not use the application's DATABASE_URL.
- Browser harness: added Admin lifecycle revalidation/reactivation/audit/withdrawal checks and Engineer visibility-isolation assertions.

## Trust boundaries

A source candidate may be pending, verified as a reference, rejected, revalidation-required, or withdrawn. `verified_reference` means only that a human checked the vendor reference and scope. It does not create a KnowledgeEntry, prove an incident root cause, or authorize a remediation.

Source revisions are detected by SHA-256 over canonical JSON. A changed reference creates an audit event and requires review again if it had already been reviewed. Prior reviewer identity and notes remain historical; the new source hash is not silently treated as verified.

The Analyzer's retrieval path continues to read approved, active `KnowledgeEntry` only. No candidate rows are promoted into that table.

## Verification performed

- Candidate catalogue dry-run: 20 records across Broadcom VMware, Fortinet, Microsoft and Veeam.
- Python compile: passed for changed backend, migration, importer and test files.
- Targeted Ruff (`F401,F841,E402`): passed on changed implementation/test files.
- Alembic offline SQL generation: passed through new head `f3c8a1d6b902`.
- Dashboard production build: passed compile, TypeScript and static generation 15/15.
- Focused tests: 10 passed; 2 PostgreSQL integration/migration tests skipped because `EIMS_TEST_DATABASE_URL` is not configured in this shell.
- Browser harness JavaScript syntax check: passed.

## Not claimed

- The migration has not been applied to an existing database in this run.
- The 20 candidates have not been imported into any database in this run.
- PostgreSQL API integration and full migration-lineage execution were skipped due to missing explicit synthetic test database configuration.
- Browser Acceptance was not executed because browser base URL, synthetic login credential and synthetic database URL were not configured in this shell.
- No production database, operational backup target, or customer data was accessed.

## Next safe execution

1. Provision/identify an explicitly allowlisted synthetic PostgreSQL test target and apply the Alembic head there.
2. Run the idempotent source importer against that exact synthetic target and verify 20 rows + audit events.
3. Run PostgreSQL API tests and Browser Acceptance with distinct synthetic Admin and Engineer accounts.
4. After witnessed tests, prepare the migration and source seed for the organization's controlled deployment process; do not run the test-only importer against production.
