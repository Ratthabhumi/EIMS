# 2026-11-20 — Cursor Parallel Frontend Acceptance

**Branch / HEAD:** `demo/2026-11-24` @ `3f2beea` (verified)  
**Verdict:** **ACCEPTED WITH LIMITATIONS**

## What was completed (independent of Claude)

1. **Automatic Incident UX**
   - Clear outcomes: created / correlated / already_linked / ambiguous / unavailable / failed.
   - Auto-navigate to Incident Workspace only on clear success outcomes.
   - Ambiguous/failed stay on the report (not shown as success).
   - In-flight + per-historyId guard against duplicate ensure calls.

2. **Evidence presentation**
   - Removed FE message-text collapse (unsafe for distinct events).
   - First/Last chronology only when failure texts differ **and** evidence timestamps exist.
   - Excerpt line / reported offset labels retained.

3. **Engineer Notes readiness**
   - `EngineerNotes.tsx` isolated integration point; `apiEnabled=false`; no localStorage.

4. **Knowledge Catalog UX**
   - Candidate vs Reference badges from `knowledge_class` / lifecycle when API provides them.
   - Inventory copy: counts ≠ validated solutions; context ≠ root cause.

5. **Technical debt (targeted)**
   - Moved `performance.now` out of search `useMemo` (render purity).

## Tests this pass

| Check | Result |
|---|---|
| `check-incident-orchestration.mjs` | **PASS** |
| `npx tsc --noEmit` | **PASS** (exit 0) |
| Browser on `:3001` | **NOT RE-RUN** — Portal and API were down (`connection refused` on `:3001` / `:8000`). Prior Automatic Incident browser evidence remains in earlier 2026-11-20 Cursor reports. Did **not** start Operational DB-backed services for this pass. |

## Integration handoff for Claude

`docs/acceptance/2026-11-20-cursor-backend-integration-readiness.md`

## Limitations

- Live browser re-verification deferred until Portal+backend are available without Operational DB risk.
- Notes / ambiguous match live paths unproven.
- Broad ESLint `any` debt not fully cleared.

## Preservation

No `git reset/clean/stash/commit/push`. Backend files not edited by Cursor this pass.
