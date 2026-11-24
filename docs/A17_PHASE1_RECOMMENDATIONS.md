# A17 Phase 1 — Recommendations (minimum safe remediation)

Date: 2026-11-19 · **Proposal only. No source change authorized yet.**

## Scope principle

Close the six HIGH gaps with the smallest changes that actually reach the execution path. Do not build a broker, do not add infrastructure, do not refactor unrelated code.

## P0 — must fix before any acceptance

### R-1 Target guard at the single application engine (G-1)
Add one check inside `backend/infrastructure/database.py` after engine creation: read `current_database/current_user/current_schema` and refuse to serve if the target is not allowlisted by an explicit environment policy. One place, inherited by every runtime path.
Risk: startup fails closed when the policy is absent → dev must set it. Mitigation: allow `development` to default to the current target but log it as unverified.

### R-2 Guard the test fixture (G-2)
`tests/test_global_search_integration.py::db_session` must call the existing disposable guard before `create_async_engine`, exactly like `conftest.py`. This is a small, local change; no product code.

### R-3 Guard the maintenance CLI (G-3)
`maintain_analyzer_sessions.py` gains: URL allowlist, post-connect identity verification on the same connection, and a printed resolved target before `--apply`. No new approval system.

### R-4 Fix the seed contradiction (G-4)
Either remove the `DELETE` (it is scoped to `parse_method`) or correct the docstring and require an isolated target. Recommended: keep the delete, remove the false claim, and require a disposable target before any write.

### R-5 Downgrade the completion claim (G-7) — L1
- Delete `observedBy`-as-proof acceptance.
- `SUCCEEDED` may only be recorded by the broker when it observed the process result; otherwise `UNVERIFIED`.
- `recover()` becomes internal.
- Persist and verify `proof`; require CREATED first; check immutability.
- Documentation: "local integrity only; not authenticity; same-user attacker can rewrite."
This closes the *false claim* and the *forgery path used by callers that are not the broker*. It does not create strong anti-forgery — that stays declared as not implemented.

### R-6 Wire or remove (G-6)
Either import the journal/policy into the gateway execution path behind a feature flag with tests, or mark both modules as `NOT WIRED` and stop claiming they enforce anything. Given the project deadline, **removing the claim is acceptable; leaving unwired libraries described as controls is not.**

## P1 — fix if time permits

### R-7 Benchmark seed/measure equality (G-5)
Assert `benchmark_db_url` and `settings.database_url` resolve to the same database before measuring, or fail with a clear message.

### R-8 Authorization (G-8)
If a real server principal does not exist, delete the `approver`/`approverVerified` parameters and make every sensitive class throw `NOT_AUTHORIZED`. A parameter that callers can set is worse than no parameter.

## P2 — explicitly deferred

| Item | Status |
|---|---|
| Separate signer / broker (L2) | **DEFERRED** — requires process identity + key custody |
| External journal checkpoint (L3) | **DEFERRED** |
| Redis ACL | **DEFERRED** (infrastructure) |
| PgBouncer SCRAM/TLS | **DEFERRED** (infrastructure) |
| Image digest pinning | **DEFERRED** (registry access) |
| Audit verifier + anchor | **DEFERRED** (design only) |
| Vector 768→384 contract | **VERIFY ONLY** — model identity must be established first |

## What this buys and what it does not

| Claim | After R-1…R-8 |
|---|---|
| Destructive CLI/test paths fail closed on a non-allowlisted target | **yes, if R-1…R-4 land** |
| Application runtime verifies its database identity | **partial** — one startup check, not per-transaction |
| Journal cannot be forged by a caller | **no** — only the caller-supplied-proof path closes |
| Journal resists same-user attacker | **no** — declared limitation |
| Authorization is server-side | **only if R-8 lands** |
| Infrastructure hardened | **no** |

## Decision requested

Approve P0 (R-1…R-6) as the A17 source scope. P1 only if the P0 verification passes and time remains. P2 stays deferred and documented.

No source was modified in Phase 1.
