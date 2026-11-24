# Module Functional Acceptance — Local vs Cloud Demo (2026-11-19)

Evidence rule: a screenshot proves the UI exists; it does not prove persistence or
backend behaviour. Each row states exactly which levels were actually verified.

Verified from this repository in this session:
- `start_eims.bat` topology (see `docs/deployment/LOCAL_APPLICATION_ARCHITECTURE.md`).
- `backend/api/routers/agents.py` (Launch Agent runs `clients/usb_auditor/run.bat`).
- `backend/domain/asset_registry/controller.py` `POST /assets/import-report`.
- `backend/domain/analyzer/services/import_pipeline.py` (offline USB report ingest).
- No backend QR endpoint; QR is client-side (`qrcode.react` in the dashboard).
- Dashboard pages: agents, analyzer, knowledge, observability, evaluations,
  timeline, ocr-history, endpoints, settings, evaluate.
- Test runs: 46 passed (EVTX/auth/controllers/search), 37 passed (sprint13
  ingestion), 6 passed (models/state machine), 22 passed (mutation safety),
  34 passed +1 skip (analyzer evaluation; teardown raised a Windows temp-dir
  PermissionError after completion).

## Matrix

| Module | Local implementation | Local API/DB | Local browser | Real-input evidence | Local verdict | Cloud demo |
|---|---|---|---|---|---|---|
| Home Portal | Next.js page (`/`) | n/a | **NOT TESTED this session** (Local stack not launched) | — | PARTIAL | show once Node service exists |
| AI Log Analyzer | analyzer pages + routers | PASS (tests) | NOT TESTED this session | synthetic fixtures; real customer EVTX: user-reported only | **PASS WITH LIMITATIONS** | show |
| Engineering Knowledge | knowledge page + routers | routers/DB present; not exercised this session | NOT TESTED | — | PARTIAL | show when data verified |
| Observability & Alerts | observability page | needs Redis/workers | NOT TESTED | — | PARTIAL | show with "unavailable" state |
| Service Evaluations | evaluations page + router | router present; controller tests pass | NOT TESTED | synthetic only | **PARTIAL → likely PASS** (CRUD/QR need one browser run) | show if that run passes |
| Timeline | timeline page + router | router present | NOT TESTED | — | PARTIAL | show |
| Client Agents | agents page + `/agents/launch` | **launch runs a local Windows batch** | NOT TESTED | — | **LOCAL-ONLY by design** | hide (no Windows session on cloud) |
| USB Auditor | endpoint inventory + Launch Agent + import report | import endpoint covered by tests; **no server-side CSV export found** (export appears client-side) | NOT TESTED | agent hardware events **NOT TESTED** | **PASS WITH LIMITATIONS** (offline import + inventory; hardware detection unproven) | show inventory/import; hide Launch Agent |
| Sticker OCR | ocr-history page + routers | routers present | user-confirmed for one customer (not re-run) | customer-specific | **CUSTOMER-SPECIFIC** | **hide** until boundaries verified |
| Grafana / MinIO / Prometheus / API docs | external consoles / docs | n/a | n/a | — | out of scope | **do not expose publicly** |
| Incident Management | Next.js pages + `/api/v1/incidents` | PASS (137 baseline) | **PASS** on the deployed read-only console | synthetic | PASS WITH LIMITATIONS | show |
| Verification Gate | service + DB triggers | PASS (22 + 24 tests) | PASS (persisted history rendered) | synthetic | PASS WITH LIMITATIONS | show (read-only) |

## Answers to the twelve questions

1. **Does USB Auditor launch an agent?** Yes — `POST /agents/launch` starts
   `clients/usb_auditor/run.bat` **on the backend host** (admin/token protected).
2. **Does the agent detect real USB devices?** **Not verified** in this session.
   The agent source exists; no agent run or hardware event was captured here.
3. **Offline report import end-to-end?** API + pipeline are implemented and
   covered by tests (`test_sprint13_evidence_ingestion`, 37 passed).
4. **CSV export correctness?** No server-side CSV export was found; the UI
   export is client-side. **Not verified.**
5. **Service Evaluations CRUD + QR?** CRUD routes/pages exist and controller
   tests pass; QR is generated client-side. **Browser CRUD/QR not executed.**
6. **Does QR lead to a working feedback workflow?** **Not verified.**
7. **Sticker OCR locally?** Reported working for one customer by the user; not
   re-run here. Customer-specific.
8. **Prior real-world EVTX evidence?** Only synthetic fixture tests are present
   in the repository; the real customer test is user-reported and was not
   re-run (per instruction).
9. **Synthetic vs real EVTX?** All repository EVTX tests use synthetic fixtures.
10. **Which workers are required?** Telemetry/EVTX/OCR/incident-ingest workers
    start only outside `EIMS_DEMO_SOFT_DEPS=1`; none are required for the
    read-only demo path.
11. **Which modules should appear in the cloud instructor demo?** Home,
    Analyzer, Knowledge, Evaluations, Timeline, Incidents/Verification,
    Observability (with honest "unavailable"), USB inventory/import
    (without Launch Agent).
12. **Which stay Local-only / customer-specific?** Client Agents (local process
    launch), Sticker OCR (customer-specific), and all admin consoles
    (Grafana/MinIO/Prometheus).

## Cloud parity status

The real portal is a **Next.js Node application**. The current Render service
runs only the Python backend plus the read-only `/demo` page. **Local→Cloud
parity is therefore not achieved yet**; it requires a second Render web service
for `clients/dashboard` with:

- build `npm ci && npm run build`, start `npm start -- -p $PORT`
- `NEXT_PUBLIC_EIMS_API_URL=https://<api-host>`
- `EIMS_BACKEND_URL=https://<api-host>` for the server-side proxy route
- API CORS allowing the portal origin
- the same demo access boundary (no public writes)

Decision: **LOCAL MODULE ACCEPTANCE: PASS WITH LIMITATIONS · CLOUD PARITY: NOT
YET DEPLOYED.**
