# EIMS Engineering Memory — 2026-11-15 Analyzer Pool Starvation

**Snapshot ID:** EIMS-ENGMEM-2026-11-15-ANALYZER-POOL-002  
**Type:** Dated continuation snapshot; supersedes the prior snapshot as the current pointer, but does not erase it  
**Repository:** `C:\Users\MewMew\Desktop\Co-op\EIMS`  
**Branch / HEAD:** `integration/eims-consolidated` / `85493b2131d3e353453072559a5dfc301d75dd06`  
**Runtime:** Windows 11, CPython 3.14.3, SQLAlchemy 2.0.57, asyncpg 0.31.0  
**Execution:** Remote Desktop Commander on Mew; Work Mode explicitly excluded

## 1. Confirmed root cause in the Analyzer request lifecycle

A live, controlled reproduction was run against the disposable PostgreSQL clone `eims-history-repro-pg-20261114` on loopback port 56442. All direct SQL/database verification used this disposable clone. A later single read-only GET to the existing live `/api/v1/health` listener may have invoked a database ping before its target was confirmed; no write endpoint was called. See section 8.

Before the Analyzer fix:
- Pool size 2, max overflow 0.
- Two concurrent `build_summary()` calls each performed the RAG read and then blocked in synthetic external summary work.
- Both request sessions retained their checked-out connection while awaiting external work.
- Pool state: 2 checked out, 0 available.
- Health probe failed at checkout with a 200 ms test deadline; diagnostic reported `phase=checkout`, `deadline_expired=True`.
- Releasing the external work returned both connections to the pool and the health probe recovered.

This proves a real SQLAlchemy session/connection lifetime defect and a reproducible Analyzer-induced pool-starvation mode. It does **not** alone prove that this was the sole cause of the historical Browser 502/503 events.

## 2. Root-cause changes

### RAG summary lifecycle — `backend/domain/analyzer/services/summary.py`
- Engine-bound request sessions now use a dedicated short-lived `AsyncSession` for `search_similar_logs()`.
- The RAG session closes before the slower external summary/translation work begins.
- The caller's request session is not committed, rolled back, or closed by this helper.
- Connection-bound sessions remain caller-owned (for example, savepoint/transaction tests); they are not closed or committed by the helper.
- The helper uses `getattr(db, "bind", None)` so test doubles without a bind attribute remain supported.

### Explicit read-only transaction release — `backend/infrastructure/database.py`
- Added `rollback_read_only_transaction()`.
- It only operates on engine-bound sessions, only when a transaction exists, and refuses to roll back when ORM `new`, `dirty`, or `deleted` state is pending.
- It uses **rollback**, not commit. This avoids committing incidental Core DML and preserves caller transaction ownership at known read-only boundaries.
- It is a no-op for connection-bound sessions. Callers must invoke it only at a boundary known to contain read-only work.

### Vector knowledge export — `backend/domain/analyzer/services/vector_db.py`
- Embedding inference runs before the first vector-table query.
- A clean read-only caller transaction is released before the CPU/worker-thread embedding step.
- No-result/no-embedding paths release the read-only lookup transaction.
- Existing vector row updates and inserts still commit their intended vector knowledge changes.
- Secure-mode guard remains intact; private secure-user history is not published into the shared vector namespace.

### Offline import pipeline — `backend/domain/analyzer/services/import_pipeline.py`
- `_analyze_event()` releases the clean dedup-read transaction before external search and summary work.
- Pending ORM changes cause a safe failure rather than being silently committed or discarded.
- Subsequent history lookup/insert occurs after external work.

### History INSERT — `backend/api/routers/analyzer/analyze.py`
- Removed the post-commit `db.refresh()` that caused a second SELECT/checkout.
- PostgreSQL INSERT RETURNING supplies the generated primary key and mapped defaults.
- The isolated `MemoryHistory` evaluation sink was updated to emulate commit-returned id/created_at values instead of relying on a route-level refresh.

## 3. Verification

### Focused pytest
Command:
```powershell
.\venv\Scripts\python.exe -m pytest -q --junitxml="$env:TEMP\eims-analyzer-lifecycle-20261115-rerun.xml" tests/test_database_ping_diagnostics.py tests/test_health_probe_concurrency.py tests/test_synthetic_health_contract.py tests/test_analyzer_reliability.py tests/test_analyzer_integration_stability.py tests/test_sprint13_evidence_ingestion.py
```

Final result: **280 passed, 0 failed, 0 errors, 0 skipped**. Process exit code 0.
- JUnit: `%TEMP%\eims-analyzer-lifecycle-20261115-rerun.xml`
- Log: `%TEMP%\eims-analyzer-lifecycle-20261115-rerun.log`
- Warnings: existing Starlette/httpx and pythonjsonlogger deprecations; duckduckgo_search reports its package rename to ddgs.
- The first run exposed one evaluation-fixture mismatch after removing `db.refresh()`: MemoryHistory did not emulate INSERT RETURNING defaults. The fixture was corrected to populate id/created_at on commit, and the complete six-file rerun passed. The earlier failed log was retained.

### Real disposable PostgreSQL verification
Final run log: `%TEMP%\eims-analyzer-pool-repro-final.log`, exit code 0.
- Two concurrent Analyzer summary tasks reached external work.
- Pool checked-out connections during external work: **0**.
- Health probe while both Analyzer tasks were blocked externally: **True**.
- Health probe after both tasks completed: **True**.
- During deliberately blocked vector embedding: pool checked-out connections **0**, health probe **True**.
- Caller cancellation during embedding propagated as `CancelledError`; pool remained at zero checked-out connections.
- Final pool checked-out count: **0**.

Additional real PostgreSQL session verification:
- After a read-only `SELECT 1`: checked-out count 1.
- After `rollback_read_only_transaction()`: checked-out count 0.
- A subsequent query successfully checked out a connection again.
- INSERT RETURNING check inside an outer transaction/savepoint populated both primary key and created_at without calling refresh; outer transaction was rolled back, leaving no persisted test row.
- Log: `%TEMP%\eims-db-session-release-20261115.log`, exit code 0.

### Static checks
- Targeted Ruff checks for syntax/undefined-name classes (`E4,E7,E9,F821,F822,F823`, with `E402` excluded due an existing late import in the large reliability test file): PASS.
- `compileall` on changed backend modules: PASS.
- `git diff --check`: PASS; line-ending conversion warnings only.
- A broader all-rules Ruff invocation on legacy files reported numerous existing style/deprecation/catch-all findings across unrelated lines in `analyze.py`, `import_pipeline.py`, and `summary.py`. Do not represent the full-file Ruff baseline as clean; the focused correctness lint passed.

## 4. Browser Acceptance boundary

- Secure Browser Acceptance remains **NOT PASSED**.
- No new Browser Acceptance attempt was launched in this continuation.
- The Analyzer pool-starvation failure mode is now fixed and reproduced as fixed on a disposable PostgreSQL clone.
- The historical Browser 502/503 and `net::ERR_NETWORK_CHANGED` root cause is not yet fully correlated across the browser, HTTPS proxy, BFF, backend, pool, and PostgreSQL.
- Existing production app listeners and Operational DB containers were left untouched. Do not restart or point the running app at another database as an improvised verification.
- Next production-grade verification must use a separately launched, explicitly disposable stack and preserve full JUnit plus correlated request/proxy/backend/PG evidence.

## 5. Git and safety state

- Branch / HEAD remain `integration/eims-consolidated` / `85493b2131d3e353453072559a5dfc301d75dd06`.
- Final observed porcelain state at this checkpoint: 35 modified tracked paths, 32 untracked paths, 67 total entries.
- All prior work remains present. No reset, clean, stash, checkout overwrite, commit, or push was performed.
- All direct PostgreSQL connections and SQL work were restricted to the disposable clone on port 56442; synthetic insert was rolled back inside an outer transaction. The single possible health-endpoint ping described in section 8 is the only uncertainty about the live app's DB target; no data write was issued.
- No containers, volumes, schemas, buckets, or historical evidence were deleted.

## 6. AI orchestration

- ChatGPT coordinated the work and verified the evidence.
- Remote Desktop Commander performed all repository and runtime actions on Mew.
- Claude Code CLI completed a read-only review in the prior continuation; cleanup and session-lifetime concerns were tested against the installed SQLAlchemy source and disposable PostgreSQL.
- OpenCode Gemini/OpenAI run-bridge attempts returned failed outcomes with zero tokens; they are not counted as completed reviews.
- Kilo's configured agent is notebook-first Data, not a repository code reviewer. OMC subagent tracking showed zero active agents. Liner invocation returned payment-required. GUI processes for Gemini/Grok/Cursor/Antigravity/Manus/Codex were visible but did not yield callable independent review output in this continuation.
- Do not claim a review from an agent unless actual output is retrieved.
- A fresh independent review of the final Analyzer diff was attempted through Claude Code CLI but did not return review content (stdin/terminal invocation stalled); do not count it as a completed review. The earlier Claude read-only review covered SQLAlchemy cancellation/cleanup semantics, not the entire final Analyzer diff.

## 7. Next actions

1. Run a controlled multi-request Analyzer workload against a separately configured disposable application stack, not the live app listeners.
2. Capture request correlation IDs, pool checkout/overflow, backend timings, PostgreSQL `pg_stat_activity`, and HTTPS proxy/BFF status to determine whether any remaining 502/503 path exists.
3. Review all request handlers that call external inference/search while holding an engine-bound session; extend the same isolated-session or explicit read-only-release pattern only where evidence shows a held connection.
4. Only after runtime stability is demonstrated, rerun Secure Browser Acceptance and retain complete JUnit plus supporting evidence.
5. Append future dated snapshots; do not overwrite historical evidence. No commit/push without explicit approval.

## 8. Post-snapshot verification and access note

- After the final defensive change from `db.bind` to `getattr(db, "bind", None)`, the Analyzer reliability + Analyzer integration-stability smoke rerun completed: **224 PASS, 0 FAIL, 0 ERROR, 0 SKIP**, exit code 0. JUnit: `%TEMP%\eims-analyzer-final-smoke-20261115.xml`; log: `%TEMP%\eims-analyzer-final-smoke-20261115.log`.
- A narrow Ruff correctness check after the final code change passed. The only excluded rule was E402, which reports an existing late import in `tests/test_analyzer_reliability.py`. The earlier full-file Ruff run still has legacy style findings and is not represented as clean.
- During a preliminary readiness check, one read-only GET was sent to the existing backend `/api/v1/health` listener before its configured database target had been positively identified. That route may perform a database ping. No write or mutation endpoint was called. The PowerShell health-check process then stalled and an attempt to stop that process returned Access Denied. No further requests were sent to the live app listeners. Treat this as a possible single read-only health probe against the existing runtime; do not repeat. All subsequent database verification stayed on the disposable clone.
- Existing app listeners on 8000/3009/3449 and Operational DB containers were not restarted or reconfigured. Browser Acceptance was not run.

