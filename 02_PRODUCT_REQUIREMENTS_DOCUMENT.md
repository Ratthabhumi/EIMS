---
id: EIMS-PRD-001
version: 1.0.0
status: Approved
owner: Lead System Engineer
last_updated: 2026-08-04
review_cycle: Annual
related_documents:
  - 01_EIMS_MASTER_PLAN.md
  - 03_SOFTWARE_ARCHITECTURE_DOCUMENT.md
  - 04_DATABASE_DESIGN.md
  - 05_API_SPECIFICATION.md
---

# EIMS Product Requirements Document

| Metadata | Value |
| :--- | :--- |
| **Document ID** | EIMS-PRD-001 |
| **Version** | 1.0.0 |
| **Status** | Approved |
| **Owner** | Lead System Engineer |
| **Last Updated** | 2026-08-04 |
| **Review Cycle** | Annual |
| **Related Documents** | [Master Plan](01_EIMS_MASTER_PLAN.md), [Architecture](03_SOFTWARE_ARCHITECTURE_DOCUMENT.md) |

---

## 1. Purpose

This document consolidates the binding functional requirements, non-functional performance thresholds, system operational capabilities, and target capacity metrics for the Enterprise Infrastructure Management System (EIMS). As Core Law 2 of the platform, this specification defines *what* engineering capabilities our architecture must satisfy and provides explicit trace identifiers (Requirement IDs) to guide all subsequent backend, frontend, database, and test suite implementations.

---

## 2. Scope

This specification spans the full functional operating boundary of EIMS across all supported infrastructure deployments:
- Autonomous *Discovery Agent* deployment, mTLS authentication, and metric streaming logic.
- Centralized *Asset Registry* ingestion and lifecycle validation engines.
- Multipart document ingestion and asynchronous *OCR Asset Registration* pipelines.
- Deep *Hardware Inventory* cataloging architectures.
- Native *Windows Log Analysis* diagnostic event processing and anomaly extraction.
- Rules-based continuous *Compliance Score* evaluation and exception flagging.
- Role-based access control (RBAC) and data visualization across the Next.js *Operational Dashboard*.

---

## 3. Audience

This document targets Senior Software Architects, Lead System Engineers, Backend/Frontend Developers, Database Specialists, Quality Assurance Test Leads, and DevOps Release Managers responsible for validating implementation completeness against authoritative engineering requirements.

---

## 4. Table of Contents

- [1. Purpose](#1-purpose)
- [2. Scope](#2-scope)
- [3. Audience](#3-audience)
- [4. Table of Contents](#4-table-of-contents)
- [5. User Personas & Operational Roles](#5-user-personas-operational-roles)
- [6. Functional Requirements](#6-functional-requirements)
  - [6.1 Infrastructure Discovery & Telemetry Ingestion](#61-infrastructure-discovery-telemetry-ingestion)
  - [6.2 Asset Registry & Lifecycle Persistence](#62-asset-registry-lifecycle-persistence)
  - [6.3 OCR Asset Registration & Hardware Inventory](#63-ocr-asset-registration-hardware-inventory)
  - [6.4 Windows Log Analysis & Security Ingestion](#64-windows-log-analysis-security-ingestion)
  - [6.5 Compliance Score & Security Auditing](#65-compliance-score-security-auditing)
  - [6.6 Operational Dashboard & UI Interfaces](#66-operational-dashboard-ui-interfaces)
- [7. Non-Functional Requirements](#7-non-functional-requirements)
  - [7.1 Performance & Telemetry Throughput](#71-performance-telemetry-throughput)
  - [7.2 Reliability & High Availability](#72-reliability-high-availability)
  - [7.3 Security & Cryptographic Enforcement](#73-security-cryptographic-enforcement)
  - [7.4 Scalability & Storage Capacity](#74-scalability-storage-capacity)
- [8. Requirement Traceability & Verification Matrix](#8-requirement-traceability-verification-matrix)
- [9. References](#9-references)
- [10. Related Documents](#10-related-documents)
- [11. Revision History](#11-revision-history)

---

## 5. User Personas & Operational Roles

To establish robust security domain separation and interface usability, EIMS defines four canonical operational role boundaries:

| Persona / Role Identifier | Primary Responsibility & Interaction Domain | Security Authorization Level |
| :--- | :--- | :--- |
| **System Administrator (Operator)** | Configures platform integrations, oversees high-level system availability, executes automated asset onboarding, and manages internal RBAC user provisioning. | Full administrative access to all API endpoints, dashboard configurations, and system registries. |
| **Security & Compliance Auditor** | Evaluates real-time *Compliance Score* metrics, investigates *Windows Log Analysis* security exceptions, generates compliance baseline reports, and audits access logs. | Read-only access to *Asset Registry*, telemetry histories, vulnerability exceptions, and *Audit Log* repositories. |
| **Hardware Field Technician** | Performs physical infrastructure maintenance, deploys new physical server racks, captures shipping specification manifests, and triggers *OCR Asset Registration* ingestions. | Read-write authorization restricted strictly to *OCR Asset Registration* upload APIs and localized *Hardware Inventory* updates. |
| **Discovery Agent (Service Account)** | Unattended daemon running on remote compute *Endpoints* tasked with gathering hardware metrics, running configuration surveys, and streaming secure JSON payloads. | Cryptographically restricted API access limited strictly to POST telemetry and diagnostic log ingestion pipelines. |

---

## 6. Functional Requirements

### 6.1 Infrastructure Discovery & Telemetry Ingestion

| Requirement ID | Requirement Summary | Detailed Technical Specification & Architectural Constraints |
| :--- | :--- | :--- |
| **REQ-DISC-01** | Agent Autonomous Enrollment | The *Discovery Agent* must register unindexed *Endpoints* upon initial execution by generating a unique cryptographic fingerprint (SHA-256 hash of mother-board serial, CPU ID, and MAC address) and initiating an mTLS handshake with the *Telemetry Collector*. |
| **REQ-DISC-02** | Telemetry Payload Streaming | The agent must collect operating system health metrics (CPU utilization, RAM saturation, disk read/write IOPS, interface throughput) at a configurable interval (default 60 seconds) and stream validated JSON payloads via HTTPS WebSockets or HTTP/2 POST requests. |
| **REQ-DISC-03** | Asynchronous Queue Buffering | The FastAPI *Telemetry Collector* must deserialize incoming payload strings, validate structure against Pydantic domain models, immediately enqueue raw telemetry into Redis broker queues, and return an HTTP 202 Accepted status under 15 milliseconds. |
| **REQ-DISC-04** | Offline Exception Recovery | If the *Telemetry Collector* network path is unreachable, the *Discovery Agent* must buffer telemetry records locally in a bounded circular write-ahead log (maximum 500 MB) and automatically flush buffered payloads upon connection restoration. |

### 6.2 Asset Registry & Lifecycle Persistence

| Requirement ID | Requirement Summary | Detailed Technical Specification & Architectural Constraints |
| :--- | :--- | :--- |
| **REQ-REG-01** | Canonical Entity Indexing | The *Asset Registry* must assign a universally unique identifier (UUIDv4) to every verified *Infrastructure Asset* and persist canonical properties (hostname, assigned IP addresses, OS kernel version, lifecycle state, deployment zone) inside normalized PostgreSQL tables. |
| **REQ-REG-02** | Telemetry State Deduplication | Background worker processes consuming Redis event streams must query existing PostgreSQL records by cryptographic fingerprint to perform upsert operations, preventing redundant *Infrastructure Asset* table entries. |
| **REQ-REG-03** | Lifecycle State Machine Enforcement | The system must constrain asset state transitions strictly to approved operational lifecycle stages: `Discovered`, `PendingAudit`, `Compliant`, `NonCompliant`, `Quarantined`, and `Decommissioned`. Illegal state transitions must return HTTP 409 Conflict errors and log security exceptions. |

### 6.3 OCR Asset Registration & Hardware Inventory

| Requirement ID | Requirement Summary | Detailed Technical Specification & Architectural Constraints |
| :--- | :--- | :--- |
| **REQ-OCR-01** | Multipart Manifest Ingestion | The API gateway must expose a dedicated HTTPS multipart endpoint accepting high-resolution hardware purchase orders, shipping labels, and faceplate specification imagery (supporting JPG, PNG, and PDF formats up to 25 MB). |
| **REQ-OCR-02** | Object Storage Archival | Upon receipt, the backend must generate an unguessable object storage hash, transfer the raw document binary into local MinIO S3 storage buckets, and record the corresponding MinIO storage URL in PostgreSQL. |
| **REQ-OCR-03** | Autonomous Hardware Parsing | A dedicated asynchronous worker must extract optical character recognition (OCR) text strings from stored image binaries, apply regex pattern matching for hardware vendor part numbers and serial codes, and automatically populate the target asset's *Hardware Inventory* record (CPU model, total RAM slots, controller interfaces). |

### 6.4 Windows Log Analysis & Security Ingestion

| Requirement ID | Requirement Summary | Detailed Technical Specification & Architectural Constraints |
| :--- | :--- | :--- |
| **REQ-LOG-01** | Windows Event Log Ingestion | The *Discovery Agent* deployed on Windows *Endpoints* must bind natively to Windows Event Log infrastructure (`Security`, `System`, and `Application` channels), filter diagnostic noise, and stream security-relevant Event IDs (e.g., 4624 Successful Logon, 4625 Failed Logon, 4720 Account Creation) to the central processing worker. |
| **REQ-LOG-02** | Anomaly & IoC Rule Evaluation | During *Windows Log Analysis*, background ingestion engines must execute real-time pattern evaluations against incoming event logs, automatically identifying unauthorized privilege escalations, repeated brute-force authentication failures (exceeding 5 failures within 60 seconds), or unexpected kernel service installations. |
| **REQ-LOG-03** | Security Exception Alerting | When an anomaly rule triggers, the processing pipeline must instantly promote the event to an active security exception, record an immutable entry inside the *Audit Log*, and dispatch alert payloads to active Next.js *Operational Dashboard* WebSockets. |

### 6.5 Compliance Score & Security Auditing

| Requirement ID | Requirement Summary | Detailed Technical Specification & Architectural Constraints |
| :--- | :--- | :--- |
| **REQ-COMP-01** | Automated Baseline Evaluation | The background evaluation engine must compare active *Infrastructure Asset* diagnostic telemetry against established enterprise baseline rules (e.g., TLS 1.3 enforced, Windows Defender antimalware active, guest operating system accounts disabled, minimum password complexity active). |
| **REQ-COMP-02** | Dynamic Compliance Calculation | The engine must calculate a composite numeric *Compliance Score* ranging precisely from 0 to 100 for every active *Endpoint*. Passing all baseline checks yields 100; failure of critical security metrics applies weighted deduction penalties to the aggregate score. |
| **REQ-COMP-03** | Automated Quarantine Threshold | If an asset's computed *Compliance Score* drops beneath the minimum acceptable enterprise threshold (defined by default at score < 70), the system must immediately update the entity state to `Quarantined`, flag an exception on the monitoring console, and block automated management API commands until remediation occurs. |

### 6.6 Operational Dashboard & UI Interfaces

| Requirement ID | Requirement Summary | Detailed Technical Specification & Architectural Constraints |
| :--- | :--- | :--- |
| **REQ-UI-01** | Real-Time Observability Portal | The Next.js web interface must render a responsive, high-contrast *Operational Dashboard* displaying global infrastructure inventory distributions, aggregate *Compliance Score* distributions, active OCR parsing tasks, and recent Windows security exceptions. |
| **REQ-UI-02** | Live Telemetry Streaming | Dashboard client sessions must establish persistent secure WebSockets with FastAPI backend gateways to render live CPU, RAM, and network throughput charts without requiring manual page refreshing. |
| **REQ-UI-03** | RBAC Enforcement UI | The dashboard must intercept user JWT authorization payloads, rendering administrative configuration controls solely for `System Administrator` roles while locking analytical views to read-only mode for `Security & Compliance Auditor` personnel. |

---

## 7. Non-Functional Requirements

### 7.1 Performance & Telemetry Throughput
- **NFR-PERF-01 (API Latency):** Synchronous REST API read operations querying the *Asset Registry* must achieve an execution latency under 50 milliseconds at the 99th percentile (p99) under load testing scenarios up to 500 concurrent operators.
- **NFR-PERF-02 (Ingestion Throughput):** The combined FastAPI *Telemetry Collector* and Redis caching tier must reliably absorb a steady-state ingestion rate of 5,000 diagnostic payloads per second without incurring queue backpressure or HTTP 429 rate limit exceptions.
- **NFR-PERF-03 (OCR Processing Duration):** Asynchronous OCR extraction worker pipelines must finish text parsing, structural database mapping, and MinIO storage commits within 10,000 milliseconds for standard single-page hardware invoices.

### 7.2 Reliability & High Availability
- **NFR-REL-01 (Database Recovery):** In the event of primary PostgreSQL master node termination, automated automated read-replica promotion and failover routing must complete within 30 seconds with zero loss of committed transactions (RPO = 0, RTO < 30s).
- **NFR-REL-02 (Agent Resilience):** Remote *Discovery Agent* daemon crashes must trigger automatic operating system service restart mechanisms within 5 seconds without user administrative intervention or operating system reboot requirements.

### 7.3 Security & Cryptographic Enforcement
- **NFR-SEC-01 (Transport Encryption):** All external network communications spanning agents, Web client dashboards, and FastAPI endpoints must strictly negotiate TLS 1.3 encryption with modern cipher suites (e.g., `TLS_AES_256_GCM_SHA384`). Unencrypted HTTP traffic must be rejected at the load balancer boundary.
- **NFR-SEC-02 (Audit Log Immutability):** System operational state changes and compliance modifications must append to an immutable PostgreSQL *Audit Log* table configured with strict table permissions preventing `UPDATE` or `DELETE` SQL commands, even by standard database application service accounts.
- **NFR-SEC-03 (Credential Storage):** User account passwords and SSH access keys must never reside in plain text; credentials must undergo one-way cryptographic derivation via Argon2id hashing before relational persistence.

### 7.4 Scalability & Storage Capacity
- **NFR-SCALE-01 (Horizontal Stateless Scaling):** FastAPI ingestion servers and Next.js interface runners must maintain completely stateless execution contexts, allowing seamless horizontal scale-out across Docker and Kubernetes deployment replicas.
- **NFR-SCALE-02 (Telemetry Data Retention):** Historical time-series telemetry metrics stored inside PostgreSQL must undergo automated table partitioning by chronological month, executing automated compression or archival to local MinIO object storage for records aged beyond 90 days.

---

## 8. Requirement Traceability & Verification Matrix

To ensure that implementation follows documentation, the matrix below maps primary Functional Requirements directly against required architectural components and designated verification mechanisms.

| Requirement ID | Primary Domain Pillar | Designated Architectural Component | Planned Verification Method & Target Test Suite |
| :--- | :--- | :--- | :--- |
| **REQ-DISC-01** | Discovery & Ingestion | Discovery Agent Daemon & FastAPI Gateway | Automated functional integration test asserting mTLS certificate acceptance and initial entity payload DB creation. |
| **REQ-DISC-03** | Telemetry Collector | FastAPI Async Routing & Redis Event Broker | Load performance benchmark asserting 5,000 requests/sec sustainment with HTTP 202 latency under 15ms. |
| **REQ-REG-01** | Asset Registry | PostgreSQL Asset Registry Table Schemas | Unit test suites evaluating SQLAlchemy/Pydantic UUIDv4 entity generation and schema constraint validation. |
| **REQ-OCR-03** | Hardware Inventory | Asynchronous OCR Worker & MinIO Store | Automated document pipeline simulation verifying precision of hardware serial Extraction from mock shipping images. |
| **REQ-LOG-02** | Windows Log Analysis | Telemetry Processing Worker & Event Engine | Synthetic security exception injection test asserting instant detection of brute-force login anomalies within event logs. |
| **REQ-COMP-02** | Compliance Auditing | Continuous Rules Engine & PostgreSQL Store | Algorithm verification unit test executing baseline permutations against mock asset configurations to verify accurate score deduction. |
| **REQ-UI-02** | Operational Dashboard | Next.js Client & FastAPI WebSocket Routing | End-to-end browser simulation testing real-time chart re-rendering upon telemetry payload injection. |
| **NFR-SEC-02** | Security Infrastructure | PostgreSQL Audit Log Repository Configuration | Automated database security test confirming SQL `DELETE` or `UPDATE` operation rejection against audit tables. |

---

## 9. References

- [IEEE Standard 29148-2018 - Systems and Software Engineering — Requirements Engineering](https://standards.ieee.org/standard/29148-2018.html)
- [NIST SP 800-53 Rev. 5 - Security and Privacy Controls for Information Systems and Organizations](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final)
- [Open-Web Application Security Project (OWASP) Top 10 Enterprise Application Security Standards](https://owasp.org/www-project-top-ten/)

---

## 10. Related Documents

- [EIMS Master Plan Specification](01_EIMS_MASTER_PLAN.md)
- [EIMS Software Architecture Document](03_SOFTWARE_ARCHITECTURE_DOCUMENT.md)
- [EIMS Database Design Specification](04_DATABASE_DESIGN.md)
- [EIMS OpenAPI Specification](05_API_SPECIFICATION.md)
- [EDS Document Standards and Terminology](docs/_style/document-standard.md)

---

## 11. Revision History

| Version | Date | Author | Status | Description of Change |
| :--- | :--- | :--- | :--- | :--- |
| 1.0.0 | 2026-08-04 | Lead System Engineer | Approved | Initial canonical release of Core Law 2: Product Requirements Document under frozen EDS v1.0.0 standards. |
