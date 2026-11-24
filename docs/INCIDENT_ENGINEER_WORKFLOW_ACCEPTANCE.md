# Incident Engineer Workflow Acceptance

Date: 2026-11-19
Test: `tests/test_incident_engineer_workflow_pg.py` (PostgreSQL disposable)
Status: **PASS 2/2** — journey + self-authorisation guard

## What an engineer can actually do today (backend/API)

| Step | Capability | Path |
|---|---|---|
| Detect / record | create an incident from one or more evidence references | `POST /api/v1/incidents` |
| Correlate | further evidence merges into the same incident by asset+signature window | `POST /api/v1/incidents/{id}/evidence` |
| Investigate | list/detail incident, read bounded correlation summary and evidence refs | `GET /api/v1/incidents`, `/{id}` |
| Record remediation observation | attach an `analysis` evidence reference (reference-only) | `POST /{id}/evidence` |
| Attempt resolution | `PATCH /{id}/status {"status":"resolved"}` | blocked without verification |
| Verify | reviewer supplies `verification.evidence_id`; server revalidates | `PATCH /{id}/status` |
| Prove / audit | detail returns `verifications[]` with verifier, time, cycle, digest; audit rows carry `verification_id` | `GET /{id}` |
| Reopen | `resolved -> investigating`, increments the remediation cycle | `PATCH /{id}/status` |
| Re-verify | new cycle needs new evidence; old evidence is rejected as stale | `PATCH /{id}/status` |

## The journey proved on PostgreSQL

1. Create an incident from a winlog reference on a synthetic asset (status `open`).
2. Attach a second winlog reference with the same signature inside the window —
   it merges into the same incident (`added == 1`, same `incident_id`).
3. `triage`, then `investigating`.
4. Attempt `resolved` with no verification → `IncidentValidationError`
   (`missing_verification`); persisted status stays `investigating`, cycle 0,
   zero verification rows.
5. Attach an `analysis` observation (the only verification-grade source type).
6. Resolve as `reviewer` with `verification.evidence_id` → status `resolved`.
7. Read back from a fresh session: 3 evidence rows
   (`winlog, winlog, analysis`), one verification row
   (`outcome=passed`, `remediation_cycle=0`, `verifier_id=reviewer`,
   `evidence_id` = the supplied one, `verified_at` set), and audit rows
   `triage -> investigating -> resolved` where the last one carries
   `verifier`, `verification_id`, `remediation_cycle`, `verified_evidence_id`.
8. Reopen → status `investigating`, cycle `1`.
9. Attempt `resolved` with the cycle-0 evidence → `evidence_stale`; status stays
   `investigating`, still exactly one verification row.
10. Attach a fresh `analysis` observation and resolve → `resolved`, cycle `1`.
11. Read back: verification history is `[cycle 0, cycle 1]`, both `passed`, both
    verified by `reviewer`, with different evidence ids. Nothing was deleted.

The second test proves an **engineer** (authenticated, not a reviewer) cannot
self-authorise: resolving with `verifier="engineer"` raises
`IncidentPermissionError`, status stays `investigating`, and no verification row
is written.

## Questions the persisted record answers

| Question | Answered by |
|---|---|
| What happened? | incident title, evidence refs, correlation summary |
| What evidence supports it? | `evidence[]` (`source_type`, `source_id`, `observed_at`, `added_by`) |
| What remediation was verified? | `verifications[].evidence_id` → evidence row; `evidence_digest` |
| Who verified it and when? | `verifications[].verifier_id`, `verified_at` |
| Which remediation cycle? | `remediation_cycle` on incident and on each verification |
| Why was resolution allowed or blocked? | 422/403 detail code (`missing_verification`, `evidence_stale`, `verifier_unauthorized`, …) |
| What changed on reopen? | cycle increment + new `remediation_started_at`; old rows retained |

## What is NOT implemented (do not claim it)

- **No incident UI.** The dashboard has no incidents page; all of the above is
  API/service level. No badge or button claims a resolved state.
- **No first-class diagnosis / remediation-action record.** There is no
  remediation table or endpoint. `root_cause_state` and `incidents.summary` are
  the only places to record reasoning, and `root_cause_state` has no API
  mutation in this revision. This is a product gap, not a hidden feature.
- **No residual-risk field.** Residual risk must live in `summary` free text.
- **No external health probe.** Verification proves persisted evidence, not that
  an external system is currently healthy.
- **Ingest worker path** (`incident_ingest`) can create incidents but cannot
  resolve them, so it is outside the invariant. Its own integration suite needs
  `EIMS_INGEST_TEST_DATABASE_URL` / `EIMS_INGEST_TEST_REDIS_URL` /
  `EIMS_INGEST_TEST_SENTINEL` and was **not run** in this round.

## Decision

**Engineer workflow: ACCEPTED WITH LIMITATIONS** — the detect → evidence →
verify → resolve → reopen journey is enforced and auditable on PostgreSQL; the
diagnosis/remediation capture surfaces and any UI are not implemented.
