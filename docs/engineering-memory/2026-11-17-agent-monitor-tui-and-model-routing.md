# EIMS Engineering Memory — 2026-11-17 Model Routing + Agent Monitor TUI

## Scope

Two file groups, one writer, no overlap:

- **Group A (Chat_HAND)**: OpenCode model routing, fail-closed against drift.
- **Group B (EIMS)**: `scripts/agent-monitor/` interactive TUI on the existing data layer.

No commit, push or deploy. No operational DB/Redis/MinIO/credential access.

## Group A — root cause and fix

`gateway/agents.json` pinned no model for the OpenCode **writer** mode, so the CLI
used its own default. Job `2656de34-…` ran `qwen/qwen4-max` (131072 output) via
OpenRouter and failed on credits; that model is not in this host's catalog
(543 models from `opencode models`). Read-only mode had been pinned earlier.

`gateway/model-routing.json` is now the single source of truth (`schemaVersion`,
`policyVersion`, `allowedModels`, per-agent/role model + `modelSource`, `timeoutSec`,
fallbacks, and `enforcement.outputTokenCap: unsupported`). `gateway/lib/routing.mjs`
reads the model **out of the argv the runner will execute**, compares it to the
manifest, rejects duplicate/injected model flags, and the gateway refuses with
`MODEL_CONFIG_INVALID`, `MODEL_ROUTING_MISMATCH` or `MODEL_NOT_ALLOWED` **before**
any approval exists. Prompts that start with a CLI flag are rejected.

Token budget is stated honestly: `opencode run` 2.3.0 has no output-token flag, so
no output cap is claimed and `timeoutSec` is never presented as one.

Verification: preflight 17 checks PASS (no LLM call); **live smoke PASS** for both
roles (one minimal prompt each, no retry); `scripts/test-agent-routing.mjs` 17/17;
orchestration 22/22; job-relay 25/25; control plane 40 pass + 1 not tested.
Independent review: round 1 NOT ACCEPTED (prompt-injected `--model`; BOM/flat
preflight unreadable) → fixed → round 2 **ACCEPTED**.

## Group B — monitor TUI

`Watch-EimsAgentJobs.ps1` gained `-Dashboard` (O/A/H/L/R/Q, J/K and arrows, `Esc`),
alternate-buffer redraw, VT + plain fallback, and terminal restoration on every
exit path with restore failures swallowed so they cannot hide the original error.
The data layer is preserved and corrected where it was wrong:

- `State` is explicit: `Pending`, `Running` (only with a runner pid), `Completed`,
  `Failed`, `Cancelled`, `Unknown`. A bare folder is never "Running".
- Elapsed freezes at `EndUtc` once terminal; hours are floored (`1h40m -> 01:40:00`).
- Historical terminal jobs do not alert on first sight (`-SinceUtc` watermark);
  real transitions alert once.
- Logs: Logs view only, prefixed, ANSI/C0/C1 stripped, secrets masked (sk/gh/AKIA/
  xox/JWT/Bearer/key=value/PEM header), 16 KiB + 16 lines with an explicit
  truncation marker, bounded 64 KiB reads, rotation detection.
- Frames clamp to the window (`height-1`, `width-1`) with a hidden-lines marker;
  a >64 KiB line without a newline flushes instead of stalling the tail.
- Exit codes are parsed as Int64.

Verification: **96 assertions pass on Windows PowerShell 5.1** (~4 s, exit 0);
`-Dashboard -Plain` renders the real root (16 jobs: 9 completed, 7 failed) and an
empty root (`Total 0`) and exits; `git diff --check` exit 0.
Independent review: round 1 NOT ACCEPTED (empty-collection crash, rounded hours,
bare-folder Running, unbounded tail, control chars, masking, frame height) →
fixed → round 2 NOT ACCEPTED (tail stall, test that could not fail) → fixed →
round 3 **ACCEPTED**.

## Known limitations

- PEM body masking is header-only; base64 body lines can still appear in the Logs
  view.
- Classic `-Watch` prints one squashed line per poll chunk (bounded, ellipsised).
- A full-window flush can split a multibyte UTF-8 character at the edge (cosmetic).
- Live smoke spends provider credits; it is opt-in and never retried on low credit.
- Fallback model `opencode-go/deepseek-v4-pro` is allowlisted and preflighted but
  not used automatically; switching requires a `policyVersion` bump.

## Rollback

- Group A: restore `gateway/agents.json` + `gateway/model-routing.json`; the
  gateway then fails closed with `MODEL_CONFIG_INVALID` until a valid manifest is
  restored (by design).
- Group B: `-Dashboard` is additive; the previous `-Once`/`-Watch` paths are
  unchanged. Revert the script and tests together.
