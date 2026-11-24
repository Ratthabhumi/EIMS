# Final blockers (2026-11-22)

Split by who or what is needed. Nothing below can be removed by more engineering effort alone.

## Needs a human reviewer (cannot be done by AI)
1. Source verification, technical/diagnostic validation, independent review and approval for every record (0 of 911 done). The decision API and gates exist; no one has used them.
2. For the 3 eligible class B records (ASA 106024, ASA 113005, Veeam replica snapshot chain): read the cited pages, confirm the remediation, risk, rollback and recovery-verification text, decide.
3. The 6 Windows records whose cited page does not name the Event ID (1026, 4000, 4015, 17, 1530, 5011): is the citation wrong?
4. The 47 Windows records with product-level applicability only and the 11 with a page-scope sentence only: accept, or find an OS/build source.
5. Cisco pages (5 records) that refuse automated retrieval: read manually.
6. Risk wording for the 6 candidates whose risk field says only "Not stated".
7. Reviewer roster and any scope-specific authority (who may approve PostgreSQL, Fortinet, Veeam, Windows records).

## Needs evidence that does not exist here
8. A FortiGate (or recorded real `get system ha status` output) for the 2 HA state records; see `fortigate_ha_capture_checklist.md`.
9. Vendor statements of rollback and post-action verification for the 25 destructive-remediation candidates (`remediation_research_ledger.json`: 20 blocked after scanning the cited pages, 5 need manual reading, 3 resolved as prohibition-only). Until a source states them, these records stay BLOCKED and must not be offered as remediation workflows.
10. A direct official source for the 42 Windows records without one.

## Needs an owner decision
11. Whether to add `rollback_steps`, `verification_steps`, `required_permission`, `human_approval_required` as separate catalog fields (additive, loader-validated) so the missing items can be recorded and shown.
12. Whether to build a catalog → `KnowledgeEntry` *proposal draft* path (requires choosing a `history_id`/case policy, a risk level and a 64-character `product_version`), or to keep `KnowledgeEntry` for human cases only.
13. Whether to render `operationalGuidance` in the dashboard (the API returns it; no UI change was made or needed for the data flow).
14. Whether to add an `account_kind` column (migration) so automation accounts are distinguishable at the database level.
15. Windows operational-context approval track (today the governance rule allows Windows context to reach `candidate` only).
16. Table-level versus per-row review for the 312 parser-mapped references.

## Not done in this round (stated)
* No migration was created or applied; no operational database was touched.
* Frontend build/typecheck was not run: no frontend or API-route frontend code changed.
* Production readiness (Gate E) is not claimed.
