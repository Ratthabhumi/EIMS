# A17 — Final Findings Register

**Date:** 2026-11-19 · **HEAD:** `85493b2` · Read-only audit; no fixes applied.

Severity: CRITICAL / HIGH / MEDIUM / LOW / INFO.
Impact: **A** delivery blocker · **B** security-acceptance blocker · **C** quality · **D** deferred · **E** documentation.

## 1. Historical findings — current disposition

| ID | Original | Current source status | Evidence | Disposition |
|---|---|---|---|---|
| **F1** | Maintenance CLI could destroy auth rows | CLI **exists and is enabled**: `tools/maintain_analyzer_sessions.py` requires `EIMS_MAINTENANCE_DATABASE_URL` + `--apply`; default is dry-run. It validates the driver only. The library function it calls defaults to `dry_run=False`. | `tools/maintain_analyzer_sessions.py:12-36`; `backend/domain/analyzer/services/session_maintenance.py:8,30` | **PARTIALLY RESOLVED** — CLI not disabled as reported; see NF-2/NF-3 |
| **F2** | `_urlsplit` local import makes R-7 unreachable | **Not reproducible.** No `_urlsplit` and no `BENCHMARK_TARGET_MISMATCH` appears in source or tools; the tokens appear only in prior reports. `main()` calls `_assert_benchmark_safety()` before engine creation. | repo-wide grep; `tools/sprint11_benchmark.py:247-273` | **STALE / NOT VERIFIED** (NF-7). Do not claim R-7 verified: the named check does not exist |
| **R-1** | DB identity not enforced at mutation boundary | Unchanged: only the configured URL is used; no connection-identity verification found. Source inspection only — not independently re-verified. | `backend/infrastructure/database.py`; `clear_db.py` | **BLOCKED (open HIGH)** |
| **R-2** | Test isolation not operationally verified | Guard-before-engine pattern only | `tests/incident_db_support.py` (inspection) | **PARTIAL** |
| **R-3** | Gateway authorization not wired | **Artifact absent**: `gateway/lib/risk-policy.mjs` does not exist in EIMS | `Test-Path` → False | **ARTIFACT NOT FOUND** (was "SAFE-DISABLED") |
| **R-4** | Journal has no runtime consumer | **No journal implementation found** in the tree | file search for `*journal*` → none | **NOT IMPLEMENTED / NOT TRUSTED** |
| **R-5** | Seed deletion target safety unproven | Seed script performs `DELETE FROM analysis_history WHERE parse_method=:pm`; no env guard found | `tools/seed_analyzer_incident.py:443` | **OPEN (NF-6)** |
| **R-6** | Benchmark target check is name-only | Confirmed: blocklist is `endswith("registry")` plus a `yes-i-know-what-i-am-doing` override | `tools/sprint11_benchmark.py:62,96-119` | **CONFIRMED (NF-4)** |
| **R-7** | Historical manifest lacks per-file hashes | All four manifests re-hash to their declared SHA-256 | §Evidence below | **MITIGATED for integrity; claim of target verification still unavailable** |
| **RR-8** | Structural tests / false assurance | `tests/test_a17_closure_behavior.py` no longer exists; its 4/4 cannot be reproduced | `Test-Path` → False | **CONFIRMED (NF-5)** |

## 2. New findings

### NF-1 — CRITICAL — Unguarded destructive script (`clear_db.py`)
- **File:** `clear_db.py` (repository root, 20 lines).
- **Behaviour:** initialises the app's own `database_engine` and executes
  `TRUNCATE TABLE analysis_history RESTART IDENTITY CASCADE` and
  `TRUNCATE TABLE ai_knowledge RESTART IDENTITY CASCADE`.
- **Guard:** none — no environment check, no confirmation, no database-name check,
  no dry-run. It uses whatever `DATABASE_URL` the application is configured with.
- **Impact:** one command destroys the analyzer history and knowledge base of the
  operational database. **A (delivery blocker for a safe demo) and B (security).**
- **Smallest safe disposition:** exclude from the delivered demo/handover and mark
  clearly, or remove it in a separately authorized change. Not fixed here.

### NF-2 — MEDIUM — `cleanup_auth_records` defaults to destructive
- **File:** `backend/domain/analyzer/services/session_maintenance.py:8` (analyzer sessions, not incident evidence).
- **Detail:** `dry_run=False` by default; the function executes `DELETE` inside its
  own transaction with `FOR UPDATE SKIP LOCKED`. It is importable by any in-process
  code and needs only a session.
- **Callers:** `tools/maintain_analyzer_sessions.py:30` (dry-run unless `--apply`)
  and tests. **No runtime caller** was found, so it is not reachable over HTTP.
- **Impact:** B. Any future code path that calls it without `dry_run=True`
  deletes rows. The default should be safe-by-default.

### NF-3 — MEDIUM (documentation) — Maintenance CLI is not SAFE-DISABLED
- **File:** `tools/maintain_analyzer_sessions.py`.
- **Detail:** fully functional; `--apply` performs the deletion. It validates the
  driver is `postgresql+asyncpg` but not host/database/role.
- **Impact:** E (documentation) with a security caveat. The operational handoff and A17
  narrative must not claim this tool is disabled.

### NF-4 — MEDIUM — Benchmark safety is name-suffix only
- **File:** `tools/sprint11_benchmark.py:62,92-119,270-273`.
- **Detail:** guard refuses empty URL and names ending in `registry`, with an
  environment override. It does not verify host, port, role, or actual connection
  identity before `TRUNCATE` of four core tables.
- **Impact:** B. Confirms R-6; exclude the benchmark from any claim of verified
  target safety.

### NF-5 — MEDIUM — A17 artefacts missing (unverifiable claims)
- `gateway/lib/risk-policy.mjs`: absent.
- Journal implementation: absent.
- `tests/test_a17_closure_behavior.py`: absent.
- **Impact:** C/E. Prior statements about these controls cannot be evidenced from
  the repository; they must be reported as "not present" rather than "passing".

### NF-6 — MEDIUM — Seed script performs a DELETE without an environment guard
- **File:** `tools/seed_analyzer_incident.py:436-448`.
- **Detail:** deletes legacy synthetic rows scoped by `parse_method`; the docstring
  says it never deletes, which its own code contradicts for that predicate.
- **Impact:** C/B. Scoped, but the documentation claim is inaccurate.

### NF-7 — LOW — F2 is not reproducible
- No `_urlsplit` and no `BENCHMARK_TARGET_MISMATCH` in source or tools (the tokens
  appear only in earlier reports). R-7 as a named check does not exist in the current
  source. Report as **STALE**, not as "fixed" or "verified".

## 3. Evidence hashes (recomputed 2026-11-19)

| File | SHA-256 | Result |
|---|---|---|
| `evidence/v12-a17-final-manifest.json` | `A108C4D074CB668B855128B7C74006E54F7CB9CE227F0D24D77C8DFB42D6D578` | VERIFIED |
| `evidence/A17_PHASE6_FINAL_EVIDENCE_MANIFEST.json` | `5F5423EE449D7A3474DA5464F675C0423544921B632521465E776AF7D6A55E5B` | VERIFIED |
| `evidence/A17_PHASE6_1_FINAL_EVIDENCE_MANIFEST.json` | `37DFF7E65A0FF58FEABE68A5E76EF5C2F5F244B35222EA0ED8FDE71CA3D460E5` | VERIFIED |
| `evidence/A17_FINAL_SIGNOFF_MANIFEST.json` | `1FB74499046B63A3945090470DE4983BDE67A1FEE75AC4F509794C67BAAEC179` | VERIFIED |

## 4. Summary

| Severity | Count (distinct) | IDs |
|---|---|---|
| CRITICAL | 1 | NF-1 |
| HIGH | 1 | R-1 |
| MEDIUM | 5 | NF-2, NF-3, NF-4 (=R-6), NF-5, NF-6 (=R-5) |
| LOW | 2 | NF-7, R-2 |
| Not present | 2 | R-3, R-4 |

R-5/NF-6 and R-6/NF-4 are the same condition reported under the historical and new
schemes; they are counted once.

No fix is applied in this audit.
