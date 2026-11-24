# EIMS PostgreSQL offsite backup and recovery runbook

Status: **prepared; external target not provisioned or witnessed**. Operations approval is required before production use.

## 1. Recovery boundary

A valid recovery set consists of:
1. A verified PostgreSQL base backup.
2. Continuous, gap-free WAL from backup start through the selected recovery target.
3. Recoverable encryption keys and credentials.
4. A restore test on infrastructure independent of the failed primary host.

A TAR of /data/docker is not a PostgreSQL base backup/WAL/PITR set.

## 2. Failure-domain requirement

The destination MUST be outside the primary EIMS host and storage failure domain. A second directory, Docker volume or disk on the same host is not offsite.

The Operations Owner must record provider/site/region, storage account/container, immutable namespace, network path, failure-domain relationship, owner/escalation contact, and whether one compromised credential can delete both primary and backup.

The destination provider is intentionally not assumed. Candidate patterns include a separately administered object-storage account/site, independent backup appliance, or remote repository with immutable retention.

## 3. Security controls

Before enabling scheduled backups, approve:
- TLS in transit; encryption at rest (provider-managed or client-side).
- Independent key custody and tested key recovery.
- Separate backup-writer and restore-reader identities.
- Least privilege; backup writer must not have unrestricted delete/admin rights.
- Immutable/WORM retention or equivalent ransomware protection.
- Versioning, access audit logs and alerting on retention changes/deletion attempts.
- Secret rotation, escrow and restore-team access.
- Network restrictions to authorized backup/restore hosts.

Never store plaintext credentials in scripts, Git, logs or this runbook.

## 4. PostgreSQL architecture

Use PostgreSQL-native base backup plus continuous WAL archiving, or a supported manager such as pgBackRest/WAL-G configured for the selected remote repository. Do not use ad-hoc shell copies of live PostgreSQL data files.

Document:
- PostgreSQL major/minor version and extension inventory.
- Base-backup method, manifest and checksum verification.
- WAL archive method, sequence continuity and archive retry behavior.
- WAL backlog alerting and failure escalation.
- Retention and WAL coverage for every retained base backup.
- Encryption/key recovery and restore-target selection.
- Monitoring for last successful base backup, last archived WAL, archive failure count and oldest recoverable point.

A successful backup command or manifest check is not proof of recoverability; a restore drill is mandatory.

## 5. Backup acceptance checks

Record backup ID, UTC start/end, PostgreSQL version, manifest/checksum result, WAL start/stop LSN, first/last archived segment, archive failures/retries, remote object/version IDs, immutable-retention state, encryption-key reference, size, duration, transfer rate and monitoring/alert result.

Acceptance fails if the backup is incomplete, WAL has a gap, destination shares the primary failure domain, keys cannot be recovered, retention can be bypassed by the writer, or no restore has been performed.

## 6. Isolated restore/PITR drill

1. Declare test incident and record requested recovery target.
2. Retrieve backup/WAL using separate restore identity.
3. Verify manifest and checksums.
4. Restore to an isolated compatible PostgreSQL instance with no production route.
5. Configure WAL retrieval and the approved timestamp/LSN/named restore point.
6. Start recovery; retain PostgreSQL logs.
7. Verify recovery reaches the intended target and promotes cleanly.
8. Prove the boundary with one known transaction before and one after the target.
9. Validate extensions, schema/migrations, row counts, constraints, login, read/write path, History/evidence integrity and core health.
10. Run a controlled synthetic incident and Knowledge retrieval workflow.
11. Record duration, gaps, failures, operator actions and witness sign-off.
12. Destroy temporary copies only after evidence retention and disposal approval.

Never run PITR over the primary database during a rehearsal.

## 7. Failover and failback

Database restore and service failover are separate procedures. Document declaration authority, target selection, write fencing against the old primary, dependencies (DNS, TLS, secrets, queues, object storage), divergence reconciliation, old-primary quarantine, failback and application validation.

Do not enable automatic failover until fencing, split-brain prevention, replication-lag monitoring and failback are tested.

## 8. RPO/RTO

No targets are assigned here. The Business Impact Analysis owner must approve them.

- Actual RPO = incident time minus latest recoverable committed transaction.
- Actual RTO = incident declaration to service restored after application-level validation, not merely PostgreSQL startup.
- Measure backup retrieval, WAL replay, database checks, application validation and approval/decision delays separately.

Synthetic local-Docker PITR is engineering evidence only. It does not prove offsite durability, business-approved RPO/RTO or witnessed production-like recovery.

## 9. Evidence package

Retain approved test plan/ticket, backup manifest/checksums, WAL continuity, restore configuration/target, recovery logs, before/after target proof, application validation, measured RPO/RTO, witness roles, deviations/corrective actions, evidence hash and immutable storage location.

## 10. Official references

- PostgreSQL 16 Continuous Archiving/PITR: https://www.postgresql.org/docs/16/continuous-archiving.html
- PostgreSQL 16 pg_basebackup: https://www.postgresql.org/docs/16/app-pgbasebackup.html
- PostgreSQL 16 pg_verifybackup: https://www.postgresql.org/docs/16/app-pgverifybackup.html
- NIST SP 800-34 Rev. 1: https://csrc.nist.gov/pubs/sp/800/34/r1/upd1/final
