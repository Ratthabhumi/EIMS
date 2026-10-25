# EIMS continuation — 26 October 2026

## Verified work

Started from GitHub PR #5 `1145276`, clean engineering checkout, three green CI jobs.
No main merge, demo checkout edits, operational DB changes or USB access.

Production fix `c1a50dd`: bare `CTK_CTKUNLINK result:2620` was incorrectly suppressed
by the numeric configuration matcher. Its exact operation/error signature now survives.
CTK uncertainty previously accepted a final status across physical lines or from another
file/session. Matching now stays within one record and reports unlinked/multiple-session
outcomes rather than implying that any observed completion resolves the failure.
No recovery mechanism or physical cause is inferred from a Success status alone.

Four failures reproduced before fixes (plus one passing control) in
[terminal-before.xml](evidence/20261026-continuation/terminal-before.xml).
After fixes: **286 passed, 1 Windows symlink skip, 19 existing warnings**;
includes **35 PostgreSQL tests**. Full suite source `3c261b2`.
[JUnit](evidence/20261026-continuation/continuation-20261026.xml).

Eight AI-generated DRAFT candidates cover unrelated two-file evidence, multiple sessions,
truncated status, unlinked apparent recovery, Success/Failed/Warning across midnight,
and bare CTK. They are outside DEV/HELDOUT and not independent quality evidence.
`tools/run_analyzer_counterexamples.py` calls existing native offline routes, summary,
local KB and memory History reconstruction; all eight uncertainty assertions and roundtrips
passed at `4fc7c69`. CI now runs this command too. Full emitted narratives and traces:
[candidate results](../../evaluation/analyzer/results/20261026-counterexamples).
Passing these contracts does not adjudicate every narrative claim.

Controlled DEV rerun at clean `3c261b2`: 12 DRAFT, 0 errors, 0 HELDOUT,
77 claims, zero human judgments. Prediction hashes and typed semantics unchanged 12/12
relative to `20261025-grounded-diagnosis-full`; no new human packet required.
[Frozen results](../../evaluation/analyzer/results/20261026-terminal-scope-full).
Legacy v2 remains frozen: its single terminal-outcome projection is not a session-aware
multi-session evaluator. Do not use it to score these candidates as Gold; a future
version must define per-session identity and ambiguous associations explicitly.

## Database and runtime evidence

Full Alembic base-to-head upgrade now executed from an empty unique schema in the existing
dedicated synthetic DB on loopback 55439. Version/table assertions passed, ending at
`e1a202610250`; no create_all/bootstrap/stamp in this full-lineage test.
The first repeated isolated attempt exposed pgvector type visibility: an existing extension
can live outside the new schema. The test discovers its namespace without relocating it,
and pins the Alembic version table to the new schema to prevent a neighboring version
table from skipping migrations. `migrations/env.py` supports that optional caller attribute.
All generated test schemas are retained. This proves empty-schema migration, not upgrades
of populated customer data, operational deployment, backup restore or OS restart.
[Migration test](evidence/20261026-continuation/full-lineage-test.xml).

The dedicated PostgreSQL container was already running; no duplicate service started.
No listener was found on prepared browser ports 3009/3449. HTTPS browser end-to-end is
**NOT_TESTED/BLOCKED**: prior Dashboard startup was rejected by automatic approval as
“blocked by policy”; no equivalent launcher/port/cookie workaround was attempted.
USB end-to-end remains NOT_TESTED.

Static catalog inspection finds **141**, all Windows-related entries, in both engineering
and demo checkout files. The requested total 163 is not reproduced in current source;
do not report it as PASS. Vendor filtering and History visual/reload acceptance remain
NOT_TESTED in a browser; isolated native History and PostgreSQL tests are separate evidence.

## Actor / resource / action matrix

| Actor | Resource/action | Secure policy and evidence |
|---|---|---|
| Active ordinary user | Own Analyzer History/read, feedback | Existing owner-scoped regression suite passes |
| Other user | Another user's History | Denied by existing ownership regressions |
| Active admin/service credential | Shared assets/OCR, evaluation, telemetry, timeline | Existing admin gate; evaluation create/read positive control passes |
| Ordinary/anonymous/forged credential | Shared API reads and EVTX ingestion | Existing negative tests pass; certificate header does not grant identity |
| Revoked/expired admin JWT | Shared reads and customer evaluation submission | New PostgreSQL tests return 401; zero evaluation rows written |
| Demoted former admin | Same reads/submission | New PostgreSQL tests return 403 despite previous role claim |
| Any caller, including forged Origin/cookie/token/header | Secure dashboard WebSocket | Real ASGI handshake denied with 1008 before registration; no alert stream |
| External customer without explicit scoped grant | Customer form | Closed; public workflow is NOT_IMPLEMENTED |

The closed policy prevents exposure but is not the completed least-privilege user workflow.
Do not grant broad admin credentials to customers/collectors to make a demo work.
Opening shared data requires an accepted resource/tenant assignment model. Proposed next
design: server-issued, revocable, expiring invitation bound to one evaluation and action,
and a separately authenticated read-only alert stream with Origin validation and session
revalidation. These are proposals, not implemented/approved features.

Research checked against [OWASP Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
and [WebSocket Security](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html).
Applied now: deny by default and recheck current permission/session on requests.
Not applied yet: scoped customer grants, authenticated WSS transport, per-message scope
and connection expiry/revocation. OWASP guidance is not runtime certification.

## Remaining decisions and next work

1. Owner supplies/accepts trusted runtime and shared-data actor/resource policy; then
   implement scoped customer/collector/stream access and run HTTPS browser acceptance.
2. Human reviews existing source-first packet (fort_config, esxi_tracker, win_policy).
   No reviewer identity, receipt, reviewed label or accuracy claim was generated.
3. Research handoff to ChatGPT: compare minimal one-evaluation invitation vs account-bound
   customer access, read-only alert polling vs WSS, and institution-specific retention.
   Return decision/source/version/applicability/negative tests/cost; do not broaden into
   model training or competitor surveys. No documentation can choose who owns shared data.
4. Investigate provenance of expected catalog 163 before importing another branch's data.
5. After approval, merge dependent PRs #2 → #3 → #4 → #5 with exact-head CI after retarget.

Five-minute demo remains: scope/limits → Fortinet nonfailure → CTK observed failure with
UNKNOWN cause → Windows DC symptom/source lines → saved History evidence and review packet.
Use offline evidence as an explicitly labeled fallback while browser acceptance is blocked.
