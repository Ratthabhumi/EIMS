# EIMS V12 — A12 Remediation Report

Date: 2026-11-18 (Asia/Bangkok)
Base: A11 frozen snapshot `53EE6A40…` / HEAD `85493b21…`
Workspace: `%TEMP%\v12-a12\EIMS` (mutable; the A11 snapshot was not modified)

## 1. Changed files

| File | Change |
|---|---|
| `tests/disposable_guard.py` | **New** shared guard: refuses the full lifespan unless DB/Redis are loopback on non-operational ports, or `EIMS_ALLOW_OPERATIONAL_FIXTURE=1` |
| `tests/conftest.py` | `client` fixture delegates to the shared guard before `TestClient(app)` |
| `tests/test_auth_modes.py` | guard added at both `TestClient(app)` sites |
| `tests/test_analyzer_investigation.py` | guard added |
| `tests/test_analyzer_reliability.py` | guard added |
| `tests/test_analyzer_integration_stability.py` | guard added — **this fourth file was not in the reviewer's list; the new wiring test found it** |
| `tests/test_fixture_isolation_contract.py` | **New** 7-check regression suite, including a wiring test and a repo-wide "every `TestClient(app)` is guarded" test |

## 2. Reproduction before the fix

One client-fixture test (`test_timeline_returns_unified_events_ordered`) with default settings:

```
Connecting to Postgres Relational Pool at: localhost:5432
SQLAlchemy Asynchronous Database Engine connected successfully to PgBouncer target.
Connecting to Redis Telemetry Broker at: localhost:6379
Async Redis Telemetry Broker connection established successfully.
Seeding admin bootstrap account...
Telemetry consumer-group worker started
Incident ingest consumer started
Subscribed to Redis PubSub channel: eims:events:alerts
1 passed
```

This is a live operational connection from a unit test. It is the definitive confirmation of F1.

**Disclosure:** the run had real side effects on the live stack — a failed admin seed `SELECT`, a created Redis consumer group and pub/sub subscription, and incident rows read but left pending. The user should inspect the operational PostgreSQL/Redis.

## 3. Regression evidence after the fix

| Check | Command | Result |
|---|---|---|
| Contract suite | `pytest tests/test_fixture_isolation_contract.py -q` | **7 passed / 0 failed** |
| Wrapper test file | `pytest tests/test_auth_modes.py -q` | **2 passed / 2 skipped**, **0** Redis connection attempts |
| Same timeline test | `pytest tests/test_timeline.py::test_timeline_returns_unified_events_ordered -q` | **1 skipped**, **0** Redis connection attempts |

The guard now runs before the lifespan in every file that constructs `TestClient(app)`.

## 4. Post-remediation independent review

Reviewer: Claude Code 2.1.323, plan mode, read-only, on this workspace diff.
Verdict: **ACCEPT_WITH_FINDINGS**.

| ID | Sev | Finding | Handling |
|---|---|---|---|
| R1 | **HIGH** | Three direct `TestClient(app)` call sites bypassed the guard; F1 was not closed | **fixed** — shared guard applied to all sites; the wiring test found a fourth |
| R2 | MED | port check is a denylist, not an allowlist | open — documented residual |
| R3 | MED | skipping can hide coverage loss | open — deliberate fail-closed choice |
| R4 | MED | escape hatch is silent and not refused under CI | open |
| R5 | MED | wiring was unprotected by tests | **fixed** — wiring + repo-wide guard tests |
| R6 | LOW | test edge cases thin | partially addressed (127.0.0.1 added) |
| R7 | LOW | object-store endpoint not checked | open |
| R8 | LOW | skip message named the wrong env variables | **fixed** (`EIMS_DB_PORT` / `EIMS_REDIS_PORT`) |
| R9 | LOW | two isolation policies exist | open |

## 5. Not fixed

- **F2** (`AUTH_MODE` demo default): the production boot guard exists; no code change made.
- **F3** (compose credentials/public bucket/ports): hardening changes `tests/test_compose_security_audit.py`, which currently asserts the known insecure state. Needs controller approval.
- **F4** (audit tamper evidence): no trigger/hash chain exists. Either implement an additive, reversible migration and verify it on a disposable DB, or withdraw the claim.
- **F5** (ledger head): the ledger is historical and must not be edited; the correct head is documented here as `c4e8a1f7b932`.
- **F6** (vector dimension): proving the failure needs a populated pgvector database; no container was started.

## 6. Residual risk

1. Any non-default loopback port is trusted; a tunnel to production would pass the guard.
2. Skipping rather than failing can hide coverage loss.
3. The escape hatch is silent.
4. Object-store and vector-DB endpoints are not covered.
5. F2–F6 remain open.

## 7. Source drift

The live EIMS repository was not modified. All changes exist only in the remediation workspace. No commit, push or merge was performed. A11 manifests and evidence are byte-unchanged.
