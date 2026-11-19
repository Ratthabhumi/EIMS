# EIMS Demo Runbook — 5–10 minutes

Status: **not yet deployable** until the Runtime URL exists (see
`DEMO_DEPLOYMENT.md`). This runbook is written for the instructor session.

## Before the session (2 minutes)

1. Open the API health URL and wait for the cold start (up to ~1 minute on the
   Render free tier). Expect a JSON body; `DEGRADED` is normal in demo mode
   because Redis/MinIO are not provisioned.
2. Open the console URL (`https://<service>.onrender.com/demo`).
3. Have the demo credentials ready — they are handed over out-of-band, never in
   this repository.

## Walkthrough

| # | Action | Expected result | What to say |
|---|---|---|---|
| 1 | Sign in as `demo.engineer` | Incident list appears, each row shows status and remediation cycle | "The list is read from PostgreSQL over the real API." |
| 2 | Open "Repeated failed logon attempts on DEMO-WS-01" | Detail shows evidence (winlog, digest, observed_at) and an empty verification history | "This is an open incident; nothing has been claimed about root cause." |
| 3 | Open "Disk latency spike on DEMO-DB-01" | Status `investigating`, evidence attached | "An engineer is working it; no verification evidence yet." |
| 4 | Open "Authentication failures on DEMO-WEB-01" | Status `resolved`, one verification row with verifier `demo.reviewer`, cycle 0 | "Resolution is only possible because a reviewer verified a post-patch analysis observation. The row is append-only." |
| 5 | Open "Account lockout on DEMO-DB-01" | Status `investigating`, `remediation_cycle = 1`, one verification row from cycle 0 | "It was resolved, then reopened. The old verification stays in history but can no longer close the new cycle." |
| 6 | With an engineer session, select the cycle-0 evidence and press Resolve | Blocked (`409`/`422`) with a reason | "The server refuses: the evidence predates the current remediation cycle." |
| 7 | Sign out, sign in as `demo.reviewer` | Same list | "Verification requires the review capability; the identity comes from the token, not the request body." |
| 8 | On DEMO-DB-01, attach/select current-cycle evidence and Resolve | `200`; verification history gains a cycle-1 row with verifier `demo.reviewer` | "This is the persisted proof: who verified, when, which cycle, which evidence digest." |
| 9 | Refresh the page | The new verification row is still there | "It is committed to PostgreSQL, not held in the browser." |

## Recovery / troubleshooting

- **Page does not load in ~60s:** the free service is cold-starting; retry once.
- **Health says `DEGRADED`:** expected with `EIMS_DEMO_SOFT_DEPS=1`.
- **Login fails:** confirm `EIMS_AUTH_MODE=secure` and that the seed ran with
  `EIMS_DEMO_PASSWORD`.
- **Resolve blocked with `missing_verification`:** select an `analysis` evidence
  row from the list; winlog evidence cannot verify by design.
- **Resolve blocked with `verifier_unauthorized`:** you are signed in as the
  engineer; switch to `demo.reviewer`.

## After the session

No cleanup is required. Do not delete the Neon project without exporting the
data; it holds the only copy of the demo evidence.
