# EIMS Engineering Memory — 2026-11-16 Incident Core v1 (backend-only)

## Scope

Implemented an additive, backend-first Incident Core v1 on the existing repository.
No dashboard/UI work and no Browser Acceptance was performed. Existing analyzer and
timeline behavior was not modified; the analyzer history model gained only a nullable
identity link.

## Schema (Alembic `b8d3f5c1a720`, parent `a4b7c9d2e601`, single head)

New tables:

- `incidents` — `incident_id` UUID PK, title, status, severity, confidence, nullable
  `asset_id` FK to `infrastructure_assets.asset_id` (`ON DELETE RESTRICT`, indexed),
  `first_seen`/`last_seen`, unique `dedupe_key`, `root_cause_state`, owner, JSONB
  `summary`, UTC `created_at`/`updated_at`. Check constraints bound status, severity,
  confidence, root-cause state and `last_seen >= first_seen`.
- `incident_evidence` — `evidence_id` UUID PK, `incident_id` FK (`ON DELETE CASCADE`,
  indexed), `source_type`, `source_id`, optional `source_event_key`, SHA-256
  `evidence_digest`, `observed_at`, `added_by`, `created_at`,
  `UNIQUE(source_type, source_id)` and a bounded `source_type` check.

Additive column: `analysis_history.asset_id` UUID NULL FK
(`ON DELETE RESTRICT`, indexed). It is **not backfilled**; unresolved stays NULL.

Audit remains the existing `audit_logs` journal. Incident actions write
`incident_id` inside `immutable_payload` and no new audit table was introduced.

## Correlation (pure, deterministic — `backend/domain/incident/correlation.py`)

- strong: same concrete asset + same signature inside the configured window.
- medium: same concrete asset with a differing signature inside the window, or the
  same signature inside the window while asset identity is unresolved.
- weak: same signature inside the expanded 2x window, or explicit single-source
  evidence.
- none: otherwise. Two different non-null asset ids are always `none`.
- `dedupe_key = sha256("asset|unresolved:signature:window_bucket")`; default window
  900 s, explicitly not the analyzer's 300 s bundle epsilon.
- Confidence, reasons, bounded sources, signature, window and asset state persist in
  `incidents.summary["correlation"]`.
- `root_cause_state` stays `unknown`; no automatic causal inference, closure or
  remediation exists.

Service lookup note: automatically merging an asset-unresolved candidate is restricted
to existing unresolved incidents, so a missing asset identity is never silently
resolved by grouping. Unresolved evidence can still be attached explicitly to a
resolved incident; the incident asset is never replaced or guessed.

## Service/API boundaries

- `IncidentService.create_from_evidence()` commits incident + evidence + audit in one
  transaction, upserts by `dedupe_key`, tolerates `IntegrityError` under concurrency,
  and returns the existing incident rather than duplicating it.
- `attach_evidence()` is idempotent on `(source_type, source_id)`.
- Lifecycle: `open -> triage -> investigating -> resolved -> closed` plus the explicit
  `resolved -> investigating` reopen. Everything else is rejected.
- `PATCH /api/v1/incidents/{id}/status` to `closed` invokes
  `require_knowledge_reviewer`; the reviewer identity is recorded as owner and in the
  audit payload. Unauthenticated callers are denied by `get_current_user`.
- Endpoints: list/detail/create/attach evidence/list evidence/status transition under
  `/api/v1/incidents`.

## Disposable PostgreSQL evidence

- Container: `eims-incident-core-pg-20261116` (`pgvector/pgvector:pg16`, loopback
  `56448`).
- Database `eims_incident_test`, role `eims_incident_test` verified
  `NOSUPERUSER / NOCREATEDB / NOCREATEROLE`.
- Ephemeral password generated in-process per command and supplied only through
  environment variables; never written to a file, artifact or document.
- Bootstrap `postgres` was used only to create the role/database and preinstall
  `vector`/`pg_trgm`. Alembic and tests ran as the non-superuser role.
- Alembic upgrade completed as that role; `alembic current` returned
  `b8d3f5c1a720 (head)` and `alembic heads` reports exactly one head.

## Verification

- Incident suite: **60 passed, 0 failed, 0 errors, 0 skipped**, exit 0.
- JUnit: `test-results/incident-core-20261116.xml`.
- Focused regressions (`test_timeline.py` plus analyzer unit tests):
  **261 passed, 0 failed, 0 errors, 1 skipped**, exit 0. The skip is the existing
  Windows-host symlink limitation in `test_analyzer_evaluation.py`.
- JUnit: `test-results/incident-core-regressions-20261116.xml`.
- Python compile for changed/new files: PASS.
- Ruff F401/F841/E402 for new files: PASS. The only findings in modified files are
  pre-existing E402/F401 patterns in `backend/main.py` and `migrations/env.py`.
- `git diff --check`: exit 0 (line-ending warnings only).
- Branch/HEAD unchanged: `integration/eims-consolidated` /
  `85493b2131d3e353453072559a5dfc301d75dd06`.
- Worktree after this snapshot: 126 entries (57 modified preserved, 69 untracked).

## Boundaries

- No Operational DB, Redis or MinIO access.
- No commit, push, reset, clean, checkout, stash or rebase.
- No dashboard/UI and no Browser Acceptance claim.
- No existing analyzer/timeline behavior changed.
- Independent review and human acceptance of incident semantics remain outstanding.
