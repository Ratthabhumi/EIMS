# Reviewer UI and access-policy report (2026-11-22, third update)

## Owner-confirmed policy
EIMS has **no application login by design**; Analyzer use is open access. No login, reviewer sign-in or authentication provider was added. The absence of login is not treated as a defect or a production blocker. Governance **decisions and draft writes** stay protected by the existing reviewer capability (`require_knowledge_reviewer`): a database user with the reviewer flag (or admin) holding a live credential-versioned session; the open-access identity (401), a non-reviewer (403) and the shared admin token (403) are refused; the decider and its kind (`human`) are set by the server, never by the client; the approver must be independent of the verifier and validator; the author of a submitted draft cannot approve it; AI/automation cannot decide or submit.

## Change made and reverted in this pass
Earlier this day the three governance **read** endpoints were made reviewer-only. Against the owner's open-access policy that was too strict: the queue, a record's status/eligibility/missing fields and its review history are informational catalog and review-status views (vendor quotes, hashes, who recorded what), and engineers should be able to see what has been reviewed. The reads are open again; nothing about decisions changed. `test_reads_follow_open_access_but_every_write_requires_the_reviewer_capability` (PostgreSQL, real dependencies) asserts: queue, record and history return 200 anonymously and for a non-reviewer; every write (`/proposals`, `/proposals/submit`, `/proposals/withdraw`, `/decisions`) returns 401 anonymous, 403 non-reviewer, 403 shared admin token, 401 expired session, 401 unknown identity. The dashboard page shows the queue to everyone and disables drafting and decisions without the capability.

## Access matrix
| Operation | Access |
|---|---|
| Analyzer, operational guidance (including approved supplements) | open access (existing policy) |
| Catalogue/reference views in the Analyzer | open access (existing policy) |
| Governance queue, record, history (GET) | open access; informational only |
| Save, submit, withdraw a draft | reviewer capability |
| Submit a human decision (source_verified, validated, approved, rejected, deprecated, superseded) | reviewer capability; approver independent; author of a submitted draft cannot approve |
| AI / automation / shared admin token | cannot create human decisions or submit drafts |

## Browser evidence (rebuilt dashboard, disposable synthetic identities)
Non-reviewer/anonymous: queue (100) and record visible, capability line "no … open access", all four action buttons disabled. Reviewer: draft save/submit and decision form work; 422 errors name the field; the success message persists; stale state is explained (see browser report, case 18).

## Residual notes
A reviewer account must exist (flag granted through the admin API); the reviewer cookie used in tests is a test device, not a product feature. The system cannot prove a human is not delegating to a tool. Synthetic test evidence in the disposable database, all labelled synthetic and never counted as certification: ASA 113005 `source_verified` and the PostgreSQL deadlock/disk-full drafts and approval by `synthetic-browser-review`, `synthetic-stale-*` users (verifier, validator, author, approver), and the pre-existing demo seed approval by `demo.reviewer`. The tables are append-only; the events stay. Repository certification counts (0 human approvals) come from repository artifacts and are unaffected.
