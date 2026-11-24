# EIMS V12 — A13 Ledger Semantic Correction (record, not a rewrite)

Date: 2026-11-18 (Asia/Bangkok)
Finding: EIMS-F5 — ledger declared head `a3d6f1e8c295`, repository chain head `c4e8a1f7b932`.

## 1. What A13.1 established

| Head | Value | Source |
|---|---|---|
| `repository_head` | **`c4e8a1f7b932`** | chain traversal over `migrations/versions/*.py` (22 revisions, 1 root `1a78de93777d`) |
| `declared_head` | `a3d6f1e8c295` | `EIMS_ACCEPTANCE_LEDGER.md` |
| `deployed_head` | **`a3d6f1e8c295`** | `SELECT version_num FROM alembic_version` on operational `eims_registry` |
| `verified_head` | `a3d6f1e8c295` | read from the deployed database (read-only) |
| `anchor_head` | none | no external anchor exists |

## 2. Corrected interpretation

This is a **semantic/documentation mismatch**, not proven corruption and not a stale pointer.

The ledger recorded the revision of the **deployed database**, while readers interpreted it as the **repository** head. Both values are individually correct for their own target. The defect is that the record did not name its target.

The earlier A11/A12 wording ("stale head", "six revisions behind") is superseded by this correction. It described the numeric difference, not the cause.

## 3. Rules for revision claims

Every revision claim must state: **value, source, target, timestamp, verification method**.

| Claim type | Required evidence |
|---|---|
| repository head | chain traversal of the source tree at a recorded commit |
| deployed head | `alembic_version` read from a named database |
| declared head | the document that asserts it, with its date |
| verified head | a read-only query transcript with target identity |
| anchor head | an external receipt; none exists |

## 4. Non-actions

- The historical ledger was **not** edited.
- The operational database was **not** migrated.
- The repository chain was **not** altered.
- No claim of chain integrity PASS is made.

## 5. Deployment implication

A six-revision gap is a **deployment planning fact**, not a defect. Migrating `eims_registry` from `a3d6f1e8c295` to `c4e8a1f7b932` is a separate, approved operation with its own backup and rollback plan. It must not be performed as part of acceptance.

## 6. Status

EIMS-F5: **RESOLVED_AS_SEMANTIC** (documentation corrected). Integrity claim stays **UNVERIFIED** until a verifier and anchor exist.
