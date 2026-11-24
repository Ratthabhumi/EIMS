# Engineering workflow (Observation → Resolution) — existing implementation and gaps, 2026-11-19

**Decision: no new workflow code was written.** The Incident Core (`backend/domain/incident/`, a separate accepted domain outside Workstream B's ownership) already implements this lifecycle with persisted, tested guarantees. Building a parallel workflow in the Knowledge package would duplicate it (project rule: reuse existing implementations).

## Stage mapping (evidence from code and tests)
| Stage | Existing implementation |
|---|---|
| Observation | Analyses enqueue to the ingest outbox in the same transaction (`enqueue_analysis_history`); `IncidentService.create_from_evidence` opens an incident (`status=open`) from bounded evidence references with digests; no raw payloads. |
| Investigation | Lifecycle `open → triage → investigating → resolved → closed` with one reopen edge (`validate_transition`). |
| Evidence | `attach_evidence`, `source_type/source_id` + digest, deterministic dedupe; correlation `confidence` describes correlation strength only, never causality. |
| Diagnosis | `root_cause_state` ∈ `unknown / hypothesis / confirmed`, "never set automatically to causality". Analyzer knowledge trust is now exposed separately as `solutionSummary.knowledgeMatch` and never changes it. |
| Remediation | `remediation_cycle` / `remediation_started_at`: reopening increments the cycle; evidence from an earlier cycle cannot verify the current one. |
| Verification | Append-only `incident_verification` (UPDATE/DELETE rejected); evidence must be persisted, belong to the incident, be of a type that can prove an outcome, have an intact digest, postdate the current remediation start; verifier must be an authorised identity and cannot verify evidence they attached. |
| Resolution | `PATCH /{id}/status` to `resolved` requires `verification.evidence_id`; raw SQL cannot resolve without verification; resolution and verification+audit are one transaction; closing requires a knowledge-reviewer capability. |

## Fresh evidence (current working tree, disposable PostgreSQL, 2026-11-19)
`tests/test_incident_verification_pg.py`, `test_incident_engineer_workflow_pg.py`, `test_incident_lifecycle.py`, `test_incident_api.py`: **58 passed, 1 failed**. The failure is `test_unauthenticated_requests_are_rejected` (`200 == 401`), the same auth-mode symptom caused by uncommitted changes elsewhere in the tree that retire application login; not related to this workflow. Not proven against a clean baseline.

## Genuine gaps (not implemented; need an owner decision because they are Incident Core changes)
1. **No way to record a diagnosis.** `root_cause_state` is only ever written as `"unknown"` at creation (`service.py:498`); there is no route or service method to record a hypothesis or confirmation, with audit and authorisation.
2. **No remediation record.** Only a cycle counter exists; what was changed, by whom and when is not captured.
3. **No link between an incident and the knowledge used.** Incidents carry no `catalog_id` / classification, so the Portal cannot show which knowledge (and at what trust level) supported a diagnosis.
4. **No UI.** `clients/dashboard/src` has no incident view.

## Rules any extension must keep
Knowledge classification may support a hypothesis but must never set `confirmed` by itself; `confirmed` and remediation entries need an authenticated human actor and an audit event; resolution keeps requiring current-cycle verification evidence. Because the verification and ingest paths are accepted evidence, changes need a migration, regression tests and independent review.

## Update (later 2026-11-19): gaps 1–3 addressed by an additive extension
Owner approved the "honest assurance tiers" attribution model (no application login; no invented identities). Implemented in the existing Incident Core, not a parallel workflow:
- Migration `c3e6a9d1f402` adds `incident_diagnosis`, `incident_remediation`, `incident_workflow_event` (append-only trigger). Nothing existing is altered.
- `actor_assurance` is derived server-side from the credential: none → `unattributed` (identifier `demo`), shared admin token → `shared-token` (identifier `shared-admin-token`, never "admin"), valid session JWT for a user → `verified-identity`. Request bodies forbid actor/assurance/knowledge/verification fields.
- Hypotheses, remediation proposals and execution records are open to all three tiers. Root-cause confirmation requires verified-identity **and** the existing reviewer capability, supporting evidence, a confirmer different from a verified proposer, and one confirmed diagnosis per cycle. `resolved`/`closed` on `PATCH /{id}/status` now additionally require verified-identity (this closes a path where the shared token resolved to the literal name "admin" and could satisfy the reviewer lookup).
- Knowledge link: `catalog_id` is optional on a diagnosis; the server snapshots classification, lifecycle status, stale/overlay flags, version scope/compatibility and the canonical content hash at that moment. Clients cannot supply it.
- Remediation `verification_state` is derived from `incident_verification` (same cycle, passed, recorded after execution) and is never writable.
Still open: gap 4 (no incident UI); no reject/supersede for hypotheses; no pagination on the new list routes.
