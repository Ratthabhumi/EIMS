# Certification Round 3 — Technical Pilot Report (2026-11-22)

One real record per class (two where the contrast matters), chosen from the committed register. "Pilot disposition" is an assessment of *technical readiness for human review*; it is not a certification. Human reviewer, review date and decision stay blank for every record.

| Class | Record key | Why chosen |
|---|---|---|
| A | `operational:windows_event:official_event_id:4199` | exact Microsoft reference; legacy meaning corrected in Tranche 18 |
| A | `operational:windows_event:official_event_id:1054` | no exact source (indirect page only): shows the blocked path |
| B | `diagnostic_legacy:cisco_asa:official_message_id:106023` | legacy parser-linked candidate |
| B | `candidate:postgresql:locks:deadlock-detected` | SQLSTATE-linked candidate |
| C | `reference:postgresql:sqlstate:40P01` | parser-mapped reference (same SQLSTATE as the B record above) |
| D | `candidate:postgresql:replication:slot-retains-wal-filling-pg-wal` | state evaluator; real PostgreSQL evidence |
| D | `candidate:fortinet-fortios:ha:failover-reason-from-ha-status` | state evaluator; no real source output |
| E | `candidate:cisco-ios:bgp:session-reset-on-interface-flap` | candidate with no parser; also has an unresolved risk statement |
| F | `reference:haproxy:termination_state_first_char:I` | reference-only; also had an "always/never" finding |

## Results
| Record | Source evidence | Technical validation method and result | Limitations / open items | Human review needed | Pilot disposition |
|---|---|---|---|---|---|
| A 4199 | 1 Microsoft Learn URL (page scope sentence only) | `resolve_windows_entry` resolves uniquely — pass | version applicability not stated explicitly (`version_scope_not_explicit`) | read the page's applicability line; confirm title/severity/meaning | READY FOR HUMAN REVIEW after the version scope is read; source-blocked until then |
| A 1054 | none exact (indirect page, disposition `INDIRECT_AUTHORITATIVE_REFERENCE`) | identity resolves — pass | `source_url_missing`, `version_scope_missing` | choose or confirm an exact source | BLOCKED (source) |
| B ASA 106023 | 1 Cisco URL, explicit version scope | 1 positive + 2 negative cases through the real parser, current hash — pass | synthetic lines only | source, causes/steps/warnings review | READY FOR HUMAN REVIEW |
| B PG deadlock | 2 PostgreSQL 16 doc URLs | SQLSTATE 40P01 positive; unlinked 23505 and success-class 00000 negatives — pass | PostgreSQL 16 only; remediation mentions retry/consistent lock order | as above | READY FOR HUMAN REVIEW |
| C PG 40P01 | 1 URL | synthetic jsonlog line with `state_code=40P01` resolves to this reference — pass | no per-row negative | table-level or row review (owner decision pending) | READY FOR HUMAN REVIEW |
| D PG slot | 3 PostgreSQL doc URLs | **real** PG 16.16 rows: reserved/active (negative), reserved/extended/lost inactive orphan (positive ×3), `safe_wal_size` NULL with `-1` (positive) — all 5 pass; 3 authored-row cases also pass | `unreserved` unobserved; no thresholds (none documented); single lab pair | DBA reviewer on attention semantics | READY FOR HUMAN REVIEW (technical) |
| D FortiGate HA | 1 Fortinet Community URL | authored-string evaluator cases pass but are **not** real-source evidence | no FortiGate/real `get sys ha status` output; version applicability to 6.2.x unstated | network engineer; real output | BLOCKED (technical) — `TECHNICAL_UNVALIDATED` |
| E Cisco IOS BGP | 1 Cisco URL | schema completeness — pass; no parser exists, no matching evidence is claimed | `destructive_remediation_risk_unresolved` ("Not stated") | decide the risk wording | PARTIAL: reference-only; not a diagnostic capability |
| F HAProxy `I` | 1 HAProxy 2.8 URL | schema completeness — pass | verbatim vendor text includes "should NEVER happen" and a restart suggestion (accepted limitation, source re-checked) | re-read source | READY FOR HUMAN REVIEW (reference scope) |

## What the pilot shows about the process
1. Every class has a working evidence path and a recorded blocker where one exists.
2. The validator caught real weaknesses in Round 2's own rules (page-scope sentence accepted as version scope; "Not stated" accepted as a risk statement) and two environment/builder bugs were found by tests and fixed (see the technical evidence report).
3. The least-evidenced classes are A (0 of 153 records have an explicit version scope) and D (2 of 4 blocked).
4. Class E and F "technical validation" is only schema completeness; do not read it as more.
5. Nothing in the pilot involved a human reviewer; no decision, name or date was written.
