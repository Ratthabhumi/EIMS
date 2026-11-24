# Claude — Backend gap report for Automatic Incident Intelligence

**Date:** 2026-11-20  
**From:** Cursor frontend workstream  
**Branch/HEAD context:** `demo/2026-11-24` @ `3f2beea`

Cursor wired the Analyzer to **existing** Incident Core HTTP contracts only. The following gaps block declaring the full automatic journey ACCEPTED.

---

## 1. Engineer Notes API (blocking for Notes UX)

| | |
|---|---|
| **Existing** | Diagnosis hypotheses, remediation `outcome_notes`, workflow-events audit. None is a lightweight engineer observation note. |
| **Missing** | `POST/GET` notes scoped to an incident: text, timestamp, actor, actor_assurance, chronological list. |
| **Proposed contract** | `POST /api/v1/incidents/{id}/notes` body `{ text: string(1..4000) }` → `{ note_id, text, created_at, actor, actor_assurance }`. `GET .../notes?limit&offset` with `X-Total-Count`. |
| **Safety** | Notes are observations, never auto-confirm root cause / resolve / verify. Unattributed actors allowed to append; privileged lifecycle unchanged. |
| **Tests** | Create note → list order; cannot escalate assurance; no promotion to diagnosis. |

Do **not** use workflow-events as a fake notes API from the frontend.

---

## 2. Explicit association outcome for “ambiguous / no safe correlate”

| | |
|---|---|
| **Existing** | `match`: `created` \| `event_already_linked` \| `correlated_with_open_incident`. |
| **Missing** | A response that tells the UI correlation was considered but left unresolved (keep separate) without implying failure. |
| **Proposed** | Optional `match: "uncorrelated"` or `correlation.status: "unresolved"` when create succeeds as a new incident **after** candidates were inspected and rejected. |
| **Safety** | Never instruct the frontend to merge. |
| **Tests** | Two analyses without asset/key remain separate; response documents why. |

---

## 3. Analyze → incident orchestration convenience (optional)

| | |
|---|---|
| **Existing** | Analyze returns `historyId`; FE calls ensure separately. Idempotent. |
| **Missing (optional)** | Analyze response field `incident_association: { incident_id, created, match } \| null` when server-side ensure runs in the same transaction as history insert. |
| **Safety** | Must reuse `create_from_evidence`; must not create duplicates; must not run if history persist fails. |
| **Tests** | Analyze twice with same stored history id → same incident; two history ids without correlate identity → two incidents. |

Frontend already works without this; it reduces race/latency only.

---

## 4. List summary fields for Incident Workspace landing

| | |
|---|---|
| **Existing** | List returns status, severity, title, timestamps, confidence, root_cause_state. |
| **Missing (nice-to-have)** | `evidence_count`, `last_activity_at`, verification summary flag, asset display name. |
| **Proposed** | Add read-only summary fields on `IncidentResponse` / list DTO. |
| **Safety** | Read-only; no new mutations. |
| **Tests** | Counts match detail evidence length. |

---

## 5. Preserve / document Event ID correlation without asset

Already implemented: same `source_event_key` + unresolved asset within window can correlate (medium). Cursor now passes Event ID when usable.

**Ask Claude:** confirm this remains intentional for analysis-sourced evidence; add regression if not already covered for `source_type=analysis` without `asset_id`.

---

## Cursor will not

- Invent a notes store in localStorage
- Frontend-merge incidents
- Edit Incident Core service/schema/migrations
- Claim shared-runtime acceptance until these contracts (at least Notes + proven idempotent browser path) are evidenced
