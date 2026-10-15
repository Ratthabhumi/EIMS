# Local repository audit — 15 October 2026

## Observed state

- Repository: `Ratthabhumi/EIMS`; remote identity verified without credentials in the URL.
- Original branch: `handoff/eims-supervision-2026-10-08`; HEAD `8c26f035244aeff9eefb87c3ed16b1aaa8e307f8`.
- Read-only remote comparison: main `bf634d9ddf86f44220ef961cf4be32988cfc5ee5`; supervision `8c26f035244aeff9eefb87c3ed16b1aaa8e307f8`. Supervision is ahead by two commits; no divergence. `v0.3.0` remains `6e5881a5a47961cca73ed71f9716cec23d15f0b3` (tag ref, not assumed peeled commit).
- 506 tracked paths; 177 untracked paths; 184107 ignored paths enumerated. These are file counts, not feature counts.
- Three tracked demo files were deleted only in the original checkout. Their committed contents were recovered into the private backup, without restoring or staging the deletions.
- Original local branches: main and supervision. A separate worktree now holds the new development branch; the original checkout is untouched.
- 772 valuable local-only files copied outside Git (505577560 bytes). Full path-level CSV includes Git state, A–F category, sensitivity, action, reason and size. Ignored runtime/cache files were inventoried but not backed up. Restricted prior-session documents were not read.

## Sanitized action table

| Path / class | Git state | Category | Sensitivity | Action | Reason |
|---|---|---|---|---|---|
| backend/, clients/dashboard/, clients/usb_auditor/ | tracked | A | Review source/config | KEEP_TRACKED | Preserve implementation; review every changed path |
| clients/log_analyzer/frontend/src/lib/ | local-only, not in baseline | A | Source review pending | NEEDS_REVIEW | Standalone client dependencies; not automatically duplicate or disposable |
| tests/ | tracked | B | Fixtures need screening | KEEP_TRACKED | Preserve regressions and synthetic provenance |
| docs/engineering-process/ | new | C | Sanitized engineering material | ADD_TO_GIT | Focused requirements, design, evaluation and test evidence |
| Existing report and slide sources | tracked/local-only | C/D | Identifiable or obsolete claims possible | NEEDS_REVIEW | Preserve; publish only after per-file content review |
| Supervision synthetic demo inputs | tracked deletions in original; present in new worktree | B/F | Synthetic-labelled | KEEP_TRACKED | Committed baseline remains reproducible; do not stage original deletions |
| Additional local demo packs | local-only and partly ignored | B | Synthetic-labelled; review required | NEEDS_REVIEW | Retained in private backup; not bulk-added |
| Workplace media, recordings, personal documents | local-only | D | Private/unredacted | KEEP_PRIVATE | Permission and redaction not established |
| Environment files, database exports, backups | ignored/local-only | D | Credentials/operational data | KEEP_PRIVATE | Never publish or mutate active storage |
| node_modules/, virtual environments, .next/, caches | ignored | E | Generated | IGNORE | Reproducible dependencies; no deletion performed |
| Legacy standalone Analyzer | tracked/local-only | F | Code | NEEDS_REVIEW | Compare callers before any future consolidation |

## Reproduction and privacy

Commands: `git rev-parse --show-toplevel`, `git branch -avv`, `git status --porcelain=v1 -uall`, `git ls-files --deleted`, `git ls-files --others --exclude-standard`, `git ls-files --others --ignored --exclude-standard`, `git diff --name-status`, `git worktree list`, `git fetch origin`, `git ls-remote --heads origin`, `git ls-remote --tags origin v0.3.0`, `git log origin/main..origin/handoff/eims-supervision-2026-10-08`.

Full filenames of private media, credential candidates and local backups are intentionally excluded from this public report. The owner has the detailed private CSV and original binary diff outside the repository. Phase 0 used no cleanup, pull, merge, database operation or history rewrite. A later legacy auth validation crossed the database-isolation boundary; see TEST_SAFETY_INCIDENT.md for impact and correction.
