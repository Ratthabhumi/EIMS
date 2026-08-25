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

---

## 🏃 Current & Upcoming Sprints

### 📅 Sprint 10: Global Search & Timeline
- **Goal**: Search the entire portal and view request timelines.
- **Tasks**:
  - Implement the `⌘K` global search.
  - Build the Request Tracking page and detail timeline.

### 📅 Sprint 11: High Availability & Public Exposure
- **Goal**: Enterprise scale reliability and public accessibility.
- **Tasks**:
  - Set up Redis Sentinel / PostgreSQL replication.
  - Load balancing across multiple worker instances.
  - Setup Public Tunneling (e.g. ngrok) or Cloud Deployment (Vercel/Render) for external 5G access to Mobile Evaluation forms (QR Codes).
