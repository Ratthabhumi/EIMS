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
- Developed an Offline USB Auditor importer with a comprehensive 4-column detailed Modal exposing OS, Network, Security, and Service telemetry.
- Persisted full offline report structures into the PostgreSQL database using `JSONB` and Alembic migrations.
- Refined Desktop Agent launch scripts (Sticker OCR Pipeline) for stealth/background UI execution.
- Standardized a cohesive, premium dark-mode minimalist UI across USB Auditor, Sticker OCR History, and System Observability pages.
- Resolved layout shift (scrollbar) issues using strict flexbox containment (`h-full`, `min-h-0`) for clean internal scrolling.
- Implemented real-time Search filtering, interactive A-Z sorting, and Export to CSV functionalities across asset data tables.
- Enhanced data readability by abstracting UUIDs and displaying structured formats (e.g. `DeviceID(SerialNumber)`) for OCR Records.

---

## 🏃 Current & Upcoming Sprints

### ✅ Sprint 8: Service Evaluation System (Admin & QR)
- **Goal**: Build a Cisco-style Post-Service Customer Evaluation System (ported from `clients/form_project`).
- **Tasks**:
  - Integrate database models for Training/Service Sessions and Assessment Responses.
  - Build Admin Dashboard to generate QR codes for specific service sessions.

### 📅 Sprint 9: Employee Evaluation Experience
- **Goal**: Complete the user-facing evaluation form.
- **Tasks**:
  - Build the minimalist, mobile-friendly Form for employees to rate the service (e.g. 1-5 stars, comments).
  - Implement form submission and link it back to the Admin Dashboard for average score tracking.

### 📅 Sprint 10: Global Search & Timeline
- **Goal**: Search the entire portal and view request timelines.
- **Tasks**:
  - Implement the `⌘K` global search.
  - Build the Request Tracking page and detail timeline.

### 📅 Sprint 11: High Availability & Clustering
- **Goal**: Enterprise scale reliability.
- **Tasks**:
  - Set up Redis Sentinel / PostgreSQL replication.
  - Load balancing across multiple worker instances.
