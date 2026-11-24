# EIMS Agent Job Monitor (local, read-only)

`Watch-EimsAgentJobs.ps1` is a **local observer** for the Chat_HAND Control Plane
EIMS agent-job artifact directory. It lets Mew keep one dedicated PowerShell
window open and watch Claude Code / OpenCode agent jobs without asking ChatGPT
for status on every poll.

The user-facing mode is the **persistent dashboard** (`-Dashboard`): it stays open
with zero jobs, refreshes on a fixed poll interval, and exits only when the user
presses **Q**, presses **Esc** from the Overview, hits **Ctrl+C**, or closes the
console window. It never auto-closes on idle and never stops, cancels, or signals
an agent job.


## Scope and safety boundaries

This monitor is deliberately narrow:

- It observes artifacts only. It is **not** a replacement runner and **not** a
  second agent launcher. It never launches, kills, cancels, or restarts agent
  processes and never changes approval policy. Closing or quitting the dashboard
  cannot affect an agent job.
- The interactive dashboard is **persistent**: it stays open with zero jobs and
  exits only on explicit user action (Q, Esc from Overview, Ctrl+C, window close).
  There is no idle auto-close.
- It is **read-only** against job artifacts. It never modifies, deletes,
  truncates, renames, or acknowledges `stdout.log`, `stderr.log`, `exit.json`,
  `runner.json`, `manifest.json`, or `runner.log`.
- It does not touch the EIMS operational database, Redis, MinIO, credentials,
  secrets, or any network listener. It reads only the local artifact directory
  (by default under `%LOCALAPPDATA%`).
- It does **not** and **cannot** send an unsolicited message into the ChatGPT
  conversation. The gateway broker reports results on demand (`jobs.wait` /
  `jobs.get_result`); there is no message injection mechanism. This tool only
  writes to its own console (and, optionally, a best-effort Windows toast).
- No modules or dependencies are installed or required. Windows PowerShell 5.1
  syntax is used throughout.

Artifact root observed (default):

```
%LOCALAPPDATA%\ChatHandControlPlane\artifacts\eims\<jobId>\
```

Expected per-job files: `stdout.log`, `stderr.log`, `exit.json`, `runner.json`,
`manifest.json`, `runner.log`.

## Files

| Path | Purpose |
|---|---|
| `Watch-EimsAgentJobs.ps1` | The monitor: Watch/Once modes and the persistent Dashboard TUI. |
| `Launch-EimsAgentMonitor.ps1` | Windows Trigger C entry point (job-triggered auto-open, explicit `-Open`, single instance, headless fallback, cleanup). |
| `EimsMonitorHost.ps1` | Visible-console host: holds the exclusive lease, writes the ownership record, runs the persistent TUI, cleans up on exit. |
| `README.md` | This document. |
| `tests/Test-WatchEimsAgentJobs.ps1` | Self-contained tests for the watcher, dashboard, persistence, and TUI (no Pester, no modules). |
| `tests/Test-LaunchEimsAgentMonitor.ps1` | Focused tests for open/eligibility, duplicate suppression, headless fallback, ownership, and cleanup. |
| `tests/fixtures/e2e-sample-0001/` | Small synthetic completed-job fixture. |

## Requirements

- Windows PowerShell 5.1 (`powershell.exe`), 64-bit or 32-bit.
- No PowerShell modules, no .NET assemblies beyond the framework, no network.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `-ArtifactRoot <path>` | `%LOCALAPPDATA%\ChatHandControlPlane\artifacts\eims` | Override the artifact directory (used by tests). |
| `-Watch` | off | Continuous plain-text monitoring loop; new job folders are auto-discovered. |
| `-Once` | off | One plain-text scan and exit. Default when neither `-Watch`, `-Once`, nor `-Dashboard` is given. |
| `-Dashboard` | off | Interactive persistent dashboard TUI. |
| `-Persistent` | on for `-Dashboard` | Explicit persistent mode: no idle auto-close. Requires `-Dashboard`. |
| `-Snapshot` | off | Render exactly one dashboard frame and exit `0` (deterministic automation). Requires `-Dashboard`. Selected automatically when stdin is redirected. |
| `-MaxFrames <n>` | `0` (unlimited) | Test/automation hook: stop after `n` frames. |
| `-JobId <id>` | all jobs | Filter to one job folder. Only `[A-Za-z0-9._-]` is accepted. |
| `-PollSeconds <n>` | `5` | Poll interval, validated to `1..3600`. No busy-loop. |
| `-NoBell` | off | Suppress the console bell on terminal transitions. |
| `-NoColor` | off | Plain output (no console color). |
| `-Toast` | off | Opt-in best-effort Windows toast; silently no-ops if unavailable. |
| `-Ascii` | off | ASCII-only dashboard symbols. |
| `-Plain` | off | Force the line-prompt dashboard (no VT, no raw keys). |
| `-NoRun` | off | Internal test hook: define functions but do not start any loop. |

`-Watch` and `-Once` are mutually exclusive. `-Persistent` and `-Snapshot` are
mutually exclusive and both require `-Dashboard`.

## Exact commands

Run from the repository root (`C:\Users\MewMew\Desktop\Co-op\EIMS`). The script
works from any current directory; only the relative path below depends on cwd.

One-shot scan:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Watch-EimsAgentJobs.ps1" -Once
```

Continuous watch in the current terminal:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Watch-EimsAgentJobs.ps1" -Watch -PollSeconds 5
```

Filter one job, plain output, no bell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Watch-EimsAgentJobs.ps1" -Watch -JobId "3ef58a7d" -PollSeconds 5 -NoColor -NoBell
```

Use a synthetic root (tests / rehearsal only):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Watch-EimsAgentJobs.ps1" -Once -ArtifactRoot "$env:TEMP\eims-agent-monitor-tests-example"
```

Persistent dashboard (stays open with zero jobs; `Q` to quit):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Watch-EimsAgentJobs.ps1" -Dashboard
```

Deterministic one-frame snapshot for automation / CI (never blocks on a key):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Watch-EimsAgentJobs.ps1" -Dashboard -Snapshot -NoColor
```

`-Dashboard` also degrades to snapshot mode automatically when stdin is
redirected, so a pipeline, scheduler, or agent runner cannot hang on a prompt.

### Dedicated persistent PowerShell window

Keep a persistent dashboard window open on the desktop with `Start-Process`:

```powershell
Start-Process -FilePath 'powershell.exe' -ArgumentList @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', '"C:\Users\MewMew\Desktop\Co-op\EIMS\scripts\agent-monitor\Watch-EimsAgentJobs.ps1"',
    '-Dashboard',
    '-PollSeconds', '5'
) -WorkingDirectory 'C:\Users\MewMew\Desktop\Co-op\EIMS' -WindowStyle Normal
```

Press **Q** in that window to close it (or close the window). No `-NoExit` is
needed: the dashboard itself is the persistent surface, and there is no idle
close to outlive.

## Output

Each scan prints:

- newly appended stdout/stderr lines, prefixed with `[jobId][stdout]` or
  `[jobId][stderr]`;
- warnings (for example, a malformed `exit.json` or an unreadable folder);
- a status table;

and, on a newly terminal job, a terminal banner with final log paths and a
console bell.

Table columns (watch mode; the dashboard replaces `JobId` with `Task`/`Agent`):

| Column | Meaning |
|---|---|
| `JobId` | Artifact folder name. |
| `Lifecycle` | `RUNNING`, `COMPLETED`, `FAILED`, `TIMED_OUT`, or `UNKNOWN` (dashboard shows `Cancelled` as a derived state). |
| `ExitCode` | Parsed exit code, or `-` when unavailable. |
| `Elapsed` | `hh:mm:ss` from start metadata (or folder creation time). |
| `LastActivity` | Newest artifact/folder write time, local time. |
| `StdoutBytes` / `StderrBytes` | Current log file sizes in bytes. |
| `Pid` | Optional, allowlisted PID metadata, or `-`. |

Display metadata comes from the optional `job.json` written by Chat_HAND at job
start. Only allowlisted fields are read (`taskTitle`, `taskId`, `agentId`,
`agentDisplayName`, `role`, `cwd`, `startedAt`); the prompt, command line,
environment and tokens are never written or displayed. Older job folders without
`job.json` fall back to the runner command and the job id.

Lifecycle rules:

- `RUNNING` â€” job folder exists and no terminal signal is present. A folder
  existing, or a log stopping growing, is **never** treated as completion.
- `COMPLETED` / `FAILED` / `TIMED_OUT` â€” only from a valid `exit.json`: exit code `0` means
  completed, a non-zero code means failed, and failure status words
  (`failed`, `error`, `cancelled`, ...) also mean failed. `timed_out` /
  `timeout` or `timedOut: true` is its own terminal state, not a generic failure. Recognized
  keys are `exitCode`, `exit_code`, `code`, `returnCode`, and `status`/`state`.
  One level of `result` / `exit` / `metadata` / `data` nesting is accepted.
- `TIMED_OUT` — a terminal timeout from `status: timed_out`/`timeout` or
  `timedOut: true`; it is not collapsed into `FAILED`.
- `UNKNOWN` â€” `exit.json` exists but is empty, locked, malformed, or has no
  recognized field. Malformed or partially written JSON is ignored for
  completion and retried on the next poll.
- With no `exit.json`, `runner.json` and `manifest.json` contribute only an
  allowlisted PID and start time. A missing PID is never used to infer
  completion.

Terminal transitions are reported at most once per job **per monitor process
run**. On a terminal transition the monitor emits a console bell (unless
`-NoBell`) and prints the final stdout/stderr paths. With `-Toast`, it also
attempts a Windows toast through built-in WinRT types; this is best-effort and
may be unavailable on a given machine. **The console bell and terminal banner
are the guaranteed fallback.** No module is installed.

## Log tailing

- On first sight of a job, each log stream is anchored at its current length:
  historical content is not replayed, only bytes appended afterwards are
  shown.
- Truncation or file replacement resets the stream to the beginning of the new
  content, so stale bytes are not repeated.
- An incomplete final line is held until its newline arrives (or until the job
  becomes terminal, when the remaining bytes are flushed).
- Locked or partially written files are retried on the next poll; they never
  crash the watcher.

## Robustness

The watcher re-enumerates the artifact directory every poll, so newly created
job folders are discovered automatically and a gateway or monitor restart does
not break it. Missing roots, permission errors, malformed JSON, and per-job
scan failures are reported as warnings and skipped for that cycle. Polling is
bounded by `-PollSeconds`; there is no busy-loop.

## Limitations

- Local only: **no unsolicited messages can be sent into the ChatGPT
  conversation.** Check this window for job status.
- Tail state is in-memory and per process run. After a monitor restart, logs
  are re-anchored at their current length, so appends that occurred while the
  monitor was stopped are not shown. Terminal alerts are likewise emitted once
  per process run.
- First-sight anchoring means content already in a log when the monitor first
  sees a job is not displayed. Start the monitor before launching jobs if you
  want to see their full output.
- Toast notifications depend on the local Windows notification runtime and an
  AppUserModelID; they are best-effort and often silently suppressed. The
  console bell/terminal banner is the supported notification path.
- A job whose `exit.json` is malformed stays `UNKNOWN` until the file is fixed
  or replaced by a valid one. This is intentional: no completion is inferred
  from folder existence, log growth, or a missing PID.
- Only a small allowlist of metadata (`pid`, start time) is read from
  `runner.json` / `manifest.json`. Command lines, prompts, environment values,
  and tokens are never displayed.
- Byte-level tails decode as UTF-8; a multi-byte sequence split across a poll
  boundary is held with the incomplete line until more bytes arrive.
- Persistence is implemented for the EIMS-side launcher and TUI described here.
  A window launched by Chat_HAND's own Trigger C manager is controlled by that
  separate manager (outside this repository); this change neither configures nor
  disables it. Use the EIMS launcher (`-Open`) for the persistent user-facing
  dashboard.
- Interactive raw-key handling, the alternate screen buffer, and visible-window
  appearance cannot be validated from an automated runner. Automated coverage
  proves mode decisions, frames, counts, persistence, and cleanup; a human must
  confirm the real console experience.

## Tests

No Pester or modules are required. The test script creates disposable synthetic
directories under `%TEMP%` and removes only its own directory. It covers
running -> completed and failed transitions with several exit-code field names,
incremental tailing with truncation/replacement/partial lines, malformed and
missing `exit.json`, secret non-disclosure, missing root, `-JobId` filtering,
and the synthetic fixture.

From the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\tests\Test-WatchEimsAgentJobs.ps1"
```

Exit code `0` means all assertions passed; `1` means at least one failed; `2`
means the monitor script could not be loaded.

---

## Interactive dashboard (`-Dashboard`)

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Watch-EimsAgentJobs.ps1" -Dashboard
# explicit persistent mode (identical to the default)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Watch-EimsAgentJobs.ps1" -Dashboard -Persistent
# one deterministic frame, then exit (automation; also used for redirected stdin)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Watch-EimsAgentJobs.ps1" -Dashboard -Snapshot
# force plain output / line prompt (interactive terminals stay persistent)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Watch-EimsAgentJobs.ps1" -Dashboard -Plain
# ASCII-only symbols
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Watch-EimsAgentJobs.ps1" -Dashboard -Ascii
```

| Key | Action |
|---|---|
| `O` | Overview (all jobs) |
| `A` | Active (Running, Pending, Unknown) |
| `H` | History (Completed, Failed, Cancelled, TimedOut; newest first) |
| `L` | Logs for the selected job (sanitized, bounded) |
| `F` | Final Result for the selected job (stdout tail) |
| `E` | Errors for the selected job (stderr tail) |
| `T` | Artifacts for the selected job (bounded listing) |
| `I` | Info / lifecycle metadata for the selected job |
| `J` / `K`, Up / Down | next / previous job |
| `R` | refresh now |
| `Q` / `Esc` | quit (`Esc` returns to Overview first when a detail view is open) |

The frame is redrawn in place (alternate screen buffer, cursor hidden) and the
terminal is restored on every exit path -- normal quit, `Esc`, Ctrl+C, or an
exception. Restoration failures are swallowed so they can never hide the original
error. Terminals without VT or raw-key support fall back to a line prompt and a
plain table (`-Plain` forces it).

### Lifecycle contract (persistent)

The dashboard is a **user-facing persistent surface**, not a transient window
tied to one job:

| Event | Result |
|---|---|
| Zero jobs at start | Dashboard renders `IDLE` with `Total 0` and waits. It does **not** exit. |
| All jobs become terminal | Dashboard renders `IDLE ... all terminal` and stays open. |
| Artifact root missing | Dashboard renders `IDLE ... (root MISSING)` and keeps polling. |
| `Q` (or `Esc` from Overview) | Explicit user quit. The window closes. |
| Ctrl+C / window close | Process exits; the OS releases the lease. A state record may remain after a hard window close; the launcher reclaims it automatically once it proves the recorded PID is not live and re-validates the record's nonce. |
| Agent job finishes or fails | Row and counts update on the next refresh; the window remains open. |
| Closing/quitting the dashboard | **No agent job is stopped, cancelled, or signalled.** The monitor is read-only and has no job-control code path. |

There is no idle timer, no "close after N seconds" option, and no automatic
dashboard restart after idle. Reopening is explicit (`-Open`, or `-Dashboard`
directly); a separately running `-Watch` launcher still treats a live job as a
launch trigger, exactly as before. `-Snapshot` is the only mode that exits by
itself, and it is chosen only when requested or when stdin is redirected.

### State model

| State | Meaning |
|---|---|
| `Pending` | exit.json reports queued/pending/waiting/started |
| `Running` | no exit.json yet **and** `runner.json` reports a pid (a bare folder or a stalled log is never completion) |
| `Completed` | exit code 0 (or a success status token) |
| `Failed` | non-zero exit code or a failure status token |
| `Cancelled` | status token cancelled/canceled/aborted/killed |
| `TimedOut` | `status` token `timed_out`/`timeout` or `timedOut: true` (terminal, not a generic failure) |
| `Unknown` | exit.json present but unreadable/malformed/unrecognised, or no exit.json and no runner pid. The dashboard shows an actionable `why unknown:` reason (missing exit metadata, malformed JSON, no recognized status, or no runner pid) instead of only `?`. |

Elapsed time freezes at the last observed activity once a job is terminal
(`EndUtc`), so a finished job never keeps counting. Hours are floored.

### Logs and limits

- Logs render only in the Logs view, prefixed with `|`, ANSI/control sequences
  stripped, secret-shaped tokens masked, truncated to the last 16 KiB and 16 lines
  with an explicit `[log truncated ...]` marker.
- File rotation/replacement is detected by file identity in the tail reader, so a
  rotated log does not replay history.
- exit.json is read with a bounded reader and parsed defensively; a malformed or
  locked file yields `Unknown` plus a warning instead of a crash.
- `-SinceUtc` (used by the dashboard) suppresses alerts for jobs that finished
  before the observer started; a job that finishes while watching always alerts.

### Tests

The self-contained suite covers 169 assertions on Windows PowerShell 5.1,
including state mapping, `job.json` task/agent metadata, actionable Unknown
reasons, Final Result/Errors/Artifacts/Info views, real `runnerPid`/`agentPid`
metadata, frozen elapsed time, historical-vs-new alerts, missing artifacts,
malformed/oversized JSON, large Int64 exit codes, log truncation, ANSI/secret
sanitisation and log-line prefixing.

Lifecycle coverage added with persistent mode:

- interactive mode resolution defaults to persistent; redirected stdin becomes a
  deterministic snapshot (with an explicit degradation reason);
- a zero-job persistent session renders five frames and **never** exits on
  idleness (bounded only by the test-only `-MaxFrames`);
- explicit `Q` is reported as the exit reason; `Esc` returns to Overview first and
  quits only from Overview;
- a one-row dashboard renders/selects its only job; a no-job dashboard states
  `IDLE`, `Total 0`, and `mode=persistent`; a missing root says `root MISSING`;
- a dummy "agent" process recorded in `runner.json` is still alive after the
  dashboard session quits, and the monitor source has no `Stop-Process`,
  `taskkill`, or tree-kill path.

---

## Windows Trigger C auto-launch

`Launch-EimsAgentMonitor.ps1` is the **EIMS-side** integration. It opens the
Dashboard TUI in a **visible console on the Windows desktop** either when an
eligible EIMS agent job starts or on explicit `-Open`. The launched dashboard is
persistent: it outlives the job that triggered it and stays open with zero jobs.

```
Launch-EimsAgentMonitor.ps1  (-Once | -Watch | -Open)
  -> scan artifacts (reusing Watch-EimsAgentJobs.ps1 functions)
  -> eligibility check (-Open skips it) -> single-instance check
  -> powershell.exe -WindowStyle Normal  EimsMonitorHost.ps1
       -> exclusive monitor.lease + identity record (mode=persistent, idleClose=false)
       -> Watch-EimsAgentJobs.ps1 -Dashboard -Persistent
```

The Chat_HAND gateway has its own, separate Trigger C manager and wrapper; it
launches the same TUI unmodified. The EIMS launcher described here is the
standalone EIMS-side path (for example, started at logon or on demand). The two
paths use different state directories, so a Chat_HAND-owned window is not
mistaken for an EIMS-owned one.

### Setup

No installation, modules, or dependencies. Use Windows PowerShell 5.1
(`powershell.exe`), not PowerShell 7, and keep the three scripts in the same
directory (or pass explicit `-MonitorScript` / `-HostScript` paths).

Open the persistent dashboard now, with zero jobs, and return immediately:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Launch-EimsAgentMonitor.ps1" -Open
```

Check that decision without opening a window:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Launch-EimsAgentMonitor.ps1" -Open -DryRun
```

Evaluate once and open when a live job exists (the window then persists):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Launch-EimsAgentMonitor.ps1" -Once
```

Keep evaluating (an already-open owned window suppresses further launches):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Launch-EimsAgentMonitor.ps1" -Watch -PollSeconds 2
```

Open modes are mutually exclusive: `-Open` cannot be combined with
`-Once`/`-Watch`, `-Diagnose`, or `-Cleanup`.

Restrict launches to particular agents. The launcher prefers explicit
`agent`/`agentId`/`agent_id`/`agentName`/`provider` keys in `manifest.json` or
`runner.json`, then falls back to the real runner `command` executable basename
(`claude.exe` -> `claude_code`, `opencode.exe` -> `opencode`):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Launch-EimsAgentMonitor.ps1" -Once -AllowedAgents @('claude_code','opencode')
```

Diagnose why a window did or did not open (no process, no claim):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Launch-EimsAgentMonitor.ps1" -Diagnose
```

The diagnosis prints artifact root existence, scanned/pending/running/completed/
failed/unknown counts, eligible job ids, the agent allowlist, interactive/headless
session state, duplicate-window state, the persistent mode, warnings, and one
explicit decision. It distinguishes `artifact root unavailable`,
`no eligible running job (...)`, `eligible job found; would launch`,
`duplicate window suppressed`, and `headless fallback: ...`.

Clean up a stale owned window/state after a crash or forced logoff:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\Launch-EimsAgentMonitor.ps1" -Cleanup
```

State location (default `%LOCALAPPDATA%\EimsAgentMonitor`, override with
`-StateDirectory`):

- `monitor.lease` -- held with `FileShare.None` while the TUI runs; proof of a live owner.
- `monitor.json` -- nonce-bound identity record (`pid`, `startedAt`, `nonce`,
  `mode`, `idleClose`, `owner`). A process is only ever stopped when a live owner
  holds `monitor.lease` **and** the PID, the exact process start time, a non-empty
  claim nonce, and the CIM command line all match this record. A free lease,
  missing CIM output, a blank `startedAt`, a missing nonce, a recycled PID, or a
  tampered record is treated as **not owned** and no signal is sent. A stale
  record (dead PID, or a `pid=0` claim older than 30 s) is reclaimed automatically
  only after its nonce is re-validated and its PID is proven not live; a record
  replaced by a faster launcher is never removed.

### Behavior and safety

- **Eligibility.** In `-Once`/`-Watch`, a window opens only for a job folder whose
  state is `Running` or `Pending`, that is not terminal, and whose job id is safe
  (`[A-Za-z0-9._-]`, no `.`/`..` traversal). A bare folder or a log that stopped
  growing is never a launch trigger; only runner metadata (PID) or a
  queued/started status qualifies. `-Open` deliberately skips eligibility and
  root existence: the dashboard can be opened before the first job exists and
  will render `root MISSING` until artifacts appear.
- **Persistent lifecycle.** Once opened, the dashboard is never closed by the
  launcher. There is no idle timer and no auto-close in this scope. The host
  records `mode=persistent` and `idleClose=false`; closing the window remains a
  user action (Q, Esc from Overview, Ctrl+C, window close).
- **Agent independence.** The monitor never launches, signals, cancels, or stops
  an agent job. The host and TUI have no job-control code path. Cleanup signal
  arguments are exactly `/PID <pid>` (graceful) or `/PID <pid> /F` (forced), and
  **never** `/T`; a runner tree cannot be reached even through a corrupted state
  record, because ownership fails closed. A free lease, a non-monitor command
  line, an empty or unavailable CIM command line, a blank `startedAt`, a missing
  nonce, or a recycled PID all refuse the signal and leave the PID untouched.
- **Partial metadata.** A partially written or unreadable JSON file is ignored
  for that scan. `-Watch` retries on the next poll; `-Once` may need a re-run if
  it catches the first half of a write.
- **Idempotent / no duplicate windows.** The lease plus an atomic `monitor.json`
  creation give a single winner. A second launcher, a held lease, or an existing
  TUI process simply reports `duplicate window suppressed`. A provisional claim
  older than 30 seconds, or a record whose PID is dead or recycled, is reclaimed
  and the claim retried; reclamation re-reads the record and only removes it when
  the nonce is unchanged, so it can never delete a claim a faster launcher just
  wrote. A hard window close therefore cannot block future launches.
- **No focus stealing.** The console is created with `Start-Process -WindowStyle
  Normal`. There is no `SetForegroundWindow`, `AppActivate`, or forced-foreground
  call. Windows may still give a newly created console focus; the launcher never
  forces it.
- **Headless fallback.** Non-interactive sessions, service sessions, and
  redirected I/O in a non-console host are detected **before** any process is
  spawned. The launcher prints a `headless fallback:` reason, starts no window,
  waits for no keyboard input, and exits (or stops a `-Watch` loop) promptly.
  A console host such as `ConsoleHost` is allowed to open a window even when its
  own I/O is redirected (IDE terminals).
- **Cleanup.** The host releases its lease in `finally` and removes only its own
  record (same PID and nonce). `-Cleanup` (and the launcher's own failure path)
  stops only an owned process, by exact PID, after a held lease AND PID + start
  time + nonce + CIM command line all match. Incomplete evidence (free lease,
  empty CIM line, blank start time, missing nonce, recycled PID, tampered record)
  clears the state record but sends no signal, and the CLI reports
  `no verified owned monitor (...); no signal sent`. Unrelated PowerShell and
  agent processes are never touched.
- Existing behavior is preserved: the TUI still restores the terminal on every
  exit path, and `-Watch` / `-Once` plain-text monitoring are unchanged.

### Troubleshooting

| Symptom | Check |
|---|---|
| `headless fallback: ...` and no window | A visible console requires an interactive desktop. Check `[Environment]::UserInteractive`, `$env:SESSIONNAME`, and that the host is `ConsoleHost`/ISE, not an embedded or service host. Running under a scheduler/service or redirected SSH session is expected to fall back, not hang. |
| `no eligible running job` | The job is terminal, has no live runner PID/status, or is filtered out by `-AllowedAgents`. The message includes `scanned/pending/running/terminal/unknown` counts; run `-Diagnose` for the full breakdown. Use `-Open` if you want the dashboard without a live job. |
| `artifact root unavailable` | In `-Once`/`-Watch`, the root does not exist and no window is opened. Check `-ArtifactRoot` and that the gateway has written job folders. `-Open` ignores this and shows `root MISSING` in the dashboard. |
| `no eligible running job (scanned=..., pending=0, running=0, terminal=..., unknown=0)` | The scan worked but every job is terminal. This is normal; the persistent dashboard (if already open) simply shows `IDLE ... all terminal`. If `unknown` is non-zero, inspect that job's `runner.json`/`exit.json`. |
| `eligible job found; would launch` | `-Diagnose` found a live job. Re-run without `-Diagnose` (or with `-Watch`) to open the window. |
| `duplicate window suppressed` | Another owned window is open, the lease is held, an existing `-Dashboard` process was detected, or a fresh state claim exists. Only one dashboard exists at a time by design. A stale claim left by a crash or hard window close is reclaimed automatically; `-Cleanup` forces the state record removal and stops a provably owned host. |
| `launch failed: ...` | Verify `-MonitorScript`/`-HostScript` paths and ExecutionPolicy. A failed launch removes its own claim so the next attempt is not blocked. |
| Window opens but shows no jobs | Expected with `-Open`. The dashboard renders `IDLE` and waits; it does not close. Check `-ArtifactRoot` if jobs exist elsewhere. |
| Dashboard stays open after jobs finish | **By design.** Persistent mode has no idle close; press **Q** (or close the window). This is not a stuck process. |
| Dashboard disappeared / window closed | The user (or the console session) closed it, or the process crashed. Start it again with `-Open`. An already-finished job is shown historically; live tailing only covers new appends. |
| `mode=snapshot (...)` instead of a dashboard | stdin is redirected, so the run rendered one frame and exited. Use a real interactive console for persistence, or `-Snapshot` deliberately in automation. |
| Closing the dashboard cancelled an agent job? | It cannot. The monitor has no job-control path; `grep` the scripts for `Stop-Process`/`taskkill` (none in the TUI/host). Check the gateway/runner logs for the real cause. |
| Paths with spaces | Argument quoting is handled by `Format-EimsAutoLaunchArgument`; pass paths normally, without manual extra quotes. |

### Tests and verification boundary

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\agent-monitor\tests\Test-LaunchEimsAgentMonitor.ps1"
```

Verification boundary: the watcher suite is **169 passed, 0 failed** on Windows
PowerShell 5.1. The launcher suite's assertion count grew with the stale-claim
and fail-closed ownership coverage below, so record the `Results:` line from the
verifier's run instead of reusing an older number; any failure exits 1. Tests
inject session, process, spawn, stale-record process identity, key, and frame
data and use disposable `%TEMP%` directories; they never spawn a visible console
and never signal an agent process. The agent-survival test starts one disposable
dummy process it owns and kills it in `finally`.

Coverage includes zero-job `-Open`, missing-root `-Open`, headless `-Open`,
spawn-argument/mode-record checks, single-instance suppression, exact-PID stop
arguments with no `/T`, refusal to stop a non-monitor command line, host
lease/nonce ownership cleanup, stale-claim reclamation (dead PID, stale `pid=0`
claim, recycled PID, concurrently replaced record, nonce mismatch), and
fail-closed ownership for a free lease, empty/blank command line, blank
`startedAt`, missing nonce, unreadable process start time, and a tampered record —
with zero stop calls in every ambiguous case.

**Visible-window limitation:** the tests and `-DryRun` prove mode, eligibility,
duplicate suppression, headless fallback, spawn arguments, and cleanup
decisions, but they do **not** prove that a GUI window actually appeared on the
desktop or that raw keys work in a real console. From an agent runner,
interactive keyboard acceptance and visual confirmation are **NOT VERIFIED** and
must be checked by a human at the Windows desktop.



