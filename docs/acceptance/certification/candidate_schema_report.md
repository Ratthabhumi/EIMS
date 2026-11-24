# Candidate schema report (2026-11-22)

## Decision
Add **one** optional block, `operational_fields`, to candidate records instead of eight new top-level columns. Existing fields that already do the same job are reused: `verification_steps` (recovery verification), `remediation`, `operational_risk`, `limitations`, `official_sources`, `version_scope`. The block carries the fields the catalogs lacked, each with an explicit state and provenance. The governance overlay is unchanged (it stores state, hash and events, not content), so no migration was needed.

## Fields (`operational_fields`, all optional, backward compatible)
`required_permission`, `human_approval_required`, `rollback_steps`, `verification_steps` (overrides the legacy list when stated), `recovery_evidence`, `recovery_success_criteria`, `operational_impact`, `destructive_risk`.

Each entry is `{state, items[], ...}` with three states:
| State | Rule enforced by `validate_operational_fields` (also run by the catalog loader) |
|---|---|
| `stated` | non-empty, non-placeholder `items` **and** `source.url` (https), a verbatim `source.quote`, and a `source.retrieved` date |
| `unverified` | non-empty `items` and a `basis` saying where it comes from; never counted as stated, never merged into active guidance |
| `not_stated` | no items and a `reason` (what was searched); empty strings and "Not stated…" placeholders are rejected as evidence |
Because the block is part of the record, it is covered by the record's content hash: changing it invalidates evidence and any decision bound to the old hash.

## Rules that follow
* A record with a destructive remediation is complete only if rollback **and** required permission are `stated`; human approval is derived from an explicit EIMS policy (`remediation_safety.DESTRUCTIVE_ACTION_POLICY`), labelled `origin: eims_policy`, never attributed to a vendor.
* Nothing in the block changes `review_status` (loader still requires PENDING_HUMAN_REVIEW) or lifecycle.
* Eligibility effect, stated plainly: tightening the contract moved the class B eligible count from **3 to 1** (two records have destructive steps without a stated permission). That is the contract working, not a regression.

## Data actually added
Four PostgreSQL 16 candidates (`remediation_fields_curated.json`, applied by `tools/apply_remediation_fields.py`): every `stated` quote was re-checked verbatim against the live official page before writing (the tool refuses otherwise): xid-wraparound (recovery evidence query, destructive risk, required permission), max_connections (operational impact), standby recovery conflict (recovery evidence, operational impact), administrator shutdown (verification via `pg_ctl status` and its documented output). Composed items are `unverified`; rollback and approval are `not_stated` with reasons. No instruction was written from memory.

## Tests
`tests/test_catalog_adapter.py`: nine rejection cases, valid/unverified behaviour, loader rejection, supplement merge rules, policy label, curated file validity and presence in the catalog.
