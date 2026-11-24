# EIMS finalization delta — 2026-11-15

## Runtime and acceptance evidence

- Work remained on Mew through Remote Desktop Commander. No Work Mode, Git reset/clean/stash, commit, push, or operational-database access.
- Branch/HEAD verified unchanged: `integration/eims-consolidated` / `85493b2`.
- Browser Acceptance final16: **33/33 PASS**; full Playwright: **2/2 PASS**, exit code 0. Evidence:
  - `test-results/secure-browser-acceptance-20261115-final16/secure-browser-acceptance.json`
  - `test-results/secure-browser-acceptance-20261115-final16/playwright/.last-run.json`
- final16 includes a unique proposal title per run and cross-user History DELETE denial with owner record retained.
- Production application-path smoke used `backend.main:app` against dedicated synthetic DB `eims_browser_acceptance_20261115`, not an operational database. Login, Windows Event 1129 Analyzer, History persistence, Follow-up, Stats and Health succeeded. Health was HEALTHY; PostgreSQL, Redis and MinIO were UP.
- Production smoke History ID 43 is synthetic test data only; it is not a customer incident or production evidence.
- The full focused Analyzer Reliability + PostgreSQL Integration + timestamp contract suite completed at 100%, process exit 0. A separate six-case PostgreSQL round-trip subset passed 6/6.
- The Knowledge lifecycle integration test, extended with full-text search assertions, passed with exit 0.
- Dashboard `npm run build`: exit 0; TypeScript passed; static generation 15/15.
- Targeted Ruff `F401,UP017`, Python compilation and `git diff --check`: PASS. Full all-rules Ruff is still not clean due pre-existing findings outside this focused scope; do not claim global lint cleanliness.

## Root-cause fixes and code changes in this delta

- Replaced `duckduckgo-search` import with maintained `ddgs` API and aligned `requirements.txt` plus `pyproject.toml` to `ddgs>=9.16.1,<10.0.0`. The installed `ddgs` package was already present; no duplicate install was needed.
- Removed deprecated `datetime.utcnow()` use from AnalysisHistory default and Stats aggregation. The legacy PostgreSQL `analysis_history.created_at` column is `TIMESTAMP WITHOUT TIME ZONE`; the ORM explicitly stores UTC-naive values to avoid an unsafe schema conversion.
- Added `tests/test_analyzer_timestamp_contract.py` to prove the default is UTC-naive.
- Updated a stale test import to `ddgs`.
- Isolated PostgreSQL Analyzer integration tests from previously approved synthetic Knowledge entries by deleting KnowledgeEntry rows inside the outer test transaction; the outer transaction rolls back, preserving the shared synthetic DB. This prevents test results from depending on Browser Acceptance leftovers.
- Added approved-only literal full-text Knowledge search across title, source family, diagnostic identity, root cause, solution steps, impact, prevention, evidence notes and references. LIKE metacharacters are escaped; query is parameterized; pending/rejected knowledge is never returned.
- Added the search field to the Knowledge UI. Search executes on explicit Search/Enter rather than each keystroke.
- Added integration assertions proving pending proposals are not searchable and approved proposals are searchable by resolution text.

## Remaining project-closure gates

1. Independent domain reviewer must review all 12 DEV gold cases, their evidence, diagnosis and resolution claims; then freeze the gold set and run the 5 HELDOUT cases without tuning against them.
2. Build a curated initial approved Knowledge corpus from authoritative vendor sources and authorized/sanitized incidents. Synthetic acceptance records are not a production knowledge corpus.
3. Add structured applicability (product/version/environment/prerequisites), remediation safety (risk level, validation and rollback), and usage outcome feedback. Full-text search is now present, but these fields and feedback lifecycle remain outstanding.
4. Add explicit JWT `exp` boundary acceptance separately from already-proven server-side DB-session expiry.
5. Witness backup/restore and rollback, WAL/PITR, retention, measured RPO/RTO, failover/recovery, capacity/load, TLS/secrets, monitoring and operational ownership sign-off.
6. Run a controlled Engineer pilot with authorized sanitized incidents and capture correctness, safety and usefulness feedback.

## Preservation and interpretation

- No project closure is declared.
- Do not treat the synthetic Production-path smoke as deployment or production certification.
- Existing modified/untracked repository work remains preserved; no commit/push/reset/clean/stash was performed.
