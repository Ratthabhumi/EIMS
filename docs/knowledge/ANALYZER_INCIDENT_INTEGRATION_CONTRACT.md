# Analyzer ↔ Incident Workspace integration contract (2026-11-19)

Audience: Log Analyzer owner (Cursor). Incident Core / Workspace owner: Claude.  
Status: **embedded in Log Analyzer** (right-side panel). Standalone Incidents menu retired; `/incidents?id=` redirects to `/analyzer?incident=`.

## Components (reuse as-is; presentation only, no business rule)

### `clients/dashboard/src/components/incidents/EventIncidentLink.tsx`
Placed **first** in Analysis History Event Detail modal and in the post-analyze Diagnostic Report modal when `historyId` exists. Primary buttons: **Create Incident**, **Open Incident**, **Link to Incident**. Props unchanged.

### `clients/dashboard/src/components/incidents/IncidentWorkspace.tsx`
Hosted by `clients/dashboard/src/app/analyzer/page.tsx` as a fixed right-side panel (drawer on narrow viewports). Props unchanged.

## Deep links
- Canonical: `/analyzer?incident=<uuid>&analysis=<id>`
- Compat: `/incidents` and `/incidents?id=<uuid>` → `router.replace` to Analyzer (no separate incident list UI)

## Encoding
Mojibake (`Ã‚Â·`) corrected at source in `AnalyzerHistoryList.tsx` to UTF-8 middle dot `·` / em dash `—`.

## Layout
- Analysis History + Diagnostic Knowledge Catalog tabs preserved.
- Selecting a history record opens Event Detail; Incident link controls appear below the detail.
- Opening an incident docks `IncidentWorkspace` on the right without replacing History.
- Global header overflow at ~390px addressed in `layout.tsx` (shrink search, hide avatar on xs).

## Known limitations
- Full shared-backend Browser E2E of create/link/diagnose/remediate/resolve/knowledge remains a follow-on gate after this P0 UI correction.
- Correlation / reopen authorization remain Claude-owned domain topics for independent review.
