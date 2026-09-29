# EIMS Oral Defense Quick-Reference Cue Card (2026)
**Student:** Ratthabhumi Peansukmanee (66011198) | **Host:** Kanematsu Electronics (Thailand)
**Advisors:** Asst. Prof. Dr. Phongsak Keeratiwintakorn & Mr. Chalermpol Phuangchalam

---

### 1. Opening Statement (30 Seconds)
"Good morning committee members. My name is Ratthabhumi Peansukmanee from Computer Engineering International Program at KMITL.
During my co-op at Kanematsu Electronics Thailand working on server staging and troubleshooting, I observed evidence fragmentation on isolated systems.
I developed EIMS to provide portable collection, sequential deduplication, and bounded AI triage for enterprise Windows infrastructure."

---

### 2. 15-Slide Presentation Cue Sheet

- **Slide 1 (Title):** Introduce self, ID 66011198, KMITL International Program, Kanematsu Electronics, and supervisors.
- **Slide 2 (Context & Routine):** Staging physical servers, OS setup, network configuration vs. independent EIMS capstone development.
- **Slide 3 (Problem Statement):** 5 frictions: network isolation, ephemeral hostnames, manual notes, event overload, missing audit provenance.
- **Slide 4 (Objectives):** 7 canonical objectives matching Chapter 1: registry, USB auditor, ingestion, dedup, AI triage, UI, validation.
- **Slide 5 (Tech Stack):** CPython 3.14.3 on USB; FastAPI backend; PostgreSQL 16 + pgvector; Redis + MinIO; Next.js 14 App Router.
- **Slide 6 (Architecture Fig 3.1):** 9-step flow: Endpoint -> USB -> Local JSON -> API -> DB -> Dedup -> AI triage -> AnalysisHistory -> Dashboard.
- **Slide 7 (USB Collection Fig 3.3):** Embedded CPython 3.14.3; read-only WMI/CIM; System + Application (24h, max 500 events); local JSON output.
- **Slide 8 (Ingestion & Dedup):** `DedupKey = SHA-256(asset_id || channel || provider || record_id || occurrence_time)`. Sequential YES, concurrent NO.
- **Slide 9 (AI Pipeline):** Prioritize Critical > Error > Warning > Info. Analyze top 10 new events. FastEmbed + pgvector cosine similarity.
- **Slide 10 (Validation Strategy):** 5 layers: 37 Sprint 13 hermetic tests, TypeScript/Next.js build, physical USB run, DB persistence, Gate A9 UI.
- **Slide 11 (Empirical Results):** 37/0/4 test suite; 49 DB events (34 Sys, 15 App); 10 AnalysisHistory; HTTP 200; Gate A9 PASS.
- **Slide 12 (Downstream Trace):** Emphasize distinction: latest session verified downstream DB/API/UI; historical trials proved USB collection.
- **Slide 13 (Engineering Lessons):** 4 incidents: Next.js hydration fix, missing `Optional` import HTTP 500, dev DB dataset, benchmark isolation.
- **Slide 14 (Limitations & Roadmap):** Windows-first, System/Application, sequential dedup, max 10 triage. Roadmap: DB unique constraints, HA, Linux.
- **Slide 15 (Conclusion):** Recap achievements; emphasize verifiable prototype baseline; close with "Thank you. I welcome your questions."

---

### 3. Key Empirical Numbers (Memorize Exactly)
- **Hermetic Ingestion Suite:** 37 passed / 0 failed / 4 deprecation warnings (`tests/test_sprint13_evidence_ingestion.py`).
- **Persisted Field Evidence:** 49 Windows Event Evidence records (34 System channel, 15 Application channel) over 24 hours.
- **AI Triage Bounded Count:** Exactly 10 AnalysisHistory records generated for test host `ASSET-01` (workload cap <= 10).
- **Filtered History Endpoint:** HTTP 200 response with asset-scoped records (`GET /api/v1/history?asset_id=...`).
- **Browser Gate A9:** PASS — Verified simultaneous visibility of Event Evidence table (49 rows) and AI findings card; placeholder absent.
- **Collection Bounds:** Default maximum 500 events across combined System/Application query; default 24-hour time window.
- **Collector Runtime:** Standalone CPython 3.14.3 amd64 embedded distribution executing `Run-EIMS-Audit.bat`.

---

### 4. Critical Scope Boundaries (Do Not Overclaim)
- **49 vs. 10:** 49 events are persisted database rows. The AI analyzer bounded cap is 10. Do NOT claim all 49 were analyzed.
- **Sequential vs. Concurrent:** Deduplication is sequential application-level. Do NOT claim database-level concurrency safety.
- **Historical vs. Latest:** Physical USB execution was proven in earlier trials. Latest session verified downstream DB/API/UI only.
- **Assistive vs. Autonomous:** AI generates diagnostic context and verification steps. It never executes automated remediation.
- **Prototype vs. Enterprise:** Single-instance container prototype. No production HA clustering, no SAML SSO, not certified forensics.

---

### 5. Personal Contribution (5 Quick Bullets)
1. **Collector:** Packaged standalone embedded CPython 3.14.3, batch launcher, and read-only WMI/Event Log extraction modules.
2. **Backend:** Engineered FastAPI REST endpoints, Pydantic contracts, SQLAlchemy relational models, and Alembic migrations.
3. **Pipeline:** Designed application-level sequential SHA-256 deduplication and severity-ranked triage queue.
4. **AI & Vector:** Integrated FastEmbed dense embeddings and pgvector cosine similarity search in PostgreSQL 16.
5. **Dashboard & QA:** Built Next.js 14 App Router interface, executed Sprint 13 test suite, and verified Gate A9 browser runtime.

---

### 6. Five Hardest Defense Questions — Instant Answers
- **Q5 (Concurrent Dedup):** "No, EIMS implements sequential deduplication. Concurrent parallel uploads could race. DB constraints are Roadmap Milestone 2."
- **Q7 (Why Cap 10 Events?):** "Workload bounding prevents worker saturation and token latency. All events are saved in DB; only top 10 are sent to AI."
- **Q11 (Historical vs. Latest):** "Historical sessions validated USB collection on servers. Latest on-site session validated downstream DB, API, and UI rendering."
- **Q12 (Why Academic Prototype?):** "It proves technical feasibility, but lacks production HA clustering, Active Directory SSO, and forensic certification."
- **EX-01 (Why SHA-256 in Python?):** "During early prototyping, DB unique constraints broke bulk batch imports. Python in-memory filtering allowed graceful rejection."

---

### 7. Difficult Question Recovery Phrases
- **Untested Metric:** "I did not measure that specific metric during our evaluation sessions, so I would not want to speculate without empirical data."
- **Out of Scope:** "That capability is an important consideration for production, but it was outside the scope of our four-month graduation prototype."
- **Code Check Needed:** "I would need to check the specific module implementation in the codebase before giving a definitive answer on that edge case."
- **Valid Critique:** "That is a very fair critique. Enforcing that at the database layer would eliminate the potential race condition I described."

---

### 8. Final Closing Statement (15 Seconds)
"In conclusion, EIMS demonstrates that infrastructure evidence from isolated Windows systems can be gathered, deduplicated, and triaged effectively using bounded AI assistance.
I would like to thank Kanematsu Electronics Thailand, my workplace supervisor Mr. Chalermpol, my advisor Asst. Prof. Dr. Phongsak, and the committee.
Thank you. I welcome your questions."
