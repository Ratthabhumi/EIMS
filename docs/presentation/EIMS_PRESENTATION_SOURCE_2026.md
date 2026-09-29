# EIMS Final Cooperative Education Presentation — Source Deck & Speaker Notes
**Academic Year 2026 | International Program, Faculty of Engineering, KMITL & Kanematsu Electronics (Thailand)**
**Author:** Ratthabhumi Peansukmanee (Student ID: 66011198)

---

## Slide 1: Title Slide
- **Category:** Final Cooperative Education Presentation
- **Title:** Development of an Enterprise Infrastructure Management System (EIMS)
- **Presenter:** Ratthabhumi Peansukmanee | Student ID: 66011198
- **Affiliation:** Computer Engineering (International Program), Faculty of Engineering, King Mongkut's Institute of Technology Ladkrabang (KMITL)
- **Supervisors:** Workplace Supervisor: Mr. Chalermpol Phuangchalam | Academic Supervisor: Asst. Prof. Dr. Phongsak Keeratiwintakorn
- **Host Organization:** KANEMATSU ELECTRONICS (THAILAND)
- **Speaker Notes:**
  > Good morning respected members of the committee, advisor, and mentors. My name is Ratthabhumi Peansukmanee, student ID 66011198 from the International Computer Engineering Program at KMITL. Today, I am presenting my cooperative education capstone project conducted at Kanematsu Electronics (Thailand), entitled 'Development of an Enterprise Infrastructure Management System (EIMS)'.

---

## Slide 2: Cooperative Education Context & Operational Responsibilities
- **Host Enterprise Context:**
  - Host Organization: KANEMATSU ELECTRONICS (THAILAND)
  - Industry Domain: Enterprise Systems Integration, Compute Infrastructure, and Cloud Managed Services
  - Placement Duration: Full-time 4th-year Cooperative Education (Academic Year 2026)
  - Workplace Division: Enterprise Infrastructure Deployment & Systems Support Engineering
  - Supervision: Under direct technical mentorship of Mr. Chalermpol Phuangchalam
- **Routine Responsibilities vs. EIMS Capstone:**
  - *Routine Enterprise Engineering Duties:*
    1. Bare-metal server staging, OS installation, and hardware component testing.
    2. Network switch configuration, VLAN tagging, and firewall policy routing.
    3. Ad-hoc endpoint troubleshooting and local diagnostic extraction on client servers.
  - *EIMS Capstone Development Scope:*
    1. Engineered central asset records anchored by cryptographic hardware composite fingerprints.
    2. Designed an air-gapped, portable USB evidence collection utility for isolated servers.
    3. Built an automated ingestion, deduplication, and AI-assisted investigation pipeline.
- **Speaker Notes:**
  > During my internship at Kanematsu Electronics, my routine duties involved physical server staging, system hardening, and network troubleshooting. In performing these duties, I observed that troubleshooting isolated client servers required time-consuming manual intervention. This motivated the development of EIMS as a dedicated capstone engineering project to automate evidence gathering and investigation.

---

## Slide 3: Problem Statement: Infrastructure Evidence Fragmentation
- **Core Friction Points:**
  1. **Network Enclave Isolation:** High-security production servers reside in air-gapped or segmented enclaves. Continuous streaming daemons cannot cross firewall boundaries, leaving endpoints invisible to central monitoring.
  2. **Fragile Ephemeral Identity:** Dynamic IPs, DHCP leases, and server renames break historical tracking. Infrastructure lacks immutable hardware-anchored identity across server migrations.
  3. **Labor-Intensive Manual Diagnostics:** Engineers must physically access servers and manually execute disparate PowerShell/CMD scripts, producing fragmented, unstructured notes without verification guarantees.
  4. **High-Volume Telemetry Overload:** Windows endpoints generate thousands of routine event logs daily. Triage is slow, prone to oversight, and lacks deterministic prioritization.
  5. **Absence of Provenance & History:** Ad-hoc investigation findings are rarely linked back to specific events, preventing retrospective auditing and historical incident cross-referencing.
- **Speaker Notes:**
  > In enterprise IT, infrastructure evidence is scattered. Air-gapped systems cannot run continuous agents, dynamic hostnames make servers hard to identify reliably, and log volumes overwhelm staff. EIMS was designed specifically to solve these five core operational friction points.

---

## Slide 4: Project Objectives (Core Engineering Scope)
- **Canonical Objectives (Aligned with Chapter 1):**
  - **OBJ-1: Centralized Asset Registry:** Establish central asset records anchored by cryptographic hardware composite fingerprints.
  - **OBJ-2: Portable Disconnected Collection:** Implement a portable, read-only collection utility for disconnected Windows hosts requiring no persistent agent installation.
  - **OBJ-3: Ingestion & Normalization Pipeline:** Ingest and normalize offline evidence payloads into schema-validated relational records.
  - **OBJ-4: Sequential Deduplication:** Enforce application-level sequential SHA-256 deduplication and deterministic severity ranking upon ingestion.
  - **OBJ-5: Assisted AI Analysis:** Deploy semantic embeddings and retrieval-augmented generation to provide assistive diagnostic context for prioritized events (bounded at most 10 per import).
  - **OBJ-6: Centralized Investigation Dashboard:** Deliver a responsive web interface displaying endpoint profiles, compliance status, event logs, and assisted findings.
  - **OBJ-7: Empirical System Validation:** Validate end-to-end data integrity from evidence ingestion to dashboard display across defined evaluation gates.
- **Speaker Notes:**
  > Here are the seven core objectives defined in Chapter 1. The prototype addresses these seven objectives, though validation depth differs by feature. Notice that we focus on bounded AI assistance, sequential deduplication, and traceable evidence metadata.

---

## Slide 5: EIMS System Overview & Technology Stack
- **Target Endpoints:** Windows endpoints; field validation on an authorized Windows Server host (WMI/CIM queries and Windows Event Log `.evtx` channels).
- **Portable USB Auditor:** Embedded CPython 3.14.3 amd64. Bundled runtime executing `Run-EIMS-Audit.bat`; read-only queries with outputs written to configured USB directories.
- **Core Backend API:** FastAPI + Pydantic + Starlette. Asynchronous Python 3.10+ gateway delivering OpenAPI 3.1 endpoints and strict schema validation.
- **Relational & Vector Store:** PostgreSQL 16 + pgvector. ACID transactional relational entity store combined with 384-dimensional vector cosine distance search.
- **Broker & Caching:** Redis 7 & MinIO Object Storage. In-memory caching and message queuing paired with S3-compatible immutable blob persistence.
- **AI Analysis Engine:** FastEmbed (`BAAI/bge-small-en-v1.5`) primary / SentenceTransformer (`all-MiniLM-L6-v2`) fallback. Bounded assistive analysis generating contextual diagnostic summaries with traceable metadata.
- **Operator Dashboard:** Next.js 14 App Router + Tailwind CSS. Server/Client hybrid rendering dashboard presenting real-time asset telemetry and AI findings.
- **Speaker Notes:**
  > EIMS is built on modern, battle-tested open-source technologies. The collection runtime uses an embedded CPython 3.14.3 distribution on USB. The backend uses FastAPI and PostgreSQL with pgvector, decoupled through Redis and MinIO, and served via a Next.js App Router interface. The embedding service initializes FastEmbed with BAAI/bge-small-en-v1.5, with SentenceTransformer all-MiniLM-L6-v2 as fallback.

---

## Slide 6: Multi-Tier System Architecture (Hybrid Modular Monolith)
- **Visual:** Figure 3.1 Multi-Tier Architecture Diagram.
- **Architectural Highlights:**
  - Hybrid Modular Monolith: Consolidates domain services into a cohesive, maintainable codebase without microservice networking overhead.
  - Episodic Disconnected Collection: USB Auditor bridges network isolation gaps without requiring continuous agent daemons.
  - Bounded Ingestion Pipeline: Strict schema checks and sequential deduplication ensure database integrity.
  - Persistence & Vector Separation: Relational tables store entities; pgvector handles mathematical distance operations.
- **Speaker Notes:**
  > This slide presents Figure 3.1 from our report. EIMS employs a hybrid modular monolith. On the left, endpoints are audited episodically via USB media. The central FastAPI service ingests and deduplicates payloads, storing records in PostgreSQL while pgvector computes vector similarity for the AI analyzer.

---

## Slide 7: Portable Offline Evidence Collection & Ingestion Sequence
- **Visual:** Figure 3.3 Offline Collection Sequence Diagram.
- **Collection Guarantees:**
  - Bundled Runtime: Runs from USB drive with embedded CPython 3.14.3 runtime; no persistent agent installation required.
  - Read-Only Queries: Interrogates WMI/CIM and event logs with non-destructive, read-only queries; writes reports/logs to configured USB directories.
  - Scoped Event Window: Captures System and Application logs spanning the preceding 24 hours (default maximum 500 events across combined query).
  - Structured JSON Artifact: Generates structured, schema-validated JSON on the USB media prior to ingestion.
- **Speaker Notes:**
  > Figure 3.3 illustrates the offline collection lifecycle. An engineer inserts the USB drive, runs the batch launcher, and the embedded CPython runtime captures hardware and event log telemetry into an offline JSON file. The drive is then brought to the central station where the file is submitted to the ingestion API.

---

## Slide 8: Event Ingestion & Application-Level Deduplication
- **Four-Step Ingestion Pipeline:**
  1. *Validation:* Pydantic payload validation rejecting malformed schemas (HTTP 422).
  2. *Asset Lookup:* Resolve asset by cryptographic hardware composite fingerprint.
  3. *SHA-256 Dedup:* Compute deterministic hash per event and filter duplicates.
  4. *Persistence:* Persist novel event records to PostgreSQL relational table.
- **Deduplication Formulation:**
  `DedupKey = SHA-256(asset_id || channel || provider || record_id || occurrence_time)`
  Here, `occurrence_time` represents the event's recorded timestamp (`TimeCreated`). Because `record_id` is monotonically assigned per channel by Windows, this hash provides deterministic deduplication across sequential collections of the same event.
- **Engineering Nuance (Sequential vs. Concurrent):**
  - The service queries existing keys and filters duplicates in memory prior to database insertion.
  - Effectively prevents duplicate records during standard, sequential report imports.
  - *Limitation:* Does NOT provide database-level concurrency guarantees. If two identical reports are submitted simultaneously across concurrent threads, race conditions can occur.
- **Speaker Notes:**
  > Deduplication is vital when engineers re-scan endpoints. We generate a SHA-256 fingerprint from the asset ID, channel, provider, record ID, and recorded timestamp. An important engineering distinction: EIMS implements sequential application-level deduplication. It skips duplicates during sequential re-imports, but does not enforce database-level concurrency constraints.

---

## Slide 9: Bounded AI-assisted Investigation & Traceable Metadata
- **Severity Prioritization & Bounded Workload:**
  - *Ranking:* `Critical (Level 1) > Error (Level 2) > Warning (Level 3) > Information (Level 4)`
  - *Bounding:* Evaluated workflow limits analysis to at most 10 selected new events. High-impact failures are triaged first, bounding processing overhead.
- **Semantic Embeddings & Conditional Analysis:**
  - *Model:* FastEmbed `BAAI/bge-small-en-v1.5` primary (384-d dense vectors) with SentenceTransformer `all-MiniLM-L6-v2` fallback.
  - *Metric:* Cosine Distance via pgvector (`<=>` operator).
  - *Flow:* Checks curated answers first, then retrieval, optional Gemini generation, and fallback.
  - *AnalysisHistory:* Traceable metadata linking diagnostic advice to source event and asset records.
  - *Assistive Role:* Accelerates human triage; does NOT act as autonomous root-cause authority or auto-remediator.
- **Speaker Notes:**
  > Our analysis pipeline is bounded and conditional. Rather than feeding thousands of events to an LLM, the evaluated workflow limits analysis to at most 10 selected new events sorted by severity. The service checks curated solutions first, then uses FastEmbed or SentenceTransformer embeddings to retrieve playbook context, with optional generative expansion. Crucially, the AI provides assistive advice and does not take autonomous remediation actions.

---

## Slide 10: Empirical Validation Strategy & Multi-Tier Gates
- **Five Validation Layers:**
  - Layer 1: Unit & Ingestion Tests — Sprint 13 test suite (`tests/test_sprint13_evidence_ingestion.py`): 37 reported passing hermetic tests with mocked database and analyzer; separate historical/live PostgreSQL checks.
  - Layer 2: Frontend Compilation — Strict TypeScript verification (`tsc --noEmit`) and Next.js production build (`next build`) verifying zero type mismatches.
  - Layer 3: Physical USB Execution — Executed portable package on an authorized Windows Server host verifying read-only WMI/CIM and event log extraction.
  - Layer 4: Filtered API Verification — Queried backend endpoints (`GET /api/v1/history?asset_id=...`) verifying HTTP 200 and asset-scoped response payloads.
  - Layer 5: Browser Runtime (A9 Gate) — End-to-end browser inspection validating concurrent rendering of 49 event evidence records and 10 AI findings.
- **Speaker Notes:**
  > We validated EIMS across distinct layers. Layer 1 executes 37 hermetic unit and ingestion tests with mocked database and analyzer components. Layer 2 verifies frontend TypeScript builds. Layer 3 reflects physical USB execution on an authorized Windows Server host. Layer 4 verifies asset-scoped REST API responses, and Layer 5 conducts browser runtime verification under Gate A9.

---

## Slide 11: Empirical Results & Reported Field Metrics
- **Top Metrics:**
  - `37 / 0 / 4`: Sprint 13 Ingestion Test Suite (37 Passed, 0 Failed, 4 Warnings)
  - `PASS`: Frontend TypeScript & Next.js Production Build
  - `49 Events`: Persisted Evidence (34 System + 15 Application over 24h window)
  - `10 Records`: AnalysisHistory Bounded Workload Path (10/10 Analyzed)
- **Field Telemetry Breakdown:**
  - Evaluated Host: Anonymized host alias `ASSET-01` representing enterprise Windows Server environment.
  - Channel Distribution: 34 System channel events + 15 Application channel events.
  - Temporal Window: Preceding 24 hours of operational activity extracted from `%SystemRoot%\System32\Winevt\Logs\`.
  - Filtered API: `GET /api/v1/history?asset_id=...` returned HTTP 200 with exactly the 10 asset-linked triage records.
  - Browser Gate A9: PASS — Verified simultaneous visibility of Event Evidence table and AI Findings inspection card. Placeholder "No AI findings yet" correctly not rendered.
- **Speaker Notes:**
  > Here are our reported results from Chapter 4. Sprint 13 passed with 37 tests. The field dataset contained 49 persisted Windows events across the System and Application channels. The analyzer triaged 10 prioritized events, matching our bounded workload cap. The filtered history API returned HTTP 200, and Gate A9 browser verification confirmed proper UI display.

---

## Slide 12: Downstream Live Validation Workflow Trace
- **Validation Pipeline:** `ASSET-01` -> `49 Events in DB` -> `Bounded Analyzer (Cap <= 10)` -> `10 AnalysisHistory Records` -> `HTTP 200 Filtered API` -> `A9 PASS UI Verification`
- **Critical Distinction:**
  - *Downstream Verification Scope:* The latest on-site verification confirmed downstream data integrity: persisted database rows, AnalysisHistory referential linkage, asset-scoped API filtering, and live Next.js UI rendering.
  - *Historical Collection Separation:* Physical USB acquisition, elevated script execution, and raw JSON extraction were proven in earlier field trials and were intentionally NOT re-run during the final downstream gate.
  - *Traceability & Auditability:* By maintaining this clear boundary, the report avoids false claims of full re-execution while demonstrating that persisted evidence correctly propagates to operator interfaces.
- **Speaker Notes:**
  > Earlier field sessions covered USB collection and JSON generation. In the latest session, I checked the stored events, analysis history, filtered API response, and dashboard. I did not repeat USB collection in that session.

---

## Slide 13: Engineering Challenges & Problem-Solving Lessons
- **Four Documented Engineering Incidents:**
  1. **Sidebar Hydration Mismatch:**
     - *Problem:* Next.js SSR generated HTML differing from client browser window dimensions, triggering hydration warnings.
     - *Solution:* Refactored navigation to two-pass mounting using `useEffect` and CSS container queries.
     - *Lesson:* Strict separation of server-rendered layouts from dynamic client-state DOM components.
  2. **Filtered History API HTTP 500:**
     - *Problem:* Querying `/api/v1/history?asset_id=...` failed with HTTP 500 due to a missing `Optional` type import in the route handler.
     - *Solution:* Added `from typing import Optional` to the route declaration (commit `acb855f`).
     - *Lesson:* Static type annotations and import hygiene must be verified through automated linting and contract checks.
  3. **Developer Environment Dataset Variance:**
     - *Problem:* Local developer database was empty and did not contain the field dataset, initially appearing as an application defect.
     - *Solution:* Verified environment state and populated local test records to mirror the field dataset structure.
     - *Lesson:* Check environment configuration and test data availability before treating empty query results as code bugs.
  4. **Benchmark Database Isolation:**
     - *Problem:* Destructive load benchmarking against a shared local development database resulted in accidental test data loss.
     - *Solution:* Enforced dedicated test databases and isolated runner environments for benchmarking scripts.
     - *Lesson:* Benchmark and evaluation scripts must operate on isolated test instances to prevent accidental data loss.
- **Speaker Notes:**
  > Engineering involves addressing practical obstacles. We encountered and resolved four key issues: Next.js hydration mismatches, an HTTP 500 error caused by a missing Optional import in the history route, distinguishing clean development databases from code defects, and isolating benchmark environments to prevent test data loss.

---

## Slide 14: Scoped Limitations & Future Engineering Roadmap
- **Acknowledged Scoped Limitations:**
  - Windows-First Focus: Portable collection utility currently targets Windows WMI/winevt subsystems; Linux/macOS collectors deferred.
  - System & Application Scope: Scoped strictly to System and Application channels (default max 500 combined events).
  - Sequential Dedup Only: Enforces application-level sequential protection; does not provide distributed database concurrency guarantees.
  - Bounded Triage Capacity: Evaluated workflow limits analysis to at most 10 prioritized events per batch import.
  - Assistive Role: AI suggests diagnoses; does not act as autonomous authority or apply automated patches.
  - Academic Prototype: Prototype implementation; not a commercial SIEM or certified forensic suite.
- **Future Engineering Roadmap (ROADMAP-aligned):**
  - Cross-Endpoint Correlation: Investigate temporal clustering to detect infrastructure-wide event sequences.
  - Database-Level Concurrency: Evaluate database-level constraints for concurrent ingestion safety.
  - Infrastructure Scaling: Connection pooling and containerized deployment as operational needs expand.
  - Directory Integration: Investigate enterprise single sign-on (SSO) integration with corporate Active Directory.
  - Cross-Platform Collection: Study portable collector implementations for Linux systemd and macOS logging.
- **Speaker Notes:**
  > Every engineering project must have well-defined boundaries. EIMS focuses on Windows System and Application logs, uses sequential deduplication, and bounds AI triage to 10 events. It is an academic prototype baseline, not a full commercial SIEM. Our future roadmap outlines clear extensions: cross-endpoint correlation, concurrent database dedup, and multi-platform Linux/macOS support.

---

## Slide 15: Conclusion & Q&A
- **Summary of Project Achievements:**
  1. Centralized Infrastructure Governance: Unified asset tracking with immutable hardware composite fingerprints.
  2. Air-Gapped Evidence Acquisition: Demonstrated non-destructive offline collection using embedded CPython 3.14.3 runtimes.
  3. Deterministic Deduplication & Prioritization: Implemented sequential SHA-256 event fingerprinting and deterministic triage.
  4. Bounded AI Assistance: Delivered RAG-assisted investigation linked to auditable AnalysisHistory records.
  5. Validated Downstream Pipeline: Confirmed end-to-end data integrity across 49 field events, HTTP 200 API, and Gate A9.
- **Closing Statement:** "Thank you. I welcome your questions."
- **Speaker Notes:**
  > In conclusion, EIMS demonstrates an integrated approach to centralized asset governance, portable offline evidence collection, and bounded AI-assisted investigation. The prototype addresses the seven project objectives within its defined scope. I would like to thank Kanematsu Electronics, my workplace supervisor Mr. Chalermpol, my academic advisor Asst. Prof. Dr. Phongsak, and the committee. Thank you. I welcome your questions.
