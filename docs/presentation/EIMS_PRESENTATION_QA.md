# EIMS Cooperative Education Oral Defense: Comprehensive Q&A Guide
# International Program — Faculty of Engineering, KMITL

This document prepares the student for the final oral defense examination before the KMITL academic committee and enterprise supervisors, providing technically rigorous, report-grounded answers to expected defense questions.

---

## 1. Architectural & Strategic Decisions

### Q1: Why develop EIMS instead of deploying an existing commercial SIEM like Splunk or Elastic SIEM?
**Answer:**
Traditional SIEM platforms (such as Splunk or Elastic) are designed for fleet-scale, continuous streaming log forwarding across highly connected enterprise networks. They impose heavy computational footprints, require persistent agent daemons running with administrative privileges, and rely on continuous network reachability back to central ingestion clusters.

In enterprise field environments (such as those encountered during the internship at Kanematsu Electronics), critical production servers often reside in air-gapped enclaves, isolated DMZs, or disconnected maintenance networks where streaming daemons cannot function. Furthermore, commercial SIEMs focus primarily on security threat correlation rather than integrating physical hardware lifecycle governance, component inventory tracking, and offline evidence triage. EIMS occupies this specific operational niche: it is a lightweight, hybrid evidence management platform that supports both connected assets and air-gapped endpoints through episodic, non-destructive portable collection, without the massive infrastructure overhead of a full SIEM.

---

### Q2: Why does EIMS need offline / portable media collection?
**Answer:**
In enterprise infrastructure administration, two fundamental constraints prevent connected collection:
1. **Network Segmentation & Air-Gapping:** High-security financial, industrial, or database hosts are physically or logically segregated from corporate networks to prevent unauthorized lateral movement. They cannot open outbound HTTP/WebSocket sockets to a central server.
2. **Operational Non-Destructiveness:** Production hosts cannot tolerate the installation of intrusive third-party software, package managers, or language runtimes.

EIMS addresses this by packaging an embedded CPython 3.14.3 amd64 runtime onto a read-only USB media. The utility executes purely in memory from the removable drive, runs non-destructive read-only WMI and Event Log queries, writes a schema-validated offline JSON artifact directly back to the USB drive, and exits cleanly. The physical JSON artifact serves as an authoritative, defensible source of truth prior to central ingestion.

---

### Q3: Why choose PostgreSQL with pgvector instead of a dedicated vector database like Milvus, Pinecone, or Qdrant?
**Answer:**
EIMS adopts a **Hybrid Modular Monolith** architecture. Using a dedicated external vector database would introduce distributed state synchronization challenges, network latency between relational and vector stores, and dual-database operational overhead for deployment and backup.

By integrating `pgvector` inside PostgreSQL 16:
1. **Transactional Integrity:** Asset records, component inventories, Windows Event evidence, and vector embeddings reside within the same relational boundary under unified ACID guarantees.
2. **Simplified Persistence:** Standard SQL queries can filter relational attributes (e.g., `WHERE asset_id = ... AND occurrence_time >= ...`) while simultaneously evaluating vector cosine distance (`ORDER BY embedding <=> query_vector LIMIT 5`) in a single query.
3. **Operational Simplicity:** A single datastore simplifies backup, point-in-time recovery (WAL), and deployment across on-premise environments.

---

## 2. Ingestion, Deduplication & Event Processing

### Q4: How does deduplication work in EIMS?
**Answer:**
To prevent duplicate records when engineers collect evidence from the same host multiple times, EIMS computes a deterministic composite SHA-256 fingerprint for every ingested Windows Event:

$$\text{DedupKey} = \text{SHA-256}(\text{asset\_id} \parallel \text{channel} \parallel \text{provider} \parallel \text{record\_id} \parallel \text{occurrence\_time})$$

Because the Windows `record_id` is a monotonically increasing 64-bit integer assigned by the local event log service and the `occurrence_time` is locked to the kernel's event creation timestamp, this hash is deterministic and collision-resistant across extractions. Upon ingestion, the backend computes this hash and filters out previously persisted events before committing new records to PostgreSQL.

---

### Q5: What happens if two identical reports are imported concurrently? Does EIMS guarantee concurrency-safe deduplication?
**Answer:**
**No.** EIMS implements **sequential application-level deduplication**, not database-level concurrent deduplication. 

In sequential imports, the service queries existing deduplication hashes in PostgreSQL, filters out duplicates in memory, and persists only novel events. However, the current PostgreSQL schema does not enforce a composite `UNIQUE` constraint or distributed table lock on the deduplication hash. Therefore, if two identical report packages are submitted simultaneously across concurrent asynchronous HTTP requests, a race condition can occur where both requests check the database before either commits, resulting in duplicate insertions. Acknowledging this distinction demonstrates academic honesty and engineering rigor. Resolving this via composite database constraints is formally deferred to future work.

---

### Q6: Why scope event log collection strictly to the System and Application channels, excluding the Security channel?
**Answer:**
This scoping decision was established for three concrete engineering reasons:
1. **Domain Relevance:** EIMS is an infrastructure management and hardware reliability system, not a digital forensics or user surveillance platform. The `System` channel records hardware failures, disk controller degradation, driver crashes, and service halts; the `Application` channel records database crashes and software dependency exceptions.
2. **Telemetry Volume:** The Windows `Security` channel generates enormous volumes of routine logon/logoff events, audit successes, and Kerberos ticket requests (often thousands per minute), which would rapidly overwhelm offline USB storage and processing pipelines without providing infrastructure diagnostic value.
3. **Privilege & Compliance Boundaries:** Reading the `Security` channel requires `SeSecurityPrivilege` (special audit privileges) and triggers strict data privacy compliance regulations regarding employee monitoring, which are inappropriate for a general infrastructure inventory utility.

---

## 3. Artificial Intelligence & Triage Pipeline

### Q7: Why cap AI analysis at at most 10 events per import?
**Answer:**
Workload bounding is a critical design requirement for production stability:
1. **Computational Bounding:** Deep learning inference—generating 384-dimensional dense embeddings and executing language model prompt synthesis—incurs significant latency and memory overhead. Without a cap, importing an endpoint with 500 events would saturate the backend worker thread and cause API backpressure.
2. **Cognitive Load Optimization:** A systems engineer responding to a server disruption does not want to read 500 AI summaries. They need rapid, actionable triage of the most catastrophic failures.
3. **Deterministic Prioritization:** EIMS sorts candidate events strictly by severity: `Critical (Level 1) > Error (Level 2) > Warning (Level 3) > Information (Level 4)`. The analyzer selects at most the top 10 prioritized events, ensuring system resources are dedicated exclusively to high-impact operational disruptions.

---

### Q8: What is the exact role of AI in EIMS? Is it autonomous?
**Answer:**
AI in EIMS functions strictly as an **intelligent assistive investigation aid**, NOT an autonomous authority. 
- It does NOT make unassisted diagnostic decisions.
- It does NOT automatically apply patches, reboot servers, or alter registry configurations.
- It uses Retrieval-Augmented Generation (RAG) to match parsed event logs with verified administrative incident playbooks, synthesizing concise diagnostic explanations and recommended verification steps for human engineers.
- All AI findings are permanently recorded in the `AnalysisHistory` table with full model provenance and timestamps, preserving human operational authority.

---

## 4. Verification, Testing & Empirical Evidence

### Q9: How was EIMS validated? What were the principal test results?
**Answer:**
Validation was conducted across five multi-tier engineering layers:
1. **Automated Ingestion Test Suite (Sprint 13):** Executed 37 automated test cases against real PostgreSQL instances, achieving **37 passed, 0 failed, 4 warnings**.
2. **Frontend Type & Production Quality:** Passed TypeScript strict type compilation (`tsc --noEmit`) and Next.js production build (`next build`) with 0 errors.
3. **Physical Hardware Field Validation:** Executed the portable USB package on real enterprise Windows Server hardware across a 24-hour collection window.
4. **Empirical Dataset Persistence:** Successfully ingested and persisted **49 Windows Event Evidence records** (34 System, 15 Application), generating exactly **10 AnalysisHistory records** for host `ASSET-01`.
5. **REST API & Browser Gate A9:** Verified the filtered history API (`GET /api/v1/history?asset_id=...`) returning **HTTP 200**, and verified live browser rendering under Gate A9.

---

### Q10: What does "A9 PASS" mean?
**Answer:**
"Gate A9" is the formal browser acceptance criterion for the end-to-end integration of EIMS. It evaluates six concrete conditions in a live browser session:
1. HTTP 200 response when loading the endpoint investigation view.
2. Full rendering of the asset header and cryptographic hardware profile.
3. Successful rendering of the Windows Event Evidence table displaying persisted events.
4. Simultaneous rendering of the AI Findings card displaying diagnostic summaries and recommendations.
5. Absence of the fallback placeholder message `"No AI findings yet"`.
6. Zero unhandled client-side JavaScript or React hydration exceptions.

Achieving A9 PASS confirms that persisted database evidence correctly propagates through the API gateway and renders seamlessly on the operator dashboard.

---

### Q11: What is the distinction between historical field validation and latest on-site verification?
**Answer:**
This is an essential distinction for technical defensibility:
- **Historical Field Validation:** Earlier development sessions validated the physical USB execution on target Windows hosts, non-destructive WMI/winevt extraction, offline JSON generation, and sequential import into the backend.
- **Latest On-Site Verification:** The final evaluation session verified downstream data integrity—confirming that the 49 persisted event rows, 10 AnalysisHistory records, asset-filtered REST API, and Next.js dashboard render accurately without re-running the physical USB drive execution.

Making this distinction proves that our evaluation claims are grounded in verifiable telemetry rather than overstated assertions.

---

## 5. Limitations & Personal Growth

### Q12: Why is EIMS an "academic prototype baseline" and not "production-ready"?
**Answer:**
EIMS proves the engineering feasibility of unified evidence management and offline AI triage. However, calling it "production-ready" would be inaccurate because:
1. It does not run in a high-availability Kubernetes cluster with automatic failover.
2. It lacks enterprise SAML/OIDC Single Sign-On (SSO) integration with Active Directory.
3. Deduplication is enforced sequentially at the application layer, not concurrently in the database.
4. The offline collector currently supports Windows systems only (Linux systemd and macOS collectors are deferred).
5. It has not undergone formal third-party penetration testing or regulatory forensic certification.

---

### Q13: What did you personally implement, and what were the most significant technical lessons learned?
**Answer:**
**Personal Implementations:**
- Developed the portable USB auditor packaging and elevated batch launcher with embedded CPython 3.14.3.
- Implemented the WMI/CIM hardware discovery and Windows Event Log extraction modules.
- Built the FastAPI ingestion pipeline, Pydantic data contracts, and SHA-256 deduplication logic.
- Configured PostgreSQL 16 with pgvector and implemented semantic cosine similarity search.
- Constructed the Next.js 14 App Router dashboard with real-time evidence inspection views.

**Key Technical Lessons:**
1. **Strict Data Contracts:** Handling messy real-world Windows event logs requires strict schema validation at the gateway boundary to prevent downstream database corruption.
2. **Asynchronous Database Nuances:** Working with async SQLAlchemy and asyncpg taught me that eager-loading relationships is essential to avoid event loop thread blocking.
3. **Non-Destructive Engineering Discipline:** Operating in production enterprise environments requires defensive, read-only principles—an auditing tool must never mutate the system it inspects.

---

### Q14: If you had another semester to continue this project, what would you prioritize next?
**Answer:**
Based on the roadmap codified in Chapter 5:
1. **Cross-Endpoint Event Correlation:** Implement temporal graph algorithms to detect when an event on one server correlates with a failure on another.
2. **Concurrent Database Deduplication:** Add composite unique constraints and database-level upsert logic (`ON CONFLICT DO NOTHING`) to guarantee race-condition safety.
3. **Linux / macOS Portable Collectors:** Create standalone binaries using PyInstaller or Go to collect systemd journals and macOS Unified Logs for heterogeneous datacenter environments.
4. **Enterprise Identity Federation:** Integrate OAuth2 / OpenID Connect with Active Directory for enterprise-grade Role-Based Access Control (RBAC).
