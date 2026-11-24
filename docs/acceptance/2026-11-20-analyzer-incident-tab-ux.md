# 2026-11-20 — Analyzer Incident as third tab (P0 UX correction)

**Branch:** `demo/2026-11-24`  
**HEAD:** `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de`  
**Scope:** Cursor-only UX correction. No Knowledge catalog growth. No Timeline/Prometheus rewrite.

## Verdict

**ACCEPTED WITH LIMITATIONS**

Incident Workspace is the third Analyzer main tab (with Analysis History and Diagnostic Knowledge Catalog). Open Incident switches that tab in the main content area. The right-side drawer/backdrop is removed from the Analyzer workflow. Portal UI defaults to English. Analyzer output language remains a separate control.

## Exact files changed

- `clients/dashboard/src/components/AnalyzerHistoryList.tsx` — third tab + embedded `IncidentWorkspace`
- `clients/dashboard/src/app/analyzer/page.tsx` — removed drawer; tab state + deep-link init; English Evidence Input chrome
- `clients/dashboard/src/components/SidebarNav.tsx` — English-first nav (no Thai UI override)
- `clients/dashboard/src/app/settings/page.tsx` — simplified to Theme + Observability link
- `clients/dashboard/src/app/timeline/page.tsx` — English UI labels retained
- `clients/dashboard/src/lib/portal-preferences.ts` — default analysis language `en`
- `clients/dashboard/src/components/incidents/EventIncidentLink.tsx` — default UI labels English
- `clients/dashboard/src/lib/session-proxy.ts` — (prior) localhost/127.0.0.1 sameOrigin (still required for Create)

Compatibility route unchanged: `clients/dashboard/src/app/incidents/page.tsx` → `/analyzer?incident=`

## Tool results

| Check | Result |
|---|---|
| `npx tsc --noEmit` | PASS (exit 0) |
| ESLint on touched files | FAIL with pre-existing `any` / `performance.now` purity findings in `AnalyzerHistoryList` — not introduced as new assertions to greenwash |
| Chromium | Portal `:3001` |

## Chromium acceptance (eight tests)

| Test | Result | Evidence |
|---|---|---|
| 1 Tab navigation | PASS | Three tabs in one row: Analysis History / Diagnostic Knowledge Catalog / Incident Workspace |
| 2 Open existing incident | PASS | Event Detail → Open Incident → Incident Workspace tab selected; `aside[aria-label=Incident Workspace]` absent |
| 3 Create incident | PASS (API + deep link) | Created `a298a65b-…` titled `Tab UX create 152`; `/analyzer?incident=…` selects Incident tab |
| 4 Link another event | PASS (API) | Linked analysis `151` to same incident; `evidence` length = 2; no duplicate incident |
| 5 Deep link | PASS | `/analyzer?incident=<id>` selects Incident tab; `/incidents?id=<id>` redirects to Analyzer |
| 6 Navigation preservation | PASS | Switch Catalog ↔ History ↔ Incident; history/catalog search controls remount from preserved state |
| 7 English-first UI | PASS | Nav, tabs, Evidence Input, Settings, Incident actions English; Analysis output language still selectable (EN/TH) |
| 8 Layout | PASS WITH LIMITATIONS | No Incident drawer; mobile 390px exercised; left nav aside remains (app shell, not Incident drawer) |

Screenshot: `page-2026-11-19T18-09-12-844Z.png` (Log Analyzer English chrome; subtitle states tab-not-drawer)

## Confirmations

- History records remain (32 analysis records observed).
- Diagnostic Knowledge Catalog tab intact (product filters/search remain).
- Incident opens as third tab, not a drawer.
- English is the default UI language.
- Analyzer output language remains separate (`Analysis output language` on Analyzer).

## Limitations

- Browser Create/Link path was proven via Event Detail Open + API create/link smoke; full click-through Create button in Chromium was not re-run end-to-end in this pass after drawer removal (same `EventIncidentLink` → `onOpenIncident` → tab switch path as Open).
- Incident Workspace inner copy remains English (component already English).
- ESLint baseline on `AnalyzerHistoryList` still has legacy `any` / purity findings.
- Knowledge 22-candidate closure is out of scope (Claude).

## Overall product gate

This P0 UX correction is **ACCEPTED WITH LIMITATIONS**. Broader EIMS product acceptance (Knowledge closure, full browser journey) remains **NOT ACCEPTED**.
