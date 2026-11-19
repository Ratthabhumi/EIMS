# EIMS deployment security bundle

Status: **PREPARED, NOT APPLIED.** No live environment was inspected or changed.
Everything here is validated on disposable PostgreSQL only.

## Contents

| File | Purpose |
|---|---|
| `env/api.env.example` | API process environment, identity enforced |
| `env/worker.env.example` | Background-worker environment, same identity policy |
| `env/migration.env.example` | Migration/owner job environment (never given to the API) |
| `sql/01_roles.sql` | Roles + database/schema access (run before migrations) |
| `sql/02_runtime_grants.sql` | Runtime table/sequence grants + denials (run after migrations) |

Both SQL files are executed verbatim by
`tests/test_privilege_topology_pg.py` against a throw-away database, so a broken
or over-permissive script fails the suite instead of production.

## Role topology

```
owner/migration role  (eims_migrator)  owns schema, tables, sequences, triggers, functions
runtime role          (eims_runtime)   SELECT/INSERT/UPDATE/DELETE app rows, minus the
                                       protected surfaces:
                                         incident_verification  no UPDATE/DELETE/TRUNCATE
                                         audit_logs             no UPDATE/DELETE/TRUNCATE
                                         incidents              no DELETE/TRUNCATE
                                         incident_evidence      no UPDATE/DELETE/TRUNCATE
                                         alembic_version        no access
```

Why two roles: PostgreSQL ownership cannot be neutralised by `REVOKE`. A role
that owns `incident_verification` or its trigger function can `ALTER TABLE …
DISABLE TRIGGER`, `DROP TRIGGER`, or `CREATE OR REPLACE FUNCTION` and erase the
append-only/resolution guards. The runtime role must not be an owner, must not
be a member of the owner role (no `SET ROLE` path), and must be
`NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS`. `01_roles.sql`
re-applies that posture even when the roles already exist, and
`02_runtime_grants.sql` raises if the runtime owns relations or holds any role
membership.

Proved on disposable PostgreSQL by `tests/test_privilege_topology_pg.py` (15
tests): catalog posture, ownership, trigger-function ownership, absence of role
membership, `SET ROLE` denial, and denial of UPDATE/DELETE/TRUNCATE on
`incident_verification`, `UPDATE` on `incident_evidence`, `DELETE` on
`incidents`, `ALTER TABLE … DISABLE TRIGGER`, `DROP TRIGGER`, `DROP FUNCTION`,
`CREATE TABLE`, `session_replication_role`, raw resolve, raw resolved-insert,
remediation-cycle rewind, `remediation_started_at` widening, and
`resolved -> open` replay.

## Deployment order

1. **Create the roles** as the database owner/superuser:
   `psql "$OWNER_URL" -f deploy/sql/01_roles.sql`
   Roles are created without passwords; set them from the secret store with
   `ALTER ROLE … PASSWORD` (never in a script or the process list).
2. **Run migrations as the migration role** (`env/migration.env.example`):
   `alembic upgrade head` → expect `f7a1c3d9e502` (single head).
3. **Apply runtime grants** after the tables exist:
   `psql "$OWNER_URL" -f deploy/sql/02_runtime_grants.sql`
   Re-run this after **every** migration: it re-applies the protected-table
   revokes, which a recreated table would otherwise lose.
4. **Verify schema guards exist**:
   `SELECT tgname FROM pg_trigger WHERE tgname LIKE 'trg_incident_%' AND NOT tgisinternal;`
   Expect five triggers: append-only (row), append-only (truncate), resolution,
   remediation-cycle guard, and insert-state guard.
5. **Start the API** with `env/api.env.example` (`EIMS_DB_IDENTITY_REQUIRED=1`).
   Startup must fail if the identity is missing, malformed, or does not match the
   live connection.
6. **Start the background workers.** In this revision they start inside the API
   lifespan (`backend/main.py`); there is no separate worker binary. If a
   separate worker process is introduced later it must use
   `env/worker.env.example` with the same identity pair.
7. **Readiness** must distinguish: database reachable → runtime identity verified
   → role posture acceptable. The schema revision is checked by the deploy
   pipeline with the migration credential (the runtime role deliberately has no
   access to `alembic_version`); a reachable database alone is not readiness.

## Startup / readiness semantics

- `AsynchronousDatabaseEngine.initialize()` validates the configuration shape
  before any pool exists: `REQUIRED=1` with no `EIMS_DB_IDENTITY` raises during
  lifespan startup.
- `verify_runtime_identity()` then asks the live connection; a wrong database or
  role aborts startup and closes the pool.
- `GET /health`/readiness should additionally report `eims_identity_status`
  (`verified` / `unconfigured`) and the Alembic revision. It must never report
  `verified` for an unconfigured deployment.

## Rollback

1. Stop API and worker.
2. `alembic downgrade c4e8a1f7b932` (drops `incident_verification`,
   `remediation_cycle`, and the four triggers; it does **not** restore deleted
   verification history — back up first).
3. Re-deploy the previous application image with its previous identity
   configuration.
4. Do not drop the runtime role while sessions exist; revoke `CONNECT` first if a
   forced cutover is required.

## Evidence collection

- Startup: capture the process log line proving `initialize` + identity
  verification succeeded (no credentials in logs).
- Identity: `SELECT current_database(), current_user, session_user` on the
  runtime connection.
- Role posture: `pg_roles` row + `pg_has_role(current_user, '<migrator>', 'MEMBER')`
  = false.
- Guards: `pg_trigger` list + one denied raw `UPDATE incidents SET status='resolved'`
  executed **on disposable PostgreSQL only**.
- Verification: resolve an incident through the API without evidence (expect
  422) and with reviewer-approved evidence (expect 200 + `verifications[]`).

Never run destructive denial tests against a live environment; prove denials on
the disposable instance and keep the live smoke read-only plus one reversible
synthetic incident.

## Not done here

- No credentials, hosts, or database names were invented.
- No live smoke test was executed.
- The dev `docker-compose.yml` still runs the owner role; it is development-only.
