# EIMS integration checkpoint — 25 October 2026

## Git decision and engineering gate

Remote PR #2 at cff00082f6905bb733849c2b74733fb50799f662 and PR #3 at
5810a259995eaf39d47f4c212c5a58cb5b0ec0d0 were verified OPEN, mergeable,
with both exact-head checks successful. main remains bf634d9. This checkpoint
continues the combined source on codex/graduation-integration-20261025.
No protected-branch merge authorization is inferred from green CI or a proposed
merge sequence. Pending owner action: merge #2, retarget #3 to main, inspect its
reduced diff and checks, then merge #3; finally retarget this continuation.
There is no rebase, force push, tag or release claim.

## Reused implementation

The existing parsers, normalized evidence records, chronology, correlation,
vendor KB, summary logic, v1/v2 evaluator, full native adapter, source inspector,
human review packet and prior regressions are reused. No third evaluator or
replacement RCA engine is introduced. The demo checkout and its dirty/untracked
files are preserved; no operational database, .env, auth mode, USB or customer
log is accessed by the test harness.

## Newly traced defects and changes

- Native single-file analysis attached textual signatures but no structured
  source evidence; CTK line 2 disappeared before response serialization and
  History, despite being recognized by canonical failure extraction. Both
  routes now convert the same retained normalized records to bounded evidence
  items. They preserve original line numbers through compaction. No DRAFT label
  or scorer change is needed to establish this information-loss defect.
- Unknown-vendor overview had been corrected in PR #3, but its generic cause
  still asserted that the session/job failed. The generic cause now says the
  physical cause is unestablished and requests explicit outcome evidence.
- History list/stats/delete/feedback and stored follow-up did not consistently
  enforce row ownership. They now scope to the authenticated username and return
  the same 404 for missing/other-owner IDs. Unowned legacy rows are not silently
  reassigned. Demo identities share the existing demo namespace; this is not
  independent-user isolation in unauthenticated mode. Auth settings are unchanged.
- Duplicate sanitized filenames could collide in provenance maps. Reject
  case-insensitive basename duplicates before analysis. Existing path-component
  sanitization remains the supported contract; it is not a filesystem write.
- Invalid plaintext UTF-8 is rejected instead of silently discarding bytes.
  Existing single-file structured ERROR response and bundle HTTP 400 behavior
  remain distinct compatibility contracts.
- Dashboard evidence now expands to exact file/line with a bounded original
  decoded/extracted excerpt, highlights the finding and returns keyboard focus.
  It never reconstructs context from compacted History text. Legacy evidence
  explicitly shows unavailable context. New excerpts persist in existing JSON;
  no table migration is needed. OCR/XML excerpts are extracted representations,
  not certified raw file bytes. No complete original file is retained by this feature.

## Validation boundaries

Initial targeted regressions on the inherited source: 2 failed, 1 passed
(missing structured CTK source items and unsupported generic failure claim;
parallel deep-copy isolation already passed). No harness import error was counted
as a product defect. A later context-bound test used a bare metadata-like CTK
fragment; its fixture was corrected to a complete timestamped VMware record.

Real PostgreSQL integration uses a new labelled, loopback-only Docker container
eims-analyzer-integration-20261025, existing pgvector:pg16 image, port 55439,
database eims_integration_test and synthetic user/key only. It does not connect
to eims-postgres or PgBouncer. The test URL guard rejects operational ports,
remote hosts, other DB names/users and absent configuration. Test request commits
are savepoints inside an outer transaction; rollback verifies the original row
count even on failed assertions. This proves PostgreSQL serialization and fresh
SELECT reconstruction, not an operational system deployment.

Real JWT verification is exercised in a separate ASGI app: no override of
get_current_user, missing/invalid/expired tokens are rejected, and synthetic
users cannot enumerate, modify or follow up another owner's record. Only DB,
local KB, RAG/model/export dependencies are isolated. Vector export is replaced
by a counted sink, never executed against a vector store. A separate loopback
HTTP harness supports actual Dashboard uploads and independent request sessions;
it uses test keys and must never be deployed.

## Scientific and human-review gate

v1 labels, fixtures, original baselines and HELDOUT lock stay byte-unchanged.
All 12 DEV and five HELDOUT remain DRAFT. Cases and proposed labels were
AI-authored and informed by existing pipeline behavior; DEV agreement is not
independent validation. Coordinate recall is not semantic support. Zero reviewed
claims means RCA accuracy, unsupported-claim rate and support precision stay null.

Reuse [the Thai packet](ANALYZER_DEV_ADJUDICATION_20261025.md), starting with
fort_config, esxi_tracker and win_policy. Reviewers should first read raw lines,
then decide identity/failure/endpoints/final outcome/cause separately; accept,
correct or unresolved with rationale. Unknown is valid. KB applicability must
record product/version/environment prerequisites; a relevant URL alone is not
an applicable fix. Do not assign reviewer identities or resolve disagreement
until real humans submit decisions. A second independent human check of a
representative subset is desirable, not falsely claimed.

Positive explicit terminal support in the frozen DEV corpus remains zero.
FAILED/SUCCEEDED/WARNING are exercised by software controls, not an independent
Gold cohort. Expanding toward 20–30 reviewed cases depends on genuine human
review and scenario-group independence; do not repackage regression literals
as independent validation or use heldout-derived examples. Review/model resources
remain owner-controlled prerequisites; implementation continues independently.

## Artifact retention and publication

Retain authoritative v1 and controlled before/after evidence in Git; never delete
or overwrite historical science to reduce size. Earlier exploratory probes remain
indexed as superseded and unsuitable for fair production comparisons. This round
will publish one frozen checkpoint run, not repeated warm-run duplicates. New
CI stores JUnit under exact-head named Actions artifacts for 30 days; routine
scratch runs, browser downloads/caches and host-labelled raw XML stay ignored.
Publish only synthetic screenshots and summaries after inspection. Future
checkpoints should retain configs/code/input hashes, per-case errors and review
decisions; optional bulky exploratory outputs belong in immutable CI artifacts.

## Research handoff and deliberate limits

Use [the existing bounded handoff](ANALYZER_RESEARCH_HANDOFF_20261025.md) for
ChatGPT Research: Fortinet format/version and add/delete semantics, CTK KB
environment prerequisites, Windows 1129 symptom taxonomy and human grounding
protocol. No competitor review or model experiment is repeated here.
Windows taxonomy and physical causes remain candidates until supported. The
vSAN-specific cause/fix is not generalized from CTK 2620. M2/M3, real USB,
installed-system authentication acceptance and deployment remain unverified.

## Acceptance for the next milestone

Exact-head CI must pass hermetic, dedicated PostgreSQL and dashboard build jobs.
Verify actual Dashboard upload → evidence → reload → reopen against the isolated
HTTP/PostgreSQL harness, then document its differences from installed EIMS.
Owner reviews three priority cases when available. Freeze a reviewed protocol
before heldout evaluation; never retune after observing heldout scores.

## Executed checkpoint results

Frozen Analyzer/evaluator source: **ee8cb7c9e9497960fdc7aea02f7e23eb88a6792d**.
PR: https://github.com/Ratthabhumi/EIMS/pull/4 (base PR #3). New final report and
artifact commits do not change Analyzer behavior. Final-head CI is linked in
the PR description; the source checkpoint's three jobs passed in
https://github.com/Ratthabhumi/EIMS/actions/runs/40151271893 .

| Verification | Actual result | Boundary |
|---|---|---|
| Combined five-file regression | **217 passed, 1 skipped**, 6 warnings, 6.66 seconds | Existing Windows symlink privilege skip; dependency and utcnow deprecations remain visible |
| Dedicated PostgreSQL/JWT suite | **12 passed**, no skips | Synthetic real DB, savepoint rollback, no auth dependency override |
| Full native evaluation | 12 DRAFT, 0 reviewed/heldout, 0 errors | Same evaluator/annotation hashes as controlled-after; no Gold accuracy |
| Native citation coordinates | 4 TP / 0 FP / 0 FN | Precision 4/4, recall 4/4 against DRAFT, not semantic support |
| Claim grounding | 135 emitted, 0 reviewed | Semantic support / unsupported rate remain null |
| Dashboard local build | Passed compile, TypeScript and 12 routes | Clean local dependency install after rejected external junction |
| Real Dashboard HTTP upload | Passed two-file upload, MEDIUM association, source expansion | Synthetic JWT supplied by browser test context, real verification on isolated API |
| History after page reload | Passed fresh request and exact stored summary equality | Independent API request/session, actual PostgreSQL commit; browser rows retained |
| Browser evidence usability | Enter-key expansion, back focus, highlighted source, dark/light passed | Actual production component/page in isolated build, not a mock response |
| Browser/network errors | 0 page exceptions, 0 external requests | Four /api/v1/health HTTP 404 responses: harness omits operational health; no green health claim |

Screenshots were visually inspected: bounded context wraps, exact line is visible
and highlighted in both themes. Published synthetic-only images and machine-readable
browser summary are under [evidence/20261025-dashboard](evidence/20261025-dashboard/).
Local XML remains under ignored test-results; CI retains JUnit for 30 days.

Important installed-system gap: this Dashboard currently has no verified secure
login/token propagation workflow. Browser automation supplies a valid synthetic
bearer header; that proves real JWT verification, not a completed human login UI.
Without that header, the secure test API correctly returns 401. The original
installed app/authentication and operational PostgreSQL remain unchanged and are
not certified by this test. An actual user acceptance run after authorized
integration/deployment remains a distinct milestone.

## Reproduce without operational services

Prerequisites: existing Docker image pgvector/pgvector:pg16; Python environment
with requirements-evaluation.txt and pytest; Node dashboard dependencies; Edge
and Playwright for optional browser QA. No model download or new vendor service.
Use a new dedicated container or reuse only the labelled test container. Never
substitute operational URL settings. Synthetic test credentials are public fixtures.

```powershell
$env:EIMS_TEST_DATABASE_URL='postgresql+asyncpg://eims_test:eims_synthetic_only@127.0.0.1:55439/eims_integration_test'
python -m pytest tests/test_analyzer_reliability.py tests/test_analyzer_evaluation.py tests/test_analyzer_investigation.py tests/test_analyzer_integration_stability.py tests/test_analyzer_postgres_integration.py -q
python -m uvicorn tests.analyzer_synthetic_demo_app:app --host 127.0.0.1 --port 8019
```

In the dashboard directory, build with NEXT_PUBLIC_EIMS_API_URL set to
http://127.0.0.1:8019, then start with `npm run start -- --hostname 127.0.0.1
--port 3009`. The browser verifier runs from repository root:
`node tools/verify_dashboard_integration.cjs`; EIMS_PLAYWRIGHT_MODULE may identify
an existing Playwright installation. It uses installed Edge without downloading a
browser, restricts page requests to the two loopback ports, uploads only the
existing synthetic hero and saves reports to test-results. Its valid bearer token
is a public synthetic test fixture, never a production credential.

Do not run the PostgreSQL rollback suite concurrently with browser writes into
the same test database: its global before/after row-count assertion assumes no
other writer. No original Docker service was stopped or modified. Test container
and its synthetic browser History are retained separately; no operational rows
or generated installed History were deleted.

## Research application delta

| Principle from prior research | Newly implemented / validated | Still missing |
|---|---|---|
| Findings must trace to source | Actual Dashboard expands persisted bounded normalized evidence; History roundtrip | Complete original file retention is deliberately absent; legacy context may be unavailable |
| Repeatable rule tests | Concurrency, config, outcome and citation regressions plus real PostgreSQL CI | Independently reviewed positive/negative cohort |
| Identity is not causal proof | Generic cause fallback no longer asserts unsupported job failure | Windows taxonomy and environment-specific KB applicability need primary-source research/review |
| Metadata preserves source identity | Sanitized filename collisions rejected before provenance mapping | Installed secure login/user workflow and release acceptance |

No additional vendor claim was researched or asserted this round. Send the
existing bounded Research handoff to ChatGPT; implementation work does not
pretend to replace independent human adjudication.
