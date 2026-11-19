# EIMS Demo Limitations (2026-11-24)

This is a demonstration deployment, not production certification.

## Not deployed yet

- **No Render or Neon resource exists.** No authenticated browser session was
  available during preparation, so no URL can be reported. Everything else
  (seed, service definition, console, runbook, compose cleanup) is ready.

## Free-tier limits

- Render free web service: 512 MB RAM, spins down after ~15 minutes idle,
  cold start up to ~1 minute, **ephemeral filesystem** (nothing written to disk
  survives), no background worker compute.
- Neon free: limited compute hours and storage. Verify the current quota in the
  console. The demo uses a direct connection with a 2–3 connection pool.
- No SLA, no backups guarantee. The demo database is the only copy of the demo
  evidence.

## Deliberate scope reductions

| Item | State | Why |
|---|---|---|
| PgBouncer | **not used in the demo** | the local pooler (1.25.2, port mismatch) never passed acceptance; the demo uses a direct connection |
| Redis / MinIO | **not provisioned** | with `EIMS_DEMO_SOFT_DEPS=1` they are optional; the incident workflow does not need them |
| Background workers | **not started in demo mode** | they require Redis; nothing in the demo path depends on them |
| Next.js dashboard | **not deployed** | app-router with server routes, no incidents page; a static export would require rewriting it. The API serves a thin same-origin console at `/demo` instead. |
| Independent verifier service | **not built** | would be a new deployable; the limitation is retained (below) |

## Security limitations carried forward

1. **Compromised runtime database credential can forge a consistent
   verification row.** The DB guards stop the cheap replay paths (raw resolve,
   cycle rewind, closed reopen, stale evidence, self-verification), but not a
   caller that can write every required field. Protecting against that needs a
   separate verifier authority — out of scope for the demo.
2. **Verification proves reference integrity, not external system health.**
   `analysis` evidence is the only verification-grade type; the human reviewer
   attests the remediation outcome.
3. **Audit journal is not tamper-evident.** `audit_logs` is INSERT-only for the
   runtime role, but an owner/superuser can rewrite it. No hash chain is claimed.
4. **No production security acceptance.** The accepted statuses are
   "with limitations" for the incident scope, runtime identity and privilege
   topology; whole-system security is not accepted.

## Local compose changes (not applied to the running stack)

`docker-compose.yml` was edited (pinned to loopback, MinIO bucket made private,
PgBouncer mapping corrected to `127.0.0.1:6432:5432`). The running containers
were **not** recreated, so they still use the old configuration until someone
restarts the stack deliberately. This does not affect the cloud demo, which does
not depend on the local stack.

## What must be fixed before the demo

- Authorize Render and Neon, create the resources, push the demo branch, run the
  migration/grant/seed sequence, and execute the browser walkthrough.
