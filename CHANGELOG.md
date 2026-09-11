# Changelog

All notable architectural changes and feature releases for the **Enterprise Infrastructure Management System (EIMS)** will be documented in this historical journal.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres strictly to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) alongside our **EIMS Documentation System (EDS v1.0.0)** governance under our **Source-Available** licensing framework.

---

## [v0.3.0] - 2026-09-11

### Phase 12: Universal Global Search & Auth Hardening (Graduation Complete)
- **Universal Global Search & Command Center (`Ctrl+K` / `Cmd+K`)**:
  - Implemented dual result classification: `result_kind` (`navigation` | `entity`) preserving backward-compatible domain `type`.
  - Expanded search surface from 3 to 9 operational Search Providers: `NavigationSearchProvider`, `AssetSearchProvider`, `AuditLogSearchProvider`, `AnalysisSearchProvider`, `WindowsEventLogSearchProvider`, `UsbAuditorSearchProvider`, `OcrSearchProvider`, `TelemetrySearchProvider` (contextual anomaly/diagnostic discovery without bulk dumps), and `EvaluationSearchProvider`.
  - Contextual deep-linking: direct navigation to `/endpoints?id=...`, `/timeline?type=...&entity_id=...`, `/ocr`, `/usb`, `/analyzer`, and `/evaluations`.
  - Frontend Command Center UI: Grouped sections, badges, arrow-key navigation, enter-to-open, and query quick-filters.
- **Authentication Hardening**:
  - Typed configuration `AUTH_MODE: Literal["demo", "secure"]` with Pydantic case-insensitive validation.
  - Demo Mode: Allows normal dashboard operation and evaluation writes without authentication or hardcoded tokens.
  - Secure Mode: Enforces strict zero-trust boundary. Admin write operations require valid Admin JWT (`role == "admin"`) or server-side `ADMIN_TOKEN`.
  - Public default credentials sanitized in `.env.example` and `backend/core/config.py`.
- **System Stability & Reliability**:
  - Redis PubSub background listener task safely cancelled and awaited during FastAPI lifespan shutdown, resolving test hang.
  - Next.js frontend TypeScript errors resolved cleanly without `any` / `as any`.
  - Real PostgreSQL database integration tests added (`tests/test_global_search_integration.py` and `tests/test_auth_modes.py`) with transaction rollback and zero destructive operations.
  - All 76 automated backend tests GREEN (including `test_closed_loop_telemetry_ingestion_and_batch_processing`).

---

## [v0.2.0] - 2026-09-10

### Sprint 10: Global Search & Timeline
- PostgreSQL-first search (pg_trgm + tsvector), extensible Search Provider pattern, Timeline via UNION ALL.
- API endpoints: `/api/v1/search`, `/api/v1/timeline`, `/api/v1/audit-logs`, `/api/v1/telemetry/metrics`, `/api/v1/telemetry/winlogs`.
- Validation: 54/57 tests passed (3 pre-existing telemetry failures); migration round-trip verified.

### Sprint 11: Verifiability & Auth Hardening
- **Auth**: PBKDF2-SHA256 hashing, env-driven secrets, async login fix, composite admin gate (JWT + static token).
- **Telemetry**: Worker broker injection, stub persistence guard, EVTX bucket fix, JSON payload. 57/57 tests GREEN.
- **RAG**: VECTOR(768) to VECTOR(384) migration, fastembed verified, dead chromadb removed.
- **Benchmark**: Global Search p95 62ms, Timeline unfiltered p95 290ms, all endpoints under 310ms p95.

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
