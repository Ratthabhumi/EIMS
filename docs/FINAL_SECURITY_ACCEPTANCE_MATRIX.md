# EIMS — Final Security Acceptance Matrix

**Date:** 2026-11-19 · HEAD `85493b2` · no source claim without a test reference.

Status vocabulary: **FIXED** (behaviourally proven) · **MITIGATED** (risk reduced, limitation stated) ·
**EXCLUDED** (capability removed from the product path) · **OPEN** · **STALE**.

| ID | Item | Status | Evidence | Residual / condition |
|---|---|---|---|---|
| **NF-1** | `clear_db.py` unguarded TRUNCATE | **FIXED** | inert import test; opt-in refusal test; gate unit tests | identity-denied path of the script itself untested; tool excluded from demo |
| **NF-2** | `cleanup_auth_records` destructive default | **FIXED** | dry-run default; denied-before-delete; accepted disposable path | no runtime caller (enforced by test) |
| **NF-3** | maintenance CLI documented SAFE-DISABLED | **FIXED (documentation)** | module docstring matches source | CLI remains enabled but gated; do not call it "disabled" |
| **NF-4 / R-6** | benchmark target safety name-only | **MITIGATED** | gate before TRUNCATE | name check still weak; benchmark excluded from claims |
| **NF-6 / R-5** | seed DELETE without guard | **MITIGATED** | gate before DELETE; docstring corrected | seed excluded from demo |
| **R-1** | DB identity at mutation boundary | **ENFORCED WHEN CONFIGURED** | `db_identity.py`; live-row check at the request-session choke point; 19 tests incl. get_session wiring | **ordinary CRUD writes are not gated**; no deployment sets `EIMS_DB_IDENTITY`; not closed |
| **R-3** | gateway authorization | **EXCLUDED** | `gateway/lib/risk-policy.mjs` absent | requires a trusted principal source |
| **R-4** | journal / tamper evidence | **EXCLUDED** | no journal implementation | requires an independent signer and checkpoints |
| **NF-5** | A17 artefacts missing | **OPEN** | files absent | prior claims must be reported as not present |
| **NF-7** | F2 `_urlsplit` defect | **STALE** | no such symbol in source/tools | do not claim R-7 verified as a check |
| **R-7** | manifest per-file hashes | **MITIGATED** | 4 manifests re-hashed and matched | per-file manifest still absent |
| **R-2** | test isolation | **MITIGATED** | guard-before-engine; disposable URL rules | not operationally verified |

## Security acceptance decision

**NOT ACCEPTED.**

Blocking conditions:
1. R-1 is only partially mitigated: writes outside the destructive helpers are not gated.
2. R-3 and R-4 remain absent/excluded.
3. No deployment configuration (`EIMS_DB_IDENTITY`) is provisioned and verified.
4. Real PostgreSQL behaviour (`shobj_description`, PgBouncer transaction mode) was not
   exercised in this round — no disposable infrastructure was provisioned.

This decision is independent of the delivery decision: the product path can be delivered
while security acceptance remains not accepted.

## What would change the decision

| Requirement | Minimum evidence |
|---|---|
| R-1 closed | expected identity provisioned in deployment + checkout/transaction gate on all write paths + tests on a disposable PG |
| R-3 closed | trusted principal source documented and wired; deny-by-default tests at the operation boundary |
| R-4 closed | independent signer, key custody, runtime emission and verification tests |


## Update — 2026-11-19 (Final Integration round)

| ID | Previous | Now | Evidence |
|---|---|---|---|
| NF-1 | FIXED (gated) | **FIXED (retired)** | clear_db.py is an inert stub; the suite asserts no destructive entry point |
| R-1 | MITIGATED (destructive paths only) | **ENFORCED WHEN CONFIGURED; NOT CLOSED** | require_runtime_identity at the request-session choke point; 5 new tests |
| R-3 / R-4 | EXCLUDED | EXCLUDED (unchanged) | artefacts absent |
| R-5 / R-6 | MITIGATED | MITIGATED (unchanged) | gates before DELETE / TRUNCATE |

Security acceptance remains **NOT ACCEPTED**: no deployment identity is configured,
worker and direct-engine sessions are not covered, and no real-database identity test was
executed in this round.
