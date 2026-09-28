# EIMS Graduation Evidence Pack 2026
*Cooperative Education Final Validation, Evidence Capture, and Defense Preparation*

**Target Execution Window:** 2026-10-01 → 2026-10-04  
**Project Baseline:** Canonical Frozen Release `v0.3.0` (`bb9210f06256c3adc0c7901352d08e1a026a8027`)  
**Current Operational Baseline:** Post-Release Field Hardening on `main`  
**Authoritative Roadmap Reference:** [ROADMAP.md](../ROADMAP.md)  
**Security / Public Repository Classification:** Strictly Anonymized / Redacted Academic Artifacts Only  

---

## 1. Purpose and Evidence Philosophy

This document serves as the operational execution checklist, validation protocol, and formal evidence register for the Enterprise Infrastructure Management System (EIMS). It defines the structured procedures required to capture defensible engineering evidence from authorized workplace endpoints to substantiate the KMITL Cooperative Education Final Report (specifically Chapter 4: Results and Validation), the oral defense presentation, and the academic poster.

### Core Principles
- **Reproducible:** Every captured artifact must be tied to a documented execution script, specific commit hash, and defined environment configuration.
- **Traceable:** Evidence must show complete end-to-end data provenance (from target host execution to JSON artifact, database record, and UI representation).
- **Anonymized:** 100% of artifacts designated for academic or public visibility must have enterprise and customer identifiers redacted.
- **Measurable:** Numerical metrics (event counts, response latencies, deduplication counts) must be recorded dynamically during live execution rather than assumed from static catalogs.
- **Honest About Limitations:** Unmitigated edge cases, architectural boundaries (such as application-level vs. database-level deduplication), and historical incidents must be documented transparently.
- **Non-Marketing:** This is an engineering verification instrument, not a commercial feature brochure.

---

## 2. Reusable Evidence Record Template

Every captured piece of evidence across all testing domains must be logged according to the following standardized schema:

```markdown
### [EV-ID] <Descriptive Title>

- **Evidence ID:** EV-XXX-YYYYMMDD-ZZ
- **Workflow Domain:** [Hero E2E | Asset Management | Security & Compliance | Event Evidence | AI Analyzer | Search & Timeline | OCR | Observability]
- **Priority:** [Priority A (Must Have) | Priority B (Should Have) | Priority C (Optional)]
- **Execution Date & Time:** YYYY-MM-DD HH:mm:ss (UTC+7)
- **Operator:** Student Engineer (Workplace Intern)
- **Execution Environment:** [Authorized Workplace Lab | Isolated Test VNet | Local Demo Host]
- **Machine Role:** [Target Monitored Server | Target Workstation | EIMS Server]
- **Operating System:** [Windows Server 2022 / 2019 | Windows 11 Enterprise | Windows 10 Pro]
- **EIMS Git Commit:** <40-char SHA>
- **EIMS Baseline Tag:** v0.3.0 (with post-v0.3.0 main hardening)
- **Input Artifact:** [e.g., Run-EIMS-Audit.bat output JSON report, EVTX file, or API POST payload]
- **Preconditions:**
  1. Backend running and healthy (`GET /api/v1/health` returns 200).
  2. Target endpoint accessible with administrative execution rights.
  3. No duplicate test record pre-existing in clean test tenant.
- **Procedure:**
  1. Step 1...
  2. Step 2...
- **Expected Result:** Clear, quantifiable statement of expected outcome.
- **Actual Result:** Verifiable observed outcome during execution.
- **Measured Values:**
  - Key Metric 1: X
  - Key Metric 2: Y
- **Pass/Fail Verdict:** [PASS | FAIL | BLOCKED]
- **Documented Limitations:** Any unexpected behavior or operational boundaries observed.
- **Confidentiality Review:** [PASSED — All Hostnames, IPs, MACs, Serials, Usernames, and Secrets Redacted | PENDING]
- **Screenshot References:** `docs/assets/screenshots/<filename>.png`
- **API / Log References:** `evidence/api/<filename>.json` or `evidence/logs/<filename>.log`
- **Notes & Reviewer Comments:** Mentor/advisor feedback or observations.
```

---

## 3. Priority Model & Exit Gates

Evidence collection activities are structured into three distinct priority classes:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PRIORITY A — MUST HAVE                          │
│  Hero E2E Pipeline • Asset Management • Security & Compliance Posture  │
│  Windows Event Evidence • AI Analyzer / History • Browser UI Proof     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Unlocks Chapter 4 Completion
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       PRIORITY B — SHOULD HAVE                         │
│  Global Search (Ctrl+K) • Unified Timeline • Sticker OCR Registration  │
│  System Observability (Prometheus/Grafana Metrics)                     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Enhances Technical Depth
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        PRIORITY C — OPTIONAL                           │
│  Visual Polish & Responsive Layouts • Mobile Service Evaluation Form   │
│  Supplementary Dark/Light Mode Screenshots                             │
└────────────────────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **Priority A Exit Gate:** Chapter 4 of the Final Report cannot be considered evidence-ready until **100% of Priority A evidence records** are executed, verified, and anonymized. Priority B and C records enhance technical depth but do not block academic submission.

---

## 4. Priority A: Hero E2E Workflow Evidence Plan

The Hero E2E workflow demonstrates the end-to-end operational lifecycle: from air-gapped field collection on an authorized Windows endpoint to ingestion, deduplication, AI triage, and web visualization.

### Stage 1: Portable USB Auditor Execution
- **What is Proven:** The portable auditor executes successfully on a target Windows machine using its bundled embedded CPython runtime, generating a structured JSON telemetry report without requiring preinstalled Python, pip, Git, Docker, or network connectivity.
- **Preconditions:**
  - Target machine runs Windows 10/11 or Windows Server 2016/2019/2022.
  - USB drive or staging directory contains the verified portable build (`Run-EIMS-Audit.bat`, embedded Python runtime, auditor scripts, `MANIFEST.txt`).
- **Exact Evidence to Capture:**
  - Console output showing execution flow, preflight environment checks, WMI/CIM discovery, and SHA-256 manifest verification.
  - Generated report JSON header showing metadata, schema version, and collection timestamps.
- **Expected Measurable Result:**
  - Execution completes with return code 0.
  - Generates a valid JSON report containing system, hardware, network, security, and event log sections.
  - Default collection window: last 24 hours of System and Application event logs (maximum 500 events per channel).
- **Pass Criteria:** JSON file generated on disk; file size > 10 KB; syntax valid (`jq` or Python JSON parser parses without error).
- **Failure Interpretation:** Batch syntax error, WMI permission denial (non-elevated prompt), or missing embedded DLLs.
- **Confidentiality Risks:** Machine hostname, serial number, internal IP/MAC, active user accounts in raw JSON.
- **Capture Reference:** Screenshot `A1-usb-audit-console.png`, Report Header snippet `EV-HERO-STAGE1-HEADER.json`.

### Stage 2: Offline Evidence Ingestion & Central Persistence
- **What is Proven:** EIMS ingestion API (`POST /api/v1/assets/import-report`) receives the offline JSON report, updates or inserts the asset in `infrastructure_assets`, persists raw telemetry in `offline_report_data`, and parses individual event logs into `windows_event_logs`.
- **Preconditions:**
  - EIMS backend service is running and connected to PostgreSQL.
  - Authentication headers configured according to active `AUTH_MODE`.
- **Exact Evidence to Capture:**
  - HTTP request/response transcript of the import operation.
  - JSON response body containing ingestion status, created `asset_id`, total events parsed, and analyzer trigger status.
- **Expected Measurable Result:**
  - HTTP 200 OK or 201 Created.
  - Response confirms asset creation/update and records total ingested event logs.
- **Pass Criteria:** Valid `asset_id` returned; database confirms row insertion in `infrastructure_assets` and `windows_event_logs`.
- **Failure Interpretation:** Schema validation failure (422), database connection failure (500), or JSON serialization mismatch.
- **Confidentiality Risks:** Raw hardware identifiers in response payload.
- **Capture Reference:** HTTP Transcript `EV-HERO-STAGE2-IMPORT.json`, Screenshot `A7-import-api-response.png`.

### Stage 3: Sequential Deduplication & Event Prioritization
- **What is Proven:**
  1. Sequential re-import of an identical report does not generate duplicate `windows_event_logs` rows (application-level deduplication).
  2. Ingested events are prioritized by severity (Critical > Error > Warning > Information) for subsequent analysis.
- **Preconditions:**
  - Initial import of the report completed successfully (Stage 2).
  - Database row counts recorded.
- **Exact Evidence to Capture:**
  - HTTP response of the second (identical) import execution.
  - Database record count comparison before and after the re-import.
- **Expected Measurable Result:**
  - Re-import response indicates: `new_events_persisted: 0`, `duplicate_events_skipped: > 0`.
  - No new rows added to `windows_event_logs` for this asset.
- **Pass Criteria:** Duplicate count exactly matches total report events; new event count equals 0.
- **Failure Interpretation:** Duplicate rows created in database (indicates broken application hash/timestamp deduplication logic).
- **Documented Limitation:** Deduplication is strictly sequential application-level protection; concurrent simultaneous imports do not have database-level unique constraints.
- **Capture Reference:** Response `EV-HERO-STAGE3-DEDUP.json`, Screenshot `A10-duplicate-reimport-result.png`.

### Stage 4: AI Analyzer Invocation & Triage Capping
- **What is Proven:** EIMS automatically routes prioritized event evidence to the AI Log Analyzer, which performs vector semantic search against the local knowledge base and persists findings, strictly capped at a maximum of 10 events per import run.
- **Preconditions:**
  - Imported report contains at least 1 Warning, Error, or Critical event log.
  - Local `FastEmbed` model and `pgvector` extension initialized.
- **Exact Evidence to Capture:**
  - Backend execution log showing analyzer dispatch, similarity retrieval, and analysis generation.
  - Count of analyzed events in the response body.
- **Expected Measurable Result:**
  - Total events analyzed is greater than 0 and less than or equal to 10 (`1 <= analyzed_count <= 10`).
  - Analysis records contain generated diagnostic summary, confidence score, and mitigation advice.
- **Pass Criteria:** Analyzer completes sub-second per event; capped strictly at 10; findings saved to `analysis_history`.
- **Failure Interpretation:** Analyzer fails with timeout, vector dimension mismatch (must be 384), or uncapped loop.
- **Capture Reference:** Analyzer log excerpt `EV-HERO-STAGE4-ANALYZER.log`.

### Stage 5: AnalysisHistory Provenance & Linkage
- **What is Proven:** Generated analysis records maintain full audit provenance linking the diagnostic outcome back to the originating asset, event source, and collection vector.
- **Preconditions:** Stage 4 completed.
- **Exact Evidence to Capture:**
  - Database query or API response for records in `analysis_history`.
  - Inspection of provenance attributes: `asset_id`, `event_source_id`, and `source_type`.
- **Expected Measurable Result:**
  - `source_type == "USB_OFFLINE_COLLECTION"`
  - `asset_id` matches the imported endpoint's UUID.
  - `event_source_id` references the specific ingested Windows event record.
- **Pass Criteria:** All three provenance fields are populated and non-null.
- **Failure Interpretation:** Analysis records orphaned from asset or lacking source telemetry linkage.
- **Capture Reference:** JSON payload `EV-HERO-STAGE5-PROVENANCE.json`.

### Stage 6: Filtered History API Query
- **What is Proven:** The backend endpoint `GET /api/v1/history/?asset_id=<uuid>` successfully returns historical diagnostic records scoped strictly to the specified asset without triggering HTTP 500 errors.
- **Preconditions:**
  - Stage 5 completed with at least 1 record in `analysis_history`.
  - Fix from commit `acb855f` (import `Optional` in router) deployed.
- **Exact Evidence to Capture:**
  - HTTP GET request to `/api/v1/history/?asset_id=<target_asset_id>`.
  - JSON response listing analysis records.
- **Expected Measurable Result:**
  - HTTP 200 OK.
  - Array length matches the number of analysis records generated for that specific asset.
- **Pass Criteria:** HTTP 200 status code; zero 500 Internal Server Errors; every record in response has matching `asset_id`.
- **Failure Interpretation:** HTTP 500 error (FastAPI query parameter typing defect) or unfiltered cross-asset data leakage.
- **Capture Reference:** HTTP Transcript `EV-HERO-STAGE6-FILTERED-API.json`, Screenshot `A8-filtered-history-api.png`.

### Stage 7: Web Dashboard Endpoint AI Findings View
- **What is Proven:** The web dashboard renders the imported endpoint, its system specifications, and displays the corresponding AI diagnostic findings and recommendations within the Asset Details view.
- **Preconditions:**
  - Next.js dashboard running (`localhost:3000` or production build).
  - Browser navigated to `/endpoints` or asset detail view.
- **Exact Evidence to Capture:**
  - Full browser screenshot showing:
    1. Asset metadata (anonymized hostname, OS, CPU, RAM).
    2. Endpoint AI Findings card showing diagnostic summary, severity badge, and mitigation steps.
- **Expected Measurable Result:**
  - UI renders findings without blank states, hydration errors, or layout overflow.
- **Pass Criteria:** Visual presence of AI findings corresponding to the imported report.
- **Failure Interpretation:** Empty findings container, infinite loading spinner, or React hydration mismatch error in console.
- **Capture Reference:** Screenshot `A9-endpoint-ai-findings.png`.

---

## 5. Hero E2E Fillable Validation Matrix

During execution, record the empirical values in this validation table:

| # | Pipeline Verification Metric | Expected Reference / Rule | Actual Field Value | Gate Status | Evidence Reference |
|---|---|---|---|---|---|
| 1 | Report Event Count | Dependent on host (e.g., ~40–200) | *[To be recorded]* | PENDING | `EV-HERO-LOGS-COUNT` |
| 2 | WindowsEventLog Persisted Rows | Matches report event count | *[To be recorded]* | PENDING | `EV-HERO-DB-WINLOGS` |
| 3 | Initial Import: New Events Persisted | Equal to persisted row count | *[To be recorded]* | PENDING | `EV-HERO-IMPORT-1` |
| 4 | Initial Import: Duplicate Events Skipped | 0 | *[To be recorded]* | PENDING | `EV-HERO-IMPORT-1` |
| 5 | Initial Import: Events Sent to Analyzer | `min(new_events, 10)` | *[To be recorded]* | PENDING | `EV-HERO-ANALYZER-1` |
| 6 | Sequential Re-Import: New Events | 0 | *[To be recorded]* | PENDING | `EV-HERO-IMPORT-2` |
| 7 | Sequential Re-Import: Duplicate Events | Equal to total report event count | *[To be recorded]* | PENDING | `EV-HERO-IMPORT-2` |
| 8 | Sequential Re-Import: Analyzed Events | 0 (no new events to analyze) | *[To be recorded]* | PENDING | `EV-HERO-ANALYZER-2` |
| 9 | AnalysisHistory Rows Persisted | Equal to initial analyzed count | *[To be recorded]* | PENDING | `EV-HERO-HISTORY-ROWS` |
| 10 | Provenance `source_type` | `"USB_OFFLINE_COLLECTION"` | *[To be recorded]* | PENDING | `EV-HERO-PROVENANCE` |
| 11 | Filtered History API HTTP Status | HTTP 200 OK | *[To be recorded]* | PENDING | `EV-HERO-API-STATUS` |
| 12 | Filtered History API Row Count | Matches asset's analysis count | *[To be recorded]* | PENDING | `EV-HERO-API-COUNT` |
| 13 | Endpoint AI Findings Rendered in UI | Rendered with mitigation advice | *[To be recorded]* | PENDING | `EV-HERO-UI-FINDINGS` |
| 14 | Next.js Frontend Production Build | 0 errors (`npm run build`) | *[To be recorded]* | PENDING | `EV-BUILD-FRONTEND` |
| 15 | Backend Automated Test Suite | 76/76 PASS (0 failures) | *[To be recorded]* | PENDING | `EV-TEST-BACKEND` |

---

## 6. Priority A: Asset Management Evidence Plan

### Objectives
Prove that EIMS accurately processes hardware inventory, network configuration, and operating system attributes from imported reports and provides functional administrative visualization.

### Verification Items
- [ ] **Asset Creation & Update:** Ingested report creates a new record or correctly updates existing asset by matching serial number / hardware UUID.
- [ ] **Hardware & Network Field Population:** CPU model, physical RAM, storage volumes, network interfaces, and IP addresses populate without null corruption.
- [ ] **Canonical IP Filtering:** Endpoints with placeholder or invalid addresses (e.g., `0.0.0.0`) are handled gracefully without corrupting display tables.
- [ ] **Asset Detail Modal Navigation:** Clicking an asset card or row opens the 4-column detail modal displaying OS, Network, Storage, and Telemetry tabs.
- [ ] **Offline Report Association:** Detail modal links directly to raw JSON telemetry stored in `offline_report_data`.

### Evidence Artifacts
- **Screenshot A3:** Endpoints table overview showing registered asset with sanitized hostname and hardware tags.
- **Screenshot A4:** Asset detail modal displaying hardware specs, network adapters, and OS build.
- **Data File:** Sanitized excerpt of asset database record (`EV-ASSET-RECORD.json`).

### Anonymization Rules
- Hostname: Replace with `ASSET-SRV-01` or `KEL-PROD-WEB-01`.
- IP Address: Replace with RFC 5737 documentation prefix (`192.0.2.x`).
- MAC Address: Replace with `00:00:5E:00:53:xx`.
- Serial Number: Replace with `SN-REDACTED-XXXX`.

---

## 7. Priority A: Security & Compliance Evidence Plan

### Objectives
Demonstrate that EIMS evaluates endpoint security posture and surfaces compliance indicators (firewall, antivirus, encryption, operating system update status).

### Verification Items
- [ ] **Firewall Status Evaluation:** Correctly reads Domain, Private, and Public firewall profiles (Enabled/Disabled).
- [ ] **Antivirus / Defender Verification:** Reports active real-time protection and antivirus signature recency.
- [ ] **BitLocker Protection State:** Reports volume encryption status (Protection On/Off, Encryption Percentage).
- [ ] **Administrative Policies:** Reports status of User Account Control (UAC), Remote Desktop (RDP), and legacy protocol state (SMBv1 Disabled).
- [ ] **Compliance Score Calculation:** System calculates overall compliance verdict based on evaluated rules.

### Strict Confidentiality & Safety Protocol
> [!CAUTION]
> **Zero Secret Collection Rule:**
> - Under no circumstances will BitLocker `RecoveryPassword`, recovery keys, passwords, or encryption key material be captured, stored, or screenshotted.
> - If an endpoint reports BitLocker as *Unavailable*, *Disabled*, or *Non-Compliant*, this represents valid empirical evidence. Do not alter endpoint security settings to force a passing score.

### Evidence Artifacts
- **Screenshot A5:** Security & Compliance panel showing evaluated rule results, firewall profile state, and overall compliance score.
- **Data File:** Sanitized compliance evaluation payload (`EV-SECURITY-COMPLIANCE.json`).

---

## 8. Priority A: Windows Event Evidence Plan

### Objectives
Demonstrate that structured Windows event logs are extracted from target endpoints, persisted in relational storage, and presented contextually for operational triage.

### Scope & Constraints
- **Supported Channels for Portable Workflow:** `System` and `Application` only. *(Note: Security event channel is excluded from the Sprint 13 portable collection path to avoid privilege escalation and domain policy conflicts).*
- **Extraction Time Window:** Default last 24 hours prior to audit execution.
- **Maximum Threshold:** Default cap of 500 events per channel.

### Verification Items
- [ ] **Log Structure Integrity:** Ingested events contain Provider Name, Event ID, Channel, Level, Timestamp, and parsed XML data.
- [ ] **Asset Association:** Every record in `windows_event_logs` contains a valid foreign key referencing `infrastructure_assets.id`.
- [ ] **Channel Scoping:** Event records are strictly confined to `System` and `Application` channels.
- [ ] **Safe API Query:** Verify retrieval via `/api/v1/telemetry/winlogs?asset_id=<uuid>`.

### Evidence Artifacts
- **Screenshot A6:** Event Evidence table showing filtered Event IDs, severity badges, and timestamp ordering.
- **Data File:** Sanitized excerpt of parsed event records (`EV-WINLOGS-PAYLOAD.json`).

---

## 9. Priority A: AI Log Analyzer & Triage Interpretation

### Objectives
Prove that the AI Log Analyzer provides intelligent triage assistance by matching event patterns against the offline vector knowledge base and generating contextual mitigation guidance.

### Ingestion & Analysis Interpretation Matrix
When executing an import, evaluate the pipeline behavior against this authoritative diagnostic matrix:

| Received Events | New Persisted | Duplicate Skipped | Analyzed Count | Pipeline Interpretation & Next Step |
|---|---|---|---|---|
| `> 0` | `> 0` | `0` | `> 0` (`<= 10`) | **Normal Fresh Ingestion:** Pipeline functioning correctly. New events persisted, high-priority items analyzed and stored in history. |
| `> 0` | `0` | `> 0` | `0` | **Normal Sequential Deduplication:** Report was previously ingested. Duplicate protection active. Zero redundant analyses generated. |
| `> 0` | `> 0` | `>= 0` | `0` | **Anomaly / Triage Threshold:** Events were persisted, but none met priority criteria (e.g., all were Information level) or analyzer failed. Inspect log priority filter. |
| `0` | `0` | `0` | `0` | **Extraction Anomaly:** Target report contained zero events or JSON structure malformed. Check collector execution log. |

> [!NOTE]
> **API Interpretation Standard:** An HTTP 500 or network timeout from the history endpoint must **never** be reported as "No Findings Found." Any API failure must be reported as a defect.

### Evidence Artifacts
- **Screenshot A8:** HTTP response transcript of filtered history endpoint.
- **Screenshot A9:** Dashboard view displaying AI diagnostic card with root cause hypothesis, confidence score, and remediation steps.
- **Data File:** Sanitized `analysis_history` record (`EV-AI-FINDINGS.json`).

---

## 10. Priority B: Global Search & Historical Timeline

### Objectives
Prove that administrators can rapidly discover assets, audit entries, and diagnostics across domains using the `Ctrl+K` universal command palette and unified timeline.

### Verification Items
- [ ] **Command Palette Activation:** `Ctrl+K` (or `Cmd+K`) opens the modal overlay instantly from any view.
- [ ] **Multi-Domain Indexing:** Querying keywords returns results categorized into Navigation, Assets, Events, and Analyses across registered providers.
- [ ] **Contextual Deep Linking:** Selecting a search result navigates directly to the target entity (e.g., `/endpoints?id=<uuid>` or `/analyzer?query=4625`).
- [ ] **Unified Timeline Query:** Accessing `/timeline` executes a performant `UNION ALL` query across audit logs, telemetry events, and Windows event logs with operational filtering.

### Evidence Artifacts
- **Screenshot B1:** `Ctrl+K` Command Center open with categorized search results for a sample query.
- **Screenshot B2:** Unified Timeline page showing filtered multi-domain events with severity indicators.
- **Historical Benchmark Note:** Historical Sprint 11 benchmark latencies (Search p95 = 62 ms, Timeline p95 = 290 ms) represent controlled synthetic benchmarks; field measurements must be recorded dynamically.

---

## 11. Priority B: Supporting Capabilities (OCR & Observability)

### Sticker OCR Registration
- **Documented Baseline:** 8 real surviving sticker JPG objects preserved in MinIO bucket `eims-ocr-manifests`; 8 corresponding database records reconstructed.
- **Verifiable Capability:** Navigating to `/ocr-history` displays the historical registration table (Record ID, Device Serial, Timestamp).
- **Academic Limitation:** Optical character re-extraction requires external Tesseract binaries which may not be present in all runtime environments.
- **Evidence Artifact:** Screenshot `B3-ocr-history.png`.

### System Observability
- **Verifiable Capability:** Backend health endpoint (`/api/v1/health`) confirms database and Redis broker readiness.
- **Evidence Artifact:** Screenshot `B4-observability-health.png` or API JSON transcript.

---

## 12. Automated Test & Build Verification Register

To ensure codebase stability, record the outcome of all automated verification runs:

### Verification Test Log
```markdown
### Automated Quality Assurance Register

1. Backend Automated Test Suite:
   - Command: `pytest tests -v`
   - Scope: Auth modes, global search integration, telemetry ingestion, benchmark safety
   - Target Result: 76 passed, 0 failed, 0 warnings
   - Actual Result: [To be executed during capture]
   - Evidence Ref: `EV-TEST-BACKEND-PYTEST`

2. Frontend TypeScript Typecheck:
   - Command: `npx tsc --noEmit`
   - Scope: Complete Next.js dashboard application
   - Target Result: Clean exit (code 0), 0 type errors
   - Actual Result: [To be executed during capture]
   - Evidence Ref: `EV-BUILD-TYPECHECK`

3. Frontend Production Build:
   - Command: `npm run build`
   - Scope: Static asset optimization and route compilation
   - Target Result: Clean generation of all static and server pages
   - Actual Result: [To be executed during capture]
   - Evidence Ref: `EV-BUILD-PRODUCTION`

4. USB Auditor Package Integrity:
   - Command: `tools/build_usb_package.bat --verify-only`
   - Scope: SHA-256 manifest validation against packaged scripts
   - Target Result: 100% manifest match, 0 missing or tampered files
   - Actual Result: [To be executed during capture]
   - Evidence Ref: `EV-BUILD-USB-MANIFEST`
```

---

## 13. Field Evidence Capture Runbook (2026-10-01 → 2026-10-04)

Follow this precise procedural sequence during the authorized on-site field validation session:

```
[Phase 1: Environment Prep]
  │  1. Check out main at verified commit. Record git SHA and environment specs.
  │  2. Start EIMS backend & PostgreSQL. Verify /api/v1/health returns 200.
  │  3. Start Next.js frontend. Verify dashboard loads at localhost:3000.
  ▼
[Phase 2: Package & Auditor Prep]
  │  4. Verify USB Auditor package build and SHA-256 manifest integrity.
  │  5. Stage package on USB drive or authorized test directory.
  ▼
[Phase 3: Endpoint Audit Execution]
  │  6. Execute Run-EIMS-Audit.bat as Administrator on authorized target host.
  │  7. Observe console execution. Capture console screenshot (Screenshot A1).
  │  8. Confirm report JSON generated in output folder. Capture path (Screenshot A2).
  │  9. Inspect report locally; verify System and Application event counts.
  ▼
[Phase 4: Central Evidence Ingestion]
  │ 10. Execute ingestion via EIMS import API. Capture response (Screenshot A7).
  │ 11. Verify asset created/updated in dashboard (Screenshot A3).
  │ 12. Open asset detail modal; verify hardware/OS specs (Screenshot A4).
  │ 13. Verify Security & Compliance indicators (Screenshot A5).
  │ 14. Verify Windows Event Evidence table (Screenshot A6).
  ▼
[Phase 5: Triage & AI Verification]
  │ 15. Verify analysis triggered (capped at <= 10 events).
  │ 16. Query filtered history API GET /api/v1/history/?asset_id=<uuid> (Screenshot A8).
  │ 17. Verify AI findings rendered in dashboard Asset Detail view (Screenshot A9).
  ▼
[Phase 6: Deduplication Check]
  │ 18. Re-import the exact same JSON report.
  │ 19. Confirm duplicate events skipped and zero new analyses created (Screenshot A10).
  ▼
[Phase 7: Search & Supporting Verification]
  │ 20. Open Ctrl+K; search for imported hostname and an Event ID (Screenshot B1).
  │ 21. Navigate to Timeline; verify ingested event entries appear (Screenshot B2).
  ▼
[Phase 8: Anonymization & Archive]
  │ 22. Apply redaction rules to all captured screenshots and JSON payloads.
  │ 23. Move raw unredacted files to secure private storage outside public Git.
  │ 24. Copy sanitized artifacts into docs/assets/ and update evidence records.
```

### Operational Failure Branches
- **If USB Auditor fails to run:** Verify administrator privileges; check if antivirus blocked batch file; verify embedded Python directory integrity.
- **If Ingestion returns 422 Unprocessable Entity:** Check JSON report schema; ensure report was not truncated during copy.
- **If History API returns 500:** Verify commit `acb855f` is active; check backend logs for query parameter deserialization errors.
- **If Deduplication creates new rows:** Do not proceed with Chapter 4 writing; document as a blocking defect for Phase 10 closeout.

---

## 14. Strict Data Anonymization Protocol

To comply with public repository policies and academic privacy guidelines, all artifacts must undergo the following sanitization before inclusion in reports or commits:

### Redaction Rules
| Information Category | Real-World Example | Mandatory Redacted Replacement |
|---|---|---|
| Enterprise Hostname | `CORP-FILESRV-01.corp.internal` | `ASSET-SRV-01.example.local` |
| Workstation Hostname | `DESKTOP-8K3N2Q1` | `WORKSTATION-01` |
| IP Address (IPv4) | `10.120.45.18` or `172.16.8.5` | `192.0.2.10` (RFC 5737 Test-Net) |
| MAC Address | `B4:2E:99:A1:BC:42` | `00:00:5E:00:53:01` (IANA OUI) |
| Hardware Serial | `5CD0141N35` | `SN-REDACTED-9901` |
| User / Admin Accounts | `ratthabhumi.c`, `Administrator` | `local-admin`, `operator` |
| Security Identifiers (SID) | `S-1-5-21-3623811015-...` | `S-1-5-21-REDACTED` |
| Internal Domains | `enterprise.internal.net` | `eims.internal` or `example.corp` |
| Raw Passwords / Secrets | Any hash, key, or token | `[REDACTED_SECRET]` |
| BitLocker Recovery Keys | `48-digit numerical password` | **NEVER COLLECTED OR STORED** |

---

## 15. Comprehensive Screenshot Register

Every image designated for the Final Report or presentation must be documented in this register:

| ID | Title / Target View | Primary Visual Elements | Required Redactions | Academic & Defensible Purpose |
|---|---|---|---|---|
| **A1** | USB Audit Console | Command prompt showing batch preflight and completed WMI extraction. | Redact computer name and target domain. | Proves standalone execution with zero target dependencies. |
| **A2** | Generated Report File | File Explorer or terminal showing generated `.json` report with file size. | Redact customer share paths. | Proves offline local file generation. |
| **A3** | Endpoints Registry List | EIMS `/endpoints` table showing registered host and status tags. | Redact real hostname, IP, MAC. | Proves successful asset discovery and central cataloging. |
| **A4** | Asset Details Modal | System specs modal (CPU, RAM, Disks, OS Build, Interfaces). | Mask physical serial number and MAC. | Proves deep telemetry parsing from raw JSON structure. |
| **A5** | Security & Compliance | Posture panel showing Firewall, AV, and BitLocker indicators. | Redact sensitive policy names. | Proves automated host compliance evaluation. |
| **A6** | Windows Event Logs | Event table listing System/Application logs with Event IDs. | Mask internal server names in payloads. | Proves structured event ingestion and channel isolation. |
| **A7** | Ingestion API Response | API client (Postman/Curl) or browser console showing HTTP 200 response. | Redact internal server IPs. | Proves correct API contract and response payload structure. |
| **A8** | Filtered History API | HTTP GET response from `/api/v1/history/?asset_id=<uuid>`. | Redact internal database IDs. | Proves resolution of commit `acb855f` (no 500 error). |
| **A9** | Endpoint AI Findings | UI card showing AI analysis, root cause hypothesis, and mitigation. | Sanitize path references in advice. | Demonstrates AI-assisted operator triage assistance. |
| **A10** | Deduplication Result | Import response showing duplicate events skipped and 0 new analyses. | None (standard JSON response). | Proves application-level sequential duplicate protection. |
| **B1** | Universal Command Search | `Ctrl+K` palette showing categorized results across assets and events. | Redact customer-identifiable terms. | Demonstrates cross-domain operational discovery. |
| **B2** | Unified Timeline | `/timeline` view showing chronological events across telemetry and audit. | Redact real user IDs. | Demonstrates unified operational event visibility. |
| **B3** | Sticker OCR History | `/ocr-history` table showing historical device records and timestamps. | Redact physical serial numbers. | Documents supporting hardware registration capability. |
| **B4** | System Observability | Backend health check response or Prometheus dashboard metrics. | Redact private infrastructure IPs. | Confirms platform reliability and broker readiness. |

---

## 16. Final Report Chapter 4 Evidence Mapping

This mapping guides the authoring of Chapter 4 (Results and System Validation) in the final cooperative education report:

| Report Section | Section Title | Primary Evidence Records | Supporting Figures / Tables | Engineering Claim Validated |
|---|---|---|---|---|
| **4.1** | Validation Environment | Environment Specs, Test Topology | Table 4.1: Test Hardware & OS Specifications | Controlled, authorized workplace testing scope. |
| **4.2** | Portable Evidence Collection | EV-HERO-STAGE1 | Figure 4.1 (A1), Figure 4.2 (A2) | Dependency-free offline collection via embedded runtime. |
| **4.3** | Asset Registration & Ingestion | EV-HERO-STAGE2, EV-ASSET-01 | Figure 4.3 (A3), Figure 4.4 (A4), Table 4.2 | Relational asset cataloging and schema normalization. |
| **4.4** | Event Parsing & Deduplication | EV-HERO-STAGE3, EV-WINLOGS-01 | Figure 4.5 (A6), Figure 4.6 (A10), Table 4.3 | System/Application event structuring and sequential dedup. |
| **4.5** | AI-assisted Log Analysis | EV-HERO-STAGE4, EV-HERO-STAGE6 | Figure 4.7 (A8), Figure 4.8 (A9), Table 4.4 | Vector RAG triage with capped analysis and full provenance. |
| **4.6** | Security Posture Evaluation | EV-SECURITY-01 | Figure 4.9 (A5) | Automated rules-based compliance checks. |
| **4.7** | Search & Timeline Visibility | EV-SEARCH-01, EV-TIMELINE-01 | Figure 4.10 (B1), Figure 4.11 (B2) | Sub-second multi-domain discovery and unified timeline. |
| **4.8** | Limitations & Defect Analysis | Defect Register entries | Table 4.5: Observed Limitations & Mitigation | Transparent academic discussion of design boundaries. |

---

## 17. Final Presentation & Poster Mapping

### Presentation Slide Allocation (15–20 Minute Defense)
1. **Slide 1–2: Introduction & Operational Context** (Problem statement in enterprise support).
2. **Slide 3–4: Objectives & Architecture** (COOP.105 alignment, high-level component diagram).
3. **Slide 5: Hero Demonstration Workflow** (Complete end-to-end operational pipeline diagram).
4. **Slide 6: Portable USB Collector** (Screenshots A1, A2; embedded Python runtime highlight).
5. **Slide 7: Ingestion & Asset Registry** (Screenshots A3, A4; relational normalization).
6. **Slide 8: Event Ingestion & Deduplication** (Screenshots A6, A10; sequential deduplication proof).
7. **Slide 9: AI Log Analyzer & Provenance** (Screenshots A8, A9; vector search + mitigation).
8. **Slide 10: Security Posture & Compliance** (Screenshot A5; firewall/BitLocker indicators).
9. **Slide 11: Universal Search & Navigation** (Screenshot B1; `Ctrl+K` command palette).
10. **Slide 12: Empirical Validation Summary** (Table summarizing test pass counts, latencies, dedup accuracy).
11. **Slide 13: Engineering Limitations & Lessons Learned** (Data loss recovery truth, dedup concurrency limit).
12. **Slide 14: Conclusion & Future Roadmap** (Post-graduation milestones: K8s, HA, SSO).

### A1 Academic Poster Layout Structure
- **Header:** Project Title, Student Name, Academic Advisor, Workplace Mentor, KMITL Logo, Company Logo.
- **Column 1 (Left):** Background, Problem Statement, System Architecture Diagram.
- **Column 2 (Center):** Hero Workflow Showcase (Screenshots A1, A3, A9), Core Engineering Features.
- **Column 3 (Right):** Empirical Validation Results Table, Measured Performance, Limitations, Conclusion.

---

## 18. Engineering Defect & Lessons-Learned Register

Documenting real engineering challenges and fixes demonstrates technical competence and intellectual honesty:

### Defect 1: Responsive Layout Hydration Mismatch
- **Issue:** React SSR hydration discrepancy occurring on navigation sidebar in Next.js.
- **Detection Method:** Browser console error (`Hydration failed because the initial UI does not match...`).
- **Root Cause:** Sidebar width was computed directly from `window.innerWidth` during initial component render before hydration completed.
- **Fix (Commit `c16b820`):** Implemented client-side mounted state guard (`useMounted`) and standard CSS media queries for responsive layout.
- **Validation:** Zero console errors upon initial load and responsive resizing.
- **Engineering Lesson:** Server-rendered markup must match initial client render precisely; defer client-only dimensions until after component mounts.

### Defect 2: Filtered History API Deserialization Error
- **Issue:** Querying `/api/v1/history/?asset_id=<uuid>` caused HTTP 500 Internal Server Error.
- **Detection Method:** Automated API smoke testing during endpoint history verification.
- **Root Cause:** FastApi route handler declared `asset_id: UUID = None` without importing typing `Optional`, causing Pydantic parameter validation failure when parsing query strings.
- **Fix (Commit `acb855f`):** Imported `Optional` from `typing` and typed `asset_id: Optional[UUID] = Query(None)`.
- **Validation:** Query returns HTTP 200 OK with filtered records.
- **Engineering Lesson:** Strict static typing in FastAPI requires explicit `Optional` wrapping when parameters allow null values.

### Defect 3: Benchmark Script Truncate Incident
- **Issue:** Automated benchmark script on 2026-09-10 executed `TRUNCATE ... CASCADE` against the development database.
- **Detection Method:** Disappearance of historical test rows across four database tables.
- **Root Cause:** Lack of environment and database name verification before executing destructive reset commands.
- **Fix (Commit `Phase 12.1`):** Added strict safety guards in `tools/sprint11_benchmark.py` requiring explicit `EIMS_BENCHMARK_DATABASE_URL` and blocking execution against databases ending in `registry`.
- **Validation:** Safety guard verified with 8/8 passing automated unit tests (`tests/test_benchmark_safety.py`).
- **Engineering Lesson:** Destructive database scripts must include automated preflight assertions preventing execution in non-benchmark environments.

---

## 19. Evidence Status Dashboard

Use this dashboard to track validation readiness toward the 2026-10-20 workplace closeout:

| Verification Domain | Priority | Current Status | Target Completion | Blocker Status | Notes |
|---|---|---|---|---|---|
| **Hero E2E Pipeline** | **A** | **FIELD VERIFY REQUIRED** | 2026-10-02 | **BLOCKING** | Full sequence to be executed on authorized Windows Server. |
| **Asset Management** | **A** | **VERIFIED / SCREENSHOT REQ** | 2026-10-02 | Non-blocking | Backend verified; capture sanitized UI shots. |
| **Security & Compliance** | **A** | **VERIFIED / SCREENSHOT REQ** | 2026-10-02 | Non-blocking | Backend verified; zero-recovery-key rule enforced. |
| **Windows Event Evidence** | **A** | **VERIFIED / SCREENSHOT REQ** | 2026-10-02 | Non-blocking | System + Application channels verified. |
| **AI Analyzer / History** | **A** | **FIELD VERIFY REQUIRED** | 2026-10-03 | **BLOCKING** | Verify filtered history API & dashboard AI findings card. |
| **Sequential Deduplication** | **A** | **VERIFIED / SCREENSHOT REQ** | 2026-10-03 | Non-blocking | Re-import duplicate suppression to be screenshotted. |
| **Global Search (Ctrl+K)** | **B** | **VERIFIED / SCREENSHOT REQ** | 2026-10-03 | Non-blocking | Search palette functional; capture multi-domain results. |
| **Unified Timeline** | **B** | **VERIFIED / SCREENSHOT REQ** | 2026-10-03 | Non-blocking | Timeline functional; capture event stream view. |
| **Sticker OCR History** | **B** | **OPTIONAL SUPPORTING** | 2026-10-04 | Non-blocking | 8 preserved records visible; supporting workflow. |
| **System Observability** | **B** | **OPTIONAL SUPPORTING** | 2026-10-04 | Non-blocking | Health endpoint verified; secondary evidence. |
| **Report Ch. 4 Mapping** | **A** | **LOCKED & READY** | 2026-09-28 | Non-blocking | Structure aligned with thesis template. |
| **Data Anonymization** | **A** | **ACTIVE PROTOCOL** | Ongoing | **BLOCKING** | All public artifacts must pass redaction review. |

---

## 20. Definition of Evidence-Ready

The EIMS project evidence base will be formally certified as **EVIDENCE-READY** when and only when all of the following conditions are met:

1. [ ] **Hero E2E Pipeline** has completed execution on an authorized Windows endpoint with 100% PASS verdicts logged across Stages 1–7.
2. [ ] **Endpoint AI Findings** are visually verified and screenshotted in the Next.js web dashboard with live server telemetry.
3. [ ] **Sequential Deduplication** has demonstrated suppression of duplicate event rows upon immediate report re-import.
4. [ ] **At least one sanitized screenshot** is captured and archived for each Priority A view (A1 through A10).
5. [ ] **Backend and Frontend Verification** logs confirm 76/76 passing pytest tests and a clean `npm run build` production output.
6. [ ] **Confidentiality Audit** certifies that zero real customer hostnames, IPs, MACs, serials, accounts, or secrets appear in tracked repository files.
7. [ ] **Chapter 4 Section Mapping** is fully populated with actual measured values and screenshot references.

> [!WARNING]
> If any Priority A condition remains unverified, the system status must be reported as **NOT EVIDENCE-READY**, and authoring of Chapter 4 results must remain on hold.

---

## 21. Local Evidence Storage Architecture

For local evidence collection, operators should maintain the following local directory structure:

```text
evidence/                          <-- Local, untracked working directory
  ├── raw/                         <-- Original JSON reports and raw console logs (DO NOT COMMIT)
  ├── sanitized/                   <-- Redacted JSON reports safe for reference
  ├── screenshots/
  │     ├── raw/                   <-- Unredacted screenshots (DO NOT COMMIT)
  │     └── approved/              <-- Fully masked/redacted PNGs (Destination: docs/assets/screenshots/)
  ├── api/                         <-- Captured HTTP request/response payloads
  ├── logs/                        <-- Backend and test execution logs
  └── notes/                       <-- Operator field notes and timing records
```

> [!IMPORTANT]
> **Git Tracking Policy:** Sensitive or unredacted raw field evidence must **never** be committed to the public Git repository. Only finalized, anonymized screenshots copied to `docs/assets/screenshots/` and sanitized demonstration payloads may be tracked.
