# A17 — Final Acceptance Matrix

**Date:** 2026-11-19 · **HEAD:** `85493b2`

Legend — Implemented / Behaviorally tested / Runtime wired / Operationally verified /
Independently reviewed. `Y` = yes with evidence in this audit, `L` = limited,
`N` = no, `-` = not attempted.

| # | Capability | Implemented | Behaviourally tested | Runtime wired | Operationally verified | Independently reviewed | Delivery disposition | Security disposition |
|---|---|---|---|---|---|---|---|---|
| 1 | Asset registry API + persistence | Y | L | Y | N | N | Include | Scoped |
| 2 | Telemetry ingest → metrics/winlog | Y | L (114 offline tests) | Y | N | L | Include | Scoped |
| 3 | EVTX upload/parse/normalize | Y | L | Y | N | L | Include | Scoped |
| 4 | Analyzer submit/bundle/offline | Y | L | Y | N | L | **Include (primary demo)** | Scoped |
| 5 | Incident correlation v1 | Y | Y (`test_incident_correlation`) | Y | N | L | Include | Scoped |
| 6 | Incident ingestion v1.1 (outbox+consumer) | Y | Y (DB integration, prior run) | Y | L | Y (3-round review) | Include | Scoped |
| 7 | Search / timeline | Y | N | Y | N | N | Include with caveat | Scoped |
| 8 | AI enrichment | Y | N | Y | N | N | Include with caveat | External dependency |
| 9 | Dashboard UI | Y | N | Y | N | N | Include with caveat | Scoped |
| 10 | USB auditor (client) | Y | N | Y (packaged) | N | N | Include with caveat | Scoped |
| 11 | Benchmark (`sprint11_benchmark.py`) | Y | N | Y | N | N | **EXCLUDE from demo** | **Unsafe (NF-4)** |
| 12 | Maintenance CLI | Y | N | Y | N | N | **EXCLUDE / document enabled** | **Unsafe default (NF-2/3)** |
| 13 | `clear_db.py` | Y | N | Y | N | N | **EXCLUDE; flag as destructive** | **CRITICAL (NF-1)** |
| 14 | Seed scripts | Y | N | Y | N | N | Exclude from demo | Open (NF-6) |
| 15 | Gateway authorization (`risk-policy.mjs`) | **N (absent)** | N | N | N | N | **EXCLUDE** | R-3 open |
| 16 | Journal (tamper-evident audit) | **N (absent)** | N | N | N | N | **EXCLUDE** | R-4 open |
| 17 | DB identity at mutation boundary | N | N | N | N | N | Document as limitation | R-1 BLOCKED |
| 18 | Test-isolation guard | Y | L | Y | N | N | Document | R-2 partial |

## Delivery gate (project closure)

| Gate | Result |
|---|---|
| Core advertised workflow demonstrated with evidence | **YES** — analyzer → incident → evidence, offline tests + prior DB integration |
| Every presented claim backed by source/evidence | **YES, after exclusions** (see evidence map) |
| No unresolved defect invalidates the advertised scope | **YES, after excluding 11-16** |
| Handover + limitations documented | YES (this pack) |
| Security acceptance | **NO** — R-1/R-3/R-4/R-5/R-6 + NF-1/NF-2 open |

## Security gate

| Requirement | Result |
|---|---|
| Runtime authorization enforced and wired | **NOT ACCEPTED** (artifact absent) |
| Destructive paths guarded | **NOT ACCEPTED** (NF-1, NF-2, NF-4) |
| Mutation-boundary DB identity | **NOT ACCEPTED** (R-1) |
| Tamper-evident audit | **NOT ACCEPTED** (no journal) |
| Secrets handling | No values exposed in this audit; not re-certified |
