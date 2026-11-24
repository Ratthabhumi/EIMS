# EIMS Engineering Memory — 2026-11-15 Reviewer Capability and Source Provenance

## Scope

Continued the existing EIMS repository on Mew. No new subsystem was created. Work was limited to reducing unnecessary RBAC separation, correcting source-provenance semantics, and preventing a misleading non-persistent Settings screen from appearing functional.

## Repository invariants

- Repository: C:\Users\MewMew\Desktop\Co-op\EIMS
- Branch: integration/eims-consolidated
- HEAD: 85493b2 (unchanged)
- New Alembic head: a4b7c9d2e601, parent f3c8a1d6b902
- No commit, push, reset, clean, or stash.
- No operational database was accessed.
- Existing modified/untracked work was preserved.

## RBAC correction

Introduced an additive user capability, `users.knowledge_reviewer`, through migration `a4b7c9d2e601`.

- Legacy Admin accounts implicitly retain Knowledge review capability for compatibility.
- An ordinary Engineer account may be granted `knowledge_reviewer=true`; it retains all ordinary Engineer functionality.
- `require_knowledge_reviewer` protects Knowledge approval, source state transitions and lifecycle mutations.
- Admin-only user administration remains separate from Knowledge review.
- Admin user API can create a reviewer-capable user and update the capability on an existing user.
- Auth session returns `capabilities.knowledge_review`; Dashboard uses this capability rather than checking the Admin role.
- Authenticated Engineers can read/search the source catalogue and inspect Source/Lifecycle audit histories.
- Only a designated Reviewer (or legacy Admin) can mutate review/lifecycle state.
- The existing record-level rule preventing a proposer from approving their own Knowledge remains in force.

This is a small-team capability model, not a multi-role enterprise RBAC expansion. No separate Reviewer identity/account is required.

## Source provenance correction

The database field `source_hash` and importer `canonical_hash()` fingerprint the canonical JSON catalogue record. They do not hash the current Vendor web page or downloaded document bytes.

The API and Dashboard now call this `catalogueRecordHash` / Catalogue record SHA-256 and explicitly state that it is not a downloaded Vendor document hash. A changed catalogue record triggers revalidation; detecting upstream Vendor page changes still requires a fresh human/source check or a separately approved fetch-and-archive workflow.

The source candidate corpus remains separate from `knowledge_entries`. `verified_reference` does not imply an approved local diagnosis, safe remediation, or automatic Knowledge promotion.

## Dashboard truthfulness

The existing System Settings screen contains local UI state only and its Save handler previously displayed a success toast without persisting configuration. It now explicitly identifies itself as a preview, reports that changes are not persisted, and disables the Save button. No fake persistence claim remains.

## Verification performed

- Python compile: PASS.
- Targeted Ruff (F401, F841, E402): PASS after moving late auth imports to module scope.
- Focused tests: 14 passed across Knowledge source-candidate, Knowledge safety, static Event Knowledge safety and auth-mode suites.
- Alembic heads: exactly one head, `a4b7c9d2e601`.
- Dashboard production build: PASS; TypeScript completed and 15/15 static pages generated.
- Browser harness JavaScript syntax: PASS.
- The PostgreSQL integration tests were not executed because `EIMS_TEST_DATABASE_URL` was not present in the process environment.
- The new migration has not been applied to any database and the 20 candidates have not been imported.
- Browser Acceptance was not executed; its test DB URL and login credentials were not configured. The prior 33/33 Browser Acceptance result predates this UI/RBAC change and is not evidence for the current version.

## Remaining acceptance gates

1. Provision or restore an explicitly authorized synthetic test URL without touching the running application identity; apply migration `a4b7c9d2e601` to the isolated synthetic DB.
2. Import 20 candidates with the guarded importer; verify row count, canonical record hashes, and import events.
3. Execute PostgreSQL integration tests, including non-Admin Reviewer capability and Engineer read-only access.
4. Execute the current Browser Acceptance suite against the current dashboard/backend and verify Reviewer controls versus Engineer read-only surfaces.
5. Obtain Domain Reviewer decisions for the 20 Vendor source candidates and the 17 DEV/HELDOUT Gold fixtures. Candidate status and AI-generated drafts are not approvals.
6. Complete offsite backup and witnessed isolated restore with Operations; obtain Business/Data/Operations approval for RPO/RTO.
7. Run an Engineer pilot and capture incident provenance, validation evidence, and reported usage outcomes.

## Evidence semantics

KnowledgeUsage outcomes are user-reported feedback linked to a History snapshot hash. They are not independent proof that a remediation worked. The incident's validation evidence remains the proof of resolution. Audit event tables are append-only through application workflows; this does not yet constitute tamper-proof/WORM storage against a database administrator.
