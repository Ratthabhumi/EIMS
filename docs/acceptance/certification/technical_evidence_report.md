# Certification Round 3 — Technical Evidence Report (2026-11-22)

Everything here is **automated technical evidence**. No record was source-verified, reviewed or approved; human review fields are blank in all 911 rows.

## 1. Baseline audit of Round 2 (before any change)
| Check | Result |
|---|---|
| Working tree at start | branch `demo/2026-11-24`, HEAD `3f2beea`, 315 entries (225 untracked, 90 modified); recorded in the session scratchpad |
| Register derived from the real catalogs | yes — `build_register()` reads the four catalog files directly |
| Stable keys / determinism | three builds (two fresh, one committed) produced identical SHA-256 `3342fb1b…` |
| Content hash | 181 legacy/operational rows use `knowledge.service.canonical_hash` of the loaded record; 730 use SHA-256 of the canonical source record |
| Record loss / duplication | none (911 unique keys = sum of the four catalogs) |
| Class assignment | recomputed independently in `tests/test_certification_round3.py`; matches |
| Validator output reproduced | **132 findings** = 131 actionable + **1 informational summary row** (`reference_parser_check_summary`); Round 2 counted the evidence row among findings |
| Test evidence in Round 2 | **all 911 `test_evidence` lists were empty** — the 43 "missing" findings meant "not attached", not "no tests exist" |
| Legacy parser mapping | the 28 legacy diagnostics had `parser_or_evaluator = null` (register gap); now `existing_parser_existing_signature` |
| Weak rules found | (a) a risk field reading "Not stated…" counted as a stated risk; (b) a cited page's scope sentence counted as a version scope for 111 Windows records; (c) two different destructive-verb lists in the register and the validator |

## 2. Evidence produced
| File | Content |
|---|---|
| `technical_evidence_matching.json` | 119 cases (42 positive, 77 negative) over 42 records run through `parse_event_metadata` → `entry_for_metadata` / `catalog_summary` (the Analyzer path). Each case stores input hash and preview, expectation, actual outcome, git HEAD, UTC time and the record's content hash |
| `technical_evidence_pg_state.json` | 9 cases from a **real disposable PostgreSQL 16.16 primary + streaming standby** (see §4) |
| `register.json` / `register.csv` | regenerated; evidence is attached per record and flagged `current` only if its bound content hash equals the record's present hash |
| `register_round2_baseline.*`, `baseline_round2_findings.json` | the Round 2 outputs, preserved unchanged |
| `findings_disposition.json` / `.csv` | one row per finding (section 3) |
| `validator_report.json` | validator run with disposition reconciliation |

Fixtures live in `tests/certification_fixtures.py` (synthetic, RFC 5737 addresses). Negative cases are non-vacuous: e.g. a PAN `THREAT` row given as the negative for `TRAFFIC` resolves to `THREAT`, not to nothing; ASA lines with an unknown ID or without the ASA prefix resolve to nothing; PostgreSQL look-alikes (other program, changed wording, no syslog prefix) never match.

## 3. Findings reconciliation
| | Count |
|---|---:|
| Round 2 findings dispositioned (each its own row) | 132 |
| → RESOLVED_BY_EVIDENCE (41 positive + 41 negative coverage findings) | 82 |
| → BLOCKED (40 Windows version scope with no exact source; 2 HA-failover + 2 unmapped-HA coverage findings) | 44 |
| → NEEDS_HUMAN_REVIEW (Windows 1002 and 1076 version scope) | 2 |
| → ACCEPTED_LIMITATION (Veeam "nearly always", HAProxy "should NEVER happen"; both checked against the source page on 2026-11-22) | 2 |
| → NOT_APPLICABLE (FortiOS object name "Default Schedule: always"; the informational summary row) | 2 |
| New findings from stricter Round 3 rules | 162 |
| → `version_scope_not_explicit` (Windows records with only a page-scope sentence) | 111 |
| → `source_url_missing` (the same 42 Windows records without an exact source) | 42 |
| → `destructive_remediation_risk_unresolved` | 6 |
| → `state_real_evidence_*_missing` (FortiGate HA) | 2 |
| → `evaluator_not_mapped` (unexpected HA failover causes) | 1 |
| **Actionable findings now (fresh validator run)** | **207** |

The finding count went **up** (131 → 207) because the rules were tightened, not loosened. No rule was relaxed. Two rule changes narrowed what a baseline finding meant, and both are reported as OPEN, not resolved: the class-D requirement moved from parser-style evidence to real-source evidence, and the HA records stay blocked.

The four baseline coverage findings of the two PostgreSQL class-D records (slot, lag) were resolved by real database output, not by authored rows.

## 4. Class D real PostgreSQL evidence
Environment (disposable, created by `tools/certification_pg_pair.sh`, labelled `eims.purpose=synthetic-cert-test`, ports on 127.0.0.1 only, torn down afterwards): PostgreSQL 16.16, `max_wal_size=32MB`, `max_slot_wal_keep_size=64MB`, `wal_keep_size=0`, one streaming standby using a physical slot. The runner refuses any non-local host, any database other than `eims_cert_state`, and any server whose `cluster_name` is not the disposable marker; credentials are not written to the evidence file.

| Evaluator | Real observation | Evaluator vs documentation mapping |
|---|---|---|
| `evaluate_replication_slot` | active standby slot `reserved` (negative) | no attention — matches |
| | orphan slot trajectory `reserved → reserved → reserved → extended → lost` over 5 WAL-generation rounds | state and attention match the documented meaning for each observed status |
| | `max_slot_wal_keep_size=-1` | `safe_wal_size` NULL; evaluator explains unlimited retention — matches |
| `evaluate_standby_lag` | idle caught-up standby: write/flush/replay lag all NULL (negative) | `no_lag_measurement`, no attention — matches |
| | measurable lag (0.000793 s) with a caller threshold of 0 s | `caller_threshold_exceeded` (the threshold is the caller's; the documentation gives none) |
| | same row, no threshold | no attention — matches |
| | standby replay paused while the primary writes: replay_lag 3.75 s vs write/flush ≈ 1 ms | consistent with the row actually returned |

Honest limits: the `unreserved` status was **not observed** (the slot went from `extended` to `lost` between checkpoints), so there is no real-source case for it; evidence proves the evaluator agrees with documented semantics on real rows, not that any threshold is right; no FortiGate or real `get sys ha status` output was available, so `failover-reason-from-ha-status` stays `TECHNICAL_UNVALIDATED` and `unexpected-failover-causes` (no evaluator) stays blocked.

An environment error was found and fixed during this run, not in the code under test: a first attempt passed `max_slot_wal_keep_size` on the server command line, which overrides `ALTER SYSTEM`, so the `-1` scenario could not take effect. The failing case was reported, the provisioning corrected, and the full scenario rerun.

## 5. Class C: the two non-emitted references
`reference:postgresql:sqlstate:00000` and `reference:systemd:exit_status:0` are success-status references. The parser contract deliberately does not surface them (PostgreSQL class 00 is excluded in `vendor_diagnostics.py`; systemd status 0 is success). The validator records `reference_parser_expected_non_emission` for exactly these two and tests assert it. The other 310 parser-mapped references each resolve through the real parser with a synthetic positive line (`reference_parser_positive`); no mismatch.

## 6. Meaning of "technically validated" per class (what it does and does not say)
| Class | Technical check executed | Weakness |
|---|---|---|
| A (153) | `resolve_windows_entry(event_id, provider)` resolves uniquely to the record | says nothing about the content being right |
| B (39) | ≥1 positive and ≥1 negative case through the real parser/Analyzer, current hash | synthetic fixtures only; no real customer logs |
| C (312) | synthetic positive line resolves to this reference | no negative per row |
| D (2 of 4) | real-source positive and negative evidence | single-node-pair lab; `unreserved` unobserved |
| E (57) / F (346) | schema completeness | the weakest check; nothing parser-related exists |


## Round 4 additions
* Windows source research: `windows_source_research_ledger.json/.csv` (92 cited pages fetched; verbatim applicability statements; publication data, OS statement, product-level scope, event schema versions and build mentions kept separate). 100 catalog records gained an `applicability` block; findings for Windows version scope fell from 111 to 11 "page-scope only" + 47 "product-level only".
* Real-source discipline unchanged: the PostgreSQL evidence (9/9) was re-verified as hash-bound and current; no new device or database evidence was created; FortiGate HA stays blocked (`fortigate_ha_capture_checklist.md`).
* Evidence is regenerated only when content or evidence changes; no earlier test was re-run without a reason.
* Risk-source scan (`risk_warning_evidence.json`): 6 candidates; 1 not retrievable automatically (Cisco, HTTP 403, not bypassed), 4 with sentences needing a human relevance check, 1 with no relevant vendor risk statement identified. Keyword scan only: not proof that no warning exists.
