# EIMS V12 â€” Final Engineering Closeout Report

Date: 2026-11-18 (Asia/Bangkok)
Repository: `C:/Users/MewMew/Desktop/Co-op/Chat_HAND`
Branch: `v2/verified-fallback`
HEAD: `c293b8aae2cbf2a669ba1cb4210001efe1f14885`

## A. Executive Summary

### Final campaign gate status

| Gate | Status | Reason |
|---|---|---|
| Gate 1 â€” Stabilize & Freeze | **BLOCKED** | 5-minute CPU avg 33%, max 88% (threshold <30%); free RAM 5.4-7.6 GB; tunnel/gateway stopped at 18:28:24; runtime unavailable |
| Gate 2 â€” Integration Closure | **BLOCKED** | Gate 1 prerequisite not met; no full relay/harness run was forced |
| Gate 3 â€” Security & Monitor | **IN PROGRESS** | Trust tests 30/30; Claude Code final review not run; GUI/raw-key not performed |
| Gate 4 â€” Live MCP E2E | **NOT RUN** | no owner ChatGPT MCP invocation; live stdio not addressable from this shell |
| Gate 5 â€” Final Evidence | **PARTIAL** | evidence index/provenance updated; relay evidence not authoritative |

Gate 1 evidence: `evidence/final-campaign-gate1.json`, `evidence/final-campaign-post-restart-preflight.json`.

The Trust Grant hardening and Persistent Monitor work are implemented and pass
their deterministic suites in disposable copies:

- Trust Grant: **30/30**
- Persistent Monitor watcher: **169/169**
- Persistent Monitor launcher: **171/171**
- Control plane: **40/40** (1 not tested)
- Approval lifecycle: **18/18**
- Agent availability: **21/21**
- Orchestration: **22/22**
- ALAP: **43/43**

The **full repository harness and Job Relay are not accepted**. The relay suite
produced a sensitive-output status assertion mismatch and repeated RPC
timeouts while the host was at ~80â€“100% CPU with ~338â€“600 MB free RAM and 37
Node processes from other applications. A minimal control-plane `initialize`
succeeds in isolation, so this is not a startup failure; the relay result is
**BLOCKED**, not PASS and not proven FAIL.

At 18:24 local the runtime was the reconciled code:

- tunnel-client PID **80916**
- gateway PID **79260** (child)
- `healthz` HTTP **200**, `readyz` HTTP **200** (two endpoint responses, not a
  count of 200 checks)
- 18 tools; `agent.run` exposes `trust_grant_id`; no Trust Grant MCP tool

During the 5-minute preflight the tunnel logged a graceful
`OnStop`/`context canceled` shutdown at **18:28:24**. No tunnel-client,
control-plane process, or `health.url` remains. **Runtime is currently FAIL /
unavailable**; this is a preflight result, not a restart authorization.

No commit, push, merge, or deployment was performed.

## B. Verified Repository Baseline

| Item | Value |
|---|---|
| Branch / HEAD | `v2/verified-fallback` / `c293b8aaâ€¦` |
| Modified / untracked | 20 / 57 |
| `git diff --check` | 0 |
| Runtime | 1 tunnel + 1 gateway; no monitor process |
| Host at baseline | CPU 100%, free RAM 338 MB, 37 Node processes |
| Host during relay | CPU ~80â€“100%, free RAM ~517â€“600 MB, 37 Node processes |

The main worktree contains pre-existing changes plus this task's changes. The
hardening job's in-scope files and the reconciliation fixes coexist. No reset,
clean, checkout, stash, commit, push, or service kill was performed.

## C. Job Outcomes

| Job | Project | Status | Result |
|---|---|---|---|
| `851b2f2a-5a4d-4a1c-8451-e14bdb5a5846` | chat_hand | **failed, exit 1** | 907 s, `SCOPE_VIOLATION:11`, result `d232dadcâ€¦` (unretrieved) |
| `7252af89-0c77-4f02-8fbb-ce43a2c5918c` | eims | **timed_out, exit 1** | 900 s, partial changes |
| `14537505-1de5-4add-a9af-7f5a46ca1e78` | eims | **timed_out, exit 1** | 905 s, partial changes, result `c9915c66â€¦` |

The Chat_HAND job's scope violations included `README.md`,
`gateway/test-fixtures/stub-agent.mjs`, and several `evidence/*.json` files.
These were caused by concurrent test/evidence writes during its run. The job's
in-scope code is present and was reconciled, but its own result is failed and is
not used as acceptance evidence.

## D. Root Cause Analysis

### D1. Trust Grant job failure â€” resolved as coordination failure

Concurrent out-of-scope modifications during the job caused its scope
verification to fail. This was not a path-escape bypass. The paired hardening
changes (routing/agent fingerprints, read-only grant disable, audit-before-use,
lock ownership) are present. A test-context bug (`setupClientContext` lacked
`agentsFile`/`routingFile`) and an mtime-resolution-sensitive lock test parameter
were corrected in the disposable copy; Trust Grant then passed 30/30.

### D2. Relay `sensitive_output_withheld` â€” focused probe passes; full-suite result BLOCKED

The implementation inspects both streams after the runner exits and forces
`failed` when `artifacts.sensitive` is true (`control-plane.mjs` finalize path,
`job-store.mjs inspectArtifacts`). A focused single-job probe in a disposable
copy produced:

```
status=failed, withheld=true, sensitiveOutput=true,
error=SENSITIVE_OUTPUT_DETECTED, stdoutBytes=44
```

So the security path is correct in isolation. The full-suite `completed`
assertion occurred in a loaded run and was not reproduced. The assertion and
detector were not weakened. **Status: BLOCKED pending a quiet-host full-suite
sequence rerun.**

### D3. Relay RPC timeouts â€” host resource contention, not proven regression

A minimal control-plane `initialize` succeeded in isolation (18 tools, correct
schemas). The failures occurred only while CPU/RAM were saturated. Timeout
thresholds were not raised and retries were not added, because that could mask a
real duplicate-execution bug. **Status: BLOCKED pending a quiet-host run.**

## E. Changes Implemented

### Trust Grant

- Local-only CLI (`gateway/trust-grant.mjs`), no MCP creation tool.
- Interactive TTY + typed `TRUST`; non-interactive `--yes` refused.
- HMAC-signed, expiring, revocable grants bound to project/workspace, branch,
  HEAD, agent, role, scope, operation, policy version, agent fingerprint,
  routing fingerprint, expiry, uses and timeout.
- Read-only grants disabled; manual read-only runs remain on approval.
- Every-segment and every-changed-path hard-deny, including nested agent
  instruction/config surfaces and the state directory.
- Audit-before-authority for creation/use; revocation audited; owner-token locks.
- Bearer-id minimization (`trustGrantRef`), revocation of new uses immediately.
- Independent review: **ACCEPT (conditional)**; conditions addressed, residual
  limitations documented.

### Persistent Monitor

- Persistent interactive dashboard (no idle auto-close), explicit `-Snapshot`
  and headless/Once behavior.
- Task/agent display, Final Result/Errors/Artifacts/Info views, TimedOut state,
  actionable Unknown reason, bounded log/artifact reads.
- 169/169 watcher and 171/171 launcher tests in a disposable copy.
- Single-job `-Dashboard -Snapshot` rendered `Persistent Job / OpenCode /
  Completed`; `-Plain` + `q` exited 0.
- GUI/raw-key and long-running agent survival remain untested.

### Runtime / evidence

- Gateway/tunnel restarted onto the reconciled code; health endpoints 200.
- `evidence/trust-grant-acceptance.json` now carries the validated **30/30**
  temp-copy result.
- `evidence/trust-grant-review.json` records the conditional security review.
- `evidence/monitor-persistent-acceptance.json` records 169/171 and the snapshot.
- `evidence/reconciliation-2026-11-18.json` records job outcomes, contamination,
  host load and runtime state.

## F. Security Review

Verdict: **ACCEPT (conditional)** with these residuals:

1. HMAC and TTY are human-authorization controls, **not OS boundaries**; the
   same Windows user can read the key or allocate a console.
2. Scope/hard-deny is **post-hoc detection**, not a sandbox; forbidden writes
   are not reverted and writes outside the workspace are not observed.
3. Revocation blocks new uses immediately but does not terminate a running job.
4. `scripts/agent-monitor` is deliberately **not grantable** as writer scope.
   Trust Grant cannot be used for the monitor work under its current policy.
5. Writer `cwd` is not constrained to the granted scope; write authority is
   still bound by the declared scope.

## G. Regression Results

| Suite | Result |
|---|---|
| Control plane | 40 passed, 0 failed, 1 not tested |
| Approval lifecycle | 18/18 |
| Agent availability | 21/21 |
| Orchestration | 22/22 |
| Trust Grant | 30/30 (disposable copy) |
| Monitor watcher | 169/169 (disposable copy) |
| Monitor launcher | 171/171 (disposable copy) |
| ALAP | 43/43 |
| Job Relay | **BLOCKED** â€” 22â€“28/31 with status assertion/RPC timeouts under load |
| Full repository harness | **BLOCKED** at relay |

## H. Relay E2E Results

- Basic control-plane startup, tool surface and state handling were repeatedly
  exercised.
- The relay suite passed 31/31 earlier in the session, before the hardening
  changes, and its evidence is preserved.
- The current tree's relay result is not green. The sensitive-output contract
  remains fail-closed in source; the failed assertion needs a quiet-host
  reproduction before any code change.
- No live ChatGPT MCP E2E was performed.

## I. Monitor Acceptance

- Deterministic tests pass in a disposable copy.
- A real `-Dashboard -Snapshot` and `-Plain` run displayed the selected job and
  exited 0 on `q`.
- **BLOCKED:** visual TUI/raw-key acceptance, long-running agent survival after
  closing the monitor, and live window behavior were not observed on a desktop.

## J. Live MCP Acceptance

**NOT RUN.** The runtime advertises 18 tools and the grant argument, but no real
ChatGPT MCP conversation was used to submit, approve, execute, retrieve and
acknowledge a job after the final changes.

## K. Evidence Index

- `evidence/trust-grant-acceptance.json` â€” 30/30, observed 2026-11-18T10:14:02Z
- `evidence/trust-grant-review.json` â€” independent conditional ACCEPT
- `evidence/monitor-persistent-acceptance.json` â€” 169/171 + snapshot evidence
- `evidence/reconciliation-2026-11-18.json` â€” baseline, job outcomes, host load
- `evidence/relay-sensitive-probe.json` â€” focused sensitive-output probe: failed/withheld
- `evidence/v6-job-relay-acceptance.json` â€” **not green; current run**
- Disposable copies: `%TEMP%/chat-hand-finalcheck-*`, `%TEMP%/eims-monitor-check-*`

## L. Remaining Risks

1. Host resource saturation prevents a defensible relay/harness result.
2. The relay sensitive-output assertion mismatch is not root-caused.
3. No GUI/raw-key or agent-survival acceptance.
4. No live ChatGPT MCP E2E.
5. Trust Grant cannot cover `scripts/agent-monitor`; a separate approved
   execution mechanism is required if that routine work must be automated.
6. Main evidence for relay is not authoritative; regenerate on a quiet host.
7. The working tree contains mixed pre-existing/hardening/reconciliation work
   and is uncommitted.

## M. Final Acceptance Matrix

| Subsystem | Result | Evidence | Remaining Risks |
|---|---|---|---|
| Source / scope integrity | **PARTIAL / RECONCILIATION REQUIRED** | branch/HEAD/status/diff check 0 | `git diff --check` is formatting only; 20 modified + 59 untracked files lack complete per-file ownership |
| Trust Grant | **PASS (technical)** | 30/30 temp copy; conditional review | HMAC/TTY not OS boundary; no scripts/agent-monitor |
| Trust Grant security review | **PENDING** | prior conditional ACCEPT | final Claude Code review not run |
| Persistent Monitor | **PASS (deterministic)** | watcher 169/169 + launcher 171/171 (separate suites); snapshot | GUI/raw-key/survival **BLOCKED** |
| Control Plane | **PASS** | 40/40 | 1 not tested |
| Approval / Availability / Orchestration / ALAP | **PASS** | 18/18, 21/21, 22/22, 43/43 | â€” |
| Job Relay | **BLOCKED** | 22â€“28/31, status/RPC failures under load; focused sensitive probe passed | needs quiet-host full-suite rerun |
| Full Harness | **BLOCKED** | fails at relay | â€” |
| Runtime consistency | **FAIL** | PIDs 80916/79260 at 18:24; stopped 18:28:24; no health file | runtime unavailable; needs supervised restart |
| Evidence integrity | **PARTIAL** | Trust/monitor evidence regenerated; relay evidence not authoritative | regenerate relay evidence |
| Live MCP E2E | **NOT RUN** | â€” | needs owner ChatGPT session |

**Overall:** Level 1 (Core Engineering) **PASS**; Level 2 (Integration
Acceptance) **BLOCKED**; Level 3 (Operational Acceptance) **BLOCKED**. EIMS is
not claimed fully complete.

## N. Recommended Next EIMS Development Phase

1. Run the relay suite and full harness in a disposable copy on a quiet host
   (close heavy Node/electron applications; target CPU <30%, free RAM >2 GB).
2. If `sensitive_output_withheld` still returns `completed`, instrument the
   finalize/collect path with job id and artifact hashes; do not weaken the
   detector or assertion.
3. Obtain a fresh Claude Code independent read-only review of the final Trust
   Grant diff after the M1 hard-deny additions.
4. Perform GUI/raw-key and long-running agent survival acceptance on a desktop.
5. Perform live ChatGPT MCP E2E: submit, local approve, execute, `jobs.wait`,
   `jobs.get_result`, `jobs.ack_result`, verify one job/process and audit.
6. Decide separately whether routine `scripts/agent-monitor` work should have a
   dedicated approval mechanism; do not weaken the Trust Grant deny policy.

## O. Presentation-ready Factual Claims

- â€œTrust Grant is a local-only, HMAC-bound, expiring authorization record; its
  deterministic suite passes 30/30 in a disposable copy.â€
- â€œRead-only grants and the EIMS monitor scope are deliberately denied; the
  feature is for ordinary workspace code, not control-plane code.â€
- â€œThe Persistent Monitor passes 169 watcher and 171 launcher tests; its
  interactive GUI/raw-key acceptance is not yet proven.â€
- â€œRuntime advertises the grant argument and 18 tools, but no live ChatGPT MCP
  E2E has been performed.â€
- â€œJob Relay is currently blocked by host-load-related RPC timeouts and one
  sensitive-output assertion that must be reproduced on a quiet host; it is not
  claimed as passing.â€

