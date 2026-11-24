# EIMS V12 — A14 Campaign Report

Date: 2026-11-18/19 (Asia/Bangkok)
Scope: A13 re-review, RV closure, offline Track C tier-1, evidence freeze. **Final Acceptance NOT granted.**

## 1. Executive status

| Phase | Status |
|---|---|
| A14.0 identity + re-review | **PASS** (re-review executed) |
| A14.1 RV closure | **PARTIAL** (RV-1, RV-2, RV-8, RV-9 closed; RV-3/4/5/6/7/10/11/12 open or partially addressed) |
| A14.2 isolation security | **PARTIAL** |
| A14.3 Chat_HAND F1/F4/F5 | **NOT RUN** (no source change; design only) |
| A14.4 Compose completion | **PARTIAL** |
| A14.5 audit package | **DESIGN_COMPLETE** (not applied) |
| A14.6 vector readiness | **DESIGN_COMPLETE** |
| A14.7 Track C tier-1 | **PARTIAL** (focused offline suites only) |
| A14.8 final review | **PASS** (no HIGH in the A14 delta) |
| A14.9 freeze | **PASS** (evidence freeze, not a Git commit) |

## 2. Repository identity

Chat_HAND `v2/verified-fallback` @ `c293b8aa…`; EIMS `integration/eims-consolidated` @ `85493b21…`.
Both worktrees unchanged by A14 (only new docs/evidence in the live repos).

## 3. Evidence integrity

A11 manifests, A12 registers, A13.1 assessment and A13 manifests verified unchanged. A13 manifest hashes matched the supplied values exactly.

## 4. A13 post-review snapshot

A byte-identical copy of the A13 workspace was reviewed. Then the A14 delta was applied and reviewed again. The final review covered only the delta (4 files) and found no HIGH issue.

## 5. RV disposition

| ID | Status | Note |
|---|---|---|
| RV-1 | **CLOSED** | sprint11 now validates `EIMS_BENCHMARK_DATABASE_URL` against the same allowlist/denylist before creating an engine or truncating; sprint12 guarded |
| RV-2 | **CLOSED** | exact endpoint match; operational bucket denylist; wildcard test |
| RV-3 | **OPEN** | operator authorization only; no cryptographic/server attestation (documented) |
| RV-4 | **OPEN** | schema still read from an intent variable; post-connect attestation not wired |
| RV-5 | **OPEN** | refusal is `pytest.skip`; a fully skipped suite must be reported NOT RUN |
| RV-6 | **PARTIAL** | AST test added; it proves presence, not dominance or ordering |
| RV-7 | **OPEN** | incident/analyzer integration tests keep a second policy |
| RV-8 | **CLOSED** | message corrected |
| RV-9 | **CLOSED** | four design docs present |
| RV-10 | **OPEN** | scanner still exempts any `${...}` value, including `:-` defaults |
| RV-11 | **OPEN** | mutable tags (`:latest`, `redis:7-alpine`) not resolved; no offline digest verification |
| RV-12 | **PARTIAL** | allowlist remains rule-level; service/rule tightening not applied |

## 6. Test isolation

Strict allowlist + identity guard; 38 offline checks pass (isolation 21, auth 6, compose 9, plus wiring). Default settings fail closed with zero connection attempts. Residual: allowlist is operator-controlled; schema is intent-only; a skip is not a pass.

## 7. Chat_HAND F1–F5

F1 `NEEDS_DESIGN_DECISION`, F2 `BLOCKED`, F3 `FIXED_IN_WORKSPACE (A12)`, F4 `NEEDS_DESIGN_DECISION`, F5 `PARTIAL`. No code change in A14. Track B stays BLOCKED.

## 8. EIMS F1–F6

F1 `FIXED_IN_WORKSPACE` (guard + tools), F2 `FIXED_IN_WORKSPACE`, F3 `PARTIAL`, F4 `DESIGN_COMPLETE`, F5 `RESOLVED_AS_SEMANTIC`, F6 `DESIGN_COMPLETE`.

## 9. Compose security

Secrets externalized with `${VAR:?}`, loopback bindings, private bucket. Remaining: Redis without auth/ACL, PgBouncer `plain` auth without verified TLS, mutable image tags, interpolation defaults not flagged.

## 10. Audit migration readiness

Canonical record, hash chain, additive migration proposal, verifier algorithm, anchor interface and threat model are documented. No migration applied, no provider selected, no anchor operational. **Tamper-evident may not be claimed.**

## 11. Vector contract

Direct 768→384 cast confirmed as a conditional defect. Model contract **UNVERIFIED**; reproduction plan and SQL prepared; no service started.

## 12. Offline test inventory and results

| Suite | Class | Result |
|---|---|---|
| `test_fixture_isolation_contract.py` | offline contract | 21 passed |
| `test_auth_mode_contract.py` | offline contract | 6 passed |
| `test_compose_security_audit.py` | static | 9 passed (with tightened pairs partially applied) |
| combined | offline | **38 passed, 0 failed, 0 skipped** |
| default-settings lifespan test | blocked by design | **skipped**, 0 connections — reported NOT RUN, not PASS |

## 13. Independent review

Re-review: `ACCEPT_WITH_FINDINGS`; found the sprint11 HIGH (unvalidated TRUNCATE target) which was then fixed. Final delta review: `ACCEPT_WITH_FINDINGS`; no HIGH; new MEDIUM findings: `assert_disposable_database_url` lacks unit tests; benchmark URL and `settings` may diverge (methodology, not safety).

## 14. Exact changes and hashes

A14 EIMS delta: 4 modified, 0 added.

- `tests/disposable_guard.py`
- `tests/test_fixture_isolation_contract.py`
- `tools/sprint11_benchmark.py`
- `docs/V12_A13_TEST_ISOLATION_DESIGN.md`

A14 manifest: `evidence/v12-a14-remediation-manifest.json` = `0E9F90E5A6BFC25E7A54A5BEDD7D796DB55E07E4F78F79D63AE5D9AED05F3DCF`

## 15. Residual risks

1. Isolation guard is authorization, not attestation.
2. Schema identity not attested; a skip is not a run.
3. Tools other than the two patched ones may still start the lifespan (not exhaustively inventoried).
4. Compose: Redis auth, PgBouncer SCRAM/TLS, image digests.
5. Chat_HAND completion and approval remain forgeable by a same-user process.
6. Audit has no anchor; vector contract unknown.
7. A14 delta fixed after the re-review received a delta-only review, not a full re-review.

## 16. Gate A/B/C/X

| Gate | Status |
|---|---|
| A — Source Integrity | **PARTIAL** (freeze exists; RV open) |
| B — Chat_HAND | **BLOCKED** (F1/F2/F4) |
| C — EIMS | **BLOCKED** (F3/F4/F6, product tests not run) |
| X — Cross-system | **NOT RUN** |

## 17. Work not performed

No container or runtime started; no migration applied; no operational connection; no Trust Grant; no commit/stage/push; no GUI or live E2E; no vector reproduction; no Track B/C full suites; no C7 rerun.

## 18. Separate approvals required

1. Authenticated approver identity (F2).
2. External audit anchor provider and trust boundary.
3. Disposable pgvector service start.
4. Operational Compose rollout plan with maintenance window and rollback.
5. Full re-review of the frozen A14 revision before Track C tier-2.
