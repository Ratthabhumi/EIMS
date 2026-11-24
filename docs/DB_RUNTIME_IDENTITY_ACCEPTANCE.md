# DB Runtime Identity Acceptance (R-1) — Application Level

Date: 2026-11-19
Environment: disposable PostgreSQL `eims-recovery-pg-20261119`,
`127.0.0.1:56455`, database `eims_incident_test`, role `eims_incident_test`,
`rolsuper=f`. Every run re-verifies `current_database/current_user/rolsuper`
before testing. No operational database is used.

## 1. Where the guard is enforced

```
settings (DB_USER/DB_PASSWORD/DB_HOST/DB_PORT/DB_NAME)
  -> AsynchronousDatabaseEngine.initialize()  (one async engine + pool)
      -> get_session()            # FastAPI dependency, one session/request
      -> get_session_maker()      # guarded wrapper for workers
      -> connect()                # guarded Core/textual boundary
          -> require_runtime_identity(session_or_connection)
              -> SELECT current_database(), current_user, session_user,
                        shobj_description(...) FROM pg_database
```

`require_runtime_identity` is called on the object that will actually run the
statement, so the check sees the live connection. A raw engine handle would
bypass it, therefore `tests/test_api_identity_pg.py` asserts that no production
module references `database_engine._engine` or `.sync_engine`.

Policy semantics (unchanged from the guard baseline):

| `EIMS_DB_IDENTITY` | `EIMS_DB_IDENTITY_REQUIRED` | Behaviour |
|---|---|---|
| `<db>|<role>` | any | live `database|current_user` must match, else deny |
| unset | `1` | deny (fail closed) |
| unset | 0/unset | allow but mark `unconfigured` (never "verified") |
| malformed | any | deny |

`session_user` is captured in `ConnectionIdentity` but the enforcement key is
`database|current_user`, so `SET ROLE` to a different role is denied (proved in
the guard matrix). Accepting `session_user` instead would ignore the effective
privilege PostgreSQL actually applies.

## 2. Layer-by-layer results

| Layer | Evidence | Result |
|---|---|---|
| Guard on a live connection (7 cases) | `tests/test_db_identity_pg.py` | **PASS 7/7** |
| Worker session factory (real `AsynchronousDatabaseEngine`) | `tests/test_worker_identity_pg.py` | **PASS 4/4** |
| Replacement pool (`close()` -> `initialize()`) | `tests/test_worker_identity_pg.py` | **PASS** |
| Active connection invalidation + reconnect | `tests/test_connection_invalidation_pg.py` | **PASS 1/1** |
| FastAPI real lifespan + real HTTP | `tests/test_api_identity_pg.py` | **PASS 9/9** |
| ORM path | `get_session()` in the same file | **PASS** |
| Core / textual SQL path | `database_engine.connect()` in the same file | **PASS** |
| Denied identity performs no mutation | all denial cases | **PASS** (row counts unchanged) |

Command:

```
pytest tests/test_db_identity_pg.py tests/test_worker_identity_pg.py \
       tests/test_connection_invalidation_pg.py tests/test_api_identity_pg.py
-> 21 passed, exit 0
```

## 3. Evidence detail

**FastAPI (9 cases)** — `TestClient(app)` used as a context manager so the real
lifespan runs; the real `database_engine` singleton; the real `get_db_session`
dependency; **no `dependency_overrides`**. Cases: correct DB+role (HTTP 200 and
a persisted row), wrong database (5xx, incident count unchanged), wrong role
(5xx, count unchanged), `REQUIRED=1` without config (5xx, count unchanged),
unconfigured optional mode (serves, status `unconfigured`), recovery with a
fresh lifecycle (200), Core/text allow, Core/text deny with no leaked row, and
the no-raw-engine source check.

**Worker (4 cases)** — `get_session_maker()` yields only after identity matches;
wrong role raises before the body; a denied session cannot create/insert; after
`close()`+`initialize()` the replacement pool still enforces the policy.

**Invalidation (1 case)** — a checked-out connection is invalidated with
`await conn.invalidate()`; the replacement has a different
`pg_backend_pid()`; the guard runs again on it (correct = allow, wrong = deny);
a denied INSERT after reconnect persists zero rows.

## 4. Correction to earlier evidence (disclosed)

Earlier rounds reported worker/pool and invalidation results while patching
`settings.__dict__["database_url"]`. `database_url` is a read-only property, so
that patch silently did nothing and those runs targeted the default
`localhost:5432/eims_registry` configuration. Two consequences:

1. `tests/test_worker_identity_pg.py` and
   `tests/test_connection_invalidation_pg.py` were rewritten to patch the
   `DB_*` fields and to assert `current_database() == 'eims_incident_test'`;
   all results above are from the corrected runs.
2. One synthetic probe table (`r1_invalidate_probe`, 0 rows) had been created in
   `eims_registry`. It was dropped and its absence verified. No business data
   was read, written or changed. See `EIMS_FINAL_DELIVERY_STATUS.md` §Residual
   risks.

The earlier 7/7 guard matrix was not affected: it built its engine directly from
`EIMS_TEST_DATABASE_URL`.

## 5. Deployment configuration readiness

Required environment for API **and** any separate worker process:

```
EIMS_DB_IDENTITY=<database>|<runtime_role>    # reviewed runtime pair
EIMS_DB_IDENTITY_REQUIRED=1
```

- Both classes read the same module (`backend/infrastructure/db_identity.py`) and
  the same `settings`; there is no separate worker override that could diverge.
- **Startup is fail-closed.** `initialize()` validates the configuration shape
  before a pool exists (`REQUIRED=1` + missing/malformed identity raises), then
  `verify_runtime_identity()` asks the live connection. A wrong database/role
  aborts startup and closes the pool. `backend/main.py` performs both steps in
  the lifespan.
- Unconfigured development mode (`REQUIRED` unset/0) remains lazy — no startup
  connection — and the guard records `eims_identity_status = "unconfigured"` on
  the session. No HTTP readiness endpoint exposes that field yet; a deployment
  must not infer "verified" from a successful request.
- `EIMS_DB_IDENTITY_REQUIRED` accepts `0/1/true/false/yes/no/on/off`; any other
  value is a configuration error.
- Configuration bundle: `deploy/env/*.env.example`, `deploy/sql/01_roles.sql`,
  `deploy/sql/02_runtime_grants.sql`, runbook `deploy/README.md`.
- No secret is written to the repository; `EIMS_DB_IDENTITY` contains no
  password.
- In this revision background workers start inside the API lifespan; there is no
  separate worker binary. A future split must reuse the same env template.

**Deployment configuration readiness: PREPARED, NOT APPLIED.** Live deployment
verification has not been performed.

## 5b. Privilege topology (new, PostgreSQL-verified)

`tests/test_privilege_topology_pg.py` creates a throw-away database, executes
`deploy/sql/01_roles.sql` verbatim, migrates as the migration role, executes
`deploy/sql/02_runtime_grants.sql`, and then attacks the boundary as the runtime
role. 24 tests, all passing:

| Check | Result |
|---|---|
| runtime: `rolsuper=f`, `rolbypassrls=f`, `rolcreatedb=f`, `rolcreaterole=f`, `rolinherit=f` | PASS |
| `incidents` and trigger function owned by the migration role, not runtime | PASS |
| runtime holds no role membership / `SET ROLE <migration>` denied | PASS |
| intended resolution write set (evidence + verification + status) allowed | PASS |
| UPDATE / DELETE / TRUNCATE on `incident_verification` denied | PASS |
| UPDATE / DELETE on `incident_evidence` and `audit_logs` denied | PASS |
| `DELETE FROM incidents` denied | PASS |
| `SELECT alembic_version` denied (deploy pipeline owns that check) | PASS |
| `ALTER TABLE … DISABLE TRIGGER`, `DROP TRIGGER`, `DROP FUNCTION` denied | PASS |
| `CREATE TABLE` denied (CREATE revoked from runtime and PUBLIC) | PASS |
| `SET session_replication_role = replica` denied | PASS |
| raw `UPDATE incidents SET status='resolved'` denied by trigger | PASS |
| raw `INSERT` of an already-resolved incident denied | PASS |
| `UPDATE incidents SET remediation_cycle = 7` denied by cycle guard | PASS |
| `UPDATE incidents SET remediation_started_at` alone denied | PASS |
| `resolved -> open` and `closed -> open` replay denied | PASS |
| migration role can still apply DDL (separation, not paralysis) | PASS |
| deploy scripts self-check: runtime owns nothing and holds no membership | PASS |

Threat-model limit: the runtime role can `INSERT` verification rows because the
application creates them. A **fully compromised runtime credential** could forge
an internally consistent row (the trigger now requires the evidence to belong to
the incident, digest to match, verifier ≠ evidence author, and evidence to be in
the current cycle). Preventing that requires a separate verifier credential or a
SECURITY DEFINER path; both are out of scope and recorded as limitations.

## 6. Decision

**R-1: ACCEPTED WITH LIMITATIONS.**

- Accepted: guard, worker session factory, replacement pool, active
  invalidation/reconnect, real FastAPI lifespan/HTTP, ORM/Core/text on the same
  engine, denied-mutation proof, startup fail-closed, least-privilege role
  topology proved by executing the real deploy SQL.
- Limitations: enforcement is at the engine *facade* (session factory +
  `connect()`), not a pool-checkout listener, because asyncpg cannot run an
  awaited identity query inside SQLAlchemy's synchronous checkout hook. A future
  contributor who reaches for `database_engine._engine` would bypass it; the
  source-scan test is the tripwire (and `create_tables.py` was moved onto
  `connect()`).
- Not covered: a real worker process restart, PgBouncer transaction-mode pool
  reuse under load, and live deployment.
