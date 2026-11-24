# EIMS Engineering Memory — 2026-11-16 DWB Orchestration + Incident Core Review

## Scope

Companion to `2026-11-16-incident-core-v1.md`. Records the DWB agent
orchestration capability, the multi-project profile layer, and the independent
review fixes applied to Incident Core v1.

## DWB agent orchestration

- Added `agent.list`, `agent.run`, `agent.cancel` to the accepted control plane.
- Registry verification: executable + version probe; Claude Code 2.1.323 and
  OpenCode 2.3.0 passed a read-only smoke; Codex remains BLOCKED (no CLI).
- Every launch requires local single-use approval; the approval CLI prints the
  complete prompt. Role/scope, writer locks, cancellation, timeout, orphan
  recovery, sensitive-output withholding and per-project jobs/artifacts are
  enforced and tested (22/22).
- Project profiles: EIMS is the only enabled profile; `_template.json` is
  disabled. Paths, approvals, locks, jobs and artifacts are project-scoped.
- Independent read-only review (Claude Code) found and we fixed: incomplete
  prompt preview, sensitive output served, scope false-open, post-finalize
  appends. Final review: no high-severity findings.

## Incident Core review fixes

- Resolved/closed incidents are excluded from correlation candidates.
- A recurrence creates a new incident with a per-bucket dedupe key instead of
  merging into a closed row.
- `_reuse_incident` and `attach_evidence` reject terminal incidents; recovery
  never merges into a closed incident.
- New DB regression covers closed-incident recurrence and evidence rejection.

## Verification

- Incident suite: 61 passed, 0 failed, 0 skipped (fresh disposable PostgreSQL,
  non-superuser role `f/f/f`).
- Regressions: 261 passed, 1 skipped (pre-existing Windows symlink limitation).
- DWB: 22/22 orchestration, 40 control-plane checks (1 not tested).
- No commit/push/reset/clean; EIMS 57 modified preserved, 69 untracked.
- ChatGPT plugin catalog refresh remains a UI step; local MCP discovery shows 14
  tools and a ready tunnel.
