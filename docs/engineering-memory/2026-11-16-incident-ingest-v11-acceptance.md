# EIMS Engineering Memory — 2026-11-16 Incident Ingestion v1.1 Acceptance

## Status

**COMPLETE (code + unit + migration + isolated DB/Redis + independent review).**
No commit/push. No operational database, Redis, MinIO, credential or listener was touched.

- Branch `integration/eims-consolidated`, HEAD `85493b2131d3e353453072559a5dfc301d75dd06`.
- Alembic head: `c4e8a1f7b932` (single head, parent `b8d3f5c1a720`).

## Root causes fixed in this pass

1. **Focused unit suite had never been run.** Three failures were stale test doubles:
   `_persist_event` stubs did not accept the new `fallback_time` kwarg (F7 change), and one
   fixture passed `severity_level` where the offline report contract uses `severity`.
   Fixed in the tests, not by weakening production behaviour.
2. **Migration test inserted `infrastructure_assets` without the four NOT NULL columns**
   (`lifecycle_state`, `current_compliance_score`, `created_at`, `updated_at`), so the
   populated-parent upgrade test failed on a real database. Test fixed.
3. **Outbox insert swallowed every error** (review M1). Now only a missing table
   (SQLSTATE 42P01) is tolerated; any other database error fails the source transaction so
   evidence and intent retry together.
4. **One unbounded multi-row INSERT** (review M2). Rows are chunked at 500
   (`MAX_ROWS_PER_INSERT`), well below asyncpg's 32767-parameter limit.
5. **Atomicity wording** in `models.py`/`consumer.py`/`outbox.py` now states the guarantee
   precisely instead of implying cross-transaction atomicity.

## Verification

| Gate | Result |
|---|---|
| Focused unit + recovery unit | **95 passed, 0 failed, 0 skipped**, exit 0 (`.omc/evidence/v11-recovery-unit-junit.xml`) |
| Unit + migration + PostgreSQL/Redis integration | **113 passed, 0 failed, 0 skipped**, exit 0, 28.6 s (`.omc/evidence/v11-ingest-full-junit.xml`, sha256 `a70109a22c326f6a…`) |
| Migration upgrade → downgrade → re-upgrade on empty and populated parent | PASS on the disposable database |
| Incident correlation regression (`tests/test_incident_correlation.py`) | PASS, exit 0 |
| `git diff --check` | exit 0 (CRLF warnings only) |
| Independent read-only review (Claude Code, 3 rounds) | round 1 no HIGH, 2 MEDIUM; round 2 NOT ACCEPTED (test gap); round 3 **ACCEPTED** |

## Isolated infrastructure

- PostgreSQL `eims-ingest-v11-pg-20261116c` on `127.0.0.1:56460`, database
  `eims_ingest_v11_test`, role `eims_ingest_v11_app` verified **NONSUPERUSER** (`rolsuper=f`),
  database comment sentinel `EIMS-DISPOSABLE-INGEST-V11:<random>` verified by the test gate.
- Redis `eims-ingest-v11-redis-20261116c` on `127.0.0.1:56461`, sentinel key
  `eims:disposable:incident-ingest-v11` verified before any write.
- Credentials were generated in-process and passed only through environment variables; they are
  not written to this file, the repo, or any artifact.
- Containers were created by this task and left running (volumes retained). No existing
  container, volume or schema was reused or deleted.

## Independent review outcome

- Round 1: no HIGH. MEDIUM: swallowed outbox errors; unbounded multi-row insert.
  LOW: reclaim counts as a delivery attempt; atomicity wording; log flooding / capped drain.
- Round 2: **NOT ACCEPTED** — fixes were correct but untested; the reviewer required a
  non-42P01 re-raise test and a chunking test.
- Round 3: **ACCEPTED** after both tests were added and 113 tests passed.

## Deferred (documented, not fixed)

| Finding | Reason |
|---|---|
| XAUTOCLAIM reclaim increments the delivery count (LOW) | Intentional Redis semantics; a long DB outage can push an entry to the poison cap. Operational, not silent data loss. |
| Error-log flood + ~20 entries/s drain when Redis is down (LOW) | Backpressure only; no correctness impact. Follow-up: skip the sleep when a batch was full. |
| F8 offline import duplicate race | Pre-existing read-then-insert dedupe; `windows_event_logs` has no unique constraint on the metadata key. A uniqueness constraint would change identity semantics; not added. Residual risk documented. |
| F10 asset FK `ON DELETE RESTRICT` | Outbox rows block asset deletion until dispatched. No automatic pruning by design. |

## Deployment prerequisite

Apply `c4e8a1f7b932` **before** deploying code that writes to `incident_ingest_outbox`. If the
table is missing, ingestion still succeeds and the intent is logged/counted but not recorded
(operator re-emission required).

## Not changed

Incident Core v1 semantics (correlation, dedupe, terminal-incident protection, evidence
idempotency), `audit_logs`, telemetry alert PubSub, dashboards, Knowledge, and any unrelated
worktree file.
