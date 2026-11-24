# EIMS V12 — A13 Remediation Report and Finding Closure

Date: 2026-11-18 (Asia/Bangkok)
Base: A12 remediation state (A11 frozen `53EE6A40…`, A12 manifest `5E4E4AE6…`)
Workspace: `%TEMP%\v12-a13\EIMS`

## 1. Changes (7 modified, 5 added)

| File | Change | Finding |
|---|---|---|
| `tests/disposable_guard.py` | strict allowlist + identity guard: marker, exact endpoint match, DB name/role, Redis index, MinIO bucket prefix, schema prefix, operational denylist | EIMS-F1 |
| `tests/test_fixture_isolation_contract.py` | 20 contract checks incl. wildcard and operational-bucket refusal | EIMS-F1 |
| `backend/core/config.py` | `AUTH_MODE` must be explicit outside development; message corrected | EIMS-F2 |
| `tests/test_auth_mode_contract.py` | 6 checks (production/staging/development/invalid) | EIMS-F2 |
| `docker-compose.yml` | loopback bindings, `${VAR:?}` secrets, private bucket, env-driven minio setup | EIMS-F3 |
| `tests/test_compose_security_audit.py` | asserts hardened baseline + documented allowlist | EIMS-F3 |
| `tools/sprint11_benchmark.py`, `tools/sprint12_search_verify.py` | guard added before `TestClient` (review RV-1) | EIMS-F1 |
| `docs/V12_A13_*.md` (4) | isolation, audit design, ledger correction, vector plan | F4/F5/F6 |

## 2. Tests (offline only)

| Suite | Result |
|---|---|
| `test_fixture_isolation_contract.py` | **20 passed** |
| `test_auth_mode_contract.py` | **6 passed** |
| `test_compose_security_audit.py` | **9 passed** |
| combined focused run | **35 passed** |
| default settings, timeline test | **skipped**, 0 connection attempts |

## 3. Finding disposition

| Finding | Status | Note |
|---|---|---|
| EIMS-F1 | **FIXED_IN_WORKSPACE** | strict guard at every lifespan entry incl. tools; residual: allowlist is operator-controlled |
| EIMS-F2 | **FIXED_IN_WORKSPACE** | explicit mode required outside development; demo refused |
| EIMS-F3 | **PARTIAL** | secrets/ports/bucket fixed; Redis auth, pgbouncer plain auth and `:latest` images remain |
| EIMS-F4 | **DESIGN_COMPLETE** | migration + verifier proposed, not applied; no external anchor, so "tamper-evident" may not be claimed |
| EIMS-F5 | **RESOLVED_AS_SEMANTIC** | ledger recorded deployed head `a3d6f1e8c295`; repo head `c4e8a1f7b932`; correction record written, ledger untouched |
| EIMS-F6 | **DESIGN_COMPLETE** | plan only; no service started; model contract UNVERIFIED |

## 4. Review

Claude Code A13 review: **ACCEPT_WITH_FINDINGS**. Addressed: RV-1 (tools bypass), RV-2 (wildcard/operational bucket), RV-8 (message), RV-9 (docs now in workspace). Open: RV-3 (no server-side identity attestation), RV-4 (schema intent variable), RV-5 (skip can hide non-run), RV-6 (regex-based wiring test), RV-7 (parallel guard), RV-10/11/12 (compose residuals).

The fixes after the review were verified by tests but **not re-reviewed**.
