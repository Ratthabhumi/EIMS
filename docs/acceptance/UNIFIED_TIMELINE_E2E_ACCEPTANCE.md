# Unified Timeline E2E Acceptance

Date: 2026-11-19  
Branch: `demo/2026-11-24`  
HEAD: `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de` (no commit)  
Disposable DB: `eims-portal-accept-pg-20261119` @ `127.0.0.1:56456`

## Verdict

**ACCEPTED WITH LIMITATIONS**

## Root causes proven

| Symptom | Proven cause | Fix |
|---|---|---|
| Timeline “does not update” while staying on the page | Frontend fetched **only on mount/filter/page** — no focus/visibility refresh | Bounded silent refresh (30s) + focus/visibility refetch; fingerprint skip when unchanged |
| Only old USB IMPORT/UPDATE visible on some local runs | Backend often not running, or DB only had USB audits; **persistence path for USB was fine** | E2E proved new IMPORT appears immediately in API after commit |
| actor / corr “unavailable” | USB `AuditLog` rows omitted `actor_id` and assurance; UI treated all missing the same | New imports store `assurance=unattributed`, `principal=open_access`; UI distinguishes historical vs unattributed vs verified |
| Redis blamed for Timeline | Timeline aggregation is **PostgreSQL UNION** — no Redis in query path | Confirmed; Redis DOWN does not block audit/evidence/verification reads |

Trace (synthetic):

1. `POST /api/v1/assets/import-report` fixture `TIMELINE-E2E-HOST` → HTTP 200, `asset_id=dad300a3-…`
2. Persist `AuditLog` `IMPORT_REPORT` with assurance payload
3. `GET /api/v1/timeline` total 13→**14**; top event `id=358eb74a-…` type=audit title=IMPORT_REPORT assurance=unattributed

## Source coverage matrix

| Source | Producer | Persistence | Timeline adapter | API | Browser |
|---|---|---|---|---|---|
| Audit journal | Asset/incident services | `audit_logs` | PASS | PASS | PASS (structure) |
| Incident transitions | Incident status audits | `audit_logs` verb filter | PASS | PASS (`type=incident_transition` total≥1) | PARTIAL |
| Evidence | Incident evidence | `incident_evidence` | PASS | PASS (total≥3 this run) | PARTIAL |
| Verification | Incident verification | `incident_verification` | PASS | PASS (total≥1) | PARTIAL |
| Telemetry | Redis workers → `telemetry_metrics` | Requires Redis workers | PASS adapter | PASS empty (total=0) | NOT RUN populated |
| Winlog | EVTX workers → `windows_event_logs` | Requires Redis/workers | PASS adapter | PASS empty (total=0) | NOT RUN populated |
| USB Auditor import | `upsert_offline_report` | `audit_logs` | PASS | PASS | PASS via API+UI refresh path |

## Limitations

- Telemetry/winlog remain empty until workers ingest events (Redis + workers must be running and sources producing).
- Full browser “no reload” proof depends on Portal process; API+frontend refresh logic implemented and unit/source guards passed.
- Historical USB rows keep `assurance=historical_unavailable` — not rewritten.

## Tests

Focused Timeline suites executed with infra/cache tests (see handoff checkpoint).
