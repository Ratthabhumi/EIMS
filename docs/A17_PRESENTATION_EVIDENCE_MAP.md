# A17 — Presentation Evidence Map

Date: 2026-11-19
Rule: every slide claim must map to evidence. Features are **not** proven by existing in a repository.

## Verification levels

- **IMPLEMENTED** — source exists
- **TESTED** — a relevant test passed (offline)
- **DEMONSTRATED** — UI or execution evidence exists
- **PARTIAL** — incomplete coverage
- **NOT VERIFIED** — insufficient evidence

## Slide map

| # | Slide / topic | Claim | Evidence | Level | Safe wording |
|---|---|---|---|---|---|
| 1 | WHY | Operational evidence is fragmented | problem statement, no repo claim | n/a | "Finding issues is not enough; engineers need evidence they can verify." |
| 2 | WHAT | EIMS integrates infrastructure management, telemetry ingest, incident processing, log analysis | `backend/domain/*`, `tests/` suites | **IMPLEMENTED** | as stated |
| 3 | HOW | Telemetry/EVTX ingest pipeline | `backend/domain/telemetry/*`, `tests/test_evtx_*` | **TESTED** (offline suites) | "The ingest pipeline is covered by automated tests." |
| 4 | HOW | Incident processing and correlation | `backend/domain/incident*`, `tests/test_incident_*` | **TESTED** | "Incident capture and correlation are implemented and tested." |
| 5 | SHOW | Analyzer workflow produces structured findings | `backend/domain/analyzer/*`, `docs/ANALYZER_BASELINE_RESULTS.md` | **PARTIAL** — accuracy not certified (0 reviewed cases) | "The analyzer produces structured investigations; accuracy is not yet certified." |
| 6 | SHOW | Search and timeline | `backend/domain/search`, `timeline`, `tests/test_global_search*`, `test_timeline` | **TESTED** | "Search and timeline are implemented and tested." |
| 7 | SHOW | Safety controls | A17 changes (test isolation, CLI disable, seed opt-in) | **PARTIAL** | "Selected workflows include safety controls, with documented limitations." |
| 8 | REFLECT | Security posture | `docs/A17_FINAL_ACCEPTANCE_MATRIX.md` | **PARTIAL / NOT ACCEPTED** | "Database trust and authorization controls are partially implemented and explicitly scoped." |
| 9 | REFLECT | Known limitations | residual risk register | n/a | list RR-1…RR-7 in one line each |

## Prohibited claims

- "Complete runtime security enforcement"
- "Tamper-proof" / "tamper-evident audit"
- "Gateway enforces authorization"
- "Maintenance CLI is guarded" (it is disabled; direct invocation unproven)
- "Benchmark is target-verified" (it currently cannot run)
- "All tests pass, therefore security is verified"
- "Full database identity verification"
- "Operational acceptance" (no operational test was run)

## Wording to avoid even when technically true

- "Production-ready"
- "Enterprise-grade security"
- "Certified"

## Recommended closing line

"EIMS is delivered as a bounded engineering project with documented capabilities, automated tests and explicit security limitations. The most important result is not only that it finds problems, but that it records evidence you can verify."
