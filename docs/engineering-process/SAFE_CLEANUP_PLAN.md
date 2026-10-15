# Safe cleanup plan

No files have been deleted or moved for cleanup. Backup copies are not a cleanup operation. Keep the original checkout as an operator/demo workspace and the separate development worktree as the code review area.

| Action | Scope | Preconditions |
|---|---|---|
| KEEP_TRACKED | Source, tests, historical specifications, baseline fixtures | Review modified files and secret-screen changes |
| ADD_TO_GIT | New synthetic regressions, targeted fixes, sanitized engineering docs | Tests, privacy review and explicit path staging |
| KEEP_PRIVATE | Environment files, raw logs, database backups, media, consent/identifiable responses | Store outside Git; control access locally |
| IGNORE | Dependencies, build output, generated test artifacts | Keep useful test evidence locally; publish sanitized summaries |
| ARCHIVE_LOCALLY | Superseded packs or duplicate exports, if owner later chooses | Verify hashes/references and a restorable backup first; none archived/moved now |
| PROPOSE_REMOVE | None in this pass | Dependency/reference check and separate owner decision required |
| NEEDS_REVIEW | Standalone client source, local slides/media, historical field claims | Preserve first; do not equate ignored or old with disposable |

The three original tracked demo deletions remain unstaged. Their baseline bytes are backed up and present in the new worktree. Do not use blanket add, clean, reset, restore, Docker volume deletion or forced checkout. The existing `/lib/` rule is root-anchored; the local-only standalone client's `src/lib/` files are untracked, not hidden by that rule. Preserve and review them before any later consolidation.
