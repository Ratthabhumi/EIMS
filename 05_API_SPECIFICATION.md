---
id: EIMS-API-001
version: 1.1.0
status: Draft
owner: Lead Software Architect
last_updated: 2026-09-10
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
| **Version** | 1.1.0 |
| **Status** | Draft |
| **Owner** | Lead Software Architect |
| **Last Updated** | 2026-09-10 |
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
- [8. Sprint 10: Global Search & Timeline API](#8-sprint-10-global-search-timeline-api)
  - [8.1 Global Search API](#81-global-search-api)
  - [8.2 Audit Log Query API](#82-audit-log-query-api)
  - [8.3 Timeline Query API](#83-timeline-query-api)
  - [8.4 Telemetry Metrics Query API](#84-telemetry-metrics-query-api)
  - [8.5 Windows Log Query API](#85-windows-log-query-api)
- [9. Asynchronous WebSocket Interface Specifications](#9-asynchronous-websocket-interface-specifications)
- [10. References](#10-references)
- [11. Related Documents](#11-related-documents)
- [12. Revision History](#12-revision-history)

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

## 8. Sprint 10: Global Search & Timeline API

### 8.1 Global Search API

#### `GET /api/v1/search`
Cross-domain search endpoint returning normalized results across searchable EIMS entities.
- **Authentication Requirement:** Bearer JWT Token (existing dependency).
- **Query Parameters:**
  - `q` (required): Search query string (minimum 2 characters).
  - `type` (optional): Filter by entity type (`asset`, `audit`, `analysis`).
  - `page` (default: 1): Page number (ge: 1).
  - `limit` (default: 20, max: 50): Results per page.
- **Successful Response (HTTP 200 OK):** Returns normalized search results grouped by entity type.
  ```json
  {
    "status": "success",
    "data": [
      {
        "type": "asset",
        "id": "8f3b2d10-6c54-4a21-9e87-2b10a9c8e7f6",
        "title": "PC-ACCT-042",
        "subtitle": "Active • 192.168.1.100",
        "metadata": {"state": "Compliant", "score": 85},
        "url": "/endpoints?id=8f3b2d10-6c54-4a21-9e87-2b10a9c8e7f6",
        "timestamp": "2026-08-10T12:00:00Z",
        "relevance": 0.95
      }
    ],
    "pagination": {
      "total_records": 12,
      "current_page": 1,
      "page_size": 20,
      "next_page_cursor": null
    }
  }
  ```
- **Search Result Contract (Normalized):**
  - `type`: Entity type identifier.
  - `id`: UUID of the entity.
  - `title`: Primary display name.
  - `subtitle`: Secondary information (state, date, severity).
  - `metadata`: Additional context (flexible JSON).
  - `url`: Canonical frontend route for navigation.
  - `timestamp`: When the entity was created or updated.
  - `relevance`: 0.0–1.0 relevance score (optional for timeline results).
- **Search Domains (Sprint 10) — Final Classification:**
  - **Asset** (primary): hostname (partial), canonical_ip (partial), lifecycle_state (exact), cryptographic_fingerprint (exact).
  - **AuditLog** (primary): action_verb (partial/exact).
  - **Analysis** (secondary): event_id (exact), description (partial/full-text), ai_summary (full-text).
  - **Not included in Sprint 10 Global Search:** Hardware, Telemetry, WinLog. These remain timeline sources and asset-context data but are not standalone search result types, to avoid search-result clutter and because they lack first-class user-facing canonical destinations.
- **Error Behavior:** RFC 7807 Problem Details for validation failures or unauthorized access.
- **Performance Target:** p95 response time < 500 ms for common queries.

### 8.2 Audit Log Query API

#### `GET /api/v1/audit-logs`
Read-only querying interface for immutable audit trail records.
- **Authentication Requirement:** Bearer JWT Token (`System Administrator` or `Security & Compliance Auditor` roles).
- **Query Parameters:**
  - `asset_id` (optional): Filter by target asset UUID.
  - `action` (optional): Filter by action_verb (exact match).
  - `from` (optional): Start date (ISO 8601).
  - `to` (optional): End date (ISO 8601).
  - `page` (default: 1): Page number.
  - `limit` (default: 50, max: 200): Records per page.
- **Successful Response (HTTP 200 OK):** Returns ordered historical audit records.
  ```json
  {
    "status": "success",
    "data": [
      {
        "log_id": "uuid",
        "actor_id": "uuid or null",
        "asset_id": "uuid or null",
        "action_verb": "TRANSITION_STATE",
        "performed_at": "2026-08-10T12:00:00Z",
        "immutable_payload": {
          "previous_state": "Discovered",
          "new_state": "Active",
          "reason": "Manual audit"
        }
      }
    ],
    "pagination": {
      "total_records": 150,
      "current_page": 1,
      "page_size": 50,
      "next_page_cursor": null
    }
  }
  ```
- **Security Constraint:** HTTP `POST`, `PUT`, `PATCH`, and `DELETE` methods are permanently disabled against `/api/v1/audit-logs`.
- **Error Behavior:** RFC 7807 Problem Details.

### 8.3 Timeline Query API

#### `GET /api/v1/timeline`
Unified timeline endpoint aggregating events from multiple domain sources.
- **Authentication Requirement:** Bearer JWT Token (existing dependency).
- **Query Parameters:**
  - `entity_id` (optional): Filter by related asset/entity UUID.
  - `type` (optional): Event type (`audit`, `telemetry`, `winlog`).
  - `severity` (optional): Severity level (`Critical`, `Warning`, `Information`).
  - `from` (optional): Start date (ISO 8601).
  - `to` (optional): End date (ISO 8601).
  - `page` (default: 1): Page number.
  - `limit` (default: 50, max: 200): Events per page.
- **Successful Response (HTTP 200 OK):** Returns unified chronological event list.
  ```json
  {
    "status": "success",
    "data": [
      {
        "id": "uuid",
        "type": "audit",
        "title": "TRANSITION_STATE",
        "description": "Asset transitioned from Discovered to Active",
        "severity": "information",
        "timestamp": "2026-08-10T12:00:00Z",
        "actor_id": "uuid or null",
        "entity_id": "uuid",
        "entity_type": "asset",
        "metadata": {}
      }
    ],
    "pagination": {
      "total_records": 500,
      "current_page": 1,
      "page_size": 50,
      "next_page_cursor": null
    }
  }
  ```
- **Timeline Data Sources (Sprint 10):**
  - `audit_logs` (type: `audit`, timestamp: `performed_at`)
  - `telemetry_metrics` (type: `telemetry`, timestamp: `event_time`)
  - `windows_event_logs` (type: `winlog`, timestamp: `occurrence_time`)
- **Excluded Source — `analysis_history`:** Not included in the Sprint 10 unified timeline because it lacks an `asset_id` foreign key and its `created_at` column is timezone-naive (`DateTime` without `timezone=True`), which would create inconsistent cross-table chronological ordering. Analysis remains searchable via Global Search and listable via the existing `GET /api/v1/history/` endpoint.
- **Behavior:** Chronological ordering (newest first by default). No new event table introduced — queries existing domain tables.
- **Performance Target:** p95 response time < 300 ms.
- **Error Behavior:** RFC 7807 Problem Details.

### 8.4 Telemetry Metrics Query API

#### `GET /api/v1/telemetry/metrics`
Query historical telemetry metrics for specific assets.
- **Authentication Requirement:** Bearer JWT Token.
- **Query Parameters:**
  - `asset_id` (required): Filter by asset UUID.
  - `from` (optional): Start date (ISO 8601).
  - `to` (optional): End date (ISO 8601).
  - `page` (default: 1): Page number.
  - `limit` (default: 50, max: 200): Records per page.
- **Successful Response (HTTP 200 OK):** Returns paginated telemetry records.
- **Error Behavior:** RFC 7807 Problem Details.

### 8.5 Windows Log Query API

#### `GET /api/v1/telemetry/winlogs`
Query historical Windows Event Log records.
- **Authentication Requirement:** Bearer JWT Token.
- **Query Parameters:**
  - `asset_id` (optional): Filter by asset UUID.
  - `event_id` (optional): Filter by Windows Event ID (exact match).
  - `severity` (optional): Filter by severity level.
  - `from` (optional): Start date (ISO 8601).
  - `to` (optional): End date (ISO 8601).
  - `page` (default: 1): Page number.
  - `limit` (default: 50, max: 200): Records per page.
- **Successful Response (HTTP 200 OK):** Returns paginated Windows Event Log records.
- **Error Behavior:** RFC 7807 Problem Details.

---

## 9. Asynchronous WebSocket Interface Specifications

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

## 12. Revision History

| Version | Date | Author | Status | Description of Change |
| :--- | :--- | :--- | :--- | :--- |
| 1.1.0 | 2026-09-10 | Lead Software Architect | Draft | Sprint 10: Added Global Search, Audit Log Query, Timeline, Telemetry Metrics, and Windows Log Query API specifications. |
| 1.0.0 | 2026-08-04 | Lead Software Architect | Approved | Initial canonical release of Core Law 5: API Specification under frozen EDS v1.0.0 rules. |
