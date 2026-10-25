# Secure Analyzer checkpoint — 25 October 2026

## Status and Git boundary

Continues verified PR #4 head 443676bf38af12c209091bd2838de0a0e3b27710
on codex/secure-analyzer-session-20261025. PR #2/#3/#4 remain stacked; no main
merge, rebase, release tag, deployment, operational DB action or USB change.
This continuation remains an engineering candidate, not an accepted secure demo.

## Reused and implemented

- Reuse backend /api/v1/auth/login, password hashing, JWT issuance, existing
  Analyzer, History, evidence schemas and evaluation. No replacement login DB,
  analyzer, gold schema, scorer or third evaluation runner.
- Add a same-origin Next BFF. Only the server forwards its HttpOnly session
  cookie as Authorization. Login JSON never returns the JWT to application JS;
  no token/admin credential is stored in localStorage or NEXT_PUBLIC variables.
  Cookies use Secure, HttpOnly and SameSite=Strict. State-changing requests require
  matching Origin; redirects upstream are prohibited. Encoded path separators
  cannot bypass the blocked raw-token login endpoint. Request bodies are bounded.
- Add a bilingual sign-in/session/sign-out panel to the actual Analyzer page.
  Session expiry clears the cookie and reloads stale UI state on its next session
  check. Feedback failures are displayed instead of silently shown as saved.
- All apiUrl HTTP requests now use the same-origin proxy. EIMS_BACKEND_URL is a
  server-side backend URL; EIMS_DASHBOARD_ORIGIN pins the externally visible HTTPS
  origin behind a reverse proxy. WebSocket transport is unchanged and is outside
  this Analyzer HTTP acceptance scope.
- Secure JWT subjects must still exist in the users table. Current DB roles,
  including the alternate admin/token guard, govern admin access rather than an
  old role claim. Deleted accounts are rejected. There is no disabled-account
  status field; a separate disable lifecycle is NOT IMPLEMENTED. Existing static
  server admin-token behavior is preserved; it is not exposed through the BFF.
- Additional legacy feedback and statistics endpoints now filter the authenticated
  owner. Privileged admin user/leaderboard/export operations remain explicitly
  admin-scoped; they are not treated as ordinary user-owned History endpoints.
- The shared vector knowledge schema has no owner identity. Secure mode therefore
  neither reads nor publishes private History in that shared namespace until an
  owner-aware design exists. Deterministic public vendor/curated KB is preserved;
  intentional Demo shared-identity behavior remains distinct.

## Reproduced evidence/privacy issues

A synthetic-only credential input reproduced clear marker values in API output
before masking: 1 failed / 14 passed in the targeted PostgreSQL run. No company
or customer secret was used. Credentials are now masked before parsing, synthesis,
KB context, persistence and optional exports. New metadata records policy version,
redaction operation count, replaced control characters and context-retention mode.
JSON quoted values retain valid JSON syntax; line boundaries survive.

Recognized key/value credentials and Bearer/Basic credential values are masked.
NUL and unsafe C0 control characters are replaced; newline/tab remain. This is
pattern-based minimization, **not complete DLP**. Unrecognized encodings/secret
formats can remain. Usernames, internal addresses, filenames and paths intentionally
remain forensic identifiers available to authorized subjects. Use synthetic inputs
until the intended deployment's privacy requirements are independently accepted.

Bounded source context is labelled redacted/extracted when transformed, never raw
file bytes. EIMS_EVIDENCE_CONTEXT=none disables the additional context snapshot;
it does not erase the independently stored History description/summary. Default
context remains at most three retained lines per item, each up to 500 characters,
under existing evidence-item caps. Owner-controlled deletion remains the existing
mechanism; no automatic TTL purge or historical migration/deletion is performed.
Legacy rows are not retrospectively sanitized or reassigned.

The two PDF export templates inserted raw analysis strings into innerHTML. Actual
historical template execution against an inert synthetic HTML marker reproduced
unescaped element markup. Both templates now escape report data; regression runs
execute the actual templates and verify encoded data. This establishes safe HTML
assembly for those payloads, not a claim that arbitrary script execution or every
PDF/browser behavior was tested. React source text remains text, not injected HTML.

## Executed validation versus missing acceptance

| Layer | Result / boundary |
|---|---|
| Combined Analyzer + integration regression | **231 passed, 1 skipped**, 16 existing dependency/utcnow warnings, 14.76 seconds; Windows symlink privilege skip; includes escaped-quote credential control |
| PostgreSQL/JWT | 16 tests in the combined suite; actual synthetic DB, real credential login, deleted user, demoted admin, other-owner feedback/stats, Demo compatibility and credential masking |
| Next routes / export templates | **13 passed** using actual route/template code with controlled synthetic upstream responses |
| Next routes → real backend HTTP → PostgreSQL | **5 passed**: actual credential login, HttpOnly/Secure cookie attributes, real subject verification, logout access denial, actual issuance with short test TTL and expired-token rejection |
| Dashboard production build | Passed compilation, TypeScript and 14 routes |
| Actual new browser login/HTTPS/History acceptance | **NOT TESTED / BLOCKED**, see below |
| Installed system, real TLS deployment, USB | **NOT TESTED** |

Automatic execution approval rejected starting the Dashboard test process with
the proposed HTTPS-origin configuration. The tool stated only **blocked by
policy**. No reason beyond that is asserted, no equivalent startup was attempted
through another mechanism, and no HTTPS/browser PASS is fabricated. In-process
Next handler tests were used as a separately declared lower-level fallback;
they open no Next listener and do not prove a real browser's cookie behavior.
No certificate, private key or real login credential is published.

`tools/verify_secure_dashboard.cjs` is prepared and syntax-checked, **not executed**.
It performs actual form login without injecting bearer headers, two-user ownership,
upload/source inspection, light/dark, page reload/History reopen, logout, expiry
and reauthentication. It requires an authorized isolated Dashboard/HTTPS runtime.
Prior PR4 browser screenshots used an injected synthetic JWT and cannot certify
this new secure flow. They are retained as historical evidence only.

Logout clears this browser's cookie; it does not globally revoke a copied JWT.
Its signature/expiry and account existence are checked server-side. A distributed
revocation/session-store design is deferred, not silently claimed. Login rate
limiting and trusted TLS deployment acceptance also remain release prerequisites.

## Reproduction and policy constraints

Use only the dedicated eims_integration_test database/user on loopback port 55439,
never application database settings. Existing test URL guards reject operational
ports and missing configuration. The PostgreSQL tests use rollback/savepoints;
the separate HTTP harness creates only explicitly named synthetic fixture users.

```powershell
$env:EIMS_TEST_DATABASE_URL='postgresql+asyncpg://eims_test:eims_synthetic_only@127.0.0.1:55439/eims_integration_test'
python -m pytest tests/test_analyzer_reliability.py tests/test_analyzer_evaluation.py tests/test_analyzer_investigation.py tests/test_analyzer_integration_stability.py tests/test_analyzer_postgres_integration.py -q
node tools/test_session_proxy.cjs
node tools/test_session_proxy.cjs --live
```

The live handler command requires the already authorized isolated backend harness,
not a production endpoint. It uses a public synthetic test password and never
prints/publishes JWT values. HTTPS Secure cookie attributes are checked as route
outputs; no TLS handshake or actual new browser flow is inferred from them.
An explicitly opted-in loopback HTTP cookie exception exists for development
only, EIMS_ALLOW_INSECURE_LOCAL_SESSION=1; it was unit-tested, not used to work
around the rejected Dashboard startup. The production default remains Secure.

## Research applied and handoff

Only narrow implementation references were checked:
[OWASP session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
[object authorization](https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/),
and [sensitive logging guidance](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html),
plus the installed Next version's cookie/route documentation. No broad competitor
or model research was repeated. These guide controls; they do not certify EIMS.

Send unresolved research to ChatGPT using ANALYZER_RESEARCH_HANDOFF_20261025.md:
Windows 1129 symptom taxonomy, Fortinet add/edit/delete/version scope, CTK article
environment prerequisites, and independent human grounding protocol. New privacy
questions: which identifiers need reversible pseudonymization without false
cross-file correlation, and what retention/deletion policy the intended institution
requires. No generic SIEM comparison or model download is necessary.

## Scientific and release gates

All 12 DEV and five reserved HELDOUT remain DRAFT; no human alias, signature or
receipt is fabricated. Original labels, heldout lock and old controlled results
remain unchanged. Claim queues are prediction-hash-specific; historical 135-claim
reviews cannot certify changed predictions. Semantic support and unsupported-claim
rate remain null until genuine judgments. Software terminal-status controls are
not independent positive Gold cases; current DEV terminal-positive support is zero.

Next acceptance: permit and execute the prepared secure browser flow in an
isolated authorized environment, including trusted TLS/operational configuration
review, then consolidate owner authorization for the PR stack. No merge request
is treated as already granted; no release is declared while this gate is incomplete.
Human review of fort_config, esxi_tracker and win_policy remains a separate owner
decision. Technical progress is not scientific validation.

## Frozen experiment and evidence publication

Native full snapshot source **256bbc6c49aa6ae4a147940479f5c0568debb381**:
evaluation/analyzer/results/20261025-secure-checkpoint-full. Executes 12 DRAFT,
zero reviewed/heldout, zero errors; exact source coordinate overlap 4 TP / 0 FP /
0 FN against unchanged proposals. All **135 claims** are NOT_REVIEWED;
semantic support and unsupported-claim rate remain NOT_MEASURED/null. A subsequent
small quoted-secret escape hardening is covered by the 231-test regression;
the snapshot is not relabelled as an execution of a later source SHA.

Session route reports are published under evidence/20261025-session. They contain
test names/status and explicit execution boundaries, never credential/JWT values.
Browser status is explicitly NOT_TESTED with the tool rejection, not an invented
PASS report. Exact final-head CI remains the authoritative test result in the PR.
v1/v2 annotations, HELDOUT and original controlled artifacts are byte-unchanged.

Chapter 4 delta: secure login is now implemented and validated below the browser
boundary; deleted users and current role enforcement are measured, and shared
unowned vectors are excluded in Secure Mode. None improves a scientific accuracy
denominator. The existing GRADUATION_DEFENSE_UPDATE_20261025.md remains the report
structure; this addendum supplies new measured facts rather than replacing it.

Priority human packet: [source-first review pages](evidence/20261025-session/review/README.md)
prepare **36/135 claims from 3/12 DEV** (fort_config, esxi_tracker, win_policy),
selected by the owner's priority rather than random sampling. Raw numbered input
appears before AI proposals. These are prepared read-only pages, not executed
secure browser acceptance or completed review. Human judgments remain 0/135.
Prediction hashes bind the pages to this snapshot's queue; no reviewer receipt
or Gold status is generated.
