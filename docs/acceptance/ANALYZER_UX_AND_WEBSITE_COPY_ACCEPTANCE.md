# Analyzer UX, Open Access & Website Copy Acceptance

Date: 2026-11-19  
Branch: `demo/2026-11-24`  
HEAD (start/end of this task): `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de`  
Machine: Mew (Windows)

## Verdict

**ACCEPTED WITH LIMITATIONS**

Core requirements are verified: application login removed at the request path, Analyzer login UI gone, product renamed to **Log Analyzer**, and focused tests pass. Full multi-page bilingual copy polish and live Analyzer analyze-with-backend browser proof remain limited by backend-not-running in this close-out.

## Product rule enforced

EIMS has **no application login**. Engineers open the Portal without username/password.

Trust boundary (accurate): access control is the **trusted internal/network deployment**, plus non-login controls (CORS same-origin writes, input validation, CSRF/same-origin BFF checks, DB least-privilege / identity guards, secrets not exposed in UI). Absence of login does **not** make a public internet exposure safe.

## Authentication mechanisms removed / changed

| Former mechanism | Location | Change |
|---|---|---|
| Analyzer username/password form + session polling | `AnalyzerSession.tsx`, used by `analyzer/page.tsx` | Component is a no-op; removed from Analyzer page |
| Session expired / session service unavailable copy | same | Removed with the UI |
| Application JWT required for Portal APIs | `get_current_user`, `require_admin_or_token` | Missing/invalid bearer → shared `OPEN_ACCESS_IDENTITY` (`demo`); never 401 for missing login |
| `/api/v1/auth/login` | `backend/api/routers/analyzer/auth.py` | Returns **410 Gone** with explicit “login not used” |
| BFF `/api/session/login` | `clients/dashboard/src/app/api/session/login/route.ts` | Returns **410** |
| BFF `/api/session/logout` | logout route | Clears legacy cookie only; no login cycle |
| Knowledge “Sign in to view…” gate | `knowledge/page.tsx` | Removed; open-access load |
| Secure-mode search/WS/vector blocks | search controller, ws_controller, vector_db | Open-access; no longer fail closed solely for AUTH_MODE=secure |
| AUTH_MODE setting | `backend/core/config.py` | Compatibility only; documented as non-login |

### Preserved (not application login)

- `require_admin` / `require_knowledge_reviewer` still require a real privileged principal for **admin user CRUD / knowledge reviewer capability** (not Portal entry).
- `EIMS_ADMIN_TOKEN` still accepted for machine/admin tooling attribution.
- CORS, same-origin BFF mutation checks, body size limits, health/ready honesty, DB identity enforcement, audit logging remain.

## Product naming

User-facing **AI Log Analyzer (EventIQ)** → **Log Analyzer** in:

- Analyzer page heading + description
- Sidebar
- Home card
- Navigation search provider title/subtitle

Internal routes (`/analyzer`), API paths, DB columns, and historical EventIQ identifiers were **not** renamed.

## Website copy corrections (this pass)

| Area | Change |
|---|---|
| Sidebar group | “Operations & AI” → “Operations” |
| Home group | same |
| Home Log Analyzer blurb | Evidence-oriented wording (no “Vector RAG” marketing) |
| Settings nav search subtitle | Runtime health/readiness (aligned with Portal Correction) |
| Knowledge | Removed Sign-in requirement message |

Preserved prior Portal Correction: Settings read-only Runtime Configuration, Timeline engineering sources, USB Auditor nav, hidden Client Agents/Knowledge/OCR from primary nav.

## Files modified

- `backend/domain/analyzer/auth.py`
- `backend/api/routers/analyzer/auth.py`
- `backend/api/routers/evaluations.py`
- `backend/core/config.py`
- `backend/domain/search/controller.py`
- `backend/domain/search/providers/navigation_provider.py`
- `backend/domain/telemetry/ws_controller.py`
- `backend/domain/analyzer/services/vector_db.py`
- `clients/dashboard/src/app/analyzer/page.tsx`
- `clients/dashboard/src/components/AnalyzerSession.tsx`
- `clients/dashboard/src/components/SidebarNav.tsx`
- `clients/dashboard/src/app/page.tsx`
- `clients/dashboard/src/app/knowledge/page.tsx`
- `clients/dashboard/src/app/api/session/login/route.ts`
- `clients/dashboard/src/app/api/session/logout/route.ts`
- `tests/test_auth_modes.py`
- `tests/test_analyzer_open_access_ui.py` (new)
- `docs/acceptance/ANALYZER_UX_AND_WEBSITE_COPY_ACCEPTANCE.md` (this file)

**Not modified:** Knowledge Foundation migrations/schema/service implementation (OpenCode workstream).

## Tests

```
.\venv\Scripts\python.exe -m pytest tests/test_auth_modes.py tests/test_analyzer_open_access_ui.py tests/test_timeline_portal_correction.py -q
```

Result: **16 passed**, exit **0**  
Log: `%TEMP%\eims-open-access-pytest.log`

Covered:

- Open-access evaluation write without token
- `AUTH_MODE=secure` does not reintroduce login requirement
- `/api/v1/auth/login` → 410
- Analyzer/home/sidebar source guards (no prohibited login strings; Log Analyzer name)

## Browser acceptance

Portal: `http://localhost:3001` (not Grafana `:3000`)

| Check | Result |
|---|---|
| Analyzer heading **Log Analyzer** | **PASS** |
| No Username/Password/Sign in / session-expired UI | **PASS** (page snapshot + source guards) |
| Nav + Home show Log Analyzer | **PASS** |
| USB Auditor still in nav | **PASS** |
| Live Analyze API with disposable backend | **NOT RUN this close-out** (backend `:8000` not listening) |
| Full bilingual copy audit of every route state | **PARTIAL** — focused routes audited; not every empty/error string on every page |

## Remaining issues (severity)

1. **Medium** — Full Thai/English copy pass across evaluations/observability/OCR deep pages not exhaustively rewritten.
2. ~~**Medium** — Live Analyzer upload→result browser proof needs disposable backend restarted.~~ **Closed in Final Cursor Closure** — see below.
3. **Low** — History encoding glitch (`Ã‚Â·`) observed in Analyzer history subtitle; pre-existing/display encoding; not fixed in this pass.
4. **Info** — Routes `/agents`, `/knowledge`, `/ocr-history` still exist by direct URL (hide ≠ delete). Knowledge Foundation readiness is OpenCode’s workstream.

## Safety

- No operational DB (`:5432`) used in this task
- No Knowledge migrations/schema edits
- No git commit/push
- Existing working tree preserved

---

## Final Cursor Closure append (2026-11-19)

Canonical handoff: **`docs/acceptance/FINAL_PORTAL_CLOSURE_HANDOFF.md`**.

| Gap from prior pass | Closure evidence |
|---|---|
| Live Analyze with backend | Browser Analyze → Diagnostic Report Event ID 1000 against disposable `:8000` |
| `Vector RAG` marketing label | Renamed to **Knowledge match**; UI test bans `Vector RAG` |
| Website-wide route scrape | Primary routes clean of EventIQ / AI Log Analyzer / login; Settings “Gemini” only in removal notice |
| Security inventory | 75 OpenAPI ops classified; admin CRUD 401; CORS allowlist; secrets absent from HTML |

Status remains **ACCEPTED WITH LIMITATIONS** (deep bilingual polish of every secondary page state still not claimed as exhaustive rewrite).
