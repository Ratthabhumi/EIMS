# EIMS V12 — Independent Review Scope (A10)

Date: 2026-11-18 (Asia/Bangkok)
Reviewer: **Claude Code — READ-ONLY**
Repository under review: `C:\Users\MewMew\Desktop\Co-op\EIMS`
Companion scope for the internal tool: `Chat_HAND/docs/V12_INDEPENDENT_REVIEW_SCOPE.md`

## 1. Mandate

The reviewer verifies whether the frozen baseline and its evidence claims are trustworthy. The reviewer does not improve the product.

Read-only means: no file creation, no edit, no delete, no formatting, no test authoring, no configuration change, no service start/stop, no `git add`, no commit, no evidence generation.

## 2. Inputs to the review

| Input | Purpose |
|---|---|
| `evidence/v12-head-manifest.json` | what `HEAD` contains |
| `evidence/v12-working-tree-manifest.json` | what is actually on disk |
| `evidence/v12-freeze-summary.json` | authoritative counts and manifest hashes |
| `evidence/v12-evidence-revision-map.json` | which evidence is bound to which revision |
| `docs/V12_SOURCE_FREEZE_MANIFEST.md` | freeze protocol and exclusions |
| `docs/V12_EVIDENCE_REVISION_BINDING.md` | classification rules and findings |
| `docs/V12_ENGINEERING_FREEZE_AUDIT.md` | audit findings |
| `docs/V12_GATE2_TEST_PLAN.md` | planned commands and stop conditions |
| `docs/V12_FINAL_ACCEPTANCE_MATRIX.md` | per-item status |
| `git status --porcelain -uall`, `git diff` | diff surface |

## 3. Review questions

### 3.1 Freeze integrity
1. Do the manifest hashes reproduce on the current tree?
2. Is any file present on disk but absent from the working-tree manifest, other than documented exclusions?
3. Are the exclusions defensible, or do they hide source, tests or required fixtures?
4. Is the `.gitignore` negation scoped exactly to `scripts/agent-monitor/tests/fixtures/**/*.log`, with no collateral effect?
5. Is `HEAD_IDENTICAL` vs `MODIFIED` classification derived from `git status` rather than hash equality?

### 3.2 Evidence integrity
6. Is any `HISTORICAL`/`STALE`/`UNVERIFIED` result presented as current anywhere in the documents?
7. Are pass counts traceable to a transcript, or only to a summary line?
8. Is the claim "45 of 58 modified files are newer than the evidence" correct?
9. Are evidence files preserved rather than rewritten?

### 3.3 Product and data integrity
10. Do migrations have a single head and a coherent chain?
11. Do tests that touch a database fail closed when pointed at a non-disposable target?
12. Is any test capable of writing into the main working tree instead of a disposable copy?
13. Are secrets excluded from evidence and from logs?
14. Is the analyzer evaluation boundary honest (no accuracy claim from 0 reviewed cases)?

### 3.4 Scope boundaries
15. Is any Chat_HAND internal capability described as an EIMS product result, or vice versa?
16. Is the persistent monitor correctly attributed to EIMS?
17. Are the two monitor suites kept separate (169 and 171, never combined)?

### 3.5 Risks not yet covered
18. Which acceptance criteria in `V12_FINAL_ACCEPTANCE_MATRIX.md` lack a test at all?
19. Which claims depend on a live runtime that is currently stopped?
20. Which container/service dependencies could make a result non-reproducible?

## 4. Prohibitions

- Do not fix anything you find.
- Do not weaken, skip or rewrite an assertion.
- Do not create evidence.
- Do not re-run a suite that writes into the working tree.
- Do not start containers, services or the Chat_HAND runtime.
- Do not modify `.gitignore`, fixtures, manifests or reports.

## 5. Output format

Per finding:

```
ID: EIMS-RV-<n>
Severity: CRITICAL | HIGH | MEDIUM | LOW | INFO
Area: freeze | evidence | product | data-integrity | security | scope | docs
Path: <file>[:line]
Claim at risk: <what would be falsely asserted>
Finding: <fact>
Reproduction: <command or inspection step>
Suggested remedy: <description only, not applied>
```

Plus a summary table of counts per severity, and an explicit statement of what the reviewer could **not** verify.

## 6. Handling of findings

1. Reviewer reports only.
2. OpenCode independently verifies each finding before it reaches the controller.
3. ChatGPT decides accept / reject / defer.
4. A CRITICAL finding blocks Gate 1. HIGH findings block the affected track only.

## 7. Out of scope

- Chat_HAND internals (separate scope document).
- Live cross-system E2E.
- UI/UX review.
- Performance tuning.
- Any change to the frozen tree.

## 8. Preconditions before requesting the review

- Freeze summary generated and hashes recorded.
- No concurrent writer.
- Diff frozen (no further edits until the review returns).
- Review scope delivered with the exact commit and manifest hashes.
