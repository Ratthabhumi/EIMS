# EIMS — Local Functional Acceptance (2026-11-19)

Scope: establish what EIMS actually does locally, with evidence levels, before the
2026-11-24 demo. This document does **not** claim production readiness, and it
does not re-label unit-test success as user-workflow acceptance.

## 0. Timeline note (important)

A public Render/Neon deployment **was already created in the previous step**
(`https://eims-demo-api.onrender.com`, commit `2351fdc`). This acceptance phase
did not deploy anything and did not create new cloud resources; it reuses that
evidence only where it is labelled "deployed".

## 1. Evidence levels used

| Level | Meaning |
|---|---|
| L1 Unit | isolated function/class behaviour |
| L2 Integration | multiple components against a real database/parser |
| L3 API | real HTTP endpoint, authenticated, persisted |
| L4 DB | state read back from PostgreSQL after the operation |
| L5 Browser E2E | a human path driven through a browser |
| L6 Real device / external | hardware or third-party provider actually used |

A module is PASS only when its **critical supported workflow** has at least L3+L4
(or L5 where the workflow is browser-only).

## 2. Functional matrix

| Module | Workflow tested | Highest evidence | Result | Notes |
|---|---|---|---|---|
| Authentication | login / invalid login / unauth API rejection / JWT roles | L3 + L4 | **PASS** | `test_auth_modes.py`, `test_api_identity_pg.py`; deployed E2E: unauth `GET /incidents` → 401, login both demo accounts → ok. Browser session persistence **NOT TESTED**. |
| Authorization | engineer vs reviewer capability on resolve/close | L3 + L4 | **PASS** | reviewer-only resolve enforced; engineer attempt → 403 (deployed E2E and PG tests). |
| Asset Management | create/list/detail/import-report | L2 + L3 | **PARTIAL** | API controller tests pass; an authenticated browser CRUD journey was not run locally. |
| USB Auditor | offline USB report import → asset/compliance | L2 | **PARTIAL** | Implemented as *offline report ingest* (`POST /assets/import-report`, `import_pipeline.py`). **No hardware/agent detection exists** → L6 NOT TESTED. |
| Log Analyzer — parsing | JSON/PAN-OS/vendor parsing, timestamps | L1 + L2 | **PASS** | `test_evtx_parser.py`, `test_analyzer_timestamp_contract.py` (46 tests together with auth/telemetry/search). |
| Log Analyzer — EVTX | real EVTX XML fixtures | L2 | **PASS** | parser tests pass on synthetic fixtures; corrupt/partial handling covered. |
| Log Analyzer — ingestion → persistence | sprint13 evidence ingestion into `analysis_history` | L2 + L4 | **PASS** | `test_sprint13_evidence_ingestion.py` 37 passed. |
| Log Analyzer — full input→UI→incident in one run | end-to-end | — | **NOT TESTED** | The stages are individually proven; a single local run from ingest to UI to incident was not executed in this phase. |
| AI analysis / recommendations | provider-backed analysis | — | **NOT APPLICABLE** | No LLM provider integration exists in `backend/` (no OpenAI/Gemini/Anthropic client, no API key config). The analyzer is a deterministic, knowledge-backed pipeline. Do not present it as an LLM. |
| Dashboard | counts vs DB, navigation | — | **NOT TESTED** | The Next.js dashboard was not run locally in this phase; it also has no incidents page. Demo console (`/demo`) is the demo UI. |
| Incident Management | create → evidence → resolve blocked → verify → resolve → reopen → stale rejected | L3 + L4 + deployed E2E | **PASS WITH LIMITATIONS** | 137-test baseline + public E2E: stale evidence → 422, valid verification → 200, `verifications=2`, cycle 1. Limitation: a fully compromised runtime credential can forge a consistent verification row. |
| Evidence & Verification | digest, distinct verifier, append-only, cycle binding | L2 + L4 | **PASS WITH LIMITATIONS** | 24 privilege tests + 22 verification tests; same credential limitation as above. |
| Audit / event history | audit rows written with verification provenance | L4 | **PASS** | `audit_logs` rows carry `verification_id`, `verifier`, `remediation_cycle`; not tamper-evident (excluded). |
| System health | required vs optional tier semantics | L3 + deployed | **PASS** | `/api/v1/ready` → 200 when DB healthy; `/api/v1/health` → 503 DEGRADED without cache/storage (by design, `EIMS_DEMO_SOFT_DEPS=1`). |

### Tests executed in this phase

| Command | Result |
|---|---|
| `pytest tests/test_evtx_parser.py tests/test_analyzer_timestamp_contract.py tests/test_auth_modes.py tests/test_api_controllers.py tests/test_telemetry_controllers.py tests/test_global_search.py` | **46 passed**, exit 0, 23.8s |
| `pytest tests/test_sprint13_evidence_ingestion.py` | **37 passed**, exit 0, 19.6s |
| `pytest tests/test_orm_models.py tests/test_state_machine.py` | **6 passed**, exit 0, 7.4s |
| combined run of sprint13 + analyzer_investigation + orm + state_machine | **collection error** (module interaction); each file passes when run alone — recorded as a harness defect, not a product defect |

Database for all runs: disposable PostgreSQL `eims_incident_test` (verified
identity, non-superuser).

## 3. Analyzer verdict (explicit)

| Question | Answer |
|---|---|
| Ingestion works? | **Yes** (L2): offline USB report + event ingestion into `analysis_history`. |
| Parsing works? | **Yes** (L1/L2): JSON, PAN-OS/vendor, timestamps. |
| EVTX works? | **Yes on synthetic fixtures** (L2). Real customer EVTX NOT TESTED (none used). |
| Analysis works? | **Deterministic knowledge-backed summary** (L2). No LLM provider. |
| Correlation works? | **Yes** (L2/L4): correlation + dedupe proven in Incident Core. |
| Persistence works? | **Yes** (L4). |
| API/UI display works? | **API yes**; **UI NOT TESTED** locally. |
| Integrates with Incident Management? | **Yes at domain/service level** (ingest → incident); a single local run through the UI was not performed. |

## 4. Engineer workflow

Proven end-to-end on the **deployed** instance: unauthenticated access denied →
login → open incident → see evidence and verification history → stale evidence
refused (`evidence_stale`) → attach current-cycle evidence → reviewer resolves →
read back `status=resolved`, `verifications=2`, cycle 1.

Proven locally at API/DB level. **Not** proven locally through a browser in this
phase.

## 5. Defects found

| ID | Defect | Root cause | Status |
|---|---|---|---|
| D1 | Seed could not verify as the least-privilege runtime role (`SELECT … FOR UPDATE` on evidence) | Row locks require UPDATE privilege, which the runtime intentionally lacks | **Fixed** — verification reads the evidence row without a lock; immutability is enforced by the absence of UPDATE/DELETE |
| D2 | `01_roles.sql` failed on managed PostgreSQL (`ALTER ROLE … NOSUPERUSER`) | Only a superuser may change SUPERUSER/BYPASSRLS | **Fixed** — attribute changes are guarded by `current_user` being superuser |
| D3 | Render deploy marked Failed | `/health` returns 503 when optional tiers are absent | **Fixed** — added `/api/v1/ready` for the required tier; health check path updated; DB ping timeout raised for Neon wake |
| D4 | Demo login 401 after re-seeding | Seed regenerated the demo password without rewriting the existing hash | **Fixed** — password reuse + `tools/reset_demo_password.py` |
| D5 | Combined pytest run of four files fails collection | Harness/module-level interaction, not product behaviour | **Open (P2)** — files pass individually |

## 6. Outstanding issues

**P0 before 24 Nov:** none identified in the tested paths.

**P1:** local browser E2E for Analyzer → Incident not executed; dashboard not
verified against DB; USB hardware path absent by design.

**P2 / future:** independent verifier service; tamper-evident journal; pooler
acceptance; production backup/HA; local dashboard incidents UI.

## 7. Deployment readiness (separate decision)

**READY FOR DEMO DEPLOYMENT** — the demo path (auth → incident → verification →
resolution → persisted proof) is already deployed and passed public E2E, and no
P0 defect is open in that path. The Analyzer/UI claims must be presented with the
limitations above; do not describe USB hardware detection or an LLM as working.
