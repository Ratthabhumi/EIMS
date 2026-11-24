# A17 Phase 6A/6B — Post-Review Verification (F1, F2)

Date: 2026-11-19 · Read-only verification of the A17 workspace. No operational contact.
**Status: F1 PARTIAL — F2 NOT VERIFIED (new defect found). Security Acceptance remains NOT ACCEPTED.**

## F1 — Maintenance CLI `--apply`

### What was tested (executed, real subprocess)

| Command | Exit | Message |
|---|---:|---|
| `python tools/maintain_analyzer_sessions.py --apply` | 1 | `A17 R-3: --apply is disabled ...` |
| `... --ap` | 1 | same refusal |
| `... --a` | 1 | same refusal |

Source check: `tools/maintain_analyzer_sessions.py:12` uses
`a == '--apply' or (a.startswith('--') and '--apply'.startswith(a))`, which covers every argparse prefix of `--apply`.

### What is still open

| Scenario | Result |
|---|---|
| Direct `main()` import then `sys.argv = ['t','--ap']` | Exit 2 — argparse refuses because `--retention-days` is required. **Not** refused by the R-3 guard. |
| Direct `main()` with a *complete* argument set including `--apply` | **Not tested**; the guard is module-level and would have been evaluated at import time, before argv was changed. This remains a bypass candidate. |

**F1 status: PATCHED — PENDING REVIEW (PARTIAL).** CLI paths are closed; direct invocation is not proven closed.

## F2 — Benchmark target check

### What was tested (executed)

`python -c "import tools.sprint11_benchmark"` →
`refusing to run: disposable guard refused: EIMS_TEST_DISPOSABLE_ID is not set` (non-zero exit).

### Finding (new)

A16 placed `require_disposable_runtime()` at **module import time** in `tools/sprint11_benchmark.py`. Consequences:

1. The module cannot be imported without the disposable environment variables, so the tool is **unusable** for its intended purpose.
2. The R-7 target check lives inside `main()`, which now can never be reached in a normal run — the process exits during import.
3. Therefore the R-7 check is **not verified**: it compiles, but it does not execute.

This is the same class of defect the reviewer found earlier (a control that exists but never runs), now at the import boundary.

**F2 status: NOT VERIFIED.** The benchmark fails closed by refusing to start, which is safe but not a working check. No claim of "benchmark target verified" may be made.

## Test evidence (executed in this phase)

| Command | Result |
|---|---|
| `pytest tests/test_a17_closure_behavior.py` | **4 passed** |
| `python tools/maintain_analyzer_sessions.py --apply/--ap/--a` | refused (exit 1) each |
| `python -c "import tools.sprint11_benchmark"` | refused at import (exit non-zero) |

## Independent re-review

**NOT RUN** in this phase. F1/F2 therefore remain *pending independent review*. The earlier A17 review rejected closure; this phase adds evidence but does not overturn that.

## Consequence for the handover

- Do **not** present the maintenance CLI as guarded; it is disabled, and direct invocation is unproven.
- Do **not** present the benchmark as target-verified; it currently cannot run.
- Security Acceptance stays **NOT ACCEPTED**.
