# EIMS V12 — A13 Audit Integrity Design (proposal, not applied)

Date: 2026-11-18 (Asia/Bangkok)
Finding: EIMS-F4 — `AuditLog` is described as immutable/tamper-resistant, but no trigger, hash chain or signature exists.

## 1. Vocabulary (do not interchange)

| Term | Meaning | What it requires |
|---|---|---|
| **Append-only** | the application only inserts | an insert-only code path; a DB role that cannot update/delete |
| **Tamper-evident** | unauthorized change is detectable under a stated trust model | canonical record + hash chain + an anchor outside the writer's control |
| **Tamper-resistant** | an attacker cannot readily modify without detection | tamper-evident plus access separation and key custody |
| **Immutable** | records cannot be changed by anyone, including the DB owner | WORM storage or an external immutable log |

Current implementation: **append-only by convention only**. No trigger, no chain, no signature, no external control. The docstrings overstate it.

## 2. Threat model

| Attacker | Capability | Consequence |
|---|---|---|
| A1 application bug | inserts malformed rows | detectable by schema + verifier |
| A2 DB role with UPDATE/DELETE | edits or deletes rows | hash chain detects unless the whole chain is rewritten |
| A3 DB superuser | rewrites rows and recomputes the chain | **only an external anchor detects it** |
| A4 backup/storage admin | restores an older snapshot | anchor + sequence detects truncation |

A hash chain stored only in the same database does **not** stop A3. That is why an external anchor is required before using "tamper-evident".

## 3. Canonical record

```
audit_event {
  schema_version, event_id, sequence, recorded_at,
  actor_id, actor_type, action, target, target_type,
  payload_hash, payload (jsonb),
  prev_hash, entry_hash, key_id
}
entry_hash = SHA-256( canonical(schema_version,event_id,sequence,recorded_at,actor,action,target,payload_hash,prev_hash) )
```

Canonical serialization: UTF-8, sorted keys, no insignificant whitespace, RFC 3339 UTC timestamps with fixed precision.

## 4. Additive migration proposal (not applied)

1. Create `audit_chain` columns on a **new** table `audit_events_v2` (do not alter historical rows).
2. Backfill is **not** performed; historical audit rows keep no chain and are labelled `pre_chain=true`.
3. A before-insert trigger computes `entry_hash` and enforces `sequence = max(sequence)+1` under a row lock.
4. A `REVOKE UPDATE, DELETE` on the table from the application role.
5. A verifier command walks the chain and reports the first break, truncation, reorder and duplicate sequence.
6. Reversible: drop the new table and trigger; historical rows untouched.

## 5. External anchor interface

```
AnchorProvider.publish(anchor: {sequence, entry_hash, recorded_at}) -> {receipt, published_at}
AnchorProvider.verify(receipt) -> {ok, anchored_sequence, anchored_hash}
```

Requirements for a real provider: independent administrative control, append-only retention, verifiable timestamps, access separation, key custody, recovery and retention policy.

**No provider is approved.** Therefore:

- the design is complete;
- the migration is proposed;
- the verifier is specified;
- **no external anchoring exists**, so `tamper-evident` may not be claimed yet.

## 6. Verification tests (to run on disposable data only)

append · concurrent append · modify · delete · reorder · truncate · duplicate sequence · broken link · anchor mismatch · recovery after restart.

## 7. Status

`DESIGN_COMPLETE` · migration `NOT APPLIED` · external anchor `NOT CONFIGURED` · claim must remain "append-only, tamper-evidence pending".
