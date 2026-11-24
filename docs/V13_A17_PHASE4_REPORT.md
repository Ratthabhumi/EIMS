# EIMS V13 — A17 Phase 4 Report (Targeted Closure)

Date: 2026-11-19 · Scope: bounded source acceptance. **Final Acceptance NOT granted.**
No operational mutation, no container/service start, no migration.

## 1. Executive status — PARTIAL within a bounded scope

| Workstream | Status |
|---|---|
| WS1 — R-1 application DB identity | **BLOCKED** (design + trace required; not implemented) |
| WS2 — R-3 maintenance CLI | **SAFE-DISABLED** (`--apply` refuses to run) |
| WS3 — R-5 journal | **LEGACY / NOT TRUSTED FOR AUTHORITY** (no v2, no consumer) |
| WS4 — behavioral tests | **PASS** for R-2/R-3/R-4/R-6/R-7 |
| Independent review | **NOT RUN** |
| Freeze | **PASS (bounded evidence)** |

## 2. What actually changed

| File | Change |
|---|---|
| `tests/test_global_search_integration.py` | disposable guard before engine creation (A17 Ph3) |
| `tools/maintain_analyzer_sessions.py` | **`--apply` disabled fail-closed** before any engine work |
| `tools/seed_analyzer_incident.py` | `DELETE` only when `EIMS_SEED_ALLOW_DELETE=1` (Ph3) |
| `tools/sprint11_benchmark.py` | `BENCHMARK_TARGET_MISMATCH` before TRUNCATE (Ph3) |
| `tests/test_a17_closure_behavior.py` | **new** 4 structural/behavioral guards |
| `gateway/lib/risk-policy.mjs` | caller `approverVerified` no longer authorizes |
| `scripts/test-a15-execution-integrity.mjs` | **new** test: `approverVerified:true` is denied |

## 3. Status per finding, stated precisely

| Finding | Implemented | Unit/behavioral tested | Runtime-wired | Operationally verified |
|---|---|---|---|---|
| R-1 app DB identity | no | no | no | no |
| R-2 test DB isolation | yes | yes (ordering) | yes (fixture) | no |
| R-3 maintenance CLI | yes (disable) | yes | yes (refuses) | no |
| R-4 seed safety | yes (opt-in) | yes (conditional DELETE) | yes | no |
| R-5 journal | classification only | n/a | no | no |
| R-6 gateway authorization | yes (deny) | yes | **no** (module not imported) | no |
| R-7 benchmark target | yes | yes (ordering) | yes | no |

## 4. Why R-1 is not implemented

The application creates one engine in `backend/infrastructure/database.py:68` from `settings.database_url`. Verifying identity once at engine creation proves nothing about each pooled connection, and verifying at pool checkout still does not bind the result to the transaction that mutates. A correct design needs:

1. a pool-checkout listener that records the verified identity per connection, and
2. a transaction-scoped assertion before each protected mutation, or
3. a `verified_session()` factory used by every mutating path.

That requires tracing every session caller first. Phase 1 traced only 7 targets and explicitly did not claim full coverage. Implementing it blind risks breaking read-only paths. **Recorded as BLOCKED with the design above.**

## 5. Journal decision (WS3)

Verified again: `execution-journal.mjs` and `risk-policy.mjs` are imported by **0** gateway modules. There is no runtime consumer, so a v2 format would add surface with no security benefit to the shipped system.

Decision:
- v1 files and any historical records are **preserved unchanged**;
- v1 is classified **LEGACY / NOT TRUSTED FOR AUTHORITY**;
- no runtime path may treat v1 `SUCCEEDED` as execution evidence (none does today);
- L2 signer and L3 anchor remain future work;
- the library's own comments must not claim broker authenticity.

Test evidence for the deny path: `authorize({approver:'admin', approverVerified:true})` returns `APPROVER_IDENTITY_UNAVAILABLE`.

## 6. Behavioral tests executed

| Command | Result |
|---|---|
| `pytest tests/test_a17_closure_behavior.py` | **4 passed** |
| `pytest` A16/A17 focused suites (benchmark, async identity, compose, isolation, auth) | **65 passed** |
| `node scripts/test-a15-execution-integrity.mjs` | **18 passed / 0 failed** |

Commands ran in the A17 workspace; no service was started.

## 7. Gate status (bounded scope)

| Gate | Status |
|---|---|
| A — Trust architecture | **BLOCKED** (R-1, journal authenticity) |
| B — Authorization | **PARTIAL** (safe denial, no principal) |
| C — Runtime mutation enforcement | **PARTIAL** (2 paths closed, app engine open) |
| D — Infrastructure | **NOT RUN** |
| E — Independent review | **NOT RUN** |

## 8. Residual risks

1. Application runtime still trusts whatever `settings.database_url` resolves to.
2. Maintenance CLI is disabled, not guarded — the capability is unavailable, not safe.
3. Seed deletion is opt-in but the opt-in alone does not prove target safety.
4. Benchmark equality check compares name/port only, not host/role/server.
5. Journal v1 is untrusted; no runtime consumer exists.
6. Gateway has no trusted principal; sensitive actions are denied, read-only unaffected in code but unwired.
7. No independent review of this revision.

## 9. Manifests

| Repo | File | SHA-256 |
|---|---|---|
| EIMS | `evidence/v12-a17-final-manifest.json` | `A108C4D074CB668B855128B7C74006E54F7CB9CE227F0D24D77C8DFB42D6D578` |
| Chat_HAND | `evidence/v12-a17-final-manifest.json` | `E04EACE441DDE748000402885F711C842366BB0BF5D06784F6878C3162184ABC` |

## 10. Honest closure statement

The project can be frozen truthfully at this scope **only if** the remaining HIGH items (R-1, journal authenticity, independent review) are disclosed as unresolved. It is not accurate to describe A17 as a complete security closure.
