# EIMS Cooperative Education Poster Source Specification (2026)
**Academic Year 2026 | International Program, Faculty of Engineering, KMITL**
**Project:** Development of an Enterprise Infrastructure Management System (EIMS)
**Author:** Ratthabhumi Peansukmanee (Student ID: 66011198)
**Host Organization:** KANEMATSU ELECTRONICS (THAILAND)
**Workplace Supervisor:** Mr. Chalermpol Phuangchalam
**Academic Supervisor / Project Advisor:** Asst. Prof. Dr. Phongsak Keeratiwintakorn

---

## 1. Specifications & Physical Formatting

- **Standard Paper Size:** ISO 216 A1 (594 mm × 841 mm / 23.386 in × 33.110 in)
- **Orientation:** Portrait (3-column academic layout aligned with official KMITL cooperative education poster guidelines).
- **Proportional Scaling & A4 Supervisor Review Proof:**
  - A1 and A4 use the same ISO A-series aspect ratio ($1:\sqrt{2}$), so the poster can be proportionally reduced to A4 without letterboxing.
  - Actual linear scale: A1 → A4 ≈ 35.36% linear scale ($1 / (\sqrt{2})^3 \approx 0.35355$, exact dimensional ratio $210 / 594$). This reduction spans three ISO A-series steps (A1 → A2 → A3 → A4) and is strictly proportional, not 1:1 scaling.
  - Point Size Equivalence Formula: `A4 equivalent point size = A1 point size × 0.3536`
  - Representative Point Size Scale:
    - Poster Title: 40 pt on A1 → approximately 14.1 pt on A4
    - Card Section Headings: 21 pt on A1 → approximately 7.4 pt on A4
    - Metric Numerals: 21 pt on A1 → approximately 7.4 pt on A4
    - Header Subtitles: 16–18 pt on A1 → approximately 5.7–6.4 pt on A4
    - Body Text & Objectives: 16.5–17 pt on A1 → approximately 5.8–6.0 pt on A4
    - Results Notes & Dedup Points: 15–16 pt on A1 → approximately 5.3–5.7 pt on A4
    - Limitations & Future Work: 14.5–15.5 pt on A1 → approximately 5.1–5.5 pt on A4
    - Deduplication Equation: 14 pt Consolas on A1 → approximately 5.0 pt on A4
    - Conclusion: 13.5–15 pt on A1 → approximately 4.8–5.3 pt on A4
    - Acknowledgment & Signature: 12.5–13 pt on A1 → approximately 4.4–4.6 pt on A4
  - Physical Readability Requirement: While digital inspection validates layout geometry, vector diagram fidelity, and font glyph rendering, physical readability on A4 paper must remain a HUMAN verification performed by the supervisor prior to final A1 print sign-off.
- **Deliverable Formats:**
  - `docs/poster/EIMS_COOP_POSTER_2026.pptx` (Native editable PowerPoint shapes, text boxes, and embedded high-resolution diagrams; 1 slide)
  - `docs/poster/EIMS_COOP_POSTER_2026.pdf` (Fixed 1-page A1 vector PDF exported via PowerPoint COM: 594 mm × 841 mm)
  - `docs/poster/EIMS_COOP_POSTER_2026.png` (High-resolution 2376 × 3364 raster preview)
  - `docs/poster/EIMS_COOP_POSTER_A4_REVIEW_2026.pdf` (Dedicated 1-page A4 physical review proof: 210 mm × 297 mm, 35.36% proportional scale)
  - `docs/poster/EIMS_COOP_POSTER_SOURCE_2026.md` (Reproducible source specification)
- **Primary Typography:**
  - Official Poster Guidance: TH SarabunPSK or Angsana New
  - Active Selected Font: Angsana New (applied consistently across all headers, cards, and metadata)
  - Font Selection Rationale: System audit verified that `Angsana New` is installed on the host system (`angsana.ttc` in Windows Fonts registry). `TH SarabunPSK` is not installed. `TH Sarabun New` is not treated as explicitly approved because official guidance specifies `TH SarabunPSK` or `Angsana New`.
  - Poster Title: 40 pt, Bold
  - Header Metadata / Subtitles: 16–18 pt, Bold / Regular
  - Card Section Headings: 21 pt, Bold (Navy `#0F172A` banner, height: 15 mm)
  - Body Text: 16.5–17 pt, Regular (with Navy bold lead-in titles)
  - Metric Numerals: 21 pt, Bold (Emerald `#047857` / Navy `#0F172A`)
  - Metric Labels: 11.5 pt, Bold
  - Deduplication Equation: 14 pt Consolas, Bold (`#1E40AF`)
  - Acknowledgment & Signature: 12.5–13 pt
- **Institutional Seal Metadata:**
  - Source: Extracted directly from official KMITL supplied document (`แปล_คู่มือใหม่ (2025).pdf`, page 23 appointment order seal).
  - Seal Asset Dimensions: 344 × 344 px.
  - Container Dimensions: 34 mm × 34 mm (1.339 in × 1.339 in).
  - Effective DPI at 34 mm: 256.9 DPI ($\ge 200\text{ DPI}$ proof-acceptable range, $< 300\text{ DPI}$ production print threshold).
  - Status: Embedded for A4 supervisor review proof; official high-resolution vector/raster seal from faculty required for final A1 printing.
- **Color Palette (High-contrast print-oriented palette):**
  - Background Canvas: Clean White (`#FFFFFF`) with subtle slate grid card fills (`#F8FAFC`)
  - Primary Headers & Card Banners: Deep Navy (`#0F172A`)
  - Accent / Highlights: Engineering Blue (`#1E40AF`, `#2563EB`)
  - Text: Black `#000000` / Charcoal `#0F172A`
  - Success Metric Accents: Deep Emerald (`#047857`)
  - Borders: Crisp Light Slate (`#CBD5E1`, `#E2E8F0`)

---

## 2. Poster Layout Structure (Three-Column Academic Format)

### 2.1 Header Banner (Full Width: 562 mm × 82 mm, y: 10 mm)
- **Official KMITL Seal Container:** Dedicated 34 mm × 34 mm white rounded card on the left containing the extracted official KMITL seal (256.9 DPI proof asset).
- **Institutional Subtitle:**
  `FACULTY OF ENGINEERING • KING MONGKUT'S INSTITUTE OF TECHNOLOGY LADKRABANG`
  `COMPUTER ENGINEERING (INTERNATIONAL PROGRAM) • COOPERATIVE EDUCATION 2026`
- **Main Project Title:**
  `Development of an Enterprise Infrastructure Management System (EIMS)`
- **Student & Advisor Metadata:**
  `Student: Ratthabhumi Peansukmanee (Student ID: 66011198) | Project Advisor: Asst. Prof. Dr. Phongsak Keeratiwintakorn`
- **Host Enterprise Metadata:**
  `Host Enterprise: KANEMATSU ELECTRONICS (THAILAND) | Workplace Supervisor: Mr. Chalermpol Phuangchalam`

---

### 2.2 Left Column Content (x: 16 mm, Width: 178 mm)

#### Section 1: Abstract (y: 98 mm, h: 144 mm)
Enterprise infrastructure auditing across isolated corporate networks is hindered by air-gapped endpoints and fragmented diagnostic records. When failures occur on hosts lacking persistent agents, administrators face manual triage without verifiable traceability. The Enterprise Infrastructure Management System (EIMS) addresses this challenge through an integrated evidence management and AI-assisted investigation platform. EIMS combines a central PostgreSQL asset registry with a portable USB collector powered by embedded CPython 3.14.3, extracting non-destructive WMI telemetry and Windows Event Logs (System and Application channels, default maximum 500 events) into schema-validated JSON reports. Upon ingestion, sequential SHA-256 deduplication and bounded semantic retrieval triage prioritized events (cap <= 10). Empirical validation confirmed end-to-end data flow across 49 persisted field events, 10 AnalysisHistory records, HTTP 200 API responses, and browser runtime verification (A9 PASS).

#### Section 2: Background & Problem Statement (y: 248 mm, h: 220 mm)
- **Disconnected & Enclave Isolation:** High-security enterprise servers prohibit continuous outbound monitoring connections to central services.
- **Fragile Ephemeral Tracking:** Dynamic DHCP IP churn and host renames disrupt historical telemetry without hardware-anchored identity.
- **Manual Diagnostic Friction:** Ad-hoc scripts produce fragmented diagnostic notes without verifiable provenance across server fleets.
- **Telemetry Volume Overload:** Windows Event Logs generate thousands of routine records daily, obscuring actionable infrastructure faults.

#### Section 3: Project Engineering Objectives (y: 474 mm, h: 354 mm)
- **OBJ-1 Central Asset Registry:** Anchor canonical asset records with cryptographic hardware composite fingerprints across lifecycle changes.
- **OBJ-2 Portable USB Auditor:** Lightweight, non-destructive collection utility executing on embedded CPython 3.14.3.
- **OBJ-3 Offline Ingestion Pipeline:** Schema-validated normalization of offline multipart JSON evidence reports into relational schemas.
- **OBJ-4 Deterministic Deduplication:** Application-level sequential SHA-256 deduplication and severity queue ordering.
- **OBJ-5 Bounded AI Investigation:** pgvector cosine similarity retrieval for prioritized events (bounded workload cap <= 10).
- **OBJ-6 Unified Web Dashboard:** Responsive Next.js 14 App Router UI for asset telemetry, evidence inspection, and AI findings.
- **OBJ-7 Empirical Validation:** End-to-end multi-tier verification from portable USB extraction to live browser display.

---

### 2.3 Center Column Content (x: 208 mm, Width: 178 mm)

#### Section 4: Multi-Tier System Architecture (y: 98 mm, h: 280 mm)
- **Primary Technical Diagram:** Embedded high-resolution Figure 3.1 (`docs/report/final/fig3_1_architecture.png`).
- **Architectural Highlights:**
  - **Hybrid Modular Monolith:** Consolidates collection, ingestion, dedup, and AI triage in a single maintainable service without microservice networking overhead.
  - **Persistence & Vector Separation:** PostgreSQL 16 handles ACID relational entities while pgvector computes 384-dimensional cosine distance in unified SQL queries.
  - **Decoupled Supporting Tier:** Redis manages message caching/queues, MinIO provides S3-compatible storage, and Next.js 14 delivers hybrid server/client rendering.

#### Section 5: Technology Implementation Stack (y: 384 mm, h: 210 mm)
- **Backend API Gateway:** FastAPI + Pydantic + Starlette delivering REST APIs and schema validation.
- **Database & Vector Store:** PostgreSQL 16 with pgvector (384-d dense vector cosine distance search).
- **Broker & Object Store:** Redis 7 (caching/queues) and MinIO (S3-compatible storage for OCR/specs).
- **Operator Web Dashboard:** Next.js 14 App Router, React 18, TypeScript, and Tailwind CSS.
- **Portable USB Auditor:** Embedded CPython 3.14.3 amd64 distribution (no target dependencies).
- **AI Embedding Hierarchy:** FastEmbed BAAI/bge-small-en-v1.5 primary / SentenceTransformer fallback.

#### Section 6: Event Deduplication & Bounded AI Role (y: 600 mm, h: 228 mm)
- **Deduplication Formulation:**
  `DedupKey = SHA-256(asset_id || channel || provider || record_id || occurrence_time)`
- **Operational Points:**
  - **Sequential In-Memory Dedup:** Windows record_id is monotonically assigned; SHA-256 hash enables deterministic duplicate skipping across sequential imports.
  - **Concurrency Boundary:** Enforced sequentially in memory. Concurrent identical imports may race as database-level uniqueness is not currently enforced.
  - **Severity Priority Ranking:** Candidate events prioritized: Critical (Level 1) > Error (Level 2) > Warning (Level 3) > Info (Level 4).
  - **Bounded Workload Cap:** Analyzer strictly triages at most 10 selected new events per import, protecting worker threads from load spikes.
  - **Assistive Role Boundary:** AI provides diagnostic hypotheses and suggested verification checks; does NOT execute autonomous remediation or guaranteed RCA.

---

### 2.4 Right Column Content (x: 400 mm, Width: 178 mm)

#### Section 7: Portable Offline Workflow (y: 98 mm, h: 240 mm)
- **Sequence Diagram:** Embedded high-resolution Figure 3.3 (`docs/report/final/fig3_3_sequence.png`).
- **Operational Guarantees:**
  - **Bundled Portable Runtime:** Embedded CPython 3.14.3 amd64; requires NO preinstalled Python, pip, Git, or Docker on target hosts.
  - **Non-Destructive Posture:** Read-only WMI/CIM and event queries; writes reports/logs strictly to configured USB directories.
  - **Scoped Telemetry Window:** Captures System and Application logs over 24h (default maximum 500 events across combined query).
  - **Deterministic JSON Output:** Produces structured, schema-compliant JSON payloads for central offline import.

#### Section 8: Empirical Validation Results & Measured Metrics (y: 344 mm, h: 260 mm)
- **Metric Cards (3 Rows × 2 Columns Grid):**
  - **37 / 0 / 4:** Sprint 13 Hermetic Ingestion Test Suite (37 passed, 0 failed, 4 warnings).
  - **49 Events:** Persisted Field Telemetry (34 System + 15 Application events).
  - **10 Records:** AnalysisHistory Records (10 AnalysisHistory records associated with the selected field dataset; analyzer cap <= 10).
  - **HTTP 200:** Filtered History REST API (`GET /api/v1/history?asset_id=...`).
  - **Gate A9 PASS:** Browser Runtime Verification Gate (Event Evidence & AI Findings verified in UI).
  - **0 Errors:** Frontend Quality Gates (strict `tsc` & Next.js production build PASS).
- **Precision Validation Notes:**
  - **Workload Bounding Distinction:** The 49 events represent persisted evidence in the database. 10 AnalysisHistory records were created associated with the selected field dataset, matching the analyzer's strict cap of at most 10 selected new events per import.
  - **Validation Scope Boundary:** Earlier field trials verified physical USB execution and JSON extraction. The latest on-site session verified downstream data integrity (persisted DB rows, filtered API, and UI) without re-running physical USB collection.
  - **A9 Runtime Verification:** The field dataset contained 49 persisted Windows Event Evidence rows. The A9 browser check confirmed that Event Evidence and AI Findings were both available in the endpoint investigation view.

#### Section 9: Scoped Limitations & Future Work (y: 610 mm, h: 115 mm)
- **Scoped Limitations:**
  - Windows-first collection focus (WMI/winevt); System and Application channels only.
  - Sequential deduplication in memory; concurrent identical imports may race.
  - Prototype baseline; does not include multi-region HA or enterprise SSO.
- **Future Engineering Work:**
  - Database-level concurrency-safe deduplication (PostgreSQL composite UNIQUE constraints).
  - Cross-endpoint event correlation (multi-host temporal incident clustering).
  - Production reliability and identity integration (clustering, SAML 2.0 / OIDC SSO).

#### Section 10: Conclusion & Advisor Approval (y: 731 mm, h: 97 mm)
- **Conclusion:**
  - EIMS centralizes asset inventory and operational evidence through hardware fingerprints.
  - Portable collection safely acquires air-gapped evidence via embedded CPython 3.14.3.
  - Combined validation evidence covered portable acquisition/import behavior and the downstream database, API, analysis-history, and UI path.
- **Acknowledgment:**
  *Sincere gratitude to KANEMATSU ELECTRONICS (THAILAND) for host enterprise support, Workplace Supervisor Mr. Chalermpol Phuangchalam for professional guidance, and Academic Supervisor Asst. Prof. Dr. Phongsak Keeratiwintakorn for academic mentorship.*
- **Advisor Signature Block (Blank for physical signing):**
  ```
  ___________________________________________________
  Asst. Prof. Dr. Phongsak Keeratiwintakorn (Project Advisor)
  Date: ________ / ________ / 2026
  ```

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
