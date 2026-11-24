# EIMS — Final Project Handover

**Date:** 2026-11-19 · Branch `integration/eims-consolidated` · HEAD `85493b2`

## 1. Delivery decision

**CLOSED — WITH EXPLICIT EXCLUSIONS.**
**Security acceptance: NOT ACCEPTED.**
Product acceptance matrix: `docs/A17_FINAL_ACCEPTANCE_MATRIX.md` (V16) still applies;
this round only changed the safety status of destructive tooling (see
`FINAL_SECURITY_ACCEPTANCE_MATRIX.md`).

## 2. Deliverable product path

Telemetry / log ingest → Analyzer → Finding / Incident → Evidence → Investigation →
recommended remediation → verification, demonstrated with synthetic data.

## 3. Excluded from delivery, demo and claims

| Excluded | Why |
|---|---|
| `clear_db.py` | destructive admin script; now refuses by default but still excluded |
| `tools/maintain_analyzer_sessions.py` | enabled with `--apply`; gated but administrative |
| `tools/seed_analyzer_incident.py`, `seed_demo_data.py` | seeding tools, not product runtime |
| `tools/sprint11_benchmark.py` | performance tool; target proof is partial |
| Gateway authorization | artefact absent |
| Journal / tamper evidence | no implementation |

## 4. Operating the safety boundary

Destructive helpers require **one** of:

- `EIMS_DB_IDENTITY="<database>|<role>"` — process configuration, set before start-up; or
- a database whose comment starts with `EIMS-DISPOSABLE-` (written by a disposable
  provisioner).

Both are checked against the **live connection** immediately before the mutation. If
neither holds, the operation raises `MutationTargetError` and no SQL is executed.

`clear_db.py` additionally requires `EIMS_ALLOW_DESTRUCTIVE_CLEAR=1`.

## 5. Safe verification

```powershell
python -m compileall -q backend tools clear_db.py
python -m pytest tests/test_mutation_safety.py `
                 tests/test_incident_correlation.py `
                 tests/test_incident_ingest_unit.py `
                 tests/test_incident_ingest_v11_recovery_unit.py -p no:cacheprovider
# expected: 126 passed (12 + 114)
```

DB-gated suites require `EIMS_TEST_DATABASE_URL` pointing at a disposable database; they
skip otherwise (68 skips). Never point them at the operational database.

## 6. Repository state

175+ worktree entries preserved (59 modified, 116+ untracked, 0 staged at audit time);
additional files from this round are new and untracked. Nothing was stashed, reset,
cleaned, staged, committed or pushed. Historical evidence was not overwritten.

## 7. Known limitations carried forward

1. R-1: ordinary CRUD writes are not identity-gated; deployment identity is not configured.
2. R-3/R-4: authorization and journal remain excluded.
3. R-2: test isolation is guard-before-engine, not operationally verified.
4. R-7: manifests lack per-file hashes (four top-level hashes verified).
5. NF-5: some A17 artefacts are absent, so earlier claims are unverifiable.
6. Real PostgreSQL identity behaviour (sentinel, PgBouncer) is untested in this round.

## 8. Future work (only what is genuinely required)

1. Provision `EIMS_DB_IDENTITY` and extend the gate to write paths, tested on disposable PG.
2. Decide whether `clear_db.py` should be deleted outright.
3. Define a trusted principal source before any authorization claim.
4. Add per-file hashes and rebuild the A17 closure test as a behavioural test.

## 9. Owner action required

Nothing is required to keep the current delivery valid. To lift Security Acceptance, the
four items in §8 must be scheduled; no further broad audit is needed.
