# EIMS Telemetry / Infrastructure Reliability Audit — 2026-10-26

> Scope: source-level review at PR #5 `f777e9c5c085e1db366b410f0ea07ed6d2a82472`, plus focused new PR #6. GitHub source and isolated CI only. No production runtime, device, USB, cloud deployment or credentials accessed. The graduation Analyzer Gold evaluation is a separate workstream.

## Verified implementation versus runtime claims

| Subsystem | Verified code/config | Not established by this audit |
| --- | --- | --- |
| FastAPI / Next.js | Backend routes and /metrics instrumentation; Next.js dashboard source and build CI | HTTPS browser acceptance on installed system |
| PostgreSQL / pgvector / PgBouncer | Dev Compose services, SQLAlchemy/Alembic, separate integration CI | Production migration, backup recovery |
| Redis | `redis.asyncio`, `XADD` producer, `XREAD` worker, cache/stream namespaces | Crash-safe stream delivery, exactly-once, restart recovery |
| MinIO | OCR/object-store code and Compose service | Private-by-default deployed policies |
| Prometheus | `Instrumentator().instrument(app).expose(app)`, scrape config for FastAPI | Live scrape target UP and representative metric series |
| Grafana and Loki | Docker Compose services declared | Loki shipping pipeline, dashboards, alerts or verified end-to-end ingestion |
| Homelab | Separate IaC, Traefik, VictoriaMetrics, Uptime Kuma, backup runbook | That this stack is the deployed EIMS instance |
| Agents/devices | Agent fingerprint/heartbeat, Windows EVTX, USB auditor, OCR clients | End-to-end physical device interoperability (NAS, firewall, switch, UPS) |

## Confirmed source-level reliability risks

**R1 — False ingestion acknowledgment (critical).** `RedisTelemetryStreamBroker._publish_to_stream` returns `status=accepted` and a fabricated `fallback-...` identifier after no Redis client or failed `XADD`, with no demonstrated durable write. Production must return a retryable failure (503) until a real durable fallback exists. A successful `XADD` response must return its real stream ID. Note that an ambiguous network timeout after `XADD` may result in duplicate retries; this contract alone does not imply exactly-once behavior.

**R2 — Unavailable persistence (critical).** `TelemetryStreamConsumer.process_batch` proceeds to acknowledge/trim a non-stub Redis batch even if `database_engine.get_session_maker()` is unavailable. The processor must refuse to advance/acknowledge without verified durable SQL persistence. Stub-mode tests are not production SQL durability evidence.

**R3 — Stream replay and acknowledgment semantics (high; architecture decision pending).** Production uses `XREAD` with in-memory `_last_id = '0-0'` and also calls `XACK`, which requires entries pending in a Redis consumer group. Restart can replay previously persisted messages; cursor or trimming can discard unprocessed entries. Current documentation's `exactly once` wording is unsupported. Migrate with care to `XREADGROUP` + recovery of pending work and database-level idempotency, or explicitly implement a durable cursor protocol; never claim exactly-once solely from `XACK`.

**R4 — Data retention and loss modes (high).** The producer sets approximate `MAXLEN=100000`, and the worker calls `XTRIM MINID`. Under backlog, a fixed limit can remove unconsumed entries. At Redis memory limit, `volatile-lru` applies only to eligible volatile keys; it does not guarantee event-stream retention. Add backlog/trim monitoring and fault-injection proving the chosen loss policy.

## Dev Compose security findings — proposal only

`docker-compose.yml` visibly declares development credentials for PostgreSQL/PgBouncer/MinIO/Grafana, host-published service ports, floating `:latest` images, and `mc anonymous set public` for an OCR bucket.

This is **not evidence of public production exposure**. It **must not** be adopted unchanged as a secure environment.

Suggested separate Secure profile (not deployed in this PR):

1. Omit direct host publications for Postgres, PgBouncer, Redis, MinIO API/console, Loki and Prometheus by default; use internal-only networks, or loopback bindings for authorized local administration.
2. Replace dev passwords and admin bootstrap credentials with external secrets/environment injection (with preflight validation and no secrets committed).
3. Keep S3/OCR bucket private by default; enable scoped presigned access only where required, with explicit authorization.
4. Pin images by tested versions or digests and record vulnerability scan results; do not automatically upgrade a working demo stack.
5. Enable Redis ACLs, scoped key permissions, TLS where crossing trust boundaries, memory/persistence/backlog alarms, and verify connection behavior.
6. Protect Prometheus/Grafana and /metrics; document log/metric sensitive-data policy.
7. Create a secure Compose config checker in CI *before* allowing a secure profile to ship. Do not alter running services with these findings.

## Observability acceptance matrix

| Probe | Code/config present | Runtime verification |
| --- | --- | --- |
| HTTP /metrics | Yes | NOT_TESTED on installed target |
| FastAPI scrape target | Configured via host.docker.internal:8000 | NOT_TESTED; host address platform dependent |
| Prometheus target availability | Prometheus service declared | NOT_TESTED |
| Grafana EIMS dashboard provisioned | Not established | NOT_TESTED |
| Loki ingest from EIMS log shipper | No shipper/provisioning confirmed in inspected tree | NOT_TESTED |
| Redis XADD errors / response 503 | Fault injection in new PR | Awaiting CI |
| Redis consumer group lag/pending | Not implemented in current worker | NOT_MEASURED |
| Redis maxmemory and persistence RPO | Compose configuration exists | NOT_TESTED |
| Backup restore of PostgreSQL/MinIO | General homelab tar backup script, not an EIMS DB restore proof | NOT_TESTED |

## Device integration evidence matrix

| Device or pathway | Evidence category | Clarification |
| --- | --- | --- |
| Windows event/log telemetry | Implemented code + stub tests | Physical collector and mTLS deployment NOT_TESTED |
| Custom agent heartbeat / enrollment | Implemented code + stub tests | No certified multi-device deployment |
| Windows USB auditor | Implemented client/test files | No physical USB access this audit |
| Sticker OCR / MinIO | Implemented client and backend | Actual camera/device and object-storage permissions NOT_TESTED |
| Firewall (Fortinet), VMware, Veeam, Cisco log files | Analyzer parser knowledge | File analysis does NOT imply live management APIs |
| Network switches / NAS / UPS | Documentation/general asset model; no device-specific integration demonstrated in inspected paths | Mark NOT_VERIFIED; do not advertise control/telemetry integration |
| Network topology | Project documents and UI elements | Live discovery/topology synchronization NOT_VERIFIED |

## Proposed follow-up reliability experiment

Use a dedicated synthetic Redis 7 and PostgreSQL 16 container in authorized CI, *not* a production service. Inject:

- Redis unavailable / `XADD` timeout / broken pipe.
- PostgreSQL unavailable, transaction rollback and reconnect.
- Consumer crash before SQL commit and after commit but before acknowledgment.
- Concurrent workers, stuck pending entries and recovery.
- Replayed stream IDs and duplicate-key idempotency behavior.
- MAXLEN trim with a slow consumer and restart.
- Poison messages with explicit dead-letter/reject handling.
- Backpressure and health/metrics during sustained ingestion.

Acceptance: no accepted event without known queue persistence, no successful acknowledgment before durable database commit, no silent truncation under the documented delivery guarantee, and explicit at-least-once versus exactly-once semantics supported by tests.

Source references:
- Redis XREAD: https://redis.io/docs/latest/commands/xread/
- Redis XREADGROUP: https://redis.io/docs/latest/commands/xreadgroup/
- Redis XPENDING: https://redis.io/docs/latest/commands/xpending/
- Redis XTRIM: https://redis.io/docs/latest/commands/xtrim/
- Redis ACL: https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/
- Docker port publishing: https://docs.docker.com/get-started/docker-concepts/running-containers/publishing-ports/

## Graduation project scope

The Analyzer and Human Gold evaluation remain the primary academic work. Redis safety issues should be addressed via focused regression PRs without replacing the EIMS stack or deploying a new cloud. No Gold annotations or research baselines are modified here.

## Continuation — 2026-10-27 (source audit, no deployment)

### New isolated verification

- `tests/test_telemetry_recovery_contracts.py` adds one synthetic SQL-rollback/restart test and two `xfail(strict=True)` contracts: replay after SQL commit before ACK, and ACK failure swallowed by the current worker. **Expected failures are unresolved risks, not green reliability guarantees.** A strict XPASS should break CI and prompt review.
- `tools/audit_compose_security.py` adds a deterministic, secret-redacted static report. `--mode dev` returns success with findings, so it does not break the existing development stack; `--mode secure` fails on high-severity findings for a future approved profile. `tests/test_compose_security_audit.py` covers actual dev risk signatures, a synthetic safe pattern, and no secret-value leakage.
- The existing telemetry CI job runs these hermetic tests and emits `test-results/compose-security.json`. This is a **static inventory**, not a Docker vulnerability scan or deployment verification.
- Previously verified PR #6 RED→GREEN run at `2ed4bb5e6fc7b312c389477ceb9e481398a7d848`: https://github.com/Ratthabhumi/EIMS/actions/runs/40263364146 (4/4 jobs). Subsequent changes require their own exact-head CI check.

### Additional source-level integration risk

**R5 — EVTX binary upload queueing (high, NOT runtime tested).** `backend/domain/telemetry/controller.py::upload_windows_evtx` writes a file to MinIO, then accesses `broker.cache_manager.redis.lpush(...)`. `RedisTelemetryStreamBroker` defines `self._cache`, not `cache_manager`; `StubTelemetryStreamBroker` does not expose this property either. This appears to raise `AttributeError` after object upload rather than returning a queued task ID. Even after correcting the property, object-store write plus Redis queue write are not atomic: failed queueing can leave orphaned objects. This needs a separate test-first, fail-closed upload contract; do not claim physical EVTX ingestion passes.

### Observability configuration detail

`deployments/observability/prometheus.yml` scrapes `host.docker.internal:8000` for FastAPI and `localhost:9090` for Prometheus. The former hostname is environment-dependent and no runtime target-UP evidence exists. `backend/main.py` exposes `/metrics`, but no EIMS Loki shipper or Grafana datasource/dashboard provisioning was demonstrated in the inspected deployment configuration. Declaring three images in Compose is not end-to-end observability.

### Delivery semantics gate before production

1. Decide the explicit service-level guarantee (at-least-once with SQL deduplication is a pragmatic default) and define whether each accepted event survives crash, restart, and retention.
2. Use a synthetic Redis/PostgreSQL CI service to test `XREADGROUP` + pending reclaim (`XAUTOCLAIM` or equivalent), with a stable stream ID persisted under a unique constraint in the SQL transaction. Test both crash windows and concurrent workers.
3. Make poison-message policy explicit (retry count, DLQ, alerting, operator replay); do not silently `XTRIM` unprocessed entries.
4. Measure backlog, pending-age, trim loss, queue errors, Redis persistence lag, and SQL commit/ACK order before approving a secure profile.

**Authorization boundary:** all new checks here operate on repository text and synthetic CI only. No production data, running Docker, network equipment, physical USB, secret rotation, or cloud changes.
