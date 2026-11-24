# EIMS Final Delivery Status

Date: 2026-11-19 · Branch `integration/eims-consolidated` · HEAD `85493b2`
No commit, push, stage, reset, clean, checkout or stash was performed.
Working tree: 207 entries (was 197), 0 staged. All pre-existing modifications and
untracked work preserved.

## Decision

> ## C. NOT READY FOR DELIVERY (overall EIMS)
> The incident workflow itself is accepted with limitations; the system as a
> whole is not, because Security Acceptance is not granted and no live
> deployment verification exists.

| Dimension | Result |
|---|---|
| Code acceptance (incident scope) | **ACCEPTED WITH LIMITATIONS** |
| Disposable PostgreSQL integration | **ACCEPTED WITH LIMITATIONS** (137 focused tests + 24 privilege-topology tests) |
| PostgreSQL privilege/ownership | **ACCEPTED WITH LIMITATIONS** (deploy SQL executed verbatim) |
| Security acceptance | **NOT ACCEPTED** — Gateway/Journal/Benchmark/CLI/seed still unaccepted |
| Deployment configuration readiness | **PREPARED, NOT APPLIED** |
| Live deployment verification | **NOT PERFORMED** |

## 1. Which parts are accepted

- **Incident Core** — creation, correlation, reuse, dedupe/idempotency,
  evidence attachment, lifecycle, API, rollback, migration, verified resolution.
  Controlled rewrite, not recovered source.
- **Verified resolution** — `investigating -> resolved` requires a persisted
  verification row bound to the incident's remediation cycle; enforced in the
  service **and** by a PostgreSQL trigger; append-only history.
- **R-1 runtime DB identity (code)** — guard on a live connection, worker session
  factory, replacement pool, active invalidation/reconnect, real FastAPI
  lifespan/HTTP, ORM/Core/text through one guarded engine.
- **Engineer workflow** — detect → evidence → verify → resolve → reopen →
  re-verify, with an auditable record.

## 1b. Deployment topology (new evidence)

**TARGET ENVIRONMENT: NOT ESTABLISHED.** No backend Dockerfile, no deploy
workflow, no orchestration manifest; `docker-compose.yml` defines infrastructure
only and the API runs from the host virtualenv. Details and the PgBouncer
findings are in `docs/DEPLOYMENT_TOPOLOGY_AND_VERIFIER_DECISION.md`:

- the running `eims-pgbouncer` is **1.25.2** (unpinned `latest`) — predates the
  1.26.x security-fix line;
- it listens on **5432** inside but is published as **6432**, so the pooler port
  has no listener behind it;
- a local transaction-pooling identity proof did **not** complete (auth
  timeout) → **NOT VERIFIED**.

## 1c. Verifier threat boundary (new decision)

A compromised runtime DB credential can still insert a constraint-consistent
verification row. Options were evaluated (separate DB role, independent service,
external signing key, SECURITY DEFINER) and **the limitation is retained**; see
§3 of the topology document for the rationale. If the deployment threat model
includes a compromised application credential, an independent verifier service
is a **deployment prerequisite**.

## 2. Accepted with limitations

- **Incident Core**: recurrence ordering not exhaustively proved; rewrite-only
  behaviours supported by tests but not by the 2026-11-16 spec.
- **R-1**: enforcement at the engine facade, not a pool-checkout listener
  (asyncpg cannot await inside the synchronous checkout hook). A raw
  `database_engine._engine` handle would bypass it; no production module uses
  one and a source-scan test enforces that.
- **Verification**: reference integrity only, not external system health;
  `analysis` is the only verification-grade evidence type; separation of duties
  is one-directional; triggers guard UPDATE/DELETE/TRUNCATE but not a raw INSERT
  of an already-resolved incident.
- **Workflow**: no diagnosis/remediation-record surface and no incident UI.

## 3. Not accepted

- **Gateway authorization**, **Journal hardening**, **Benchmark mutation
  safety**, **Maintenance CLI**, **Seed/`clear_db`** — unchanged exclusions. No
  evidence they are disabled or restricted in a deployable topology.
- **Live deployment** — not inspected.

## 4. What is ready to use

The backend incident surface: create incidents from evidence references, attach
evidence, correlate, transition legally, and resolve only with reviewer-approved,
server-revalidated evidence. Everything is reachable over
`/api/v1/incidents` and is documented in
`INCIDENT_VERIFICATION_AND_RESOLUTION_POLICY.md`.

## 5. What must be configured in deployment

1. `EIMS_DB_IDENTITY=<database>|<runtime_role>` and
   `EIMS_DB_IDENTITY_REQUIRED=1`. Startup now fails closed on a missing,
   malformed or mismatched identity, in the API lifespan (workers start inside
   that lifespan in this revision).
2. Run `deploy/sql/01_roles.sql` (roles + schema access), migrate as the
   migration role, then run `deploy/sql/02_runtime_grants.sql`. These two scripts
   are executed verbatim by the test suite, so they are proven runnable and
   least-privilege.
3. Keep trigger/table ownership with the migration role; the runtime role must
   never own them (the test proves it cannot disable or drop the guards).
4. Apply migration `f7a1c3d9e502` (single head) before enabling the API.
5. A readiness probe that reports database reachable **and** identity verified
   **and** schema revision; identity is now checked at startup, so a mis-targeted
   process never becomes ready.

## 6. What must not be enabled until accepted

Gateway-exposed authorization paths, Journal/the audit pipeline as a
tamper-evident control, Benchmark mutation endpoints, the maintenance CLI, and
seed/`clear_db`. Do not treat the audit log as tamper-evident.

## 7. Residual risks

1. **Operational DB contact (disclosed).** An earlier test round patched
   `settings.__dict__["database_url"]`, which has no effect (it is a property),
   so two test files targeted the default `localhost:5432/eims_registry`
   configuration. One synthetic probe table (`r1_invalidate_probe`, 0 rows) was
   created there; it has been dropped and its absence verified. No business data
   was read, written or changed. The tests were rewritten to patch `DB_*` fields
   and assert `current_database() = eims_incident_test`; all R-1 evidence in this
   report is from the corrected runs.
2. Reference-level evidence integrity only.
3. Recurrence ordering unproved.
4. Next.js dashboard has no incident UI (no false "resolved" badge exists).
5. Audit rows are not hash-chained.
6. Disposable PostgreSQL only; PgBouncer transaction-mode reuse under load and a
   real worker process restart are untested.
7. `tests/test_incident_ingest_integration.py` (6 tests) skipped — requires
   `EIMS_INGEST_TEST_DATABASE_URL` / `_REDIS_URL` / `_SENTINEL`.
8. **Pooler is unverified and currently misconfigured:** 1.25.2 unpinned, port
   6432 published with a 5432 listener, `auth_type=plain`. Production must pin a
   patched tag (>= 1.26.1), fix the mapping, use scram/auth_query, and run the
   pooler identity matrix.
9. **A compromised runtime credential can forge verification** (threat model,
   retained limitation).
10. **No target environment:** no deployment, role provisioning, or live smoke
    was performed anywhere.

## 8. Exact next action to move to B

Apply and verify the deployment steps in §5 in a real target, plus:
pin and fix the pooler (or document a direct-PostgreSQL topology) and decide the
verifier threat model for that environment (independent verifier service if a
compromised app credential is in scope). Then run one synthetic incident smoke
and record the results. Until then the correct status is **NOT READY**.

## Evidence index

| Artifact | Path |
|---|---|
| Acceptance manifest | `evidence/EIMS_FINAL_ACCEPTANCE_MANIFEST.json` |
| Incident Core review | `docs/INCIDENT_CORE_INDEPENDENT_REVIEW.md` |
| R-1 acceptance | `docs/DB_RUNTIME_IDENTITY_ACCEPTANCE.md` |
| Verification policy | `docs/INCIDENT_VERIFICATION_AND_RESOLUTION_POLICY.md` |
| Engineer workflow | `docs/INCIDENT_ENGINEER_WORKFLOW_ACCEPTANCE.md` |
| Exclusions | `docs/EIMS_SECURITY_FINDINGS_RECONCILIATION.md` |
| Independent acceptance | `docs/EIMS_FINAL_INDEPENDENT_ACCEPTANCE.md` |
| Deployment topology & verifier decision | `docs/DEPLOYMENT_TOPOLOGY_AND_VERIFIER_DECISION.md` |
| Pre-change snapshots | `.recovery/2026-11-19-final-closure/` |
| Forensic / rewrite snapshots | `.recovery/2026-11-19-incident-core/` |
