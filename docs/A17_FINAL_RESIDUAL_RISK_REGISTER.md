# A17 — Final Residual Risk Register (RR-1 … RR-8)

Date: 2026-11-19 · Canonical. Historical documents unchanged.

## ID continuity

| ID | Original meaning (Phase 6) | Phase 6.1 usage | Canonical decision |
|---|---|---|---|
| RR-6 | benchmark target limitation | used for structural-test weakness | **keeps benchmark meaning**; the test observation becomes RR-8 |
| RR-7 | historical manifest lacks per-file hash | same | unchanged |
| RR-8 | — | — | **new** structural test weakness |

Cross-reference: any Phase 6.1 text that cites "RR-6" for test quality maps to RR-8.

## Register

### RR-1 — HIGH — application DB identity
- Component: `backend/infrastructure/database.py:68,76`
- Failure: app connects to whatever `settings.database_url` resolves to; every runtime mutation inherits that.
- Mitigation: none at runtime.
- Exposure: write path can target an unintended database.
- Delivery impact: none (demo runs against its own DB).
- Security impact: blocks Security Acceptance.
- Deferred: pool-checkout identity + transaction-bound assertion.

### RR-2 — MED — test isolation not operationally verified
- Component: `tests/conftest.py`, `tests/test_global_search_integration.py`
- Failure: guard proves ordering, not that a rejected target causes zero connection.
- Mitigation: allowlist + fail-closed guard.
- Exposure: a misconfigured allowlist can still point at a non-disposable endpoint.
- Deferred: behavioural test with a fake engine asserting zero connection.

### RR-3 — HIGH — gateway authorization not wired
- Component: `gateway/lib/risk-policy.mjs`
- Failure: policy exists but is imported only by tests; no trusted principal.
- Mitigation: caller `approverVerified` is ignored; sensitive classes deny.
- Exposure: no runtime enforcement.
- Deferred: principal source + enforcement at the execution boundary.

### RR-4 — HIGH — journal untrusted
- Component: `gateway/lib/execution-journal.mjs`
- Failure: no runtime consumer; completion proof is not authenticated.
- Mitigation: classified LEGACY / NOT TRUSTED; no v2.
- Exposure: cannot be used as audit evidence.
- Deferred: L2 signer, L3 anchor.

### RR-5 — HIGH — seed target not verified
- Component: `tools/seed_analyzer_incident.py`
- Failure: `EIMS_SEED_ALLOW_DELETE=1` enables DELETE without target identity.
- Mitigation: default is non-destructive.
- Exposure: opt-in plus a wrong URL deletes history.
- Deferred: target verification on the executing connection.

### RR-6 — MED — benchmark target comparison
- Component: `tools/sprint11_benchmark.py:265`
- Failure: compares DB_NAME/DB_PORT only; no host/role/server/connection identity.
- Mitigation: identity check on the engine (A16) — but see RR-8/F2.
- Exposure: misconfiguration can still produce misleading benchmark evidence.
- Deferred: compare the verified connection identity.

### RR-7 — LOW — historical manifest lacks per-file hashes
- Component: `evidence/v12-a17-final-manifest.json`
- Failure: file lists only; A16 base absent.
- Mitigation: Phase 6 and 7 manifests add per-file hashes.
- Exposure: older evidence is less reproducible.
- Deferred: cannot be fixed retroactively; historical files are immutable.

### RR-8 — MED — structural test weakness
- Component: `tests/test_a17_closure_behavior.py`
- Failure: the suite passed 4/4 while F1 had a syntax error and while F2's check was unreachable.
- Mitigation: Phase 6.1 added a real subprocess test for `--apply/--ap/--a`.
- Exposure: the suite gives false assurance; it is not evidence for F1/F2.
- Deferred: replace string-position assertions with behavioural tests.

## Severity policy

No severity was lowered. RR-8 was added rather than reclassifying RR-6.
