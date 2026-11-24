# EIMS V13 — A17 Phase 0 Baseline & Mutation Path Inventory

Date: 2026-11-19 (Asia/Bangkok)
Status: **PHASE 0 COMPLETE — awaiting approval before any source change.**
No source file was modified. No service, container, migration or operational target was touched.

## 1. Repository identity (verified)

| | EIMS | Chat_HAND |
|---|---|---|
| Root | `C:\Users\MewMew\Desktop\Co-op\EIMS` | `C:\Users\MewMew\Desktop\Co-op\Chat_HAND` |
| Branch | `integration/eims-consolidated` | `v2/verified-fallback` |
| HEAD | `85493b2131d3e353453072559a5dfc301d75dd06` | `c293b8aae2cbf2a669ba1cb4210001efe1f14885` |
| Modified / Untracked (`-uall`) | 59 / 200 | 20 / 94 |
| Staged | 0 | 0 |

Both match the A16 baseline. No unexplained drift.

## 2. Evidence integrity

| Artifact | Actual SHA-256 | Matches A16 report |
|---|---|---|
| EIMS `v12-a16-remediation-manifest.json` | `D8481ABB6FDCD873CF625339A1E6D551EE25EFAB2E241EEA11FC11E10111B84A` | **yes** |
| Chat_HAND `v12-a16-remediation-manifest.json` | `F0CDDA94A2575A5C3691431EC753BA8DB34341ABEB7737F087ED123444003963` | **yes** |

## 3. A16 findings re-checked against current source

| A16 finding | Current state |
|---|---|
| Missing `docs/V12_A16_CHAT_HAND_TRUST_BOUNDARY.md` | **confirmed absent** (file does not exist) |
| Journal/policy not wired | still only imported by `scripts/test-a15-execution-integrity.mjs` |
| Destructive paths unguarded | still true; see inventory |

## 4. Mutation path inventory (Phase 1, grep-level)

Search over `backend/`, `tools/`, `scripts/`, `migrations/` for `TRUNCATE|DROP TABLE|DELETE FROM|INSERT INTO|UPDATE … SET|execute(|session.add|add_all|bulk_save`:

- **180 hits across 43 files**
- Engine/session creation: **15 hits in 5 files** (`backend/infrastructure/database.py`, `tools/sprint11_benchmark.py`, `migrations/env.py`, `tools/import_knowledge_source_candidates.py`, `tools/maintain_analyzer_sessions.py`)

### Highest-density mutation files

| File | Hits | Class |
|---|---:|---|
| `tools/seed_analyzer_incident.py` | 25 | **C — seed/demo** |
| `tools/seed_demo_data.py` | 15 | **C — seed/demo** |
| `backend/domain/asset_registry/repository.py` | 13 | **A — application runtime** |
| `backend/api/routers/analyzer/knowledge.py` | 11 | **A — application runtime** |
| `backend/domain/analyzer/services/bundle.py` | 10 | **A — application runtime** |
| `tools/sprint11_benchmark.py` | 10 | **B — maintenance/benchmark** |
| `backend/domain/telemetry/worker.py` | 9 | **A — application runtime** |
| `backend/api/routers/analyzer/history.py` | 8 | **A — application runtime** |
| `backend/domain/incident/service.py` | 7 | **A — application runtime** |
| `backend/api/routers/evaluations.py` | 7 | **A — application runtime** |
| `backend/domain/incident_ingest/dispatcher.py` | 5 | **A — application runtime** |

### Paths explicitly named by A16 (re-verified as present)

| Path | Mutation | Guard | Identity check |
|---|---|---|---|
| `tools/maintain_analyzer_sessions.py --apply` | DELETE auth rows | none | none |
| `tools/seed_analyzer_incident.py` | DELETE + inserts | none | none |
| `tools/seed_demo_data.py` | inserts via `settings` engine | none | none |
| `tests/test_global_search_integration.py::db_session` | test DB session | none | none |
| `tools/sprint11_benchmark.py` | TRUNCATE | URL allowlist + guard | **async identity (new)** |

**Not yet verified:** each of the 43 files traced to its entry point; `backend/infrastructure/database.py` engine lifetime relative to lifespan; whether `migrations/env.py` can be invoked by a non-migration path. These remain **UNVERIFIED** until Phase 1 is completed path-by-path.

## 5. Classification summary (working)

| Class | Count (files) | Enforcement status |
|---|---:|---|
| A — application runtime | ~30 | no authorization boundary; app role only |
| B — maintenance CLI | 4 | partial (benchmark only) |
| C — seed/demo | 2 | none |
| D — test-only DB access | ~8 | partial (client fixture guard) |
| E — migrations | ~2 | no approval gate (by design) |
| F — read-only | ~6 | n/a |
| G — dead/unused | 0 verified | not assessed |

## 6. ADR drafts (decisions required before code)

### ADR-01 — Trusted broker / signer
Options:
- **L1 Local integrity**: HMAC key stored outside the journal file but readable by the same OS user. Detects corruption and accidental edits only. Cannot resist a same-user attacker.
- **L2 Separate signer**: broker runs under a different OS identity; signing key ACL-denied to the application; signed completion records; verifier checks signature, sequence, lifecycle, signer key version.
- **L3 External anchored store**: L2 plus an append-only remote checkpoint.

Decision needed: which level is in scope for V13. **Strong anti-forgery may only be claimed at L2+.**

### ADR-02 — Authorization
Remove `approver` / `approverVerified` from the API. Principal comes from a server context. Actions come from a server-owned registry with risk class, required authority and resource scope. Deny by default. Approval remains BLOCKED until an authenticated approver exists.

### ADR-03 — Mutation enforcement
Single enforcement boundary used by every destructive path. Prohibit direct engine creation outside it, or require every engine creation to pass target resolution + identity verification.

### ADR-04 — Database identity
Validate URL → create engine → open connection → read `current_database/current_user/session_user/current_schema` → **execute the mutation on that same connection/transaction**. Pooled-checkout gaps must be closed.

### ADR-05 — Journal lifecycle
Lifecycle: REQUESTED → AUTHORIZED → EXECUTION_STARTED → EXECUTION_SUCCEEDED/FAILED → (RECOVERY). COMPLETED only from the trusted executor. Verifier rejects missing first record, bad signature, broken chain, reorder, duplicate/missing sequence, illegal transition, unknown key. `recover()` becomes internal-only. Truncation detection requires an external checkpoint.

### ADR-06 — Infrastructure scope
Redis ACL, PgBouncer auth/TLS, image digests remain a **separate gate**. No running-service changes.

### ADR-07 — Vector contract
Determine the embedding model identity and output dimension before any schema decision. The 768→384 cast is not evidence of intent.

## 7. Gate status at Phase 0

| Gate | Status |
|---|---|
| A — Trust architecture | **DESIGN_ONLY / BLOCKED** |
| B — Authorization | **BLOCKED** (caller-authoritative) |
| C — Runtime mutation enforcement | **BLOCKED** (inventory incomplete) |
| D — Infrastructure / data integrity | **NOT RUN** |
| E — Independent review | **NOT RUN** |

## 8. Stop point

Phase 0 ends here. Required approvals before Phase 3 (source changes):

1. Choose ADR-01 level (L1 / L2 / L3) — this determines whether "anti-forgery" may be claimed at all.
2. Approve the authorization model (server principal + registry; approval stays blocked).
3. Approve that every destructive path must route through one boundary (this changes CLI/seed ergonomics).
4. Confirm whether `seed_demo_data` / `seed_analyzer_incident` are demo-only (isolate) or maintenance (guard) — they should not be forced into the broker path without a decision.
5. Confirm Phase 1 may take the time to trace all 43 files to entry points (no code change).

No source was modified in Phase 0.
