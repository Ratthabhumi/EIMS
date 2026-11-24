# EIMS — Final Remediation Report

**Date:** 2026-11-19 · Branch `integration/eims-consolidated` · HEAD `85493b2`
**Scope:** destructive-path safety (NF-1, NF-2, NF-3, NF-4/R-6, NF-6/R-5) and R-1.
**No commit, stage, push, migration or operational database access.**

## 1. Decision summary

| | |
|---|---|
| Delivery | **CLOSED — WITH EXPLICIT EXCLUSIONS** |
| Security acceptance | **NOT ACCEPTED** (unchanged) |
| Core product path | Analyzer → Incident → Evidence, as bounded in the V16 audit |

## 2. Root cause and fix, per finding

### NF-1 — `clear_db.py` truncated the application database unguarded
- **Root cause:** a root-level script using the app's own engine with no gate at all.
- **Fix:** rewritten. Import is inert; execution requires `EIMS_ALLOW_DESTRUCTIVE_CLEAR=1`
  **and** a positive live-connection identity check (`require_destructive_target`) on the
  same connection as the TRUNCATE.
- **Proof:** `test_clear_db_import_does_not_connect_or_execute` (subprocess asserts
  `database_engine._engine is None`), `test_clear_db_refuses_without_explicit_opt_in`.
- **Residual:** the identity-denied path of `clear_db` itself has no dedicated test
  (the gate it calls is fully tested). Tool remains excluded from the demo.

### NF-2 — `cleanup_auth_records` defaulted to destructive
- **Root cause:** `dry_run=False` was the default, so a library call deleted rows.
- **Fix:** `dry_run=True` is the default. A destructive call performs
  `require_destructive_target` **inside the same transaction** before any DELETE.
- **Proof:** `test_cleanup_default_is_dry_run_and_deletes_nothing`,
  `test_cleanup_destructive_without_identity_is_denied_before_delete`,
  `test_cleanup_destructive_with_disposable_target_deletes`.
- **Caller inventory:** enforced by `test_no_runtime_caller_of_destructive_helpers`
  (fails if a new file imports the helper without review). Current callers: the CLI,
  the seed tool, and tests only — no runtime caller.

### NF-3 — documentation said SAFE-DISABLED; the CLI is enabled
- **Fix:** the module docstring now states the truth (dry-run default, `--apply` gated by
  the live identity check). No behaviour was weakened to match old docs; the docs were
  corrected to the source.

### NF-4 / R-6 — benchmark guarded only by a database-name suffix
- **Fix:** the name check remains as a first hint, but `require_destructive_target` now runs
  inside the benchmark transaction before the four-table TRUNCATE.
- **Residual:** the benchmark is still excluded from the product path and from claims;
  a full verified-target benchmark is future work.

### NF-6 / R-5 — seed DELETE with no guard, docstring said "never deletes"
- **Fix:** the purge function calls the gate before its DELETE; the docstring no longer
  claims the tool never deletes.
- **Residual:** seed tools remain excluded from the demo.

### R-1 — database identity not proven at mutation time
- **Implementation:** `backend/infrastructure/db_identity.py` asks the live session for
  `current_database()`, `current_user`, `session_user` and the database comment, and
  accepts the mutation only when that matches `EIMS_DB_IDENTITY`
  (`"<database>|<role>"`, trusted process config) or the database carries the
  `EIMS-DISPOSABLE-` sentinel.
- **Applied at:** clear_db, session cleanup, seed purge, benchmark truncate.
- **Status: PARTIALLY MITIGATED, not closed.** Ordinary CRUD writes are not gated, and no
  deployment sets `EIMS_DB_IDENTITY` yet. Gating every write without that configuration
  would break normal operation, so it is a deployment decision, not a silent change.

## 3. Test-harness correction (review finding)

`tests/test_analyzer_postgres_integration.py` expected deletion from a call that now
previews. The four destructive call sites pass `dry_run=False`; the fixture binds the
identity with `monkeypatch.setenv` from the connection it actually opens (no env leak);
three hard environment lookups now skip cleanly instead of raising `KeyError`, and a
failure would otherwise print the whole process environment (a pre-existing leak path).

## 4. What is deliberately not done

- R-3 (gateway authorization) and R-4 (journal) remain **excluded**: the artefacts are
  absent and no trusted principal or independent signer exists.
- No new schema, no migration, no product-path refactor.
- Benchmark, seed, maintenance CLI and `clear_db.py` stay **out of the product path**.

## 5. Trade-offs

Fail-closed identity checks can block a legitimate operator who has not configured
`EIMS_DB_IDENTITY`. That is deliberate: for destructive operations, a refusal is the
correct failure mode, and the message names the exact configuration required.

## 6. Verification

See `FINAL_TEST_EVIDENCE.md`. 129 passed, 68 skipped, 0 failed; compile exit 0;
`git diff --check` exit 0. Independent review round 2: **ACCEPTED** with two
non-blocking notes (bind from the sentinel rather than the URL; state the skip cause),
both addressed or recorded.
