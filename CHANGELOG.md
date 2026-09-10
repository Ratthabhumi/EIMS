# Changelog

All notable architectural changes and feature releases for the **Enterprise Infrastructure Management System (EIMS)** will be documented in this historical journal.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres strictly to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) alongside our **EIMS Documentation System (EDS v1.0.0)** governance under our **Source-Available** licensing framework.

---

## [v0.2.0] - 2026-09-10
### In Progress — Sprint 10: Global Search & Timeline
- **Design Approved**: Architecture review completed with corrections for search scope, provider registry, and performance targets.
- **Documentation Updated**:
  - Updated `03_SOFTWARE_ARCHITECTURE_DOCUMENT.md` with EIMS Query Layer architecture, Search Provider pattern, and Timeline design.
  - Updated `04_DATABASE_DESIGN.md` with search indexes (pg_trgm, tsvector GIN) for Global Search.
  - Updated `05_API_SPECIFICATION.md` with new endpoints: `/api/v1/search`, `/api/v1/audit-logs`, `/api/v1/timeline`, `/api/v1/telemetry/metrics`, `/api/v1/telemetry/winlogs`.
  - Updated `ROADMAP.md` with Sprint 10 status and architecture details.
- **Architecture Decisions**:
  - PostgreSQL-first search (pg_trgm + tsvector) — no external search engine for Sprint 10.
  - Extensible Search Provider pattern for future module integration.
  - Search domains: Asset + AuditLog (primary), Analysis (secondary); Telemetry/WinLog/Hardware retained as timeline sources only.
  - Timeline built from asset-linked domain tables (AuditLog, Telemetry, WinLog) — no new event table.
  - Normalized search result contract for consistent frontend integration.
- **Performance Targets** (acceptance criteria until measured):
  - Global Search p95 < 500 ms.
  - Timeline p95 < 300 ms.
- **Status**: Documentation update complete. Implementation pending approval.

---

## [v0.1.0] - 2026-08-04
### Added — Documentation Foundation Complete
- **EDS Constitution Established**: Initialized the canonical EIMS Documentation System (`EDS v1.0.0`) setting binding writing tone rules, terminology compliance catalogs, and Mermaid visual diagram palettes.
- **Core Law 1 (`01_EIMS_MASTER_PLAN.md`)**: Documented architectural engineering vision, technology selection trade-offs (FastAPI, Next.js, PostgreSQL, Redis, MinIO, Docker), C4 system telemetry pipelines, and Sprint 1–7 release milestones.
- **Core Law 2 (`02_PRODUCT_REQUIREMENTS_DOCUMENT.md`)**: Specified over 25 verifiable functional and non-functional engineering requirement trace codes (`REQ-DISC-01` to `NFR-SCALE-02`) and operational persona security authorization domains.
- **Core Law 3 (`03_SOFTWARE_ARCHITECTURE_DOCUMENT.md`)**: Detailed Hybrid Modular Monolith runtime boundaries, asynchronous event ingestion sequences (<15ms HTTP 202 acknowledgment targets), PgBouncer transaction connection pooling, and asset lifecycle state machines.
- **Core Law 4 (`04_DATABASE_DESIGN.md`)**: Configured relational PostgreSQL database schemas, Entity-Relationship mappings (`erDiagram`), declarative time-series table partitioning for telemetry/event metrics, Volatile-LRU Redis namespaces, and zero-downtime Alembic migration rules.
- **Core Law 5 (`05_API_SPECIFICATION.md`)**: Established HTTPS OpenAPI REST administrative contracts, edge mTLS ingestion boundaries, asynchronous WebSocket streaming (`WSS /api/v1/ws/dashboard`), and RFC 7807 Problem Details error schemas.
- **Source-Available Repository Foundation**: Initialized All Rights Reserved licensing terms (`LICENSE`, `NOTICE`), comprehensive `.gitignore` exclusion paths, GitHub template automations (`.github/`), internal contributing governance guidelines, and security policies.

---

## [v0.0.0] - 2026-08-04
### Added — Repository Initialized
- Scaffolding of Git version control structures and initial project workspace directory definitions.
