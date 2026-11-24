# 2026-11-20 — Cursor Analysis Flow, Incident Workspace UX & USB Auditor

**Branch / HEAD:** `demo/2026-11-24` @ `3f2beea`  
**Runtime under test:** API `127.0.0.1:8022` → disposable PG `56470/eims_e2e_test` (alembic `a7d2c5e8f604`); Portal `127.0.0.1:3001` (`EIMS_BACKEND_URL=http://127.0.0.1:8022`)  
**Not used:** Operational `:5432`, `start_eims.bat`, inventing DELETE APIs  
**No commit/push**

## Verdicts by workstream

| Workstream | Verdict |
|---|---|
| 1. Analyze journey (no auto-jump) | **ACCEPTED** |
| 2. Incident Workspace investigation IA | **ACCEPTED WITH LIMITATIONS** |
| 3. USB Auditor endpoint removal | **ACCEPTED WITH LIMITATIONS** |

Overall Product Acceptance: **not claimed**.

## Files changed

| File | Change |
|---|---|
| `clients/dashboard/src/app/analyzer/page.tsx` | Removed auto-`openIncident` after association; toast only; Analysis Details stays open |
| `clients/dashboard/src/components/AnalysisResultDetail.tsx` | Fact vs hypothesis labels: “Diagnostic possibilities (not observed facts)” + Observed Evidence disclaimer (Event 41 class) |
| `clients/dashboard/src/components/incidents/IncidentWorkspace.tsx` | Overview + Evidence & Timeline first; Notes; Investigation Findings with honest empty copy; link back to Analysis |
| `clients/dashboard/src/components/incidents/shared.tsx` | Optional `asset_id` on Incident type |
| `clients/dashboard/src/app/endpoints/page.tsx` | Row Remove by `asset_id`; confirm dialog; soft-archive via `PATCH … Decommissioned` when state allows; hide archived by default |
| `docs/acceptance/2026-11-20-cursor-analysis-incident-usb-ux-closure.md` | This report |

## Exact behavior changed

### Workstream 1
- **Before:** `onLinked` called `openIncident` on clear association → user left Analysis Details for Incident Workspace.
- **After:** Association remains background; Analysis Record Details stays open; compact association panel + explicit **Review in Incident Workspace**.
- Ambiguous still never auto-opens (unchanged mapping).

### Workstream 2
- Incident detail order: Overview → Evidence & Timeline → Engineer Notes → Investigation Findings → Remediation → Verification → Knowledge → Proposal → Audit.
- Empty hypotheses: compact “No supported hypothesis yet…” (vs empty-looking panels).
- Evidence lists association time honestly; link “Open Analysis Record Details” for `analysis:{id}`.

### Workstream 3
- Remove targets **only** `asset_id`.
- Uses existing `PATCH /api/v1/assets/{asset_id}` → `Decommissioned` when Core Law 3 allows (Compliant / NonCompliant / Quarantined).
- **No** `DELETE /assets/{id}` exists. From `Discovered` / `PendingAudit`, UI confirms but reports backend limitation (Claude handoff).

### Event 41 fact vs hypothesis
Browser Analyze Event 41 showed:
- Observed Evidence (from submission): `Level: Critical` (+ description in timeline).
- Diagnostic possibilities explicitly **not observed facts**.
- Unknowns: physical root cause not established by these signals alone.
- Knowledge: Reference context / Exact Provider match when supplied.

## Tests / commands

| Command | Exit |
|---|---|
| `node scripts/check-incident-orchestration.mjs` | **0** PASS |
| `node scripts/check-evidence-presentation.mjs` | **0** PASS |
| `node scripts/check-engineer-notes.mjs` | **0** PASS |
| `npx tsc --noEmit` (src errors; `.next` generated noise filtered) | **0** for application sources |
| ESLint on touched analyzer/workspace/endpoints files | Exit **1** — residual pre-existing `any` / `StatusIcon` static-components in `endpoints/page.tsx`; no new broad suppressions |

## Browser scenarios

| Scenario | Result |
|---|---|
| Analyze Event 41 text → Details remain open (History tab still selected; URL without forced jump until user clicks Review) | **PASS** |
| Association completes in background (“Incident created”) + Review CTA | **PASS** |
| Explicit Review opens Incident Workspace Event 41 | **PASS** |
| Evidence & Timeline + Notes empty state + compact hypothesis empty copy | **PASS** |
| Event 41 fact vs diagnostic possibilities labeling | **PASS** |
| Ambiguous live Analyze journey | **Not re-proven this pass** (mapping still covered by scripts) |
| Notes add/reload | Covered in prior Notes integration report; Notes UI still live on this runtime |
| USB Remove UI present with asset_id confirmation | **PASS** (UI) |
| USB archive of a Discovered e2e host | **Blocked by lifecycle** — needs Claude archive-from-Discovered or multi-step transitions |

## Redis / health (frontend observation only)

- Soft-deps disposable API: Redis ping timeout → `/api/v1/health` can be **503** while Analyzer/Incident still serve useful work.
- `/metrics` 200 ≠ healthy dependencies.
- **No** frontend weakening of health checks. Hand off to Claude: is Redis mandatory for Analyzer/Incident paths, or cache-only degrade?

## Claude handoff

1. **USB Auditor:** Provide safe archive/remove for assets in `Discovered`/`PendingAudit` (or document allowed operator path), by `asset_id`, with audit + recoverability. Current UI refuses to invent DELETE.
2. **Redis 503:** Clarify health contract vs soft-deps demo mode; correlate whether real Analyzer/Incident requests fail when Redis is down.
3. **Ambiguous browser fixture:** Optional reusable Analyze path that returns `ambiguous_not_merged` for FE UX proof.

## Remaining limitations / risks

- Incident Workspace still exposes engineer forms for hypothesis/remediation (backend-owned workflows); not a full playbook engine.
- USB removal is soft-archive only when state machine allows; duplicate `e2e-host-1` rows in Discovered cannot be archived until Claude expands the contract.
- Live ambiguous association UI not re-run this pass.
- Pre-existing Sidebar hydration warning remains.
