# EIMS V12 — Acceptance Execution Plan (Track-Separated)

Date: 2026-11-18 (Asia/Bangkok)
Status: **NOT RUN** — prepared only.
Supersedes the earlier mixed Gate 2 plan. The earlier single "Gate 2" conflated Chat_HAND internal tests with EIMS product acceptance; that is corrected here.

## 0. Why this plan exists

Two independent systems produce two independent acceptance results:

| Track | System | Owner |
|---|---|---|
| **A** | Engineering baseline (resources, freeze, provenance) | both repositories |
| **B** | Chat_HAND internal tool workflow | Chat_HAND |
| **C** | EIMS product behaviour | EIMS |
| **E2E** | ChatGPT → Chat_HAND → OpenCode → EIMS → result → acknowledgement | integration |

Scores are never combined. A Track B pass does not imply Track C progress, and vice versa.

---

## 1. Track A — Entry preconditions (must clear before B or C)

| # | Precondition | Verification | Current |
|---|---|---|---|
| A1 | Correct repository roots, branches, HEADs | `git rev-parse HEAD`, `git remote -v` | PASS |
| A2 | Known change inventory | `git status --porcelain -uall`, `git diff --check` | PASS (20/65, 58/86) |
| A3 | No active jobs | job store census | PASS (0 active) |
| A4 | No test-owned orphan writers | process scan | PASS (0) |
| A5 | CPU <30% continuously for 5 minutes | 21 samples at 15 s | **FAIL** — user workload |
| A6 | Free RAM >2 GB | same samples | PASS (2.2–2.4 GB) |
| A7 | Runtime stable under foreground owner | 1 tunnel, 1 gateway, same PIDs at 5 min | **FAIL** — stopped |
| A8 | Evidence bound to frozen source hashes | hash manifest | **FAIL** — see below |

### A8 — Revision freeze procedure (new, mandatory)

Because existing evidence is not revision-bound:

1. Record `HEAD`, `git status --porcelain -uall`, and `git diff --check`.
2. Record SHA256 of every file that a test will exercise, plus every test file itself.
3. Run tests **only** from a disposable copy whose hashes match that manifest.
4. Store the manifest next to the result: `{revision, fileHashes, command, result, timestamp, environment}`.
5. Reject any result whose manifest does not match the tree it claims to certify.

Do not start Track B or C before A8 exists.

---

## 2. Track B — Chat_HAND internal integration

### B.0 Environment

```
Copy Chat_HAND -> %TEMP%\chathand-accept-<timestamp>
```

- Use a dedicated `CHATHAND_STATE_DIR` inside the copy (never the live profile).
- No real Trust Grant is created; use the test harness's own grants.
- One writer at a time. No concurrent suites.

### B.1 Suites and purpose

| # | Command (inside the copy) | Checks | Purpose | Est. |
|---|---|---:|---|---|
| B1 | `node scripts/test-control-plane.mjs` | 35 | tool allowlist, deny rules, approval-before-write, audit completeness | 2–4 min |
| B2 | `node scripts/test-approval-lifecycle.mjs` | 17 | approval issuance, single use, expiry | 2–3 min |
| B3 | `node scripts/test-trust-grant.mjs` | 30 | grant scope, tamper, expiry/revocation, concurrency, audit-before-authority | 4–6 min |
| B4 | `node scripts/test-orchestration.mjs` | 22 | routing, multi-agent orchestration | 3–5 min |
| B5 | `node scripts/test-job-relay.mjs` | 31 | dispatch, execution, result, ack, idempotency, sensitive-output withholding | 6–10 min |
| B6 | `node scripts/test-agent-availability.mjs` | 17 | agent availability/failure handling | 2–3 min |
| B7 | `node scripts/test-job-relay.mjs` re-run (B5 only) | 31 | duplicate-execution prevention across restart | 6–10 min |

`scripts/Test-Repository.ps1` is a superset harness (all suites + syntax + guards + link check) and must also run **inside the copy only**, after B1–B7.

### B.2 Behaviour coverage map (existing coverage, no new tests needed)

| Required behaviour | Covered by |
|---|---|
| Job creation | `control-plane.job.*`, `relay.*` |
| Approval lifecycle | `test-approval-lifecycle.mjs`; `approval.*`, `relay.task_title_rejected_before_approval` |
| Trust Grant enforcement | `grant.*`, `integration.*` (30 checks) |
| Agent execution | `relay.*`, `test-orchestration.mjs` |
| Result persistence | `relay.stdout_stderr_separate`, `relay.chunks_match_full_hash` |
| Result retrieval | `relay.wait_returns_terminal_result`, `relay.pending_results_are_discoverable`, `relay.wait_fails_closed_without_result`, `relay.retrieval_is_recorded` |
| Acknowledgement | `relay.ack_is_idempotent`, `relay.ack_clears_unacknowledged`, `relay.no_duplicate_result_files` |
| Idempotency / duplicate prevention | `relay.duplicate_completion_idempotent`, `approval.single_use_race`, `grant.concurrent_use_single_winner` |
| Sensitive-output withholding | `relay.sensitive_output_withheld`, `relay.sensitive_anthropic_key_withheld`, `relay.interrupted_sensitive_withheld`, `relay.audit_has_no_secret`, `relay.token_not_on_disk`, `relay.detector_covers_pattern_families` |
| Failure recovery | `relay.agent_crash_failed`, `relay.runner_crash_interrupted`, `relay.missing_exit_interrupted`, `relay.late_exit_reconciles_interruption`, `relay.forged_exit_ignored`, `relay.mcp_restart_survives` |
| Session/scope boundaries | `relay.session_scope_denied`, `relay.cross_session_requires_local_approval`, `grant.scope_outside_and_hard_deny` |

### B.3 Known coverage gaps (do not invent results)

| Gap | Status |
|---|---|
| RPC latency budget | No assertion exists for an absolute latency bound; `relay.wait_is_bounded` only bounds the wait. Measure and report latency, do not assert a new threshold. |
| Live tunnel transport over ChatGPT | Not covered by any local suite — belongs to E2E. |
| Runtime lifecycle automation | No supervisor by design; manual 5-minute observation only. |
| Multi-job concurrency under load | Not covered. |

### B.4 B stop conditions

Stop and report BLOCKED if: any assertion fails; any RPC timeout occurs without a proven host cause; a duplicate job or process appears; evidence is written outside the disposable copy; the runtime stops; or a pass would require weakening an assertion, timeout or security control.

---

## 3. Track C — EIMS product integration

### C.0 Environment prerequisites

| Requirement | Status |
|---|---|
| Virtualenv `venv\Scripts\python.exe` | present (Python 3.14.3) |
| PostgreSQL disposable | container `eims-evtx-e2e-pg-20261114` — **Exited (255)** |
| Redis disposable | container `eims-evtx-e2e-redis-20261114` — **Exited (255)** |
| MinIO disposable | container `eims-evtx-e2e-minio-20261114` — **Exited (255)** |
| Ports | PG 56441, Redis 56379, MinIO 59000/59001 |

**All three disposable acceptance containers are stopped.** Service-dependent tests cannot run until they are restarted. Starting containers is a state change and is **not** performed in this read-only phase; it belongs to Track C execution under approval. Do not remove volumes.

Service-dependent tests resolve their target from environment variables and **fail closed** if the target is not the disposable loopback instance:

| Variable | Used by | Constraint enforced in code |
|---|---|---|
| `EIMS_TEST_DATABASE_URL` | EVTX e2e, analyzer postgres, incident DB tests | `postgresql+asyncpg`, loopback host, allowlisted database, allowlisted user, port not 5432/6432 |
| `EIMS_TEST_REDIS_URL` | EVTX e2e, lease refresh | loopback, port 56379 |
| `EIMS_TEST_MINIO_ENDPOINT` | EVTX e2e, restart recovery | `127.0.0.1:59000` |
| `EIMS_TEST_MINIO_ACCESS_KEY` / `EIMS_TEST_MINIO_SECRET_KEY` | EVTX e2e | disposable credentials only |
| `EIMS_TEST_SCHEMA` | EVTX e2e | must match `eims_full_lineage_<32 hex>` |
| `EIMS_TEST_BROWSER_BASE_URL`, `EIMS_TEST_LOGIN_CREDENTIAL` | browser acceptance | approved synthetic credential only |

**Credentials are not stored in the repository.** They must be supplied by the user from the disposable environment created on 2026-11-14. Do not invent values and do not point any test at the operational database.

Incident-ingest tests additionally use dedicated endpoints PG **56460** and Redis **56461**, declared in `tests/incident_ingest_support.py`.

Run from a disposable EIMS copy with the frozen hash manifest from A8.

### C.1 Subsystem matrix

| Subsystem | Source | Existing tests | Evidence today |
|---|---|---|---|
| Telemetry ingest / EVTX | `backend/domain/telemetry` | `test_telemetry_*` (13), `test_evtx_parser`, `test_evtx_worker_fault_contracts`, `test_evtx_queue_fail_closed`, `test_evtx_redis_recovery_integration`, `test_evtx_minio_postgres_e2e_acceptance` | HISTORICAL / UNVERIFIED for current tree |
| Incident | `backend/domain/incident`, `incident_ingest` | `test_incident_*` (10) | HISTORICAL |
| Analyzer | `backend/domain/analyzer` | `test_analyzer_*` (6) | PARTIAL (249 unit, 1 skip) HISTORICAL |
| Search | `backend/domain/search` | `test_global_search*` | HISTORICAL |
| Timeline | `backend/domain/timeline` | `test_timeline` | HISTORICAL |
| Evaluation | `backend/domain/evaluation` | `test_analyzer_evaluation` | **INSUFFICIENT_DATA** (0 reviewed cases) |
| Asset registry | `backend/domain/asset_registry` | `test_telemetry_nogroup_asset_lock_index` | HISTORICAL |
| API / auth / health | `backend/api/routers` | `test_api_controllers`, `test_auth_modes`, `test_health_probe_concurrency` | HISTORICAL |
| Data integrity / migrations | `migrations/` | `test_orm_models`, `test_sprint10_migrations`, `test_state_machine` | HISTORICAL |
| Evidence / audit | `backend/domain/incident`, migrations | `test_sprint13_evidence_ingestion` | **UNVERIFIED** — file modified 2026-11-17, after the last recorded run |
| Security config | `deployments/`, compose | `test_compose_security_audit`, `test_knowledge_safety_contract`, `test_event_knowledge_safety` | HISTORICAL |
| Recovery | telemetry/redis/minio | `test_redis_minio_restart_recovery_integration`, `test_telemetry_end_to_end_recovery`, `test_incident_ingest_v11_recovery_unit` | HISTORICAL |
| Persistent Monitor | `scripts/agent-monitor` | `Test-WatchEimsAgentJobs.ps1`, `Test-LaunchEimsAgentMonitor.ps1` | source-byte matched, 2 suites |

Total: 57 `test_*.py` files. No custom pytest markers; service-dependent tests are identified by name and by support modules (`incident_db_support.py`, `incident_ingest_support.py`, `analyzer_synthetic_demo_app.py`).

### C.2 Execution order

| # | Command | Purpose | Est. |
|---|---|---|---|
| C1 | `venv\Scripts\python.exe -m pytest tests -q` (no services) | baseline unit/contracts | 5–15 min |
| C2 | `pytest tests/test_telemetry_* tests/test_evtx_* -q` with PG/Redis/MinIO up | telemetry E2E | 15–25 min |
| C3 | `pytest tests/test_incident_* -q` with PG | incident + data integrity | 10–20 min |
| C4 | `pytest tests/test_analyzer_* -q` | analyzer regression | 10–20 min |
| C5 | `pytest tests/test_global_search* tests/test_timeline.py tests/test_orm_models.py -q` | search/timeline/ORM | 5–10 min |
| C6 | `pytest tests/test_sprint13_evidence_ingestion.py -q` | evidence/audit (currently untested revision) | 2–5 min |
| C7 | `powershell -File scripts\agent-monitor\tests\Test-WatchEimsAgentJobs.ps1` | watcher | 1–2 min |
| C8 | `powershell -File scripts\agent-monitor\tests\Test-LaunchEimsAgentMonitor.ps1` | launcher | 1–2 min |

Capture JUnit XML per command into the disposable copy and hash it.

### C.3 Known EIMS limitations to report honestly

- Analyzer evaluation: 0 reviewed cases → accuracy cannot be claimed.
- Browser acceptance previously FAILED/BLOCKED (no listener on 3449/8000).
- Monitor GUI, raw-key and long-running survival not verified.
- Ledger file is untracked and reports a stale repository state (32/30 vs 58/86).

### C.4 C stop conditions

Stop and report BLOCKED if: a service is unavailable; a test needs data that does not exist; a result would require modifying a test to pass; evidence lands outside the disposable copy; or a service restart destroys a volume.

---

## 4. Cross-system E2E (after B and C)

Sequence to prove: ChatGPT → Chat_HAND → OpenCode → EIMS repository → job result → evidence verification → acknowledgement.

Prerequisites: runtime running under the user's persistent terminal; 18 tools; `trust_grant_id` present; Track B green; Track C green on the frozen revision.

This must be executed with the user present, because approval is a human step. Do not fabricate a pass.

---

## 5. Independent security review scope (Claude Code, read-only)

**Chat_HAND:** Trust Grant design and scope enforcement; approval boundaries; job execution authority; audit-before-use; result handling and sensitive-output withholding; runtime lifecycle and ownership.

**EIMS:** product security configuration; data integrity and migrations; evidence provenance; agent integration boundaries; monitoring permissions; recovery behaviour.

Requested only after the diff and hash manifest are frozen.

---

## 6. Expected evidence record format

```json
{
  "track": "B | C",
  "command": "...",
  "revision": { "repo": "...", "branch": "...", "head": "...", "worktreeDirty": true },
  "fileHashes": { "path": "sha256" },
  "environment": "disposable copy path, PowerShell version, Python version, service endpoints",
  "result": { "passed": 0, "failed": 0, "skipped": 0, "exitCode": 0 },
  "classification": "CURRENT VERIFIED | HISTORICAL | STALE | MIXED PROVENANCE | UNVERIFIED | INVALID",
  "timestamp": "ISO-8601"
}
```

---

## 7. Current blockers for this plan

1. Runtime stopped; user must start it in a persistent terminal.
2. CPU 65–96% from user workload; a quiet 5-minute window is required.
3. EIMS disposable PostgreSQL/Redis/MinIO containers are stopped.
4. No frozen hash manifest yet (A8).
5. Monitor Git provenance decision pending (fixture tracking).
6. Two job files remain ACL-unreadable.

No command in this plan has been executed.
