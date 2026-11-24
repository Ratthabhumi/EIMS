# EIMS Security Findings Reconciliation

Date: 2026-11-19. Scope: reconcile the *existing* exclusions after the Incident
Core / R-1 / verification work. No new broad audit was performed.

Classification key: **A** accepted · **B** accepted with limitations ·
**C** mitigated, deployment verification pending · **D** explicitly excluded ·
**E** not accepted / blocking.

| Area | Class | Enabled in delivery? | Residual risk / required control |
|---|---|---|---|
| **Incident Core** (creation, correlation, evidence, lifecycle, verified resolution) | **B** | Yes | Recurrence ordering not exhaustively proved. DB guards now block raw UPDATE/DELETE/TRUNCATE and raw `INSERT` of an already-resolved incident; a fully compromised runtime credential could still forge an internally consistent verification row (see below). |
| **DB runtime identity (R-1)** | **B** | Yes | Code + PostgreSQL accepted (guard 7, worker 4, invalidation 1, FastAPI 9). Startup is fail-closed. Live deployment must still set `EIMS_DB_IDENTITY`/`REQUIRED=1` and prove it in the target environment. Enforcement is at the engine facade; `create_tables.py` was moved onto `connect()` and a source scan blocks raw engine handles. |
| **PostgreSQL privilege/ownership** | **B** | Yes | Two-role topology executed by `tests/test_privilege_topology_pg.py` (24 tests): runtime is non-superuser, non-BYPASSRLS, NOINHERIT, not an owner, holds no role membership; it cannot alter/drop/disable the guards, create objects, truncate, rewrite evidence, read `alembic_version`, rewind the cycle, widen `remediation_started_at`, or move a closed incident. Residual: a compromised runtime credential can INSERT verification rows by design; least-privilege provisioning is applied by deployment, not by code. |
| **Verification before resolution** | **B** | Yes | Reference-integrity, not external-artifact proof. `analysis` is the only verification-grade evidence type. Separation of duties is one-directional (verifier ≠ attacher). A fully compromised runtime DB credential could still insert an internally consistent verification row; the DB trigger requires incident-bound evidence, matching digest, a distinct verifier and current-cycle freshness. Production must run the role per `deploy/sql/02_runtime_grants.sql` and keep trigger ownership with the migration role. |
| **Gateway authorization** | **D** | No | Unchanged from the prior acceptance. Not implemented/verified in this round; must not be exposed publicly until its own acceptance. |
| **Journal hardening** | **D** | No | Unchanged. Audit rows are not hash-chained; they carry `verification_id`/`verifier` but are not tamper-evident against a privileged writer. |
| **Benchmark mutation safety** | **D** | No | Unchanged; no regression observed, no evidence needed for this delivery decision. |
| **Maintenance CLI** | **D** | No | Operational tooling remains excluded from acceptance. |
| **Seed / `clear_db`** | **D** | No | `clear_db.py` remains an inert retired stub. Seeding is excluded. |
| **Incident ingest worker** | **D** | Partially (creates incidents) | Can create incidents, cannot resolve them, so it is outside the resolution invariant. Its integration suite needs `EIMS_INGEST_TEST_DATABASE_URL`/`_REDIS_URL`/`_SENTINEL` and was **not run** this round → 6 skips. |

## Blocking findings

None in the accepted scope. The backend has no Incident UI, so the "resolved
badge without backend approval" risk does not exist (there is no badge).

## Deliberately not claimed

- Security Acceptance as a whole is **not** granted: Gateway, Journal, Benchmark,
  maintenance CLI and seed remain excluded.
- Production readiness is **not** claimed: only disposable PostgreSQL was used.
