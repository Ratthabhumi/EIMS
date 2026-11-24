# EIMS Engineering Memory — 2026-11-16 Auto Job Relay (Chat_HAND V6)

## Scope

Implemented the EIMS Auto Job Relay inside **Chat_HAND only**. No EIMS
application code, Incident Core, database, Redis or MinIO change. The running
Incident Core work was not touched.

## Problem

`agent.run` launched an agent as a child of the MCP server. Nothing observed the
job afterwards: the caller had to poll `workspace.job_status` and fetch the
artifact by hand, and an MCP restart killed a healthy agent.

## Platform boundary (verified, not assumed)

An external MCP gateway cannot inject an unsolicited assistant message into an
existing ChatGPT conversation.

- MCP 2025-06-18 defines request/response/notification only; `sampling` is a
  server-to-client request the host may decline, not a conversation write.
- ChatGPT tool calls are request-scoped (our accepted run: 55.1 s).
- `learn.chatgpt.com/docs/automations` supports a scheduled task **inside a
  chat** that checks a long-running operation and reports back, but the Help
  Center states a different minimum cadence. The cadence is unverified on this
  account and is therefore not assumed.

Consequence: delivery is **on demand** (`jobs.wait`, `jobs.get_result`), with a
scheduled follow-up as a supported but unverified option.

## Architecture

| Component | File | Responsibility |
|---|---|---|
| Detached runner | `gateway/lib/agent-runner.mjs` | one agent child, stdout/stderr by fd, heartbeat, atomic `exit.json` |
| Job store | `gateway/lib/job-store.mjs` | atomic records, split artifacts, SHA-256, result envelopes, delivery ledger |
| Monitor | `gateway/lib/job-monitor.mjs` | bounded scan, finalization, restart adoption, bounded reconcile |

Lifecycle: `queued -> running -> collecting -> completed|failed|timed_out|cancelled|interrupted`.
Delivery is a separate dimension (`result.state`: `available -> acknowledged`),
composed into the read-only `lifecycle` field, so a failure outcome is never
overwritten by "the result is now available".

Durability: the runner is spawned detached with `unref()`; nothing in the write
path touches the MCP server. Interruption proves process identity with a Windows
`StartTime` window, defers three times before killing (sleep/resume), never kills
an unverified pid, and releases the writer lock last. An interrupted job stays
reconcilable for five minutes against a late, token-matching exit document.

Artifacts: `stdout.log` and `stderr.log` separately, per-stream SHA-256,
truncation flag, chunked reads with `offsetBytes`/`eof`, credential-shaped output
withheld (broader pattern set, including on the interruption path).

## Session and project isolation

`hostSessionId` is host-supplied correlation metadata, not an authenticated
identity. Session filtering is scoping, not access control; **project isolation
is the boundary**. Cross-session reads require `cross_session: true` plus a
consumed single-use local approval.

## Verification

- `node scripts/test-job-relay.mjs`: **25 passed, 0 failed**, exit 0.
  `evidence/v6-job-relay-acceptance.json`.
- `node scripts/test-orchestration.mjs`: **22 passed, 0 failed**, exit 0.
- `node scripts/test-control-plane.mjs`: **40 passed, 0 failed, 1 not tested**.
- `node scripts/Smoke-EimsAgentRelay.mjs`: **7 passed, 0 failed** — approved
  read-only Claude Code job: bounded `jobs.wait` returned `still_running` at 40 s,
  `jobs.get_result` retrieved the completed result (exit 0, 231 bytes,
  `sha256 1cdff417…`), acknowledged; worktree unchanged. An archived OpenCode run
  shows the relay correctly recording a provider-credit failure (exit 1, stderr
  captured and retrievable). `evidence/v6-real-relay-e2e.json`,
  `evidence/v6-real-relay-runs/`.
- Independent read-only review (Claude Code, three rounds): round 1 HIGH
  (interruption could release a writer lock without proving the process dead);
  round 2 HIGH introduced by that fix (unbounded pid kills with no identity
  proof); round 3 **NO HIGH-SEVERITY FINDINGS**. `evidence/v6-review.json`.

## Boundaries / pending

- Unsolicited ChatGPT delivery is not possible; scheduled-task cadence unverified.
- Machine restart is not survived; such jobs are `interrupted`.
- Real writer mode through the relay is not claimed.
- Browser Acceptance NOT RUN.
- No commit, push, reset, clean, checkout, stash or rebase; 57 modified EIMS files
  preserved.
