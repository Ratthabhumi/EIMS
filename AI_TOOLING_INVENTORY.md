# EIMS AI Tooling Inventory

**Verified:** 2026-11-15 (Mew / Windows 11)
**Repository:** `C:\Users\MewMew\Desktop\Co-op\EIMS`
**Purpose:** Evidence-backed registry of AI applications, coding agents, providers, MCP servers, roles, and verification status. This file is a living inventory, not a claim that every installed tool is authorized for every EIMS task.

## 1. Status vocabulary

- **CONNECTED** — the owning application’s live status command reported a healthy/connected endpoint at the verification time.
- **CONFIGURED** — a configuration entry exists, but live connection/authorization was not proven.
- **INSTALLED** — executable, application, extension, or project configuration was found; no successful EIMS task is thereby implied.
- **USED-HISTORY** — project-specific session/history or an earlier operational handoff records use/assignment. This is historical evidence, not proof the process is currently active.
- **AUTH-REQUIRED** — server is listed but reports that authentication is required.
- **FAILED** — live status reported a connection or endpoint failure.
- **CANDIDATE** — proposed in historical research; no installation/connection evidence.

Never upgrade a status based only on a directory, credential, process, extension, or config file.

## 2. Machine AI applications and coding agents

| Tool | Evidence on Mew | Status | EIMS role / boundary |
|---|---|---|---|
| Claude Code | `claude.exe` at `~/.local/bin`; version 2.1.323; 33 EIMS project session JSONL files; global `~/.claude/CLAUDE.md`; 2026-11-16 headless read-only `-p` smoke returned `OK` with no files changed; live `claude mcp list` recheck timed out at 90 s | INSTALLED + USED-HISTORY + HEADLESS VERIFIED | Implementation/debugging only on an assigned file group; can orchestrate specialists via OMC. Must not self-approve. |
| Oh My ClaudeCode (OMC) | Global Claude instructions declare OMC 4.10.1 and multi-agent workflows; EIMS `.omc` memory/state exists | CONFIGURED | Planner/architect/executor/reviewer workflows when actually spawned. EIMS tracking file last reported 0 spawned / 0 completed on 2026-11-13; verify current state before assuming active agents. |
| Codex | Codex Windows app config under `~/.codex/config.toml`; model label `gpt-6-luna`; bundled app build path in config | INSTALLED + CONFIGURED | Implementation or independent verification when launched successfully. The `codex` command was not recognized in the inspected PowerShell PATH; app presence is not CLI health evidence. |
| Gemini CLI | `~/.gemini` state and config exist; `gemini` command not recognized in inspected shell; Gemini MCP config is empty | INSTALLED/CONFIGURED ARTIFACTS | Research/cross-review only after executable and account/session health are verified. |
| Antigravity (IDE/Standalone) | `~/.gemini/antigravity`, `antigravity-ide`, browser profile, CLI binary `agy.exe`; MCP config files are empty | INSTALLED + USED-HISTORY (prior handoff role) | Read-only architecture/UI review unless separately assigned. Distinguish IDE from Standalone. |
| OpenCode | version 2.3.0; `~/.config/opencode/opencode.jsonc` contains `fablecut` and `browse`; live `opencode mcp list` on 2026-11-16 reported `browse connected` and `fablecut failed` (missing external FilmAI server file); used as the read-only reviewer on 2026-11-16 | INSTALLED + CONNECTED (browse) + USED | Multi-provider coding/review; fablecut is outside EIMS and must not be relied on. |
| Cursor | version 3.30.14; EIMS always-on rule `.cursor/rules/eims-engineering-memory.mdc`; workspace/global state present | INSTALLED + PROJECT RULES + USED-HISTORY | Code exploration/implementation only for an explicitly assigned file group. |
| Kilo Code | EIMS `.kilo/agents/data.md` and `.kilo/kilo.jsonc` | PROJECT-CONFIGURED | The EIMS Data agent is notebook-first Jupyter. Do not use it as a repository code implementer. |
| GitHub Copilot | Azure Skills manifest was found in prior machine inspection | INSTALLED ARTIFACT (connection not revalidated) | Azure/coding assistance only after account and target repository access are verified. |
| Cline | User configuration/extension data found in prior inspection | INSTALLED ARTIFACT (connection not revalidated) | Optional IDE coding agent; do not assume active EIMS access. |
| Continue | Configuration/extension data found in prior inspection | INSTALLED ARTIFACT (connection not revalidated) | Optional IDE assistance; no verified EIMS role. |
| Windsurf | `~/.windsurf/argv.json` and extension data | INSTALLED ARTIFACT (connection not revalidated) | Optional IDE assistance; no verified EIMS role. |
| Grok / Cursor-Grok | `cursor-grok.cmd` wrapper and local Grok Bot runtime were found in prior inspection; prior handoff assigns Cursor/Grok implementation | USED-HISTORY / CONFIG ARTIFACT; live provider not revalidated | Only one designated writer for a file group; verify model/provider and actual output before assigning. |
| Manus | Skills/user-skills artifacts found in prior inspection | INSTALLED ARTIFACT (connection not revalidated) | Agent workflow candidate; no verified EIMS access. |
| CrewAI | `~/.config/crewai` directory found | INSTALLED/CONFIG ARTIFACT | Orchestration candidate; no verified EIMS run. |
| cagent | `~/.config/cagent` first-run/user state found | INSTALLED/CONFIG ARTIFACT | Orchestration candidate; no verified EIMS run. |

**Important:** 33 Claude EIMS session files establish project-specific Claude history exists, but the session contents have not been exhaustively audited here to attribute every change or review. The previous operational handoff records Cursor/Grok as implementation writer, OpenCode as independent read-only reviewer, Claude Code Safe Mode as test/reliability reviewer (with a startup/stdin caveat), Antigravity as read-only architecture reviewer, and ChatGPT as technical lead. Treat those as recorded role assignments; require fresh tool output for each new review.

## 3. Live MCP inventory — Claude Code

Command run on Mew: `claude mcp list` (2026-11-15). It returned a live server health report.

### CONNECTED (15)

1. Claude Docs — `https://api.anthropic.com/v1/pages/mcp`
2. Linear — `https://mcp.linear.app/mcp`
3. Wispr Flow — `https://api.wisprflow.ai/connect/mcp`
4. Stripe — `https://mcp.stripe.com`
5. Microsoft Learn — `https://learn.microsoft.com/api/mcp`
6. Context7 — `https://mcp.context7.com/mcp`
7. Vercel — `https://mcp.vercel.com`
8. Supabase — `https://mcp.supabase.com/mcp`
9. Canva — `https://mcp.canva.com/mcp`
10. Google Docs — `https://docsmcp.googleapis.com/mcp/v1`
11. Google Slides — `https://slidesmcp.googleapis.com/mcp/v1`
12. Google Sheets — `https://sheetsmcp.googleapis.com/mcp/v1`
13. Gmail — `https://gmailmcp.googleapis.com/mcp/v1`
14. Google Calendar — `https://calendarmcp.googleapis.com/mcp/v1`
15. Google Drive — `https://drivemcp.googleapis.com/mcp/v1`

These are connected in Claude Code's global MCP environment. They are not automatically EIMS-specific tools, and their availability in another AI application must be checked independently.

### AUTH-REQUIRED

- Todoist Automations
- Stoky Matrix
- Storeask
- Wix
- Exa
- Orion Advisor Solutions
- Wealth.com
- Wealthbox
- Addepar
- Zocks
- iCapital
- CAIS
- Salesforce
- Microsoft 365
- Dropbox
- Daloopa
- FactSet
- S&P Global
- Morningstar
- BlackRock

### FAILED / NOT CONFIGURED

- Black Diamond — endpoint returned HTTP 503 maintenance response.
- Vanguard Advisor Tools — endpoint not found at configured host.
- Snowflake — listed but no endpoint configured.

Do not attempt authentication, repair, or enablement as part of ordinary EIMS work unless the user explicitly requests that integration and the business use case is approved.

## 4. MCP configuration in other clients

| Client | Evidence | Current interpretation |
|---|---|---|
| Codex | `~/.codex/config.toml` defines `node_repl` (bundled app runtime) and `fablecut` (external FableCut server) | CONFIGURED. Not live-verified in Codex; `codex` was not recognized in PATH. FableCut belongs to the separate FilmAI project, not EIMS. |
| OpenCode | `opencode.jsonc` defines `fablecut` and `browse`; live `opencode mcp list` reported no configured servers | CONFIGURED FILE / LIVE STATUS CONFLICT. Investigate config path/profile only when needed; do not claim connected. FableCut is outside EIMS. |
| Gemini CLI | `~/.gemini/config/mcp_config.json` has empty `mcpServers`; CLI not recognized in inspected shell | No MCP configured in this file; runtime not verified. |
| Antigravity | Standalone and IDE `mcp_config.json` files contain empty `mcpServers` objects | No MCP configured in those files. |
| EIMS Kilo | `.kilo/kilo.jsonc` only sets schema/snapshot; agent definition is notebook-first Data | No MCP server declared in this project config. |
| EIMS OMC | `.omc/state/subagent-tracking.json` says 0 spawned / 0 completed at last recorded update 2026-11-13 | Do not infer active orchestration. |

## 5. Historical candidates — not connected evidence

The 2026-10-28 research record mentioned DWB MCP Studio, OpenAI Secure MCP Tunnel, MCP Inspector, Serena MCP, Google Stitch, ComfyUI MCP, OpenAI Developer Docs MCP, and DWB Agent Skills. These remain **CANDIDATE / historical proposal** unless a later live check proves otherwise. Do not install duplicates or add MCP endpoints without a concrete EIMS use case, security review, and owner approval.

## 6. EIMS responsibility and review protocol

| Responsibility | Primary | Boundary |
|---|---|---|
| Technical orchestration, architecture decisions, sequencing, external research, evidence integration | ChatGPT | Does not claim machine execution unless Remote Desktop evidence is returned. |
| Repository/runtime access on Mew | Remote Desktop Commander | Use for actual machine inspection and execution; preserve worktree and evidence. |
| Implementation | One explicitly assigned coding agent (Claude Code, Cursor/Grok, Codex, or other verified agent) | One writer per file group; do not let multiple agents edit the same files concurrently. |
| Independent code/migration/security review | A different agent from the implementer (historically OpenCode) | Read-only; return concrete findings tied to changed paths and failure modes. |
| Test/reliability review | Separate agent (historically Claude Safe Mode) | Do not rely on it until startup/stdin health is verified. |
| Architecture/UI review | Antigravity, read-only | Separate IDE vs Standalone and prove actual output. |
| Data investigation | Kilo Data | Notebook-first; append and execute Jupyter cells; no repository implementation. |
| Evidence verification | Separate verifier / ChatGPT evidence integration | Inspect exit codes, JUnit, logs, runtime state, and exact diff. No self-certification. |

A tool is a reviewer only when it returns review content for the exact change. A successful MCP health check, installed extension, credential, open process, or empty review response is not a review.

## 7. Mandatory EIMS safety boundaries

- Read root `AGENTS.md`, this inventory, Engineering Memory `INDEX.md` and current dated snapshot, `EIMS_OPERATIONAL_HANDOFF.md`, and `EIMS_ACCEPTANCE_LEDGER.md` before starting.
- Preserve all existing modified/untracked files. No `git reset`, `git clean`, destructive checkout, stash, rebase, commit, or push without explicit authorization.
- Never access or mutate the Operational DB. Use positively identified disposable DBs, Redis namespaces, MinIO buckets, and synthetic/public fixtures only.
- Never place credentials, tokens, passwords, or credential-bearing URLs in source control, logs, prompts, or memory documents.
- Do not let agents share write ownership of the same files. Reviewers are read-only.
- Browser Acceptance is not PASS without the complete browser journey, JUnit, exit code, and correlated runtime evidence.
- Draft, Verified Reference, and Approved Knowledge are distinct states. AI cannot impersonate a human domain reviewer.
- Record actual tool output and timestamp. If a connection fails or cannot be checked, leave status as unknown/configured rather than guessing.

## 8. Refresh procedure

At the start of a major EIMS milestone, refresh only the relevant status without dumping secrets:

1. `claude --version` and `claude mcp list`.
2. `opencode --version` and `opencode mcp list` from the intended EIMS working directory/profile.
3. Launch Codex/Gemini/Antigravity through their actual installed application/CLI entry point and verify account/session plus a harmless read-only EIMS task.
4. Inspect configuration by parsing/redacting secret-bearing fields; never print raw credential stores.
5. Confirm actual use with returned output and EIMS project session/task evidence.
6. Update this file with status, date, exact evidence, and any unresolved mismatch.

**Last verified:** 2026-11-15. Recheck before relying on any connection; status can change.


## 9. External research basis

The registry and continuity design follow current official guidance and security research checked on 2026-11-15:

- OpenAI/Codex — [Custom instructions with AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md): layered global/project instructions, discovery precedence, and verification of loaded instructions.
- OpenAI/Codex — [Customization overview](https://learn.chatgpt.com/docs/customization/overview): project guidance, memories, skills, MCP, and subagents are complementary layers with different purposes.
- OpenAI Cookbook — [Iterating Development Workflows with Codex](https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex): keep durable repo instructions, phase plans, build logs, context, and review artifacts separate.
- Anthropic — [Steering Claude Code: skills, hooks, rules, subagents](https://claude.com/resources/articles/steering-claude-code-skills-hooks-rules-subagents-and-more): use CLAUDE.md for persistent session guidance, skills for reusable procedures, hooks for deterministic controls, and subagents for isolated work/review.
- Cloud Security Alliance — [MCP Tool Poisoning and AI Agent Exfiltration research note](https://labs.cloudsecurityalliance.org/wp-content/uploads/2026/07/CSA_research_note_mcp_tool_poisoning_ai_agent_exfiltration_20260702-csa-styled.pdf): maintain a complete MCP inventory, restrict connections to an allowlist, verify tool definitions, and govern access rather than trusting model behavior alone.

### Practical design adopted for EIMS

- Root `AGENTS.md` is the concise, canonical operating contract; it points to detailed artifacts rather than duplicating them.
- Root `CLAUDE.md` and `GEMINI.md` are client-specific entry points that point back to the same contract. Cursor and Kilo retain their native project-specific rules.
- `AI_TOOLING_INVENTORY.md` owns machine/client/MCP status; `EIMS_OPERATIONAL_HANDOFF.md` owns current execution state; `EIMS_ACCEPTANCE_LEDGER.md` owns acceptance evidence; Engineering Memory snapshots own dated decisions; the continuation prompt is the portable new-chat bootstrap.
- Keep the always-loaded instruction layer short and actionable. Detailed historical evidence belongs in linked documents to reduce context cost and instruction drift.
