# 2026-11-20 — Cursor Backend Integration Readiness

**Workstream:** Frontend Acceptance, UX Integrity & Backend Integration Readiness  
**Branch / HEAD (verified this pass):** `demo/2026-11-24` @ `3f2beea`  
**Working tree:** pre-existing dirty tree preserved; **no stage/commit/push**  
**Claude ownership:** `backend/**` untouched by this Cursor pass

## Verdict

**ACCEPTED WITH LIMITATIONS** (frontend-only)

Independent FE progress completed without inventing APIs, without FE-only correlation/dedupe stores, and without waiting for Claude. Full Automatic Incident product acceptance remains blocked on Claude Notes + correlation outcome contracts + retained shared-runtime evidence.

---

## 1. Existing backend endpoints actually consumed

| Endpoint | Status | Frontend use |
|---|---|---|
| `POST /api/v1/analyze/` (+ `/bundle`) | **Existing and verified** | Evidence submit |
| `GET /api/v1/history/` | **Existing and verified** | Analysis History |
| `GET /api/v1/history/catalog` | **Existing and verified** | Knowledge Catalog list |
| `GET /api/v1/incidents/by-evidence` | **Existing and verified** | Association lookup |
| `POST /api/v1/incidents` | **Existing and verified** | `create_from_evidence` ensure |
| `POST /api/v1/incidents/{id}/evidence` | **Existing and verified** | Advanced manual link |
| `GET /api/v1/incidents` | **Existing and verified** | Open-issue landing |
| `GET /api/v1/incidents/{id}` (+ diagnoses/remediations/workflow-events/knowledge-proposals) | **Existing and verified** | Incident detail |
| `GET/POST /api/v1/incidents/{id}/notes` | **Missing** | Prepared in `EngineerNotes.tsx` behind `apiEnabled=false` |

## 2. Existing request/response fields used

**Ensure create**

- Request: `title?`, `severity?`, `evidence[]` with `source_type=analysis`, `source_id=<historyId>`, `observed_at`, optional `source_event_key`
- Response: `incident_id`, `created`, `match`, `title`, `status`, `severity`, `root_cause_state`, `evidence[]`, `summary.correlation?`

**Match values handled by FE today**

| `match` | FE outcome | Auto-open Workspace |
|---|---|---|
| `created` / `created:true` | created | Yes |
| `correlated_with_open_incident` | correlated | Yes |
| `event_already_linked` | already_linked | Yes |
| `uncorrelated` / `ambiguous` / `correlation_unresolved` | ambiguous | **No** (proposed; not emitted by backend yet) |
| unrecognized + id | ambiguous | No |
| no id / error | failed | No |

## 3. Missing backend capabilities

| Capability | Label |
|---|---|
| Engineer Notes API | **Missing** |
| Explicit ambiguous / unresolved correlation match | **Missing** (FE ready to display) |
| Evidence identity stronger than message text (EventRecordID, offsets) for presentation | **Missing / partial** — FE no longer collapses by text |
| Analyze response embedding `incident_association` | **Proposed** (optional convenience) |
| List DTO: evidence_count, last_activity, asset display | **Proposed** (nice-to-have) |

## 4. Engineer Notes contract requirements (**Proposed**)

```
GET  /api/v1/incidents/{id}/notes?limit=&offset=
  → Note[]  (+ X-Total-Count preferred)
POST /api/v1/incidents/{id}/notes
  body: { text: string(1..4000) }
  → { note_id, text, created_at, actor, actor_assurance }
```

Safety: notes are observations; never confirm root cause / verify / resolve.  
FE integration point: `clients/dashboard/src/components/incidents/EngineerNotes.tsx` — set `apiEnabled={true}` when live.

**Not yet tested** against a real Notes API.

## 5. Evidence identity fields needed for safe presentation

| Field | Status |
|---|---|
| Preserve raw `solutionSummary.evidence` / `evidenceItems` arrays | **Existing** — FE displays as-is (unsafe text collapse **removed** this pass) |
| `sourceFile`, `lineNumber`, `sourceContext`, `sourceContextOrigin` | **Existing** — labeled as excerpt line / reported offset |
| Distinct event identity (EventRecordID / TimeCreated) | **Missing** for pasted text path — FE must not invent |
| Chronology First/Last | FE shows only when failure texts differ **and** at least one evidence timestamp exists |

## 6. Correlation outcomes required by the frontend

| Outcome | Status |
|---|---|
| created / correlated / already_linked / failed | **Existing and verified** |
| ambiguous / uncorrelated | **Proposed** — FE maps if/when backend emits |
| FE merge of incidents | **Not implemented** (forbidden) |

## 7. Provider-aware Knowledge match metadata

| Need | Status |
|---|---|
| Catalog `verification_status`, `support_level` | **Existing** — shown in UI |
| `knowledge_class` / `lifecycle_status` for candidate vs reference | **Existing when API sends** — FE badges Candidate vs Reference |
| Count of operational vs candidates | **Existing** from inventory fields when present |
| Implying candidate = approved | **Not done** — copy states otherwise |

## 8. Mismatches / assumptions corrected this pass

| Assumption | Correction |
|---|---|
| FE may hide duplicate evidence strings | **Removed** — can hide distinct events |
| Timeline length > 1 ⇒ First/Last chronology | **Removed** — need timestamps |
| Stay on report after association | **Changed** — auto-open Workspace only for clear success outcomes |
| Ambiguous should look like success | **No** — amber banner; no auto-navigate |
| Double ensure from Strict Mode | **Mitigated** with in-flight + per-historyId ref |

## 9. Files modified (this Cursor parallel pass)

- `clients/dashboard/src/components/AnalysisResultDetail.tsx`
- `clients/dashboard/src/app/analyzer/page.tsx`
- `clients/dashboard/src/components/incidents/EventIncidentLink.tsx`
- `clients/dashboard/src/components/incidents/IncidentWorkspace.tsx`
- `clients/dashboard/src/components/incidents/EngineerNotes.tsx` (**new**)
- `clients/dashboard/src/components/AnalyzerHistoryList.tsx`
- `clients/dashboard/src/lib/incident-orchestration.ts`
- `clients/dashboard/scripts/check-incident-orchestration.mjs`
- `docs/acceptance/2026-11-20-cursor-backend-integration-readiness.md` (**this file**)

## 10. Tests and browser scenarios

| Check | Result |
|---|---|
| `node clients/dashboard/scripts/check-incident-orchestration.mjs` | Run this pass |
| `npx tsc --noEmit` | Run this pass |
| Browser Portal `:3001` Analyze→Incident, nav, Knowledge, Settings | Run this pass — record exact outcomes in companion acceptance note |
| Notes write path | **Not yet tested** (API missing) |
| Ambiguous match from live backend | **Not yet tested** (API does not emit) |

## 11. Exact limitations

1. Notes cannot be persisted until Claude ships the API.
2. Ambiguous correlation UX is ready but unproven against live responses.
3. Broad ESLint debt in AnalyzerHistoryList (`any`, etc.) not fully cleared — only render-purity timing moved out of `useMemo`.
4. Full Browser Acceptance for product gate still **NOT PASSED** until Claude backend + correlated evidence retained.
5. Knowledge inventory split (141/22) depends on API fields `knowledge_class` / counts; UI shows whatever the catalog endpoint returns.

## Labels legend used above

- **Existing and verified** — used by FE against live/current contract  
- **Missing** — required for complete journey  
- **Proposed** — contract for Claude; not claimed to exist  
- **Not yet tested** — FE ready or partial; no live proof
