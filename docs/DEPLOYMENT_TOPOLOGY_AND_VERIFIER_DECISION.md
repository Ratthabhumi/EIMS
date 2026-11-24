# EIMS Deployment Topology and Verifier Trust-Boundary Decision

Date: 2026-11-19. Status of this document: evidence record and decision, not a
deployment approval.

## 1. Target environment

**TARGET ENVIRONMENT: NOT ESTABLISHED.**

Evidence (read from the repository and the running host, not assumed):

| Question | Finding |
|---|---|
| Backend container image | **None.** The only Dockerfiles belong to `clients/log_analyzer/*`; there is no Dockerfile for `backend/`. |
| CD / deployment workflow | **None.** `.github/workflows/` contains only `analyzer-reliability.yml` (tests), no deploy job. |
| Orchestration manifests | **None** for the EIMS API (no k8s/Helm/Terraform for the service). `deployments/homelab` is unrelated homelab infrastructure. |
| What `docker-compose.yml` actually defines | Infrastructure only: `postgres_db` (`pgvector/pgvector:pg16`), `pgbouncer`, `redis_cache`, `minio`, `minio_setup`, `prometheus`, `grafana`, `loki`. No API/worker service. |
| How the API runs on this machine | From the repository virtualenv on the host (`uvicorn`/pytest), not from a container. |
| Secret management | `.env` / process environment; `docker-compose.yml` contains plaintext dev credentials. No external secret manager is configured. |

Consequences: there is no deployment target to inspect, no environment in which
to provision the runtime role, and no authorized place to run a live smoke. No
configuration was applied anywhere.

## 2. Actual local topology (observed 2026-11-19)

```
host venv (backend)  --unverified path-->  eims-pgbouncer:6432 (published)
                                              |  listens on 5432 inside
                                              v
                                          eims-postgres:5432 (pgvector/pg16, eims_registry)
```

Read-only inspection of the running containers:

| Fact | Value |
|---|---|
| `eims-pgbouncer` version | **PgBouncer 1.25.2** |
| `pgbouncer.ini` | `listen_port = 5432`, `pool_mode = transaction`, `auth_type = plain` |
| Published mapping | `0.0.0.0:6432->6432/tcp` |
| Listener inside the container | `0.0.0.0:5432` only |

### Findings

1. **The published pooler port has no listener behind it.** The container
   serves 5432 but the mapping targets 6432, so a client configured with
   `DB_PORT=6432` is accepted at TCP level and then reset. A client configured
   with 5432 talks to PostgreSQL directly, bypassing the pooler entirely.
2. **The image is unpinned and currently resolves to an unpatched version.**
   `image: edoburu/pgbouncer:latest` resolves to **1.25.2** on this machine.
   The advisory list supplied with this mission (CVE-2026-19888, CVE-2026-6668,
   CVE-2026-6669, fixed in the 1.26.x line) **has not been independently
   verified here** — it must be confirmed against the official PgBouncer release
   notes and the pinned image digest before deployment. Either way, an unpinned
   `latest` is not an acceptable production reference.
3. **`auth_type = plain` with plaintext credentials in the compose file.** It is
   a development convenience, not a deployment posture; production requires
   `scram-sha-256` (or `auth_query`) and credentials from the secret store.
4. **Transaction pooling is configured.** That is the correct mode for the
   application's short transactions, but it means a client "new connection" is
   not a new PostgreSQL backend, which is exactly what the identity guard must
   cope with.
5. **Other compose findings (not previously recorded):**
   - `minio_setup` runs `mc anonymous set public eims_local/eims-ocr-manifests`,
     making the OCR manifest bucket publicly readable.
   - `postgres_db` (5432), `redis_cache` (6379) and `minio` (9000/9001) are
     published on all host interfaces, not loopback.
   - Most images are unpinned (`redis:7-alpine` is the exception).

These are development-stack characteristics. They are listed so that no one
mistakes the compose file for a production topology.

### PgBouncer gate result

**NOT APPLICABLE to a verified target + NOT ACCEPTED for production.**

- No verified target exists (§1), so no production pooler acceptance is possible.
- A local transaction-pooling identity proof was attempted against a throw-away
  `edoburu/pgbouncer` container in front of the disposable PostgreSQL. The
  container started (1.25.2, transaction mode, confirmed via `pgbouncer
  --version` and its generated ini), but the client never completed
  authentication in this environment (TCP accepted, then timeout). The proof is
  therefore **NOT VERIFIED**, and `tests/test_pgbouncer_transaction_pool_pg.py`
  is a **harness that has never run** — it must not be cited as pooler evidence
  until it runs and is strengthened to capture server-side reuse.

## 2b. Grant re-application after migrations

`02_runtime_grants.sql` grants on the tables that exist when it runs and sets
default privileges for future tables. A later migration that recreates a
protected table can therefore regain UPDATE/DELETE for the runtime role. The
provisioning procedure must **re-run `02_runtime_grants.sql` after every
migration** and re-check the trigger list; this is recorded in the script header
and the deployment runbook.
- Before any deployment that uses a pooler: pin a patched version, fix the port
  mapping, switch to scram/auth_query, and run a bounding test that captures
  `pg_backend_pid()` across reuses and proves the guard re-checks identity on
  every server connection.

The direct-PostgreSQL path remains proven (worker, replacement pool, active
invalidation, HTTP/lifespan). The pooler path is not.

## 3. Verifier trust boundary — threats and decision

### Threat model

| ID | Threat | Prevented? | Detected? | Notes |
|---|---|---|---|---|
| A | Ordinary application bug or unauthorized API caller | **Yes** | Yes (422/403 + audit) | Invariant in service + DB trigger; request schema forbids forged fields. |
| B | Compromised API runtime DB credential | **No (limitation)** | Partially (audit trail) | The credential can insert a *constraint-consistent* verification row and resolve. |
| C | Compromised worker DB credential | **No (limitation)** | Partially | Same role in this revision; workers cannot resolve today, but share the credential. |
| D | Compromised verifier user account | **No** | Yes (verifier_id recorded) | A stolen reviewer account can verify; that is normal authorization failure. |
| E | Compromised migration/owner credential | **No** | No | The owner can rewrite guards and history. Accepted: the owner is the database trust anchor. |
| F | Database superuser compromise | **No** | No | Out of scope by definition. Not claimed. |

What the database guards *do* buy: an attacker with the runtime credential
cannot resolve without writing a verification row that satisfies evidence
ownership, digest equality, verifier ≠ evidence author, and current-cycle
freshness. That is a meaningful bar (it blocks the cheap replay paths), but it is
still forgeable by that credential.

### Options evaluated

| Option | Verdict |
|---|---|
| 1. Separate PostgreSQL verifier role | **Rejected for this mission.** The verifier decision is made inside the same API process, so a second credential would be loaded into the same memory/process. A process compromise yields both; the separation buys little and adds a second secret to rotate. It becomes meaningful only if the verifier runs as a separate service. |
| 2. Independent verification service | **Correct long-term design, out of scope.** It requires a new deployable, its own credential, its own audit trail and an availability story. Introducing it un-deployed and un-tested in a closure round would be worse than the honest limitation. |
| 3. Cryptographic signature from an external verifier key | **Not implementable safely here.** No key custodian, no rotation procedure, no storage outside the app DB exists. Binding a private key into the same runtime process recreates threat B. |
| 4. `SECURITY DEFINER` function owned by a dedicated role | **Rejected on two independent grounds.** (a) It does not reduce threat B: the runtime role is the *caller*, so a compromised runtime credential can still invoke it. (b) Even a correct implementation requires owner-privilege hygiene (fixed `search_path` with `pg_temp` last, `PUBLIC EXECUTE` revoked in the same transaction, validated inputs), which is real risk for no gain here. |
| 5. Current design with an explicit limitation | **Selected.** |

### Decision

**The current design is sufficient for the threats it claims to address
(ordinary bugs and unauthorized API callers) and explicitly insufficient
against a fully compromised runtime credential.**

- It must not be described as "forgery-proof" or "tamper-evident".
- If the deployment's threat model includes a compromised application credential,
  an independent verifier service (option 2) is a **deployment prerequisite**,
  not a follow-up improvement.
- The limitation is recorded in `EIMS_FINAL_DELIVERY_STATUS.md`,
  `EIMS_SECURITY_FINDINGS_RECONCILIATION.md` and the acceptance manifest.

## 4. Excluded subsystems — topology disposition

| Subsystem | Present in the deployed topology? | Disposition |
|---|---|---|
| Gateway | **No service exists** (no manifest, no reverse proxy definition for EIMS, no in-repo implementation). | **NOT DEPLOYED.** Not "secure by absence", simply out of scope until a topology exists. |
| Journal (`audit_logs`) | Yes, as a table. Runtime is INSERT-only **at provisioning time**; re-run `02_runtime_grants.sql` after every migration (§2b), because default privileges would otherwise re-grant UPDATE/DELETE on a recreated table. | **Excluded, limitation retained.** It is an operational journal, not tamper-evident: an owner or superuser can rewrite it. No unkeyed hash chain is claimed. |
| Benchmark (`tools/sprint11_benchmark.py`) | **Not packaged**: there is no backend image, so the script exists only in the repository. | **Excluded.** Guarded by `EIMS_BENCHMARK_DATABASE_URL` + `_assert_benchmark_safety` + `require_destructive_target`; not reachable from the API process. |
| Seed (`tools/seed_*.py`) | Not packaged. | **Excluded.** `seed_analyzer_incident` guards its DELETE with `require_destructive_target`; `seed_demo_data` is insert-only. |
| Maintenance CLI (`tools/maintain_analyzer_sessions.py`) | Not packaged. | **Excluded.** Dry-run default, explicit `--apply` + explicit DB URL, guarded delete. |
| `clear_db.py` | Repository root only, inert stub (imports no engine, runs no SQL). | **Excluded / retired.** |

Because the API is not containerized and there is no deployment workflow, these
tools are not reachable from the runtime service in the only topology that
exists. If the API is later packaged into an image, the packaging step must
exclude `tools/` and `clear_db.py` — recorded as a deployment requirement.

## 5. Deployment readiness

`deploy/README.md` holds the order (roles → migrate as migration role → grants →
verify triggers → start API → readiness), rollback, and evidence collection.
`deploy/sql/01_roles.sql` and `02_runtime_grants.sql` are executed verbatim by
the privilege suite, so they are known runnable and least-privilege.

What is still required before deployment acceptance:

1. A real target environment with change control and a verified backup point.
2. A patched, pinned pooler (or a documented direct-PostgreSQL topology).
3. Role provisioning and identity configuration applied there.
4. A bounded smoke (one synthetic incident) with the results recorded.
5. A decision on the verifier threat model (§3) for that environment.

Until then: **DEPLOYMENT CONFIGURATION: PREPARED · LIVE DEPLOYMENT: NOT
PERFORMED · BLOCKER: VERIFIED TARGET ENVIRONMENT / AUTHORIZED CHANGE WINDOW.**
