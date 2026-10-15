# Consolidated workspace and approval-only cleanup — 15 October 2026

## Current active project

`C:\Users\Ratthabhumi\Desktop\CO-OP_Project\EIMS` is the single active development directory on `work/eims-engineering-process-2026-10`. All five previous commits through `a4c5c66` were retained by Git branch switching, not source-folder copying. The former development worktree is detached at `a4c5c66`, retained as an inactive checkout pending approval. No worktree, backup directory, Git branch, tag or ZIP was deleted.

Original local changes consisted of three deleted tracked demo files. Their deletion state is preserved in Git stash `dbb2a25392f1e412510ede75cf5d6d3213814a9b`; original baseline files are restored for reproducible tests. Do not blindly apply this stash: it intentionally deletes those demo files. The original supervision branch still points to `8c26f03`; main/release are unchanged.

180 private/unreviewed presentation, media and demo-pack files were moved within EIMS to `.local-private`, with before/after SHA-256 equality. Existing operational environment/runtime data remain in place. Five unique standalone client helper files remain at their original paths under local `.git/info/exclude`, pending review. No uncommitted source was overwritten. The private movement manifest records exact paths. The new tracked ignore rule excludes `.local-private/`; Git tracking and ignore checks confirm it is untracked and ignored.

## Exact approval list

| Absolute path | Recommendation | Evidence / conditions |
|---|---|---|
| `C:\Users\Ratthabhumi\Desktop\CO-OP_Project\EIMS-engineering-2026-10` | PROPOSE_REMOVE after owner approval | Clean detached snapshot; five commits recoverable in the active branch; 10 unique prior raw test artifacts (11,093,391 bytes) copied and hash-verified under EIMS/.local-private/previous-test-evidence. Remaining ignored files are build/cache/runtime artifacts. Remove through the Git worktree lifecycle, after checking no new files appeared. |
| `C:\Users\Ratthabhumi\Desktop\CO-OP_Project\EIMS-engineering-2026-10\clients\dashboard\node_modules` | PROPOSE_UNLINK junction as part of approved worktree removal | This is a junction pointing at EIMS/clients/dashboard/node_modules. Never recursively delete its target. Verify the resolved target immediately before any approved removal. |
| `C:\Users\Ratthabhumi\Desktop\CO-OP_Project\EIMS_ENGINEERING_REVIEW_2026-10-15.zip` | PROPOSE_REMOVE after approval | Earlier 24-file export is now outdated; canonical documents are in Git. No replacement ZIP was created. |
| `C:\Users\Ratthabhumi\Desktop\CO-OP_Project\EIMS_PRIVATE_2026-10-15` | KEEP_PRIVATE; not approved for deletion | Contains the only private inventory/backup, verified baseline and delivery bundles, original diff, incident IDs and consolidation manifests. No complete replacement of this backup was made. |
| `C:\Users\Ratthabhumi\Desktop\CO-OP_Project\EIMS\.local-private` | KEEP_PRIVATE | Moved assets, earlier raw test evidence and synthetic evaluation databases. Ignored does not mean encrypted; retain appropriate filesystem/account access controls. |

No other files are proposed for removal. Do not remove the original venv/node_modules, operational storage, environment files, logs or private backup. Dependencies are reused from EIMS; no additional worktree/environment was created. Caches may remain until the approved inactive-worktree cleanup; their presence is not an active development copy.

## Recovery checks

All five prior commits are ancestors of the active branch. The supervision/main/release refs and preserved stash are available; the existing private Git bundles verify successfully. Backup and moved-file manifests remain private. The active working tree is committed after review. No remote publication is allowed until the credential blocker is resolved. The three operational incident rows were neither queried nor modified during this continuation.
