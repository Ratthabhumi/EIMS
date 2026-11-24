# EIMS V12 — Evidence-to-Revision Binding

Date: 2026-11-18 (Asia/Bangkok)
Repository: `C:\Users\MewMew\Desktop\Co-op\EIMS`
Machine-readable version: `evidence/v12-evidence-revision-map.json`

## 1. The rule

A test result may be reported as acceptance **only if** all of the following are recorded and consistent:

1. repository, branch, `HEAD`;
2. working-tree manifest SHA-256 (or per-file hashes) of the source under test;
3. the exact command;
4. start and end timestamps with timezone;
5. environment and dependency versions;
6. exit code and pass/fail/skip counts;
7. raw transcript, not only a summary line;
8. the SHA-256 of the evidence file itself.

A result missing any of 1–2 is **not** current acceptance. A result run against a different tree is **HISTORICAL** or **STALE** by definition, regardless of matching test names.

## 2. Classification vocabulary

| Class | Meaning |
|---|---|
| `CURRENT_AND_BOUND` | produced on the frozen tree, hashes recorded and matching |
| `HISTORICAL` | genuine result, but from an older revision; useful context only |
| `STALE` | genuine result, but the source under test has since changed |
| `UNVERIFIED` | result exists but its revision association cannot be established |
| `PARTIAL` | covers part of the claim only |
| `NOT_RUN` | no result |

## 3. Measured facts at audit time

| Fact | Value |
|---|---|
| `HEAD` commit date | 2026-11-13 20:08 +07 |
| Earliest product evidence date | 2026-11-14 |
| Latest product evidence date | 2026-11-16 |
| Modified tracked files | 58 |
| Modified files newer than 2026-11-14 | **45 of 58** |
| Modified files newer than 2026-11-16 | **1** (`tests/test_sprint13_evidence_ingestion.py`, 2026-11-17 02:57) |
| Acceptance ledger state | **untracked**, reports 32 modified / 30 untracked (stale vs current) |

**Conclusion:** the product evidence was produced against an uncommitted tree that no longer exists. No source hash was recorded with it. It cannot certify the current tree.

## 4. Evidence inventory and status

| Evidence | Location | Status | Reason |
|---|---|---|---|
| Acceptance ledger | `EIMS_ACCEPTANCE_LEDGER.md` (untracked) | **HISTORICAL / UNVERIFIED** | no hash binding; stale counts |
| Reliability batch (155 tests) | `%TEMP%\eims-reliability-focused.xml` | **HISTORICAL** | temp file, revision unknown |
| Analyzer unit (249 tests, 1 skip) | `%TEMP%\eims-analyzer-unit-20261114.xml` | **HISTORICAL** | temp file, revision unknown |
| Browser security guard | `test-results/eims-secure-browser-*-20261114.xml` | **HISTORICAL** | predates current tree |
| Browser acceptance | ledger: FAIL/BLOCKED | **FAIL** (as recorded) | no listener on 3449/8000 |
| Incident core / regressions | `test-results/incident-core*-20261116.xml` | **HISTORICAL** | 2026-11-16, tree has since changed |
| Reviewer DB probes | `test-results/reviewer-*-20261116.xml` | **HISTORICAL** | one-off probes |
| V11 ingest final status | `test-results/v11-ingest-db-redis-junit.xml` | **HISTORICAL** | state file, not bound |
| JUnit bundles in agent state | `.omc/evidence/v11-*.xml` | **HISTORICAL** | agent-generated, not bound |
| Monitor acceptance | `evidence/monitor-persistent-acceptance.json` | **PARTIAL** | source-byte matched; GUI/survival absent |
| Monitor source binding | `evidence/monitor-source-binding-20261118.json` | **CURRENT_AND_BOUND** (source only) | 12/12 hashes match the tested snapshot |
| V12 engineering report copy | `docs/V12_FINAL_ENGINEERING_REPORT.md` | **HISTORICAL** | content predates `HEAD` |
| This campaign's freeze | `evidence/v12-*` | **CURRENT** | generated from the frozen tree |

## 5. Claims that must not be made from this evidence

- "The full regression suite passes on the current revision" — it has not been run on the frozen tree.
- "Telemetry, analyzer and data integrity are accepted" — no current-revision run exists.
- "Monitor is accepted" — GUI, raw-key and long-running survival were never observed.
- "Analyzer accuracy is certified" — 0 reviewed cases; status was `INSUFFICIENT_DATA`.

## 6. Regeneration requirement

Every claim intended for final acceptance must be regenerated **after** the freeze, with:

- output written under `evidence/v12-track-c-results/<command-id>/`;
- JUnit XML plus raw stdout/stderr;
- a JSON record matching the schema in `docs/V12_GATE2_TEST_PLAN.md` §6;
- the frozen working-tree manifest SHA-256 in the record.

Evidence produced in `%TEMP%` without a copy and hash is not acceptable for final acceptance.

## 7. Preservation rules

- No historical evidence file may be edited, re-timestamped, renamed or deleted.
- Old results stay in place and stay labelled `HISTORICAL`/`STALE`.
- A copy never upgrades a result's class.
- The `evidence/archive/` material inside Chat_HAND remains historical and out of EIMS scope.
