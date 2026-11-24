# EIMS Agent Operating Contract

Before any EIMS task, read:
1. `docs/engineering-memory/INDEX.md` and its current dated snapshot.
2. `AI_TOOLING_INVENTORY.md`.
3. `EIMS_OPERATIONAL_HANDOFF.md`.
4. `EIMS_ACCEPTANCE_LEDGER.md`.
5. For a new ChatGPT conversation, use `docs/engineering-memory/NEW_CHAT_CONTINUATION_PROMPT.md` as the continuation prompt.

## Orchestration

- ChatGPT is the central technical orchestrator and evidence integrator.
- Use Remote Desktop Commander for repository and runtime work on Mew.
- Use the execution mode the user explicitly directs for the current task. Work Mode may be used when the user explicitly requests it; Remote Desktop Commander remains the required channel for direct repository/runtime operations on Mew. Never let a mode change bypass repository safety, independent review, or evidence requirements.
- Delegate by capability: research, implementation, independent read-only review, and evidence verification.
- Keep one writer per file group. A reviewer must be separate from the implementer where possible.
- Only report an AI review if the tool returned actual review content. Stored provider credentials or running desktop processes alone are not review evidence.
- If a connected AI tool fails or returns no content, report that limitation and continue with available tools.
- Kilo's current project agent is notebook-first Data; use it for Jupyter-based data investigation, not repository code implementation. OMC subagent tracking must be checked before assuming agents are active.

## Non-destructive engineering rules

- Preserve all existing modified and untracked files. Do not run `git reset`, `git clean`, destructive checkout, stash, rebase, commit, or push unless explicitly authorized.
- Never access or mutate the Operational DB. Use only positively identified disposable databases, Redis namespaces, MinIO buckets, and synthetic/public fixtures.
- Do not delete containers, volumes, schemas, buckets, or evidence artifacts without explicit approval.
- Do not rerun broad test suites without an evidence-based reason. Prefer focused regression tests and retain JUnit plus process exit code.
- SKIP, incomplete output, a config-only guard, or a proxy smoke test is not a full acceptance PASS.
- Browser Acceptance is not PASS until the complete browser journey, JUnit, and supporting runtime evidence are retained.
- Fix root causes; do not inflate timeouts to conceal stalls. Distinguish cancellation deadline from hard wall-clock completion when cleanup must finish safely.
- Never store passwords, tokens, or credential-bearing connection strings in source control or engineering memory.

## Evidence discipline

- Verify branch, HEAD, and working-tree status before and after changes.
- Inspect the exact diff and run `git diff --check`.
- For database changes, test checkout, execution, cleanup, cancellation, pool recovery, and a real disposable database path where feasible.
- Keep historical evidence immutable and append dated updates to the acceptance ledger and operational handoff.
- Do not claim the Browser 502/503 root cause is resolved until the browser, proxy/BFF, backend, pool, and PostgreSQL evidence is correlated.
