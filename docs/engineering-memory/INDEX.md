# EIMS Engineering Memory Index

**Active infrastructure (2026-11-19):** [Local-First Infrastructure Necessity Audit](../architecture/LOCAL_FIRST_INFRASTRUCTURE_AUDIT.md) → implemented: [Consolidation Acceptance](../acceptance/LOCAL_FIRST_INFRASTRUCTURE_CONSOLIDATION_ACCEPTANCE.md), [Local Operations Runbook](../operations/LOCAL_OPERATIONS_RUNBOOK.md).

**Current authoritative snapshot:** [2026-11-16 — Incident Ingestion v1.1 Acceptance](2026-11-16-incident-ingest-v11-acceptance.md)

**Previous snapshot:** [2026-11-16 — Relay Finalization + Incident Core v1.1 Prep](2026-11-16-relay-finalization-and-v11-prep.md)

**Latest implementation record (not yet verified):** [2026-11-16 — Incident Core v1.1 Ingestion implementation](2026-11-16-incident-core-v11-ingestion-implementation.md)

**Previous snapshot:** [2026-11-16 — Auto Job Relay (Chat_HAND V6)](2026-11-16-auto-job-relay.md)

**Previous snapshot:** [2026-11-16 — DWB Orchestration and Incident Core Review](2026-11-16-orchestration-and-incident-review.md)

**Previous snapshot:** [2026-11-16 — Incident Core v1 (backend-only)](2026-11-16-incident-core-v1.md)

**Previous snapshot:** [2026-11-16 — Reviewer Audit and Synthetic DB Acceptance](2026-11-16-reviewer-audit-synthetic-db-acceptance.md)

**Earlier snapshot:** [2026-11-15 — Final Readiness](2026-11-15-final-readiness.md)

**Earlier snapshot:** [2026-11-15 — Health Monitor Verification](2026-11-15-health-monitor-verification.md)

**Earlier snapshot:** [2026-11-15 — Health Monitor Coalescing](2026-11-15-health-monitor-coalescing.md)

**Older snapshot:** [2026-11-15 — Analyzer Pool Starvation](2026-11-15-analyzer-pool-starvation.md)

**Historical snapshot:** [2026-11-15 — Database Health Probe](2026-11-15-database-health-probe.md)

## Rules

- Treat each dated snapshot as immutable historical evidence. Append a new dated snapshot for later work; do not rewrite prior snapshots to make history look current.
- The current acceptance state lives in `EIMS_ACCEPTANCE_LEDGER.md`.
- The current operational sequence and safety constraints live in `EIMS_OPERATIONAL_HANDOFF.md`.
- This index is a pointer, not a replacement for either ledger.
- Before implementation, read this index, the current snapshot, the operational handoff, and the acceptance ledger.

- 2026-11-15 finalization — Knowledge revalidation lifecycle, JWT exp boundary and synthetic PostgreSQL 16 PITR rehearsal: `2026-11-15-finalization-lifecycle-jwt-pitr.md`.

- 2026-11-15 finalization — Knowledge Lifecycle UI, official vendor source candidates and static Event Knowledge safety: `2026-11-15-knowledge-ui-vendor-candidates-event-safety.md`.

- Operations readiness — PostgreSQL offsite backup/PITR runbook and BIA decision record for owner-approved RPO/RTO: `../operations/postgresql-offsite-backup-recovery-runbook.md`, `../operations/eims-bia-rpo-rto-decision-record.md`.

- 2026-11-15 — Database-backed vendor source candidates, review API, Admin UI, hash-aware import and browser acceptance extensions: `2026-11-15-database-backed-knowledge-sources.md`.

- 2026-11-15 — Reviewer capability, Engineer-readable source/audit surfaces, catalogue hash semantics and Settings preview correction: `2026-11-15-reviewer-capability-source-provenance.md`.


- **AI tooling registry (verified 2026-11-15):** `../../AI_TOOLING_INVENTORY.md` — machine AI applications, live Claude MCP status, configured-vs-connected distinctions, role boundaries, and refresh procedure.
- **New-chat continuation prompt:** `NEW_CHAT_CONTINUATION_PROMPT.md` — copy into a new ChatGPT conversation after attaching/opening the EIMS repository context.

- 2026-11-16 — Reviewer grant/revoke audit, non-superuser PostgreSQL migration/import/API acceptance, and current Browser gate boundary: `2026-11-16-reviewer-audit-synthetic-db-acceptance.md`.

- 2026-11-16 — Backend-only Incident Core v1, deterministic correlation, migration `b8d3f5c1a720`, non-superuser disposable PostgreSQL acceptance: `2026-11-16-incident-core-v1.md`.

- 2026-11-16 — Auto Job Relay (Chat_HAND V6): detached runner, durable job store, background monitor, bounded `jobs.wait`, chunked result retrieval, delivery ledger, three-round independent review: `2026-11-16-auto-job-relay.md`.

- 2026-11-16 — Relay finalization: 18-tool surface verified, symlink case disposition, hard-link residual, writer mode BLOCKED on human approval; Incident Core v1.1 trace recovered and plan written: `2026-11-16-relay-finalization-and-v11-prep.md`.

- 2026-11-16 — Incident Core v1.1 architecture trace (recovered read-only evidence, job `3ef58a7d…`): `2026-11-16-incident-core-v11-architecture-trace.md`.

- 2026-11-16 — Incident Core v1.1 implementation plan (event-to-incident ingestion, outbox decision, open decisions): `2026-11-16-incident-core-v11-plan.md`.

- 2026-11-16 — Incident Ingestion v1.1 acceptance: outbox + async consumer verified on isolated PostgreSQL/Redis, 113 tests passed, migration `c4e8a1f7b932` upgrade/downgrade, independent review ACCEPTED: `2026-11-16-incident-ingest-v11-acceptance.md`.

- 2026-11-19 — Knowledge Foundation / Incident Core architecture alignment (not yet accepted): `2026-11-19-knowledge-incident-architecture-alignment.md`.
