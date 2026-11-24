# EIMS Business Impact Analysis — RPO/RTO decision record

Status: **template prepared; targets intentionally unset pending business-owner approval**.

Complete this record with the EIMS Service Owner, business process owners, Data Owner and Operations Owner. Engineering must not invent acceptable data loss or downtime.

## 1. Business context

| Field | Owner input |
|---|---|
| Business service/process supported by EIMS | |
| Business owner and delegate | |
| Data owner / classification | |
| Critical user groups and operating hours | |
| Upstream/downstream dependencies | |
| Legal, contractual or audit obligations | |
| Impact if EIMS is unavailable | |
| Impact if data is stale/incomplete | |
| Impact if incident evidence is lost/altered | |

## 2. Data criticality

For each class, record value, change rate, retention and integrity needs:
- AnalysisHistory and source evidence.
- Approved Knowledge, lifecycle events and audit trail.
- KnowledgeUsage feedback and source-history hashes.
- User/session/security audit records.
- Telemetry and outbox events.
- Attachments/object-store data and derived indexes.
- Schema migrations, configuration and encryption-key dependencies.

## 3. Owner-approved objectives

| Workload | Maximum tolerable data loss | Approved RPO | Maximum tolerable outage | Approved RTO | Priority |
|---|---|---|---|---|---|
| Incident History/evidence | TBD | TBD | TBD | TBD | |
| Approved Knowledge/audit history | TBD | TBD | TBD | TBD | |
| Telemetry/outbox | TBD | TBD | TBD | TBD | |
| Dashboard/API | TBD | N/A or owner decision | TBD | TBD | |
| Attachments/object storage | TBD | TBD | TBD | TBD | |

RPO is the maximum acceptable data loss measured in time. RTO is the maximum acceptable time to restore the service to an agreed usable state. Recovery completion requires application-level validation, not just a live database connection.

## 4. Recovery dependencies and sequence

Record actual dependencies, recovery order, owner and evidence:
1. Identity, secrets and encryption-key recovery.
2. Network, DNS, TLS and remote backup repository.
3. PostgreSQL base backup and WAL/PITR.
4. Object storage and attachment integrity.
5. Redis/cache and message broker rebuild/replay policy.
6. Backend services, scheduled workers and outbox replay.
7. Dashboard and user authentication.
8. Synthetic incident and Knowledge retrieval validation.

Confirm how duplicate/stale messages and split-brain writes are prevented.

## 5. Scenario analysis

For each, record business impact, detection time, decision authority, recovery method and evidence:
- Primary host or storage failure.
- Ransomware or accidental database deletion.
- Site/network outage.
- Database corruption.
- Backup credential compromise or encryption-key loss.
- WAL archive gap or remote repository outage.
- Failed migration/incompatible application release.
- Object storage/attachment loss.
- Stale standby, split-brain or failover failure.

## 6. Measurement plan

During each witnessed drill, record incident declaration, last recoverable transaction, base-backup retrieval, WAL replay, database validation, application validation, service restoration, actual RPO/RTO, deviations and corrective actions.

## 7. Approval

| Role | Name | Decision | Date | Evidence/ticket |
|---|---|---|---|---|
| Business Service Owner | | Pending | | |
| Data Owner | | Pending | | |
| Operations Owner | | Pending | | |
| Security Owner | | Pending | | |
| EIMS Engineering Lead | | Pending | | |

No RPO/RTO value becomes an EIMS acceptance criterion until the relevant owners approve this record.
