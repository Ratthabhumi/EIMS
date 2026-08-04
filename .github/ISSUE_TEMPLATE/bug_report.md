---
name: Bug / Defect Report
description: Submit a reproducible bug report or architectural discrepancy against EIMS specifications
title: "[BUG]: <short descriptive title>"
labels: [bug, triage]
assignees: []
---

### 1. Defect Description
<!-- Provide a clear, active voice description of what is broken or violating our functional requirements. -->

### 2. Implicated Component
<!-- Select the subsystem experiencing the defect -->
- [ ] FastAPI Core Gateway
- [ ] FastAPI Telemetry Collector
- [ ] Next.js Operational Dashboard
- [ ] Discovery Agent Daemon
- [ ] PostgreSQL / PgBouncer Persistence
- [ ] Redis Event Broker Queue
- [ ] MinIO Object Store / OCR Pipeline

### 3. Steps to Reproduce
1. Go to '...'
2. Send API command / payload '...'
3. See error exception or malformed payload '...'

### 4. Expected vs. Actual Behavior
- **Expected Behavior (per Core Laws):** 
- **Actual Runtime Behavior:** 

### 5. Environment & Version Metrics
- EIMS Version / Commit Tag: `v0.x.x`
- Operating System & Kernel: 
- Python / Node runtime versions:

### 6. Logs & RFC 7807 Exception Traces
```json
// Paste JSON Problem Details or server exception logs here
```
