# Merge readiness — 30 October 2026

Read-only GitHub inspection. No merge authorization, branch protection acceptance or independent code review is inferred from CI. Comments/reviews below are GitHub-visible metadata, not a completed security audit.

Core stack #2 → #3 → #4 → #5. New delivery branch forks #5; audit stack #6 → #7 → #8 → #9 separately depends on #5. Integrating either line does not validate the other.

Evidence is committed to Git; CI artifacts have workflow retention (core 30 days). Preserve source SHA and download needed artifacts before expiry. No customer logs or credentials should be included.


## PR #2
Head: `cff00082f6905bb733849c2b74733fb50799f662`; base: `main`; draft: False.
Checks: analyzer-hermetic: SUCCESS, dashboard-typecheck-build: SUCCESS. Visible reviews: 0; issue comments: 0.
Changed files (146, paginated):

```text
.gitattributes
.github/workflows/analyzer-reliability.yml
.gitignore
docs/ANALYZER_BASELINE_RESULTS.md
docs/research/ANALYZER_CURRENT_STATE_2026.md
docs/research/ANALYZER_DEV_ADJUDICATION_20261025.md
docs/research/ANALYZER_IMPLEMENTATION_MATRIX_V2_20261025.md
docs/research/ANALYZER_PR2_ENGINEERING_REVIEW_20261025.md
docs/research/ANALYZER_RESEARCH_HANDOFF_20261025.md
docs/research/ANALYZER_WEEK1_AUDIT_2026-10-25.md
evaluation/analyzer/GOLD_PROTOCOL.md
evaluation/analyzer/README.md
evaluation/analyzer/SEMANTICS_V2.md
evaluation/analyzer/gold/REVIEW_QUEUE.md
evaluation/analyzer/gold/cases/bundle_related/a.txt
evaluation/analyzer/gold/cases/bundle_related/b.txt
evaluation/analyzer/gold/cases/bundle_unrelated/a.txt
evaluation/analyzer/gold/cases/bundle_unrelated/b.txt
evaluation/analyzer/gold/cases/esxi_heartbeat/input.txt
evaluation/analyzer/gold/cases/esxi_missing_reserved/input.txt
evaluation/analyzer/gold/cases/esxi_tracker/input.txt
evaluation/analyzer/gold/cases/fort_accept/input.txt
evaluation/analyzer/gold/cases/fort_config/input.txt
evaluation/analyzer/gold/cases/fort_deny_reserved/input.txt
evaluation/analyzer/gold/cases/json_info/input.txt
evaluation/analyzer/gold/cases/noise_filename/veeam_windows.txt
evaluation/analyzer/gold/cases/unknown_truncated_reserved/input.txt
evaluation/analyzer/gold/cases/veeam_options/input.txt
evaluation/analyzer/gold/cases/veeam_outcome_reserved/input.txt
evaluation/analyzer/gold/cases/veeam_tracker/input.txt
evaluation/analyzer/gold/cases/win_auth_reserved/input.txt
evaluation/analyzer/gold/cases/win_boot/input.txt
evaluation/analyzer/gold/cases/win_policy/input.txt
evaluation/analyzer/gold/heldout.v1.lock.json
evaluation/analyzer/gold/manifest.v1.json
evaluation/analyzer/gold/manifest.v1.schema.json
evaluation/analyzer/gold/manifest.v2.dev-draft.json
evaluation/analyzer/gold/manifest.v2.schema.json
evaluation/analyzer/grounding.py
evaluation/analyzer/grounding.v2.schema.json
evaluation/analyzer/inspection.py
evaluation/analyzer/investigation.py
evaluation/analyzer/manual_reviews.schema.json
evaluation/analyzer/manual_reviews.template.json
evaluation/analyzer/results/20261025-V2-RUN-INDEX.md
evaluation/analyzer/results/20261025-controlled-before-full/case_scores.jsonl
evaluation/analyzer/results/20261025-controlled-before-full/claim_grounding_queue.json
evaluation/analyzer/results/20261025-controlled-before-full/config.json
evaluation/analyzer/results/20261025-controlled-before-full/errors.csv
evaluation/analyzer/results/20261025-controlled-before-full/grounding_metrics.json
evaluation/analyzer/results/20261025-controlled-before-full/manual_reviews.json
evaluation/analyzer/results/20261025-controlled-before-full/metrics.json
evaluation/analyzer/results/20261025-controlled-before-full/predictions.jsonl
evaluation/analyzer/results/20261025-controlled-before-m0/case_scores.jsonl
evaluation/analyzer/results/20261025-controlled-before-m0/config.json
evaluation/analyzer/results/20261025-controlled-before-m0/errors.csv
evaluation/analyzer/results/20261025-controlled-before-m0/manual_reviews.json
evaluation/analyzer/results/20261025-controlled-before-m0/metrics.json
evaluation/analyzer/results/20261025-controlled-before-m0/predictions.jsonl
evaluation/analyzer/results/20261025-controlled-before-m1/case_scores.jsonl
evaluation/analyzer/results/20261025-controlled-before-m1/config.json
evaluation/analyzer/results/20261025-controlled-before-m1/errors.csv
evaluation/analyzer/results/20261025-controlled-before-m1/manual_reviews.json
evaluation/analyzer/results/20261025-controlled-before-m1/metrics.json
evaluation/analyzer/results/20261025-controlled-before-m1/predictions.jsonl
evaluation/analyzer/results/20261025-controlled-demo-before/a-veeam.txt
evaluation/analyzer/results/20261025-controlled-demo-before/b-vmware.txt
evaluation/analyzer/results/20261025-controlled-demo-before/config.json
evaluation/analyzer/results/20261025-controlled-demo-before/history_snapshot.json
evaluation/analyzer/results/20261025-controlled-demo-before/inspector.html
evaluation/analyzer/results/20261025-controlled-demo-before/investigation.json
evaluation/analyzer/results/20261025-offline-demo-before/a-veeam.txt
evaluation/analyzer/results/20261025-offline-demo-before/b-vmware.txt
evaluation/analyzer/results/20261025-offline-demo-before/config.json
evaluation/analyzer/results/20261025-offline-demo-before/history_snapshot.json
evaluation/analyzer/results/20261025-offline-demo-before/inspector.html
evaluation/analyzer/results/20261025-offline-demo-before/investigation.json
evaluation/analyzer/results/20261025-offline-demo/a-veeam.txt
evaluation/analyzer/results/20261025-offline-demo/b-vmware.txt
evaluation/analyzer/results/20261025-offline-demo/config.json
evaluation/analyzer/results/20261025-offline-demo/history_snapshot.json
evaluation/analyzer/results/20261025-offline-demo/inspector.html
evaluation/analyzer/results/20261025-offline-demo/investigation.json
evaluation/analyzer/results/20261025-v1-m0-dev-draft/case_scores.jsonl
evaluation/analyzer/results/20261025-v1-m0-dev-draft/config.json
evaluation/analyzer/results/20261025-v1-m0-dev-draft/errors.csv
evaluation/analyzer/results/20261025-v1-m0-dev-draft/manual_reviews.json
evaluation/analyzer/results/20261025-v1-m0-dev-draft/metrics.json
evaluation/analyzer/results/20261025-v1-m0-dev-draft/predictions.jsonl
evaluation/analyzer/results/20261025-v1-m1-dev-draft/case_scores.jsonl
evaluation/analyzer/results/20261025-v1-m1-dev-draft/config.json
evaluation/analyzer/results/20261025-v1-m1-dev-draft/errors.csv
evaluation/analyzer/results/20261025-v1-m1-dev-draft/manual_reviews.json
evaluation/analyzer/results/20261025-v1-m1-dev-draft/metrics.json
evaluation/analyzer/results/20261025-v1-m1-dev-draft/predictions.jsonl
evaluation/analyzer/results/20261025-v1-reviewed-dev/case_scores.jsonl
evaluation/analyzer/results/20261025-v1-reviewed-dev/config.json
evaluation/analyzer/results/20261025-v1-reviewed-dev/errors.csv
evaluation/analyzer/results/20261025-v1-reviewed-dev/manual_reviews.json
evaluation/analyzer/results/20261025-v1-reviewed-dev/metrics.json
evaluation/analyzer/results/20261025-v1-reviewed-dev/predictions.jsonl
evaluation/analyzer/results/20261025-v2-before-full/case_scores.jsonl
evaluation/analyzer/results/20261025-v2-before-full/claim_grounding_queue.json
evaluation/analyzer/results/20261025-v2-before-full/config.json
evaluation/analyzer/results/20261025-v2-before-full/errors.csv
evaluation/analyzer/results/20261025-v2-before-full/grounding_metrics.json
evaluation/analyzer/results/20261025-v2-before-full/manual_reviews.json
evaluation/analyzer/results/20261025-v2-before-full/metrics.json
evaluation/analyzer/results/20261025-v2-before-full/predictions.jsonl
evaluation/analyzer/results/20261025-v2-before-m0/case_scores.jsonl
evaluation/analyzer/results/20261025-v2-before-m0/config.json
evaluation/analyzer/results/20261025-v2-before-m0/errors.csv
evaluation/analyzer/results/20261025-v2-before-m0/manual_reviews.json
evaluation/analyzer/results/20261025-v2-before-m0/metrics.json
evaluation/analyzer/results/20261025-v2-before-m0/predictions.jsonl
evaluation/analyzer/results/20261025-v2-before-m1/case_scores.jsonl
evaluation/analyzer/results/20261025-v2-before-m1/config.json
evaluation/analyzer/results/20261025-v2-before-m1/errors.csv
evaluation/analyzer/results/20261025-v2-before-m1/manual_reviews.json
evaluation/analyzer/results/20261025-v2-before-m1/metrics.json
evaluation/analyzer/results/20261025-v2-before-m1/predictions.jsonl
evaluation/analyzer/results/20261025-v2-reviewed-empty/case_scores.jsonl
evaluation/analyzer/results/20261025-v2-reviewed-empty/claim_grounding_queue.json
evaluation/analyzer/results/20261025-v2-reviewed-empty/config.json
evaluation/analyzer/results/20261025-v2-reviewed-empty/errors.csv
evaluation/analyzer/results/20261025-v2-reviewed-empty/grounding_metrics.json
evaluation/analyzer/results/20261025-v2-reviewed-empty/manual_reviews.json
evaluation/analyzer/results/20261025-v2-reviewed-empty/metrics.json
evaluation/analyzer/results/20261025-v2-reviewed-empty/predictions.jsonl
evaluation/analyzer/results/20261025-v2-role-before-full/case_scores.jsonl
evaluation/analyzer/results/20261025-v2-role-before-full/claim_grounding_queue.json
evaluation/analyzer/results/20261025-v2-role-before-full/config.json
evaluation/analyzer/results/20261025-v2-role-before-full/errors.csv
evaluation/analyzer/results/20261025-v2-role-before-full/grounding_metrics.json
evaluation/analyzer/results/20261025-v2-role-before-full/manual_reviews.json
evaluation/analyzer/results/20261025-v2-role-before-full/metrics.json
evaluation/analyzer/results/20261025-v2-role-before-full/predictions.jsonl
evaluation/analyzer/runner.py
evaluation/analyzer/scoring.py
evaluation/analyzer/semantics_v2.py
requirements-evaluation.txt
tests/test_analyzer_evaluation.py
tests/test_analyzer_investigation.py
tools/demo_analyzer_investigation.py
tools/eval_analyzer.py
tools/review_analyzer_case.py
```

Evaluation infrastructure: engineering merge need not wait for human labels. No production migration. Review baseline immutability and large artifact diff.
Unexpected scope: no automatic clean bill from file names; #5 cross-domain scope and #6–#9 deployment changes need dedicated review.
Authorization: owner merge approval required; rerun CI after each retarget/merge.


## PR #3
Head: `5810a259995eaf39d47f4c212c5a58cb5b0ec0d0`; base: `work/analyzer-week1-evaluation-2026-10-25`; draft: False.
Checks: analyzer-hermetic: SUCCESS, dashboard-typecheck-build: SUCCESS. Visible reviews: 0; issue comments: 0.
Changed files (32, paginated):

```text
backend/domain/analyzer/services/bundle.py
backend/domain/analyzer/services/event_knowledge.py
backend/domain/analyzer/services/incident_extract.py
backend/domain/analyzer/services/summary.py
docs/research/ANALYZER_CORRECTNESS_20261025.md
evaluation/analyzer/results/20261025-controlled-after-full/case_scores.jsonl
evaluation/analyzer/results/20261025-controlled-after-full/claim_grounding_queue.json
evaluation/analyzer/results/20261025-controlled-after-full/config.json
evaluation/analyzer/results/20261025-controlled-after-full/errors.csv
evaluation/analyzer/results/20261025-controlled-after-full/grounding_metrics.json
evaluation/analyzer/results/20261025-controlled-after-full/manual_reviews.json
evaluation/analyzer/results/20261025-controlled-after-full/metrics.json
evaluation/analyzer/results/20261025-controlled-after-full/predictions.jsonl
evaluation/analyzer/results/20261025-controlled-after-m0/case_scores.jsonl
evaluation/analyzer/results/20261025-controlled-after-m0/config.json
evaluation/analyzer/results/20261025-controlled-after-m0/errors.csv
evaluation/analyzer/results/20261025-controlled-after-m0/manual_reviews.json
evaluation/analyzer/results/20261025-controlled-after-m0/metrics.json
evaluation/analyzer/results/20261025-controlled-after-m0/predictions.jsonl
evaluation/analyzer/results/20261025-controlled-after-m1/case_scores.jsonl
evaluation/analyzer/results/20261025-controlled-after-m1/config.json
evaluation/analyzer/results/20261025-controlled-after-m1/errors.csv
evaluation/analyzer/results/20261025-controlled-after-m1/manual_reviews.json
evaluation/analyzer/results/20261025-controlled-after-m1/metrics.json
evaluation/analyzer/results/20261025-controlled-after-m1/predictions.jsonl
evaluation/analyzer/results/20261025-controlled-demo-after/a-veeam.txt
evaluation/analyzer/results/20261025-controlled-demo-after/b-vmware.txt
evaluation/analyzer/results/20261025-controlled-demo-after/config.json
evaluation/analyzer/results/20261025-controlled-demo-after/history_snapshot.json
evaluation/analyzer/results/20261025-controlled-demo-after/inspector.html
evaluation/analyzer/results/20261025-controlled-demo-after/investigation.json
tests/test_analyzer_reliability.py
```

Analyzer behavior fixes: preserve failure/identity/cause distinctions. No new DB migration. Human accuracy remains unmeasured.
Unexpected scope: no automatic clean bill from file names; #5 cross-domain scope and #6–#9 deployment changes need dedicated review.
Authorization: owner merge approval required; rerun CI after each retarget/merge.


## PR #4
Head: `443676bf38af12c209091bd2838de0a0e3b27710`; base: `codex/analyzer-evidence-correctness-20261025`; draft: False.
Checks: analyzer-hermetic: SUCCESS, analyzer-postgres-integration: SUCCESS, dashboard-typecheck-build: SUCCESS. Visible reviews: 0; issue comments: 0.
Changed files (25, paginated):

```text
.github/workflows/analyzer-reliability.yml
backend/api/routers/analyzer/analyze.py
backend/api/routers/analyzer/history.py
backend/domain/analyzer/schemas/analyze.py
backend/domain/analyzer/services/bundle.py
backend/domain/analyzer/services/summary.py
clients/dashboard/src/components/AnalysisResultDetail.tsx
clients/dashboard/src/components/EvidenceSourceReview.tsx
docs/research/GRADUATION_DEFENSE_UPDATE_20261025.md
docs/research/GRADUATION_INTEGRATION_20261025.md
docs/research/evidence/20261025-dashboard/dashboard-browser-report.json
docs/research/evidence/20261025-dashboard/dashboard-evidence-dark-history.png
docs/research/evidence/20261025-dashboard/dashboard-evidence-light.png
evaluation/analyzer/results/20261025-graduation-full/case_scores.jsonl
evaluation/analyzer/results/20261025-graduation-full/claim_grounding_queue.json
evaluation/analyzer/results/20261025-graduation-full/config.json
evaluation/analyzer/results/20261025-graduation-full/errors.csv
evaluation/analyzer/results/20261025-graduation-full/grounding_metrics.json
evaluation/analyzer/results/20261025-graduation-full/manual_reviews.json
evaluation/analyzer/results/20261025-graduation-full/metrics.json
evaluation/analyzer/results/20261025-graduation-full/predictions.jsonl
tests/analyzer_synthetic_demo_app.py
tests/test_analyzer_integration_stability.py
tests/test_analyzer_postgres_integration.py
tools/verify_dashboard_integration.cjs
```

History/evidence viewer and PostgreSQL integration: owner scope and stored evidence require review. Browser evidence does not certify later secure session changes.
Unexpected scope: no automatic clean bill from file names; #5 cross-domain scope and #6–#9 deployment changes need dedicated review.
Authorization: owner merge approval required; rerun CI after each retarget/merge.


## PR #5
Head: `f777e9c5c085e1db366b410f0ea07ed6d2a82472`; base: `codex/graduation-integration-20261025`; draft: True.
Checks: analyzer-hermetic: SUCCESS, analyzer-postgres-integration: SUCCESS, dashboard-typecheck-build: SUCCESS. Visible reviews: 0; issue comments: 0.
Changed files (122, paginated):

```text
.github/workflows/analyzer-reliability.yml
backend/api/routers/analyzer/admin.py
backend/api/routers/analyzer/analyze.py
backend/api/routers/analyzer/auth.py
backend/api/routers/analyzer/feedback.py
backend/api/routers/analyzer/obsidian.py
backend/api/routers/analyzer/stats.py
backend/api/routers/evaluations.py
backend/domain/analyzer/auth.py
backend/domain/analyzer/models/session.py
backend/domain/analyzer/services/evidence_privacy.py
backend/domain/analyzer/services/incident_extract.py
backend/domain/analyzer/services/observed_summary.py
backend/domain/analyzer/services/session_maintenance.py
backend/domain/analyzer/services/session_security.py
backend/domain/analyzer/services/summary.py
backend/domain/analyzer/services/vector_db.py
backend/domain/analyzer/services/vendor_knowledge.py
backend/domain/asset_registry/audit_controller.py
backend/domain/asset_registry/controller.py
backend/domain/search/controller.py
backend/domain/search/providers/analysis_provider.py
backend/domain/search/service.py
backend/domain/telemetry/controller.py
backend/domain/telemetry/query_controller.py
backend/domain/telemetry/security.py
backend/domain/telemetry/ws_controller.py
backend/domain/timeline/controller.py
clients/dashboard/src/app/analyzer/page.tsx
clients/dashboard/src/app/api/eims/[...path]/route.ts
clients/dashboard/src/app/api/session/login/route.ts
clients/dashboard/src/app/api/session/logout/route.ts
clients/dashboard/src/components/AnalysisResultDetail.tsx
clients/dashboard/src/components/AnalyzerHistoryList.tsx
clients/dashboard/src/components/AnalyzerSession.tsx
clients/dashboard/src/components/EvidenceSourceReview.tsx
clients/dashboard/src/lib/api.ts
clients/dashboard/src/lib/login-gate.ts
clients/dashboard/src/lib/report-data.ts
clients/dashboard/src/lib/session-proxy.ts
docs/research/ANALYZER_IMPLEMENTATION_MATRIX_V2_20261025.md
docs/research/ANALYZER_RESEARCH_HANDOFF_20261025.md
docs/research/CONTINUATION_20261026.md
docs/research/GRADUATION_DEFENSE_UPDATE_20261025.md
docs/research/GROUNDED_DIAGNOSIS_CHECKPOINT_20261025.md
docs/research/NEXT_EXECUTION_PROMPT_20261026.md
docs/research/SECURE_ANALYZER_CHECKPOINT_20261025.md
docs/research/SESSION_LIFECYCLE_GATE_20261025.md
docs/research/evidence/20261025-grounded/HUMAN_REVIEW_PACKET_TH.md
docs/research/evidence/20261025-grounded/before-after.json
docs/research/evidence/20261025-grounded/esxi_tracker.html
docs/research/evidence/20261025-grounded/fort_config.html
docs/research/evidence/20261025-grounded/migration-rehearsal.xml
docs/research/evidence/20261025-grounded/semantic-before.xml
docs/research/evidence/20261025-grounded/semantic-combined.xml
docs/research/evidence/20261025-grounded/win_policy.html
docs/research/evidence/20261025-lifecycle/acceptance-status.json
docs/research/evidence/20261025-lifecycle/lifecycle-combined.xml
docs/research/evidence/20261025-lifecycle/review/README.md
docs/research/evidence/20261025-lifecycle/review/esxi_tracker.html
docs/research/evidence/20261025-lifecycle/review/fort_config.html
docs/research/evidence/20261025-lifecycle/review/win_policy.html
docs/research/evidence/20261025-lifecycle/session-migration-offline.sql
docs/research/evidence/20261025-lifecycle/session-proxy-live.json
docs/research/evidence/20261025-lifecycle/session-proxy-unit.json
docs/research/evidence/20261025-lifecycle/snapshot-comparison.json
docs/research/evidence/20261025-session/acceptance-status.json
docs/research/evidence/20261025-session/review/README.md
docs/research/evidence/20261025-session/review/esxi_tracker.html
docs/research/evidence/20261025-session/review/fort_config.html
docs/research/evidence/20261025-session/review/win_policy.html
docs/research/evidence/20261025-session/session-proxy-live.json
docs/research/evidence/20261025-session/session-proxy-unit.json
docs/research/evidence/20261026-continuation/continuation-20261026.xml
docs/research/evidence/20261026-continuation/full-lineage-test.xml
docs/research/evidence/20261026-continuation/terminal-before.xml
evaluation/analyzer/candidates/counterexamples-20261026.json
evaluation/analyzer/candidates/terminal-outcomes-20261025.json
evaluation/analyzer/results/20261025-grounded-diagnosis-full/case_scores.jsonl
evaluation/analyzer/results/20261025-grounded-diagnosis-full/claim_grounding_queue.json
evaluation/analyzer/results/20261025-grounded-diagnosis-full/config.json
evaluation/analyzer/results/20261025-grounded-diagnosis-full/errors.csv
evaluation/analyzer/results/20261025-grounded-diagnosis-full/grounding_metrics.json
evaluation/analyzer/results/20261025-grounded-diagnosis-full/manual_reviews.json
evaluation/analyzer/results/20261025-grounded-diagnosis-full/metrics.json
evaluation/analyzer/results/20261025-grounded-diagnosis-full/predictions.jsonl
evaluation/analyzer/results/20261025-secure-checkpoint-full/case_scores.jsonl
evaluation/analyzer/results/20261025-secure-checkpoint-full/claim_grounding_queue.json
evaluation/analyzer/results/20261025-secure-checkpoint-full/config.json
evaluation/analyzer/results/20261025-secure-checkpoint-full/errors.csv
evaluation/analyzer/results/20261025-secure-checkpoint-full/grounding_metrics.json
evaluation/analyzer/results/20261025-secure-checkpoint-full/manual_reviews.json
evaluation/analyzer/results/20261025-secure-checkpoint-full/metrics.json
evaluation/analyzer/results/20261025-secure-checkpoint-full/predictions.jsonl
evaluation/analyzer/results/20261025-session-lifecycle-full/case_scores.jsonl
evaluation/analyzer/results/20261025-session-lifecycle-full/claim_grounding_queue.json
evaluation/analyzer/results/20261025-session-lifecycle-full/config.json
evaluation/analyzer/results/20261025-session-lifecycle-full/errors.csv
evaluation/analyzer/results/20261025-session-lifecycle-full/grounding_metrics.json
evaluation/analyzer/results/20261025-session-lifecycle-full/manual_reviews.json
evaluation/analyzer/results/20261025-session-lifecycle-full/metrics.json
evaluation/analyzer/results/20261025-session-lifecycle-full/predictions.jsonl
evaluation/analyzer/results/20261026-counterexamples/config.json
evaluation/analyzer/results/20261026-counterexamples/predictions.json
evaluation/analyzer/results/20261026-terminal-scope-full/case_scores.jsonl
evaluation/analyzer/results/20261026-terminal-scope-full/claim_grounding_queue.json
evaluation/analyzer/results/20261026-terminal-scope-full/config.json
evaluation/analyzer/results/20261026-terminal-scope-full/errors.csv
evaluation/analyzer/results/20261026-terminal-scope-full/grounding_metrics.json
evaluation/analyzer/results/20261026-terminal-scope-full/manual_reviews.json
evaluation/analyzer/results/20261026-terminal-scope-full/metrics.json
evaluation/analyzer/results/20261026-terminal-scope-full/predictions.jsonl
migrations/env.py
migrations/versions/e1a202610250_revocable_analyzer_sessions.py
tests/analyzer_synthetic_demo_app.py
tests/test_analyzer_integration_stability.py
tests/test_analyzer_postgres_integration.py
tests/test_analyzer_reliability.py
tools/maintain_analyzer_sessions.py
tools/run_analyzer_counterexamples.py
tools/test_session_proxy.cjs
tools/verify_secure_dashboard.cjs
```

Cross-domain auth, telemetry, assets, evaluations and search changes extend beyond Analyzer. Expected from security scope but require explicit owner acceptance. Auth migration/deployment and trusted browser remain gates. Draft stays Draft.
Unexpected scope: no automatic clean bill from file names; #5 cross-domain scope and #6–#9 deployment changes need dedicated review.
Authorization: owner merge approval required; rerun CI after each retarget/merge.


## PR #6
Head: `28c5e5f97de3791be73cfd4449da2742efea3460`; base: `codex/secure-analyzer-session-20261025`; draft: True.
Checks: analyzer-hermetic: SUCCESS, analyzer-postgres-integration: SUCCESS, dashboard-typecheck-build: SUCCESS, telemetry-reliability: SUCCESS. Visible reviews: 0; issue comments: 0.
Changed files (8, paginated):

```text
.github/workflows/analyzer-reliability.yml
backend/domain/telemetry/broker.py
backend/domain/telemetry/worker.py
docs/research/TELEMETRY_INFRA_AUDIT_20261026.md
tests/test_compose_security_audit.py
tests/test_telemetry_fail_closed.py
tests/test_telemetry_recovery_contracts.py
tools/audit_compose_security.py
```

Separate telemetry/Compose audit scope; not adopted into graduation delivery checkout. Green checks do not certify operational recovery. Review own audit report and deployment assumptions before integration.
Unexpected scope: no automatic clean bill from file names; #5 cross-domain scope and #6–#9 deployment changes need dedicated review.
Authorization: owner merge approval required; rerun CI after each retarget/merge.


## PR #7
Head: `e6f248748a758111ba69f430388462d58d23d1c3`; base: `audit/telemetry-reliability-20261026`; draft: True.
Checks: analyzer-hermetic: SUCCESS, analyzer-postgres-integration: SUCCESS, dashboard-typecheck-build: SUCCESS, telemetry-reliability: SUCCESS. Visible reviews: 0; issue comments: 0.
Changed files (4, paginated):

```text
.github/workflows/analyzer-reliability.yml
backend/domain/telemetry/controller.py
docs/research/EVTX_QUEUE_ACCEPTANCE_20261028.md
tests/test_evtx_queue_fail_closed.py
```

Separate telemetry/Compose audit scope; not adopted into graduation delivery checkout. Green checks do not certify operational recovery. Review own audit report and deployment assumptions before integration.
Unexpected scope: no automatic clean bill from file names; #5 cross-domain scope and #6–#9 deployment changes need dedicated review.
Authorization: owner merge approval required; rerun CI after each retarget/merge.


## PR #8
Head: `133dfa55a47dc421917372a101b172c8df4cb328`; base: `audit/evtx-queue-failclosed-20261028`; draft: True.
Checks: analyzer-hermetic: SUCCESS, analyzer-postgres-integration: SUCCESS, dashboard-typecheck-build: SUCCESS, telemetry-reliability: SUCCESS. Visible reviews: 0; issue comments: 0.
Changed files (4, paginated):

```text
.github/workflows/analyzer-reliability.yml
backend/domain/telemetry/evtx_worker.py
docs/research/EVTX_WORKER_FAULT_BOUNDARY_20261029.md
tests/test_evtx_worker_fault_contracts.py
```

Separate telemetry/Compose audit scope; not adopted into graduation delivery checkout. Green checks do not certify operational recovery. Review own audit report and deployment assumptions before integration.
Unexpected scope: no automatic clean bill from file names; #5 cross-domain scope and #6–#9 deployment changes need dedicated review.
Authorization: owner merge approval required; rerun CI after each retarget/merge.


## PR #9
Head: `90324cf9925bc556b77235cef2e386b1bf97a6ab`; base: `audit/evtx-worker-fault-boundary-20261029`; draft: True.
Checks: analyzer-hermetic: SUCCESS, analyzer-postgres-integration: SUCCESS, dashboard-typecheck-build: SUCCESS, telemetry-reliability: SUCCESS. Visible reviews: 0; issue comments: 0.
Changed files (3, paginated):

```text
docs/research/COMPOSE_SECURE_GATE_BOUNDARIES_20261030.md
tests/test_compose_security_audit.py
tools/audit_compose_security.py
```

Separate telemetry/Compose audit scope; not adopted into graduation delivery checkout. Green checks do not certify operational recovery. Review own audit report and deployment assumptions before integration.
Unexpected scope: no automatic clean bill from file names; #5 cross-domain scope and #6–#9 deployment changes need dedicated review.
Authorization: owner merge approval required; rerun CI after each retarget/merge.
