# EIMS V12 — A12 C1/C7 Safe Test Plan (Prepared, Not Run)

Date: 2026-11-18 (Asia/Bangkok)
Status: **NOT RUN.** This plan replaces the earlier C1/C7 assumptions with a verified dependency map.

## 0. What changed since A11

A11 called C1 "dependency-free" for 770 tests based on the absence of the `client` fixture and of `EIMS_TEST_*` variables. The review showed that some tests call `TestClient(app)` directly, which starts the full lifespan. The A12 guard now blocks that path, but C1 must still be classified honestly.

**C1 is renamed: "no declared external dependency and no unguarded lifespan".** It is not called dependency-free.

## 1. Verified dependency map (from source, not from test names)

| Group | Files | Tests | Behaviour | Safe now? |
|---|---:|---:|---|---|
| A. Pure unit / contract | 33 | ~741 | no `TestClient`, no `EIMS_TEST_*` | yes |
| B. Lifespan-guarded `client` fixture | 6 | 29 | would start the full lifespan; now skips unless disposable | **yes, as skips** |
| C. Direct `TestClient(app)` (previously unguarded) | 4 | see below | now guarded and skips | **yes, as skips** |
| D. Explicit disposable service tests | 14 | 139 | require `EIMS_TEST_DATABASE_URL` etc. | only with disposable services |

Group C files (guard added in A12): `test_auth_modes.py`, `test_analyzer_investigation.py`, `test_analyzer_reliability.py`, `test_analyzer_integration_stability.py`.

Note: group B and group C overlap in intent but not in files (B is the six `client`-fixture files; C is four separate direct call sites). The exact per-file counts must be recomputed with `--collect-only` on the A12 workspace before the run; do not reuse the A11 938 total blindly.

## 2. C7 — Agent Monitor preflight

Before running either suite:

1. Copy the monitor directory into a disposable root (never run against the live `%LOCALAPPDATA%` state).
2. Set `EIMS_MONITOR_STATE_ROOT` (or the suite's equivalent) to a `%TEMP%` path.
3. Record the source hashes of the 12 monitor files before and after the run.
4. Record the process tree before and after; assert no orphan `powershell`/`conhost` remains.
5. Assert the fixture directory is unchanged after the run.
6. Capture raw stdout/stderr and the two suite totals **separately**.

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\agent-monitor\tests\Test-WatchEimsAgentJobs.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\agent-monitor\tests\Test-LaunchEimsAgentMonitor.ps1
```

Expected: watcher 169/169 and launcher 171/171 — **two separate suites**. The historical counts may be cited only as historical until this run produces a current transcript.

## 3. C1 — execution order

1. Run group A first (pure unit). Expected: no skips caused by the guard.
2. Run group B and C next. Expected: guard-driven skips with a clear message; **zero** connection attempts in the log.
3. If any test in B or C does not skip, stop: the guard is incomplete.
4. Do not run group D without disposable services and explicit approval.

## 4. Stop conditions

- Any connection line (`Connecting to Postgres`, `Connecting to Redis`) during groups A–C.
- Any guard-driven skip missing its message.
- Any orphan process after C7.
- Any source hash change inside the monitor directory.
- Any test edit needed to pass.

## 5. Evidence

Per step write `evidence/v12-track-c-results/<step>/result.json` with: step, command, base frozen manifest SHA-256, A12 workspace manifest SHA-256, collected/passed/failed/skipped, exit code, timestamps, transcript hash.

No step in this plan has been executed.
