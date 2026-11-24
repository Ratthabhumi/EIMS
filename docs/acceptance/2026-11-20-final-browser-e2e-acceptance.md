# 2026-11-20 — Final Full Browser End-to-End Acceptance (Cursor)

**Branch / HEAD:** `demo/2026-11-24` @ `3f2beea`  
**Role:** Cursor — Portal / UI / Browser journeys (primary). Claude — backend contract (read-only for this closure).  
**No commit / push / operational DB / `start_eims.bat` / `docker compose down -v`.**

## Overall verdict

**ACCEPTED WITH LIMITATIONS** (Browser E2E against one verified integrated runtime).

**Product Acceptance: NOT claimed.** Critical journeys A–E and H (partial) passed on the same runtime; full verification→resolution with a verified-identity reviewer, and USB archive-from-Discovered, remain backend/policy limitations.

## Runtime identity (Gate A)

| Item | Value |
|---|---|
| Portal | `http://127.0.0.1:3001` (`EIMS_BACKEND_URL` / `NEXT_PUBLIC_EIMS_API_URL` → `http://127.0.0.1:8031`) |
| API | `127.0.0.1:8031` uvicorn `backend.main:app` |
| PostgreSQL | host `127.0.0.1:56470`, DB **`eims_cursor_accept`**, role **`eims_incident_test`** (non-superuser) |
| Container | `eims-knowledge-b-pg-20261119` (synthetic-integration-test) |
| Alembic head | **`c9f4a7b0d826`** (chain includes `a7d2c5e8f604` notes, `b8e3f6a9c715` provider scope, `c9f4a7b0d826` event time) |
| Catalog | `/api/v1/analyzer/catalog/summary` → **175** records (`approved=0`) |
| Soft deps | `EIMS_DEMO_SOFT_DEPS=1`; Redis host `127.0.0.1` |
| Health vs ready | `/api/v1/ready` **200**; `/api/v1/health` may be slow/DEGRADED — **not** weakened; `/metrics` ≠ dependency proof |
| Not used | Operational `:5432` / `eims_registry`; stale Portal→`:8022` (repointed for this run) |

**Note:** `tools/verify_backend_identity.py` reports the *caller* process settings, not the live uvicorn env. Live identity was proven by TCP→`56470`, `pg_stat_activity` → `eims_cursor_accept`, and route probes.

Evidence dir: `docs/acceptance/evidence/browser-e2e-2026-11-20/`

## Gate results

| Gate | Result | Evidence |
|---|---|---|
| A. Runtime identity & isolation | **PASS** | Portal infra-status → `:8031`; DB `eims_cursor_accept` @ `56470`; head `c9f4a7b0d826` |
| B. Analyze journey | **PASS** | Event 1026 fixture → Diagnostic Report stayed open; History tab remained selected; no auto Workspace nav. Screenshot `A-analyze-details.png` |
| C. Automatic Incident association | **PASS** | Background “Incident created.” + Review CTA; duplicate → `event_already_linked` (`B-already-linked-api.json`); incident `06f3290a-…` |
| D. Ambiguous correlation | **PASS** | API `ambiguous_not_merged` + browser UI with candidates, amber “Ambiguous — not correlated”, **no** auto-open Workspace. Screenshot `C-ambiguous-browser.png`; `C-ambiguous-api.json`. Required known `asset` query (FE now forwards `asset_id` when provided; never invents from hostname) |
| E. Incident Workspace IA | **PASS** | Overview → Evidence & Timeline → Notes → Findings → Remediation → Verification → Knowledge → Proposal → Audit; honest empty/partial; close → Workspace **list** |
| F. Notes persistence & attribution | **PASS** | Note via UI; `demo` / `unattributed`; reload + **hard API restart** still 1 note (`K-after-hard-restart.json`); no localStorage |
| G. Findings / remediation / verification / resolution | **PASS with limitations** | Hypothesis `status=hypothesis` (“not confirmed”); remediation `proposed` / not executed / not verified; incident stayed `open`. PATCH resolve as open-access → **403** verified-identity required. Full execute→verify→resolve with reviewer **NOT TESTED** (needs Claude/reviewer token) |
| H. Knowledge provenance & proposal | **PASS with limitations** | Catalog **175** in UI (“Not validated solutions · Context ≠ root cause”); Event 1026 Knowledge “Reference context only” / exact provider match; **0 approved**. Proposal lifecycle UI present; no auto-promotion observed |
| I. USB Auditor lifecycle | **PASS with limitations** | List + Remove by `asset_id` + confirm; Discovered host blocked with honest error (no invented DELETE). Archive success path needs Compliant/NonCompliant/Quarantined (Claude handoff) |
| J. Browser console / network integrity | **PASS with limitations** | Analyze/association/notes/workspace succeeded. Pre-existing SidebarNav hydration warning remains; not treated as journey failure |
| K. Persistence across hard restart | **PASS** | Stopped uvicorn `:8031`, restarted against same disposable DB; notes=1, incidents=4, status=open, root=hypothesis |

## Journey summary counts

| Journey | Result |
|---|---|
| A Evidence / Analyze | PASS |
| B Auto association + idempotency | PASS |
| C Ambiguous | PASS |
| D Workspace | PASS |
| E Notes | PASS |
| F Findings / rem / resolve gate | PASS (limitations) |
| G Knowledge | PASS (limitations) |
| H USB | PASS (limitations) |

**Pass / Fail / Blocked / Not tested (gates A–K):** 7 PASS, 4 PASS-with-limitations (counted as PASS for journey continuity), 0 FAIL, 0 BLOCKED. Full Product gates for verified resolve and USB archive-from-Discovered: **NOT TESTED / limited**.

## Files changed this acceptance pass

| File | Why |
|---|---|
| `clients/dashboard/src/lib/incident-orchestration.ts` | Optional `assetId` → POST `asset_id` for real correlation |
| `clients/dashboard/src/components/incidents/EventIncidentLink.tsx` | Pass `assetId`; ambiguous candidates stay manual |
| `clients/dashboard/src/app/analyzer/page.tsx` | `?asset=` → EventIncidentLink; no ambiguous auto-nav |
| `clients/dashboard/src/components/AnalyzerHistoryList.tsx` | `correlationAssetId` for URL-driven association |
| `docs/acceptance/2026-11-20-final-browser-e2e-acceptance.md` | This report |
| `docs/acceptance/evidence/browser-e2e-2026-11-20/*` | Screenshots + JSON |
| `EIMS_ACCEPTANCE_LEDGER.md` | Append-only entry |

Prior uncommitted FE work (Analyze no-auto-nav, Workspace IA, USB remove UI, Event 41 labeling) was exercised as-is.

## Commands / exit codes

| Command | Exit |
|---|---|
| `node scripts/check-incident-orchestration.mjs` | **0** |
| `node scripts/check-evidence-presentation.mjs` | **0** |
| `node scripts/check-engineer-notes.mjs` | **0** |

## Claude handoff (backend)

1. **USB:** Safe archive/remove from `Discovered`/`PendingAudit` by `asset_id` with audit + recoverability (or document operator multi-step path).
2. **Verified-resolution browser path:** Disposable reviewer session for execute → verify → resolve proof (open-access correctly 403s).
3. **Identity verifier script:** Prefer probing the live process DB (or require env) so `verify_backend_identity.py` cannot confuse caller defaults (`5432`) with uvicorn reality.

## What the cooperative report may truthfully claim

Portal + Analyzer + Incident Workspace + Notes + ambiguous association UX were proven in a real browser against disposable API `:8031` / DB `eims_cursor_accept` at migration `c9f4a7b0d826`, with Analyze staying on Analysis Record Details and association remaining background/explicit. Full Product Acceptance (verified resolution end-to-end, Knowledge approvals, USB archive of Discovered duplicates) is **not** established by this frontend-led run.

## Runtime still running / safe stop

- **Still running:** Portal `3001` (npm/next), API `8031` (uvicorn → `eims_cursor_accept`), plus pre-existing `8022`/`8032` (leave alone unless you own them).
- **Safe stop (Cursor-owned only):** stop the Next process for `:3001`; stop uvicorn whose command line is `backend.main:app --host 127.0.0.1 --port 8031`. Do **not** `docker compose down -v` or touch `:5432`.
