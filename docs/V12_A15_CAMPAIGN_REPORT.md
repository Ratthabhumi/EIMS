# EIMS V12 — A15 Campaign Report

Date: 2026-11-18/19 (Asia/Bangkok)
Scope: security-boundary closure, offline implementation, full review, evidence freeze. **Final Acceptance NOT granted.**

## 1. Executive status

**PARTIAL.** The offline controls were implemented and tested, the benchmark URL boundary now fails closed, and a full independent review was performed. Two HIGH findings from that review remain: the connected-identity verifier is library-only (not wired), and the execution journal is not wired into the gateway.

## 2. Repository identity

Chat_HAND `v2/verified-fallback` @ `c293b8aa…`; EIMS `integration/eims-consolidated` @ `85493b21…`. Neither worktree received A15 source changes; only reports and manifests were added.

## 3. A11–A14 evidence integrity

A11 manifests, A12 registers, A13 manifests and A14 evidence were verified unchanged. **A14 manifest discrepancy found:** the campaign prompt supplied `0E9F90E5…` for both repositories. The EIMS artifact does hash to `0E9F90E5…`, but **no Chat_HAND A14 manifest exists** — the supplied Chat_HAND value was a duplicate of the EIMS value. Recorded, not assumed.

## 4. A14 freeze verification

A14 was an evidence freeze, not a security acceptance. Its final review was delta-only. A15 does not inherit that review as coverage.

## 5. RV-1 — RV-12 disposition

| ID | Status | Evidence |
|---|---|---|
| RV-1 | **CLOSED (EIMS)** | `assert_disposable_database_url` called before `create_async_engine`; 15 dedicated checks incl. AST ordering; any URL query string now refused |
| RV-2 | **CLOSED** | exact endpoint match, operational bucket denylist, wildcard tests |
| RV-3 | **OPEN** | operator authorization only; no cryptographic attestation (documented) |
| RV-4 | **PARTIAL** | `verify_connected_identity` implemented + unit tested; **not wired** and not async-compatible (review F2) |
| RV-5 | **OPEN** | skip is still a skip; reports must use NOT RUN |
| RV-6 | **PARTIAL** | AST guard-presence test added; dominance not proven |
| RV-7 | **OPEN** | incident/analyzer paths keep a second policy |
| RV-8 | **CLOSED** | message corrected in A14 |
| RV-9 | **CLOSED** | four design docs present |
| RV-10 | **PARTIAL** | scanner now flags `:-`, `-`, `:+` defaults; inline URL credential with `${` fixed; broader syntax still not a full parser |
| RV-11 | **BLOCKED** | image digests cannot be verified offline; no pinning attempted |
| RV-12 | **PARTIAL** | rule-level allowlist unchanged; service/rule test not applied |

## 6. Benchmark URL guard

Implemented and tested: scheme, exact endpoint, database name, role, operational denylist (name/role/port), empty/missing/malformed values, encoded credentials, and **any query string refused** (F1). Ordering is proven by an AST test and by the call site before engine creation.

## 7. Database identity validation

`verify_connected_identity(conn, expected)` compares `current_database()`, `current_user` and `current_schema()` and refuses known operational identities. Unit tested with a fake connection. **Not wired into any execution path**; the real engine is async and the helper is sync. RV-4 therefore remains open at runtime.

## 8. Isolation call graph

Entry points covered: `tests/conftest.py` client fixture, four test files with direct `TestClient(app)`, and the two tools patched in A14. An AST test asserts every `TestClient` call in `tests/` and `tools/` has a guard call. Coverage is presence-level, not dominance-level.

## 9. Compose interpolation

`SAFE_INTERPOLATION` accepts only `${NAME}` and `${NAME:?message}`. Six tests cover `${X}`, `${X:?m}`, `${X:-lit}`, `${X-lit}`, `${X:+lit}` and a literal. Inline URL credentials are no longer exempted merely because the string contains `${`.

## 10. Redis ACL design

Not implemented. Design requirement recorded: per-service ACL users (app, telemetry worker, incident worker, health, admin), key patterns, command categories, pub/sub and stream permissions, TLS where the boundary requires it. No operational Redis was touched.

## 11. PgBouncer auth/TLS/version

Not implemented. `auth_type: plain` remains in the compose file. Required: verify the deployed PgBouncer version against the 1.26.0 security fixes (CVE-2026-19888 / -6668 / -6669), then move to SCRAM-SHA-256 with separately configured client and server TLS. **Compatibility unverified, so no change was made.**

## 12. Image references

**BLOCKED.** `:latest` and mutable tags remain. Digests cannot be verified without a registry action outside the authorized scope; no value was invented.

## 13. Chat_HAND F1–F5

| Finding | Status |
|---|---|
| F1 execution journal | **FIXED_IN_WORKSPACE (library)** — `execution-journal.mjs`: legal transitions, immutable attempt identity, COMPLETED requires broker proof, recovery yields COMPLETION_UNKNOWN. **Not wired into the gateway.** |
| F2 approval identity | **BLOCKED** — no authenticated approver exists |
| F3 README | **FIXED_IN_WORKSPACE (A12)** |
| F4 pre-execution | **FIXED_IN_WORKSPACE (library)** — `risk-policy.mjs` default-denies unknown and sensitive classes; not wired |
| F5 scope | **PARTIAL** — A12 hashing retained; TOCTOU/attestation open |

Review finding F3 is accepted: `append()` is a public method, so any holder of the journal can append COMPLETED **if** it supplies broker-shaped proof. Proof is a structure, not an authenticated signature; that remains an open MEDIUM.

## 14. Audit synthetic verification

**DESIGN_COMPLETE, NOT IMPLEMENTED.** The verifier was not written in A15. No migration applied, no anchor configured.

## 15. Vector model contract

**UNVERIFIED.** Static analysis confirms the direct 768→384 cast. The embedding model contract was not established; no service started.

## 16. Offline regression

| Suite | Result |
|---|---|
| Chat_HAND execution integrity | **16 passed / 0 failed** |
| EIMS benchmark URL guard | **15 passed** |
| EIMS compose interpolation + audit | **15 passed** |
| EIMS isolation + auth | **29 passed** |
| Combined EIMS | **59 passed / 0 failed / 0 skipped** |

No service-dependent test, no C7, no GUI, no E2E.

## 17. Full independent review

Claude Code 2.1.323, plan mode, full workspace review. Verdict: **PARTIAL**.

| ID | Sev | Finding | Status after A15 |
|---|---|---|---|
| F1 | MED | URL query substring bypass | **fixed** (whole query refused) |
| F2 | **HIGH** | identity verifier is dead code and async-incompatible | **OPEN** |
| F3 | **HIGH** | journal COMPLETED is not authenticated; append is public | **PARTIAL** (proof + immutability required; still unauthenticated and unwired) |
| F4 | MED | URL-credential check skipped on `${` | **fixed** |
| F5 | MED | no fsync/lock; torn line throws | **OPEN** |
| F6 | MED | unkeyed chain; tail truncation undetected | **OPEN** |
| F7 | MED | `run_focused_tests` allowed without scope check | **OPEN** |
| F8 | MED | `approverVerified` is caller-supplied | **OPEN** (documented as library-only) |
| F9 | LOW | AST ordering compares line numbers only | **OPEN** |

## 18. New manifest hashes

| Repo | Manifest | SHA-256 |
|---|---|---|
| EIMS | `evidence/v12-a15-remediation-manifest.json` | `F6C6F2E59D7D14A4C660EF103639700FEBEB3B396B6EDA5C1B2E3C100E1C5906` |
| Chat_HAND | `evidence/v12-a15-remediation-manifest.json` | `07DEE01B8F4320B41EFEB3E408E2ECA267EF81A3E3F334E2886CD805922CD6F1` |

A15 EIMS delta: 2 modified, 2 added. Chat_HAND delta: 3 added, 0 modified.

## 19. Residual risks

1. Identity verification is not enforced at runtime (RV-4 / F2).
2. Journal and risk policy are libraries, not controls (F3/F7/F8).
3. Journal is unkeyed and not crash-safe (F5/F6).
4. Redis has no auth/ACL; PgBouncer plain auth without verified TLS.
5. Image digests unverified; mutable tags.
6. Skip vs not-run still depends on report discipline.
7. Audit and vector remain design-only.

## 20. Gate A/B/C/X

| Gate | Status |
|---|---|
| A — Source Integrity | **PARTIAL** (full review done; RV open) |
| B — Chat_HAND | **BLOCKED** (F1/F4 unwired, F2 blocked) |
| C — EIMS | **BLOCKED** (Compose, audit, vector, product tests) |
| X — Cross-system | **NOT RUN** |

## 21. Work not performed

No container or runtime start; no migration; no operational connection; no Trust Grant; no image pull/pin; no Redis/PgBouncer reconfiguration; no audit verifier implementation; no vector reproduction; no Track B/C suites; no C7; no commit/stage/push.

## 22. Separate approval requirements

1. Authenticated approver identity (F2).
2. Wiring approval for the journal and risk policy (changes execution behaviour).
3. Redis ACL + PgBouncer SCRAM/TLS rollout with compatibility verification.
4. Image digest verification (registry access).
5. Audit verifier implementation and anchor selection.
6. Disposable pgvector service start.
7. Full re-review after wiring.

## 23. Honest classification

| Claim | Class |
|---|---|
| Benchmark URL boundary closed | **IMPLEMENTED + TESTED** |
| Compose interpolation default-literal detection | **IMPLEMENTED + TESTED** |
| Execution journal semantics | **IMPLEMENTED AS LIBRARY, NOT WIRED** |
| Risk policy default-deny | **IMPLEMENTED AS LIBRARY, NOT WIRED** |
| Connected-identity verification | **IMPLEMENTED, NOT WIRED** |
| Redis ACL / PgBouncer SCRAM/TLS | **DESIGN ONLY** |
| Audit verifier | **DESIGN ONLY** |
| Vector contract | **UNVERIFIED** |
