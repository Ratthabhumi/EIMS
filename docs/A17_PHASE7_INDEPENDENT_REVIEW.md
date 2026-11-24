# A17 Phase 7 — Independent Review (sign-off)

Date: 2026-11-19 · Reviewer: Claude Code 2.1.323, plan mode, read-only, no execution.
Scope: F1 and F2 only, plus evidence honesty. **Security Acceptance unchanged: NOT ACCEPTED.**

## Verdicts

| Finding | Verdict |
|---|---|
| F1 — maintenance CLI | **ACCEPTED WITH LIMITATIONS** |
| F2 — benchmark import/execution guard | **REJECTED** |

## F1 — accepted with limitations

Verified in source:
- module-level prefix guard catches `--apply`, `--ap`, `--a` (and, over-broadly, a bare `--`);
- **post-parse** `if args.apply: parser.exit(1, ...)` runs before URL handling and before `create_async_engine`;
- direct `main()` with complete arguments cannot reach the DELETE because `args.apply` is false by then (`dry_run=not args.apply`).

Limitations (recorded, not patched):
- `cleanup_auth_records(..., dry_run=False)` is importable and unguarded (`backend/domain/analyzer/services/session_maintenance.py:8,30`). Any importer can call it directly.
- The refusal message ends in a literal `\n`.

## F2 — rejected

The guard placement is correct: `main()` runs the disposable guard before the URL check, the R-7 check and `create_async_engine`; import no longer triggers the guard.

**But the R-7 check is unreachable.** `tools/sprint11_benchmark.py:271` imports `urlsplit` *inside* `main()`, which makes `_urlsplit` a local name for the whole function; the use at line 264 raises `UnboundLocalError`. Execution stops before the comparison, the engine and the TRUNCATE.

Consequences:
- the benchmark cannot run at all (fails closed);
- the claim "R-7 compares DB_NAME and DB_PORT (PARTIAL)" is **not supported** by execution;
- the earlier `settings` NameError is fixed; the `_urlsplit` defect remains.

Deferred fix (one line, not applied in this read-only phase): delete the in-function import at line 271 and rely on the module-level import.

## R-7 limitation (independent of the crash)

Even once reachable, R-7 compares only `DB_NAME` and `DB_PORT`, against app settings, not the opened connection. It does not prove host, role, server or connection identity. **R-7 stays PARTIAL.**

## Test evidence assessment

| Test | Finding |
|---|---|
| `test_r7_...` (`tests/test_a17_closure_behavior.py:52-57`) | Compares string positions only; **passes while the check crashes** → false assurance |
| `test_r3_...` (`:28-34`) | Runs the CLI with `--apply/--ap/--a`; does **not** exercise direct `main()` with argv set after import |
| suite 4/4 | Not evidence for F1/F2 (it passed earlier while F1 had a syntax error) |

The behavioural evidence for F1 comes from the direct-invocation runs reported in Phase 6.1, not from this suite.

## Not inspected

Model modules imported by the benchmark (no engine-on-import check), and the A17 documents (they are not present inside the workspace snapshot).

## Review limitations

No test was executed by the reviewer. Verdicts are source-reading based, except where they reference the implementer's executed runs.
