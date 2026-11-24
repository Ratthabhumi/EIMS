# EIMS V12 — A12 Finding Register (Reconciled)

Date: 2026-11-18 (Asia/Bangkok)
Machine-readable: `evidence/v12-a12-finding-register.json`
Source of truth: `evidence/v12-independent-review-findings.json` + the raw reviewer transcript.

## 1. Reconciliation result

| Source | Rows | CRITICAL | HIGH | MEDIUM | LOW | INFO |
|---|---:|---:|---:|---:|---:|---:|
| Raw reviewer transcript | 20 | 0 | 4 | 7 | 8 | 1 |
| `v12-independent-review-findings.json` | 20 | 0 | 4 | 7 | 8 | 1 |
| Reviewer self-summary line | — | 0 | 4 | 7 | 8 | 1 |
| Resolved | 20 | 0 | **4** | **7** | **8** | **1** |

EIMS has no count discrepancy. The A11 report's wording was still imprecise: it said "4 of 4 verified" under a table that listed **six** rows. F1–F4 are HIGH; **F5 and F6 are MEDIUM** and were also verified. Correct statement: 4 HIGH verified + 2 MEDIUM verified; F6 reproduction is static only.

No severity was changed by OpenCode.

## 2. Finding status

| ID | Sev | Area | Reproduction | Remediation | Blocks |
|---|---|---|---|---|---|
| F1 | HIGH | Test isolation / full lifespan | **REPRODUCED** (connected to operational PG+Redis) | **FIXED_IN_WORKSPACE** | PARTIAL |
| F2 | HIGH | `AUTH_MODE` default demo | CODE_PATH_PROVEN | OPEN | CONDITIONAL |
| F3 | HIGH | Compose credentials / public bucket / ports | CODE_PATH_PROVEN | **NEEDS_DESIGN_DECISION** | YES for compose use |
| F4 | HIGH | Audit "immutable" without tamper evidence | CODE_PATH_PROVEN (0 triggers) | **NEEDS_DESIGN_DECISION** | YES for tamper claim |
| F5 | MED | Ledger head stale | **REPRODUCED** | DOCUMENTED | YES as evidence claim |
| F6 | MED | `vector(768)→vector(384)` cast | CODE_PATH_PROVEN | **NEEDS_SERVICE** | YES for vector function |
| F7–F15, F17–F19 | MED/LOW | ingest, dedupe, idempotency, search, auth, scripts | NOT_REPRODUCED | NOT_ADDRESSED | NO |
| F16 | LOW | `scratch_append_tests.py` mutates tests | CONFIRMED | DOCUMENTED | NO |
| F20 | INFO | positive findings | ACCEPTED | NONE | NO |

## 3. Reproduction evidence

| ID | Method | Result |
|---|---|---|
| F1 | One client-fixture test with default settings | Logged `Connecting to Postgres ... localhost:5432`, `connected successfully`, `Connecting to Redis ... localhost:6379`, `connection established`, `Seeding admin bootstrap account`, `Telemetry consumer-group worker started`, `Incident ingest consumer started`, `Subscribed to Redis PubSub channel: eims:events:alerts`. The test passed. **This is direct proof that a unit test reached the operational stack.** |
| F5 | Chain computation over `migrations/versions/*.py` | 22 revisions, 1 root `1a78de93777d`, 1 head **`c4e8a1f7b932`**; `a3d6f1e8c295` is six revisions behind the head |
| F6 | Source read | `migrations/versions/8a2b4d6f9c1e…py:19-36` casts 768→384 directly; proving the failure needs a populated pgvector DB |

## 4. Operational side effect to disclose

The F1 reproduction was a real test execution and it **did** reach the live stack. Observed effects: an admin seed `SELECT` failed on a schema mismatch (no write), a Redis consumer group and pub/sub subscription were created, and the incident dispatcher read pending rows but its dispatch failed, leaving them pending. No deletion was observed. The user should inspect the operational PostgreSQL/Redis for those two jobs' side effects.

No finding was closed by changing severity, and no historical evidence was edited.
