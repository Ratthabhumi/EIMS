# EIMS V12 — A13 Vector Dimension Reproduction Plan (not executed)

Date: 2026-11-18 (Asia/Bangkok)
Finding: EIMS-F6 — `ALTER COLUMN embedding TYPE vector(384) USING embedding::vector(384)` from `vector(768)`.

## 1. Static analysis

| Item | Finding |
|---|---|
| Migration | `migrations/versions/8a2b4d6f9c1e_align_ai_knowledge_embedding_dimension.py:19-36` |
| Up | `vector(768) → vector(384)` with a direct dimension cast |
| Down | `vector(384) → vector(768)` with a direct dimension cast |
| pgvector behaviour | a dimension-changing cast fails on non-null rows; it succeeds only on an empty table or all-NULL column |
| Deployment state | the operational DB is at `a3d6f1e8c295`, which is **after** `8a2b4d6f9c1e` in the chain, so this migration has already been applied to that database |
| Consequence | the migration can only be evaluated against a database that has data at the moment of the cast, or by inspecting whether the column was empty |

This is a **conditional defect**: it is safe on an empty table and unsafe on populated data. It cannot be classified as FAIL without a populated reproduction.

## 2. Open contract question

Two different facts must be separated:

1. what dimension the embedding model produces (its contract), and
2. what dimension the column stores.

A migration from 768 to 384 is only correct if the model contract changed to 384 **and** an explicit projection/down-projection is defined. Arbitrary truncation is not a valid reduction. The model contract is **UNVERIFIED** in this campaign; no embedding provider call was made.

## 3. Disposable reproduction plan (requires separate approval)

1. New disposable PostgreSQL with the `pgvector` extension; **new** volume, new network, new database `eims_vec_repro`, new schema.
2. Seed synthetic `ai_knowledge` rows with explicit 768-dimension vectors.
3. Run the migration in isolation and capture the exact error.
4. Repeat on an empty table to demonstrate the conditional behaviour.
5. Insert a 384-dimension vector after migration; insert an invalid dimension; run a similarity query.
6. Record: server version, extension version, SQL, error text, timings.

## 4. Prohibitions

- No operational database, no customer data, no existing volume.
- No container start in this campaign.
- No arbitrary truncation as a "fix".

## 5. Status

`DESIGN_COMPLETE` · reproduction `NOT RUN` · service start requires separate approval.
