# EIMS — Project-wide readiness audit / 31 October 2026

Audited source: `acf024f6466e8bc84c52b107486d74d4a0aafd6d`, PR #10; main `bf634d9ddf86f44220ef961cf4be32988cfc5ee5`. Publication HEAD/CI/tested checkout are recorded in PR #10 after this audit. No main merge. This is a bounded delivery audit, not a new feature phase.

## Module evidence matrix

| Module | Source / implemented features | Existing tests / actual execution | Historical evidence | Gaps / classification |
|---|---|---|---|---|
| Analyzer/RCA | backend/domain/analyzer; native routes, vendor rules, citations, uncertainty | 282 hermetic + 40 PG at baseline CI 41104413703; final CI recorded in PR | Separate September bounded import path | TESTED_IN_ISOLATION; diagnostic quality NOT_MEASURED |
| Authentication/History | backend/api/routers/analyzer; server revocation, current-user ownership | Same 40 PG tests + 18 BFF/PDF checks | Historical A9 does not validate current cookies | TESTED_IN_ISOLATION; HTTPS RUNTIME_NOT_TESTED |
| Dashboard | clients/dashboard; Analyzer/Inventory/Agents/OCR/Evaluations/Timeline/Settings | Typecheck/build in CI; not all-page interaction | September A9 field display | IMPLEMENTED; current browser RUNTIME_NOT_TESTED |
| Asset registry / import | backend/domain/asset_registry; schema/state machine/ingestion | 3 state + 3 ORM + 37 ingestion PASS; 2 mocked health PASS; 3 asset API cases blocked by uninitialized DB dependency | Chapter 4: 49 events / 10 findings, historical baseline c38bef9 | TESTED_IN_ISOLATION for units; HISTORICALLY_FIELD_TESTED; current API/runtime incomplete |
| USB collector/package | clients/usb_auditor; tools/Build-EIMS-USB.ps1; portable JSON/event extraction | Before: 45 PASS/1 FAIL stale path assertion; after test-only correction: 46 PASS | Prior Windows collection described in September report, run SHA not newly established | TESTED_IN_ISOLATION; HISTORICALLY_FIELD_TESTED; latest hardware NOT_TESTED |
| OCR/MinIO | backend/domain/asset_registry/ocr_worker.py; backend/infrastructure/object_store.py | Existing test_ocr_upload_pipeline.py: 2 blocked cases, no accepted runtime result | No fresh field evidence inspected | IMPLEMENTED; RUNTIME_NOT_TESTED |
| Search | backend/domain/search; providers/filtering | test_global_search.py: 1 PASS/8 DB-setup failures; secure owner/search negatives covered in core PG suite | Earlier benchmark evidence is historical only | TESTED_IN_ISOLATION for security; general runtime NOT_TESTED |
| Timeline | backend/domain/timeline; unified event service/UI | test_timeline.py: 8 DB-setup failures | Historical latency claims not rerun | IMPLEMENTED; RUNTIME_NOT_TESTED |
| Service evaluations/customer forms | backend/api/routers/evaluations.py; backend/domain/evaluation | Existing core PG shared-route/current-role negative tests; no dedicated positive customer workflow suite found | No current acceptance evidence | IMPLEMENTED admin paths; customer-scoped workflow DEFERRED |
| Telemetry/Redis/EVTX | backend/domain/telemetry; separate audit PR #6–#9 and new #11 | Not rerun on core; #11 e47cd72 CI 4/4 observed, not included in PR #10 | Historical collector/ingestion not crash-recovery proof | IMPLEMENTED; four recovery XFAIL contracts remain separate; runtime NOT_TESTED |
| Monitoring | deployments/observability | Configuration inspected; no live metric/log pipeline test | None newly validated | IMPLEMENTED configuration; RUNTIME_NOT_TESTED |
| Homelab/cloud/device integration | deployments/homelab, agent/collector code | No IaC apply, physical equipment or network actions | Historical docs only, not universal device support | IMPLEMENTED scaffolding; deployment/expansion DEFERRED |
| Scientific evaluation | evaluation/analyzer; runner/scoring/grounding | Existing binding/review integrity suite; frozen 12 predictions/60 claims compatible | No real human review | TESTED_IN_ISOLATION; SCIENTIFIC_REVIEW_PENDING |

## Bounded execution and failures

[evidence/results.json](evidence/20261031-project-audit/results.json) records per-suite outcomes. API smoke used the original tests under a process-local no-op lifespan, with SQLAlchemy execute/commit/connect explicitly denied. Original startup initializes PostgreSQL/Redis, seeds users and starts workers, so it was not permitted to execute. No auth dependency was bypassed. Result: **46 PASS / 21 FAIL / 0 SKIP**, all 21 failures were `Database Engine invoked prior to initialization lifecycle step.` These are test-setup blockers under the isolated boundary, not evidence of production API correctness or a reproduced production defect. We did not initialize an operational database to make them pass, nor repeatedly rerun this blocked batch. [Reproducer](evidence/20261031-project-audit/run_project_audit.py) must be run from repository root; it deliberately retains these blockers.

USB isolated tests: **45 PASS / 1 FAIL before**, **46 PASS / 0 FAIL after**. `test_builder_never_formats_or_autoselects` expected a literal interpolated target; actual PowerShell now constructs DriveRoot + Join-Path. Corrected only the assertion to check drive root, target and expected target. No collector/launcher production edit; no USB formatting, deployment or collection. CI now runs these 46 offline tests separately from Analyzer counts. No tests above prove physical device acceptance.

## Academic consistency register

| Document | Outdated claim | Verified replacement / source | Human verification |
|---|---|---|---|
| README.md | Graduation Hardening Complete / enterprise-grade | Draft RC with external gates; historical sprint markers; current package versions at acf024f | Owner release designation |
| Chapters 1–2 | RAG-centric objectives/theory read as current experiment | Current multi-vendor investigation objective; M0/M1/Full vs M2/M3 NOT_RUN; old theory retained historically | Advisor scope/methodology approval |
| Chapter 3 | Wider platform architecture read as accepted runtime | Current BFF/session/Analyzer/History workflow and access boundaries, Next 16.3.0/React 19.2.8 | Architecture figures and final layout |
| Chapter 4 | 49 events/10 findings/A9 read as recent Secure Mode proof | Separate current 322-test CI/12 DRAFT/60 claims/0 reviews from September field results | Verify original field dates/source SHAs; independent Gold review |
| Chapter 5 | Prototype conclusions imply project completion | ENGINEERING_RC_WITH_EXTERNAL_GATES and explicit operational/scientific gaps | Final conclusions after real review |
| Abstracts TH/EN | Historical RAG/field validation only | Current abstract revision above retained historical abstract | Select/approve final submitted text |
| Presentation source | Next.js 14, old experiment/demo conclusions | Slides 4/9–12/14–15 aligned to current core; stack Next16.3/React19.2.8; historical USB/ingestion retained | Rebuild and inspect all 15 slides |
| Rehearsal/cue card/editorial/assembly manifest | Old QA/completion statements | Prominent historical/stale notice and current-source pointer | Rewrite speaking notes from revised slides, institutional details |
| Existing DOCX/PDF/PPTX | Rendered September baseline | **STALE_PENDING_REBUILD**, binaries unchanged | Rebuild, inspect every page/slide/figure, approve before submission |

Binary regeneration was not attempted: no repository report/deck builder was found in the inspected tracked tools and no pandoc/LibreOffice converter was found on PATH. We did not install an ad-hoc rendering stack or overwrite accepted historical artifacts. Markdown sources are updated; no visual/structural approval of new binaries is claimed. Use the existing assembly manifest and authoring application, then compare source text, headers/figures/page layout and all 15 slides. Historical editorial baseline is 29 September at c38bef9; do not invent individual field-run dates where absent.

## Final release and operator checklist

- [x] Preserve production code, original snapshots/Gold/HELDOUT, historical binaries and operational data.
- [x] Correct source claims; publish bounded smoke results including failures and limitations.
- [ ] Owner supplies authentic fort_config/esxi_tracker/win_policy judgments (case/claim ID, hash, actual alias/time/rationale). 12 DEV DRAFT / 5 HELDOUT reserved / 0 genuine reviews remain; quality metrics undefined.
- [ ] Owner provides approved trusted HTTPS Dashboard/BFF/backend + dedicated synthetic PostgreSQL/accounts; run existing verify_secure_dashboard.cjs. Prior startup was rejected as blocked by policy; no workaround attempted.
- [ ] Rebuild DOCX/PDF/PPTX, visually inspect and obtain advisor/institutional verification. Do not submit stale binaries as current.
- [ ] Merge only with owner approval: #2 into main, retarget/review/recheck CI on #3, then #4, #5, #10. Green mergeability is not approval. Separate #6→#7→#8→#9→#11 is not automatically included; main remains unchanged.
- [ ] Decide USB/telemetry demonstration scope explicitly. Any current physical installation/runtime testing needs its own authorization and evidence. Preserve backups/source refs; no downgrade/reset/volume deletion or unsafe benchmarks.

No new external research is needed to fix these documentary discrepancies. Highest-value next milestone: genuine three-case review plus hash-bound claim judgments, followed by reviewed-only pilot with explicit support counts; it is not broad multi-vendor accuracy. Final core CI and broader bounded audit remain separate evidence sets.
