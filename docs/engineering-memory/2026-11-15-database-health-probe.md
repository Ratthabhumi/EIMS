# EIMS Engineering Memory — 2026-11-15

**Snapshot ID:** EIMS-ENGMEM-2026-11-15-DB-PING-001  
**Snapshot type:** Immutable continuation record  
**Repository:** `C:\Users\MewMew\Desktop\Co-op\EIMS`  
**Branch:** `integration/eims-consolidated`  
**HEAD:** `85493b2131d3e353453072559a5dfc301d75dd06`  
**Machine:** Mew / Windows 11  
**Runtime:** CPython 3.14.3

## 1. Operating rules

- ChatGPT is the central technical orchestrator. Delegate research, implementation, independent review, and evidence verification by capability.
- Use Remote Desktop Commander for repository and runtime operations on Mew. **Work Mode is explicitly excluded from the EIMS workflow.**
- Preserve the existing Git working tree. No reset, clean, checkout-overwrite, stash, commit, push, or deletion of existing evidence.
- Never access or mutate the Operational DB. Use positively identified disposable databases and synthetic/public fixtures only.
- Do not rerun the broad 540-test suite without a specific evidence-based reason.
- A test is PASS only with a completed process, exit code 0, and retained report or direct service evidence. SKIP and incomplete runs are not PASS.
- Browser Acceptance remains NOT PASSED until the complete browser flow, JUnit, and supporting evidence are retained.
- Fix root causes. Do not increase timeouts merely to hide a failure.
- Keep implementer and verifier separate where possible. A reviewer must not claim a review unless the connected tool returned actual review content.

## 2. Repository baseline and preservation

At the start of this continuation:
- Branch: `integration/eims-consolidated`
- HEAD: `85493b2131d3e353453072559a5dfc301d75dd06`
- Working tree: 32 modified tracked paths and 30 untracked paths.
- No commit or push was performed.

After implementation, dependency updates, and engineering-memory additions, re-read `git status --short` before any further work. Existing modifications and untracked files must remain intact.

## 3. Database health-probe finding

The previous `AsynchronousDatabaseEngine.ping()` limited only the `SELECT 1` execution. Connection-pool checkout and connection cleanup were outside the deadline. This left the health endpoint vulnerable to an indefinitely delayed pool checkout or cleanup path. Caller cancellation also needed explicit lifecycle verification.

The installed runtime was Python 3.14.3, SQLAlchemy 2.0.52, and asyncpg 0.31.0 before this correction. The project dependency declaration contradicted the actual driver runtime: `pyproject.toml` constrained asyncpg below 0.30, while the active environment used 0.31.0.

### SQLAlchemy cancellation semantics verified

The official SQLAlchemy 2.0 changelog documents relevant asyncio fixes:
- 2.0.55: context-manager close now completes before cancellation is propagated; related pool reset, checkout, repeated-cancellation, and connection-discard cases were repaired.
- 2.0.56: cancellation handling in `AsyncConnection.close()` and an async pool checkout cancellation race were fixed.
- 2.0.57 was the installed version selected for this patch.

The installed SQLAlchemy 2.0.57 source was inspected directly:
- `AsyncConnection.__aexit__()` awaits `_run_to_completion(self.close())`.
- `_run_to_completion()` shields the close task, waits for cleanup to finish, and only then re-raises cancellation.

**Important deadline contract:** the 2-second deadline initiates cancellation across checkout, query, and context exit. It is not a hard wall-clock cutoff. SQLAlchemy intentionally waits for safe cleanup to complete; a stalled cleanup can therefore extend total elapsed time beyond 2 seconds. The probe records actual total elapsed time and whether the deadline expired. Do not replace this with detached background cleanup or return a connection to a disposed pool.

## 4. Implemented changes

Files changed in this continuation:
- `backend/infrastructure/database.py`
- `tests/test_database_ping_diagnostics.py` (pre-existing untracked test file extended)
- `pyproject.toml`
- `requirements.txt`

Implementation:
- One `asyncio.timeout(2.0)` context encloses `async with engine.connect()`, `SELECT 1`, scalar validation, and connection return.
- The result must contain scalar value `1`.
- Caller `asyncio.CancelledError` is not swallowed.
- Diagnostics distinguish checkout, execute, and cleanup; include phase timings, total elapsed time, `deadline_expired`, sanitized exception class, and pool status.
- No raw DSN, password, or exception text is emitted by the health-probe diagnostic.
- Dependency constraints are now aligned with the tested runtime:
  - `sqlalchemy[asyncio]>=2.0.57,<2.1.0`
  - `asyncpg>=0.31.0,<0.32.0`

asyncpg 0.31.0 adds Python 3.14 support. The environment was verified as SQLAlchemy 2.0.57 and asyncpg 0.31.0 after installation.

## 5. Verification evidence

### Focused pytest

Command:
```powershell
.\venv\Scripts\python.exe -m pytest -q tests/test_database_ping_diagnostics.py tests/test_health_probe_concurrency.py tests/test_synthetic_health_contract.py
```

Result: **15 passed, 0 failed, 0 errors, 0 skips**.
- Database ping diagnostics: 12 passed.
- Health-probe concurrency: 1 passed.
- Synthetic health contract: 2 passed.
- Two existing dependency deprecation warnings remain (Starlette TestClient/httpx and pythonjsonlogger import path).

### Static / dependency checks

- Ruff on `backend/infrastructure/database.py` and `tests/test_database_ping_diagnostics.py`: PASS.
- `pip check`: PASS, no broken requirements.
- `git diff --check`: PASS; Git emitted existing LF-to-CRLF working-copy warnings only.

### Real disposable PostgreSQL lifecycle verification

Target: disposable clone container `eims-history-repro-pg-20261114`, loopback port 56442, database `eims_history_repro_20261114`. This is not an Operational DB. The verification used `SELECT 1` only and did not modify database rows or schema.

Using a pool with size 1 and max overflow 0:
1. Hold the only connection and call the probe. It returns `False` at the 200 ms deadline with `phase=checkout`, `deadline_expired=True`, and a measured checkout duration.
2. Release the held connection. The next probe returns `True`; pool checked-out count returns to zero.
3. Delay `AsyncConnection.close()` deliberately. The probe remains pending after the deadline while safe cleanup is outstanding. Once cleanup is released, the probe returns `False`, logs `phase=cleanup` and total elapsed time, and the pool has zero checked-out connections.
4. The next probe after cleanup timeout returns `True`.
5. Cancel a caller during delayed cleanup. `CancelledError` propagates after cleanup; the pool has zero checked-out connections and a subsequent probe returns `True`.

Latest live run log: `%TEMP%\eims-ping-live-lifecycle-final.log`. Exit code 0.

## 6. Browser Acceptance and root-cause boundary

- Browser Acceptance remains **NOT PASSED**.
- No new Browser Acceptance run was started in this continuation.
- Earlier secure-browser attempts recorded 502/503 responses around Analyzer/History, upstream timeout symptoms, and `net::ERR_NETWORK_CHANGED`. Prior PostgreSQL process failures and proxy/network symptoms remain relevant evidence.
- This database-probe correction closes a confirmed lifecycle gap and proves pool recovery on a disposable clone. **It does not prove that this gap caused the earlier Browser 502/503 failures.**
- Do not label the Browser Acceptance root cause resolved until a live failing path is correlated across browser request IDs, HTTPS proxy/BFF logs, backend health/analyzer logs, SQLAlchemy pool state, and PostgreSQL activity.

## 7. AI and tool orchestration record

- Remote Desktop Commander connected to Mew and was used for repository reads, edits, focused tests, and disposable-clone verification.
- Claude Code CLI completed a read-only audit. It correctly challenged cleanup semantics, phase attribution, and the lack of real pool evidence. The SQLAlchemy source was then inspected and real cancellation-safe cleanup was tested against the disposable PostgreSQL clone.
- Parallel research was used for current SQLAlchemy and asyncpg release information.
- OpenCode auth inventory showed stored providers for Google, OpenAI OAuth, OpenRouter, xAI, DeepSeek, Groq, and Cloudflare Workers AI. However, OpenCode run-bridge attempts for Gemini and OpenAI returned `outcome=failed` with zero tokens; do not count those as completed reviews.
- Gemini, Grok, Cursor, Antigravity, Manus, and Codex desktop processes were visible on Mew, but their GUI sessions were not directly callable through the current connector. Do not fabricate their findings.
- Kilo config contains only the notebook-first Data agent, intended for Jupyter-based data investigation rather than repository code implementation; no Kilo CLI was available in PATH.
- OMC subagent tracking currently reports zero active/spawned agents; its replay file contains historical stop events only, with no recoverable task outputs.
- Liner search-agent invocation was unavailable due a payment-required response; do not retry without a changed account state.
- For future tasks, use connected agents only when invocation succeeds and actual output is available. Assign read-only review to a separate model from the implementation writer.

## 8. Next actions

1. Inspect current database pool settings, health route, and analyzer request lifecycle without repeating completed exploration.
2. Run a controlled concurrent Analyzer workload against a dedicated disposable PostgreSQL/Redis/MinIO environment. Capture pool checkout/overflow, PostgreSQL `pg_stat_activity`, backend logs, health transitions, and request correlation IDs.
3. Independently inspect the Next.js BFF and synthetic HTTPS proxy path for 502/503 propagation and network-change handling. Do not assume PostgreSQL is the sole cause.
4. Reproduce the relevant failure with evidence before changing additional pool or timeout settings.
5. Only after runtime stability is demonstrated, rerun Secure Browser Acceptance and retain complete JUnit plus supporting evidence.
6. Append new dated engineering-memory snapshots; do not overwrite this snapshot or historical evidence.
7. Request explicit approval before commit, PR, push, operational DB work, or destructive cleanup.

## 9. Final Git state for this snapshot

- Branch remains `integration/eims-consolidated`; HEAD remains `85493b2131d3e353453072559a5dfc301d75dd06`.
- Final status after this continuation: 34 modified tracked paths, 32 untracked paths, 66 total porcelain entries.
- This preserves the original 32 modified and 30 untracked paths; the two additional modified paths are dependency declarations, and two new untracked paths are the root agent pointer and engineering-memory directory. Existing untracked directories remain intact.
- `git diff --check` passes with existing line-ending warnings only. No commit, push, reset, clean, or stash was performed.
