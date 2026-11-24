# 2026-11-20 — Cursor Frontend Integration Closure

**Branch / HEAD:** `demo/2026-11-24` @ `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de`  
**Verdict:** **ACCEPTED WITH LIMITATIONS**  
**Owner this pass:** Cursor (frontend only)  
**Not claimed:** Full Frontend Product Acceptance / Full E2E product acceptance

## 1. Baseline verified (not repeated as UX redesign)

Prior accepted work retained:
- Automatic association outcomes including ambiguous-first mapping (`ambiguous_not_merged` before `created`).
- Workspace auto-open only on clear success (`created` / `correlated` / `already_linked` with incident id).
- Unsafe frontend evidence text-collapse removed.
- Chronology requires actual timestamps.
- `EngineerNotes.tsx` with `apiEnabled=false`, no localStorage.
- Knowledge Candidate vs Reference labeling.
- No inventing of backend endpoints or match values.

This pass closed integration readiness gaps: contract matrix against live code/runtime, disposable browser acceptance, workspace partial-load resilience, evidence regression scripts, targeted type/lint debt that blocked `tsc`.

## 2. Worktree preservation

- No `git reset` / `git clean` / stash / commit / push.
- No edits under `backend/**` by Cursor this pass.
- Pre-existing dirty tree (including Claude-owned backend files) preserved.
- Disposable runtime only: PostgreSQL comment `EIMS-DISPOSABLE-portal-accept-20261119` on `:56456`; API `:8021`; Portal `:3001` with BFF → `8021`.
- Did **not** run `start_eims.bat` (historically runs Alembic against shared DB).
- Did **not** run `docker compose down -v` or touch Operational DB / port `5432`.

## 3. Frontend files changed this closure pass

| File | Change |
|---|---|
| `clients/dashboard/src/components/incidents/IncidentWorkspace.tsx` | Load incident detail independently; tolerate secondary workflow endpoint failures without blanking the whole workspace |
| `clients/dashboard/src/components/AnalyzerHistoryList.tsx` | Remove dead `searchLatencyMs: null` that broke `tsc` (`never`); omit unused `onSearchLatency` destructure after pure-ranking change |
| `clients/dashboard/src/components/incidents/EngineerNotes.tsx` | Document source Notes contract vs runtime 404; keep `apiEnabled=false` |
| `docs/acceptance/2026-11-20-cursor-frontend-integration-closure.md` | This report |

Scripts used (already present): `clients/dashboard/scripts/check-incident-orchestration.mjs`, `check-evidence-presentation.mjs`.

## 4. Backend contracts verified

Classification legend: **Code** = present in shared worktree source; **Runtime** = exercised against disposable `:8021` this pass; **FE** = frontend mapping only; **Missing** = not available; **Not tested** = not exercised this pass.

### Contract matrix

| Feature | Existing verified API | Fields consumed | Missing fields | Frontend behavior | Class |
|---|---|---|---|---|---|
| Analyze (text) | `POST` analyzer analyze path via BFF `/api/eims/...` | history id, event fields, evidence excerpts | — | Submits paste; opens Event Detail | Runtime |
| Event Detail | Analysis history record payload | event id, provider, excerpts, timestamps when present | — | Honest chronology; excerpt offsets; no text-collapse | Runtime |
| Auto association lookup | `GET /api/v1/incidents/by-evidence` | linked incident row | — | Prefer existing link before create | Code + FE (guard) |
| Auto association create | `POST /api/v1/incidents` (`create_from_evidence`) | `incident_id`, `created`, `match`, title/status/severity/root_cause_state | — | Map match enum; auto-open only clear success | Code + Runtime (created / already_linked) |
| Match enum | `schemas.py` `match` | `created` \| `event_already_linked` \| `correlated_with_open_incident` \| `ambiguous_not_merged` | — | FE outcomes: created / already_linked / correlated / ambiguous / failed / unavailable | Code verified; ambiguous **Not tested** at runtime |
| Incident detail | `GET /api/v1/incidents/{id}` | `incident_id`, title, status, severity, confidence, evidence[], first/last_seen | `match`/`created` absent on GET (POST-only) | Workspace header + evidence count | Runtime |
| Diagnoses / remediations / workflow-events / knowledge-proposals | `GET .../diagnoses` etc. | list pages | — | Secondary panels; empty + alert if fail | Code present; Runtime **500** on disposable |
| Notes | `GET/POST /api/v1/incidents/{id}/notes` | `note_id`, `text` (body alias), `actor`, `actor_assurance`, `created_at` | Runtime mount | UI stub; `apiEnabled=false` | Code verified; Runtime **404** |
| Catalog summary | `GET /api/v1/analyzer/catalog/summary` | `total_records`, `counts.*` | — | Live count 175; Candidate/Reference badges | Runtime |
| Catalog inventory | catalog list fetch used by AnalyzerHistoryList | `knowledge_class` / lifecycle fields when present | Provider match provenance when absent | No hard-coded 163; no fake Exact/Ambiguous match | Runtime |
| Knowledge proposals review | `/api/v1/knowledge/...` | review status | — | Link out; not auto-approve | Not tested deeply |

### Match → FE outcome (no silent success mapping)

| Backend `match` | FE outcome | Auto-open Workspace |
|---|---|---|
| `created` | `created` | Yes (with id) |
| `correlated_with_open_incident` | `correlated` | Yes |
| `event_already_linked` | `already_linked` | Yes |
| `ambiguous_not_merged` (even if `created=true`) | `ambiguous` | **No** |
| unknown / missing id | `failed` / safe fallback | No |
| by-evidence empty + create skipped | `unavailable` / no association messaging | No (analysis still valid) |

## 5. Backend contracts still missing / blocked

1. **Runtime Notes API** — source exists (`controller.py` NoteCreateRequest/NoteResponse) but disposable process returned **404** for GET/POST notes. FE stays `apiEnabled=false`.
2. **Runtime ambiguous match** — no controlled `ambiguous_not_merged` response observed this pass; FE mapping unit-checked; live UX **blocked** for full acceptance.
3. **Workflow sub-routes** — diagnoses / remediations / workflow-events / knowledge-proposals returned **500** on disposable (`Internal Infrastructure Server Exception`). Claude ownership. FE now shows incident shell + explicit secondary error instead of total blank.
4. **Provider-aware match provenance** (Exact / Contextual / No / Ambiguous knowledge match) — not simulated; display only when backend supplies it.
5. **OpenAPI** on `:8021` returned 404 — docs surface not available on this runtime.

## 6. Automatic Incident outcome behavior

- **created / already_linked:** Proven on disposable browser. Event 1026 Analyze → incident `48eb0b9d-c419-4d7b-946e-65d7b747e7ec` auto-opened. Re-open Event Detail shows *“Evidence already linked; existing incident opened.”* with Review button.
- **ambiguous:** FE ready (`outcomeFromCreate` checks ambiguous before created). Real-runtime acceptance **blocked**.
- **failed / no_association:** FE messaging distinguishes association failure from analysis failure; not exhaustively browser-forced this pass.
- Duplicate ensure guarded by in-flight + per-historyId (`EventIncidentLink`); backend idempotency remains source of truth.

## 7. Evidence presentation regression

Script: `check-evidence-presentation.mjs` → **PASS**.

Browser Event 1026 detail:
- Distinct observed evidence lines remain separate (excerpt lines 6 and 7).
- Copy states excerpt positions are **not** guaranteed original file lines.
- “Chronology could not be established from the supplied evidence.”
- “Physical root cause is not established by these signals alone.”
- Analysis History keeps three separate records (including two similarly titled App Error rows) — no FE identity collapse.
- No frontend correlation/dedupe engine added.

## 8. Engineer Notes readiness

- Component ready: load / empty / validation / error / retry paths behind `apiEnabled`.
- Display contract aligned with Claude source: text, timestamp, actor, actor_assurance, note_id, chronological order.
- **Runtime:** Notes endpoints 404 on disposable API → `apiEnabled` remains **false**; UI shows honest gap; nothing stored in browser.

## 9. Knowledge presentation

- Runtime catalog summary: `total_records=175`; counts include `operational_context=153`, `diagnostic_candidates=22`.
- UI: `Diagnostic Knowledge Catalog (175)` and `175 records (153 operational/reference · 22 diagnostic candidates) · Not validated solutions · Context ≠ root cause`.
- Candidate / Reference badges visible on entries.
- No hard-coded historical 163.
- Approval never inferred from mere catalog presence.
- Provider match Exact/Contextual/No/Ambiguous **not simulated**.

## 10. TypeScript

`npx tsc --noEmit` → **PASS** (exit 0) after removing the `searchLatencyMs` `never` stub.

## 11. ESLint before / after

Targeted lint on Analyzer / Incident / orchestration files:

| | Problems | Errors | Warnings |
|---|---|---|---|
| Before (prior closure baseline) | 36 → then 34 | 26 | 8 |
| After this pass | **34** (26 errors / 8 warnings) on same scope; unused `onSearchLatency` warning cleared by omitting destructure |

**Fixed this pass (correctness / purity):**
- Dead `searchLatencyMs` const that broke `tsc` and was leftover from moving `performance.now` out of render.
- IncidentWorkspace total-failure on secondary 500s (integration integrity, not cosmetic UX).

**Remaining (deferred — pre-existing / non-blocking for integration closure):**
- Many `@typescript-eslint/no-explicit-any` in `AnalyzerHistoryList.tsx` / analyzer page — typing rewrite; deferred.
- `react-hooks/set-state-in-effect` for language/history prefs and URL sync — intentional sync patterns; deferred (changing URL sync risks navigation races).
- `react-hooks/exhaustive-deps` on catalog/history effects — deferred with care (avoid duplicate fetches).
- Sidebar hydration mismatch (dev overlay) — pre-existing; not FE association logic.

No broad rule suppressions. No repository-wide rewrite.

## 12. Test results

| Check | Result |
|---|---|
| `check-incident-orchestration.mjs` | **PASS** |
| `check-evidence-presentation.mjs` | **PASS** |
| `npx tsc --noEmit` | **PASS** |
| Targeted ESLint | Exit 1 with documented residual debt (above) |
| Backend suites | **Not run** (Claude ownership; out of scope) |

## 13. Browser scenarios and evidence

Runtime: Portal `http://127.0.0.1:3001`, API `http://127.0.0.1:8021`, disposable PG identity verified before use.

| Scenario | Result | Notes |
|---|---|---|
| A. Analyze → Incident (Event 1026) | **PASS with limitation** | Association succeeded; Workspace auto-opened; incident title Event 1026; 1 evidence. Workflow panels empty due to backend 500s (alerted, not blank). |
| B. Ambiguous association | **BLOCKED** | No real `ambiguous_not_merged` response available |
| C. Navigation | **PASS** | Close → Current issues list; reopen from list; deep link refresh restores Workspace |
| D. Notes | **PASS (honest gap)** | UI states Notes API not enabled; no fake persistence |
| E. Knowledge | **PASS** | Live 175; Candidate/Reference; honesty copy |
| F. Settings / infra | **PASS** | Theme preference; Runtime Health link; System & Infra: Grafana, MinIO, Prometheus, Core API Docs, Settings |

Screenshots retained under Cursor screenshot temp (examples): `closure-incident-1026-workspace.png`, `closure-catalog-175.png`, `closure-event-1026-detail-evidence.png`.

## 14. Exact remaining limitations

1. Ambiguous-match UX not proven against a real backend response.
2. Notes persistence not enabled — runtime Notes routes 404 despite source presence.
3. Diagnoses/remediations/workflow/knowledge-proposals **500** on disposable stack — Claude must fix before full Workspace acceptance.
4. Residual ESLint `any` / setState-in-effect debt.
5. Sidebar hydration warning in Next.js overlay.
6. Full product E2E (Log → Diagnosis → Remediation → Verification) still requires Claude backend + correlated browser evidence.

## 15. Claude handoff requirements

1. Ensure disposable/runtime process serves Notes routes (`GET/POST /api/v1/incidents/{id}/notes`) and `incident_note` migration on disposable DBs.
2. Fix 500s on diagnoses / remediations / workflow-events / knowledge-proposals for newly created incidents.
3. Provide a reproducible fixture or API path that returns `match=ambiguous_not_merged` (with or without `created=true`) so FE auto-open rules can be browser-verified.
4. Keep Provider-safe Knowledge / evidence identity / correlation as backend source of truth — FE will consume, not invent.
5. After the above, joint Full E2E acceptance (not another FE UX redesign pass).

## Completion verdict

**ACCEPTED WITH LIMITATIONS** — independent frontend integration work is correct and disposable browser evidence was captured for clear association, navigation, Knowledge counts, Notes honesty, and evidence presentation. Named backend/runtime dependencies remain; do not treat this as Frontend Product Acceptance or full E2E acceptance.
