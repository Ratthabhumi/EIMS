---
id: EDS-INDEX-001
version: 1.0.0
status: Approved
owner: Lead Software Architect
last_updated: 2026-08-04
review_cycle: Bi-annual
related_documents:
  - _style/document-standard.md
  - _style/writing-guide.md
  - _style/terminology.md
---

# EIMS Engineering Handbook

| Metadata | Value |
| :--- | :--- |
| **Document ID** | EDS-INDEX-001 |
| **Version** | 1.0.0 |
| **Status** | Approved |
| **Owner** | Lead Software Architect |
| **Last Updated** | 2026-08-04 |
| **Review Cycle** | Bi-annual |
| **Related Documents** | [Document Standard](_style/document-standard.md), [Writing Guide](_style/writing-guide.md), [Terminology](_style/terminology.md) |

---

## Introduction

This repository serves as the single source of truth for the **Enterprise Infrastructure Management System (EIMS)** engineering organization. EIMS is an enterprise-grade software platform engineered to centralize infrastructure discovery, hardware inventory, OCR-based asset registration, Windows log analysis, real-time telemetry monitoring, compliance assessment, and operational visibility across diverse distributed infrastructures.

The Engineering Handbook defines structural specifications, architectural trade-offs, database designs, communication protocols, deployment topologies, and verification procedures. Every engineering deliverable within this platform strictly adheres to the EIMS Documentation System (EDS).

---

## Handbook Navigation

The handbook organizes engineering documentation into dedicated functional boundaries to prevent duplication and preserve operational clarity.

### 1. Master Plan
Defines long-term product vision, system evolution strategy, lifecycle management, and overarching platform roadmap milestones.
- **Authoritative Document:** [01_EIMS_MASTER_PLAN.md](../01_EIMS_MASTER_PLAN.md)

### 2. Product Requirements
Consolidates functional and non-functional engineering requirements, personas, user workflows, operating domain constraints, and capacity targets.
- **Authoritative Document:** [02_PRODUCT_REQUIREMENTS_DOCUMENT.md](../02_PRODUCT_REQUIREMENTS_DOCUMENT.md)

### 3. Architecture
Outlines foundational software architectural boundaries, high-level structural blueprints, subsystem decoupling techniques, domain models, and core structural guidelines.
- **Software Architecture Document:** [03_SOFTWARE_ARCHITECTURE_DOCUMENT.md](../03_SOFTWARE_ARCHITECTURE_DOCUMENT.md)
- **System Blueprint:** [SYSTEM_BLUEPRINT.md](../SYSTEM_BLUEPRINT.md)
- **Engineering Guidelines:** [ENGINEERING_GUIDELINES.md](../ENGINEERING_GUIDELINES.md)
- **Legacy Architectural References:** [ARCHITECTURE.md](../ARCHITECTURE.md)

### 4. Database
Defines relational schemas, relational normalization boundaries, indexing strategies, audit persistence tables, migration procedures, and caching designs across PostgreSQL and Redis datastores.
- **Authoritative Document:** [04_DATABASE_DESIGN.md](../04_DATABASE_DESIGN.md)

### 5. API
Establishes OpenAPI/REST interface contracts, authentication headers, error payload schemas, synchronous webhooks, and gRPC internal service communication interfaces.
- **Authoritative Document:** [05_API_SPECIFICATION.md](../05_API_SPECIFICATION.md)

### 6. Engineering Standards (EDS)
Establishes the binding engineering writing conventions, document structure rules, canonical vocabulary dictionary, and structural diagram specifications.
- **Document Standard:** [_style/document-standard.md](_style/document-standard.md)
- **Writing Guide:** [_style/writing-guide.md](_style/writing-guide.md)
- **Terminology Guide:** [_style/terminology.md](_style/terminology.md)
- **Diagram Standard:** [_style/diagram-standard.md](_style/diagram-standard.md)
- **Canonical Document Template:** [_templates/document-template.md](_templates/document-template.md)

### 7. Security
Details identity and access management (IAM) frameworks, role-based access control (RBAC), TLS encryption enforcement, secret rotation protocols, and system threat modeling mitigations.
- **Authoritative Document:** [SECURITY.md](../SECURITY.md)

### 8. Deployment & Operations
Documents containerization topologies, Docker compositions, Kubernetes manifests, reverse proxy infrastructure, environment variable schemas, and CI/CD deployment execution pipelines.
- **Authoritative Document:** [DEPLOYMENT.md](../DEPLOYMENT.md)

### 9. Testing
Defines testing strategy frameworks covering unit test execution, functional API integration validation, end-to-end user browser simulations, regression benchmarking, and release gate verification.
- **Authoritative Document:** [TESTING.md](../TESTING.md)

### 10. Architecture Decision Records (ADR)
Contains immutable engineering records documenting architectural options considered, chosen engineering designs, context, trade-offs, and operational consequences.
- **Directory Repository:** [adr/](adr/)

### 11. References
Houses external protocol whitepapers, compliance specifications, industry compliance frameworks (NIST, CIS), and vendor API integrations supporting EIMS implementations.
- **Directory Repository:** [assets/](assets/)
