**Current source audit: 31 October 2026 — `acf024f6466e8bc84c52b107486d74d4a0aafd6d` (PR #10).** Next.js 16.3.0 / React 19.2.8. Engineering CI: 322 Python tests in Analyzer/secure PostgreSQL suites, not project-wide certification. DEV 12 DRAFT, HELDOUT 5 reserved, claims 60, genuine human reviews 0. Diagnostic accuracy NOT_MEASURED; secure HTTPS browser BLOCKED_NOT_TESTED; current USB/production acceptance NOT_TESTED. No main merge.

**Rendered PPTX/PDF: STALE_PENDING_REBUILD. The source revision below has not been visually accepted as a rebuilt deck.**

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
  - Context: Cooperative education placement at KANEMATSU ELECTRONICS (THAILAND)
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
- **Main Problems:**
  1. **Network Enclave Isolation:** High-security production servers reside in air-gapped or segmented enclaves. Continuous streaming daemons cannot cross firewall boundaries, leaving endpoints invisible to central monitoring.
  2. **Fragile Ephemeral Identity:** Dynamic IPs, DHCP leases, and server renames break historical tracking. Infrastructure lacks immutable hardware-anchored identity across server migrations.
  3. **Labor-Intensive Manual Diagnostics:** Engineers must physically access servers and manually execute disparate PowerShell/CMD scripts, producing fragmented, unstructured notes without verification guarantees.
  4. **High-Volume Telemetry Overload:** Windows endpoints generate thousands of routine event logs daily. Triage is slow, prone to oversight, and lacks deterministic prioritization.
  5. **Absence of Provenance & History:** Ad-hoc investigation findings are rarely linked back to specific events, preventing retrospective auditing and historical incident cross-referencing.
- **Speaker Notes:**
  > In enterprise IT, infrastructure evidence is scattered. Air-gapped systems cannot run continuous agents, dynamic hostnames make servers hard to identify reliably, and log volumes overwhelm staff. EIMS was designed specifically to solve these five main problems.

---

## Slide 4: Current Graduation Objectives
- Evidence-grounded multi-vendor investigation; separate event identity, observed failures, final outcomes and causal uncertainty.
- Preserve source-file/line evidence and user-owned History.
- Evaluate M0/M1/Full reproducibly with authentic reviewed-only judgments.
- Retain portable Windows/asset ingestion as historical supporting work.
- **Speaker Notes:**
  > The current objective is verifiable investigation, not adding more features or claiming a trained model.

---

## Slide 5: EIMS System Overview & Technology Stack
- **Target Endpoints:** Windows endpoints; field validation on an authorized Windows Server host (WMI/CIM queries and Windows Event Log `.evtx` channels).
- **Portable USB Auditor:** Embedded CPython 3.14.3 amd64. Bundled runtime executing `Run-EIMS-Audit.bat`; read-only queries with outputs written to configured USB directories.
- **Core Backend API:** FastAPI + Pydantic + Starlette backend providing REST APIs and schema validation.
- **Relational & Vector Store:** PostgreSQL 16 + pgvector. ACID transactional relational entity store combined with 384-dimensional vector cosine distance search.
- **Broker & Caching:** Redis 7 & MinIO Object Storage. In-memory caching and message queuing paired with S3-compatible object storage.
- **AI Analysis Engine:** FastEmbed (`BAAI/bge-small-en-v1.5`) primary / SentenceTransformer (`all-MiniLM-L6-v2`) fallback. Bounded assistive analysis generating contextual diagnostic summaries with traceable metadata.
- **Operator Dashboard:** Next.js 16.3.0 / React 19.2.8 App Router + Tailwind CSS. Server/Client hybrid rendering dashboard presenting asset details, compliance status, event evidence, and AI findings.
- **Speaker Notes:**
  > Here are the main technologies used in EIMS. The collection runtime uses an embedded CPython 3.14.3 distribution on USB. The backend uses FastAPI and PostgreSQL with pgvector, decoupled through Redis and MinIO, and served via a Next.js App Router interface. The embedding service initializes FastEmbed with BAAI/bge-small-en-v1.5, with SentenceTransformer all-MiniLM-L6-v2 as fallback.

---

## Slide 6: Multi-Tier System Architecture (Hybrid Modular Monolith)
- **Visual:** Figure 3.1 Multi-Tier Architecture Diagram.
- **Architectural Highlights:**
  - Hybrid Modular Monolith: Consolidates domain services into a cohesive, maintainable codebase without microservice networking overhead.
  - Episodic Disconnected Collection: USB Auditor bridges network isolation gaps without requiring continuous agent daemons.
  - Bounded Ingestion Pipeline: Strict schema checks and sequential deduplication help maintain consistent stored data.
  - Persistence & Vector Separation: Relational tables store entities; pgvector handles mathematical distance operations.
- **Speaker Notes:**
  > This slide presents Figure 3.1 from our report. EIMS employs a hybrid modular monolith. On the left, endpoints are audited episodically via USB media. The central FastAPI service ingests and deduplicates payloads, storing records in PostgreSQL while pgvector computes vector similarity for the AI analyzer.

---

## Slide 7: Historical Prototype — Portable Offline Evidence Collection & Ingestion Sequence
- **Visual:** Figure 3.3 Offline Collection Sequence Diagram.
- **Collection Guarantees:**
  - Bundled Runtime: Runs from USB drive with embedded CPython 3.14.3 runtime; no persistent agent installation required.
  - Read-Only Queries: Interrogates WMI/CIM and event logs with non-destructive, read-only queries; writes reports/logs to configured USB directories.
  - Scoped Event Window: Captures System and Application logs spanning the preceding 24 hours (default maximum 500 events across combined query).
  - Structured JSON Artifact: Generates structured, schema-validated JSON on the USB media prior to ingestion.
- **Speaker Notes:**
  > Figure 3.3 illustrates the offline collection lifecycle. An engineer inserts the USB drive, runs the batch launcher, and the embedded CPython runtime captures hardware and event log telemetry into an offline JSON file. The drive is then brought to the central station where the file is submitted to the ingestion API.

---

## Slide 8: Historical Prototype — Event Ingestion & Application-Level Deduplication
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

## Slide 9: Current Investigation Workflow
- Source identification → normalized records → vendor rules/local KB → evidence-linked summary → authenticated History.
- Fortinet config edits are not automatically failures. CTK 2620 is technical failure, not proven physical cause. Windows 1129 is a DC-connectivity symptom.
- No observed failure is not system-health certification; unrelated session success cannot resolve another failure.
- M2/RAG and M3/LLM experiments: NOT_RUN.
- **Speaker Notes:**
  > Distinguish the historical bounded RAG ingestion path from the current deterministic evaluation; citation coordinates alone do not establish semantic support.

---

## Slide 10: Validation Layers and Current Gates
- Engineering: Analyzer hermetic, synthetic PostgreSQL and BFF/frontend checks.
- Scientific: 12 DEV DRAFT; 5 HELDOUT reserved; 0 genuine reviewed cases/claims.
- Operational: secure HTTPS browser BLOCKED_NOT_TESTED; latest USB/production NOT_TESTED.
- **Speaker Notes:**
  > Each layer answers a different question. The current CI does not certify all project modules or a deployed system.

---

## Slide 11: Current Results and Separate Historical Evidence
- Current baseline CI: 282 hermetic + 40 PostgreSQL = 322 PASS; counterexamples 8/8.
- Full DEV: 60 claims; diagnostic accuracy/support precision/unsupported-claim rate NOT_MEASURED.
- Historical September evidence: 49 Windows events (34 System, 15 Application), 10 AnalysisHistory findings, filtered API HTTP 200, A9 display PASS.
- New bounded module audit: see PROJECT_WIDE_READINESS_20261031.md; setup failures must not be reported as passes.
- **Speaker Notes:**
  > Historical A9 does not establish secure browser acceptance for October. Fewer claims do not demonstrate better accuracy.

---

## Slide 12: Reproducible Demo and Honest Fallback
- Authorized live demo: login → Fortinet → CTK → Windows 1129 → informational negative control → unrelated bundle → inspect evidence → reopen History → ownership/logout checks.
- Without approved HTTPS: use frozen offline results and label the boundary explicitly.
- Preserve snapshot/source/prediction hashes; original DRAFT and HELDOUT remain unchanged.
- **Speaker Notes:**
  > Do not simulate a live acceptance result. Historical USB collection and historical downstream verification were different sessions, not a new end-to-end run.

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

## Slide 14: Remaining Acceptance Gates
- Authentic priority-three human review with claim rationale and exact hashes.
- Approved trusted HTTPS runtime and real browser acceptance.
- Academic artifact rebuild and human visual/institutional review.
- Owner-authorized core merge with fresh CI; no automatic infrastructure merge.
- Defer new vendors/models/tenancy/cloud migration.
- **Speaker Notes:**
  > Infrastructure now includes separate PR #11; recovery XFAILs remain outside graduation core certification.

---

## Slide 15: Conclusion and Q&A
- Delivered: evidence-grounded investigation, conservative uncertainty, owner-scoped History and reproducible engineering checks.
- Preserved: historical portable collection and asset evidence.
- Not yet established: diagnostic accuracy, secure live browser acceptance or installed production readiness.
- **Speaker Notes:**
  > Our contribution is traceable engineering with explicit evidence boundaries. The next measurable step is genuine reviewed-only pilot data, not another feature count.

---
