# Official vendor source candidates — v1

Snapshot date: 2026-11-15

This is a **source-candidate catalogue**, not an approved Knowledge corpus and not an incident-derived remediation library.

## Current inventory

20 candidates across four vendor families:

- Microsoft (5): Event 4625, Event 4740, Advanced Audit Policy, Event 1129, Event 6005
- Broadcom VMware (6): VM network connectivity, post-upgrade/physical network mapping, FC/iSCSI/NFS storage, CTK unlink result 2620, missing snapshot file/revert and consolidation
- Veeam Backup & Replication 13 (4): backup health check, SureBackup recovery verification, backup verification, failed session/task log retrieval
- Fortinet (5): event logs, packet-flow diagnostics, IPsec in HA, forward traffic log ID 0000000013, configuration object log ID 0100044547

Structured data: `official-vendor-candidates.v1.json`.

## Trust and promotion rules

Every record is marked `pending_domain_review` and `candidate_only_not_approved_knowledge`.

These records:
- MUST NOT be inserted into `knowledge_entries` as approved records.
- MUST NOT be returned by exact-identity Knowledge Retrieval.
- MUST NOT be represented as proof of a local incident root cause.
- MUST NOT be treated as a vendor-independent fix.
- MUST be reviewed against the exact product, build, topology, prerequisites and observed incident evidence.

Promotion requires a real authorized incident or independently verified operational case, source-history provenance, a human reviewer who did not author the proposal, risk classification, safe prerequisites, validation, rollback, and evidence that the cited source actually applies.

High/Critical remediation must include concrete validation and rollback steps. If the official source describes only diagnosis and does not prescribe a safe fix, the candidate remains diagnostic guidance; a reviewer must not invent a repair and attribute it to the vendor.

## Important applicability boundaries

- Microsoft Event 4625 means a logon attempt failed; the event alone does not prove brute force or identify the cause. Interpret Status/SubStatus, LogonType, source and process context.
- Microsoft Event 4740 confirms an account lockout; Caller Computer Name and correlated events are evidence to investigate, not proof of a human actor.
- Broadcom KB 450303 is limited to the documented host-connectivity failure after hardware change/upgrade. Validate cabling, VLAN and vmnic/vmk mapping before physical changes.
- Broadcom KB 324542 is a troubleshooting guide for VM connectivity symptoms, not a single-cause diagnosis.
- Broadcom KB 309348 spans FC/iSCSI/NFS; validate protocol, array, fabric and host versions.
- Veeam Backup Health Check verifies the latest restore point in the chain; it is not a substitute for application recovery testing.
- SureBackup full recoverability testing requires an isolated test design; VM boot alone does not prove business-service recovery.
- FortiOS 8.0.0 guidance must not be applied to another firmware train without checking that release's documentation and feature behavior.
- FortiGate debug flow can generate substantial logs and may not observe NP6/NP7 offloaded traffic. Use bounded, filtered diagnostics and stop/reset them afterwards.

## Revalidation

No arbitrary 30/90/180-day review interval is assigned. Trigger a revalidation when the vendor revises the source, product reaches EOL, supported build changes, security advisories affect applicability, topology/prerequisites change, or actual usage feedback contradicts the candidate.

## Research sources

All source URLs in the JSON point to official vendor documentation or official vendor support knowledge bases:

- Microsoft Learn — Event 4625, Event 4740, Advanced Audit Policy, Event 1129 Group Policy troubleshooting and Event 6005 reboot correlation
- Broadcom Knowledge Base — KB 450303, 324542, 309348, 442155 (CTK unlink/result 2620), 424591 (snapshot revert missing file) and 343510 (snapshot consolidation)
- Veeam Help Center — VBR 13 Backup Health Check, SureBackup, backup verification and REST API session/task logs
- Fortinet Document Library / Fortinet Community — FortiOS event logs, debug flow, IPsec HA, traffic log ID 0000000013 and configuration object log ID 0100044547

Research findings are snapshots. Re-check the live vendor page and installed product build before any operational action.

## Database-backed review workflow

The application stores source references in the separate `knowledge_source_candidates` table and append-only review/import events in `knowledge_source_events`. These tables are intentionally separate from `knowledge_entries` and are never queried by the Analyzer's approved-Knowledge retrieval path.

The authenticated Engineer read surface and Knowledge Reviewer write workflow supports:
- vendor/product/version-scope filtering and source detail inspection
- verification of a vendor reference, rejection, withdrawal and event-triggered revalidation
- reviewer identity, timestamp, rationale and catalogue-record SHA-256
- audit history for imports, source revisions and review decisions

A `verified_reference` means only that a reviewer checked the vendor source and its stated scope. It does not certify a local root cause, validate an organization-specific remediation, or publish an Engineer-reusable KnowledgeEntry.

### Import controls

`tools/import_knowledge_source_candidates.py` validates the versioned JSON catalogue and is dry-run by default:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python tools/import_knowledge_source_candidates.py
```

The write path is deliberately restricted to an explicitly supplied loopback PostgreSQL test URL, the `eims_test` database user, a non-operational port, and an exact database-name allowlist. It never reads the application's `DATABASE_URL`:

```powershell
$env:EIMS_SOURCE_CATALOGUE_DATABASE_URL = $env:EIMS_TEST_DATABASE_URL
$env:EIMS_SOURCE_CATALOGUE_IMPORT_ALLOWED_DATABASES = "eims_regression_test_20261115"
python tools/import_knowledge_source_candidates.py --apply
```

Only use `--apply` after verifying that the explicit URL targets an isolated synthetic database and the new Alembic migration has been applied. Re-running the same catalogue is idempotent. A changed canonical catalogue-record hash creates an audit event and moves a previously reviewed candidate to `revalidation_required`; it never silently retains a prior verification. This is a hash of the curated JSON record, not the live Vendor webpage or downloaded document bytes. Upstream Vendor changes still require a fresh source check.

This importer is a development/test bootstrap, not a production data-import mechanism. Production migration and catalogue seeding require the organization's approved deployment identity, database target and change controls.
