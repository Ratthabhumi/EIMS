# 2026-11-20 — Cursor Incident Notes Integration + Browser Acceptance

**Branch / HEAD:** `demo/2026-11-24` @ `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de`  
**Verdict:** **ACCEPTED WITH LIMITATIONS**  
**Owner:** Cursor (frontend only)  
**Not claimed:** Product Acceptance / full E2E product closure

## Backend version / migration head tested

| Item | Value |
|---|---|
| Disposable PostgreSQL | `eims-knowledge-b-pg-20261119` → `127.0.0.1:56470` |
| Database | `eims_e2e_test` (Claude E2E disposable; non-superuser `eims_incident_test`) |
| Alembic head on DB | `a7d2c5e8f604` (Notes migration present; `incident_note` table verified) |
| API process | uvicorn `127.0.0.1:8022` against that DB (`EIMS_DEMO_SOFT_DEPS=1`) |
| Portal | Next.js `127.0.0.1:3001` with `EIMS_BACKEND_URL=http://127.0.0.1:8022` |
| Not used | Operational PG `:5432`; older portal-accept API `:8021` / `:56456`; `start_eims.bat` |

Note: tree also contains unapplied revision `b8e3f6a9c715` (provider scope). Disposable DB under test remained at `a7d2c5e8f604`. Notes do not require that later revision.

## Notes API contract (verified in source + runtime)

| Call | Contract |
|---|---|
| `POST /api/v1/incidents/{id}/notes` | Body `{ "text": "1..4000" }` only (`extra=forbid`). `201` → `{ note_id, incident_id, text, actor, actor_assurance, created_at }` |
| `GET /api/v1/incidents/{id}/notes?limit&offset` | Oldest first; array response; `X-Total-Count` |
| Actor / assurance | Server-derived. Open access → `demo` / `unattributed` |
| Semantics | Observation only — not diagnosis / verification / resolution |

Runtime probes on `:8022` returned `GET 200` and `POST 201` against incident `6478f129-8c7a-42cc-aa73-f1a33141a236`.

## Files changed (frontend)

| File | Change |
|---|---|
| `clients/dashboard/src/components/incidents/EngineerNotes.tsx` | Real API load/create; auto-load; busy/duplicate-submit guard; retry; honest unattributed labeling; default `apiEnabled=true` |
| `clients/dashboard/src/components/incidents/IncidentWorkspace.tsx` | Enable Notes (remove `apiEnabled={false}`) |
| `clients/dashboard/src/lib/incident-orchestration.ts` | Ambiguous message + `summary.correlation.candidates` passthrough; still never clear-success |
| `clients/dashboard/src/components/incidents/EventIncidentLink.tsx` | Ambiguous banner/candidates; distinct CTA wording |
| `clients/dashboard/src/components/KnowledgeMatchBadge.tsx` | Display `matchKind` / `matchBasis` when server supplies them |
| `clients/dashboard/scripts/check-engineer-notes.mjs` | New contract self-check |
| `clients/dashboard/scripts/check-incident-orchestration.mjs` | Ambiguous candidates shape |
| `docs/acceptance/2026-11-20-cursor-incident-notes-integration.md` | This report |

No backend / migration / backend-test edits. No commit/push.

## Notes persistence evidence

1. Opened deep link `/analyzer?incident=6478f129-…` on Claude disposable backend.
2. Loaded existing notes (including Claude E2E note + prior API probe).
3. Browser **Add Note**: `browser acceptance note — persistence check`.
4. UI showed **Saving…** (disabled) then listed the new note with server timestamp + `demo (unattributed — not a verified person)`.
5. Full page reload → all **3** notes still present (API `GET` count=3 confirmed).
6. Audit trail shows `note noted by demo Unattributed` entries.
7. No localStorage / sessionStorage for notes.

## Actor / assurance display

- Unattributed notes render `actor (unattributed — not a verified person)` with assurance title tooltip.
- Does not invent a verified person identity.
- Confirmed diagnosis actors remain distinct (`e2e-reviewer` / Verified identity).

## Ambiguous association result

| Check | Result |
|---|---|
| Code: `ambiguous_not_merged` + `created:true` → outcome `ambiguous` | **PASS** (`check-incident-orchestration.mjs`) |
| Code: `isClearAssociationSuccess(ambiguous) === false` | **PASS** |
| UI: candidates list + “Ambiguous — not correlated” badge | Implemented |
| Browser Analyze → live `ambiguous_not_merged` response | **NOT PROVEN this pass** (no controlled live fixture produced in browser; do not claim Scenario C browser PASS) |

## Partial-load behavior

- Preserved: core `GET /incidents/{id}` succeeds independently of secondary failures.
- On Claude `:8022` / `eims_e2e_test`, diagnoses / remediations / workflow-events / knowledge-proposals returned **200** for the tested incident (panels populated).
- Secondary failure path from prior closure remains in `IncidentWorkspace` (settle + alert).

## Knowledge presentation

- Live catalog summary: `total_records=175`; `operational_context=153`; `diagnostic_candidates=22`; **approved=0**.
- UI: `Diagnostic Knowledge Catalog (175)` with Candidate/Reference honesty copy; not hardcoded 163.
- `KnowledgeMatchBadge` shows `matchKind`/`matchBasis` only when present on the analysis payload.

## Browser scenarios

| Scenario | Result | Evidence |
|---|---|---|
| A. Notes load/add/reload/actor | **PASS** | 3 notes after reload; unattributed labels; Saving… guard |
| B. Lifecycle presentation | **PASS** | Confirmed cause vs hypothesis labeling; remediation Executed/verified distinct from Resolved status (`status=resolved` via API; Fix executed ≠ silent auto-resolve in UI copy) |
| C. Ambiguous association UI | **LIMITED** | Mapping tests PASS; live browser response not captured |
| D. Partial load | **PASS** (current backend healthy) / prior settle code retained | Diagnoses 200 on `:8022` |
| E. Knowledge | **PASS** | 175 live; Candidate labels; 0 approved |
| F. Navigation / Settings / Infra | **PASS** | Close → Current issues list; deep link reload; Theme + Runtime Health; System & Infra five entries (Grafana, MinIO, Prometheus, Core API Docs, Settings) |

## Test results

| Check | Result |
|---|---|
| `check-incident-orchestration.mjs` | **PASS** |
| `check-evidence-presentation.mjs` | **PASS** |
| `check-engineer-notes.mjs` | **PASS** |
| `npx tsc --noEmit` | **PASS** |
| ESLint on touched Notes/orchestration/KnowledgeMatch files | Clean after removing reset-effect; residual repo `any` debt elsewhere unchanged |

## Exact remaining limitations

1. **Scenario C browser** — live `ambiguous_not_merged` Analyze journey not re-proven in the browser this pass.
2. Tree has newer migration `b8e3f6a9c715` not applied on the tested disposable DB (Notes do not require it).
3. Knowledge still has **0** approved / source-verified records (Claude backend limitation).
4. Sidebar hydration warning remains (pre-existing).
5. Product Acceptance / full Evidence→Resolve chain still requires joint Claude+Cursor closure.

## Worktree preservation

Porcelain dirty tree preserved. No `git reset/clean/stash/commit/push`. Operational database untouched.
