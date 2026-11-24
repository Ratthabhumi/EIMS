# EIMS V12 — A13.1 Operational Side-Effect Impact Assessment

Date: 2026-11-18 (Asia/Bangkok)
Mode: **READ-ONLY.** No ACK, DEL, XACK, XDEL, FLUSH, UPDATE, DELETE, replay, restart, or cleanup was performed.
Machine-readable: `evidence/v12-a13-operational-impact.json`

## 1. Incident under assessment

| Item | Value |
|---|---|
| Event | One EIMS unit test was executed from the A12 remediation workspace and reached a live stack |
| Local time | 2026-11-18 21:23:51–21:23:52 (+07) |
| UTC | 2026-11-18 14:23:51–14:23:52 |
| Command | `pytest tests/test_timeline.py::test_timeline_returns_unified_events_ordered -q -s -p no:cacheprovider -o addopts=""` |
| Working directory | `%TEMP%\v12-a12\EIMS` |
| Interpreter | `C:\Users\MewMew\Desktop\Co-op\EIMS\venv\Scripts\python.exe` |
| Test result | 1 passed |
| Disposable markers set | **none** (`EIMS_TEST_*` absent) |
| Settings used | defaults: DB `localhost:5432`, Redis `localhost:6379` |

The command was launched as an intentional reproduction of EIMS-F1. It was not a disposable environment.

## 2. Destination identity (verified, not assumed)

| Service | Container | Image | Version | Endpoint | Identity |
|---|---|---|---|---|---|
| PostgreSQL | `eims-postgres` | `pgvector/pgvector:pg16` | PostgreSQL 16.14 | `0.0.0.0:5432` | DB `eims_registry`, user `eims_user`, alembic `a3d6f1e8c295` |
| Redis | `eims-redis` | `redis:7-alpine` | Redis 7.4.10 | `0.0.0.0:6379` | db 0, `DBSIZE=3` |
| MinIO | `eims-minio` | `minio/minio:latest` | running | `0.0.0.0:9000` | buckets `eims-integration-test`, `eims-ocr-manifests` |

The full operational stack is running: `eims-postgres`, `eims-redis`, `eims-minio`, `eims-pgbouncer`, `eims-prometheus`, `eims-loki`, `eims-grafana` (all started 2026-11-18T11:33:03Z).

Both containers are **running** with `restart=unless-stopped`, started 2026-11-18T11:33:03Z. They are **not** the disposable acceptance containers, all of which are still `exited (255)` on ports 56441/56379/59000/56460/56461.

No credentials are reproduced in this document.

## 3. PostgreSQL impact — no data mutation found

All queries ran under `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY`.

| Check | Result | Interpretation |
|---|---|---|
| `alembic_version` | `a3d6f1e8c295` | deployed schema is 6 revisions behind repo head `c4e8a1f7b932` |
| `users` columns | `id, username, password, role` | **no `knowledge_reviewer` column** |
| `users` rows | 1 (`admin`) | unchanged; seed `SELECT` failed before any write |
| `telemetry_alert_outbox` rows | **0** | no pending outbox state |
| `audit_logs` rows | 7 | newest `2026-10-08 18:23:31Z` |
| `audit_logs` in 14:20–14:30Z | **0** | no audit row written by the test |
| `windows_event_logs` / `telemetry_metrics` | queried successfully, no errors | reachable, untouched |

The startup log showed `column users.knowledge_reviewer does not exist`, which aborts the seed `SELECT` before any insert. **No admin row was created or modified.**

The incident dispatcher logged `ProgrammingError; rows remain pending`, but the operational DB has **no incident/outbox table** for that path and the outbox is empty, so nothing was enqueued.

## 4. Redis impact — metadata only, no pending messages

| Check | Result |
|---|---|
| `DBSIZE` | 3 |
| Keys | `eims:telemetry:ingestion`, `eims:jobs:incident-ingest:stream`, `eims:jobs:evtx:stream` |
| Stream lengths | **0 / 0 / 0** |
| Dead-letter stream | absent |
| Consumer group `eims:telemetry:consumer` | exists; consumers 0; pending 0; `last-delivered-id 0-0` |
| Consumer group `eims:jobs:incident-ingest:workers` | exists; **1 consumer** `eims-ingest-3e6706224155`; pending 0; idle ≈ 5,896,584 ms |
| Consumer group `eims:jobs:evtx:workers` | exists; **1 consumer** `evtx-8f7ca049cdc8`; pending 0; idle ≈ 5,896,865 ms |
| Pub/Sub channels now | none (`PUBSUB CHANNELS *` empty, `NUMSUB eims:events:alerts` = 0) |

The two consumer entries have been idle for ~98 minutes, which matches the test timestamp exactly (21:23 vs 23:02). They were created by the test's worker startup.

**No message was consumed, acknowledged, or left pending.** The only durable mutation is the creation of consumer groups and two consumer identities.

## 5. MinIO impact — no object written

| Check | Result |
|---|---|
| Buckets | `eims-integration-test`, `eims-ocr-manifests` |
| Files modified in the last 3 hours under `/data` | **none** |

The OCR worker starts at lifespan but wrote nothing during the test. No object-store mutation found.

## 6. Process state

| Check | Result |
|---|---|
| Test process | exited (1 passed) |
| Orphan `pytest` process | none (the only match was the inspection shell itself) |
| Operational EIMS backend (`uvicorn`/`backend.main`) | not running |
| Leftover pub/sub subscriber | none |

## 7. Summary of side effects

| Class | Finding |
|---|---|
| Data loss | **none found** |
| Data mutation (rows) | **none found** |
| Redis message loss / pending | **none** |
| Durable metadata created | **3 consumer groups + 2 consumer identities** |
| Audit contamination | **none** (0 rows in the window) |
| Running processes left behind | **none** |
| Containers/volumes changed | **none** (no start/stop/recreate) |

## 8. What could not be verified

- Whether the `eims:telemetry:consumer` group existed **before** this run. Its `last-delivered-id 0-0` and zero consumers are consistent with either.
- PostgreSQL WAL / statement log: no access without superuser tooling; the row counts and column error are strong but indirect evidence of zero writes.
- Redis AOF/RDB history: not inspected.
- Whether another local process (not started by the test) subscribed to `eims:events:alerts` transiently.

These remain **UNVERIFIED**, not assumed clean.

## 9. Root cause of the incident

`Disposable workspace ≠ disposable environment.` The A12 workspace contained the source, but the process still inherited the operational defaults `localhost:5432` / `localhost:6379`. The guard added in A12 was not yet present in the snapshot at the moment of the run, and it was only a port denylist anyway.

## 10. Recommended owner actions

1. **No cleanup is required for correctness.** All streams are empty and no row was written.
2. If the leftover consumer identities are undesirable, they can later be removed with `XGROUP DELCONSUMER` / `XGROUP DESTROY` — **under explicit approval and only after this assessment is accepted.** Do not do it now.
3. Do **not** apply repository migrations to `eims_registry`; it is 6 revisions behind by design of the current deployment.
4. Note for EIMS-F5: the ledger head `a3d6f1e8c295` matches this **deployed** database, which explains the apparent mismatch against the repository head `c4e8a1f7b932`. The ledger is a deployment record that was read as a repository record.

## 11. Verdict

**CONTAINED — no data loss, no pending work, metadata-only residue.**
The incident is real and must stay recorded, but it does not require emergency cleanup. A13.2 (test isolation) remains mandatory before any further test execution.
