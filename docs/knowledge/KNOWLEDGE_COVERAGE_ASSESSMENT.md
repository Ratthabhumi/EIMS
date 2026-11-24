# Knowledge coverage assessment — measured from the 163 canonical records (2026-11-19)

Supersedes the product-family view in `KNOWLEDGE_COVERAGE_MATRIX.md` (kept, not edited) by measuring domain coverage and record depth directly from `load_catalog()`. All numbers below were computed from the catalog in the working tree; nothing is estimated.

**Terminology correction.** `KNOWLEDGE_COVERAGE_MATRIX.md` / `KNOWLEDGE_CATALOG_AUDIT.md` call the 22 vendor records "validated". In the governance lifecycle they are **candidates**: none has a human source verifier, a lab validation, or an approval (see `CANDIDATE_SOURCE_VERIFICATION_20261119.md`). Use "candidate" in any trust-facing text.

## 1. Depth: what the records actually contain
| Field | 141 Windows context records | 22 vendor candidates |
|---|---|---|
| description / operator_context / keywords / related_events | 141 / 141 / 141 / 141 | description 22 |
| investigation_steps | **0** | 22 |
| limitations | **0** | 22 |
| official_references | **0** | 20 |
| remediation_guidance | **0** | **0** |
| verification_criteria | **0** | **0** |
| Mean description length | 77 characters | n/a |

Reading: the Windows layer is an event dictionary (what an event ID is), not diagnostic knowledge. The vendor layer has investigation steps and limitations, but **no record anywhere has remediation or verification guidance**, so the "what to fix and how to prove it" half of the engineer workflow has no knowledge behind it. 16 of 22 candidates carry catalog status `official_documentation_verified`; the independent pass on 2026-11-19 could reproduce only part of that (Cisco, OpenSSH, PAN-OS partially; FortiOS not readable).

## 2. Breadth: Windows context records by category (141)
Account Management 17 · Defender/Endpoint 13 · Services 12 · Authentication 11 · PowerShell 8 · System 7 · Storage/Disk 7 · Persistence 6 · Firewall/Network Security 6 · Networking & File Share 5 · Application 5 · DNS 5 · Task Scheduler 5 · RDP/Remote 5 · Active Directory 4 · Group Policy 4 · WMI 4 · Privilege 3 · Hyper-V 3 · Process 2 · Audit 2 · DHCP 2 · TCP/IP 2 · Hardware/Resource 2 · **Backup/Recovery 1**.
Severity: Info 85, Warning 34, Error 21, Critical 1 — 60% of records are informational/audit events, which is why they are context, not diagnostics.

## 3. Domain coverage vs. proposed EIMS scope
Scope tiers are **proposed from the parsers the Analyzer actually ships** (windows_event, veeam_vbr, vmware, fortinet, cisco_asa, palo_alto, linux_syslog, json); the owner should confirm them.

| Domain | Proposed tier | Records today | Depth | Verdict |
|---|---|---|---|---|
| Windows event log (identity, services, storage, GPO, RDP, DNS/DHCP, Defender) | Core | 141 | context only | breadth fair, **no diagnostic depth** |
| Windows Update, cluster/failover, Kernel-Power/crash dumps, NTFS/volsnap detail, SChannel/TLS, Kerberos failure codes, WinRM | Core | few/none by category (Hardware 2, Backup 1) | — | **largest Windows gaps** |
| Backup and restore (Veeam) | Core | 4 candidates | steps, no remediation | thin |
| Virtualization (VMware/ESXi, Hyper-V) | Core | 2 candidates + 3 Hyper-V context | thin | thin |
| Firewalls (FortiOS, Cisco ASA, PAN-OS) | Secondary | 5 + 6 + 4 candidates | category/message level | log-format coverage, not incident diagnostics |
| Linux / SSH | Secondary | 1 candidate | minimal | **minimal** (no sudo/systemd/disk/network) |
| Database (PostgreSQL), Redis, MinIO | EIMS platform | **0** | — | **none** |
| EIMS platform itself (FastAPI, Next.js BFF, workers, outbox, Prometheus, Grafana) | Core (self-diagnosis) | **0** | — | **none** |
| SQL Server, Kubernetes, cloud IAM/connectivity | Future / unconfirmed | 0 | — | out of scope until confirmed |
| Cross-product correlation (Windows ↔ Veeam ↔ VMware) | Core value | 0 | — | none |

## 4. Prioritised gaps
| # | Gap | Why it matters | Needs |
|---|---|---|---|
| 1 | Remediation + verification fields on the vendor model | Without them no record can answer "how to fix / how to prove fixed"; blocks the Resolution stage of the workflow | schema/loader change (validated by `load_catalog`), then per-record sourced content |
| 2 | Depth for the highest-impact Windows Error/Critical events (22 Error/Critical records) before touching the 85 Info events | Engineers hit failures first; context events are rarely the answer | Microsoft Learn per event; verification of version scope |
| 3 | Veeam job/repository/proxy/snapshot failure chains; VMware datastore/HA/vCenter | These are the product's differentiating incident types | Veeam KB / Broadcom KB, exact error strings |
| 4 | EIMS platform self-diagnosis (Postgres, Redis, MinIO, workers, outbox) | EIMS cannot explain its own outages | official docs for each component; local runbook facts |
| 5 | Linux syslog beyond sshd | Single record today | OpenSSH/systemd/Linux docs (pinned releases) |
| 6 | Cross-product scenarios | Highest value, depends on 1–5 | multi-source evidence design |

## 5. What this assessment does **not** do
- It adds no catalog records. Records must not be added without per-record primary-source verification, which has not been performed for any new content; a larger catalog of unsourced text would reduce, not raise, trust.
- Target sizes (e.g. 250–500) are not goals; the measure is the share of Error/Critical and vendor-incident scenarios with sourced remediation and verification.
- Scope tiers above are proposals, not owner decisions.
