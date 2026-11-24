# 2026-11-20 — Final UX Correction + Evidence Presentation (Cursor)

**Branch:** `demo/2026-11-24`  
**HEAD:** `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de` (unchanged; no commit)  
**Scope:** Cursor frontend only. Knowledge expansion and evidence-pipeline root cause remain Claude-owned.

## Verdict

**ACCEPTED WITH LIMITATIONS** for Cursor gates in this round.

| Gate | Result |
|---|---|
| Incident X → Incident list (same tab) | **PASS** |
| Workspace spacing / nested scroll | **PASS WITH LIMITATIONS** |
| Settings small cleanup | **PASS** |
| Evidence presentation honesty | **PASS (presentation layer)** |
| Knowledge expansion | **OUT OF SCOPE (Claude)** |
| Evidence pipeline / Event 1026 analysis contract | **OUT OF SCOPE (Claude)**; UI no longer invents chronology labels |

## Files changed (this pass)

- `clients/dashboard/src/app/analyzer/page.tsx` — `closeIncidentDetail`; URL sync clears `incident`; stays on `mainTab=incident`
- `clients/dashboard/src/components/AnalyzerHistoryList.tsx` — `onCloseIncident`; detail padding `p-4`; X no longer switches to History
- `clients/dashboard/src/components/incidents/IncidentWorkspace.tsx` — X `aria-label="Close incident detail"`; shorter header; no duplicate title in summary
- `clients/dashboard/src/app/settings/page.tsx` — Theme preference + Runtime Health link only
- `clients/dashboard/src/components/AnalysisResultDetail.tsx` — display-only evidence dedupe; chronology honesty; line/offset labels
- `clients/dashboard/src/components/EvidenceSourceReview.tsx` — excerpt line vs reported offset labels

## Incident close behavior

States:

- **A** Incident list / landing (`incidentId` null, tab = Incident Workspace)
- **B** Selected incident detail (`incidentId` set, tab = Incident Workspace)

X transitions **B → A**. Does not navigate to Analysis History, home, or create/delete incidents.

URL: closing removes `?incident=`; deep link `/analyzer?incident=<id>` still opens detail on Incident tab.

## Chromium evidence (Portal `:3001`)

| Test | Result |
|---|---|
| Open existing incident deep link | PASS — `?incident=a298a65b-…` / `7acf9a5a-…`; Incident tab selected |
| Click X | PASS — landing list “Incidents” + open-incident buttons; Incident tab remains selected; URL → `/analyzer` |
| Open another incident from list | PASS — detail for `analysis incident: 155`; URL gains `?incident=7acf9a5a-…` |
| Refresh deep link | PASS — Incident tab + selected incident retained |
| Settings | PASS — Theme + Runtime Health / Observability link; no deployment essay |
| Mobile 390px | PASS WITH LIMITATIONS — list/tabs usable; left app shell still present |

Screenshots (Cursor capture dir):

- `incident-workspace-list-2026-11-20.png`
- `incident-workspace-list-mobile-390-2026-11-20.png`
- Settings viewport captured in-session (Theme + Runtime Health)

## Evidence presentation (Cursor)

- Duplicate identical evidence strings / source refs collapsed **for display only**; original analysis payload untouched.
- First/Last observed failure shown only when texts or timeline entries are distinct; otherwise: “Chronology could not be established from the supplied evidence.”
- `:` line refs labeled as **excerpt line** or **reported offset**, not implied original file lines.

Does **not** fix parser duplication or analysis-contract overclaim for Event 1026 — that is Claude’s pipeline work.

## Tool results

| Check | Result |
|---|---|
| `npx tsc --noEmit` | PASS (exit 0) |
| Git commit/push | Not run (not authorized) |
| Knowledge catalog count | Not modified by Cursor |

## Remaining limitations

- Presentation dedupe cannot distinguish two genuine events that share message text but differ by EventRecordID/TimeCreated — backend identity required (Claude).
- Nested scroll may still appear if Incident section content exceeds the shared Analyzer tabpanel; outer scroll is intentional single container.
- Knowledge Phase 1 expansion, coverage matrix, retrieval tests, Event 1026 regression: Claude report required.
- Browser Acceptance for full product journey remains **NOT PASSED** until Claude evidence + full correlated proof.

## Claude handoff (do not edit Cursor-owned UI files for these)

1. Trace evidence pipeline for .NET Runtime Event ID 1026 duplicates and false chronology at parse/normalize/prompt stages.
2. Preserve raw evidence; fix identity/provenance dedupe without text-only collapse of distinct EventRecordIDs.
3. Stage Knowledge expansion: Windows / AD / GPO / DNS / Networking first; authoritative sources; no thousand-record dump; keep 163 baseline + lifecycle.
4. Retrieval regression: Event ID / Provider / product vs root-cause language.
5. Produce Claude acceptance report separate from this file.
