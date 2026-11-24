# EIMS — Final Operational Readiness Report

**Date:** 2026-11-19 · Branch `integration/eims-consolidated` · HEAD `85493b2`

## 1. What changed in this round

| File | Change |
|---|---|
| `backend/infrastructure/db_identity.py` | Added `require_runtime_identity` (Policy A) next to the existing destructive-target gate (Policy B) |
| `backend/infrastructure/database.py` | `get_session()` runs the identity check on every request session **before** yielding |
| `clear_db.py` | **Retired**: inert module, no engine import, no SQL; exits with guidance |
| `tests/test_mutation_safety.py` | 12 → **17 tests**: runtime policy (unconfigured / required / malformed / mismatch / cache) and the retired-script check |

Design and bypass analysis: `FINAL_DATABASE_IDENTITY_DESIGN.md`.

## 2. R-1 outcome

- Application writes obtained through the API dependency are checked against the live
  connection. With `EIMS_DB_IDENTITY` configured, a wrong database **or** wrong role is
  rejected before the statement runs.
- With no configuration the session is marked `unconfigured` and a one-time WARNING is logged — the application
  keeps working (the owner's explicit requirement), and compliance is never claimed.
- `EIMS_DB_IDENTITY_REQUIRED=1` converts missing configuration into a hard failure.
- **Not closed:** background-worker sessions, direct engine construction, and sessions that
  re-check out a connection are not covered; no deployment carries the configuration yet.

## 3. Engineer workflow (Workstream C)

Not re-implemented in this round. Its status is unchanged from V16:
analyzer → incident → evidence is implemented and partially tested; the
remediation/verification stages are the weakest link. `FINAL_ENGINEER_WORKFLOW_ACCEPTANCE.md`
records the ten questions, what the current data model can answer, and the gaps.

## 4. Excluded capabilities (unchanged, now explicit)

| Capability | State |
|---|---|
| `clear_db.py` | **retired** (inert stub) |
| maintenance CLI | enabled, dry-run default, destructive path gated; excluded from demo |
| seed tools | gated before DELETE; excluded from demo |
| benchmark | gated before TRUNCATE; excluded from claims |
| gateway authorization (R-3) | excluded — no trusted principal |
| journal (R-4) | excluded — no runtime consumer or independent signer |

## 5. Tests executed this round

| Command | Result |
|---|---|
| `pytest tests/test_mutation_safety.py` | **17 passed** (5.1 s) |
| `pytest` correlation + ingest unit + recovery + analyzer integration | **117 passed, 68 skipped** (1.5 s) |
| `compileall backend tools clear_db.py` | exit 0 |

The 68 skips are DB-gated tests (no `EIMS_TEST_DATABASE_URL`). No disposable PostgreSQL was
provisioned this round, so **no real-database identity test was executed**; that is the
largest evidence gap in this report.

## 6. Decision

**Delivery: CLOSED — WITH EXPLICIT EXCLUSIONS.**
**Security acceptance: NOT ACCEPTED.**

Reasons: R-1 is not verified in a real deployment and does not cover worker/direct-engine
paths; R-3 and R-4 remain excluded; the engineer remediation/verification workflow is not
behaviourally demonstrated end to end.

## 7. Exact remaining work (no new audit)

1. Provision a disposable PostgreSQL and run the identity matrix (wrong db, wrong role,
   reconnect, ORM/Core/text SQL) — the test plan is in the design document.
2. Extend Policy A to `get_session_maker()` consumers.
3. Set `EIMS_DB_IDENTITY` + `EIMS_DB_IDENTITY_REQUIRED=1` in the target deployment.
4. Add remediation/verification evidence fields and a behavioural test for the close path.
