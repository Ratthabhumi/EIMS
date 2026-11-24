# EIMS V12 — A11 Freeze Integrity Closure & Independent Review

Date: 2026-11-18 (Asia/Bangkok)
Campaign: V12 A11 — continuation of A8/A9/A10 (no recovery, no re-freeze)
Repository: `C:\Users\MewMew\Desktop\Co-op\EIMS`
Type: read-only audit + independent review. No source, test, config or `.gitignore` change.

## 1. Identity at A11

| Item | Value |
|---|---|
| Remote | `Ratthabhumi/EIMS` |
| Branch | `integration/eims-consolidated` |
| HEAD | `85493b2131d3e353453072559a5dfc301d75dd06` |
| Modified / Untracked (`-uall`) | 59 / 172 at A11 start |
| Staged / deleted | 0 / 0 |
| `git diff --check` | 0 |
| `core.autocrlf` | true |

Identity matches A8. The only tracked modification beyond A8's 58 is the authorized `.gitignore` line.

## 2. Manifest verification (statuses kept separate)

| Check | Result |
|---|---|
| `MANIFEST_FILE_HASH_VALID` | **PASS** — all four evidence files recompute to the A8 SHA-256 values |
| `MANIFEST_SCHEMA_VALID` | **PASS** — `v12-source-manifest/v1`, `sha256`, repository block present |
| `HEAD_BINDING_VALID` | **PASS** — 895 entries equal `git ls-tree -r HEAD`; reprocessing produced changed 0 / missing 0 / added 0 |
| `WORKING_TREE_BINDING_VALID` | **PASS** — 1,063 frozen entries match disk (changed 0 / missing 0); only the 4 declared post-freeze files differ |
| `SNAPSHOT_REPRODUCIBLE` | **PASS** — see §4 |
| `FREEZE_STILL_VALID` | **PASS** for source bytes; campaign output has since been added (§3) |

Integrity checks: 0 duplicate paths, 0 backslash paths, 0 `./` prefixes, 0 self-references, 0 null hashes, 0 case collisions, 0 `.git/` entries, 0 `venv/` entries, 0 `node_modules/` entries.

Three `.log` entries are legitimately present: two are the A9-released monitor fixtures (untracked), one is a tracked demo file (`EIMS_supervision_synthetic_demo_files_2026-10-09/02_Task_long.log`, `HEAD_IDENTICAL`). A tracked file is part of HEAD regardless of `*.log`.

## 3. Post-freeze output classification

| Path | Type | In frozen manifest | Source dependency |
|---|---|---|---|
| `evidence/v12-head-manifest.json` | freeze metadata | no | no |
| `evidence/v12-working-tree-manifest.json` | freeze metadata | no | no |
| `evidence/v12-evidence-revision-map.json` | evidence inventory | no | no |
| `evidence/v12-freeze-summary.json` | freeze metadata | no | no |

Classification: `POST_FREEZE_CAMPAIGN_OUTPUT`. The frozen manifest was not silently updated. A11 deliverables are the same class.

## 4. Disposable snapshot materialization

| Item | Value |
|---|---|
| Source | frozen working-tree manifest `53EE6A40…` |
| Snapshot root | `%TEMP%\v12-snapshot\EIMS-20261118-204324` |
| Files materialized | **1,063** |
| Total bytes | 41,344,360 |
| `.git/` copied | no |
| Changed vs frozen | **0** |
| Missing | **0** |
| Added in snapshot | **0** |

Includes product source, all 57 test files, migrations, the 12-file agent monitor plus fixtures, `docker-compose.yml`, `.env.example`, and the demo pack. Record: `evidence/v12-snapshot-materialization.json`.

## 5. Ownership and scope findings

| Item | Classification | Evidence |
|---|---|---|
| `scripts/agent-monitor/` (12 files) | `KEEP` — EIMS product component, untracked by decision | 12/12 hashes match the tested snapshot; A9 made the fixtures visible; **not staged or committed** |
| `scratch_append_tests.py` (7,562 B, 2026-10-03) | **DEVELOPMENT_TOOL / SOURCE MUTATOR** | rewrites `tests/test_analyzer_reliability.py` in place and writes `tests/_field_fixture_veeam.py`; referenced by nothing; **must not be run during acceptance** because it would invalidate the freeze |
| `tests/_field_fixture_veeam.py` | `LEGITIMATE EIMS PRODUCT (test fixture)` | tracked, imported by `tests/test_analyzer_reliability.py:1675` |
| `.omc/` (9 files, 61 KB) | `KEEP_PENDING_OWNER` — agent tooling state | contains `evidence/v11-*.xml` JUnit (HISTORICAL) and session/state JSON |
| `.kilo/`, `.cursor/` | `KEEP_PENDING_OWNER` — agent tooling config | no test/build references |
| `EIMS_DEMO_PACK_ORGANIZED_2026-10-09/` (17 MB) | `OUT_OF_SCOPE_BUT_PRESERVE` | untracked demo material; three `.log` members are git-ignored |

No file was deleted, moved or re-permissioned. No secret value was read or reported.

## 6. Independent review — executed

Reviewer: Claude Code CLI 2.1.323, `--permission-mode plan`, edits disallowed, run against the **materialized snapshot**.

Verdict: **BLOCK for acceptance**, explicitly *not* a code-quality block; the reviewer stated it found **no CRITICAL defect**.

| Severity | Count |
|---|---:|
| CRITICAL | 0 |
| HIGH | 4 |
| MEDIUM | 7 |
| LOW | 8 |
| INFO | 1 |

Full structured record: `evidence/v12-independent-review-findings.json`.

OpenCode re-verified the highest-severity findings against the frozen source:

| ID | Claim | OpenCode verification |
|---|---|---|
| F1 | The shared `client` fixture runs the full app lifespan and can reach default localhost services | **CONFIRMED** — `tests/conftest.py:94-98` uses `with TestClient(app)`; `backend/main.py` lifespan starts OCR/EVTX/telemetry workers and a Redis pub/sub listener; no disposable-target guard in the fixture |
| F2 | `AUTH_MODE` defaults to `demo` | **CONFIRMED** — `backend/core/config.py:53`; production boot guard exists at `config.py:94-112` |
| F3 | Dev compose ships hardcoded credentials and a public bucket | **CONFIRMED by reading** — `docker-compose.yml`; `tests/test_compose_security_audit.py` asserts these known findings |
| F4 | `AuditLog` immutability is documentation only | **CONFIRMED** — `asset_registry/models.py:175-221` uses the words "immutable"/"tamper-resistant"; **0** `CREATE TRIGGER` / `REVOKE` / hash-chain constructs exist in any migration |
| F5 | The ledger claims a migration head that is six revisions old | **CONFIRMED** — ledger says single head `a3d6f1e8c295`; the chain continues `a3d6f1e8c295 → b7c2e9a4f601 → … → c4e8a1f7b932` |
| F6 | `vector(768) → vector(384)` cast fails on populated data | **CONFIRMED by reading** — `migrations/versions/8a2b4d6f9c1e:19-26` uses `postgresql_using="embedding::vector(384)"`; pgvector rejects a dimension-changing cast on non-null rows |
| F16 | A scratch script rewrites tracked tests | **CONFIRMED** — see §5 |

### Evidence-honesty note

The ledger's PASS rows are not wrong as history; they are **not current**. `docs/V12_EVIDENCE_REVISION_BINDING.md` classifies the ledger HISTORICAL/UNVERIFIED, but the ledger itself does not carry that label. This remains an acceptance risk, not a code defect.

## 7. Container dependency (unchanged, not started)

From `docs/V12_CONTAINER_PREFLIGHT.md`: 5 acceptance containers are `exited (255)` with volumes intact, `eims-pgbouncer` is up, and ports 56441 / 56379 / 59000 / 59001 / 56460 / 56461 are free. Docker engine availability and restart-stability must be confirmed before Track C service steps. No container was started, stopped, recreated or pruned, and no volume was removed.

## 8. Test inventory — collected, not executed

`pytest --collect-only` in the snapshot (no test executed, `-p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`):

- **938 tests** collected from **57 files**, 0 collection errors, 11.7 s
- Partition (disjoint):
  - 770 tests / 37 files — no `client` fixture, no disposable-service environment variable
  - 29 tests / 6 files — use the `client` fixture (full lifespan; see F1)
  - 139 tests / 14 files — require explicit disposable service configuration

These counts are the basis of `docs/V12_TRACK_C_EXECUTION_PACKAGE.md`. They are collection counts, **not** pass counts.

## 9. Acceptance gate structure (corrected)

The former single "Gate 1" conflated source integrity with execution readiness. Gates are now separate, and each is evaluated only against the dependencies it actually needs.

| Gate | Scope | Requires runtime | Requires containers | Requires quiet host |
|---|---|---|---|---|
| **S — Source Integrity** | identity, frozen manifests, snapshot materialization, evidence mapping, ownership disposition, independent review, no unexplained writer | no | no | no |
| **C — EIMS Product Execution Readiness** | frozen EIMS snapshot, isolated env, CPU/RAM, only the dependencies of the step being run, credentials supplied safely, no data-loss risk | no | only for C2–C4 | yes |
| **B — Chat_HAND Internal Execution Readiness** | frozen Chat_HAND snapshot, user-started foreground runtime, process ownership, MCP health/tools, isolated state dir, no conflicting jobs | yes (live steps only) | no | yes |
| **X — Cross-system E2E** | Gate B and Gate C both PASS, explicit user approval, correlation test prepared | yes | yes | yes |

Rules:

- Chat_HAND runtime is **not** a prerequisite for EIMS `C1` / `C5` / `C7`.
- Containers are **not** a prerequisite for EIMS `C1`, `C5`, `C7`, `C9`.
- High CPU from user workload is never recorded as an EIMS or Chat_HAND product defect.
- A gate result is reported per item; a single aggregate PASS is not allowed.

## 10. Current gate status

| Gate | Status | Reason |
|---|---|---|
| **S — Source Integrity** | **PARTIAL** | manifests and snapshot verified; 4 HIGH findings; ledger stale |
| **C — EIMS Product Execution** | **BLOCKED** | containers stopped; credentials not supplied; test-isolation finding F1 must be resolved or mitigated before a full-suite run |
| **B — Chat_HAND Internal Execution** | **BLOCKED** | runtime stopped; Chat_HAND HIGH findings |
| **X — Cross-system E2E** | **NOT RUN** | depends on B and C |

## 10. What this proves and does not prove

Proves: the frozen EIMS bytes are reproducible in a disposable snapshot, the product test inventory is real, and an independent reviewer examined the actual source.

Does not prove: that any test passes on this revision, that the analyzer is accurate (0 reviewed cases), that audit records are tamper-evident, or that the operational database is safe from the shared `client` fixture.

No commit, push, merge, deploy, stage, reset, clean, checkout or stash was performed.
