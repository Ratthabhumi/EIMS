# Final test report (2026-11-22)

All runs use the project virtual environment against disposable, loopback PostgreSQL instances (non-superuser role, non-standard port); the operational database was never used. Skipped tests are not counted as passed.

| Command | Environment | Passed | Failed | Skipped |
|---|---|---:|---:|---:|
| `pytest tests --ignore=tests/test_analyzer_postgres_integration.py` (final code) | disposable PostgreSQL, `EIMS_DEMO_SOFT_DEPS=1` | **2077** | **0** | 51 |
| `pytest tests/test_analyzer_postgres_integration.py` | its own disposable DB | **75** | **0** | 0 |
| `tests/test_catalog_adapter.py`, `tests/test_certification_round3.py`, `tests/test_certification_round4.py`, `tests/test_certification_tools.py`, gates and catalog suites (focused, before the full run) | no database | 382 | 0 | 0 |
| `tests/test_knowledge_governance_api_pg.py` (13 scenarios) | disposable PostgreSQL, real authentication dependencies | 13 | 0 | 0 |

The 51 skips are the same environment-gated tests as in every previous run.

## An invalid run, reported
One earlier full run of the final code failed (34 failed, 38 errors; analyzer suite 71 failed). Every failure was `asyncpg CannotConnectNowError: the database system is in recovery mode`: the disposable PostgreSQL crashed and recovered during that run (its log shows automatic recovery). No code defect was involved; the full suite was re-run after the database recovered and passed as shown above. The first of the two earlier "final" runs was stopped on purpose because code changed after it started.

## Coverage of the requested test areas
Catalog adapter eligibility per class, import idempotency (service and CLI), content hash integrity (all 911 hashes equal the register), stale evidence and stale source, remediation risk (negation-aware rule, destructive action needs rollback), rollback completeness, recovery verification through the real Analyzer path, human decision authorization, AI/automation denial (gate, service, API), trusted actor persistence, review history, approval scope, `KnowledgeEntry` backward compatibility (columns, contract), Analyzer knowledge integration, diagnostic result contract, end-to-end recovery evidence for the three eligible records. A mutation check confirmed that the decision-API tests fail when the server-set verifier and the forbidden-key list are removed.

## Not run
Frontend build/typecheck and browser checks: no frontend code changed. Migration upgrade/downgrade: no migration exists.
