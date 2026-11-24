# 2026-11-20 — Automatic Incident Intelligence (Cursor frontend)

**Branch:** `demo/2026-11-24`  
**HEAD:** `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de` (no commit)  
**Scope:** Frontend transformation only. Incident Core backend unchanged (Claude-owned).

## Verdict

**ACCEPTED WITH LIMITATIONS**

The Analyzer now associates incidents automatically through the **existing** Incident Core contract (`GET /by-evidence` → `POST /incidents` / `create_from_evidence`). The UI does not invent endpoints, does not frontend-dedupe as a substitute for backend idempotency, and does not claim success without a confirmed response.

Full automatic product acceptance (shared-runtime browser proof of create + idempotent reopen + multi-event correlate + Engineer Notes) remains **NOT ACCEPTED** until Claude closes backend gaps and shared-runtime evidence is retained.

## Workflow before → after

| Before | After |
|---|---|
| Analyze → open Event Detail → manually Create / Link | Analyze → Incident Core ensure runs → status shown (created / correlated / already linked / failed) → Review in Incident Workspace |
| Manual title + correlate checkbox required to start tracking | Title hint optional; `source_event_key` passed when Event ID is usable so backend may correlate |
| Create button primary | Automatic path primary; Advanced link for correcting association only |

## Automatic behavior actually implemented

1. After analysis (and when reopening Analysis History Event Detail), `EventIncidentLink` calls `ensureIncidentForAnalysis`.
2. Lookup `GET /api/v1/incidents/by-evidence?source_type=analysis&source_id=<historyId>`.
3. If unbound: `POST /api/v1/incidents` with evidence reference only (no raw log payload).
4. Display truthful outcomes from `created` + `match`.
5. Refresh Incident Workspace open-issue list via `refreshTrigger`.
6. Engineer opens Workspace explicitly via “Review in Incident Workspace” (association is shown on the report first).

## API contracts used (existing)

| Call | Purpose |
|---|---|
| `GET /api/v1/incidents/by-evidence` | Existing association lookup |
| `POST /api/v1/incidents` | `create_from_evidence` — create / reuse / correlate |
| `POST /api/v1/incidents/{id}/evidence` | Explicit manual link (advanced) |
| `GET /api/v1/incidents?limit=50` | Open-issue landing list |

## Idempotency

- Same `analysis` + `source_id` (history id): backend returns existing incident (`event_already_linked` / reuse). Frontend never POSTs when lookup already finds a link.
- Browser refresh / reopen Event Detail: lookup-first path; no frontend-only dedupe store.
- Distinct history rows without asset/event-key identity remain separate incidents (Incident Core rule). With a usable Event ID, `source_event_key` is sent so **backend** correlation may attach to an open incident — FE does not merge.

## Correlation

- FE never merges incidents.
- Ambiguous / unsafe relationships stay as separate incidents until Incident Core correlates or the engineer explicitly links (Advanced).

## Human authorization boundaries (preserved)

- Confirm root cause / verify / resolve / close / approve Knowledge: still backend-gated; FE does not fabricate verified identity.
- Labels: “Possible cause” ≠ “Cause confirmed”; “Fix applied” ≠ “Resolved”; “Awaiting verification” when execution exists without verification records.
- Unattributed open-access provenance remains visible in workflow sections.

## Engineer Notes

**Not implemented** — no Incident Core notes API exists. UI shows an honest gap panel. Contract for Claude: see companion gap report.

## Files changed

- `clients/dashboard/src/lib/incident-orchestration.ts` (new)
- `clients/dashboard/src/components/incidents/EventIncidentLink.tsx`
- `clients/dashboard/src/app/analyzer/page.tsx`
- `clients/dashboard/src/components/AnalyzerHistoryList.tsx`
- `clients/dashboard/src/components/incidents/IncidentWorkspace.tsx`
- `clients/dashboard/scripts/check-incident-orchestration.mjs` (new)
- `docs/acceptance/2026-11-20-automatic-incident-intelligence-cursor.md`
- `docs/acceptance/2026-11-20-automatic-incident-backend-gaps-claude.md`

## Tests

| Check | Result |
|---|---|
| `node clients/dashboard/scripts/check-incident-orchestration.mjs` | **PASS** |
| `npx tsc --noEmit` | **PASS** (exit 0) |
| Chromium Portal `:3001` analyze → associate | **PASS WITH LIMITATIONS** (see below) |

### Chromium spot evidence (shared Portal `:3001`)

1. Pasted .NET Runtime Event 1026 text → Analyze Evidence.
2. Diagnostic Report opened with **Incident association** region: “Automatic via Incident Core · idempotent per analysis record”.
3. Status shown: association confirmed (idempotent remount showed “Evidence already linked…”); **Review in Incident Workspace** available.
4. History count 33 → 34; evidence `analysis:156`.
5. Review opened Incident tab with `?incident=58a8c0b1-…&analysis=156`; summary “What happened”; Engineer Notes gap panel present; Close control still present.
6. Full idempotent re-POST proof and Notes create not claimed (Notes API missing; no extra synthetic POST from acceptance harness).

## Remaining limitations

- Engineer Notes API missing (Claude).
- No dedicated “correlation ambiguous” match value from API — only created / already_linked / correlated_with_open_incident.
- Analyze without `historyId` cannot associate (backend must persist history).
- Without Event ID / asset, multi-log correlation still requires explicit Advanced link or Claude ingest improvements.
- Auto-open Workspace after analyze is intentionally not forced (report + association first).

## Backend gaps → Claude

See `docs/acceptance/2026-11-20-automatic-incident-backend-gaps-claude.md`.
