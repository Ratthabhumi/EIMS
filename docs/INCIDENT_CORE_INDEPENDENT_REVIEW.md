# Incident Core — Independent Review and Limitation Disposition

Original review: 2026-11-19, read-only reviewer (Claude Code CLI), of the
controlled rewrite `service.py` SHA-256 `E91AFE2A…7B63` (812 lines).
This document records that review, what changed since, and what remains.

Provenance reminder: the authentic original of `backend/domain/incident/service.py`
was never recovered (Cursor local history, Cursor global chat store, VS Code
history, git unreachable objects, filesystem). The file is a **controlled
rewrite** reconstructed from `correlation.py`, surviving call sites and tests.
Nothing here claims source recovery.

## 1. Original findings and disposition

| # | Finding (severity) | Disposition |
|---|---|---|
| 1 | `_reuse_incident` may drop a recurrence in some orderings (MEDIUM) | **Open — documented.** Recurrence is covered by `test_recurrence_after_closure_creates_new_open_incident`; no counter-example reproduced on PostgreSQL. Not changed in this round. |
| 2 | Terminal guard not race-safe (MEDIUM) | **Fixed.** `change_status` now does `SELECT … FOR UPDATE` + `populate_existing` and one commit; concurrent resolves serialise and the loser gets `IncidentTransitionRejected`. Proved by `test_concurrent_resolution_produces_one_authoritative_verification`. |
| 3 | Evidence attach swallowed `IntegrityError` (MEDIUM) | **Fixed.** Only the expected `23505` on `uq_incident_evidence_source` is treated as an idempotent duplicate; any other integrity failure is re-raised (`_is_duplicate_evidence`). |
| 4 | Caller-supplied digest trusted through a bypassed schema (LOW) | **Fixed for verification.** Resolution recomputes the digest from the stored row and rejects a mismatch (`evidence_digest_mismatch`). Attachment still stores a caller digest when supplied; such a row simply cannot verify resolution. |
| 5 | Service commits/rolls back the caller's session (LIMITATION) | **Documented + constrained.** `change_status` owns exactly one transaction and commits once; callers must pass a dedicated session. The API dependency provides one per request; tests use one per operation. |
| 6 | Unverified rewrite behaviours (`:r{bucket}`, `multi_source_no_positive_correlation`, earliest-observation-wins, caps/`merged_signatures`, `evidence_added` injection) | **Retained with justification.** They are exercised by the correlation/idempotency/API suites and the API contract (`summary.evidence_added` is asserted by `test_incident_api`). They do not affect the resolution invariant. Treated as behaviour of the controlled rewrite, not as documented v1 requirements. |

## 2. New defects found by the second independent pass

| Finding | Severity | Status |
|---|---|---|
| Raw `UPDATE incidents SET status='resolved'` bypassed the service invariant | HIGH | **Fixed** — PostgreSQL `BEFORE UPDATE OF status` trigger requires a `passed` verification row for the current cycle. Test: `test_raw_sql_cannot_resolve_without_verification`. |
| Verification history could be `TRUNCATE`d | MEDIUM | **Fixed** — `BEFORE TRUNCATE … FOR EACH STATEMENT` trigger. Test covers UPDATE, DELETE and TRUNCATE. |
| A verifier could verify evidence they attached | MEDIUM | **Fixed** — `verifier_conflict`. Test: `test_verifier_cannot_verify_evidence_they_attached`. |
| Non-canonical `analysis` source ids (`01`, `+1`) and NULL-asset observations could verify | MEDIUM | **Fixed** — canonical decimal + 32-bit bound + strict asset match. Test: `test_non_canonical_source_id_is_rejected`, `test_analysis_observation_for_another_asset_is_rejected`. |
| Oversized all-digit id produced a raw DB error instead of a validation code | MEDIUM | **Fixed** — `source_pk > 2**31-1` rejected as `evidence_source_malformed`. |
| `SELECT … FOR UPDATE` did not refresh a session-cached `Incident` | LOW | **Fixed** — `populate_existing=True`. |

## 3. Current PostgreSQL evidence

Command (disposable container `eims-recovery-pg-20261119`, db/role
`eims_incident_test`, `rolsuper=f`):

```
pytest tests/test_incident_api.py tests/test_incident_correlation.py \
       tests/test_incident_idempotency.py tests/test_incident_lifecycle.py \
       tests/test_incident_migration.py tests/test_incident_verification_pg.py \
       tests/test_incident_engineer_workflow_pg.py tests/test_api_identity_pg.py \
       tests/test_db_identity_pg.py tests/test_worker_identity_pg.py \
       tests/test_connection_invalidation_pg.py
-> 106 passed, exit 0
```

Baseline preservation: the original 61-test incident suite still passes; the
four lifecycle resolutions and the API resolution were updated to the new
contract (they now attach verification-grade evidence and resolve as a
reviewer). No assertion was removed or weakened; the new tests add persisted
state assertions.

## 4. Decision

**Incident Core: ACCEPTED WITH LIMITATIONS.**

Accepted: creation, correlation, reuse, dedupe/idempotency, evidence attachment,
lifecycle edges, API, rollback, migration, and the new verified-resolution
invariant with database-level enforcement.

Limitations: recurrence ordering (finding 1) is not exhaustively proved; the
rewrite-specific behaviours in finding 6 are supported by tests but not by the
2026-11-16 specification; a raw `INSERT` of an already-`resolved` incident or of
a `passed` verification row is not blocked by the triggers (they guard
`UPDATE`/`DELETE`); the test-schema trigger DDL is a hand-copy of the migration
DDL and could drift.
