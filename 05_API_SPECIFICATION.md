---
id: EIMS-API-001
version: 1.0.0
status: Approved
owner: Lead Software Architect
last_updated: 2026-08-04
review_cycle: Annual
related_documents:
  - 01_EIMS_MASTER_PLAN.md
  - 02_PRODUCT_REQUIREMENTS_DOCUMENT.md
  - 03_SOFTWARE_ARCHITECTURE_DOCUMENT.md
  - 04_DATABASE_DESIGN.md
---

# EIMS API Specification

| Metadata | Value |
| :--- | :--- |
| **Document ID** | EIMS-API-001 |
| **Version** | 1.0.0 |
| **Status** | Approved |
| **Owner** | Lead Software Architect |
| **Last Updated** | 2026-08-04 |
| **Review Cycle** | Annual |
| **Related Documents** | [Master Plan](01_EIMS_MASTER_PLAN.md), [SAD](03_SOFTWARE_ARCHITECTURE_DOCUMENT.md), [Database Design](04_DATABASE_DESIGN.md) |

---

## 1. Purpose

This document establishes the authoritative canonical API interface contracts, RESTful OpenAPI schemas, asynchronous WebSocket communication protocols, cryptographic authentication header layouts, rate-limiting thresholds, and RFC 7807 exception payloads for the Enterprise Infrastructure Management System (EIMS). As Core Law 5 of the platform, this specification binds backend FastAPI service gateways and front-end Next.js client integrations to an immutable networking standard, preventing interface drift during iterative engineering development.

---

## 2. Scope

This specification governs every external and inter-module networked interface across the EIMS deployment domain:
- RESTful HTTP endpoints published by the central FastAPI Core Gateway and edge FastAPI *Telemetry Collector*.
- Secure WebSocket streams (WSS) connecting the Next.js *Operational Dashboard* to backend real-time telemetry events.
- Mutual TLS (mTLS) authentication parameters and high-frequency JSON payload schemas consumed from remote *Discovery Agents*.
- Multipart image ingestion contracts supporting asynchronous *OCR Asset Registration* pipelines.
- Read-only querying interfaces serving auditing compliance reports from immutable PostgreSQL *Audit Log* registries.

---

## 3. Audience

This document targets Senior Software Architects, Lead System Engineers, Backend and Frontend Software Developers, Quality Assurance Test Engineers, DevOps Platform Integration Leads, and Security Compliance Reviewers implementing or validating API integration contracts across our enterprise ecosystem.

---

## 4. Table of Contents

- [1. Purpose](#1-purpose)
- [2. Scope](#2-scope)
- [3. Audience](#3-audience)
- [4. Table of Contents](#4-table-of-contents)
- [5. API Design Principles & Architecture Protocols](#5-api-design-principles-architecture-protocols)
  - [5.1 Protocol Selection Rationale & Trade-offs](#51-protocol-selection-rationale-trade-offs)
  - [5.2 URI Structuring & Semantic Versioning](#52-uri-structuring-semantic-versioning)
  - [5.3 Authentication & Authorization Header Contracts](#53-authentication-authorization-header-contracts)
- [6. Standardized Response & Exception Schemas](#6-standardized-response-exception-schemas)
  - [6.1 Canonical Collection Wrapper & Pagination Schema](#61-canonical-collection-wrapper-pagination-schema)
  - [6.2 RFC 7807 Problem Details Error Architecture](#62-rfc-7807-problem-details-error-architecture)
  - [6.3 Rate Limiting & Overload Control Headers](#63-rate-limiting-overload-control-headers)
- [7. Core REST Endpoint Specifications](#7-core-rest-endpoint-specifications)
  - [7.1 Telemetry Collector & Agent Ingestion API](#71-telemetry-collector-agent-ingestion-api)
  - [7.2 Asset Registry Administration API](#72-asset-registry-administration-api)
  - [7.3 OCR Asset Registration & Hardware Upload API](#73-ocr-asset-registration-hardware-upload-api)
  - [7.4 Compliance Auditing & Audit Log API](#74-compliance-auditing-audit-log-api)
- [8. Asynchronous WebSocket Interface Specifications](#8-asynchronous-websocket-interface-specifications)
- [9. References](#9-references)
- [10. Related Documents](#10-related-documents)
- [11. Revision History](#11-revision-history)

---

## 5. API Design Principles & Architecture Protocols

### 5.1 Protocol Selection Rationale & Trade-offs

EIMS orchestrates network communications through a dual-protocol strategy balancing interoperability against ingestion efficiency:
- **HTTPS REST / OpenAPI for Administration:** All entity administrative operations (*Asset Registry* CRUD, operator RBAC configuration, historical auditing) utilize secure HTTP/2 REST endpoints powered by FastAPI. This design ensures automatic OpenAPI 3.1 contract compilation, native client caching compatibility, and seamless Next.js frontend integration via strongly typed TypeScript interfaces. *Trade-off:* Introduces slightly higher text serialization HTTP header overhead compared to custom binary RPC protocols.
- **WebSockets (WSS) for Real-Time Observability:** To power live telemetry rendering on the *Operational Dashboard* (`REQ-UI-02`), client sessions establish continuous bi-directional WebSocket connections. This eliminates destructive HTTP polling loops that would otherwise exhaust reverse-proxy file descriptors and spike database connection pool utilization during simultaneous operator monitoring sessions.

### 5.2 URI Structuring & Semantic Versioning

All endpoints enforce strict uniform routing syntax across application domains:
- **Path Versioning:** Every interface requires explicit major version path prefixes (`/api/v1/...`). Introducing breaking contract modifications necessitating backward-incompatible client alterations mandates incrementing the root routing prefix to `/api/v2/` while running concurrent deprecation routing.
- **Pluralized Resource Nouns:** REST endpoints identify functional entities via pluralized lowercase domain terminology without verbs (e.g., `/api/v1/assets`, `/api/v1/endpoints`, `/api/v1/audit-logs`).
- **Trailing Slash Prohibition:** Route specifications prohibit trailing URL slashes (use `/api/v1/assets` instead of `/api/v1/assets/`) to eliminate routing redirect penalties and cache fragmentation across reverse proxy layers.

### 5.3 Authentication & Authorization Header Contracts

API endpoints require cryptographic validation headers matching the interacting operational subject:
- **Operator Web Client Requests:** Must supply an OAuth2-compatible Bearer Authorization header embedding an active JSON Web Token (JWT) signed by our authentication gateway:
  ```http
  Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
  ```
- **Discovery Agent Telemetry Ingestion:** Edge ingestion routes (`/api/v1/telemetry/...`) reject JWT credentials. Agents authenticate natively at the transport layer via Mutual TLS (mTLS). Reverse proxies extract client SSL certificate SHA-256 fingerprints, injecting verified cryptographic identities directly into internal headers (`X-Client-Cert-Fingerprint`) evaluated by FastAPI Pydantic security dependencies.

---

## 6. Standardized Response & Exception Schemas

### 6.1 Canonical Collection Wrapper & Pagination Schema

To protect backend database connection pools against unbounded memory consumption during table enumerations, every collection query endpoint requires mandatory offset/limit cursor pagination. Responses encapsulate records within a uniform JSON wrapper containing explicit structural pagination metadata.

```json
{
  "status": "success",
  "data": [
    {
      "asset_id": "8f3b2d10-6c54-4a21-9e87-2b10a9c8e7f6",
      "hostname": "srv-prod-db-01.internal",
      "canonical_ip": "10.240.16.10",
      "lifecycle_state": "Compliant",
      "current_compliance_score": 98,
      "updated_at": "2026-08-04T08:15:22Z"
    }
  ],
  "pagination": {
    "total_records": 1420,
    "current_page": 1,
    "page_size": 50,
    "next_page_cursor": "eyJvZmZzZXQiOjUwLCJsaW1pdCI6NTB9"
  }
}
```

### 6.2 RFC 7807 Problem Details Error Architecture

When processing errors, validation exceptions, or authorization failures occur, API endpoints bypass unstructured textual error messages entirely. All application failures emit a structured JSON payload conforming strictly to **RFC 7807 Problem Details for HTTP APIs**, complete with an explicit tracking UUID linking directly to corresponding Prometheus and Loki distributed logging records.

```http
HTTP/2 422 Unprocessable Entity
Content-Type: application/problem+json

{
  "type": "https://eims.internal/errors/validation-exception",
  "title": "Invalid Telemetry Payload Schema",
  "status": 422,
  "detail": "Field 'cpu_utilization' value 145.2 exceeds physical constraint limits (0.0 - 100.0).",
  "instance": "urn:uuid:7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "invalid_params": [
    {
      "name": "cpu_utilization",
      "reason": "Value must be less than or equal to 100.0"
    }
  ]
}
```

### 6.3 Rate Limiting & Overload Control Headers

To shield backend database infrastructure from denial-of-service degradation during traffic spikes, FastAPI edge gateways enforce fixed window rate limits tracked within Redis in-memory storage. Every response includes real-time quota telemetry headers:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 984
X-RateLimit-Reset: 1722762000
```
If an actor exhausts their operational allotment, the gateway rejects subsequent inbound packets instantly with HTTP status `429 Too Many Requests`, appending a mandatory `Retry-After: <seconds>` pause indicator.

---

## 7. Core REST Endpoint Specifications

### 7.1 Telemetry Collector & Agent Ingestion API

#### `POST /api/v1/telemetry/heartbeat`
Asynchronous edge ingestion route absorbing high-frequency diagnostic payloads emitted by remote *Discovery Agents*.
- **Authentication Requirement:** mTLS Client Certificate Verification (`X-Client-Cert-Fingerprint`).
- **Request Body Schema (JSON):**
  ```json
  {
    "agent_version": "v1.2.4",
    "timestamp": "2026-08-04T08:14:55Z",
    "metrics": {
      "cpu_utilization": 42.5,
      "ram_used_mb": 8420,
      "ram_total_mb": 16384,
      "disk_iops": 312
    }
  }
  ```
- **Successful Response (HTTP 202 Accepted):** Bypasses immediate database persistence; enqueues stream payload directly into Redis event broker queue (`eims:telemetry:ingestion`) under 15ms total latency (`REQ-DISC-03`).
  ```json
  {
    "status": "accepted",
    "stream_job_id": "1722760000000-0",
    "queued_at": "2026-08-04T08:14:55.012Z"
  }
  ```

#### `POST /api/v1/telemetry/winlog`
Ingestion endpoint receiving diagnostic Windows Event Log strings captured during *Windows Log Analysis* workflows.
- **Authentication Requirement:** mTLS Client Certificate Verification.
- **Request Body Schema (JSON):**
  ```json
  {
    "occurrence_time": "2026-08-04T08:15:01Z",
    "event_id": 4625,
    "severity": "Critical",
    "event_channel": "Security",
    "metadata": {
      "target_user_name": "Administrator",
      "workstation_name": "WORKSTATION-X",
      "source_network_ip": "192.168.1.104"
    }
  }
  ```
- **Successful Response:** HTTP `202 Accepted` (Payload queued for Redis sliding-window brute-force rate anomaly evaluations).

### 7.2 Asset Registry Administration API

#### `GET /api/v1/assets`
Enumerate registered *Infrastructure Asset* records subject to role filtering and offset pagination.
- **Authentication Requirement:** Bearer JWT Token (`System Administrator` or `Security & Compliance Auditor` roles).
- **Query Parameters:** `?page=1&limit=50&state=Compliant&min_score=70`
- **Successful Response:** HTTP `200 OK` matching canonical collection wrapper schema Section 6.1.

#### `PATCH /api/v1/assets/{asset_id}`
Execute operational mutations or administrative lifecycle state transitions against a target *Infrastructure Asset*.
- **Authentication Requirement:** Bearer JWT Token (`System Administrator` role strictly enforced).
- **Request Body Schema:**
  ```json
  {
    "lifecycle_state": "Quarantined",
    "operator_rationale": "Manual isolation due to unexplained network egress patterns."
  }
  ```
- **Successful Response (HTTP 200 OK):** Updates PostgreSQL entity record and records an immutable entry inside `audit_logs`.
- **Exception Response (HTTP 409 Conflict):** Triggered if the proposed state modification violates established asset lifecycle state machine arrows (`REQ-REG-03`).

### 7.3 OCR Asset Registration & Hardware Upload API

#### `POST /api/v1/assets/register/ocr`
Multipart document ingestion endpoint receiving hardware purchase manifests and shipping imagery for background processing.
- **Authentication Requirement:** Bearer JWT Token (`System Administrator` or `Hardware Field Technician` roles).
- **Content-Type:** `multipart/form-data`
- **Form Parameters:**
  - `manifest_file`: Binary document file stream (JPG, PNG, PDF up to 25 MB).
  - `deployment_zone`: String identifier for target physical datacenter rack assignment.
- **Successful Response (HTTP 202 Accepted):** Streams binary directly to local MinIO object storage (`eims-ocr-manifests` bucket), initiates preliminary relational DB tracking, and dispatches a background task to the Redis OCR job queue (`REQ-OCR-02`).
  ```json
  {
    "status": "processing",
    "record_id": "4e1a91b2-5c4a-4b11-9a74-8b10f9e8d7a1",
    "minio_object_uri": "s3://eims-ocr-manifests/2026/08/a948904f2f0f479b.pdf",
    "estimated_completion_ms": 10000
  }
  ```

#### `GET /api/v1/assets/register/ocr/{record_id}`
Poll execution progress and extraction results for an initiated *OCR Asset Registration* job.
- **Successful Response (HTTP 200 OK):** Returns extraction status (`Pending`, `Completed`, or `Failed`) alongside populated *Hardware Inventory* serial strings mapped by background processing daemons.

### 7.4 Compliance Auditing & Audit Log API

#### `GET /api/v1/audit-logs`
Read-only querying interface providing forensic access to system operational modifications and compliance state transitions.
- **Authentication Requirement:** Bearer JWT Token (`System Administrator` or `Security & Compliance Auditor` roles).
- **Query Parameters:** `?asset_id=8f3b2d10-6c54-4a21-9e87-2b10a9c8e7f6&from=2026-08-01T00:00:00Z&limit=100`
- **Successful Response (HTTP 200 OK):** Returns ordered historical execution records from immutable PostgreSQL audit tables.
- **Security Constraint:** HTTP `POST`, `PUT`, `PATCH`, and `DELETE` routing methods are permanently disabled against `/api/v1/audit-logs` at the application framework gateway (`NFR-SEC-02`).

---

## 8. Asynchronous WebSocket Interface Specifications

#### `WSS /api/v1/ws/dashboard`
Bi-directional WebSocket streaming pipeline pushing live operational metrics and security anomaly alerts to Next.js clients.

- **Connection Handshake:** Client initializes TLS connection at `/api/v1/ws/dashboard?token=<active_jwt_bearer>`. The server validates token revocation status against Redis cache prior to completing upgrade handshake.
- **Outbound Server Stream (Live Telemetry Event):** Emitted continuously as background workers process incoming agent diagnostic heartbeats.
  ```json
  {
    "event_type": "TELEMETRY_UPDATE",
    "timestamp": "2026-08-04T08:16:02Z",
    "payload": {
      "asset_id": "8f3b2d10-6c54-4a21-9e87-2b10a9c8e7f6",
      "cpu_utilization": 68.4,
      "current_compliance_score": 98
    }
  }
  ```
- **Outbound Server Stream (Security Anomaly Alert):** Broadcast instantly when *Windows Log Analysis* engines detect brute-force threshold violations or configuration drift causing an asset's *Compliance Score* to fall beneath required baseline thresholds (<70).
  ```json
  {
    "event_type": "SECURITY_QUARANTINE_EXCEPTION",
    "severity": "Critical",
    "timestamp": "2026-08-04T08:16:05Z",
    "payload": {
      "asset_id": "8f3b2d10-6c54-4a21-9e87-2b10a9c8e7f6",
      "hostname": "srv-prod-db-01.internal",
      "violation_detail": "Consecutive failed login threshold exceeded (Event ID 4625: 6 occurrences in 45s). Asset quarantined automatically.",
      "new_state": "Quarantined"
    }
  }
  ```

---

## 9. References

- [OpenAPI Specification Version 3.1.0 Formal Standards](https://spec.openapis.org/oas/v3.1.0)
- [RFC 7807 - Problem Details for HTTP APIs](https://tools.ietf.org/html/rfc7807)
- [RFC 6455 - The WebSocket Protocol Engineering Architecture](https://tools.ietf.org/html/rfc6455)
- [OWASP REST Security Cheat Sheet - Authentication & Rate Limiting](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html)

---

## 10. Related Documents

- [EIMS Master Plan Specification](01_EIMS_MASTER_PLAN.md)
- [EIMS Product Requirements Document](02_PRODUCT_REQUIREMENTS_DOCUMENT.md)
- [EIMS Software Architecture Document](03_SOFTWARE_ARCHITECTURE_DOCUMENT.md)
- [EIMS Database Design Specification](04_DATABASE_DESIGN.md)
- [EDS Document Standards and Terminology](docs/_style/document-standard.md)

---

## 11. Revision History

| Version | Date | Author | Status | Description of Change |
| :--- | :--- | :--- | :--- | :--- |
| 1.0.0 | 2026-08-04 | Lead Software Architect | Approved | Initial canonical release of Core Law 5: API Specification under frozen EDS v1.0.0 rules. |
