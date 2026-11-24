# Certification Readiness Report — Round 3 (2026-11-22)

Computed from `register.json` (911 records) and the dispositions. Counts are separate by dimension and are **not** certifications. Source verified, independently reviewed and approved are **0 / 0 / 0**: every record is `SOURCE_UNVERIFIED`, `INDEPENDENT_REVIEW_PENDING`, `NOT_APPROVED`.

## Coverage by class
| Class | Records | Source URL present | Explicit version scope | Technically validated (automated) | Bound positive+negative evidence | Source-blocked | Any blocker |
|---|---:|---:|---:|---:|---:|---:|---:|
| A Windows context | 153 | 111 | 0 | 153 | n/a | 153 | 153 |
| B parser-linked candidates | 39 | 39 | 39 | 39 | 39 | 0 | 0 |
| C parser-mapped references | 312 | 312 | 312 | 312 | n/a (per-row positive check) | 0 | 0 |
| D state/telemetry | 4 | 4 | 4 | 2 | 2 (real PostgreSQL) | 0 | 2 |
| E unmapped candidates | 57 | 57 | 57 | 57 | n/a | 0 | 0 |
| F reference-only | 346 | 346 | 346 | 346 | n/a | 0 | 0 |
| **Total** | **911** | 869 | 758 | 909 | | 153 | 155 |

(Class A "technically validated" means only that each Event ID + provider resolves uniquely; its 153 source blockers are the 42 records with no exact source plus 111 whose version applicability is only a page-scope sentence.)

## Findings
Round 2 baseline 132 (131 actionable + 1 informational) → all dispositioned (82 resolved by evidence, 44 blocked, 2 needs-human-review, 2 accepted limitation, 2 not applicable). Stricter Round 3 rules added 162. Fresh validator: **207 actionable findings, 0 errors, 0 undispositioned**.

## What this means for each question the owner asked
| Question | Answer |
|---|---|
| Is the register trustworthy? | Deterministic, complete (911 = sum of catalogs), JSON/CSV consistent, evidence hash-bound and flagged stale on change |
| Is the validator weaker than before? | No; it is stricter (new rules, class-aware evidence). One count rule changed: the informational row is reported separately |
| Can any record be called certified? | No. Zero human actions exist |
| Which records are the closest to human review? | B (39) and D slot/lag (2): source, version scope and bound positive/negative evidence all present |
| What blocks most records? | Windows version applicability (111) and missing exact sources (42); real FortiGate output (2) |

## Remaining human decisions
1. Reviewers and review authority (names are yours to enter; none were invented).
2. Approve per-row vs table-level review for the 312 parser-mapped references.
3. Source confirmation for the 42 Windows records without an exact source (and for the indirect/needs-review ones: 1054, 1055, 5009, 21–25, 1002, 1076).
4. Explicit version applicability for the 111 Windows records (read from each cited page, or confirm none is stated).
5. Risk wording for the 6 destructive-remediation candidates that only say "Not stated".
6. Whether a FortiGate or recorded real `get sys ha status` output can be supplied for the HA evaluator; whether to build an evaluator for the unmapped HA record.
7. The 22 legacy entries labelled `official_documentation_verified` (earlier audit finding A) — relabel or review.
8. Approval of the governance DB changes proposed in Round 1 (not applied).

## Verdict
**PARTIALLY READY — TECHNICAL BLOCKERS REMAIN.**
Evidence: classes B, C, E, F and two of four D records have complete automated technical evidence; the register and validator are consistent and reproducible; real PostgreSQL evidence exists for the slot and lag evaluators. Against that, 153 Windows records are source-blocked, two class-D records lack real-source evidence, 121 findings need a human, and nothing has any human review. It is not "READY FOR HUMAN PILOT REVIEW" for the whole program because the Windows class cannot start source review without source decisions; it is ready to start human review for classes B and the two PostgreSQL D records now.

## Tests run (final state, 2026-11-22)
| Command (project venv) | Environment | Result |
|---|---|---|
| `pytest tests --ignore=tests/test_analyzer_postgres_integration.py` | disposable non-superuser PostgreSQL, `EIMS_DEMO_SOFT_DEPS=1` | **1952 passed, 51 skipped, 0 failed** (460 s) |
| `pytest tests/test_analyzer_postgres_integration.py` | its own disposable DB | **75 passed, 0 failed** (52 s) |
| `pytest tests/test_certification_round3.py tests/test_certification_tools.py` | no database | 49 passed (includes the 4 Round 2 tests) |

The 51 skips are the same environment-gated tests as before and are not counted as passed. Not run: frontend build/typecheck, browser checks (no frontend or API change was made in this round).


---

## Round 4 update (2026-11-22) — supersedes the coverage and findings figures above

Coverage by class after the Windows source research (register regenerated; source blockers and technical blockers kept apart):
| Class | Records | Source URL | Explicit version scope | Technically validated (automated) | Bound positive+negative evidence | Source-blocked | Technically blocked |
|---|---:|---:|---:|---:|---:|---:|---:|
| A Windows | 153 | 111 | 53 (official OS statement) | 153 | n/a | 100 | 0 |
| B | 39 | 39 | 39 | 39 | 39 | 0 | 0 |
| C | 312 | 312 | 312 | 312 | n/a | 0 | 0 |
| D | 4 | 4 | 4 | 2 | 2 (real PostgreSQL) | 0 | 2 |
| E | 57 | 57 | 57 | 57 | n/a | 0 | 0 |
| F | 346 | 346 | 346 | 346 | n/a | 0 | 0 |
Class A source blockers: 42 no direct source, 47 product-level scope only, 11 page-scope sentence only. Findings: **154 actionable over 110 unique records** (was 207 over 163), every one dispositioned; source_verified / reviewed / approved remain 0 / 0 / 0.
Operational completeness (new measure, `knowledge_model_gap_analysis.md`): engineer-ready B 3 of 39, D 0 of 4, E 6 of 57.
Gate verdicts (Round 4): Gate 1 PARTIAL, Gate 2 NOT MET, Gate 3 NOT MET — see `post_round3_completion_report.md` §15.
**Overall verdict: PARTIALLY READY — TECHNICAL AND GOVERNANCE BLOCKERS REMAIN.**

### Round 4 tests (final state)
| Command (project venv) | Environment | Result |
|---|---|---|
| `pytest tests --ignore=tests/test_analyzer_postgres_integration.py` | disposable non-superuser PostgreSQL, `EIMS_DEMO_SOFT_DEPS=1` | **2030 passed, 51 skipped, 0 failed** (434 s) |
| `pytest tests/test_analyzer_postgres_integration.py` | its own disposable DB | **75 passed, 0 failed** (48 s) |
| `pytest tests/test_certification_round4.py` (after two last tests were added) | no database | 37 passed |
| focused knowledge/governance suites | disposable PostgreSQL | 198 passed, 0 skipped |
The 51 skips are the same environment-gated tests as before and are not counted as passed. Frontend build/typecheck and browser checks were not run: no frontend or API code changed.
