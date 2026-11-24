# EIMS Engineering Memory — 2026-11-16 Relay Finalization + Incident Core v1.1 Prep

## Scope

Final acceptance pass on the Chat_HAND Auto Job Relay, plus preparation of the
Incident Core v1.1 milestone. **No EIMS application code, backend, or Incident
Core file was changed.** Chat_HAND tooling and EIMS documentation only.

## 1. Relay final acceptance (status, not a re-build)

| Item | Status |
|---|---|
| Local MCP surface: 18 tools, exact names, `jobs.*` callable | **PASS** (`scripts/Verify-EimsMcpSurface.mjs`, `evidence/v6-mcp-surface.json`) |
| Relay suites re-run on current code | **PASS** — 25/25, 22/22, 40 pass + 1 not tested |
| Real read-only agent end-to-end | **PASS** — Claude Code, bounded wait returned `still_running`, result retrieved and acknowledged, worktree unchanged |
| ChatGPT host catalog refresh | **NOT TESTED — user action** (Plugins → EIMS Control Plane → refresh/reconnect) |
| The single `NOT TESTED` control-plane case | **DOCUMENTED — environment limitation** |
| Real writer mode | **BLOCKED** (see §2) |
| Unsolicited ChatGPT injection | **UNSUPPORTED** (platform boundary) |
| Scheduled-task delivery | **NOT TESTED** |

### The previously untested case

`deny.symlink_file_escape` is skipped because creating a file symlink requires
`SeCreateSymbolicLinkPrivilege`; a direct probe returns "Administrator privilege
required". It is not an uncovered branch: the same reparse-point deny path is
proven by `deny.junction_escape` (PASS). No security behaviour was changed to
force a green result.

### New residual risk (path guard, not the relay)

A hard link created **inside** the workspace pointing at a file **outside** it is
readable through `workspace.read_file`; reproduced with a disposable workspace
(`OUTSIDE-MARKER-9f2` returned). Hard links need no privilege on the same volume.
This is a read path only: creating the link already requires local write access,
and there is no execution or write capability through it. Documented in
Chat_HAND `docs/CONTROL_PLANE.md` and `docs/AUTO_JOB_RELAY.md` §13; not "fixed",
because rejecting `nlink > 1` would reject legitimate files.

## 2. Writer smoke: BLOCKED, with evidence

- **OpenCode** cannot run at all on this host right now: a direct
  `opencode run --agent build` probe exits 1 with the provider message
  "This request requires more credits, or fewer max_tokens".
- The strongest supported alternative — **Claude Code writer mode** through the
  same approval-gated path — was prepared and its approval request created
  (`5cbe12e0…`, scope `sandbox/relay-writer-smoke`). The local approval was never
  executed: the record remained `pending`, so **no agent started** and no file
  was written. The gate behaved exactly as designed.
- Nothing outside the sandbox was touched; the empty sandbox directory was
  removed and the worktree is back to 126 entries (57 modified, 69 untracked).

Writer mode therefore remains **NOT ACCEPTED**; it needs one human approval step.

## 3. Incident Core v1.1 preparation

- Recovered the prior read-only architecture trace (job `3ef58a7d…`, exit 0,
  36 KB artifact) and preserved it as
  `2026-11-16-incident-core-v11-architecture-trace.md`.
- Wrote the implementation plan:
  `2026-11-16-incident-core-v11-plan.md`.
- Design decision (evidence-based): **additive `incident_ingest_outbox` plus a
  dedicated async consumer**. Do not extend `telemetry_alert_outbox` — it is a
  quarantine-transition path (one row per transition), it publishes every payload
  to the live alert PubSub channel, it has no durable consumer or processed-state
  table, and it is written only inside `_detect_brute_force`.
- Emission must be transactional with the source row, must use
  `ON CONFLICT DO NOTHING … RETURNING` (transient PKs are fresh uuid4 per
  attempt), and must never block ingestion on correlation or AI.
- `IncidentService.create_from_evidence` is a transaction **owner** (it commits),
  so it must run on a dedicated session after the source commit; it can never be
  called inside the ingestion transaction.
- Idempotency comes from `UNIQUE(source_type, source_id)` plus the service's
  evidence-identity lookup; no new processed-state table is needed.
- No atomicity is claimed across the source transaction and the incident
  transaction.

Open decisions before implementation: emission policy (recommended: winlog
Critical/Error/Warning + analyzer history, no per-heartbeat incidents), whether
to include the offline USB winlog batch, and the disposable test target.

## 4. Boundaries

- No commit, push, reset, clean, checkout, stash or rebase.
- No operational database, Redis, MinIO, credential or listener access.
- No EIMS backend or Incident Core change; the running Incident Core work was not
  touched.
- Browser Acceptance remains NOT RUN.
