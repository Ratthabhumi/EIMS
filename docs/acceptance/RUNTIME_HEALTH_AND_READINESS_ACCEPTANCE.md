# Runtime Health and Readiness Acceptance

Date: 2026-11-19  
Branch: `demo/2026-11-24`

## Verdict

**ACCEPTED WITH LIMITATIONS**

## Semantics (unchanged by design)

| Endpoint | Meaning | Observed with live Redis+MinIO+disposable PG |
|---|---|---|
| `GET /api/v1/health` | Process + dependency snapshot | **200 HEALTHY** — PG UP, Redis UP, MinIO UP |
| `GET /api/v1/ready` | Required tier = database | **200 ready** |

Earlier intermittent **503 DEGRADED** with Redis DOWN was consistent with optional Redis failure while readiness stayed ready — not a contradiction.

## Redis consumer criticality

| Consumer | Criticality | Behavior when Redis DOWN |
|---|---|---|
| Asset cache `set_value`/`get_value` | Optional cache | Non-fatal skip (soft-fail) |
| Timeline SQL aggregation | **Not Redis** | Unaffected |
| Telemetry / EVTX / OCR workers | Feature-required | Workers not started or cannot stream |
| Incident ingest dispatcher/consumer | Feature-required for stream path | Pending outbox cannot dispatch without Redis |
| WS pub/sub alerts | Optional UX | Alert stream unavailable |

## Observability cards (PgBouncer / MinIO “DOWN”)

These are **not missing products**. Compose already runs:

- `eims-postgres` `:5432`, `eims-pgbouncer` `:6432`
- `eims-minio` `:9000`/`:9001`

Observability “PgBouncer Pool” and “MinIO Storage” cards mirror `/api/v1/health` component probes via the Core API. When the API is unreachable, cards now show **UNAVAILABLE** (not falsely DOWN). When API is up and probe fails, they show **DOWN**.

There is still **no dedicated PgBouncer admin UI** in Portal — only the DB-tier health probe. That is intentional for this scope (no redesign / no new infra console).

## Settings / Runtime Configuration

Remains read-only. Added engineer-facing impact notes for PG/Redis/MinIO and clarified health vs readiness. Identity/recovery remain **not exposed by contract** (not the same as dependency DOWN).

## Limitations

- Full Redis-down browser matrix not re-run after this live HEALTHY session (prior soft-deps evidence retained).
- No speculative database-identity endpoint added.
