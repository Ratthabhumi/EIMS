# Incident Verification and Resolution Policy (v1, 2026-11-19)

Status: **implemented and PostgreSQL-accepted**
Scope: `backend/domain/incident/**`, migration `f7a1c3d9e502`
Supersedes: the Incident Core v1 position that "no remediation or closure
automation exists" (docs/engineering-memory/2026-11-16-incident-core-v1.md).
That document remains the behavioural baseline for correlation; this one adds
the missing resolution invariant.

## 1. The invariant

> An incident cannot become `resolved` unless a persisted
> `incident_verification` row proves that evidence attached during the
> **current remediation cycle** was revalidated by an **authorised verifier**.

The invariant lives in `IncidentService.change_status`, not in the controller.
`PATCH /api/v1/incidents/{id}/status` is the only API path that reaches it, and
no worker, CLI or repository method can resolve an incident
(`grep change_status backend/` returns exactly the service definition and the
controller call site).

## 2. Which transitions require verification

| Transition | Requirement |
|---|---|
| `open -> triage` | none |
| `triage -> investigating` | none |
| `investigating -> resolved` | **verification required** |
| `resolved -> closed` | Knowledge Reviewer capability (unchanged) |
| `resolved -> investigating` (reopen) | starts a new remediation cycle |
| everything else | illegal (`IncidentTransitionRejected`) |

There is no incident "type" column in the schema, so the policy is uniform.
Adding per-type exceptions would be a new product decision, not an
implementation detail.

## 3. What qualifies as verification evidence

Caller input is only:

```json
{"evidence_id": "<incident_evidence.evidence_id>"}
```

`outcome` and `verifier_id` are **rejected** by the request schema
(`extra="forbid"`) and are never read from the request body.

Server-side checks, in this order:

| # | Check | Failure code |
|---|---|---|
| 1 | verifier is a known principal with `role=admin` or `knowledge_reviewer` | `verifier_required` / `verifier_unauthorized` (403) |
| 2 | evidence row exists | `evidence_unknown` |
| 3 | evidence belongs to this incident | `evidence_foreign` |
| 4 | `source_type` is in the verification allowlist (`analysis`) | `evidence_type_not_verifiable` |
| 5 | stored digest equals a server-side recomputation | `evidence_digest_mismatch` |
| 6 | evidence was attached during the current cycle | `evidence_stale` |
| 7 | `source_id` is the canonical decimal form of an existing `analysis_history.id` | `evidence_source_malformed` / `evidence_source_unknown` |
| 8 | the referenced record is attributed to the incident's asset (when the incident has one) | `evidence_asset_mismatch` |
| 9 | the verifier did not attach the evidence they are verifying | `verifier_conflict` (403) |

Why the allowlist is narrow: `winlog`, `telemetry` and `audit` rows are
reference-only metadata with no trusted outcome signal. Accepting them would let
a caller "prove" a fix with an event that only proves the incident occurred.
They fail closed.

## 4. Trusted persistence and digest semantics

Evidence is reference-only by design: EIMS stores
`(source_type, source_id, digest, observed_at)` and never copies source
payloads. The digest is therefore **reference integrity**, computed as

```
sha256(f"{source_type}:{source_id}:{observed_at.isoformat()}")
```

and recomputed from the stored row at verification time. This proves the row was
not edited after attachment. It does **not** prove the bytes of an external
artifact, because no such artifact is stored. A caller-supplied digest that does
not match the recomputation can never authorise resolution.

## 5. Remediation cycle

- `incidents.remediation_cycle` (int, default 0) and
  `incidents.remediation_started_at` were added by migration `f7a1c3d9e502`.
- A **genuine reopen** (`resolved -> investigating`) increments the cycle by
  exactly one and sets `remediation_started_at = now()` in the same transaction
  as the status change and audit row.
- Nothing else changes the cycle: duplicate resolves, failed transitions and
  retries do not increment it.
- Evidence attached before `remediation_started_at` cannot verify the new cycle.

## 6. Atomicity and concurrency

One transaction owns the whole decision:

1. `SELECT ... FOR UPDATE` on the incident row.
2. Re-read status and cycle (no TOCTOU window).
3. Validate the lifecycle edge.
4. Authorise the verifier.
5. Lock and revalidate the evidence row.
6. Insert the verification row.
7. Update status, bump the cycle if this is a reopen, write the audit row.
8. Commit once.

Failure at any step rolls the whole transaction back: no `resolved` status
without a verification row, and no verification row for a transition that did
not commit. Deadlocks/serialisation failures surface as errors, never as a
successful response.

Transaction ownership: `change_status` owns the transaction it starts and
commits exactly once; callers must pass a dedicated session. The API dependency
already provides one session per request.

## 7. Append-only history and database-level enforcement

Two PostgreSQL controls, not just ORM conventions:

1. **Append-only evidence of verification.** `BEFORE UPDATE OR DELETE ... FOR
   EACH ROW` and `BEFORE TRUNCATE ... FOR EACH STATEMENT` triggers raise
   `restrict_violation` with `incident_verification is append-only`. Raw SQL
   cannot rewrite or erase history.
2. **Resolution cannot be set by raw SQL.** A `BEFORE UPDATE OF status ON
   incidents` trigger raises `check_violation` when `status` becomes `resolved`
   without a `passed` verification row for the incident's current
   `remediation_cycle`. `UPDATE incidents SET status='resolved'` therefore fails
   even outside the service.

Both foreign keys use `ON DELETE RESTRICT`, so history survives
incident/evidence lifecycle changes. Reopening makes old rows *inapplicable by
cycle*, it never deletes them.

## 8. Legacy incidents

Incidents resolved before this migration keep their status. They are **not**
retroactively marked verified: no `incident_verification` row is fabricated.
`remediation_started_at` is backfilled from `created_at`. If such an incident is
reopened it starts cycle 1 and needs fresh evidence before resolving again.

## 9. API behaviour

| Situation | HTTP | Body |
|---|---|---|
| resolved without `verification` | 422 | `resolution_blocked:missing_verification: ...` |
| unknown/malformed/foreign/stale/wrong-type evidence | 422 | `resolution_blocked:<code>: <detail>` |
| verifier lacks capability / anonymous | 403 | `verifier_*` |
| illegal transition | 409 | `Illegal incident transition ...` |
| success | 200 | incident detail incl. `remediation_cycle` and `verifications[]` |

`IncidentDetailResponse.verifications[]` exposes
`verification_id, remediation_cycle, evidence_id, evidence_digest, outcome,
verifier_id, verified_at` so an engineer can answer "who verified what, when,
for which cycle". No evidence payload content is exposed because none is stored.

## 10. Honest limits

- **Separation of duties is one-directional.** The verifier may not verify their
  own evidence, but any authenticated user can attach evidence (the controller
  docstring says Engineer; the code only requires authentication). A stricter
  attach policy is a separate decision.
- **One verification row per cycle is guaranteed by the state machine**, not by
  a `(incident_id, remediation_cycle)` unique constraint. The constraint is
  `(incident_id, remediation_cycle, evidence_id)` so a cycle could hold two rows
  if the service were bypassed; the DB resolution trigger and the append-only
  rules still prevent an unverified resolution.
- **The table owner can disable triggers.** A runtime role that owns the tables
  can `ALTER TABLE ... DISABLE TRIGGER`; production should run as a non-owner
  with `INSERT`/`SELECT` only. That provisioning is a deployment step, not
  implemented here.
- **`analysis` existence is a reference check, not outcome proof.**
  `analysis_history` has no remediation-outcome field. The human verifier
  attests; the system proves the reference is real, current, unmodified and
  theirs to verify. Do not describe this as an external health probe.
- **Staleness uses timestamps**: `incident_evidence.created_at` (PostgreSQL
  `now()`) vs `incidents.remediation_started_at`. A reopen stamps a Python UTC
  value, so a large app/DB clock skew would widen or narrow the window. Both
  sides are UTC-aware; skew is expected to be sub-second.
- **A successful commit followed by a response-serialisation failure** returns
  5xx although the incident is resolved. The persisted state is authoritative.
- **Migration test coverage**: `test_incident_migration.py` covers upgrade,
  downgrade, constraints and data preservation; the two triggers are exercised
  by `test_incident_verification_pg.py` on `create_all` schemas rather than on a
  migrated schema.
- No remediation-action or diagnosis endpoint exists; investigation context
  lives in `incidents.summary`/`root_cause_state`.
- No incident UI in the dashboard; the workflow is API/service level.
- Audit rows are not hash-chained; they carry `verification_id`/`verifier` but
  are not tamper-evident against a privileged writer.
