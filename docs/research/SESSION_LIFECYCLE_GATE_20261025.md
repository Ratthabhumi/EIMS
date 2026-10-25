## Current checkpoint — 26 October 2026 publication

This update supersedes historical status below; historical measurements remain intact.
Implementation source: `348f892719cc0e839cd2813d344d26e672c883fd`.
See [grounded diagnosis report](GROUNDED_DIAGNOSIS_CHECKPOINT_20261025.md) and
[next execution instructions](NEXT_EXECUTION_PROMPT_20261026.md).

- Implemented vendor-grounded Fortinet configuration identity, Windows 1129 symptom-only summary,
  CTK cause abstention and narrower KB applicability; removed cross-vendor default assumptions.
- Local regression: 273 passed, 1 Windows skip, including 31 dedicated PostgreSQL tests.
  Actual Alembic upgrade was rehearsed from a minimal parent schema; full historical chain and
  operational migration remain untested. Bounded cleanup, rollback and concurrency verified.
- Direct organization APIs now require admin/service authorization in Secure Mode;
  customer evaluation forms are also restricted, ingestion requires service authorization,
  and secure WebSocket streaming is disabled pending an authenticated transport.
- Controlled DEV: 12 DRAFT, zero execution errors, 77 claims, zero human judgments.
  Narrative changed 12/12; typed v2 fields unchanged 12/12. Claim reduction from 135 is not accuracy.
- HTTPS browser acceptance, independent human validation, institutional retention and deployment
  acceptance remain open. M2/M3 remain NOT_RUN. Existing review packets are historical.

# EIMS session/privacy checkpoint — 25 October 2026

## A. Git state

Existing Draft [PR #5](https://github.com/Ratthabhumi/EIMS/pull/5), branch
`codex/secure-analyzer-session-20261025`. Frozen implementation:
`77603388de96324fc5dbf56e1de2cdc192cde747`. The evidence publication commit
packages that source's experiments; it is not another Analyzer execution source.
PR stack #2 → #3 → #4 → #5 unchanged. Main remains
`bf634d9ddf86f44220ef961cf4be32988cfc5ee5`; no merge/rebase/reset/force push.
Original demo checkout's dirty/untracked work preserved. New-head CI must be
checked on PR #5; the earlier run 40168947216 cannot certify this source.

## B–D. Existing implementation, corrections and regressions

Reuse credential login, JWT, Next BFF, owner-filtered History, native Analyzer,
local KB, evaluator, PDFs and dedicated PostgreSQL harness. No replacement system.

- Previously logout only cleared the cookie. Login now signs a random SID backed
  by a PostgreSQL row storing its SHA-256 digest, user ID, username, password-hash
  fingerprint and timestamps. Logout revokes it; copied JWT replay fails, while a
  second independent session stays valid. No raw JWT/password in the new tables.
- Absolute expiry follows configured JWT lifetime (default 60 min), idle expiry
  is 15 min. Background `/auth/session` probes do not extend idle. Password changes,
  deleted accounts and different account IDs invalidate sessions. Current DB role
  remains authoritative. Old SID-less user JWTs require re-login. Static ADMIN_TOKEN
  is a separate service credential and is not revoked by logout. No disable-account
  flag/password-reset UI or statistically constant-time login is claimed.
- PostgreSQL atomic fixed windows: 8/account/60 sec, 120/observed peer/60 sec,
  reserved before password checks and committed even on failed attempts. BFF gate:
  8/account and 60 total/60 sec, bounded per-process memory. 429 + Retry-After,
  automatic window recovery, generic missing/wrong-password 401, dummy hash work.
  Incoming forwarded IP is ignored; behind one BFF the peer quota is shared.
- Failed backend revocation returns 502 and retains cookie for retry. Successful
  revocation clears cookie. Browser pageshow triggers a session check.
- User deletion previously omitted await; now executes. Recreating a username
  with retained History returns 409 to prevent ownership inheritance.
- Global Search's evaluation provider emitted customer/engineer metadata without
  an admin gate. Secure non-admin searches now dispatch only navigation and owned
  analysis. Explicit other types return 403; unfiltered queries cannot bypass it.
  Current DB admins retain organization-wide search; demo behavior unchanged.
- Masking missed quoted multiline secrets and consumed following query parameters.
  Policy v2 handles these, preserving physical CR/LF counts and unrelated IPs.
  Nested JSON, escaped quotes, Basic and long lines have regressions. Unknown keys,
  arbitrary embedded/encoded JSON and arbitrary prose secrets remain outside this
  pattern-based minimization contract; this is not DLP.

Tests: `tests/test_analyzer_postgres_integration.py`,
`tests/test_analyzer_integration_stability.py`, `tools/test_session_proxy.cjs`.

## E. Actual browser / HTTPS

**NOT_TESTED.** No existing approved isolated runtime was found on prepared ports.
Prior automatic approval rejected Dashboard startup with HTTPS-origin configuration:
**"blocked by policy"**. No equivalent Next/TLS listener or insecure-cookie workaround
was launched. Only the independent documented loopback synthetic backend harness
was started, used for handler→HTTP/JWT/PostgreSQL tests, then stopped.
First handler probe preceded backend readiness (502); after startup all 6 passed.
This is not browser/TLS evidence. Login form, browser cookie storage, upload/reload,
two-user UI, logout/back navigation and real reverse proxy remain NOT_TESTED.
Prepared `node tools/verify_secure_dashboard.cjs` is for an independently authorized
runtime after the policy restriction is resolved; do not disguise/retry the rejected
startup. Existing acceptance evidence remains historical.

## F. Session, privacy and deployment gates

| Surface | Effective boundary / evidence | Remaining limit |
|---|---|---|
| Analyze/bundle/follow-up | Current user + owner History; cross-user 404 tests | Browser flow pending |
| History/stats/asset filter/feedback | Username owner predicate | Null/imported unowned rows are not reassigned |
| Global Search analysis | Task-local owner, FTS/fallback predicates | No-scope fail closed |
| Search asset/audit/winlog/USB/OCR/telemetry/evaluation | Current admin in secure mode, including unfiltered query | No per-user domain ownership contract |
| Obsidian export | Admin/service-token dependency; downgrade denied | Actual filesystem export not run; privileged cross-owner contract |
| Reports/PDF | Owner-delivered input; both real templates escaped | Actual browser PDF pending |
| Shared vectors | Secure mode skips unowned read/write; forbidden-sink tests | Owner-aware vector index deferred |
| Admin users/leaderboard | Current DB admin; username retention conflict | Dedicated admin audit trail not added |
| Direct other-domain APIs / WebSocket | Outside Analyzer/BFF acceptance | Global Search fix does not certify these routes |

Handler tests cover missing/cross/conflicting Origin and pinned expected origin;
forwarded Host/Protocol cannot replace the pinned value. Real TLS/header trust is
still pending. Deployment must pin EIMS_DASHBOARD_ORIGIN to trusted HTTPS and keep
EIMS_BACKEND_URL server-controlled/backend private. BFF caps body at 40 MiB and
upstream at 60 sec; responses no-store, cookies HttpOnly/Secure/SameSite Strict,
Path=/, no Domain. Optional __Host- rename deferred. No operational config changed.

Alembic head `e1a202610250`, parent `8a2b4d6f9c1e`: auth tables only.
`alembic heads` and offline `upgrade parent:head --sql` passed;
[SQL artifact](evidence/20261025-lifecycle/session-migration-offline.sql).
No operational migration applied. ORM tables were created only in the dedicated
test DB; deployed migration is NOT_TESTED. Apply reviewed auth migration before
deployment, require old-token re-login and run health/login checks. If deployment
fails restore the prior app artifact with ingress denied until its earlier logout
limitation is accepted. No automatic table drop or History reset rollback.

BFF memory/counter values are bounded; DB key cardinality and expired session
retention are not globally bounded. Approved retention, quota/load tuning and
deployment-wide permissions remain pending. No automatic cleanup or History deletion.
Already authorized in-flight requests may finish after logout; subsequent checks deny.

## G–I. Scientific status, research delta and experiments

[Full snapshot](../../evaluation/analyzer/results/20261025-session-lifecycle-full):
source `77603388`, clean tree at execution, PYTHONHASHSEED=0, 3 warmups/3 repeats;
12 DEV DRAFT, 0 reviewed, 0 HELDOUT, 0 errors, 135 claims, 0 human judgments.
Accuracy/grounding/unsupported-claim rate remain undefined. Existing baselines,
v1/v2 labels and HELDOUT unchanged.

[Comparison](evidence/20261025-lifecycle/snapshot-comparison.json): semantics v2
unchanged 12/12, claims unchanged 12/12. All 12 prediction hashes changed solely
through native privacy policyVersion v1→v2, not a measured diagnostic improvement.
Fresh source-first [packet](evidence/20261025-lifecycle/review/README.md) for
fort_config, esxi_tracker, win_policy: 36/135 prepared, 0/135 reviewed.
Use new snapshot queue/hashes for judgments; old pages preserved.

| Experiment | Actual result | Boundary |
|---|---:|---|
| Combined Python | 251 passed, 1 skipped, 19 warnings | Windows symlink skip; dependency/utcnow warnings |
| PostgreSQL subset | 28 passed | Dedicated loopback DB, savepoints/outer rollback |
| Handler/PDF regressions | 18 passed | Synthetic upstream, no browser |
| Handler→real HTTP/JWT/PostgreSQL | 6 passed | Backend-only harness, no Next HTTP/TLS |
| Dashboard build | PASS | Next 16.3.0, TypeScript, 14 generated routes |
| Native full DEV | 12 / 0 errors | Memory History, local KB; no network/model/vector/operationalDB |
| M2/M3 / USB / installed secure deployment | NOT_TESTED | No inference/index/USB changes |

Safe JUnit/JSON in `evidence/20261025-lifecycle/`. Use existing test commands from
SECURE_ANALYZER_CHECKPOINT_20261025.md; no new runner. Initial DB checks failed
because the dedicated container was stopped; same labelled container restarted
and final suite passed. Oversized pytest case ID caused a Windows filename error;
short explicit test IDs fixed that harness issue.

Narrow references checked: [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
for server invalidation/idle/absolute expiry and [OWASP Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
for generic errors/throttling. These inform controls, not certification; thresholds
are EIMS engineering choices. No broad vendor/model Research repeated. Handoff:
ANALYZER_RESEARCH_HANDOFF_20261025.md.

## J–L. Readiness, human decisions, next milestone

**Engineering checkpoint, not a secure release candidate. Keep PR #5 Draft.**
Human work: review the three priority cases/claims; accept trusted environment,
retention/admin scope; explicitly authorize stack merge after gates. No fabricated
reviewer aliases, receipts or approvals. Next milestone: approved HTTPS browser
acceptance and real adjudication, then deployed migration/permission acceptance.
Merge #2→#3→#4→#5 only after owner authorization and fresh checks.

Five-minute safe demo: 30s synthetic/DRAFT limits; 90s two-file failure and unknown
physical RCA; 60s exact file/line evidence; 60s History/ownership/session test evidence;
60s current packet and remaining gates. Existing offline demo/screenshots in
GRADUATION_INTEGRATION_20261025.md remain fallback evidence, never current secure
browser proof. Chapters 2–5 should use these boundaries; Chapter 4 must retain the
zero reviewed denominator and avoid a successful-scientific-validation conclusion.
