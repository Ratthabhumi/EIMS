# EIMS Cooperative Education Oral Defense: Q&A Guide
# International Program - Faculty of Engineering, KMITL

This document prepares the student for the final oral defense examination before the KMITL academic committee and enterprise supervisors, providing direct, report-grounded answers to expected defense questions.

---

## 1. Architectural & Design Decisions

### Q1: Why develop EIMS instead of deploying an existing commercial SIEM like Splunk or Elastic SIEM?
**Answer:**
EIMS is not intended to replace a SIEM. The project focuses on asset-centered infrastructure evidence and a portable offline workflow for endpoints that may not continuously reach a central service.

While enterprise SIEM platforms focus on real-time streaming security log correlation across fleet-wide networks, EIMS addresses the practical gap of auditing isolated, air-gapped, or maintenance endpoints. It ties physical hardware inventory and operating system event logs to a central asset registry without requiring persistent background daemons.

---

### Q2: Why does EIMS need offline / portable media collection?
**Answer:**
In enterprise infrastructure administration, two fundamental constraints prevent connected collection:
1. **Network Segmentation & Air-Gapping:** High-security segmented or isolated enterprise hosts are physically or logically segregated from corporate networks. They cannot open outbound network connections to a central server.
2. **Non-Destructive Posture:** Production servers cannot tolerate the installation of external software packages, package managers, or third-party background daemons.

The portable auditor runs from the removable USB package using the bundled Python runtime. It performs read-only queries against the target system and writes its report/log output to configured directories on the USB package. The resulting JSON artifact serves as a structured local evidence source prior to central ingestion.

---

### Q3: Why choose PostgreSQL with pgvector instead of a dedicated vector database like Milvus, Pinecone, or Qdrant?
**Answer:**
EIMS adopts a modular monolith architecture. Using an external vector database would introduce distributed state synchronization challenges, additional network latency between relational and vector stores, and dual-database operational overhead.

By integrating `pgvector` inside PostgreSQL 16:
1. **Transactional Integrity:** Asset records, component inventories, Windows Event evidence, and vector embeddings reside within the same relational boundary under unified ACID guarantees.
2. **Simplified Persistence:** Standard SQL queries can filter relational attributes (e.g., `WHERE asset_id = ... AND occurrence_time >= ...`) while simultaneously evaluating vector cosine distance (`ORDER BY embedding <=> query_vector LIMIT 5`) in a single query.
3. **Operational Simplicity:** A single datastore simplifies backup, point-in-time recovery, and deployment across on-premises environments.

---

## 2. Ingestion, Deduplication & Event Processing

### Q4: How does deduplication work in EIMS?
**Answer:**
To prevent duplicate records when engineers collect evidence from the same host multiple times, EIMS computes a deterministic composite SHA-256 fingerprint for every ingested Windows Event:

DedupKey = SHA-256(asset_id | channel | provider | record_id | occurrence_time)

Because the Windows `record_id` is a monotonically increasing integer assigned by the local event log service and the `occurrence_time` is locked to the event's recorded timestamp (`TimeCreated`), this hash is deterministic and collision-resistant across extractions. Upon ingestion, the backend computes this hash and filters out previously persisted events before committing new records to PostgreSQL.

---

### Q5: What happens if two identical reports are imported concurrently? Does EIMS guarantee concurrency-safe deduplication?
**Answer:**
**No.** EIMS implements **sequential application-level deduplication**, not database-level concurrent deduplication. 

In sequential imports, the service queries existing deduplication hashes in PostgreSQL, filters out duplicates in memory, and persists only novel events. However, the current schema does not enforce a composite `UNIQUE` constraint or distributed table lock on the deduplication hash. Therefore, if two identical report packages are submitted simultaneously across concurrent asynchronous HTTP requests, a race condition can occur where both requests check the database before either commits, resulting in duplicate insertions. Acknowledging this distinction demonstrates clear engineering boundaries. Resolving this via database-level unique constraints is part of our future roadmap.

---

### Q6: Why scope event log collection strictly to the System and Application channels, excluding the Security channel?
**Answer:**
The portable graduation workflow intentionally collects the System and Application channels because the project focuses on infrastructure reliability and application diagnostics.

The System channel records hardware health, driver events, and operating system reliability issues, while the Application channel captures software and database exceptions. In addition, the Windows Security channel produces extremely high volumes of routine authentication events that fall outside our infrastructure maintenance scope.

---

## 3. Artificial Intelligence & Triage Pipeline

### Q7: Why cap AI analysis at most 10 events per import?
**Answer:**
Workload bounding is an important design choice for system stability:
1. **Computational Bounding:** Dense embedding generation and language model prompt synthesis incur noticeable latency and memory overhead. Capping the workload limits processing cost during large imports.
2. **Operator Focus:** A systems engineer responding to a server disruption needs a concise list of high-severity events rather than hundreds of routine notifications.
3. **Deterministic Prioritization:** EIMS sorts candidate events strictly by severity: `Critical (Level 1) > Error (Level 2) > Warning (Level 3) > Information (Level 4)`. The analyzer selects at most the top 10 prioritized events, ensuring system resources are focused on critical errors and warnings.

---

### Q8: What is the exact role of AI in EIMS? Is it autonomous?
**Answer:**
AI in EIMS functions strictly as an **assistive investigation aid**, NOT an autonomous authority:
- It does NOT make unassisted diagnostic decisions.
- It does NOT automatically apply patches, reboot servers, or alter registry configurations.
- It uses Retrieval-Augmented Generation (RAG) to match parsed event logs with retrieved solution/reference context, synthesizing concise diagnostic explanations and recommended verification steps for human engineers.
- All AI findings are recorded in the `AnalysisHistory` table with traceable event and asset metadata, preserving human operational oversight.

---

## 4. Verification, Testing & Empirical Evidence

### Q9: How was EIMS validated? What were the principal test results?
**Answer:**
Validation was conducted across five multi-tier engineering layers:
1. **Hermetic Ingestion Test Suite (Sprint 13):** 37 tests in `tests/test_sprint13_evidence_ingestion.py` using mocked/isolated dependencies (**37 passed, 0 failed, 4 warnings**). Live database testing was verified separately.
2. **Frontend Type & Production Quality:** Passed TypeScript strict type compilation (`tsc --noEmit`) and Next.js production build (`npm run build`) with 0 errors.
3. **Physical Hardware Field Validation:** Executed the portable USB package on an authorized Windows Server host across a 24-hour collection window.
4. **Field Dataset Persistence:** Successfully ingested and persisted **49 Windows Event Evidence records** (34 System, 15 Application), generating **10 AnalysisHistory records** for host `ASSET-01`.
5. **REST API & Browser Gate A9:** Verified the filtered history API (`GET /api/v1/history?asset_id=...`) returning **HTTP 200**, and verified live browser rendering under Gate A9.

---

### Q10: What does "A9 PASS" mean?
**Answer:**
Gate A9 verified that the endpoint investigation UI successfully renders persisted evidence and active AI triage in a live browser session:
1. Browser runtime checked: YES
2. Event Evidence table visible: YES (49 events displayed)
3. AI Findings visible: YES
4. Placeholder "No AI findings yet": NOT SHOWN
5. Filtered History API: HTTP 200
6. Overall A9 verdict: PASS

Achieving A9 PASS confirms that persisted database evidence correctly propagates through the API gateway and renders properly on the operator dashboard.

---

### Q11: What is the distinction between historical field validation and latest on-site verification?
**Answer:**
This is an important distinction for accurate technical reporting:
- **Historical Field Validation:** Earlier development sessions validated the physical USB execution on target Windows hosts, non-destructive CIM/event log extraction, offline JSON generation, and sequential import into the backend.
- **Latest On-Site Verification:** The final evaluation session verified downstream data integrity—confirming that the 49 persisted event rows, 10 AnalysisHistory records, asset-filtered REST API, and Next.js dashboard render accurately without re-running the physical USB drive execution.

Making this distinction ensures our evaluation claims are grounded in verifiable evidence.

---

## 5. Limitations & Personal Growth

### Q12: Why is EIMS an "academic prototype baseline" and not "production-ready"?
**Answer:**
EIMS proves the engineering feasibility of unified evidence management and offline AI triage. However, calling it "production-ready" would be inaccurate because:
1. It does not run in a high-availability cluster with automatic failover.
2. It lacks enterprise SAML/OIDC Single Sign-On (SSO) integration with Active Directory.
3. Deduplication is enforced sequentially at the application layer, not concurrently in the database.
4. The offline collector currently supports Windows systems only.
5. It has not undergone formal third-party penetration testing or regulatory forensic certification.

---

### Q13: What did you personally implement, and what were the most significant technical lessons learned?
**Answer:**
**Personal Implementations:**
- Developed the portable USB auditor packaging and batch launcher with embedded CPython 3.14.3.
- Implemented the WMI/CIM hardware discovery and Windows Event Log extraction modules.
- Built the FastAPI ingestion pipeline, Pydantic data contracts, and SHA-256 deduplication logic.
- Configured PostgreSQL 16 with pgvector and implemented semantic cosine similarity search.
- Constructed the Next.js 14 App Router dashboard with evidence inspection views.

**Key Technical Lessons:**
1. **Strict Data Contracts:** Handling real-world Windows event logs requires strict schema validation at the gateway boundary to prevent downstream database corruption.
2. **Framework Runtime Typing:** In FastAPI/Pydantic, a missing type import such as `Optional` in route signatures (commit `acb855f`) causes runtime request dispatch failures, underscoring the necessity of integration tests across all query parameters.
3. **Non-Destructive Engineering Discipline:** Operating in production enterprise environments requires defensive, read-only principles—an auditing tool must never mutate the system it inspects.

---

### Q14: If you had another semester to continue this project, what would you prioritize next?
**Answer:**
Based on the project roadmap:
1. **Database High Availability & Clustering:** Multi-node PostgreSQL clustering and Kubernetes orchestration as outlined in Milestone 1.
2. **Concurrency-Safe Deduplication:** Adding database-level unique constraints and upsert logic to handle simultaneous parallel imports safely.
3. **Cross-Endpoint Event Correlation:** Multi-host incident timeline correlation and service dependency mapping (Milestone 2).
4. **Multi-Platform Extension:** As a possible future extension, exploring portable collection utilities for Linux environments.
