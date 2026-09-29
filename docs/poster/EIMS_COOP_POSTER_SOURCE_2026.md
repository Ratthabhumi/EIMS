# EIMS Cooperative Education Poster Source Specification (2026)
**Academic Year 2026 | International Program, Faculty of Engineering, KMITL**
**Project:** Development of an Enterprise Infrastructure Management System (EIMS)
**Author:** Ratthabhumi Peansukmanee (Student ID: 66011198)
**Host Organization:** KANEMATSU ELECTRONICS (THAILAND)
**Workplace Supervisor:** Mr. Chalermpol Phuangchalam
**Academic Supervisor:** Asst. Prof. Dr. Phongsak Keeratiwintakorn

---

## 1. Specifications & Physical Formatting

- **Standard Paper Size:** ISO 216 A1 (594 mm × 841 mm / 23.386 in × 33.110 in)
- **Orientation:** Portrait (chosen to match KMITL Faculty of Engineering standard vertical display panels and allow clean 1:1 scaling down to standard A4 portrait for supervisor review).
- **Deliverable Formats:**
  - `docs/poster/EIMS_COOP_POSTER_2026.pptx` (Native editable PowerPoint shapes, text boxes, and embedded high-resolution vector diagrams)
  - `docs/poster/EIMS_COOP_POSTER_2026.pdf` (Fixed 1-page A1 vector PDF exported via PowerPoint COM)
  - `docs/poster/EIMS_COOP_POSTER_SOURCE_2026.md` (Reproducible source specification)
- **Primary Typography:** TH Sarabun New / TH SarabunPSK (fallback: Calibri / Arial for universal system rendering)
  - Poster Title: 50 pt, Bold
  - Metadata / Subtitles: 18–20 pt, Bold / Regular
  - Section Headings: 26 pt, Bold
  - Subsection Headings: 18–19 pt, Bold
  - Body Text: 17.5–19 pt, Regular (with Navy bold lead-in titles)
  - Metric Numerals: 30–32 pt, Bold (Emerald / Navy)
  - Metric Labels: 15–16 pt, Bold
  - Metric Descriptions: 12.5–13 pt, Regular
  - Deduplication Equation: 15 pt Consolas, Bold
- **Color Palette (Restrained Academic Engineering Style):**
  - Background Canvas: Clean White (`#FFFFFF`) with subtle slate grid card fills (`#F8FAFC`)
  - Primary Headers & Cards: Deep Navy (`#0F172A`, `#1E293B`)
  - Accent / Highlights: Engineering Blue (`#2563EB`, `#1D4ED8`)
  - Text: Black `#000000` / Charcoal `#0F172A` (high contrast, WCAG AAA compliant)
  - Success Metric Accents: Deep Emerald (`#047857`)
  - Borders: Crisp Light Slate (`#E2E8F0`, `#CBD5E1`)

---

## 2. Complete Visible Poster Content & Layout Structure

### 2.1 Header Banner (Full Width: 594 mm)
- **University & Project Header:**
  *Faculty of Engineering | King Mongkut's Institute of Technology Ladkrabang*
  *Computer Engineering (International Program) | Cooperative Education Project 2026*
- **Main Project Title:**
  **Development of an Enterprise Infrastructure Management System (EIMS)**
- **Author & Institutional Metadata:**
  **Student:** Ratthabhumi Peansukmanee (Student ID: 66011198)
  **Host Enterprise:** KANEMATSU ELECTRONICS (THAILAND)
  **Workplace Supervisor:** Mr. Chalermpol Phuangchalam
  **Academic Supervisor:** Asst. Prof. Dr. Phongsak Keeratiwintakorn

---

### 2.2 Left Column Content (Width: ~265 mm)

#### Section 1: Background & Problem Statement
- **Context:** Managing enterprise infrastructure requires auditing heterogeneous servers across well-connected and isolated networks.
- **Operational Problems:**
  - **Network Isolation:** Air-gapped and high-security endpoints cannot maintain continuous outbound connections to cloud monitoring daemons.
  - **Ephemeral Identity:** Dynamic DHCP IP leases and server renames break historical tracking across server migrations.
  - **Manual Diagnostic Friction:** Field technicians execute disparate ad-hoc scripts, producing fragmented notes without provenance.
  - **Telemetry Overload:** Windows Event Logs generate thousands of routine records daily, creating severe triage fatigue.

#### Section 2: Project Objectives (7 Canonical Objectives)
1. **Central Asset Registry:** Anchor asset records with cryptographic hardware composite fingerprints.
2. **Portable Windows Collector:** Build a lightweight, read-only collection package using embedded CPython 3.14.3.
3. **Offline Ingestion Pipeline:** Ingest and normalize offline multipart JSON evidence into relational schemas.
4. **Sequential Deduplication:** Enforce application-level SHA-256 event fingerprinting and severity ranking.
5. **AI-Assisted Investigation:** Deploy pgvector cosine similarity search to retrieve contextual solution playbooks.
6. **Unified Web Dashboard:** Deliver a responsive Next.js 14 interface for asset details and event evidence.
7. **Empirical System Validation:** Validate data integrity from offline collection to live browser display.

#### Section 3: Multi-Tier System Architecture
- **Visual Diagram:** Embedded high-resolution Figure 3.1 (`docs/report/final/fig3_1_architecture.png`).
- **Caption:** *Figure 1: Hybrid Modular Monolith Architecture of the EIMS Platform.*
- **Key Architectural Highlights:**
  - **Portable Edge:** Standalone USB collection without persistent host agent installation.
  - **Central Core:** Asynchronous FastAPI backend delivering strict Pydantic contract validation.
  - **Unified Datastore:** PostgreSQL 16 combining ACID relational tables with pgvector similarity search.
  - **Decoupled Services:** Redis for queuing/caching, MinIO for S3-compatible object storage, and Next.js 14 App Router for visualization.

#### Section 4: Technology Implementation Stack
- **Backend Service:** FastAPI + Pydantic + Starlette (REST APIs & schema validation)
- **Persistence & Vector:** PostgreSQL 16 + pgvector (384-dimensional cosine distance)
- **Broker & Object Store:** Redis 7 (caching/queuing) & MinIO (S3-compatible storage)
- **Operator Dashboard:** Next.js 14 App Router + React + Tailwind CSS
- **Portable Collector:** Embedded CPython 3.14.3 amd64 distribution (USB-based)
- **AI Retrieval Models:** FastEmbed `BAAI/bge-small-en-v1.5` primary / SentenceTransformer fallback

---

### 2.3 Right Column Content (Width: ~265 mm)

#### Section 5: Portable Offline Collection Workflow
- **Visual Diagram:** Embedded high-resolution Figure 3.3 (`docs/report/final/fig3_3_sequence.png`).
- **Caption:** *Figure 2: Disconnected Evidence Acquisition and Ingestion Sequence.*
- **Operational Guarantees:**
  - **Zero Target Dependencies:** Bundled CPython 3.14.3; no target Python, pip, Git, or Docker required.
  - **Read-Only Interrogation:** Non-destructive WMI/CIM queries and Windows Event Log parsing.
  - **Bounded Collection Scope:** Scoped to System and Application channels over 24 hours (default max 500 events).
  - **Structured Local Output:** Emits schema-validated JSON artifact to USB storage prior to central upload.

#### Section 6: Empirical Validation Results
- **Metric Cards (Prominent Visual Grid):**
  - **37 Passed / 0 Failed / 4 Warnings:** Sprint 13 Hermetic Ingestion Test Suite (`tests/test_sprint13_evidence_ingestion.py`).
  - **49 Persisted Events:** Field evidence records stored in PostgreSQL (34 System channel, 15 Application channel).
  - **10 AnalysisHistory Rows:** Bounded AI triage records for test host `ASSET-01` (analyzer workload cap <= 10).
  - **HTTP 200 OK:** Filtered History REST API (`GET /api/v1/history?asset_id=...`).
  - **A9 Gate PASS:** Live browser runtime verification (simultaneous display of 49 events and active AI findings).
  - **Frontend Build PASS:** Strict TypeScript compilation (`tsc --noEmit`) and Next.js production build (`next build`).
- **Workload Bounding Note:** *Note: AI analysis is bounded to at most 10 selected new events per import.*

#### Section 7: Event Deduplication & Bounded AI Role
- **Deduplication Formulation:**
  $$\text{DedupKey} = \text{SHA-256}(\text{asset\_id} \parallel \text{channel} \parallel \text{provider} \parallel \text{record\_id} \parallel \text{occurrence\_time})$$
  *Sequential application-level deduplication filters duplicates in memory prior to insertion. (Concurrent identical imports may race as database-level uniqueness is not currently enforced).*
- **AI-Assisted Investigation Role:**
  - Prioritizes incoming anomalies by severity (`Critical > Error > Warning > Information`).
  - Retrieves relevant solution context using cosine similarity without autonomous execution.
  - Persists diagnostic summaries in `AnalysisHistory` with traceable event and asset foreign metadata.

#### Section 8: Scoped Limitations & Future Roadmap
- **Design Limitations:**
  - Windows-first collection focus (WMI/winevt); System and Application channels only.
  - Sequential deduplication without database-level concurrency locks.
  - Prototype baseline: lacks multi-region clustering and enterprise Active Directory SSO.
  - Assistive triage: AI recommendations assist human operators and do not act as autonomous authorities.
- **Future Engineering Roadmap:**
  - Milestone 1: Multi-node PostgreSQL clustering and connection pooling.
  - Milestone 2: Concurrency-safe database unique constraints (`ON CONFLICT DO NOTHING`).
  - Milestone 3: Cross-endpoint event timeline correlation and Linux `systemd` collectors.

#### Section 9: Conclusion
- Demonstrated safe, non-destructive evidence gathering for isolated Windows environments.
- Enforced deterministic sequential deduplication and severity-ranked triage pipelines.
- Empirically validated end-to-end data flow from offline collection to interactive web dashboard.

---

## 3. Confidentiality & Non-Claims Audit

- **Anonymized Identifiers:** Test host referred to strictly as `ASSET-01` / `Windows Server A`. Zero customer hostnames, private IP/MAC addresses, credentials, or BitLocker recovery keys.
- **No Field Screenshots:** Uses clean system architecture and sequence diagrams (Figures 3.1 and 3.3). Zero unapproved field screenshot placeholders (Figures 4.1–4.5 omitted).
- **Prohibited Claims Verified Absent:**
  - Zero claims of "production-ready" or "enterprise-grade deployment".
  - Zero claims of "certified digital forensics" or "court-admissible chain of custody".
  - Zero claims of "complete commercial SIEM replacement".
  - Zero claims of "autonomous root-cause authority" or "automated remediation".
  - Zero claims of "concurrent database deduplication safety".
  - Zero false assertions of a latest physical USB re-execution.
