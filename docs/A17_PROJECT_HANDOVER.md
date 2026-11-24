# A17 — Project Handover

Date: 2026-11-19
**Security Acceptance: NOT ACCEPTED** · **Bounded project deliverable: READY WITH LIMITATIONS**

## 1. Repository state (verified)

| | EIMS | Chat_HAND |
|---|---|---|
| Branch | `integration/eims-consolidated` | `v2/verified-fallback` |
| HEAD | `85493b21…` | `c293b8aa…` |
| Modified / Untracked | 59 / 207 | 20 / 97 |
| Staged | 0 | 0 |

Working trees are **not clean**. These are pre-existing user changes plus evidence documents; none were discarded.

## 2. What A17 changed (workspace only)

| File | Change |
|---|---|
| `tests/test_global_search_integration.py` | disposable guard before engine creation |
| `tools/maintain_analyzer_sessions.py` | `--apply` refused (prefix-proof, import-proof) |
| `tools/seed_analyzer_incident.py` | `DELETE` requires `EIMS_SEED_ALLOW_DELETE=1` |
| `tools/sprint11_benchmark.py` | target-mismatch check; module-level imports fixed after review |
| `tests/test_a17_closure_behavior.py` | 4 tests; R-3 runs the real CLI |
| `gateway/lib/risk-policy.mjs` | caller `approverVerified` ignored |
| `scripts/test-a15-execution-integrity.mjs` | deny test for `approverVerified:true` |

No source change was made to the real repositories.

## 3. Demonstrated capabilities

- Infrastructure inventory, telemetry/EVTX ingest, incident processing, analyzer, search/timeline — implemented in the product and exercised by the existing offline suites (65 focused tests in A17 scope; broader suites remain historical).
- Test isolation contract for the app lifespan and the integration fixture.
- Safe-disabled destructive maintenance operation.
- Deny-by-default policy logic for sensitive action classes (library-level).

## 4. Stated limitations (must appear in the presentation)

1. **Application database identity is not verified at runtime.** The app trusts `settings.database_url`.
2. **Maintenance CLI is disabled, not guarded.** The capability is unavailable by design.
3. **Seed opt-in is not target verification.**
4. **Benchmark equality is configuration-level (name/port).**
5. **Gateway authorization is not wired.** The policy module is unit-tested only.
6. **Journal v1 is legacy and not trusted for authority.**
7. **Redis ACL, PgBouncer SCRAM/TLS, image digests, external audit anchor: not implemented.**
8. **Independent review rejected closure before the F1/F2 fixes**; those fixes were not re-reviewed.

## 5. Evidence

| Artifact | SHA-256 |
|---|---|
| `evidence/v12-a17-final-manifest.json` (EIMS) | `A108C4D074CB668B855128B7C74006E54F7CB9CE227F0D24D77C8DFB42D6D578` |
| `evidence/v12-a17-final-manifest.json` (Chat_HAND) | `E04EACE441DDE748000402885F711C842366BB0BF5D06784F6878C3162184ABC` |
| `docs/A17_FINAL_INDEPENDENT_REVIEW.md` | review of the A17 revision |
| `docs/A17_FINAL_ACCEPTANCE_MATRIX.md` | matrix + risk register |
| `docs/V13_A17_PHASE4_REPORT.md` | phase 4 report |
| `docs/A17_PHASE1_*` (3 files) | inventory, gaps, recommendations |

## 6. Not performed

No container/service start · no migration · no operational DB/Redis/MinIO contact · no Trust Grant · no commit/stage/push · no Redis/PgBouncer change · no image pull · no vector reproduction · no live E2E.

## 7. Recommended future work (not this project)

1. R-1: pool-checkout identity recording + transaction-bound assertion in every mutating path.
2. Real trusted principal + gateway enforcement.
3. Seed/maintenance target verification on the executing connection.
4. Journal v2 with a separate signer, then an external checkpoint.
5. Redis ACL, PgBouncer SCRAM/TLS, digest pinning.
6. Embedding model contract + vector reproduction on an isolated pgvector instance.

## 8. Presentation wording that is supported

- "EIMS integrates infrastructure management, telemetry ingest, incident processing and log analysis."
- "Selected workflows include automated validation and safety controls, with documented limitations."
- "Database trust and authorization controls are partially implemented and explicitly scoped."
