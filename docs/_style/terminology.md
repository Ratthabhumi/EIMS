---
id: EDS-TERM-001
version: 1.0.0
status: Approved
owner: Lead Software Architect
last_updated: 2026-08-04
review_cycle: Annual
related_documents:
  - document-standard.md
  - writing-guide.md
---

# EIMS Canonical Terminology

| Metadata | Value |
| :--- | :--- |
| **Document ID** | EDS-TERM-001 |
| **Version** | 1.0.0 |
| **Status** | Approved |
| **Owner** | Lead Software Architect |
| **Last Updated** | 2026-08-04 |
| **Review Cycle** | Annual |
| **Related Documents** | [Document Standard](document-standard.md), [Writing Guide](writing-guide.md) |

---

## 1. Purpose

This document establishes the official canonical vocabulary (Ubiquitous Language) for the Enterprise Infrastructure Management System (EIMS). Every engineering document, architecture schema, API endpoint path, relational database table, variable identifier, and user UI label must adopt these terms consistently. 

---

## 2. Scope

This terminology applies universally across the entire project lifecycle—spanning requirements analysis, documentation, backend services, frontend web interfaces, DevOps pipelines, and test automation frameworks. Using unlisted synonyms or colloquial alternatives is strictly prohibited to prevent architectural ambiguity and semantic drift.

---

## 3. Canonical Domain Glossary

| Canonical Term | Definition & Architectural Scope | Prohibited Synonyms |
| :--- | :--- | :--- |
| **Infrastructure Asset** | Any identifiable hardware, physical server, virtual machine, network infrastructure appliance, or registered physical unit managed within EIMS. | Device, Machine, Server Box, Hardware Node, Item, Managed Unit |
| **Endpoint** | A specific software communication interface, networked operating system runtime, or accessible host destination targeted by EIMS agents or APIs. | Target Node, Host System, Client Computer, Remote Box |
| **Discovery Agent** | The secure lightweight telemetry daemon deployed on remote endpoints or network segments to interrogate, register, and report local configuration and runtime health to EIMS services. | Scanner, Collector Script, Probe Daemon, Monitor App, Sniffer |
| **Asset Registry** | The central service module and underlying relational database engine responsible for indexing, validating, and persisting the lifecycle states of all Infrastructure Assets. | Asset Database, Inventory Tracker, Device Catalog, Machine DB |
| **Compliance Score** | A calculated numeric evaluation metric (ranging from 0 to 100) expressing an Infrastructure Asset's adherence to required enterprise configuration baselines and security hardening benchmarks. | Health Rating, Security Percentage, Audit Score, Trust Level |
| **Operational Dashboard** | The primary user interaction interface presenting centralized real-time telemetry metrics, system health monitors, asset distributions, and security exception alerts. | Control Panel, Admin Page, Monitoring Console, Status Portal |
| **Audit Log** | The tamper-resistant append-only temporal tracking store recording all system state modifications, user authorization attempts, and administrative configuration executions. | System Log, Event Tracker, History DB, Activity Journal |
| **OCR Asset Registration** | The ingestion workflow analyzing physical hardware shipping manifests, specification barcodes, or hardware faceplate imagery using optical character recognition to provision initial Asset Registry entries. | Image Scanner, Receipt Reader, Visual Add, Photo Intake |
| **Hardware Inventory** | The structural component catalog detailing internal hardware subcomponent topologies (CPUs, storage arrays, RAM DIMMs, network interface cards) attached to an Infrastructure Asset. | Spec List, Hardware Specs, Component Roster, Parts Sheet |
| **Telemetry Collector** | The backend aggregation subsystem engineered to receive, validate, deserialize, and enqueue high-frequency diagnostic metric payloads emitted by remote Discovery Agents. | Log Receiver, Data Sink, Payload Listener, Metric Gateway |
| **Windows Log Analysis** | The specialized processing pipeline responsible for ingesting, filtering, normalizing, and extracting security indicators from native Windows Event Log (`.evtx` or live Eventing) streams. | Event Viewer Parsing, WinLog Reader, Microsoft Log Scraping |

---

## 4. Architectural Technology Stack Nomenclature

When referencing standard infrastructure and runtime dependencies, always utilize the proper capitalized trademarked nomenclature defined in our system defaults:
- **Backend Framework:** FastAPI *(Prohibited: fast-api, FastApi, python-api)*
- **Frontend Stack:** Next.js with React and TypeScript *(Prohibited: NextJS, next.js, React-TS, TSX Front)*
- **Relational Datastore:** PostgreSQL *(Prohibited: Postgres, psql, PGDB)*
- **In-Memory Cache:** Redis *(Prohibited: redis-db, redis cache)*
- **Object Storage:** MinIO *(Prohibited: Minio, Min-IO, local S3 bucket)*
- **Container Infrastructure:** Docker *(Prohibited: docker daemon, container engine)*
- **Automation Pipeline:** GitHub Actions *(Prohibited: GHA, github workflows, CI runner)*
- **Observability Suite:** Prometheus, Grafana, and Loki *(Prohibited: prom/grafana, metrics bundle)*

---

## 5. Terminology Enforcement

Whenever engineering code reviews or architectural evaluations uncover Prohibited Synonyms in pull requests or technical documents, reviewers are required to reject the modification with direct instruction to realign language terminology with this specification.
