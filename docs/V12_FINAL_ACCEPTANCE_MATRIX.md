# EIMS V12 — Final Acceptance Matrix (Track-Separated)

Generated: 2026-11-18 (Asia/Bangkok)
Status: **NOT a completion declaration.** Gate 1 is blocked; no integration test has run against the current source.

Scores are not combined across tracks.

## Repository baselines

| Repository | Branch | HEAD | HEAD date | Role |
|---|---|---|---|---|
| EIMS | `integration/eims-consolidated` | `85493b21…` | 2026-11-13 | primary product |
| Chat_HAND | `v2/verified-fallback` | `c293b8aa…` | 2026-11-16 | internal control plane |

Working-tree inventory at audit time: EIMS **58 modified / 84 untracked** (86 after this campaign's two evidence files), Chat_HAND **20 modified / 65 untracked**. `git diff --check` = 0 in both.

---

## Track A — Engineering Baseline

| Item | Status | Evidence | Note |
|---|---|---|---|
| Repository identity and boundaries | **PASS** | remotes, branches, `gateway/projects/eims.json` | two distinct repositories |
| Recovery copies (report, monitor evidence) | **PASS** | SHA `5AFB495E…`, `F59DCC75…` | byte-identical |
| Historical HEAD archive | **PASS** | `Chat_HAND/evidence/archive/historical-head-c293b8aa/` | HISTORICAL only |
| Per-file provenance inventory | **PASS** | `Chat_HAND/docs/RECOVERY_CHAT_HAND_INVENTORY.md`, `EIMS/docs/RECOVERY_EIMS_INVENTORY.md` | classification present |
| Resource readiness | **NOT READY** | `EIMS/evidence/resource-attribution-20261118.json` | CPU 65–96% from user workload |
| Free RAM >2 GB | **PASS (marginal)** | same | 2.2–2.4 GB |
| Active jobs / orphan writers | **PASS** | job census | 0 active, 0 orphan |
| Evidence revision binding | **PARTIAL** | manifests exist; prior results remain STALE/UNVERIFIED until regenerated | see below |
| Frozen hash manifests (HEAD + working tree) | **PASS** | `EIMS/evidence/v12-*.json` | authoritative counts in freeze summary |
| Monitor Git provenance | **PARTIAL** | scoped negation applied (A9); directory still untracked | controller decides whether to track |
| Independent review | **NOT RUN** | `docs/V12_INDEPENDENT_REVIEW_SCOPE.md` | scope prepared, review not requested |

### Revision-binding finding

- EIMS: HEAD is 2026-11-13, but product test evidence is dated 2026-11-14/16 and **45 of 58 modified files are newer than 2026-11-14**, one newer than 2026-11-16. Evidence is **UNVERIFIED** for the current tree.
- Chat_HAND: `gateway/control-plane.mjs` was modified at 16:27, **after** the 16:20 relay evidence. Relay evidence is **STALE**.

---

## Track B — Chat_HAND Internal Tool Readiness

| Capability | Status | Basis |
|---|---|---|
| Runtime lifecycle | **BLOCKED** | runtime stopped; last session survived 5 min (tunnel 34036 / gateway 34296) |
| Control-plane tool surface | **PASS (historical)** | 35 checks; evidence predates current file |
| Approval lifecycle | **PASS (historical)** | 17 checks |
| Trust Grant | **PARTIAL** | 30/30 in disposable copy; not re-bound to current tree; conditional security review |
| Agent orchestration / routing | **PASS (historical)** | 22 checks |
| Job dispatch → execute → result | **STALE** | 31/31 recorded 16:20; gateway changed 16:27 |
| Result retrieval and acknowledgement | **STALE** | same suite |
| Sensitive-output withholding | **PARTIAL** | focused probe passed; suite evidence stale |
| RPC latency and correlation | **NOT MEASURED** | no absolute latency assertion exists |
| Failure recovery | **STALE** | suite evidence stale |
| Live ChatGPT MCP path | **NOT RUN** | requires tunnel |

Track B cannot be certified until it is re-run against the frozen hash manifest inside a disposable copy.

---

## Track C — EIMS Product Acceptance

| Subsystem | Status | Evidence |
|---|---|---|
| Persistent Monitor (source/tests) | **PARTIAL** | 12/12 files byte-identical to tested snapshot; watcher 169/169, launcher 171/171 (separate suites); transcript not preserved |
| Monitor GUI / raw-key / survival | **NOT RUN** | not observed |
| Telemetry ingest / EVTX | **HISTORICAL** | evidence predates current tree |
| Incident ingest / lifecycle | **HISTORICAL** | same |
| Analyzer | **PARTIAL / HISTORICAL** | 249 unit, 1 skip; accuracy not certifiable (0 reviewed cases) |
| Search / timeline / ORM | **HISTORICAL** | same |
| Data integrity / migrations | **HISTORICAL** | same |
| Evidence / audit ingestion | **UNVERIFIED** | test file modified 2026-11-17, after last recorded run |
| Security configuration | **HISTORICAL** | compose/auth/knowledge-safety suites |
| Recovery behaviour | **HISTORICAL** | redis/minio restart suites |
| Browser acceptance | **FAIL** | previous run: connection refused on 3449/8000 |
| Operational acceptance | **NOT RUN** | — |

All service-dependent suites need the disposable PostgreSQL/Redis/MinIO containers, which are currently **stopped**.

---

## Cross-System E2E

| Item | Status |
|---|---|
| ChatGPT → Chat_HAND → OpenCode → EIMS → result → acknowledgement | **NOT RUN** |

---

## Gate 1 Decision

**BLOCKED**

| Prerequisite | Result |
|---|---|
| Repository identity | PASS |
| Known change inventory | PASS |
| Evidence provenance / revision binding | PARTIAL — manifests exist, results not yet regenerated |
| No active jobs | PASS |
| No orphan writers | PASS |
| CPU <30% for 5 continuous minutes | FAIL (user workload) |
| Free RAM >2 GB | PASS |
| Stable owned runtime | FAIL (stopped) |

Gate 2 is **NOT RUN**.

---

## Remaining risks

1. Manifests exist, but no test result is yet bound to them; every prior result is STALE or UNVERIFIED.
2. Runtime is foreground-owned; closing the terminal stops dispatch.
3. Monitor is untracked and 2 fixtures are ignored by `*.log`.
4. Two job files remain ACL-unreadable and UNVERIFIED.
5. Analyzer accuracy cannot be certified with 0 reviewed cases.
6. No independent security review has been performed.
7. Browser acceptance previously failed.
8. EIMS ledger is untracked and reports a stale 32/30 inventory.

---

## Next actions

1. Controller decides whether to track the monitor directory now that the fixture negation is applied.
2. User starts the runtime in a persistent terminal.
3. Quiet-host 5-minute resource preflight.
4. Record the frozen hash manifest (Track A8).
5. Run Track B in a disposable Chat_HAND copy.
6. Restart disposable EIMS services, then run Track C in a disposable EIMS copy.
7. Claude Code read-only review on the frozen diff.
8. GUI/raw-key and long-running survival acceptance.
9. Live cross-system E2E, or mark BLOCKED.
10. Re-issue this matrix using only revision-matched evidence.

No commit, push, merge or deploy has been performed.
