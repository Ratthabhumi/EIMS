# A17 — Final Project Handover & Acceptance Matrix (Phase 7)

Date: 2026-11-19
**Project Delivery: READY WITH LIMITATIONS** · **Security Acceptance: NOT ACCEPTED** · **Development: FREEZE**

## 1. Acceptance matrix (dimensions kept separate)

| Control | Implemented | Behaviour tested | Runtime wired | Operationally verified | Independently reviewed | Status |
|---|---|---|---|---|---|---|
| R-1 app DB identity | no | no | no | no | no | **BLOCKED** |
| R-2 test isolation | yes | ordering | yes (fixture) | no | no | **PARTIAL** |
| R-3 maintenance CLI | yes (disable) | CLI + direct `main()` | yes | no | **F1 ACCEPTED WITH LIMITATIONS** | **SAFE-DISABLED** |
| R-4 seed target | opt-in | structural | yes | no | no | **PARTIAL** |
| R-5 journal | classification | n/a | no | no | no | **LEGACY / NOT TRUSTED** |
| R-6 gateway auth | deny logic | unit | no | no | no | **NOT WIRED** |
| R-7 benchmark target | check | **unreachable (F2 rejected)** | no | no | **F2 REJECTED** | **NOT VERIFIED** |
| L2 / L3 | no | no | no | no | no | **FUTURE WORK** |
| Redis ACL / PgBouncer / digests | no | no | no | no | no | **NOT RUN** |

F1 and F2 are findings about specific behaviours; they do not upgrade R-3 or R-7 as controls.

## 2. Verified capabilities (for the presentation)

- Infrastructure asset management, telemetry/EVTX ingest, incident processing, analyzer workflow, search and timeline — implemented and covered by offline suites.
- Test-isolation contract for the application lifespan and the integration fixture.
- Maintenance destructive CLI is **safe-disabled** and the disable is enforced after argument parsing, including direct `main()` invocation.

## 3. Known limitations (must be stated)

1. Application runtime does not verify database identity at the mutation boundary (RR-1).
2. Gateway authorization is not wired (RR-3).
3. Journal is legacy and not trusted (RR-4).
4. Seed destructive opt-in does not verify the target (RR-5).
5. Benchmark target comparison is name/port only and, after F2, **unreachable** (RR-6, F2 rejected).
6. A17 behavioural tests are partly structural (RR-8).
7. Infrastructure hardening is not done.

## 4. Tests — current vs historical

| Evidence | When | Result |
|---|---|---|
| `py_compile` both tools | Phase 6.1 | exit 0 |
| `import tools.sprint11_benchmark` | Phase 6.1 | import_ok |
| `main()` without disposable env | Phase 6.1 | exit 1 refusal |
| direct `main()` + complete args + `--apply` | Phase 6.1 | exit 1 refusal |
| `pytest tests/test_a17_closure_behavior.py` | Phase 6.1 | 4 passed (structural — not evidence for F1/F2) |
| EIMS focused 65 / Chat_HAND 18 | Phase 4 | **historical, not re-run** |

## 5. Reproduction (safe, offline)

```powershell
cd <workspace>\EIMS
python -m py_compile tools\maintain_analyzer_sessions.py tools\sprint11_benchmark.py
python -c "import tools.sprint11_benchmark; print('import_ok')"
python -c "import sys; import tools.maintain_analyzer_sessions as m; sys.argv=['t','--retention-days','30','--apply']; m.main()"
pytest tests/test_a17_closure_behavior.py -q
```
No command starts a service, connects to a database, or mutates data.

## 6. Repository state

| | EIMS | Chat_HAND |
|---|---|---|
| Branch | `integration/eims-consolidated` | `v2/verified-fallback` |
| HEAD | `85493b21…` | `c293b8aa…` |
| Staged | 0 | 0 |

Working trees are **not clean** (pre-existing user changes plus campaign evidence). Nothing was discarded.

## 7. Approved presentation wording

- "EIMS integrates infrastructure management, telemetry ingest, incident processing and log analysis."
- "Selected workflows include automated validation and safety controls, with documented limitations."
- "Database trust and authorization controls are partially implemented and explicitly scoped."
- Maintenance CLI: **safe-disabled**, not guarded.
- Benchmark target: **not verified**.

## 8. Prohibited claims

Complete runtime security · tamper-proof/tamper-evident audit · gateway enforces authorization · maintenance CLI guarded · benchmark target verified · full database identity verification · "all tests pass therefore security passed" · production-secure.

## 9. Final decisions

| Decision | Value |
|---|---|
| Project Delivery Readiness | **READY WITH LIMITATIONS** |
| Security Acceptance | **NOT ACCEPTED** |
| Phase 7 | **COMPLETE (review executed)** — F2 rejected, recorded |
| Development | **FREEZE** — no A18 |

## 10. Deferred roadmap (not required for Co-op delivery)

R-1 identity at the mutation boundary · R-4 target verification · R-6 gateway authorization + trusted principal · journal L2/L3 · Redis ACL · PgBouncer SCRAM/TLS · image digests · embedding model contract.
