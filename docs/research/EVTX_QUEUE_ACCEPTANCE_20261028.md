# EIMS EVTX Queue Acceptance — 2026-10-28 (synthetic-only)

## Proven scope and branch separation

Stacked Draft PR #7 is based on PR #6 head `28c5e5f97de3791be73cfd4449da2742efea3460`; PR #6 is based on PR #5 `f777e9c5c085e1db366b410f0ea07ed6d2a82472`. No changes to main, production, MinIO/Redis sockets, USB, remote computers, credentials, or customer data.

**R5 producer fault (source-confirmed):** The prior `upload_windows_evtx` called `broker.cache_manager.redis.lpush`, although `RedisTelemetryStreamBroker` has `_cache`, not `cache_manager`, and the stub broker has neither property. A MinIO upload could succeed before an AttributeError. The route now injects `AsynchronousCacheManager` and calls its existing `lpush_queue("eims:jobs:evtx", payload)`. HTTP 202 is emitted only after a positive integer Redis LPUSH result. Queue errors and unconfirmed writes return 503 with Retry-After, without exposing the exception message. Storage errors remain 502, and queue is not attempted.

**What tests can prove:** Synthetic mocks verify confirmed queue acceptance, failed Redis LPUSH, unconfirmed return (0/None), and storage fault. CI is a hermetic source-level contract, not a Redis 7/MinIO integration test or end-to-end EVTX parsing proof. The workflow also runs the pre-existing telemetry and Compose checks.

**R6 consumer loss (still OPEN):** `backend/domain/telemetry/evtx_worker.py::_process_pending_tasks` uses destructive `RPOP` before reading/parsing/publishing events. A crash after pop, malformed job, MinIO read failure, partial publication, or swallowed exception can lose work without replay. The Redis list is a distinct path from `eims:telemetry:ingestion` Streams, so PR #6's stream tests do **not** establish EVTX worker recovery.

**R7 cross-store non-atomicity (still OPEN):** MinIO upload and Redis LPUSH are separate operations. If LPUSH fails, an orphaned object can remain. If LPUSH succeeded but the response was lost, a retry can create another object/job. Do not auto-delete the object on ambiguous Redis outcomes: deletion could remove data referenced by a committed queue entry. A future solution needs idempotency keys, an explicit object lifecycle/GC policy, and a tested reconciliation path. This PR does not claim at-most-once or exactly-once.

## Recommended next experiment (no production)

1. Decide whether EVTX jobs should remain a Redis list or move to a consumer-group stream. Do not conflate this with telemetry metric Streams.
2. In isolated synthetic Redis 7/MinIO/SQL, inject crash before/after job claim, malformed job, missing object, partial `publish_winlog`, and Redis reconnect. Capture queue depth, processing age, retries and durable result IDs.
3. For lists, Redis documents `LMOVE`/ `BLMOVE` to atomically transfer a job into a processing list; remove it with `LREM` only after durable success, and reclaim stale entries with a bounded lease/retry policy. This still requires idempotency and poison-job handling. Reference: https://redis.io/docs/latest/commands/lmove/
4. For streams, use `XREADGROUP`, `XPENDING` and `XAUTOCLAIM` with stable job IDs and a durable idempotency boundary. Reference: https://redis.io/docs/latest/develop/data-types/streams/
5. Establish a bounded orphan object reconciliation policy before enabling retry at scale; do not silently delete customer objects.
6. Review upload authorization and size/type limits separately; filename/MIME checks are not evidence of binary EVTX validation.

## Existing work retained (do not repeat)

- PR #6 has XADD fail-closed and SQL unavailable no-ACK fixes; two strict XFAIL contracts remain for stream replay/ACK.
- PR #6 already has a read-only Compose security scanner; development Compose is not secure deployment.
- Observability and device integration evidence remain source-level only in `docs/research/TELEMETRY_INFRA_AUDIT_20261026.md`.
- PR #5's Analyzer Human Gold review remains human-only, unrelated to this patch.

**Status gate:** Keep PR #7 Draft until exact-head CI is successful; keep PR #6 Draft until Redis recovery/idempotency and secure deployment evidence are independently verified.
