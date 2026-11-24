# A17 Phase 1 — Mutation Path Inventory

Date: 2026-11-19 · Read-only. No source or operational change.

Search scope: `backend/`, `tools/`, `scripts/`, `migrations/`. Pattern set: `TRUNCATE|DROP TABLE|DELETE FROM|INSERT INTO|UPDATE … SET|execute(|session.add|add_all|bulk_save`.
Result: **180 hits / 43 files** — a candidate list, not 180 paths. Each row below is a *file*, traced only as far as stated.

## A — Application runtime (request/worker initiated)

| File | Mutation | Target | Guard | Identity | Authorization |
|---|---|---|---|---|---|
| `backend/domain/asset_registry/repository.py` | ORM add/update | app engine (`settings.database_url`) | none | none | none |
| `backend/api/routers/analyzer/knowledge.py` | ORM/execute | app engine | none | none | route auth only |
| `backend/api/routers/analyzer/history.py` | ORM/execute | app engine | none | none | route auth only |
| `backend/domain/analyzer/services/bundle.py` | execute/insert | app engine | none | none | n/a |
| `backend/domain/telemetry/worker.py` | execute | app engine | none | none | n/a |
| `backend/domain/incident/service.py` | ORM | app engine | none | none | n/a |
| `backend/api/routers/evaluations.py` | ORM | app engine | none | none | route auth only |
| `backend/domain/incident_ingest/dispatcher.py` | execute | app engine | none | none | n/a |
| `backend/api/routers/analyzer/admin.py` | ORM | app engine | none | none | route auth only |
| `backend/domain/analyzer/auth.py` | execute | app engine | none | none | n/a |
| `backend/infrastructure/database.py` | engine creation | `settings.database_url` | none | none | n/a |

`backend/infrastructure/database.py:68` is the single application engine factory. It never verifies what it connected to. Every runtime row above inherits that gap.

## B — Maintenance CLI

| Entry point | Mutation | Target resolution | Guard | Identity |
|---|---|---|---|---|
| `tools/maintain_analyzer_sessions.py --apply` | `DELETE` of auth rows (`--apply` commits) | `EIMS_MAINTENANCE_DATABASE_URL` (`:20`) | none | none |
| `tools/sprint11_benchmark.py` | `TRUNCATE … CASCADE` | `EIMS_BENCHMARK_DATABASE_URL` | URL allowlist + async identity (A16) | yes, same engine |
| `tools/sprint11_rag_smoke.py` | inserts | own URL | none verified | none |
| `tools/import_knowledge_source_candidates.py` | inserts | own URL | none verified | none |

## C — Seed / demo

| Entry point | Mutation | Target | Guard |
|---|---|---|---|
| `tools/seed_analyzer_incident.py` | `INSERT` ×6 + `DELETE FROM analysis_history WHERE parse_method=:pm` (`:443`) | own URL | none |
| `tools/seed_demo_data.py` | `INSERT` ×4 | app `settings` engine | none |

**Documentation defect:** `seed_analyzer_incident.py:13` states it "NEVER deletes, truncates, or renames any existing row", but line 443 deletes. Either the statement or the code is wrong.

## D — Test-only

| Entry point | Behaviour | Gap |
|---|---|---|
| `tests/test_global_search_integration.py::db_session` | creates engine from `settings.database_url` (`:44`) | **no guard, no identity check** — can target the operational DB |
| `tests/conftest.py::client` | lifespan + guard | guarded, but no post-connect identity check |

## E — Migration

| Entry point | Reachability |
|---|---|
| `migrations/env.py` | sets URL from `settings` (`:58`); **no reference from `backend/`** — migration-tooling only. Not an application runtime path. |

## F — Read-only

`centers`/`providers`/`query_controller`/`timeline` read paths — no mutation, out of remediation scope.

## G — Dead / unused

Not assessed. No file was proven dead.

## Confirmed path-level facts

1. `sprint11_benchmark.py` seeds the **benchmark** engine (`:256`) but `measure()` drives `TestClient(app)` (`:262`, `:280`), which uses `settings.database_url`. The two targets are never asserted equal.
2. `test_global_search_integration` writes through `settings.database_url` with no isolation guard — the strongest live risk in this inventory.
3. Chat_HAND: `execution-journal` and `risk-policy` are imported by **0** gateway files.
