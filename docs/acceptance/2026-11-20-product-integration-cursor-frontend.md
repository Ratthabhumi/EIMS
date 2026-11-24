# 2026-11-20 — Product Integration (Cursor frontend workstream)

**Branch:** `demo/2026-11-24`  
**HEAD (at start of this note):** `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de`  
**Owner split:** Cursor = Analyzer / Evidence Input / i18n / Timeline UI / Settings UI / Incident panel integration. Claude = Knowledge Catalog quality + proposal lifecycle (not claimed here).

## Verdict (Cursor scope only)

| Area | Verdict | Notes |
|---|---|---|
| Evidence Input UX | **ACCEPTED WITH LIMITATIONS** | Unified “Evidence Input” with Paste / Upload Files / Upload Evidence Bundle. Backend parsers unchanged. Limits aligned to `BUNDLE_MAX_*` (12 / 5 MiB / 30 MiB). ZIP still rejected (honest copy). |
| Thai / EN localization | **ACCEPTED WITH LIMITATIONS** | Shared `ui-i18n.ts` (127 keys, parity self-check PASS). Analyzer chrome, Incident actions, History tabs, Timeline, Settings, Sidebar. Analysis body still mixes technical EN where content is English. Incident Workspace body still mostly EN (Claude-owned component; labels not fully translated). |
| Settings prefs vs ops config | **ACCEPTED** | Tabs: User Interface Preferences vs Runtime Diagnostics. Explicit Application Configuration section labelled deployment-controlled; no fake editable ops knobs. |
| Unified Timeline frontend | **ACCEPTED WITH LIMITATIONS** | Honesty banner shows API totals + source mix. USB Auditor audit rows preserved. After Incident create, API returned `total=11` (`audit=9`, `evidence=2`) — no second timeline invented. Incident transitions / verification appear only when rows exist. |
| Incident Create/Open + right panel | **ACCEPTED WITH LIMITATIONS** | Deep link `?incident=&analysis=` opens right-side Incident Workspace. Event Detail Create/Open/Link in Thai. Root-cause fix: BFF `sameOrigin` equated `localhost` ↔ `127.0.0.1` (was rejecting Portal POSTs as Cross-origin). Full multi-event Link + reload matrix not exhaustively re-run in this pass. |
| Knowledge 163 / 22 candidates | **NOT ACCEPTED (Claude)** | Catalog count still 163 (`OPERATIONAL_EVENT_CATALOG`). No artificial growth. Candidate review / proposal→approved loop not owned or claimed by Cursor. |
| Prometheus | **ACCEPTED (spot)** | `up{job="eims_fastapi"}=1` queried live. Grafana dashboard not re-proven this pass. |

## Evidence

- i18n: `node clients/dashboard/scripts/check-ui-i18n.mjs` → `PASS ui-i18n parity keys=127`
- Browser: Portal `:3001` Analyzer Evidence Input TH labels; Event Detail Incident actions TH; Settings Preferences vs Operational; Timeline honesty UI; Incident Workspace panel with `browser panel smoke3` + evidence `analysis:150`
- Timeline API after incident smoke: `pagination.total_records=11`, types `audit=9`, `evidence=2`
- Screenshot: `page-2026-11-19T17-45-23-070Z.png` (Event Detail + Open Incident)

## Files touched (Cursor)

- `clients/dashboard/src/lib/ui-i18n.ts` (new)
- `clients/dashboard/scripts/check-ui-i18n.mjs` (new)
- `clients/dashboard/src/app/analyzer/page.tsx`
- `clients/dashboard/src/components/AnalyzerHistoryList.tsx`
- `clients/dashboard/src/components/incidents/EventIncidentLink.tsx` (labels only)
- `clients/dashboard/src/app/settings/page.tsx`
- `clients/dashboard/src/app/timeline/page.tsx`
- `clients/dashboard/src/components/SidebarNav.tsx`
- `clients/dashboard/src/lib/session-proxy.ts` (localhost/127.0.0.1 sameOrigin)

## Handoff to Claude

1. Inventory lifecycle of the 163 records; review 22 candidates without inventing rows.
2. Prove Incident → Knowledge Proposal → pending review → approve → Analyzer retrieval.
3. Do not edit Cursor frontend files without coordination.

## Overall EIMS product gate

**NOT ACCEPTED** as a whole — Knowledge closure and full browser journey (remediation → verification → approved knowledge) remain open.
