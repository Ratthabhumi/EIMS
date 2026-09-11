# EIMS Project Roadmap
*Enterprise Information Management System*

This document tracks the historical and upcoming Sprints for the EIMS project, providing a high-level overview of our progress toward the ultimate World-Class Enterprise Portal.

---

## ✅ Completed Sprints

### Sprint 1: Project Initialization
- Initialized FastAPI backend and Next.js frontend structure.
- Established documentation standards (EDS v1.0.0, Core Laws).

### Sprint 2 - 4: Core Infrastructure & Asset Registry
- Configured PostgreSQL and Redis.
- Implemented SQLAlchemy ORM models for the Asset Registry.
- Setup `start_eims.bat` for one-click startup.

### Sprint 5: Database Refinements
- Migrated schemas using Alembic.
- Implemented PgBouncer for transaction pooling.

### Sprint 6: Real-time Observability
- Added Prometheus/Grafana infrastructure for metrics.
- Built a WebSocket-powered Real-time Dashboard in Next.js to monitor Security Alerts (Quarantines).
- Integrated background workers for telemetry ingestion.

### Sprint 7: Enterprise Portal & Endpoint Auditor
- Replaced the operational dashboard with a World-Class Enterprise Portal (Home) using Japanese Minimalist design principles.
- Established the `globals.css` Tailwind v4 design tokens (`#F5F3EE` backgrounds, Sage accents).
- Created a Global Navigation Sidebar and Command Palette Search layout.
- Decoupled **Endpoint Auditor** (Client Telemetry) from **System Observability** (Server Monitoring).
- Standardized 3 core portal categories: **Operations & AI**, **Client Agents** (Client Agents, USB Auditor, Sticker OCR), and **System & Infra**.
- Re-architected Theme management using a clean React 19 Context Native ThemeProvider with smooth dark/light transitions and zero script-injection errors.
- Built responsive toolbars with adaptive search fields and right-aligned metrics across all auditor dashboards.
- Standardized symmetrical header alignments, uniform subtext margins, and cohesive muted section indicator dots.
- Developed an Offline USB Auditor importer with a comprehensive 4-column detailed Modal exposing OS, Network, Security, and Service telemetry.
- Persisted full offline report structures into the PostgreSQL database using `JSONB` and Alembic migrations.
- Refined Desktop Agent launch scripts (Sticker OCR Pipeline) for stealth/background UI execution.
- Standardized a cohesive, premium dark-mode minimalist UI across USB Auditor, Sticker OCR History, and System Observability pages.
- Resolved layout shift (scrollbar) issues using strict flexbox containment (`h-full`, `min-h-0`) for clean internal scrolling.
- Implemented real-time Search filtering, interactive A-Z sorting, and Export to CSV functionalities across asset data tables.
- Enhanced data readability by abstracting UUIDs and displaying structured formats (e.g. `DeviceID(SerialNumber)`) for OCR Records.

### Sprint 8: Service Evaluation System (Admin & Mobile Form)
- **Goal**: Build a complete, Cisco-style Post-Service Customer Evaluation System (ported from `clients/form_project`).
- **Tasks**:
  - **Admin Dashboard**: Built a management portal to create Service Sessions (IT support, Training, etc.) and generate unique QR codes.
  - **Database Integration**: Implemented SQLAlchemy ORM models (`ServiceSession`, `ServiceEvaluation`) and ran Alembic migrations.
  - **Mobile-Friendly Evaluation Form**: Built a minimalist, responsive, user-facing form for employees/customers to rate the service (1-5 stars, dynamic questions, comments) upon scanning the QR code.
  - **Backend APIs**: Implemented FastAPI routes (CRUD) to create/edit/delete sessions, fetch session details, submit evaluation feedback, and delete responses.

---

### Sprint 9: AI Log Analyzer (EventIQ Integration & Vector RAG Engine)
- **Goal**: Integrate an intelligent, multi-modal, cross-platform Log Analyzer with Local Vector Semantic Search (RAG) and Root Cause Analysis (RCA).
- **Accomplishments**:
  - **Core Analyzer Architecture**: Unified EVTX, XML, CSV, Screenshot Images, and Raw Text log ingestion pipeline.
  - **Local Semantic Vector Engine**: Integrated `FastEmbed` / `all-MiniLM-L6-v2` generating 384-dimensional dense vectors 100% offline with zero API cost.
  - **PostgreSQL Vector RAG (pgvector)**: Configured Cosine Distance search (`<=>`) for self-learning historical diagnosis reuse.
  - **Multi-Platform Support**: Added heuristic & structured log parsers for Windows Event Viewer, Linux Syslog/Kernel (Segfault, Auth), Cloud Microservices JSON, and Network Firewalls (Fortinet FortiGate, Cisco ASA).
  - **Vision OCR Preprocessing**: Built adaptive image thresholding, binarization, and contrast scaling for sharp text extraction from screenshots.
  - **Curated Knowledge & Guaranteed References**: Curated expert offline diagnostics database and guaranteed minimum 3 official Microsoft / vendor references.
  - **Interactive User Feedback Loop**: Implemented UI feedback rating (Helpful 👍 / Not Helpful 👎) directly tuning vector confidence scores.
  - **Responsive Dashboard UI**: Designed responsive Tailwind v4 dark-mode layout with side-by-side Donut Chart, interactive Top-5 / View All provider breakdowns, and real-time history refresh.
  - **Enterprise Benchmark Testing**: Verified with automated test suites achieving **100/100 (Grade A+)** across Windows and Multi-Platform test cases with sub-second latencies (<0.9s).
  - **Operational Fixes & Dependency Sync**: Resolved Python/Node.js package desynchronization issues (`requests`, `react-hot-toast`) and cleared stale Redis telemetry cache causing `ForeignKeyViolationError` against the asset registry.

---

###  Sprint 10: Global Search & Timeline ✅ COMPLETED
- **Goal**: Implement cross-domain search capability and unified event timeline for operational visibility.
- **Accomplishments**:
  - Removed the placeholder portal search bar and replaced it with a fully functional `⌘K` Global Search command palette (Cmd/Ctrl+K, normalized results, safe internal navigation).
  - Implemented the Search Provider abstraction and registry with accurate Search domains: Asset + AuditLog (primary), Analysis (secondary).
  - Implemented a unified Timeline query layer (UNION ALL) across existing asset-linked domain tables (AuditLog, Telemetry, WinLog) — no new event table, `analysis_history` intentionally excluded.
  - Added database indexes for search performance (pg_trgm on hostname/IP/action_verb, tsvector GIN on `analysis_history`) via migration `d6a97e3f2b15`.
  - Added API endpoints: `/api/v1/search`, `/api/v1/timeline`, `/api/v1/audit-logs`, `/api/v1/telemetry/metrics`, `/api/v1/telemetry/winlogs`.
  - Built the Timeline UI page with type/severity filters and pagination.
  - Added tests for search, timeline, provider contracts, and migration integrity.
- **Validation**:
  - 22/22 targeted Sprint 10 tests passed (global search 9, timeline 8, migration 5).
  - Full backend suite: 54 passed / 3 pre-existing baseline failures (telemetry worker `broker=` argument mismatch) — no Sprint 10 regressions.
  - Real PostgreSQL migration round-trip passed (upgrade → downgrade → upgrade to head) for migration `d6a97e3f2b15`.
  - Search/timeline API integration validation passed against real PostgreSQL.
  - Frontend static validation passed for Sprint 10 files (0 lint errors, 0 warnings, 0 TypeScript errors).
- **Documented Limitations**:
  - Global Search p95 < 500 ms: NOT MEASURED (dataset too small for index effectiveness validation).
  - Timeline p95 < 300 ms: NOT MEASURED.
  - Browser E2E: NOT TESTED (repository has no browser E2E framework; static + runtime HTTP smoke verification only).

---

## ✅ Completed Phases

### ✅ Sprint 11: Verifiability & Auth Hardening
- **Auth Hardening**: PBKDF2-SHA256 hashing, env-driven secrets, async login, composite admin gate.
- **Telemetry Reconciliation**: 57/57 tests green (3 former failures fixed), worker broker injection, EVTX bucket consistency.
- **RAG Consistency**: VECTOR(384) migration aligned across DB/model/embedding; fastembed verified.
- **Benchmark Evidence**: 10k/50k/20k/20k dataset; Global Search p95=62ms, Timeline p95=290ms (all under 310ms).
- **Evidence Pack**: `docs/EVIDENCE_PACK.md`, `docs/BENCHMARK_RESULTS.md`.

---

### ✅ Phase 11.5: Hardening Audit
- Reviewed authentication surface, token lifecycle, and admin gate logic.
- Identified EIMS-ADMIN-TOKEN hardcoded in evaluations admin pages (deferred to Phase 12.2).
- Documented remaining auth debt before graduation freeze.

---

### ✅ Phase 12.0: Data Integrity Investigation
- Confirmed that `tools/sprint11_benchmark.py` executed `TRUNCATE ... CASCADE` against `eims_registry` on 2026-09-10.
- **CONFIRMED DATA LOSS**: `infrastructure_assets` (10,000 rows), `audit_logs` (50,000 rows), `telemetry_metrics` (20,000 rows), `windows_event_logs` (20,000 rows) — all benchmark-synthetic, original real rows destroyed.
- **Survived intact**: `analysis_history` (8 real records), MinIO `eims-ocr-manifests` (8 sticker JPG objects), USB report JSON.
- Alembic migration head `8a2b4d6f9c1e` — unchanged.

---

### 🟡 Phase 12.1: Data Recovery & Demo Reconstruction
- **Status**: Complete — original real data NOT recoverable from DB; surviving sources preserved and demo data reconstructed.
- **Backup**: `backups/eims_pre_recovery_20260910_162200.dump` (~5 MB, PostgreSQL custom format, gitignored).
- **Benchmark Safety Fixed**: `tools/sprint11_benchmark.py` now requires `EIMS_BENCHMARK_DATABASE_URL` and refuses to run against any database whose name ends in `registry`. Safety guard tested by `tests/test_benchmark_safety.py` (8/8 PASS).
- **Demo Dataset Reconstructed** (non-destructive, alongside benchmark rows):
  - 5 demo assets: AI-WORKER-001, KEL-PROD-WEB-01, KEL-PROD-DB-01, SECURITY-SIEM-01, KEL-OFFICE-PC-001
  - 8 audit events (coherent incident story: GPU spike → AUTH_FAILURE → SIEM alert → analysis)
  - 8 telemetry events (CPU anomaly, GPU thermal data)
  - 7 Windows event logs (AUTH_FAILURE, GPU service crash, audit clear, new user)
  - 8 analysis records — **REAL SURVIVING DATA** (not reconstructed)
- **OCR**: 8 MinIO objects preserved. `ocr_registration_records` metadata reconstructed from object names (record_ids embedded in filenames). OCR text not recovered (tesseract unable to re-extract). 8 records visible in Sticker OCR History UI.
- **USB Auditor**: Real report `5CD0141N35-Int3_11-08-2026_14.43.json` imported via existing `/api/v1/assets/import-report` endpoint. Asset visible and searchable.
- **Data Classification**:
  - `REAL SURVIVING DATA`: analysis_history (8 rows), MinIO OCR objects (8), USB report (1 JSON)
  - `RECONSTRUCTED DEMO DATA`: demo assets (5), demo audit (8), demo telemetry (8), demo winlog (7), USB-imported asset (1), OCR DB metadata (8)
  - `SYNTHETIC BENCHMARK DATA`: infrastructure_assets (10,000), audit_logs (50,000), telemetry_metrics (20,000), windows_event_logs (20,000)
- **Known Limitations**:
  - Original pre-benchmark rows in 4 tables are permanently lost from DB.
  - OCR extracted text cannot be recovered without reprocessing (tesseract not configured in this environment).
  - `EIMS-ADMIN-TOKEN` still hardcoded in evaluations admin pages — deferred to Phase 12.2.
  - Analysis History page (`/api/v1/history/`) requires auth token (works correctly when authenticated).

---

## 🏃 Upcoming Phases

### ✅ Phase 12.2: Auth Boundary / Access Hardening
- **Goal**: Implement explicit Demo Mode / Secure Mode boundary.
- **Accomplishments**:
  - Added `EIMS_AUTH_MODE` configuration (demo/secure) in `backend/core/config.py`
  - Modified `get_current_user` in `backend/domain/analyzer/auth.py`:
    - Demo mode: returns "demo" identity without login
    - Secure mode: requires valid JWT, raises 401 if missing/invalid
  - Updated `require_admin` and `require_admin_or_token` to handle demo identity
  - Updated evaluations router to use mode-aware admin dependency
  - Added tests for both modes

### ✅ Phase 12.3: Remove Hardcoded Admin Token
- **Goal**: Remove `EIMS-ADMIN-TOKEN` from frontend source code.
- **Accomplishments**:
  - Removed hardcoded `"Authorization": "Bearer EIMS-ADMIN-TOKEN"` from:
    - `clients/dashboard/src/app/evaluations/admin/page.tsx`
    - `clients/dashboard/src/app/evaluations/admin/[session_id]/page.tsx`
  - Admin write operations now use backend `verify_admin_token` / `require_admin_for_write` dependency
  - Frontend no longer contains any privileged static token
  - Verified with grep: zero occurrences of `EIMS-ADMIN-TOKEN` in frontend source

### ✅ Phase 12.4: Login UI Decision
- **Decision**: No mandatory login screen in Demo Mode.
- **Implementation**:
  - Demo Mode (default): Dashboard opens immediately, no login required
  - Secure Mode: Authentication enforced via JWT; login endpoint available at `/api/v1/auth/login`
  - Login page UI deferred — security boundary takes priority over visual polish
  - Existing PBKDF2-SHA256 auth backend ready for Secure Mode

### ✅ Phase 12.5: Final Demo / Evidence / Graduation Freeze
- **Setup Script Hardened**: `setup.bat` now determines repository root from `%~dp0`, validates prerequisites, fails with non-zero exit code on error, no fake SUCCESS
- **Data Integrity Verified**:
  - Demo dataset intact (5 assets, 8 audit, 8 telemetry, 7 winlog events)
  - Analysis history (8 REAL surviving records) preserved
  - Benchmark safety guard enforced (8/8 tests pass)
- **Data Classification**:
  - REAL SURVIVING DATA: `analysis_history` (8 rows), MinIO OCR objects (8), USB audit report (1 JSON)
  - RECONSTRUCTED DEMO DATA: 5 assets, 8 audit events, 8 telemetry vitals, 7 winlog events, 8 OCR metadata, 1 USB-imported asset
  - SYNTHETIC BENCHMARK DATA: isolated, benchmark safety guard prevents accidental truncation

### ✅ Phase 12.6: Universal Global Search & Auth Hardening (Graduation Complete)
- **Universal Search / Command Center (`Ctrl+K` / `Cmd+K`)**:
  - Dual Result Classification: `result_kind` (`navigation` | `entity`) with backward-compatible domain `type`
  - 9 Search Providers operational:
    1. `NavigationSearchProvider` (10 verified Next.js routes with keyword matching)
    2. `AssetSearchProvider` (`infrastructure_assets` hostname, IP, MAC, serial, model, vendor)
    3. `AuditLogSearchProvider` (`audit_logs` action verb, actor, payload)
    4. `AnalysisSearchProvider` (`analysis_history` query, summary, remediation)
    5. `WindowsEventLogSearchProvider` (`windows_event_logs` event ID, level, EVTX metadata, e.g. 4625)
    6. `UsbAuditorSearchProvider` (`offline_report_data` USB vendor, device, serial number)
    7. `OcrSearchProvider` (`ocr_registration_records` serial, vendor, model, OCR raw text)
    8. `TelemetrySearchProvider` (`telemetry_metrics` contextual diagnostic payload and asset discovery, avoiding bulk time-series dumps)
    9. `EvaluationSearchProvider` (`service_sessions` session title, target service, notes)
  - Contextual Navigation: Results deep-link to specific asset details, filtered timelines (`?type=...&entity_id=...`), OCR history, USB evidence, and analyzer
  - Command Center UI: Grouped sections with badges, keyboard navigation (Up/Down/Enter/Esc), quick filters
- **Auth Hardening**:
  - Typed configuration `AUTH_MODE: Literal["demo", "secure"]` with Pydantic validation
  - Demo Mode: Dashboard usage and evaluation writes work seamlessly without login and without hardcoded frontend tokens
  - Secure Mode: Admin JWT (`role == "admin"`) and server-side `ADMIN_TOKEN` properly validated; protected endpoints reject unauthenticated calls
  - Public default credentials sanitized in `.env.example` and `backend/core/config.py`
- **Lifespan & Test Suite**:
  - Redis PubSub background task safely cancelled and awaited during FastAPI lifespan shutdown
  - 76/76 tests pass (100% GREEN), including `test_closed_loop_telemetry_ingestion_and_batch_processing`
  - Real PostgreSQL integration tests added with transaction rollback (zero TRUNCATE/DELETE-all)
- **Frontend Quality**:
  - Zero TypeScript errors (`npx tsc --noEmit` clean)
  - Production build verified (`npm run build` generates all routes)

### ✅ Phase 12.7: AI Log Analyzer Operational Catalog, Dynamic Metrics & Visual Polish
- **141 Operational Event Catalog**:
  - Complete static knowledge base covering 141 critical Windows, security, and infrastructure event definitions (Security 4625, 4624, 4740, 1102; System 7036, 6008, 41; PowerShell 4104; Defender 1116; Firewall 5152; etc.)
  - Full operational descriptions, categories, keyword indexes, related events, and administrator mitigation advice
  - Strict provenance isolation: catalog items serve as reference knowledge and are never counted as runtime analyzed logs
- **Data Integrity & Metric Semantics**:
  - `Total Logs Analyzed`: Derived strictly from the `analysis_history` table (9 real records: 8 Windows event logs + 1 AI incident investigation)
  - `Critical Errors`: Derived strictly from actual analyzed records (`AINC-2026-0910-0001` flagged with `isCritical: true` = 1)
  - `Avg Search Time`: Replaced static/misleading `0.00s` with honest dynamic `performance.now()` client-side latency measurement. Displays `—` initially, then averages all real user searches performed in the session (e.g., 16 ms)
- **Event Types by Category Analytics**:
  - Replaced coarse provider chart with a horizontal bar chart (`BarChart layout="vertical"`)
  - Real-world categorization across 7 operator categories derived from actual event semantics:
    - Authentication (2): Events 4625, 4624
    - System (2): Events 7036, 6008
    - Account Management (1): Event 4720
    - Windows Update (1): Event 2004
    - Application (1): Event 1001
    - Security (1): Event 1102
    - Incident Investigation (1): AINC-2026-0910-0001
    - Total = 9 (100% matches Total Logs Analyzed)
- **Strict 7-Day Trend Window**:
  - `Daily Trends`: Fixed window to exactly the last 7 calendar days (09/05 to 09/11) with zero-value day preservation
- **Layout Height Alignment & UX Polish**:
  - Responsive `ResizeObserver` sync (`xl:h-[var(--left-col-height)]`) guaranteeing the right Result Panel bottom aligns flush with the left sidebar's Common Event IDs panel (zero page-level scrolling)
  - Muted enterprise theme: softened electric blue, neon green, and bright purple accents into an elegant dark enterprise palette while retaining semantic color identities
