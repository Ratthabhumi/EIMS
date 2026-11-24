# EIMS Engineering Memory — 2026-11-16 Incident Core v1.1 Architecture Trace

**Origin:** recovered from the read-only OpenCode plan job
`3ef58a7d-64eb-4fc6-9b3a-80c39a539953` (DWB control plane, project `eims`,
role `read_only`, finished 2026-11-16T06:05Z, exit 0).

**Status:** read-only architecture evidence. The job modified no file, queried no
database, ran no migration, executed no test and touched no service. Line
references reflect the worktree at capture time.

**Fidelity:** captured from a console stream. 65 byte sequences in the
capture were already unrecoverable (console decoding), shown as � below.
Substance was verified against the source files during this session's plan review;
re-check any line number before writing code.

**Use:** baseline for Incident Core v1.1 (Event-to-Incident Ingestion Integration).

---

# EIMS Incident Core v1.1  Read-Only Architecture Trace

**Mode compliance:** read-only. I read the mandatory contract files (INDEX + current snapshot, AI_TOOLING_INVENTORY, OPERATIONAL_HANDOFF, ACCEPTANCE_LEDGER), traced source files, and ran one read-only `git status --short` scoped to the relevant paths. **No file was modified, no DB queried, no migration run, no test executed, no service touched.** All line numbers below were verified against current worktree contents.

---

## 0. Baseline verification (repository, not DB)

- Migration graph is **linear, single head `b8d3f5c1a720`** at file level:
  `& e4a9c8b12d77 � f7b3d91c4a58 (outbox) � a3d6f1e8c295 � b7c2e9a4f601 � c9a4e7b2d610 � d1e5a7c9b204 � d2f6b8c1e305 � e5a7c9d2f416 � f3c8a1d6b902 � a4b7c9d2e601 � b8d3f5c1a720` (verified `revision`/`down_revision` in every `migrations/versions/*.py`).
- `git status` confirms the reported discrepancy: `migrations/versions/b8d3f5c1a720_add_incident_core.py` and `backend/domain/incident/` are **untracked (`??`)**; `backend/domain/telemetry/{worker,broker,models,evtx_worker,evtx_parser,controller,schemas}.py`, `backend/main.py`, `analyze.py`, `history.py`, `migrations/env.py` are **modified (`M`)**. All preserved.
- **DB state is unknown and was not queried.** The ledger records one disposable DB at `b8` (`eims-incident-core-pg-20261116`, port 56448) and another at `a4` (`eims-reviewer-source-nonsuper-pg-20261116`, port 56446); the user-reported `a4` head is a third, unverified claim. Design below chains from the **repository head `b8d3f5c1a720`** and assumes nothing about any live DB. Any future application must first verify `alembic current` on a positively identified disposable target.

---

## 1. Telemetry metrics ingestion  exact path

| Step | File / function | Lines | Facts |
|---|---|---|---|
| HTTP edge | `backend/domain/telemetry/controller.py` `ingest_agent_heartbeat` | 7689 | `POST /api/v1/telemetry/heartbeat`; router guarded by `require_admin_or_token` (L59) + `verify_mtls_fingerprint` (L79). Returns 202 after Redis XADD only. |
| Idempotency key | same file `_stable_ingestion_key` | 5055 | `"ingest:" + sha256(event_type \x1f cert_fingerprint.lower() \x1f canonical-json(payload))`  stable across HTTP retries. |
| Broker publish | `backend/domain/telemetry/broker.py` `RedisTelemetryStreamBroker._publish_to_stream` | 85111 | Envelope `{event_type, cert_fingerprint, payload, ingested_at, source_event_key}` � XADD `eims:telemetry:ingestion` (L16). Key length d160 enforced (L9394, L21). Never MAXLEN-trims (L100). Unconfirmed XADD � 503. |
| Consumer | `backend/domain/telemetry/worker.py` `TelemetryStreamConsumer.process_batch` | 216235 | Drains outbox first (L218), fetches via `fetch_stream_batch` (broker L121149: XAUTOCLAIM stale-pending e30 s, then XREADGROUP), starts lease-refresh task (L227; `_refresh_claim_loop` L183214 uses XCLAIM JUSTID  no delivery-count increment). |
| Validation + identity | `_process_fetched_batch` | 237320 | `source_event_key` fallback to stream id (L255); only `heartbeat`/`winlog` accepted (L259); **asset resolution** `_resolve_asset` L93113: in-memory resolver cache � `InfrastructureAsset.cryptographic_fingerprint` lookup (`asset_registry/models.py` L5763, unique). Unresolved � `UnresolvedAssetError` � **DLQ, never persisted, never fabricated** (L288290). DB unavailable � `DatabaseUnavailableError`, batch stays pending (L100103, L296297). |
| Row build | same | 269286 | `TelemetryMetric(metric_id=uuid4(), asset_id, event_time=heartbeat.timestamp, &, source_event_key)`; `WindowsEventLog(log_id=uuid4(), &, occurrence_time, event_id, severity_level, evtx_metadata, source_event_key)`. **PKs are fresh uuid4 per attempt**  critical for outbox design (�7). |
| **DB transaction T1** | `_persist_batch` | 368390 | One `session_maker()` + `session.begin()`: bulk insert metrics (L372378), bulk insert winlogs (L379385), `_detect_brute_force` (L386). `_insert_rows` L345348 = `pg_insert & on_conflict_do_nothing(index_elements=[source_event_key])`  **currently returns nothing**. |
| Poison isolation | `_persist_isolating` | 322343 | Only `IntegrityError`/`DataError` trigger recursive bisect; transient errors propagate � nothing ACKed/DLQ'd. |
| Quarantine + outbox write | `_detect_brute_force` | 392446 | Inside T1: asset rows locked `FOR UPDATE` sorted (L411415), durable per-(asset, src_ip) 60 s count (L351366, L423425, threshold >5), then `lifecycle_state="Quarantined"` + score 30 + `AuditLog(AUTOMATED_QUARANTINE_4625)` + **`TelemetryAlertOutbox` row in the same transaction** (L431444). |
| Commit � dispatch | `_persist_batch` tail | 387390 | Only after T1 commit: `_dispatch_outbox_safely` (L448456, never fails ingestion). |
| DLQ then ACK-last | `_process_fetched_batch` tail | 312320 | DLQ writes confirmed first (L313314), then `_ack_and_trim` (L516519 � broker `ack_stream_messages` L151164: XACK must equal count, XDEL best-effort). |
| Persistence models | `backend/domain/telemetry/models.py` | 3274, 77128 | `uq_telemetry_metrics_source_event_key` (L72), `uq_windows_event_logs_source_event_key` (L122), partial 4625 index (L124126). Both `asset_id` FKs are **NOT NULL, ON DELETE CASCADE**. `source_event_key` nullable (multiple NULLs allowed). |
| Worker lifecycle | `backend/main.py` lifespan | 7677, 9091 | `evtx_worker.start()` / `telemetry_worker.start()` in-process with the API; singletons at `worker.py` L522, `evtx_worker.py` L346. |

**Transaction topology (metrics/winlog):** `T1 = {source rows + (quarantine + AuditLog + TelemetryAlertOutbox)}` � commit � Redis dispatch (no DB tx) � `T2 stamp`. Redis ACK is after T1 + DLQ durability. At-least-once everywhere; SQL uniqueness is the replay guard.

## 2. Windows EVTX  exact path

1. **Upload:** `controller.py upload_windows_evtx` L120167  64 MiB cap (L3647), MinIO upload (L136), then `cache_manager.xadd_queue(EVTX_STREAM_KEY, {job_id, minio_uri, uploader_fingerprint})` (L145148; `cache.py xadd_queue` L149157 wraps fields as `{"payload": json}`). Unconfirmed queue write � 503; MinIO object may orphan, **no auto-delete** (L151159).
2. **Job consumer:** `evtx_worker.py EVTXBackgroundWorker._process_pending_tasks` L238343. Stream `eims:jobs:evtx:stream` / group `eims:jobs:evtx:workers` / DLQ `eims:jobs:evtx:dead-letter` (L2325). Legacy list migration is atomic XADD-before-RPOP Lua (L3137, L8285). Gates: undecodable fields (L256261), malformed payload (L262268), missing job/uri (L270274), **uploader must be 64-hex SHA-256  never fabricated** (L275279), bucket-scoped URI validation `_object_name` L185192, bounded download L194203/287295, d100 000 records L296303.
3. **Parser validation:** `evtx_parser.py parse_evtx_records` L69214  exactly one yield per record (stable positions), `parse_error` sentinels, reserved `evtx_*` keys immune to EventData spoofing (L3440, L178186), missing `TimeCreated` yields `""` (never fabricated) and fails downstream. Each record then validated by `AgentWinlogRequest.model_validate` (`evtx_worker.py` L310; schema `schemas.py` L5063 requires tz-aware `occurrence_time`, normalized to UTC L5459).
4. **Event identity:** `_source_event_key` L145156  with `evtx_event_record_id`: `"evtx:" + sha256(uploader \x1f evtx_computer \x1f provider \x1f channel \x1f record_id \x1f occurrence_time \x1f event_id)` (stable across re-uploads); fallback `evtx:{job_id}:{index}`.
5. **Broker � persistence:** valid records published via `broker.publish_winlog(payload, cert_fingerprint=uploader, source_event_key)` (L316317) into the **same** `eims:telemetry:ingestion` stream � the �1 telemetry consumer persists them in T1. Record-level DLQ only after all valid publishes; job ACK last (L318326). Retry cap: `max_delivery_attempts=5` via XPENDING delivery count (L121127, L329337). **The EVTX worker never touches PostgreSQL**  asset identity is resolved later by the telemetry consumer from the uploader fingerprint.

## 3. Analyzer  exact AnalysisHistory insert/commit points

There are **three** insertion sites; none currently sets `asset_id`:

| Site | Insert / commit | Asset identity |
|---|---|---|
| `backend/api/routers/analyzer/analyze.py submit_analysis` | row L268279, `db.add` L280, **`await db.commit()` L281** | **Not resolvable**  pasted text/upload; only `metadata.attributes`/`event_metadata` (hostname-like strings). Must stay NULL; never infer. |
| `analyze.py submit_bundle` | row L487498, add L499, **commit L500** | Same  NULL. Bundle provenance (file SHA-256s) lives in `attributes["bundle"]` L468486. |
| `backend/domain/analyzer/services/import_pipeline.py _analyze_event` (offline USB) | row L328339 (`username="system"`), add L340, **commit L341** | **Explicitly resolvable.** `asset_id` is a function parameter (L284) coming from `repo.upsert_offline_report` (`asset_registry/controller.py import_offline_report` L230, passed L244). `build_analysis_provenance` L158176 already embeds `asset_id` + `event_source_id` (= `WindowsEventLog.log_id`, resolved by `_find_event_log_id` L262270) into `event_metadata`  **but the new `analysis_history.asset_id` column (history.py L3136) is not populated.** This is the one legitimate explicit-resolution point. |

Session semantics: `get_db_session` (`infrastructure/database.py` L276279 � `get_session` L257265) yields a session, rolls back on exception, closes in finally  **no autocommit**; the router's `db.commit()` is the sole commit. `expire_on_commit=False` (L91); INSERT RETURNING populates `id` (comments at analyze.py L282/L501). Offline path commits winlog batch separately (`ingest_report_events` L406420) **before** per-event analysis commits (L341)  two distinct transactions; its winlog rows have **NULL `source_event_key`** (`_persist_event` L247259), deduped instead by `evtx_metadata._reporter_dedup` (`compute_dedup_key` L125141: asset|channel|provider|record_id|occurrence_time).

`AnalysisHistory.created_at` is legacy **UTC-naive** `TIMESTAMP WITHOUT TIME ZONE` (history.py L3738); incident correlation coerces naive�UTC deterministically (`correlation.py normalize_observed_at` L4959).

## 4. Existing outbox dispatcher / consumer / dedupe

- **Model:** `TelemetryAlertOutbox` (`telemetry/models.py` L131151): `alert_id` UUID PK, `payload` JSONB, `created_at`, `published_at` NULL, partial pending index `idx_telemetry_alert_outbox_pending` (migration `f7b3d91c4a58`).
- **Dispatcher:** `worker.py dispatch_outbox` L458514. Topology:
  - **T2 (short):** select pending `FOR UPDATE SKIP LOCKED`, copy `(alert_id, payload+alert_id)` (L474485); locks released before any Redis I/O.
  - **Redis:** XADD to `eims:events:alerts:stream` (L33, L490492); failure/unconfirmed � row stays pending, loop breaks.
  - **T3 (per row, no network awaits):** stamp `published_at` only after confirmed XADD (L501507).
  - Best-effort PubSub `eims:events:alerts` (L509513).
  - Crash between XADD and stamp � **republish � at-least-once; consumers must dedupe by `alert_id`** (documented contract, handoff �2).
- **Consumer side  key finding:** the durable alert stream **has no consumer today**. Repo-wide grep for `alerts:stream` matches only the producer constant. The only subscriber is `ws_controller.py redis_pubsub_listener` L4167 on the **PubSub channel** (live, lossy, demo-mode-only WS fan-out L6986). So "existing consumer dedupe" is a *contract without an implementation*  there is no processed-state table and no durable alert consumer to extend.
- Dispatch is triggered opportunistically: start of every `process_batch` (L218) and after any T1 that produced alerts (L389390). No independent timer.

## 5. `IncidentService.create_from_evidence`  invocation contract

`backend/domain/incident/service.py`:

- Signature L393402: `(evidence: list[EvidenceInput], *, actor: str, asset_id: UUID|None, title, severity, window_seconds) -> (Incident, created)`.
- **It is a transaction OWNER, not a participant:** `begin_nested()` savepoint L480, flush, then **`await self.db.commit()` L495**; `_reuse_incident` commits at L594; `attach_evidence` at L654; `change_status` at L702. On `IntegrityError` it rolls back and recovers via `_recover_after_conflict` L514543.
- **Consequence:** calling it inside the ingestion transaction would commit the source transaction prematurely (nested-commit hazard) and couple ingestion latency to correlation queries. It must be invoked **after the source commit, on a dedicated session** obtained from `database_engine.get_session_maker()` (`database.py` L267269)  exactly how workers already get sessions.
- `actor` is a free-form non-empty string (L405406; stored in `incident_evidence.added_by` String(255) and audit payload). The HTTP controller passes the JWT username (`controller.py` L150155); a worker may pass a stable service identity (e.g. `"system:incident-ingest"`). No `get_current_user` involvement is required off-HTTP.
- `asset_id` is validated against `infrastructure_assets` (L412419)  a deleted asset raises `IncidentValidationError`.
- Idempotency layers already present: dedupe-key upsert (L423436, terminal-recurrence per-bucket key L426432), **evidence-identity lookup across window buckets** (L438450: same `(source_type, source_id)` always returns the bound incident, terminal � `(incident, False)`), candidate correlation (L452457), `UNIQUE(source_type, source_id)` (`models.py` L236240).
- `EvidenceInput` (L97124): `signature = normalize_signature(source_type, source_event_key or source_id)`; digest defaults to `sha256(source_type:source_id:observed_at_iso)` (`correlation.py` L104108). `source_id` d 64 chars (L189190)  UUID strings (36) and integer history ids fit.
- Allowed `source_type`: `analysis | winlog | telemetry | audit` (`models.py` L41; migration check L110113).
- Current callers: **only** `incident/controller.py` L153 and tests. No ingestion integration exists yet.

## 6. Identity / timestamp / provenance matrix

| Source | Event identity (stable) | Row PK (source_id) | Asset identity | observed_at | Provenance |
|---|---|---|---|---|---|
| Heartbeat metric | `ingest:sha256(type\x1f FP\x1f payload)` (controller L5055) | `telemetry_metrics.metric_id` (uuid4/attempt) | **Resolved, NOT NULL** via mTLS FP � `cryptographic_fingerprint`; unresolved � DLQ | `event_time` = agent `timestamp` (tz UTC, schemas L34) | cert FP in envelope; `diagnostic_payload` |
| Agent winlog (HTTP) | same `ingest:` scheme | `windows_event_logs.log_id` | same | `occurrence_time` (tz-required, UTC-normalized, schemas L5459) | FP; `evtx_metadata` (extra="allow") |
| EVTX record | `evtx:sha256(uploader\x1fcomputer\x1fprovider\x1fchannel\x1frecord_id\x1ftime\x1fevent_id)` or `evtx:{job}:{index}` (evtx_worker L145156) | `windows_event_logs.log_id` | uploader FP resolved by telemetry consumer | parser `TimeCreated`; missing � validation failure � record DLQ | MinIO URI + job_id + uploader FP; `evtx_*` parser-owned metadata |
| Offline USB winlog | **NULL `source_event_key`**; `evtx_metadata._reporter_dedup` = sha256(asset\|channel\|provider\|record_id\|time) (import_pipeline L125141) | `log_id` (known pre-commit, L249) | **Explicit** from report upsert | `occurrence_time` or now(UTC) fallback (L253) | `source_type=USB_OFFLINE_COLLECTION`, `collected_at` (L144155) |
| Analyzer history | none (no source_event_key) | `analysis_history.id` (integer, RETURNING) | **NULL** except offline path where explicit `asset_id` exists | `created_at` UTC-naive � coerced UTC | `username`, `event_metadata` incl. `asset_id`/`event_source_id` provenance (offline), bundle SHA-256s |
| Quarantine alert | `alert_id` (outbox PK) | `audit_logs.log_id` / alert_id | concrete asset | `created_at` | `AUTOMATED_QUARANTINE_4625` payload |

---

## 7. Design decision

### Recommendation: **additive dedicated `incident_ingest_outbox` + async incident-ingestion consumer** (Option B). Do **not** extend `telemetry_alert_outbox`.

### Why not extend the existing telemetry outbox (exact compatibility analysis)

Extending is *mechanically* possible  the table is generic (`payload` JSONB) and the dispatcher publishes any pending row. But it is not safe/narrow:

1. **Semantic collision with an accepted surface.** Today one outbox row = one real quarantine transition (worker L441444). Incident ingestion would add a row per qualifying source event  orders of magnitude more volume through the same `OUTBOX_DISPATCH_BATCH=100` claim loop, delaying security-alert delivery behind incident traffic.
2. **WS fan-out leakage.** `dispatch_outbox` best-effort publishes *every* dispatched payload to PubSub `eims:events:alerts` (L509510), which `ws_controller` broadcasts verbatim to demo dashboards. Incident envelopes would leak into the live alert channel; filtering would require modifying the accepted dispatcher.
3. **Shared-stream consumer coupling.** A new incident consumer group on `eims:events:alerts:stream` would share delivery/reclaim semantics with future alert consumers; the stream key also sits outside the approved namespace prefixes (`cache.py _validate_namespace` L116126  warning-only, and `dispatch_outbox` bypasses it via raw `xadd`).
4. **Write-site mismatch.** The outbox is written only inside `_detect_brute_force`; per-event emission requires touching `_persist_batch` anyway  so extension saves no code, only adds coupling.
5. The existing outbox has **no consumer and no processed-state** to reuse (�4); its dedupe contract (`alert_id`) is alert-shaped, not source-row-shaped.

Conclusion: keep `telemetry_alert_outbox` byte-for-byte unchanged; add a parallel, additive mechanism that **copies its proven transaction pattern**.

### Option B  concrete shape (all additive)

**Migration** (new revision, `down_revision = "b8d3f5c1a720"`, single head preserved):
- `incident_ingest_outbox`: `outbox_id UUID PK`, `source_type VARCHAR(16) CHECK (analysis|winlog|telemetry|audit)`, `source_id VARCHAR(64) NOT NULL`, `source_event_key VARCHAR(160) NULL`, `asset_id UUID NULL FK infrastructure_assets ON DELETE RESTRICT`, `observed_at TIMESTAMPTZ NOT NULL`, `payload JSONB NOT NULL DEFAULT '{}'` (bounded provenance only  cert fingerprint prefix, job_id, parse method; **never raw log payloads**, matching the incident domain's reference-only rule), `created_at TIMESTAMPTZ`, `published_at TIMESTAMPTZ NULL`, partial index on `created_at WHERE published_at IS NULL` (mirror of `idx_telemetry_alert_outbox_pending`).
- No change to `incidents`, `incident_evidence`, `analysis_history`, `telemetry_alert_outbox`, or any existing index. Downgrade drops only the new table.

**Emission (same DB transaction as source persistence  true transactional outbox):**

1. **Telemetry worker (`_persist_batch`, worker.py L368390):** extend `_insert_rows` (L345348) to `&on_conflict_do_nothing(...).returning(pk, source_event_key, asset_id, event_time/occurrence_time, severity_level)` and insert outbox rows **inside the same `session.begin()`** for *returned (actually new)* rows only.
   - **Why RETURNING is mandatory:** transient row PKs are fresh uuid4 per attempt (L274/L282); on replay, `ON CONFLICT DO NOTHING` keeps the *original* row, so enqueuing the transient PK would create phantom `source_id`s and duplicate incidents. RETURNING yields the durable identity and naturally suppresses replay duplicates at the source.
   - **Emission policy (deterministic, pure, configurable  decision point):** recommended v1.1 default = winlog rows with `severity_level  {Critical, Error, Warning}` (parser LEVEL_MAP L1219); **no per-heartbeat incidents** (high-frequency, low signal; the meaningful metric-derived signal is the quarantine transition, which already has its own outbox). Optional later bridge: a tiny consumer on the existing alert stream (dedupe by `alert_id`, `source_type='audit'`, `source_id=alert_id`)  explicitly out of v1.1 scope unless you want it.
2. **Analyzer (`analyze.py` L280/L499, `import_pipeline.py` L340):** add the outbox row to the session **before the existing single `db.commit()`** (L281/L500/L341). Same transaction, no nested commit, no extra commit, latency cost = one INSERT. `source_type='analysis'`, `source_id=str(history.id)`  available pre-commit via INSERT RETURNING flush (or flush-then-enqueue inside the same tx). `observed_at` = the same UTC-naive `created_at` value (coerced by `normalize_observed_at`). `asset_id=NULL` for submit/bundle; **offline path: also set `row.asset_id = asset_id` explicitly** (the column exists, b8 applied; this is explicit resolution, not inference) and enqueue with that asset.
3. **Offline USB winlog batch (`ingest_report_events` L406408):** optional in v1.1; if included, enqueue before the L408 commit using the known `event_log_id` (L249)  these rows have NULL `source_event_key`, which the envelope tolerates because `source_id` is authoritative.

**Dispatcher:** new function mirroring `dispatch_outbox` exactly (claim `FOR UPDATE SKIP LOCKED` in short tx � release locks � XADD � stamp `published_at` in a separate network-free tx), targeting a **new** durable stream under an approved namespace, e.g. `eims:jobs:incident-ingest:stream`, DLQ `eims:jobs:incident-ingest:dead-letter`. Trigger: post-commit hook in `_persist_batch` + drain at batch start (same opportunistic pattern), never inside T1, never allowed to fail ingestion (`_dispatch_outbox_safely` pattern L448456).

**Consumer:** new `IncidentIngestConsumer` (own consumer group, own `get_session_maker()` sessions, XAUTOCLAIM reclaim + lease refresh without delivery-count increment  copy broker L121149 / worker L183214 patterns). Per entry:
1. Build `EvidenceInput(source_type, source_id, observed_at, source_event_key)` directly from the envelope  **no source-row re-read needed** (identity was captured at commit time).
2. `await IncidentService(dedicated_session).create_from_evidence([item], actor="system:incident-ingest", asset_id=envelope.asset_id)`  the service owns its commit; one fresh session per entry (or small batch) avoids nested commits and keeps correlation queries off the ingestion path.
3. **ACK only after the incident transaction commits.** Crash between commit and ACK � redelivery � service's evidence-identity lookup (L438450) returns `(existing, False)` � ACK. **The durable processed-state is the `incident_evidence` unique binding itself**  no extra processed table required.
4. Retry/DLQ: transient DB/Redis errors � leave pending (no ACK, no DLQ  mirror `DatabaseUnavailableError` contract); deterministic poison (invalid envelope, `IncidentValidationError` such as asset-deleted FK failure) � DLQ with stable reason after delivery-count cap (mirror evtx_worker L329337, cap 5). Never fabricate identity on failure.

**Latency/AI isolation:** T1 gains only local INSERTs; correlation, retries, and any future AI enrichment run in the separate consumer. Analyzer AI latency is untouched (outbox INSERT precedes its existing commit; no new awaits on external services).

### Audit consistency (explicit, no cross-transaction atomicity claims)

- **T_source** = source row(s) + outbox row (+ quarantine/AuditLog where applicable)  atomic. If it rolls back, no outbox row exists and no incident can ever be derived.
- **T_incident** = incident + evidence + `INCIDENT_CREATED`/`INCIDENT_EVIDENCE_ADDED` AuditLog  atomic, **later, separate transaction**. There is **no atomicity between T_source and T_incident**; the guarantee is *durable intent + at-least-once delivery + idempotent sink*: committed source � eventual incident attempt; repeated delivery � exactly one evidence binding.
- Source-side audit (`AUTOMATED_QUARANTINE_4625`) and incident-side audit (`INCIDENT_*`, `incident_id` in `immutable_payload`, service L358388) live in their own transactions and reference each other only by identity strings  no cross-transaction FKs, no implied simultaneity. `audit_logs` journal reused; no new audit table.

### Duplicate & cross-asset isolation

- **Duplicates:** four independent layers  (1) `ON CONFLICT DO NOTHING` + RETURNING-only emission (no replay envelopes); (2) dispatcher at-least-once republish absorbed by (3) `UNIQUE(source_type, source_id)` + service evidence-lookup idempotency; (4) `dedupe_key` upsert with terminal-recurrence per-bucket keys (service L426432). Window-bucket boundaries cannot split one source row into two incidents because layer 3 keys on source identity, not time.
- **Cross-asset:** telemetry/winlog sources always carry a concrete resolved asset (unresolved never persists). `classify()` returns `none` for any two different concrete assets (correlation.py L202218); candidate query restricts to same-or-unresolved (service L251257); unresolved auto-merge only into unresolved incidents; `_reuse_incident` sets an asset only when the incident's is NULL and an explicit asset is supplied (L578579)  **hostname/workstation_name is never used**. Analyzer-origin incidents stay asset-unresolved until explicit evidence resolves them.
- **Asset deletion edge:** telemetry FKs are CASCADE (source rows vanish with asset); incident/analysis FKs are RESTRICT. If an asset is deleted between T_source and T_incident, `create_from_evidence`'s asset validation (L412419) rejects deterministically � DLQ with reason, never a guessed/NULL-substituted identity.

---

## 8. Tests and exact edge cases (focused only; no broad suites)

**Extend existing seams:** `tests/test_telemetry_reliability_fixes.py` (FakeDB/FakeSession), `tests/test_telemetry_outbox_and_db_unavailable.py` (pending/no-DLQ/no-ACK contracts, SKIP LOCKED compile check), `tests/test_telemetry_outbox_concurrent_dispatch_integration.py` (real disposable PG+Redis), `tests/test_evtx_worker_fault_contracts.py`, `tests/test_evtx_minio_postgres_e2e_acceptance.py`, incident suites (`test_incident_idempotency.py`, `test_incident_correlation.py`, `test_incident_lifecycle.py`, `test_incident_migration.py`) with `tests/incident_db_support.py` (allowlisted disposable `eims_incident_test` only; ingestion tests will need an explicitly approved disposable target/allowlist decision at implementation time).

New focused cases:
1. **Outbox atomicity:** forced failure after flush � source row *and* outbox row both absent (rollback); success � both present in one commit.
2. **Replay suppression:** redeliver same `source_event_key` � ON CONFLICT drops row, RETURNING empty � **zero** new outbox rows; transient uuid4 PK never leaks into an envelope.
3. **Dispatcher crash window:** XADD confirmed, stamp transaction killed � row republished � consumer produces exactly one `incident_evidence` row.
4. **Consumer crash window:** incident committed, ACK lost � redelivery � `created=False`, no duplicate evidence, no second `INCIDENT_CREATED` audit.
5. **Transient DB outage during consume:** no ACK, no DLQ, entry pending; recovery processes it (mirror P1-B test).
6. **Poison envelope** (bad source_type / missing fields / asset-deleted `IncidentValidationError`): DLQ after delivery cap with stable reason; valid siblings unaffected; delivery count not inflated by lease refresh.
7. **Cross-asset isolation at ingestion level:** identical signature+time on two assets � two incidents; unresolved analysis evidence never merges into a concrete-asset incident.
8. **NULL-asset analyzer path:** submit/bundle � incident `asset_id NULL`; offline import � `analysis_history.asset_id` explicitly set and equal to provenance `event_metadata.asset_id`; hostname strings never produce an asset.
9. **NULL `source_event_key`** (offline winlog): envelope keyed by `source_id`; two NULL keys still accepted by the unique index.
10. **Timestamp edges:** UTC-naive `created_at` coerced deterministically; EVTX missing TimeCreated � record DLQ (no fabricated time); window-bucket boundary recurrence after terminal status � new per-bucket incident.
11. **Latency isolation:** assert no Redis/external awaits inside T1; dispatch failure never fails ingestion (existing `_dispatch_outbox_safely` contract).
12. **Migration:** empty-schema upgrade to new head; populated parent at `b8` preserved (outbox empty, incidents untouched); downgrade drops only `incident_ingest_outbox`; re-upgrade; single head; non-superuser disposable role.
13. **Concurrency:** two dispatchers (SKIP LOCKED) and two consumers racing the same source identity � one incident, IntegrityError recovery path exercised (service L501509).

---

## 9. Open decision points for you

1. **Emission policy:** confirm the recommended default (winlog Critical/Error/Warning + all analysis history; no per-heartbeat incidents; quarantine-alert bridge deferred). Alternative: event-ID allowlist (e.g., 4625/1129/6005) instead of severity filter.
2. **Offline USB winlog batch:** include in v1.1 emission or defer (analysis-side coverage already captures the analyzed subset)?
3. **Actor identity** for worker-created incidents: proposed `"system:incident-ingest"` (free-form, audited in `added_by`/payload).
4. **Disposable test target** for the new integration tests (new container vs. extending the `eims_incident_test` allowlist)  must be explicitly approved before implementation.

No files were created or changed. If you want this trace persisted as a plan/snapshot document, say so explicitly and I'll write it only to the approved plan location  and implementation itself requires switching out of Plan mode to an authorized writer agent per the operating contract.
