# A17 Phase 6.1 — F1/F2 Final Verification

Date: 2026-11-19 · Narrow defect resolution. No operational contact.
**Security Acceptance: NOT ACCEPTED.** **Phase 6.1: PARTIAL (independent review not run).**

## F1 — Maintenance CLI destructive path

### Source change
`tools/maintain_analyzer_sessions.py` now enforces the disable at the **execution boundary**:
after `args = parser.parse_args()`, `if args.apply: parser.exit(1, 'A17 R-3: ...')`.
The module-level prefix check remains for early CLI refusal.

### Behavioural evidence (executed)

| Scenario | Exit | Result |
|---|---:|---|
| `--apply` (CLI) | 1 | R-3 refusal |
| `--ap` (CLI) | 1 | R-3 refusal |
| `--a` (CLI) | 1 | R-3 refusal |
| **direct `main()` with complete args + `--apply`** | **1** | **R-3 refusal** |
| direct `main()`, complete args, no `--apply` | 2 | config validation only; no engine, no DELETE |

The previous gap — direct invocation not proven — is now closed by a real call with a complete argument set. The engine is never created because the guard exits before `create_async_engine`.

**F1: VERIFIED (pending independent review).**

## F2 — Benchmark import and execution boundary

### Source change
The module-level `require_disposable_runtime()` block was removed from `tools/sprint11_benchmark.py`.
The guard now runs at the start of `main()`, before URL validation, engine creation and the R-7 check.

### Behavioural evidence (executed)

| Scenario | Result |
|---|---|
| `import tools.sprint11_benchmark` without disposable env | **succeeds** (`import_ok`, `has_main True`) |
| `asyncio.run(main())` without disposable env | exit 1, `refusing to run: ... EIMS_TEST_DISPOSABLE_ID is not set` |
| Guard position | inside `main()`, before `assert_disposable_database_url`, `BENCHMARK_TARGET_MISMATCH` and `create_async_engine` |

Import no longer performs safety checks, creates engines, or connects. Execution refuses before any engine or connection.

**F2: VERIFIED (pending independent review).**

## R-7 — Benchmark target check

The check is now reachable (previously unreachable because import aborted). It still compares **DB_NAME and DB_PORT only**.
It does not prove host, role, server or connection identity. **R-7 remains PARTIAL.**

A mismatch test is not exercised against a live target; only the ordering and reachability are established. This limitation is recorded rather than overstated.

## Test results (executed in this phase)

| Command | Result |
|---|---|
| `python -m py_compile tools/maintain_analyzer_sessions.py tools/sprint11_benchmark.py` | exit 0 |
| `python -c "import tools.sprint11_benchmark"` | import_ok |
| `python -c "... main()"` without env | exit 1, refusal |
| direct `main()` with `--apply` | exit 1, refusal |
| `pytest tests/test_a17_closure_behavior.py` | 4 passed |

Historical counts (65 EIMS focused, 18 Chat_HAND) are **not** re-run here and must not be cited as current.

## Observation about the tests

`tests/test_a17_closure_behavior.py` is structural: it passed while the F1 file had a syntax error and while F2's guard was unreachable. This is recorded as a test-quality limitation (RR-6). The behavioural evidence above comes from direct execution, not from those tests.

## Independent review

**NOT REVIEWED.** No separate reviewer pass was run in this phase. F1/F2 are therefore *verified by execution* but not *independently accepted*.

## Consequences

- Maintenance CLI: **SAFE-DISABLED, enforced at the execution boundary.**
- Benchmark: **importable; execution guarded.**
- Security Acceptance: unchanged — **NOT ACCEPTED** (R-1, R-4, R-6, journal remain).
