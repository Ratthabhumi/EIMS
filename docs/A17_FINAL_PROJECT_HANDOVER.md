# A17 — Final Project Handover

**Date:** 2026-11-19 · Branch `integration/eims-consolidated` · HEAD `85493b2`

## 1. What this project is

EIMS: infrastructure asset management, telemetry/EVTX ingest, log analysis,
incident correlation with evidence references, search/timeline, and a dashboard.
Audited subsystems and their verification levels are in `A17_FINAL_ACCEPTANCE_MATRIX.md`.

## 2. Verified capabilities (safe to demonstrate)

- Asset registry API and persistence.
- Telemetry ingest and EVTX parsing into persisted rows.
- Analyzer submit / bundle / offline import → analysis history.
- Incident correlation, deduplication and evidence binding.
- Incident ingestion v1.1 (transactional outbox + async consumer).
- Search and timeline reads (inspection-verified).

## 3. Excluded capabilities (do not claim or demo)

| Excluded | Reason |
|---|---|
| Benchmark (`tools/sprint11_benchmark.py`) | target guard is database-name-only; TRUNCATEs four tables |
| Maintenance CLI (`tools/maintain_analyzer_sessions.py`) | enabled, not SAFE-DISABLED; deletes auth rows with `--apply` |
| `clear_db.py` | unguarded TRUNCATE of the application database |
| Seed scripts | DELETE with no environment guard |
| Gateway authorization | artifact not present (`gateway/lib/risk-policy.mjs`) |
| Journal / tamper-evident audit | no implementation present |

## 4. Setup and safe verification

```powershell
# environment
python -m venv venv; .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
# configuration: copy .env.example; never commit real secrets

# safe static verification (no DB, no services)
python -m compileall -q backend tools
python -m pytest tests/test_incident_correlation.py `
                 tests/test_incident_ingest_unit.py `
                 tests/test_incident_ingest_v11_recovery_unit.py -p no:cacheprovider
# expected: 114 passed
```

DB-backed suites require a disposable PostgreSQL/Redis provisioned for the test
allowlist. They were **not** run in this audit; treat earlier DB results as
historical and clearly labelled.

## 5. Repository state at handover

- 175 worktree entries: 59 modified, 116 untracked, 0 staged — preserved as found.
- Single Alembic head: `c4e8a1f7b932`.
- Historical evidence manifests verified by SHA-256 (see findings register §3).

## 6. Known limitations (carry forward)

1. R-1 Database identity is not enforced at the mutation boundary.
2. R-2 Test isolation is guard-before-engine, not operationally verified.
3. R-3 Gateway authorization artifact is absent.
4. R-4 Journal/tamper-evidence is absent.
5. R-5 / NF-6 Seed deletion has no environment guard.
6. R-6 / NF-4 Benchmark target safety is name-only.
7. NF-1 `clear_db.py` is unguarded.
8. NF-2 `cleanup_auth_records` defaults to `dry_run=False`.
9. NF-5 Some A17 artefacts are missing, so earlier claims cannot be re-verified.
10. NF-7 The F2 `_urlsplit` finding is not reproducible in the current source.

## 7. Future work (not started)

- Delete or guard `clear_db.py`; make `dry_run=True` the default everywhere.
- Verify database identity (host/role) at the mutation boundary.
- Implement and wire authorization; implement a journal with a runtime consumer.
- Add per-file hashes to manifests; rebuild the A17 closure test as a behavioural test.
- Add a disposable-DB acceptance run for the analyzer and incident paths.

## 8. Closure decision

**CLOSED — WITH EXPLICIT EXCLUSIONS.**
**Security Acceptance: NOT ACCEPTED.**

The delivered scope is the analyzer/incident/telemetry product path. The excluded
items above must not appear in claims, slides or the demo.
