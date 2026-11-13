# EIMS EVTX worker fault boundary — 2026-10-29

## Scope and provenance

Draft PR #8 is stacked on PR #7 (`audit/evtx-queue-failclosed-20261028`), which is stacked on PR #6 and PR #5. The base is PR #7 commit `e6f248748a758111ba69f430388462d58d23d1c3`. The existing PR #6 Redis stream and Compose work and PR #7 EVTX producer fix are not reimplemented. No changes to `main`, running infrastructure, devices, USB, credentials, operational data, or Human Gold labels.

## Implemented, bounded security correction

`backend/domain/telemetry/evtx_worker.py::_process_pending_tasks` previously interpolated raw untrusted Redis-list bytes into the malformed-JSON log and interpolated the full decoded task object into the missing-`minio_uri` log. Those strings can include unexpected sensitive content. Both failure logs now use static messages. Hermetic tests in `tests/test_evtx_worker_fault_contracts.py` use synthetic marker strings and require them to be absent from captured ERROR logs. The empty-queue test ensures no storage read or event publication.

**Boundary:** This is log minimization for two known error paths, not a comprehensive audit of all telemetry logging. The worker still logs URI/job identifiers on other paths; those may need a separately approved structured logging and retention policy. Malformed and missing-URI tasks are still discarded without DLQ, as explicitly stated in the logs.

## Unresolved, executable fault contracts

Two `xfail(strict=True)` tests are deliberately unresolved:

1. **MinIO outage after RPOP:** the EVTX job is already removed from `eims:jobs:evtx` when the object read fails; the worker catches the exception without a durable retry or processing list.
2. **Partial winlog publication:** one event may be accepted by the stream before a later publication fails. The worker catches the exception after destructive RPOP; a retry would also require stable event IDs or deduplication to avoid duplicates.

These are hermetic fault injections using fake Redis list, fake MinIO client, and a mocked broker; they do not prove crash recovery, Redis persistence, MinIO interoperability, exactly-once delivery, or end-to-end EVTX correctness. A future strict XPASS is a signal to review the contract, not permission to deploy.

## Additional stream protocol finding (source-level, not runtime-verified)

`RedisTelemetryStreamBroker.fetch_stream_batch` and `TelemetryStreamConsumer._fetch_batch` use `XREAD` with an in-memory cursor. Meanwhile `RedisTelemetryStreamBroker.ack_stream_messages` invokes `XACK` against a named consumer group, catches exceptions, and does not validate the acknowledged count. Redis documents that `XACK` removes messages from a **consumer group's pending entries list**, which is populated by `XREADGROUP`, not ordinary `XREAD`. Therefore, the existing source does not establish real consumer-group pending recovery or acknowledged durability. The worker's `XTRIM MINID` is not a substitute for a pending-entry recovery policy. Do **not** fix this by merely propagating the current `XACK` error: first design and test the full consumer-group migration, pending reclaim, SQL stream-ID idempotency, and safe retention boundaries.

References:
- https://redis.io/docs/latest/commands/xreadgroup/
- https://redis.io/docs/latest/commands/xack/
- https://redis.io/docs/latest/commands/lmove/

## Existing infrastructure/security evidence reused

- **Dev vs secure Compose:** PR #6 already includes `tools/audit_compose_security.py` with dev inventory and secure-mode high-finding rejection. This is static, not a deployed secure profile or a container vulnerability assessment.
- **Observability:** `/metrics` and Prometheus configuration exist, but no verified target-UP, Loki shipping, Grafana datasource/dashboard, or alerting end-to-end evidence.
- **Device capability:** Windows heartbeat and EVTX code exist, but live collection remains unverified; Fortinet/Cisco/VMware/Veeam are offline analyzer parser coverage, not demonstrated live device control; NAS/UPS/SNMP remain unverified.
- Authoritative prior evidence: `docs/research/TELEMETRY_INFRA_AUDIT_20261026.md` and `docs/research/EVTX_QUEUE_ACCEPTANCE_20261028.md`. No invented runtime certification.

## Next highest-value bounded experiment

In an isolated, explicitly authorized synthetic Redis/PostgreSQL/MinIO environment, decide EVTX queue semantics (LMOVE processing list + stale lease or consumer-group stream), implement crash-window recovery and bounded poison-job/DLQ policy, and use stable event IDs for partial-publish idempotency. Separately, design Redis telemetry `XREADGROUP` + `XPENDING`/`XAUTOCLAIM` + SQL stream-ID unique constraint before changing ACK/trim semantics. Keep all PRs Draft and do not merge/deploy without exact-head CI and review.
