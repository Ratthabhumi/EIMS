# EIMS — Final Test Evidence

**Date:** 2026-11-19 · HEAD `85493b2` · Windows · Python 3.14.3 · pytest 9.1.1

Everything below was executed in this round. Historical results are not mixed in.

## Executed

| # | Command | Result | Runtime | Environment |
|---|---|---|---|---|
| 1 | `python -m compileall -q backend tools clear_db.py` | exit 0 | ~3 s | offline |
| 2 | `pytest tests/test_mutation_safety.py` | **12 passed** | 5.4 s | offline, fake sessions |
| 3 | `pytest tests/test_incident_correlation.py tests/test_incident_ingest_unit.py tests/test_incident_ingest_v11_recovery_unit.py` | **114 passed** | 1.3 s | offline |
| 4 | `pytest` (suites 2+3 + `tests/test_analyzer_postgres_integration.py`) | **129 passed, 68 skipped, 0 failed** | 8.0 s | offline; the 68 skips are all `EIMS_TEST_DATABASE_URL` unset |
| 5 | `git diff --check` | exit 0 | — | — |

The 68 skips are DB-gated analyzer integration tests. They were **not** run against a
database in this round; the skip message names the missing variable.

## Not executed (and why)

| Not run | Reason |
|---|---|
| Analyzer PostgreSQL integration (68 tests) | no disposable PostgreSQL provisioned in this round |
| Incident ingest DB integration | same |
| Redis / MinIO / browser / service-starting suites | would start shared services; not authorized |
| `clear_db.py`, seed, benchmark, maintenance CLI against a DB | destructive; explicitly prohibited |
| Migration upgrade/downgrade | requires disposable PG; not provisioned |

No destructive script was executed. No operational database, Redis, MinIO, container or
credential was contacted.

## What the passing tests actually prove

- `test_mutation_safety.py` proves the **policy and the sequencing**: identity is read from
  the live session, denied paths issue no DELETE/TRUNCATE (asserted on recorded SQL), the
  dry-run default performs no mutation, and the accepted path does reach DELETE.
- It does **not** prove real PostgreSQL semantics. `shobj_description`, role resolution and
  PgBouncer transaction-mode behaviour are untested here and are listed as a limitation.

## Known test-harness risk (recorded, mitigated)

A failing `os.environ[...]` lookup previously printed the whole process environment,
including unrelated secrets, into pytest output. Three lookups now use
`_required_test_url()` with an explicit skip. The remaining hard lookups were removed from
the destructive call sites.


## Update — 2026-11-19 (Final Integration round)

| Command | Result |
|---|---|
| pytest tests/test_mutation_safety.py | **19 passed** (5.1 s) |
| pytest (correlation + ingest unit + recovery + analyzer integration) | **117 passed, 68 skipped** (1.5 s) |
| compileall backend tools clear_db.py | exit 0 |

No disposable PostgreSQL was provisioned this round, so no real-database identity test ran.
