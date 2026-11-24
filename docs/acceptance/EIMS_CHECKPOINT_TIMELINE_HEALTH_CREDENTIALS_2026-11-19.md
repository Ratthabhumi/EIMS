# EIMS Checkpoint — Timeline, Health, Credentials (2026-11-19)

## Repo

- Branch: `demo/2026-11-24`
- HEAD: `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de` (unchanged; no commit)
- Worktree: pre-existing modifications preserved

## Root causes

1. Timeline UI did not refresh after mount → new persisted events looked “stuck” until full navigation remount.
2. USB audits lacked assurance provenance → UI showed generic unavailable actor/corr.
3. Observability DOWN on PgBouncer/MinIO often meant **API unreachable**, not missing infrastructure (services exist in compose).
4. Grafana env password does not rotate existing volume DB → needed CLI reset.
5. MinIO root rotation deferred; console IAM admin added instead to avoid breaking app S3.

## Implementation (high level)

- USB audit payload assurance; Timeline metadata/UI honesty; Timeline bounded refresh
- Settings impact notes; Observability UNAVAILABLE vs DOWN; health-monitor API-down semantics
- Grafana CLI password rotation; MinIO `eims_console_admin` + `consoleAdmin`
- Secrets only in `%TEMP%\eims-infra-credentials.secret`

## Tests

```
.\venv\Scripts\python.exe -m pytest tests/test_timeline_portal_correction.py tests/test_timeline.py tests/test_system_infrastructure_consoles.py tests/test_cache_ping.py -q
```

**27 passed**, exit **0**

## Runtime evidence

- Disposable PG `:56456` + live Redis/MinIO → health **HEALTHY**, ready **200**
- Synthetic USB import → Timeline total +1, event id traced, assurance=unattributed
- Source counts: audit/incident_transition/evidence/verification populated; telemetry/winlog 0

## Related (2026-11-19) — Local-First Infrastructure Audit → Consolidation

- Audit: `docs/architecture/LOCAL_FIRST_INFRASTRUCTURE_AUDIT.md`
- Consolidation acceptance: `docs/acceptance/LOCAL_FIRST_INFRASTRUCTURE_CONSOLIDATION_ACCEPTANCE.md`
- Runbook: `docs/operations/LOCAL_OPERATIONS_RUNBOOK.md`
- Handoff: `EIMS_OPERATIONAL_HANDOFF.md` § 2026-11-19 consolidation

## Rollback

- Revert listed Portal/backend file diffs; Grafana CLI reset; remove MinIO IAM user if needed (root unchanged)

## Next highest-value task

OpenCode Knowledge Foundation / Analyzer retrieval depth; optional telemetry/winlog producer E2E when workers are intentionally exercised.
