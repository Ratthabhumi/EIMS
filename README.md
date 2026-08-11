# Enterprise Infrastructure Management System (EIMS)

[![License: All Rights Reserved](https://img.shields.io/badge/License-All%20Rights%20Reserved-red.svg)](LICENSE)
[![Licensing Model](https://img.shields.io/badge/Model-Source--Available-E11D48.svg)](NOTICE)
[![EDS Constitution](https://img.shields.io/badge/EDS%20Constitution-v1.0.0%20Approved-047857.svg)](docs/index.md)
[![Build Status](https://img.shields.io/badge/Build-Active%20Development-1E40AF.svg)](CHANGELOG.md)

**EIMS (Enterprise Infrastructure Management System)** is an enterprise-grade platform engineered to centralize compute infrastructure discovery, hardware inventory tracking, automated optical character recognition (OCR) asset registration, continuous Windows log diagnostics, rules-based compliance auditing, and live operational visibility.

---

## 🔒 Source-Available Licensing & Legal Status

> [!IMPORTANT]
> **This project is NOT an Open Source software product.** 
> EIMS is published under a strict **Source-Available / All Rights Reserved** proprietary licensing model ([LICENSE](LICENSE)).

| Licensing Parameter | Authoritative Project Policy |
| :--- | :--- |
| **Repository Visibility** | **Public** (Exclusively for architectural evaluation and technical portfolio demonstration). |
| **Source Code Visibility**| **Public** |
| **License Type** | **All Rights Reserved** (See [LICENSE](LICENSE) and [NOTICE](NOTICE) specifications). |
| **Open Source Rights** | **No** (Public visibility does not imply or confer any open-source usage rights). |
| **Commercial Utilization**| **Not permitted** without express prior written commercial license authorization. |
| **Redistribution Rights** | **Not permitted** under any circumstances. |
| **Modification & Derivation**| **Not permitted** unless explicitly authorized in writing by project copyright owners. |
| **Trademark Rights** | **Strictly Reserved** |

*Commercial distribution and operational deployment licensing will be made available upon formal request in future product lifecycle stages.*

---

## 🚧 Project Status

This project is currently under active development.

- **Sprint 0 – Documentation Foundation** ✅
- **Sprint 1 – Engineering Specifications** ✅
- **Sprint 2 – Backend Foundation** ✅
- **Sprint 3 – Telemetry Collector & Discovery Agent Ingestion** ✅
- **Sprint 4 – MinIO Integration & OCR Asset Registration** ✅
- **Sprint 5 – Windows Log Analytics & Compliance Score Engines** ✅
- **Sprint 6 – Operational Dashboard & Enterprise Observability** ✅
- **Sprint 7 – Enterprise Portal, Endpoint Auditor & UI Polish** ✅
- **Sprint 8+ – High Availability & Service Evaluation Systems** *(Next Target / Active)*

*The project is currently transitioning toward upcoming enterprise clustering operational milestones.*

---

## 🚀 Quick Start & Cheatsheet

For detailed instructions on how to start the backend, frontend dashboard, agent simulation, and database infrastructure, please refer to the **[EIMS Developer Cheatsheet](CHEATSHEET.md)**.

---

## System Architecture Overview

EIMS utilizes a **Hybrid Modular Monolith paired with an Asynchronous Event-Driven Ingestion Architecture**. High-frequency diagnostic telemetry and security events stream over Mutual TLS (mTLS) into real-time Redis queues, decoupling rapid network ingestion from synchronous relational PostgreSQL database writes.

```mermaid
flowchart LR
    classDef service fill:#1E293B,stroke:#475569,color:#FFFFFF,stroke-width:2px;
    classDef store fill:#1E40AF,stroke:#3B82F6,color:#FFFFFF,stroke-width:2px;
    classDef agent fill:#047857,stroke:#10B981,color:#FFFFFF,stroke-width:2px;
    classDef ui fill:#5B21B6,stroke:#8B5CF6,color:#FFFFFF,stroke-width:2px;

    Agent[Discovery Agent] -->|mTLS HTTPS Telemetry| Collector[FastAPI Telemetry Collector]
    Collector -->|LPUSH Redis Stream| Broker([Redis Event Broker])
    Broker -->|Consume Batch Queue| Worker[Telemetry & Log Worker]
    Worker -->|Batch SQL UPSERT| Pool[PgBouncer Pool]
    Pool <-->|TCP Relational Trunk| DB[(PostgreSQL Asset Registry)]
    Operator[System Administrator] <-->|WSS Real-time Feed| UI[Next.js Operational Dashboard]
    UI <-->|OpenAPI / REST| Gateway[FastAPI Core Gateway]
    Gateway <--> Pool

    class Agent,Operator agent;
    class Collector,Broker,Worker,Pool,Gateway service;
    class DB store;
    class UI ui;
```

---

## Authoritative Core Laws (Single Source of Truth)

All software implementation, database schema modeling, and API routing within EIMS strictly obey our foundational architectural specifications (**Core Laws**) governed under the frozen **EIMS Documentation System (EDS v1.0.0)**:

1. **[Core Law 1: EIMS Master Plan](01_EIMS_MASTER_PLAN.md)** — Architectural vision, technology selection trade-off evaluations (FastAPI, Next.js, PostgreSQL, Redis, MinIO, Docker), and product development sprint milestones.
2. **[Core Law 2: Product Requirements Document](02_PRODUCT_REQUIREMENTS_DOCUMENT.md)** — Binding functional execution capabilities, operational personas (`System Administrator`, `Security Auditor`), and verifiable Requirement Traceability IDs (`REQ-DISC-01` through `NFR-SCALE-02`).
3. **[Core Law 3: Software Architecture Document](03_SOFTWARE_ARCHITECTURE_DOCUMENT.md)** — C4 container topology boundaries, edge sequence flows (<15ms HTTP 202 latencies), PgBouncer transaction pooling, and asset lifecycle state transition tables.
4. **[Core Law 4: Database Design Specification](04_DATABASE_DESIGN.md)** — Complete PostgreSQL relational tables, Mermaid Entity-Relationship diagrams (`erDiagram`), composite B-Tree/GIN JSONB indexes, declarative monthly time-series partitioning, and Volatile-LRU Redis namespace definitions.
5. **[Core Law 5: API Specification](05_API_SPECIFICATION.md)** — Canonical REST / OpenAPI routing protocols, secure WebSocket channels (`WSS /api/v1/ws/dashboard`), mTLS authentication parameter contracts, and RFC 7807 Problem Details error schemas.

---

## Engineering Governance & Evaluation

We practice professional software engineering governance. Before interacting with our public evaluation repositories or reviewing architectural proposals, visitors must read our engineering conventions:
- **[Contributing Handbook](CONTRIBUTING.md)**: Details Git branching standards (`feature/`, `fix/`, `docs/`), **Conventional Commits** formatting rules, and documentation-first development practices.
- **[Security & Vulnerability Disclosure Policy](SECURITY.md)**: Outlines responsible private reporting channels for diagnostic vulnerability submissions.
- **[Community Code of Conduct](CODE_OF_CONDUCT.md)**: Binds evaluation community observers to professional collaborative standards under Contributor Covenant v2.1.
- **[Changelog Archive](CHANGELOG.md)**: Records sequential platform engineering progressions and historical milestone tagging.

---

## License

Copyright 2026 EIMS Project Engineering Team & Ratthabhumi. 
Licensed under **[All Rights Reserved / Source-Available Proprietary Policy](LICENSE)**.
