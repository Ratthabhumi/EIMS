# Remediation evidence — final report (2026-11-22)

Scope: the 28 candidates the engineer-facing contract rejected last round (3 later shown to be prohibition-only). Raw material: `remediation_research_candidates.json` (verbatim keyword sentences from the cited pages), `remediation_fields_curated.json` (fields prepared for four records), `remediation_research_ledger.json` (per-record outcome with the adapter's current missing items).

## Outcome
| Outcome | Records | Meaning |
|---|---:|---|
| RESOLVED_RULE_DEFECT | 3 | the text only prohibits the action; the negation-aware rule no longer flags it |
| PARTIAL_EVIDENCE_ADDED_STILL_BLOCKED | 4 | official PostgreSQL 16 pages read; stated fields added with verbatim quotes; rollback (and in places permission/verification) still not stated by the vendor |
| MANUAL_REVIEW_REQUIRED | 5 | cisco.com refuses automated retrieval; not bypassed |
| BLOCKED | 16 | cited source scanned; no explicit rollback or post-action verification found; **not researched further this round** (see below) |
No record became eligible through this research. The only eligible class B record is `cisco_asa:official_message_id:113005`.

## What the PostgreSQL pages did and did not state
| Record | Added as `stated` (verbatim quote) | `unverified` (composed) | `not_stated` (reason recorded) | Still missing for eligibility |
|---|---|---|---|---|
| xid wraparound | monitoring query `SELECT datname, age(datfrozenxid) FROM pg_database;`; replica may need rebuilding if a slot is dropped; VACUUM "should be performed by a superuser" | re-run the query and confirm messages stop | rollback; approval | recovery verification (unverified), rollback |
| max_connections | "can only be set at server start" (impact) | `SHOW max_connections;` after restart | rollback; permission; approval | recovery verification, rollback, permission |
| standby recovery conflict | `pg_stat_database_conflicts` shows cancels and reasons; hot_standby_feedback delays cleanup, table bloat | compare conflict counters over time | rollback; permission | recovery verification, rollback, permission |
| administrator shutdown | `pg_ctl status` checks whether the server is running; documented output `server is running (PID: …)` | — | rollback; permission; approval | rollback, permission |
Human approval for destructive actions is reported from the EIMS policy constant, not from any vendor page.

## Why the other 16 non-Cisco records were not finished
Reading and curating each Veeam, Microsoft and Fortinet page for rollback/verification is per-record manual work. The keyword scan for those pages returned generic sentences (for example Hyper-V: "Back up and, if needed, delete or rename the .vmcx and .vmrs files." is a backup step with no rollback or check). Nothing was adopted without a quote that applies to the specific action, and nothing was inferred. They stay BLOCKED with the missing items listed per record; continuing is a research task for a person (or a further research pass) with the vendor pages open.

## Rules kept
No bypass of cisco.com; no commands or rollback written from memory; nothing made eligible by generic text; every added `stated` field is bound to the record content hash and was re-verified against the live page.
