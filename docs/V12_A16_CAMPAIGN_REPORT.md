# EIMS V12 — A16 Campaign Report

Date: 2026-11-19 (Asia/Bangkok)
Scope: trust-boundary enforcement & runtime wiring. **Final Acceptance NOT granted. A16 is NOT accepted.**

## 1. Executive status

**BLOCKED.** A16 wired the async identity check into the benchmark TRUNCATE path and added a journal authority primitive, but the full independent review rejected the revision with **4 HIGH findings**. Two of them are claim-level: the journal and the risk policy are still caller-trusting and are not wired into the gateway at all.

## 2. Repository identity

Chat_HAND `v2/verified-fallback` @ `c293b8aa…`; EIMS `integration/eims-consolidated` @ `85493b21…`. No source change in the real repositories.

## 3. Historical evidence integrity

A11–A15 evidence unchanged. A15 manifests verified:

- EIMS `F6C6F2E59D7D14A4C660EF103639700FEBEB3B396B6EDA5C1B2E3C100E1C5906`
- Chat_HAND `07DEE01B8F4320B41EFEB3E408E2ECA267EF81A3E3F334E2886CD805922CD6F1`

The A14 Chat_HAND manifest gap remains recorded, not fabricated.

## 4. A15 finding disposition

| A15 finding | A16 result |
|---|---|
| RV-4 identity verifier not wired | **PARTIAL** — wired on the benchmark path only; other paths unguarded |
| F2 journal authority | **PARTIAL** — private symbol, but proof is self-asserted |
| F3 journal forgeability | **OPEN** — HIGH |
| F4 policy caller trust | **OPEN** — HIGH |
| F5 scope | unchanged |
| F9 ordering test | **PARTIAL** — async test added, ordering still line-based |

## 5. EIMS async identity call graph

| Path | URL source | Guard | Identity check | Mutation |
|---|---|---|---|---|
| `tools/sprint11_benchmark.py` | `EIMS_BENCHMARK_DATABASE_URL` | yes | **yes (async, same engine)** | TRUNCATE after check |
| `tools/maintain_analyzer_sessions.py --apply` | own URL | none | none | DELETE |
| `tools/seed_analyzer_incident.py` | own URL | none | none | DELETE |
| `tools/seed_demo_data.py` | `settings` (default `eims_registry`) | none | none | writes |
| `tests/test_global_search_integration.py` `db_session` | `settings.database_url` | none | none | test DB access |
| `tests/conftest.py` client | settings + allowlist | yes | no (guard only) | lifespan |

The "every mutation path" requirement is **not met**.

## 6. Identity verification tests

`tests/test_async_identity.py` — 6 checks with async doubles: matching, wrong DB, wrong role, operational session user, wrong schema, missing row. All pass. They do not prove `main()` ordering; that is a reviewer finding (#9/MEDIUM).

## 7. Isolation call-order evidence

The benchmark now validates URL → creates engine → awaits identity → seeds/truncates. The identity check runs on a pooled connection that is released before the TRUNCATE, so the mutation may use a different connection (reviewer #9/LOW).

## 8. Chat_HAND journal authority

`createBrokerJournal()` is the only way to obtain an append capability; `ExecutionJournal._append` rejects anything but the module-private symbol. A caller-constructed journal cannot append (tested).

**However** `record()` accepts a caller-supplied `proof` object; `observedBy: 'broker'` is a string, not an attestation. The hash chain is unkeyed and `verify()` does not require CREATED first, does not check immutability, and does not persist proof. **COMPLETED remains forgeable by anyone who can write the journal file.**

## 9. Journal durability and threat model

Not implemented: fsync, atomic append, cross-process lock, torn-write recovery, key custody. The referenced `docs/V12_A16_CHAT_HAND_TRUST_BOUNDARY.md` was **not created** — a dangling reference (reviewer #6).

Same-user compromise is explicitly **outside** what this design can defend; that limitation is stated here, not in the missing doc.

## 10. Action registry and approval boundary

`risk-policy.mjs` still accepts `action`, `approver` and `approverVerified` from the caller. `approver: 'x', approverVerified: true` authorizes write/delete/deploy/grant — **contradicting the module's own comments**. It is imported only by a test. There is no trusted action registry.

## 11. F1–F5 disposition

| Finding | Status |
|---|---|
| F1 | **IMPLEMENTED_NOT_WIRED** — authority primitive exists; broker does not use it; proof forgeable |
| F2 | **BLOCKED** — no authenticated approver |
| F3 | **FIXED_IN_WORKSPACE (A12)** |
| F4 | **IMPLEMENTED_NOT_WIRED** — caller-trusting |
| F5 | **PARTIAL** |

## 12. Redis ACL inventory/policy

Not produced in A16. Design requirement stands: per-service command/key/channel matrix, explicit denial of `FLUSHALL`-class commands, no `+@all`, no `~*`.

## 13. PgBouncer assessment

Not produced. `plain` auth remains; TLS directions unverified; version vs 1.26.0/1.26.1 advisories not assessed against the project image.

## 14. Compose interpolation

A15 scanner change retained; A16 added no new syntax coverage. Nested expressions and `$$` remain untested.

## 15. Audit verifier

**NOT IMPLEMENTED** (A16.7 was not reached). Design only.

## 16. Vector model contract

**UNVERIFIED.** No model identification performed.

## 17. Offline regression

| Suite | Result |
|---|---|
| EIMS (async identity + benchmark + compose + isolation + auth) | **65 passed / 0 failed** |
| Chat_HAND execution integrity | **17 passed / 0 failed** |

Skipped: 0. No service-dependent test was run.

## 18. Full independent review

Claude Code 2.1.323, plan mode, full workspace. **Verdict: NOT ACCEPTED.**

| # | Sev | Finding |
|---|---|---|
| 1 | **HIGH** | Journal COMPLETED forgeable: self-asserted proof, unkeyed chain, `verify` gaps, public `recover` |
| 2 | **HIGH** | `risk-policy` trusts caller `approverVerified`; comments claim unconditional denial |
| 3 | **HIGH** | Journal and policy wired nowhere — no effective control |
| 4 | **HIGH** | Guard coverage incomplete: `maintain_analyzer_sessions --apply`, `seed_analyzer_incident` DELETE, `seed_demo_data`, `test_global_search_integration` unguarded |
| 5 | MEDIUM | Benchmark seeds `engine` but measures `settings` DB |
| 6 | MEDIUM | Referenced trust-boundary doc missing |
| 7–12 | LOW | verify gaps, optional identity fields, pooled connection, no lock, test ordering, `pytest.skip` in CLI |

## 19. New manifests

| Repo | Manifest | SHA-256 |
|---|---|---|
| EIMS | `evidence/v12-a16-remediation-manifest.json` | `D8481ABB6FDCD873CF625339A1E6D551EE25EFAB2E241EEA11FC11E10111B84A` |
| Chat_HAND | `evidence/v12-a16-remediation-manifest.json` | `F0CDDA94A2575A5C3691431EC753BA8DB34341ABEB7737F087ED123444003963` |

A16 delta: EIMS 2 modified + 1 added; Chat_HAND 2 modified.

## 20. Residual risks

1. COMPLETED can be forged by a file writer.
2. Policy is caller-authoritative and unwired.
3. Four destructive paths remain unguarded.
4. No crash-safety or key custody.
5. Same-user compromise is undefended (documented here only).
6. Audit verifier, Redis ACL, PgBouncer, image digests, vector contract all open.

## 21. Gate A/B/C/X

| Gate | Status |
|---|---|
| A | **PARTIAL** (full review done; HIGH open) |
| B | **BLOCKED** |
| C | **BLOCKED** |
| X | **NOT RUN** |

## 22. Work not performed

No container/runtime start; no migration; no operational connection; no Trust Grant; no image pull; no Redis/PgBouncer change; no audit verifier; no vector reproduction; no Track B/C suites; no C7; no commit/stage.

## 23. Separate approval requirements

1. Authenticated approver identity (F2).
2. Separate broker process/identity before claiming journal authenticity.
3. Decision on wiring the policy into execution (changes behaviour).
4. Redis ACL + PgBouncer SCRAM/TLS rollout.
5. Registry access for image digests.
6. Audit verifier + anchor.
7. pgvector service start.
8. Full re-review after the four HIGH findings are fixed.

## 24. Honest classification

| Claim | Class |
|---|---|
| Benchmark TRUNCATE path protected | **WIRED + TESTED** (one path only) |
| Async identity verifier | **IMPLEMENTED + TESTED**, wired on one path |
| Journal authority primitive | **IMPLEMENTED**, not wired, proof forgeable |
| Risk policy | **IMPLEMENTED**, caller-trusting, unwired |
| Anti-forgery guarantee | **NOT ACHIEVED** |
| Guard on every destructive path | **NOT ACHIEVED** |
| Redis/PgBouncer/audit/vector | **NOT DONE** |
