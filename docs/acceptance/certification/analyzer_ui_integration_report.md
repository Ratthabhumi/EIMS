# Analyzer UI integration report (2026-11-22)

## What exists
* API: `solutionSummary.operationalGuidance` (backend, tested).
* **New component** `clients/dashboard/src/components/OperationalGuidancePanel.tsx` (additive, display only) and **three inserted lines** in the existing, already-modified `AnalysisResultDetail.tsx` (import, one optional type field, one render line before the Event Details grid). No existing line of that file was rewritten; `page.tsx` was not touched.
* The panel renders the twelve requested sections, each with a status badge decided by the server and never upgraded by the client: **STATED**, **NOT STATED**, **UNVERIFIED**.
  1 What happened · 2 Why · 3 What to inspect · 4 Recommended remediation · 5 Required permission · 6 Operational risk (risk + operational impact + destructive risk) · 7 Human approval requirement · 8 Rollback · 9 Recovery verification (+ recovery evidence and success criteria) · 10 Evidence and source (links) · 11 Product/version applicability · 12 Confidence and limitations.

## Behaviour rules (each tested)
* NOT STATED sections show "No source-backed information in the catalog. Nothing is suggested." and no items.
* UNVERIFIED sections show an amber notice "Unconfirmed … do not treat as confirmed guidance"; the weakest status wins when several fields share a section.
* A banner says the guidance is pending human review (not approved) unless the server reports an approved supplement.
* A destructive action with no stated rollback shows a red alert (`role="alert"`) telling the engineer not to execute without a verified recovery plan and human approval.
* The human-approval row says when the text is EIMS policy rather than a vendor statement.
* No guidance object (reference-only lookups, unmatched input) or no `catalogId` renders nothing, so a reference or unmapped candidate never looks like diagnostic guidance.

## Verification performed
| Check | Result |
|---|---|
| `npx tsc --noEmit` in `clients/dashboard` | clean |
| Real component server-rendered with guidance JSON produced by the real backend (`tests/analyzer_guidance_ui.cjs`, `tests/test_analyzer_guidance_ui.py`) | 5 tests pass: all 12 rows present with the right statuses for an eligible record and for a record lacking recovery verification; unverified flagged; destructive warning appears and disappears with a stated rollback; null/no-id renders nothing; EIMS-policy label |
| `next build`, Playwright/browser session against a running backend | **not run** in this round |
So the display is verified at component and type level with real backend data; it was not yet exercised in a live browser against a running stack.

## Not done
Thai translations exist for headings and notices only; item text is shown as returned (English vendor text). No UI to edit drafts or to record decisions (API only).
