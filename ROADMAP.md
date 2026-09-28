# Enterprise Infrastructure Management System (EIMS) — Project Roadmap
*Cooperative Education Engineering Roadmap & Finalization Freeze*

This document tracks the engineering lifecycle, release provenance, historical sprints, and cooperative education finalization roadmap for the EIMS project.

---

## 📌 Source of Truth & Release Provenance

### A. Canonical Frozen Release: `v0.3.0`
- **Release Tag:** `v0.3.0` (Annotated tag, immutable release baseline)
- **Dereferenced Commit:** `bb9210f06256c3adc0c7901352d08e1a026a8027`
- **Scope Included:** Sprints 1–11, Phase 11.5, Phase 12.0–12.7 (Universal Search, Auth Boundary, 141 Operational Catalog, Honest Metric Semantics, Visual Polish).
- **Release Status:** **FROZEN**. The `v0.3.0` release tag will not be moved, retagged, or updated.

### B. Post-`v0.3.0` Main Hardening & Field Integration
- **Branch:** `main` (HEAD: `acb855f2f47b8ea8aa17073d504ec522c7d1a104`)
- **Nature of Changes:** Targeted field integration, preflight safety, and reliability fixes following real field testing. These commits are *not* part of `v0.3.0` and represent post-release operational hardening:
  - `0761211`: **feat: connect portable infrastructure evidence to analyzer** — Ingests offline JSON evidence into central registry and routes prioritized event evidence to the AI analyzer.
  - `9ef3580` / `8f25c68`: **feat(usb-auditor): add portable USB builder** — Standalone USB auditor packager; reports worktree cleanliness from tracked git state only.
  - `a682627` / `d7c1fc3` / `9ad9566`: **feat(tools) / fix(usb-auditor): harden EIMS USB builder preflight and drive safety** — Eliminates BitLocker recovery key exposure risk, adds drive preflight safety guards, and strips sensitive material.
  - `c16b820`: **fix(dashboard): resolve responsive sidebar hydration mismatch** — Eliminates SSR/client React hydration discrepancies in the navigation layout.
  - `acb855f`: **fix(backend): import Optional in analyzer history router so asset_id filter stops 500** — Restores filtered history queries by asset ID for endpoint-specific AI findings.

---

## 🛑 CO-OP Finalization & Graduation Evidence Freeze

- **Freeze Window:** 2026-09-28 → 2026-10-20
- **Operational Mode:** **MAJOR FEATURE DEVELOPMENT IS STRICTLY FROZEN**
- **Core Mission:** The project has completed its feature-building phase. The objective from 2026-09-28 through 2026-10-20 is stabilizing existing capabilities, executing authorized real-world validation, gathering defensible engineering evidence, preparing the graduation thesis report and defense materials, and preventing scope creep.

### Allowed Activities (2026-09-28 → 2026-10-20)
- P0/P1 blocker and regression fixes
- Test suite and CI/CD stabilization
- Demo workflow reliability and deterministic seeding
- Engineering and academic documentation
- Real field evidence capture and strict data anonymization
- KMITL cooperative education report preparation (Chapters 1–5)
- Presentation slides, runbook rehearsal, and A1 poster layout
- Accessibility, hydration, or error-state polish *only* when justified by a verified defect with low regression risk

### Prohibited Activities (Frozen without explicit authorization)
- ❌ Cross-Endpoint Correlation
- ❌ Distributed Kubernetes (K8s) deployment or Helm packaging
- ❌ High-Availability (HA) clustering (PostgreSQL replicas, Redis Sentinel)
- ❌ Enterprise SSO (SAML 2.0 / OIDC / Active Directory)
- ❌ Major RBAC architecture redesign
- ❌ New AI models, vector stores, or search engines
- ❌ Database schema overhauls or disruptive migrations
- ❌ Agent fleet management automation or remote daemon distribution
- ❌ Mobile application development
- ❌ External SIEM / syslog forwarder integrations
- ❌ Large-scale architectural refactoring

*All features above are deferred to the Post-Graduation Roadmap.*

---

## 🎯 Current Definition of Done (CO-OP DoD)

To ensure academic and engineering rigor, the platform must satisfy the following 10 verification gates prior to graduation sign-off:

| # | Gate | Requirement & Acceptance Criteria | Verification Status |
|---|---|---|---|
| 1 | **Portable Collector** | Portable USB Auditor package with an embedded Python runtime; the target Windows host requires no preinstalled Python, pip, Git, Docker, or EIMS backend. Local JSON report generated with package integrity verification. | VERIFIED |
| 2 | **Offline Evidence Import** | EIMS backend successfully imports JSON report via `/api/v1/assets/import-report`, creating or updating the asset record and persisting raw telemetry. | VERIFIED |
| 3 | **Windows Event Evidence** | Ingested System and Application event logs are properly structured, categorized, and visible in asset-linked views with complete collection metadata. | VERIFIED |
| 4 | **Sequential Dedup** | Application-level sequential deduplication prevents duplicate log creation when identical reports are imported sequentially. *(Note: Documented honestly as sequential application protection; does NOT guarantee concurrent DB-level uniqueness).* | VERIFIED |
| 5 | **Analyzer Integration** | Priority-ranked events from imported evidence feed directly into the analyzer pipeline, strictly capped at a maximum of 10 events per import run. | VERIFIED |
| 6 | **AnalysisHistory Provenance** | Analysis records maintain complete audit provenance: linked `asset_id`, `event_source_id`, and `source_type = USB_OFFLINE_COLLECTION`. | VERIFIED |
| 7 | **Filtered History API** | Backend endpoint `/api/v1/history/?asset_id={id}` successfully returns historical analysis records scoped to the specified asset without HTTP 500 errors. | VERIFIED |
| 8 | **Endpoint AI Findings UI** | Dashboard endpoints page displays AI diagnostic findings and recommendations corresponding to the specific asset. | FIELD VERIFY REQUIRED *(Real-data browser field verification in environment with authorized Windows Server evidence)* |
| 9 | **Test & Build Evidence** | Backend automated test suites pass cleanly with zero regression; Next.js frontend builds cleanly (`npm run build`) with zero TypeScript errors. | VERIFIED |
| 10 | **Confidentiality Review** | 100% of artifacts, screenshots, reports, and presentation slides are sanitized and anonymized (no customer hostnames, IPs, MACs, serials, accounts, or secrets). | ACTIVE AUDIT |

---

## 🎬 Primary Hero Demonstration Workflow

The primary demonstration for faculty and industry mentors follows a single defensible end-to-end engineering pipeline:

```
[ Authorized Windows Endpoint ]
              │
              ▼
[ Portable USB Auditor (BAT Runner + Embedded Python + WMI / EVTX) ]
              │
              ▼
[ Offline JSON Evidence (Verified Portable Package) ]
              │
              ▼
[ EIMS Central Ingestion Engine (/api/v1/assets/import-report) ]
              │
              ▼
[ Central Asset Registry + 49 Structured Windows Events ]
              │
              ▼
[ Sequential Dedup + Priority Ranking Filter ]
              │
              ▼
[ AI Log Analyzer (RAG Vector Similarity, max 10 events) ]
              │
              ▼
[ AnalysisHistory DB Persistence (Provenance & Audit Trail) ]
              │
              ▼
[ Filtered History API (/api/v1/history/?asset_id=...) ]
              │
              ▼
[ Endpoint AI Findings & Mitigation View in Dashboard ]
```

### Engineering Rationale
- **End-to-End Cohesion:** Demonstrates the complete operational lifecycle: offline field acquisition, central ingestion, schema normalization, automated AI-assisted diagnostics, and interactive administrative visibility.
- **Defensible Scope:** Focuses on air-gapped infrastructure management where agents cannot be installed as persistent daemons due to customer security constraints.
- **Honest Positioning:**
  - EIMS is an **operational management and triage assistance platform**, not a certified digital forensics acquisition suite.
  - AI diagnostic outputs are **investigative recommendations**, not guaranteed or authoritative root-cause conclusions.

---

## 📊 Graduation Evidence Pack Matrix

The graduation evaluation is backed by six structured operational evidence workflows:

| # | Workflow Domain | Engineering Question Demonstrated | Execution / Evidence Needed | Expected Proof | Confidentiality Requirement | Current Status |
|---|---|---|---|---|---|---|
| 1 | **Infrastructure Asset Management** | Can EIMS accurately track hardware, network configurations, and lifecycle metadata for diverse enterprise hosts? | Ingest offline reports and view asset inventory in web dashboard. | Asset cards, interface listings, storage stats, serial/vendor tracking. | Anonymize hostnames, MAC addresses, internal IP subnets, and serials. | **VERIFIED** |
| 2 | **Portable USB / Offline Auditor** *(Hero)* | Can infrastructure evidence be collected from isolated/air-gapped Windows servers without agent installation? | Run portable USB Auditor package (`Run-EIMS-Audit.bat`) on target machine; verify generated JSON schema and integrity. | Portable directory structure, execution log, validated JSON output. | Sanitize customer host identity, domain names, and user accounts. | **VERIFIED** |
| 3 | **Windows Event Evidence** *(Hero)* | Can critical event logs (System and Application) be parsed, structured, and presented contextually? | Import evidence JSON; inspect parsed Windows events linked to asset. | Event table showing EventID, Level, Provider, and parsed XML data. | Strip raw user SIDs, customer account names, and private network IPs. | **VERIFIED** |
| 4 | **AI-assisted Log Analysis** *(Hero)* | Can vector RAG and rule heuristics assist system operators in triaging Windows operational failures? | Execute analyzer on imported evidence; observe Top-10 prioritized events and mitigation advice. | Cosine similarity scores, RAG reference citations, AnalysisHistory records. | Mask customer-specific application log paths or internal server names. | **FIELD VERIFY REQUIRED** *(Browser UI with server data)* |
| 5 | **Security & Compliance** | Can automated checks evaluate endpoint security posture (firewall, BitLocker, antivirus, updates)? | Ingest and inspect security posture metrics in endpoint details view. | Security posture score, BitLocker status, AV definition state. | **STRICT:** Redact BitLocker recovery IDs/passwords; mask policy names. | **VERIFIED** |
| 6 | **Global Search & Historical Tracking** | Can administrators efficiently locate assets, audit trails, and historical analyses across system domains? | Perform `Ctrl+K` searches across 9 registered search providers; query timeline. | Keyboard-navigated search palette results, latency metrics (<300ms). | Ensure sample search queries do not expose proprietary enterprise data. | **VERIFIED** |

*Supporting Capabilities Note:* Optical Character Recognition (Sticker OCR) and System Observability (Prometheus/Grafana) serve as secondary supporting workflows and will be referenced in documentation rather than showcased live.

---

## ⚖️ Claims & Academic Honesty Policy

EIMS maintains strict engineering transparency and academic integrity across all documentation, presentations, and reports:

### Permitted Claims (Verified by Repository & Test Evidence)
- Fully functioning offline Windows infrastructure evidence collector requiring zero target dependencies.
- Centralized web portal for asset management, event investigation, and administrative auditing.
- Automated application-level sequential deduplication of imported telemetry reports.
- Offline-capable AI log triage assistance leveraging local FastEmbed vector embeddings and pgvector semantic retrieval.
- Multi-domain universal search (`Ctrl+K`) indexing assets, logs, analyses, and navigation routes.
- Basic security compliance indicators (BitLocker protection status, firewall profile state, OS patch recency).

### Prohibited Claims (Strictly Forbidden)
- ❌ **Do NOT claim production-ready commercial SaaS readiness.** EIMS is an architectural prototype and cooperative education engineering project.
- ❌ **Do NOT claim certified digital forensic acquisition capabilities.** EIMS collects administrative diagnostics via standard WMI/CIM/EVTX; it is not a forensically sound evidentiary tool (no write-blockers, no raw disk imaging).
- ❌ **Do NOT claim concurrent DB-level uniqueness guarantees.** Deduplication is performed at the application layer during sequential ingestion; race conditions during concurrent imports remain an unmitigated limitation.
- ❌ **Do NOT claim recovery of original database rows destroyed during the 2026-09-10 benchmark incident.** Historical truth: original pre-benchmark rows in 4 tables were destroyed by `TRUNCATE CASCADE`; surviving data comprises 8 real analysis records, MinIO OCR objects, and 1 USB JSON report, alongside reconstructed demo data.
- ❌ **Do NOT conflate the static 141 Operational Event Catalog with runtime analyzed events.** The 141 entries serve purely as reference knowledge definitions; analyzed metrics must reflect only true `analysis_history` records.
- ❌ **Do NOT claim AI findings represent authoritative or guaranteed root cause diagnoses.** AI findings are diagnostic assistance tools with explicit confidence ratings and vendor references.
- ❌ **Do NOT claim High Availability, Kubernetes orchestration, or Enterprise SSO as implemented features.** These remain conceptual roadmap items for post-graduation lifecycle development.

---

## 🔒 Public-Repository Confidentiality Policy

Because the `Ratthabhumi/EIMS` repository is publicly accessible for portfolio evaluation, strict data protection protocols apply:

### Prohibited Artifacts in Git Tracking
Under no circumstances may the following data types be committed, staged, or pushed:
- Real customer or enterprise hostnames and domain names
- Public or private customer IP addresses (IPv4/IPv6)
- Physical MAC addresses and hardware serial numbers
- Customer usernames, administrator accounts, or user SIDs
- Raw customer business logs or proprietary application data
- Internal corporate network topologies and IP routing tables
- Passwords, API keys, JWT secret keys, or cryptographic private keys
- **BitLocker Recovery Passwords or recovery key identifiers**
- Unredacted screenshots displaying customer-identifiable data

### Academic Screenshot & Artifact Sanitization Rules
- All screenshots utilized in the Final Report, presentation slides, or poster must be sanitized, cropped, or masked.
- Standard synthetic replacement identifiers must be used (e.g., `KEL-PROD-WEB-01`, `192.168.1.100`, `00:1A:2B:3C:4D:5E`).
- Real-world evidence gathered during field testing must be stored strictly in local, untracked, gitignored directories or company-managed secure storage.

---

## 🏷️ Release & Tagging Policy

- **Canonical Baseline:** Release tag `v0.3.0` (`bb9210f06256c3adc0c7901352d08e1a026a8027`) is permanently frozen.
- **Git State:** Current `main` contains post-`v0.3.0` field integration, bug fixes, and safety hardening.
- **Future Tagging:** If a final graduation release snapshot tag is desired (e.g., `v0.3.1` or `v0.4.0`), it will:
  1. Be created as a **new** tag, never reusing or moving `v0.3.0`.
  2. Require explicit human authorization after all field validation gates are verified.
  3. **No new git tag will be created during this documentation update.**

---

## 🎓 CO-OP Academic & Administrative Deliverables

To fulfill KMITL Cooperative Education requirements, project outputs must align with official university evaluation standards:

### KMITL Evaluation Weight Distribution
| Document / Event | Evaluator | Weight | Key Criteria & Evaluation Scope |
|---|---|---|---|
| **COOP.201** | Faculty Supervisor & Job Supervisor | **20%** | Workplace supervision record; tripartite consultation between academic advisor, student, and industrial mentor regarding project progress and workplace conduct. |
| **COOP.202** | Examination Committee | **40%** | Post-internship evaluation upon return to university:<br>• **Presentation Examination:** 20% (Clarity, flow, defense, live demo)<br>• **Final Report Quality:** 20% (Technical depth, structure, academic rigor) |
| **COOP.304** | Company Job Supervisor | **40%** | Workplace performance and final project evaluation:<br>• Evaluates work planning, project execution, independence, and technical quality.<br>• Must be submitted within one week following internship completion.<br>• **Confidential Document:** Must be handled through official corporate channels, not transported openly by the student. |

### Administrative Planning Tracking
- **COOP.104 (Job Assignment):** Completed. Recorded initial general assignment as *Infrastructure Deployment, Configuration and Support*.
- **COOP.105 (Action Plan):** Completed. Officially established the project title as **Development of an Enterprise Infrastructure Management System (EIMS)** with an 8-stage work breakdown (Requirement/Design, Asset Management, Endpoint Auditing, Event Logs, Troubleshooting, Security/Compliance, Testing, Documentation).
- **COOP.303 (Pre-Evaluation):** Completed / pending final administrative confirmation.
- **Project Title Consistency Policy:**
  - All formal outputs (Final Report, Presentation Slides, A1 Poster, COOP.201, COOP.202, COOP.304) will consistently utilize the official project title:
    > **"Development of an Enterprise Infrastructure Management System (EIMS)"**
  - Historical differences between COOP.104 and COOP.105 represent standard assignment maturation and project evolution, permitted by university guidelines. Prior forms will not be retroactively altered.

### Privacy Policy for Public Documentation
- Student ID, personal telephone numbers, personal email addresses, home addresses, company HR contacts, and mentor direct phone/email data **must never be published** in this repository or tracked files.

---

## 📅 Date-Based Closeout Timeline (2026-09-28 → 2026-10-20)

| Timeframe | Phase | Key Engineering & Academic Outputs | Exit Gate |
|---|---|---|---|
| **2026-09-28 → 2026-09-30** | **Scope Freeze & Audit** | • Finalize scope boundaries and freeze major feature development.<br>• Update authoritative `ROADMAP.md`.<br>• Audit documentation, git status, and test suites.<br>• Coordinate COOP.201 supervision schedule. | Zero new major feature branches initiated. |
| **2026-10-01 → 2026-10-04** | **Field Validation & Evidence Capture** | • Execute USB collector on authorized Windows Server endpoints.<br>• Import real evidence into EIMS; verify asset creation and event parsing.<br>• Validate AI Analyzer prioritization and History API.<br>• Capture clean, anonymized screenshots for report. | Hero E2E workflow successfully demonstrated and documented. |
| **2026-10-05 → 2026-10-08** | **Blocker Fixes & Demo Stabilization** | • Resolve P0/P1 blockers or regressions discovered during field validation.<br>• Stabilize local demo runner scripts (`start_eims.bat`, seeders).<br>• Lock demo dataset candidate. | Full test suite green; demo environment repeatable and stable. |
| **2026-10-09 → 2026-10-12** | **Final Report: Chapters 1–3** | • Author Chapter 1: Introduction, Problem Statement, Objectives, Scope.<br>• Author Chapter 2: Concepts, Technologies, Related Work (FastAPI, Next.js, pgvector, EVTX).<br>• Author Chapter 3: System Design, Architecture, Data Model, USB Workflow, Ingestion, AI Pipeline. | Chapters 1–3 draft complete and internally reviewed. |
| **2026-10-13 → 2026-10-16** | **Final Report: Chapters 4–5 & Front Matter** | • Author Chapter 4: Results, Measured Performance, Test Verification.<br>• Author Chapter 5: Summary, Known Limitations, Recommendations.<br>• Compose Thai Abstract, English Abstract, References, and Appendices. | Complete full report draft compiled. |
| **2026-10-17 → 2026-10-19** | **Review, Rehearsal & Package Readiness** | • Industrial mentor review of draft report.<br>• Rehearse oral presentation and live hero demo execution.<br>• Prepare offline backup demo video / screenshots.<br>• Finalize COOP.304 company evaluation package. | Submission-ready package assembled; demo rehearsed. |
| **2026-10-20** | **Workplace Stage Closeout** | • Conclude on-site cooperative education workplace duties.<br>• Hand off confidential COOP.304 evaluation to company supervisor.<br>• Securely preserve company-approved evidence artifacts. | Workplace phase formally concluded. |
| **Post-2026-10-20** | **Academic Submission & Examination** | • Incorporate advisor feedback into final report.<br>• Design and print A1 Academic Poster.<br>• Prepare final PowerPoint slide deck and PDF submission.<br>• Attend final defense examination. | *Official 2026 faculty submission deadline: TBD / must be confirmed from the current academic-year announcement.* |

> [!WARNING]
> **Academic Deadline Notice:** Prior KMITL manuals cite a historical deadline of *15 December 2025*. That date is specific to the 2025 academic calendar and must **not** be assumed for 2026. Official 2026 faculty deadlines must be confirmed directly from the current institutional schedule.

---

## 📖 Cooperative Education Final Report Structure

The Final Report will follow the standard 5-chapter academic engineering framework:

- **Front Matter**
  - Thai Abstract (บทคัดย่อภาษาไทย)
  - English Abstract
  - Acknowledgments (กิตติกรรมประกาศ)
  - Table of Contents, List of Tables, List of Figures
- **Chapter 1: Introduction**
  - 1.1 Background and Problem Significance
  - 1.2 Project Objectives
  - 1.3 Scope of the Project
  - 1.4 Project Methodology Overview
  - 1.5 Expected Academic and Operational Benefits
- **Chapter 2: Theoretical Concepts and Related Technologies**
  - 2.1 Enterprise Infrastructure Management Principles
  - 2.2 Windows Diagnostics & Event Telemetry (WMI, CIM, EVTX architecture)
  - 2.3 Semantic Vector Search and Retrieval-Augmented Generation (FastEmbed, pgvector)
  - 2.4 Modern Web Architecture (FastAPI async lifespan, Next.js React 19 SSR)
  - 2.5 Relational Schema Design and Search Indexing (PostgreSQL pg_trgm, tsvector)
- **Chapter 3: System Design and Implementation Methodology**
  - 3.1 Operational Requirements & Use Case Analysis
  - 3.2 High-Level System Architecture
  - 3.3 Database Schema & Relational Data Model
  - 3.4 Portable USB Evidence Collector (Embedded Python Runtime)
  - 3.5 Offline Telemetry Ingestion Pipeline
  - 3.6 Event Deduplication and Priority Scoring Engine
  - 3.7 Local Vector AI Analysis Pipeline & Provenance Model
  - 3.8 Security Posture Evaluation & Secret Remediation
  - 3.9 Web Investigation Dashboard & Command Center UI
  - 3.10 System Verification and Testing Methodology
- **Chapter 4: Implementation Results and System Validation**
  - 4.1 Asset Registry & Inventory Validation
  - 4.2 Portable Ingestion & Sequential Dedup Performance
  - 4.3 AI Log Analyzer Diagnostics Accuracy & Latency Measurements
  - 4.4 Universal Search Index Efficiency & Response Times
  - 4.5 Automated Test Suite Verification (Unit, Integration, Lifespan)
- **Chapter 5: Conclusion, Limitations, and Future Recommendations**
  - 5.1 Project Conclusion & Objectives Fulfillment
  - 5.2 Technical & Operational Limitations
  - 5.3 Recommendations for Future Enterprise Enhancement
- **Back Matter**
  - References (IEEE format)
  - Appendix A: Database Schema Specifications
  - Appendix B: Operational Event Knowledge Catalog
  - Author Biography

---

## 🎤 Final Presentation & Defense Strategy

The graduation defense will follow a structured 11-step narrative flow focused on defensible engineering rather than commercial feature lists:

1. **Company & Industrial Context:** Operating environment, scale of infrastructure, and constraints (air-gapped systems, security boundaries).
2. **Routine Operational Duties:** Practical workplace responsibilities informing system requirements.
3. **Problem Statement:** The friction of manual Windows server diagnostics, air-gapped data collection, and operational alert fatigue.
4. **Project Objectives:** Engineering goals established in COOP.105.
5. **Architectural Concepts:** Technology choices (portable collector, FastAPI, pgvector, Next.js).
6. **System Implementation:** Core engineering components and integration patterns.
7. **Hero Workflow Demonstration:** Live or recorded walk-through:
   *Authorized Host → Portable USB Auditor → Offline JSON Evidence → Central Ingestion → Asset Registration → Windows Event Evidence → Deduplication → AI Analyzer → Provenance History → Filtered Findings UI*.
8. **Measured Validation:** Quantitative test suite results, search latencies (<300ms), and ingestion accuracy.
9. **Known Limitations:** Honest discussion of application-level dedup limits, air-gap transfer friction, and benchmark data loss history.
10. **Summary:** Key engineering achievements against initial objectives.
11. **Future Work:** Phased roadmap for post-graduation enterprise scaling.

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

### Sprint 10: Global Search & Timeline ✅ COMPLETED
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
- **Benchmark Safety Fixed**: `tools/sprint11_benchmark.py` now requires `EIMS_BENCHMARK_DATABASE_URL` and blocks databases ending in `registry` by default (with an explicit dangerous override for exceptional operator-controlled use). Safety guard tested by `tests/test_benchmark_safety.py` (8/8 PASS).
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
  - `Total Logs Analyzed`: Derived strictly from the `analysis_history` table. Graduation baseline: 9 `analysis_history` records total (8 real surviving historical records + 1 synthetic AI demo incident). Runtime history may grow as additional analyses are performed
  - `Critical Errors`: Derived strictly from actual analyzed records. Graduation baseline critical count: 1 (`AINC-2026-0910-0001` flagged with `isCritical: true`). Runtime critical count may grow with subsequent analyses
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

---

## 🔭 Future / Post-Graduation Roadmap

> **Status Legend**:
> - ✅ **Completed**: Implemented, verified in test suites, and delivered in release `v0.3.0`.
> - ⏳ **Deferred**: Conceptually scoped in initial Master Plan (formerly referenced as Sprint 7+), intentionally deferred past graduation hardening.
> - 💡 **Future / Unimplemented**: Planned enterprise capabilities for post-graduation product lifecycle stages; not implemented in the current repository.

### ⏳ Milestone 1: High Availability & Enterprise Scale Production Clustering (Deferred)
*Note: Originally forecasted in early planning as "Sprint 7+", production clustering was deferred to focus on core platform verifiability, data recovery, search, and graduation hardening. These items are NOT currently implemented.*

- **Database High Availability**:
  - PostgreSQL Read-Replica cluster configuration with streaming replication.
  - PgBouncer automatic read/write routing and connection failover.
- **Distributed Caching & Brokering**:
  - Redis Sentinel / Redis Cluster high-availability broker configuration.
  - Broker partition tolerance and automated split-brain recovery testing.
- **Container Orchestration**:
  - Multi-node Kubernetes (K8s) deployment manifests and production Helm charts.
  - Pod horizontal autoscaling (HPA) for telemetry ingestion workers.
- **Disaster Recovery**:
  - Automated point-in-time recovery (PITR) pipelines and off-site backup replication.

### 💡 Milestone 2: Enterprise Commercialization & Advanced Integrations (Future)
- **Cross-Endpoint Correlation**:
  - Multi-host incident timeline reconstruction and distributed attack chain tracking.
  - Graph-based dependency visualization and anomaly correlation across network tiers.
- **Enterprise Single Sign-On (SSO)**:
  - SAML 2.0 and OpenID Connect (OIDC) integration for Active Directory / Okta.
  - Granular Role-Based Access Control (RBAC) policy administration UI.
- **Large-Scale Fleet Management**:
  - Distributed Discovery Agent deployment management across 10,000+ endpoints.
  - Agent auto-update, configuration sync, and certificate rotation automation.
- **SIEM & Security Ecosystem Integration**:
  - External Syslog/CEF forwarder and bidirectional enterprise SIEM synchronization.
  - Automated exportable audit reports for ISO 27001, PCI-DSS, and HIPAA frameworks.
- **Automated Regulatory Compliance Engines**:
  - CIS Benchmark Level 1 & 2 automated rule evaluations.
