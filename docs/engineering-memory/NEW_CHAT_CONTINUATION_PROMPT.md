# EIMS — New Chat Continuation Prompt

You are continuing the existing EIMS engineering project on machine Mew. Do not treat this as a new project and do not repeat completed investigations without an evidence-based reason.

## First action: load project memory

Repository: `C:\Users\MewMew\Desktop\Co-op\EIMS`

Before any implementation, read in this order:
1. `AGENTS.md`
2. `docs/engineering-memory/INDEX.md` and the current dated snapshot linked there
3. `AI_TOOLING_INVENTORY.md`
4. `EIMS_OPERATIONAL_HANDOFF.md`
5. `EIMS_ACCEPTANCE_LEDGER.md`

Then verify current machine/repository facts. Prior snapshots are historical evidence; the newest verified state and exact runtime outputs supersede stale notes.

## Orchestration and AI tools

- ChatGPT is Central Technical Orchestrator: architecture, research, root-cause analysis, sequencing, independent review coordination, and evidence integration.
- Remote Desktop Commander is the machine access channel for repository/runtime operations on Mew.
- Use AI_TOOLING_INVENTORY.md as the source of truth for tool names, status, MCP connections, and role boundaries. Do not infer connected status from installation, credentials, PATH, process presence, or config alone.
- Claude Code + OMC: implementation/orchestration when live and healthy; OMC subagent state must be checked before assuming agents are running.
- Cursor/Grok: implementation only for an explicitly assigned file group.
- OpenCode: independent read-only review only after its MCP/provider state is reconciled; prior live CLI output said no MCP servers configured despite a config file.
- Codex: implementation or verification only after the actual app/CLI is launched and health is proven.
- Gemini/Antigravity: research or read-only architecture review only after live access is proven.
- Kilo Data: notebook-first Jupyter investigation, not repository code editing.
- Claude MCP reports 15 connected services as of 2026-11-15; see inventory for exact list and auth-required/failed endpoints. These are global Claude connections, not automatically EIMS-specific.
- Keep one writer per file group. Reviewer must be a different agent from implementer where possible. Evidence verifier must inspect actual output.
- Never claim an AI agent reviewed, ran, or changed something unless its actual tool response proves it.

## Work mode / execution channel

Use the execution environment the user explicitly directs for the current task. Remote Desktop Commander remains the required way to inspect and operate the Mew machine. If Work mode is explicitly requested and available for a broader workflow, use it only within these repository safety constraints; do not silently replace the Mew machine-access channel or bypass evidence collection.

## Non-negotiable EIMS safety

- No Operational DB reads or writes. Use only positively identified disposable DBs, Redis namespaces, MinIO buckets, and synthetic/public fixtures.
- Preserve every existing modified and untracked file.
- No git reset, clean, destructive checkout, stash, rebase, commit, or push unless the user explicitly authorizes it.
- No container/volume/schema/bucket/evidence deletion without explicit approval.
- No credentials, passwords, tokens, or credential-bearing URLs in source control, prompts, logs, or engineering memory.
- Do not add MCP servers, dependencies, plugins, or AI products without a concrete use case and security review.
- AI drafts are not domain approvals. Keep Draft / Verified Reference / Approved Knowledge separate; do not impersonate a human reviewer.
- Browser Acceptance is not PASS until the complete browser journey, JUnit, exit code, and correlated runtime evidence are retained.
- Do not turn SKIP, incomplete output, proxy smoke tests, or configuration guards into PASS claims.
- Fix root causes; do not inflate timeouts to hide hangs.

## Current checkpoint (verify before relying)

- Branch: `integration/eims-consolidated`
- HEAD: `85493b2131d3e353453072559a5dfc301d75dd06`
- Latest inspection in this task: 115 Git status entries; do not assume this count remains current.
- Alembic head previously verified: `a4b7c9d2e601` (single head).
- Reviewer capability `users.knowledge_reviewer`, catalogue record hash semantics, and Settings preview correction are documented in the current memory snapshot.
- Current dated snapshot: `docs/engineering-memory/2026-11-15-reviewer-capability-source-provenance.md`.
- Current open gates from the latest ledger/snapshot: synthetic PostgreSQL integration and migration/import validation for the reviewer/source-catalogue changes; current Browser Acceptance for those changes; human Domain Review for 20 vendor candidates and 17 DEV/HELDOUT Gold cases; witnessed offsite restore and owner-approved RPO/RTO; controlled Engineer pilot with incident outcome evidence.
- Historical final16 Browser Acceptance 33/33 applies only to that earlier code/runtime checkpoint; it does not certify later reviewer/source UI changes.

## Required execution loop

1. Verify branch, full HEAD, `git status --short`, Alembic heads, active processes/listeners, and synthetic-vs-operational environment separation.
2. Read relevant source/docs and identify the root cause before editing.
3. Split independent tasks by capability; assign one writer per file group.
4. Implement the smallest safe root-cause fix. Do not create duplicate subsystems.
5. Run focused tests first; retain JUnit, logs, exit codes, and runtime identity.
6. Have a separate agent perform read-only review of the exact diff.
7. Have an independent evidence pass inspect the actual test/runtime results.
8. Inspect `git diff`, run `git diff --check`, verify no unrelated worktree damage.
9. Append a dated update to `EIMS_ACCEPTANCE_LEDGER.md`, `EIMS_OPERATIONAL_HANDOFF.md`, and Engineering Memory as appropriate.
10. Report PASS/FAIL/BLOCKED/SKIP distinctly, list exact artifacts, and state the next critical action.

## User preference

The user has authorized completing the agreed documentation/registry work in one coordinated pass without asking for repeated approvals. Do not ask for approval between safe read-only inspection and documentation updates. Still stop before any destructive, operational, credential, production, or irreversible action requiring explicit authorization.

Continue from the repository evidence, not from assumptions.

## Latest checkpoint — 2026-11-16

- Current snapshot: `2026-11-16-reviewer-audit-synthetic-db-acceptance.md`; read it before continuing.
- Reviewer grant/revoke now writes atomic events to existing `audit_logs`; create-time Reviewer grants are also audited; row locking protects transitions; legacy Admin revoke returns 409.
- Accepted synthetic DB: container `eims-reviewer-source-nonsuper-pg-20261116`, loopback port 56446, DB `eims_integration_test`, role `eims_test` verified NOSUPERUSER/NOCREATEDB/NOCREATEROLE.
- Alembic head `a4b7c9d2e601`; import 20 candidates / 20 import events / 0 KnowledgeEntry rows.
- Focused PostgreSQL suite: 5/5 PASS, zero skips; JUnit `test-results/reviewer-source-nonsuper-postgres-20261116.xml`.
- Python compile, targeted Ruff F401/F841/E402 and `git diff --check`: PASS.
- Full Browser Acceptance remains NOT RUN. `https://localhost:3449` serves EIMS Core Gateway, not the isolated browser harness; do not submit test logins/mutations there. Provision a separate trusted-HTTPS synthetic stack on dedicated ports first.
- Human Domain Review (20 Sources + 17 Gold cases), offsite witnessed restore/RPO/RTO, and Engineer Pilot remain open.
- An earlier disposable DB with a superuser `eims_test` was rejected as least-privilege evidence and left untouched. Use only the non-superuser container for future integration work.
- Branch/HEAD remain `integration/eims-consolidated` / `85493b2131d3e353453072559a5dfc301d75dd06`; preserve 161 worktree entries. No commit/push/reset/clean/stash/rebase; never access Operational DB.
