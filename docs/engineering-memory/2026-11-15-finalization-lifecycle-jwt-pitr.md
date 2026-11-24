# EIMS finalization delta — Knowledge lifecycle, JWT expiry and PITR (2026-11-15)

## Scope and preservation

- Executed on Mew through Remote Desktop Commander only.
- Branch: `integration/eims-consolidated`.
- HEAD remains `85493b2131d3e353453072559a5dfc301d75dd06`.
- No commit, push, reset, clean, stash, operational database access, or destructive cleanup.
- Existing modified and untracked repository work was preserved.
- All database changes in this checkpoint were limited to named synthetic databases and an isolated synthetic PostgreSQL container.

## Knowledge revalidation lifecycle

Alembic revision `e5a7c9d2f416` (parent `d2f6b8c1e305`) adds:

- `knowledge_entries.lifecycle_state`: active, revalidation_required, superseded, withdrawn.
- `lifecycle_reason`, `lifecycle_updated_at`, and `superseded_by_id`.
- `knowledge_lifecycle_events` audit records with prior/new state, action, reason, reviewer note, actor and timestamp.

API:
- `POST /knowledge/{id}/lifecycle`: require_review, revalidate, supersede, withdraw.
- `GET /knowledge/lifecycle/review-queue`: admin-only revalidation queue.
- `GET /knowledge/{id}/lifecycle/events`: admin-only lifecycle history.

Controls:
- Only approved knowledge can transition.
- Proposer cannot review its own lifecycle.
- Revalidation is permitted only from revalidation_required.
- Superseding requires a different active approved entry with the same source family and diagnostic identity.
- Inactive entries are excluded from full-text discovery, exact-identity automated retrieval, and new usage reporting.
- Existing usage history and aggregate outcome summary remain inspectable.
- Feedback does not automatically alter AI confidence or the source Knowledge Entry.

No time-based review interval was invented. Automatic due dates and expiry remain gated on an explicit Domain Owner policy. Until that policy exists, reviewers must raise revalidation on material changes such as vendor support/EOL, product-version drift, security advisories, contradictory evidence, or failed usage outcomes.

## JWT expiry boundary

- `get_current_user` now requires the JWT `exp` claim and explicitly uses zero leeway.
- Token creation uses `datetime.now(UTC)`.
- PostgreSQL-backed integration test keeps the DB session valid and proves:
  - future exp accepted;
  - exp at the current NumericDate rejected;
  - past exp rejected;
  - missing exp rejected.
- This isolates JWT expiration from server-side session expiration.

## Database migration evidence

Alembic head: `e5a7c9d2f416`.

Successfully upgraded and verified:
- `eims_browser_acceptance_20261115`
- `eims_regression_test_20261115`
- Fresh migration rehearsal DB `eims_finalization_migration_20261115`

All three report the same Alembic head and contain `knowledge_lifecycle_events`. The full empty-schema migration and populated-parent upgrade tests also pass. The original `eims_integration_test` was not used.

## Test evidence

Focused command selected Knowledge, migration-lineage/populated-upgrade and JWT expiry tests:
- **8 passed, 0 failed, 0 errors, 0 skipped**, exit code 0.
- Coverage includes lifecycle suspension/reactivation, exclusion from search and exact-identity reuse, admin review queue, lifecycle event history, JWT exp boundary, empty-schema migration lineage, and populated-parent preservation.
- Targeted Ruff `F401,UP017`: PASS.
- Python compileall: PASS.
- `git diff --check`: PASS (existing LF-to-CRLF working-copy warnings only).
- This does not claim full all-rules Ruff cleanliness or a new Browser Acceptance run.

## Synthetic PostgreSQL 16 base-backup / WAL / PITR rehearsal

Reproducible harness: `tools/rehearse_postgres_pitr_synthetic.ps1`.

The harness creates a uniquely named isolated local Docker PostgreSQL 16 container and separate named data/WAL volumes. It does not read EIMS .env, production URLs, or operational database credentials. The container is stopped at completion; named volumes are preserved for inspection.

Observed run:
- `pg_basebackup -Fp -X stream`: PASS.
- `pg_verifybackup`: PASS.
- WAL archive: confirmed archived segment `000000010000000000000004`.
- Created named restore point `eims_pitr_target`.
- Started a second PostgreSQL instance from the base backup with `restore_command` and `recovery_target_name`.
- Restored rows: `before_backup,before_target`.
- The transaction committed after the named restore point was absent, proving recovery stopped at the intended boundary.
- Harness output: `%TEMP%\eims-pitr-rehearsal-20261115-v5.log`; exit code 0.

This is a successful synthetic PITR rehearsal, not production disaster-recovery certification. The rehearsal used local Docker storage on the same host. It does not prove off-host/offsite durability, production encryption/key recovery, retention, monitoring, standby failover, or real infrastructure RPO/RTO.

The existing Homelab `auto_backup.sh` archives `/data/docker`; it is not a PostgreSQL base-backup/WAL/PITR implementation and is not accepted as EIMS database recovery evidence.

## Remaining operational gates

1. Choose an independent, failure-domain-separated WAL/base-backup destination and approve encryption, access control, retention and deletion policy.
2. Run the same restore drill against that real backup target in an authorized non-production environment; verify backup manifests, WAL continuity, restore target and application-level invariants.
3. Complete Business Impact Analysis with service/data owners; then approve and measure RPO/RTO. Do not infer targets from the synthetic test.
4. Exercise failover, restore rollback, monitoring/alerting and operational ownership with witnesses.
5. Obtain independent human review of the 12 DEV gold cases; freeze reviewed annotations; then execute the 5 sealed HELDOUT cases without tuning against them. All 17 current proposals remain DRAFT.
6. Curate an initial approved Knowledge corpus from official vendor documents and authorized/sanitized incidents. Do not treat synthetic fixtures or AI proposals as approved production knowledge.
7. Begin a controlled Engineer pilot only after the domain and operational gates above are signed off.

## Research references

- PostgreSQL 16, Continuous Archiving and Point-in-Time Recovery: https://www.postgresql.org/docs/16/continuous-archiving.html
- PostgreSQL 16, pg_basebackup: https://www.postgresql.org/docs/16/app-pgbasebackup.html
- PostgreSQL 16, pg_verifybackup: https://www.postgresql.org/docs/16/app-pgverifybackup.html
- RFC 7519, JWT exp claim: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.4
- NIST SP 800-34 Rev. 1, Contingency Planning: https://csrc.nist.gov/pubs/sp/800/34/r1/upd1/final

## Final interpretation

The Knowledge application now has a governed revalidation state machine, JWT expiry has explicit boundary evidence, and a full synthetic PostgreSQL PITR recovery has succeeded. EIMS is still not closed: external backup durability, business-approved recovery objectives, independent gold review, real approved Knowledge corpus and controlled Engineer pilot remain mandatory.
