# Browser acceptance report (2026-11-22, updated after rebuild)

Real browser (Claude desktop built-in browser) against a **local stack**: synthetic backend (`tests.analyzer_synthetic_demo_app`, 127.0.0.1:8019, disposable PostgreSQL `eims_analyzer_it`) and a **production build of the latest source** (`next build --webpack`, rebuilt twice this pass from the current `clients/dashboard/src`, `next start`, 127.0.0.1:3009). No operational database. Synthetic identities only (a disposable JWT session cookie injected for the reviewer cases; see reviewer report). Screenshots in `screenshots/`. The viewport of the pane during the second half was narrow (268 px), which doubles as a small-screen check.

| # | Case | Input | Expected | Actual | Result |
|---|---|---|---|---|---|
| 1 | Health via proxy | `/api/eims/api/v1/health` | 200 | 200 HEALTHY | PASS |
| 2 | Analyzer result, STATED/NOT STATED | Cisco ASA `%ASA-2-113005` line | 12 sections, pending-review banner | 10 STATED, 2 NOT STATED, banner, source and version scope shown (`analyzer_guidance_asa113005.jpg`) | PASS |
| 3 | UNVERIFIED badge | PostgreSQL xid-wraparound syslog line | recovery verification UNVERIFIED with warning | "9. Recovery verification UNVERIFIED — Unconfirmed … do not treat as confirmed guidance" | PASS |
| 4 | Destructive warning | same line | red alert, rollback NOT STATED, missing list | alert "state-changing action and no rollback is stated…", "8. Rollback steps NOT STATED", "Missing for operational use: recovery_verification, rollback_for_destructive_action" (`analyzer_destructive_warning_narrow.jpg`) | PASS |
| 5 | Human approval row | same line | EIMS policy, not vendor | "STATED … Origin: EIMS policy, not a vendor statement." | PASS |
| 6 | Unmatched / reference-style input | PostgreSQL SQLSTATE 23505 text | no guidance | "Unknown", no panel | PASS |
| 7 | Empty submission | blank text | no record, no crash | 0 records | PASS |
| 8 | Backend unavailable, Analyzer | backend stopped, submit ASA line | clear error, input kept | toast "Analysis service unavailable"; text kept; system status Degraded/Offline; no record | PASS |
| 9 | Backend unavailable, reviewer page | backend stopped | not a misleading "no capability" | after fix: "The EIMS backend could not confirm your session (HTTP 502)…" (before the fix it said only "no reviewer capability") | PASS after fix |
| 10 | No session (open access) | anonymous `/knowledge/review` | per owner policy: reads open, actions disabled | queue of 100 and record visible; capability "no … open access"; Save/Submit/Withdraw/Record disabled (earlier deny-by-default behavior was reverted, see reviewer report) | PASS |
| 11 | Success message persists (fix 1) | Save draft; Submit | message visible after reload | "Submitted for human review" visible; status DRAFT then HUMAN_REVIEW; history shows both events | PASS |
| 12 | 422 names the field (fix 2) | invalid evidence reference | field named | "422: evidence_refs.0: Input should be a valid URL…" | PASS |
| 13 | Queue columns (fix 3) | reviewer queue | spaced columns | cell padding 8 px | PASS |
| 14 | Fields keep all values (fix 4) | 4 validation fields set rapidly | all retained | all four values present | PASS |
| 15 | Draft Save / Submit / Preview | UNVERIFIED draft for `candidate:postgresql:locks:deadlock-detected` | preview says unverified never counts; saved; submitted | exactly that; the draft did not complete the record ("Missing now: recovery_verification → with draft: recovery_verification") | PASS |
| 16 | Pending human review | after submit | status HUMAN_REVIEW, not active guidance | HUMAN_REVIEW | PASS |
| 17 | Small screen | 375 px (earlier) and 268 px (this pass) | no page overflow | scroll width equals viewport width both times | PASS |
| 18 | Stale source/hash | synthetic source change applied after a draft (disk-full) and after a human-approved supplement (deadlock) via a flag-driven in-memory harness, repository untouched | STALE shown and explained; old draft cannot be submitted; old approval does not authorize; Analyzer ignores the stale approval | before: draft DRAFT, deadlock APPROVED, Analyzer showed "APPROVED_SUPPLEMENT (human-approved; catalog content hash current)" with recovery verification STATED; after: both records STALE, banner "STALE: the catalog record changed after this draft or approval was recorded…" (`screenshots/reviewer_stale_state.jpg`); submit refused "422 proposal_rejected: only a DRAFT can be submitted (status is STALE)"; re-approval refused "422 transition_rejected"; Analyzer: "pending human review — not approved", recovery verification NOT STATED, missing recovery_verification | PASS |

## Defects found in this acceptance work and fixes
1. Reviewer record showed BLOCKED while nothing was missing → `proposals.get` now assesses operational completeness only and states its basis.
2. Success message disappeared; 422 lacked the field; columns cramped; review fields lost values → fixed in `knowledge/review/page.tsx` and **verified on the rebuilt dashboard** (cases 11–14).
3. With the backend down the reviewer page claimed the user lacked the capability → now says the backend could not confirm the session (case 9).

## Limits
Only the ASA and PostgreSQL families were driven in the browser. The reviewer cookie is test-only; the product has no reviewer sign-in (owner decision). The in-repo Turbopack build was not run (the user's `next dev` owns that directory); `next build --webpack` passed on a copy that differs from the repository only by build artifacts.

## Stale-source harness (disposable)
`stale_app.py` (session scratch directory) wraps the synthetic backend and, while a flag file exists, appends a marker to two catalog records in memory; the approved supplement was created by four synthetic reviewer users (verifier, validator, author, approver) with obviously synthetic text and a synthetic quote. All of it is test evidence, not certification. The page was rebuilt after the final wording change and re-verified.
