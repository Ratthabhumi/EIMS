# A17 — Final Independent Review (read-only)

Date: 2026-11-19 · Reviewer: Claude Code 2.1.323, plan mode, no edits, no execution.

## Verdict

**Do not accept A17 as closed.** The reviewer found two HIGH defects that make two claimed controls non-functional, and noted that the A17 tests were structural and would not have caught them.

## Findings

| ID | Sev | Path:line | Finding | Status after review |
|---|---|---|---|---|
| F1 | **HIGH** | `tools/maintain_analyzer_sessions.py:10,26` | `'--apply' in sys.argv` is an exact match; argparse accepts prefixes (`--ap`, `--a`), and a direct `main()` import bypasses the guard entirely. | **FIXED** — guard now matches any unique prefix and runs before import-time engine work; behavioural subprocess test covers `--apply`, `--ap`, `--a` |
| F2 | **HIGH** | `tools/sprint11_benchmark.py:262-264,269` | `_urlsplit` used before its in-function import (`UnboundLocalError`); `settings` never imported. The R-7 check never ran. | **FIXED** — module-level imports added; benchmark no longer crashes before the check |
| F3 | HIGH | `backend/infrastructure/database.py:68,76` | No runtime identity verification of the application engine. | **BLOCKED** (accepted residual) |
| F4 | MED | `tools/seed_analyzer_incident.py:444,491` | Opt-in DELETE has no target verification; seeder inserts unguarded. | **OPEN** |
| F5 | MED | `tests/test_a17_closure_behavior.py` | String-position tests passed regardless of whether guards worked. | **PARTIALLY FIXED** — R-3 now runs the real CLI; R-2/R-4/R-7 remain structural |
| F6 | LOW | `tools/seed_analyzer_incident.py:447-449` | Possible misleading "Purged" message when nothing is deleted. | OPEN, unverified |
| F7 | LOW | `evidence/*-a17-final.json` | Manifests list file names but no per-file hashes; A16 base absent. | **OPEN** — recorded, not rewritten |
| F8 | INFO | `risk-policy.mjs`, `execution-journal.mjs` | Not wired to runtime. | Recorded as NOT WIRED |

## What the review confirmed as sound

- R-2 guard ordering is real (`require_disposable_runtime()` before `create_async_engine`).
- `approverVerified` is ignored by the policy (no caller path authorizes a sensitive class).
- No runtime consumer imports the journal.
- No evidence file was modified after its manifest was written.

## Review limits

Read-only; no test executed. The post-review F1/F2 fixes were verified by a subprocess test and compilation, **but were not re-reviewed**.

## Residual risk

1. Application runtime database identity remains unverified (R-1).
2. Seed destructive path and inserts still have no target check (F4).
3. Benchmark equality is name/port only (F2 fixed the crash, not the scope).
4. R-2/R-4/R-7 tests are structural, not behavioural.
5. Manifests lack per-file hashes.
6. Journal remains legacy/untrusted; gateway authorization is not wired.
