# App Router Registration — Root Cause Record (2026-11-19)

## Symptom

A probe reported that `backend.main.app` exposed only 28 routes and **no**
`/api/v1/analyzer/*` or `/api/v1/auth/*` paths, although the source clearly
registers them and the running service serves them. That led to a (wrong)
conclusion that the Catalog router was not wired.

## Root cause (established, not inferred)

FastAPI **defers `include_router()`**. Immediately after import, the application
stores `_IncludedRouter` placeholders (empty `path`) and materialises the real
routes when the app is built.

Runtime evidence from the same process:

```
empty-path routes : 20   type=_IncludedRouter
app.openapi()     : 66 paths
  /api/v1/auth/login, /api/v1/auth/logout, /api/v1/auth/session
  /api/v1/analyze/, /api/v1/analyze/bundle
  /api/v1/analyzer/catalog/summary
  /api/v1/demo/incidents, ...
```

Therefore:

- No router was missing.
- No `include_router()` call was skipped.
- No second application instance exists.
- The source was never the problem; the **assertion method** was.

## Correction

No production code change was needed or made. Adding another `include_router()`
would have created genuine duplicate routes.

The diagnostic rule going forward:

> Never assert route presence from `app.routes` at import time. Use
> `app.openapi()["paths"]` or a started `TestClient`.

## Regression guard

`tests/test_app_router_registration.py` — 6 tests, all passing:

| Test | Assertion |
|---|---|
| auth routes | `/api/v1/auth/login` and `/logout` present in the built app |
| analyzer routes | at least one `/api/v1/analyze*` path |
| catalog summary | `/api/v1/analyzer/catalog/summary` present, `GET` only |
| catalog router | declares exactly one route |
| duplicates | no duplicate path in `app.routes` |
| deferred behaviour | documented, duplicate-path invariant re-asserted |

Command: `pytest tests/test_app_router_registration.py -q` → **6 passed**, exit 0.

## What this does and does not prove

- Proves: the canonical app object built by `backend.main` contains Auth,
  Analyzer and Catalog routes, exactly once.
- Does not yet prove an HTTP round trip (that requires a started app with a
  database session). The endpoint remains HTTP-pending in the checkpoint.

## Consequence for the Knowledge Foundation

Gate 2's router is correctly wired. The blocker is closed. Work can proceed to
the JSON-canonical + PostgreSQL-overlay architecture without touching app
wiring again.
