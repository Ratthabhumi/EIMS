# EIMS — A17 Final Full Project Audit

**Date:** 2026-11-19 · **Branch:** `integration/eims-consolidated` · **HEAD:** `85493b2`
**Mode:** read-only source audit. No source change, no migration, no container, no operational DB.

## 1. Executive summary

EIMS is a working, substantial system: asset registry, telemetry/EVTX ingestion,
analyzer, incident correlation, search/timeline, API and dashboard all exist in
source and are wired into the FastAPI runtime. The **core analyzer → incident →
evidence** path is the strongest part of the project and is the defensible
demonstration area.

The project **cannot be presented as security-accepted**. Four earlier risk items
remain open, and this audit found **one new destructive path that is fully
unguarded** (`clear_db.py`) plus a documentation claim that does not match the
code (the maintenance CLI is *not* SAFE-DISABLED).

Several A17 artefacts referenced by earlier reports **do not exist in the current
tree**, so those claims cannot be re-verified: `gateway/lib/risk-policy.mjs`,
any journal implementation, and `tests/test_a17_closure_behavior.py`. The
reviewer's F2 description (`_urlsplit`, `BENCHMARK_TARGET_MISMATCH`) is **not
reproducible**: neither symbol exists anywhere in the repository.

**Decision: CLOSED — WITH EXPLICIT EXCLUSIONS. Security Acceptance: NOT ACCEPTED.**

## 2. Repository identity

| Item | Verified value |
|---|---|
| Root | `C:\Users\MewMew\Desktop\Co-op\EIMS` |
| Branch / HEAD | `integration/eims-consolidated` / `85493b2` |
| Working tree | **175 entries**: 59 modified, 116 untracked, 0 staged |
| Test DB access | none performed |
| Containers / services | none started or stopped |

The tree is **not** 59/207 as historically reported; the count has grown. It was
not cleaned, reset or reverted.

## 3. Repository inventory (first-party)

| Area | Location | Status |
|---|---|---|
| API | `backend/api/routers/**` | implemented, wired in `backend/main.py` |
| Analyzer | `backend/domain/analyzer/**` | implemented; main product path |
| Telemetry / EVTX | `backend/domain/telemetry/**` | implemented; workers started in lifespan |
| Incident | `backend/domain/incident/**` | implemented (v1 + v1.1 ingest) |
| Asset registry | `backend/domain/asset_registry/**` | implemented |
| Search / timeline | analyzer history + telemetry queries | implemented |
| Dashboard | `clients/dashboard/**` | implemented (not exercised here) |
| USB auditor | `clients/usb_auditor/**` | packaged client |
| Tools / CLIs | `tools/**`, `clear_db.py` | several destructive paths |
| Migrations | `migrations/versions/**` | 12+ revisions, single head `c4e8a1f7b932` |
| Tests | `tests/**` | mixed: unit, integration (DB-gated), structural |
| Evidence | `evidence/**`, `test-results/**` | historical manifests verified |

## 4. Destructive operation inventory (first-party)

Filtered to repository code (vendored `.venv`/`dist` excluded). Scripts found in
13 files; the material ones:

| Path | Operation | Guard | Reachability | Severity |
|---|---|---|---|---|
| `clear_db.py` | `TRUNCATE analysis_history, ai_knowledge` via app `database_engine` | **NONE** | `python clear_db.py` | **CRITICAL** |
| `backend/domain/analyzer/services/session_maintenance.py:8,30` | `DELETE` sessions/login windows | function-level: retention+batch validation; **`dry_run=False` by default** | importable; no runtime caller | HIGH |
| `tools/maintain_analyzer_sessions.py:30` | calls the above | requires `EIMS_MAINTENANCE_DATABASE_URL`; `--apply` to delete; **not** disabled | operator CLI | MEDIUM |
| `tools/sprint11_benchmark.py:270` | `TRUNCATE` 4 tables | DB-name suffix blocklist + override env | operator CLI | HIGH |
| `tools/seed_analyzer_incident.py:443` | `DELETE FROM analysis_history WHERE parse_method=:pm` | scoped predicate only | operator script | MEDIUM |
| `backend/api/routers/analyzer/admin.py`, `history.py`, `evaluations.py` | deletes via API | route auth (not exercised here) | HTTP | MEDIUM (unverified) |
| `backend/domain/analyzer/services/bundle.py` (10) | cleanup of extracted files | temp-dir scoped | runtime | LOW |

## 5. Functional audit (by subsystem)

| Subsystem | Verification class | Evidence |
|---|---|---|
| Asset management | IMPLEMENTED + RUNTIME WIRED | routers/registry/controller/repository |
| Telemetry ingest → persistence | IMPLEMENTED + TESTED-LIMITED | worker + outbox; 114 offline tests incl. ingest unit |
| EVTX upload/parse | IMPLEMENTED + TESTED-LIMITED | parser + worker; no live MinIO run here |
| Analyzer (submit/bundle/offline) | IMPLEMENTED + TESTED-LIMITED | 3 history insert sites; incident emission |
| Incident correlation | IMPLEMENTED + TESTED | `test_incident_correlation.py` passes |
| Incident ingestion v1.1 | IMPLEMENTED + DB-INTEGRATION TESTED (prior run) | outbox + consumer, migration `c4e8a1f7b932` |
| Search / timeline | IMPLEMENTED (not behaviourally exercised) | query paths read only |
| AI enrichment | IMPLEMENTED (external dependency) | prompt/parse paths; no live model call |
| Dashboard | IMPLEMENTED (NOT VERIFIED here) | no service started |
| USB auditor | IMPLEMENTED (packaged client) | scanner code present |
| Benchmark | **BROKEN/UNSAFE FOR DEMO** | name-only guard; TRUNCATE |
| Maintenance CLI | **MIS-DOCUMENTED** | fully enabled, not SAFE-DISABLED |

## 6. Database and integrity

- Models and migrations exist; single head `c4e8a1f7b932`.
- Incident/evidence uniqueness and idempotency are implemented and tested offline.
- **R-1 remains BLOCKED:** no evidence that mutation boundaries verify the actual
  connection identity (host/role/database), only the configured URL.
- **R-2 PARTIAL:** test isolation uses guard-before-engine, not operationally verified.
- `clear_db.py` bypasses every database-safety convention in the repo.

## 7. Security audit

| Control area | Finding |
|---|---|
| Authentication | JWT/session paths exist; not re-verified against a running service |
| Authorization | Route-level dependencies exist for reviewer-gated incident close; **gateway authorization artifact absent** (`gateway/lib/risk-policy.mjs` not found) → R-3 |
| Secrets | No credential values were printed; `.env*` is denied by the Chat_HAND gateway, outside this audit |
| Input/file | Upload size caps and parser guards exist (prior reviews); not re-exercised |
| Destructive safety | **New CRITICAL `clear_db.py`**; maintenance CLI enabled; `dry_run=False` default in the library function |
| Audit/journal | **No journal implementation found** in the current tree → R-4 stands; no tamper-evidence claim is supportable |

## 8. Test quality

- `python -m compileall -q backend tools` → exit 0.
- `pytest tests/test_incident_correlation.py tests/test_incident_ingest_unit.py tests/test_incident_ingest_v11_recovery_unit.py` → **114 passed**, 1.87 s, exit 0.
- Not run: any DB-backed, MinIO, Redis, browser or service-starting suite
  (side effects not provable offline).
- **False-assurance risk confirmed structurally:** the previously cited
  `tests/test_a17_closure_behavior.py` does not exist, so its 4/4 result cannot be
  reproduced. Tests that assert module structure rather than executed behaviour
  must not be counted as behavioural evidence.

## 9. Evidence integrity

| Artifact | Declared SHA-256 | Recomputed | Result |
|---|---|---|---|
| `evidence/v12-a17-final-manifest.json` | `A108C4D0…D578` | matches | **VERIFIED** |
| `evidence/A17_PHASE6_FINAL_EVIDENCE_MANIFEST.json` | `5F5423EE…5E5B` | matches | **VERIFIED** |
| `evidence/A17_PHASE6_1_FINAL_EVIDENCE_MANIFEST.json` | `37DFF7E6…60E5` | matches | **VERIFIED** |
| `evidence/A17_FINAL_SIGNOFF_MANIFEST.json` | `1FB74499…C179` | matches | **VERIFIED** |

Historical manifests are intact. Their *claims* are separately assessed and some
are not reproducible (above).

## 10. Findings

See `A17_FINAL_FINDINGS_REGISTER.md` for the full register. New IDs:

- **NF-1 (CRITICAL)** `clear_db.py` unguarded TRUNCATE on the application DB.
- **NF-2 (MEDIUM)** `cleanup_auth_records` defaults to `dry_run=False` and is importable in-process (no runtime caller found).
- **NF-3 (MEDIUM, documentation)** maintenance CLI claimed SAFE-DISABLED; it is enabled (dry-run unless `--apply`).
- **NF-4 (MEDIUM)** benchmark guard is database-name-suffix only with an override.
- **NF-5 (MEDIUM)** A17 artefacts missing → prior claims unverifiable.
- **NF-6 (MEDIUM)** seed script performs a DELETE with no environment guard.
- **NF-7 (LOW)** F2 as described is not reproducible: no `_urlsplit` or `BENCHMARK_TARGET_MISMATCH` appears in source or tools (the tokens appear only in prior reports).

## 11. Confirmation

No file was modified, created outside the audit documents, staged, committed or
pushed. No database was contacted. No migration, seed, cleanup or service action
was performed. Historical evidence files were read only.
