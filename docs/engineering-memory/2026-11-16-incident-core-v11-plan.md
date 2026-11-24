# EIMS Engineering Memory — 2026-11-16 Incident Core v1.1 Implementation Plan

**Milestone:** Event-to-Incident Ingestion Integration.
**Basis:** [2026-11-16-incident-core-v11-architecture-trace.md](2026-11-16-incident-core-v11-architecture-trace.md) (recovered read-only trace, job `3ef58a7d…`).
**Status:** PLANNED — implementation must not start until the Chat_HAND writer smoke is accepted.

## 1. What exists and must not be rebuilt

- `backend/domain/incident/{models,correlation,service,controller,schemas}.py`
- `/api/v1/incidents` API and its reviewer-gated close.
- Migration `b8d3f5c1a720_add_incident_core.py` (repository head; untracked).
- Additive nullable `analysis_history.asset_id`.

No new Timeline, Audit or Knowledge table. `audit_logs` stays the journal.

## 2. Design decision (evidence-based)

**Additive dedicated `incident_ingest_outbox` + async `IncidentIngestConsumer`.**
Do not extend `telemetry_alert_outbox`.

Trace evidence for rejecting extension: one outbox row currently equals one
quarantine transition; the dispatcher publishes every payload to the live alert
PubSub channel (WS fan-out leakage); the alert stream has no durable consumer and
no processed-state table; and the outbox is written only inside
`_detect_brute_force`, so per-event emission would touch `_persist_batch` anyway.

Reuse the *pattern*, not the table: short claim transaction → Redis XADD →
network-free stamp transaction.

## 3. Scope

### 3.1 Migration (single new revision, `down_revision = "b8d3f5c1a720"`)

`incident_ingest_outbox`:
- `outbox_id UUID PK`
- `source_type VARCHAR(16)` CHECK in (`analysis`, `winlog`, `telemetry`, `audit`)
- `source_id VARCHAR(64) NOT NULL`
- `source_event_key VARCHAR(160) NULL`
- `asset_id UUID NULL` FK `infrastructure_assets` `ON DELETE RESTRICT`
- `observed_at TIMESTAMPTZ NOT NULL`
- `payload JSONB NOT NULL DEFAULT '{}'` — bounded provenance only, never raw logs
- `created_at TIMESTAMPTZ`, `published_at TIMESTAMPTZ NULL`
- partial index `(created_at) WHERE published_at IS NULL`
- `UNIQUE(source_type, source_id)` as the emission-level replay guard

Downgrade drops only this table. Empty-schema upgrade and populated-parent upgrade
must both be tested on a disposable PostgreSQL.

### 3.2 Emission (same transaction as source persistence)

1. **Telemetry worker** `_persist_batch` / `_insert_rows`: add
   `.on_conflict_do_nothing(...).returning(pk, source_event_key, asset_id, time, severity)`
   and enqueue **only returned rows**, inside the existing `session.begin()`.
   RETURNING is mandatory: transient PKs are fresh `uuid4` per attempt, so
   enqueuing a transient id would fabricate source identities on replay.
2. **Analyzer** `analyze.py` (submit, submit_bundle) and
   `import_pipeline._analyze_event`: enqueue before the *existing* single
   `db.commit()`. `source_type='analysis'`, `source_id=str(history.id)`;
   `asset_id` NULL for submit/bundle, explicitly set on the offline path.
3. **Offline USB winlog batch:** defer or include per owner decision (§8).

No new `await` on an external service inside the source transaction. Ingestion
must not wait for correlation or AI.

### 3.3 Dispatcher

Mirror `dispatch_outbox`: claim with `FOR UPDATE SKIP LOCKED` in a short
transaction, release locks, XADD to a new stream under an approved namespace
(`eims:jobs:incident-ingest:stream`, DLQ `eims:jobs:incident-ingest:dead-letter`),
stamp `published_at` in a separate network-free transaction. Trigger
opportunistically after commit and at batch start; never fail ingestion.

### 3.4 Consumer

`IncidentIngestConsumer` (own group, own sessions, XAUTOCLAIM + lease refresh that
does not inflate delivery count):
1. Build `EvidenceInput` from the envelope (no source-row re-read).
2. `IncidentService(dedicated_session).create_from_evidence([...], actor="system:incident-ingest", asset_id=envelope.asset_id)`.
   The service owns its commit; it must never run inside the source transaction.
3. ACK only after the incident transaction commits. Redelivery is absorbed by the
   existing `UNIQUE(source_type, source_id)` + evidence-identity lookup, so the
   durable processed-state is the evidence binding itself.
4. Transient errors → leave pending, no ACK, no DLQ. Deterministic poison →
   DLQ after the delivery cap (5), stable reason, never a fabricated identity.

## 4. Invariants

- Never infer hostname or asset identity; unresolved evidence stays unresolved.
- Two different concrete asset ids never merge.
- Preserve the original source event identity (`source_event_key`).
- Correlation is not causality; no automatic closure or remediation.
- No atomicity claimed across `T_source` and `T_incident`; the guarantee is
  durable intent + at-least-once + idempotent sink.
- Evidence is preserved when incident processing temporarily fails.

## 5. Tests (focused, disposable infrastructure only)

Extend: `test_telemetry_reliability_fixes.py`,
`test_telemetry_outbox_and_db_unavailable.py`,
`test_telemetry_outbox_concurrent_dispatch_integration.py`,
`test_evtx_worker_fault_contracts.py`, incident suites + `incident_db_support.py`.

Required cases: outbox atomicity and rollback; replay suppression (RETURNING
empty); dispatcher crash window (republish → one evidence row); consumer crash
window (ACK lost → `created=False`); transient DB outage; poison envelope → DLQ;
cross-asset isolation; NULL-asset analyzer path vs explicit offline asset; NULL
`source_event_key`; timestamp edges; no external await inside the source
transaction; migration upgrade/downgrade/re-upgrade on a non-superuser disposable
role; concurrent dispatcher/consumer race.

## 6. Sequence and writers

One writer per file group, no concurrent overlapping scopes:

1. Migration + model (group A).
2. Telemetry/analyzer emission (group B) — depends on A.
3. Dispatcher + consumer (group C) — depends on A.
4. Tests (group D) — can start alongside C with stub seams.
5. Independent read-only review of the exact diff.
6. Disposable PostgreSQL acceptance.

## 7. Explicitly out of scope

- Dashboard/UI.
- Rebuilding Incident Core v1.
- AI enrichment inside ingestion.
- Operational database, Redis or MinIO access.
- Modifying `telemetry_alert_outbox` or the alert stream semantics.

## 8. Open decisions (owner)

1. **Emission policy:** recommended default is winlog `Critical|Error|Warning`
   plus all analyzer history, and no per-heartbeat incidents. Alternative: an
   event-id allowlist (4625/1129/6005).
2. **Offline USB winlog batch:** include in v1.1 or defer (analysis coverage
   already captures the analyzed subset)?
3. **Disposable test target:** new container or extend the
   `eims_incident_test` allowlist — must be approved before implementation.
