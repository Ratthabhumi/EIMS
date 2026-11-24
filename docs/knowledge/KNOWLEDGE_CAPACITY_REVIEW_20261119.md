# Knowledge governance capacity review — 2026-11-19 (milestone 5, part H)

Method: scratch database `eims_capacity` (+ `eims_capacity_restore`) inside the disposable container `eims-knowledge-b-pg-20261119` (pgvector/pg16). Schema and append-only triggers created from the real models and migration DDL. Synthetic load only; the operational DB was not touched.

## Workload actually in use
- Catalog is fixed at 163 records (141 context, 22 candidates); the overlay is **sparse**, so `knowledge_review` holds at most one row per reviewed record.
- Event growth is human-paced: one row per reviewed state change. Even 100 events per record would be ~16,000 rows (~16 MB at the measured row size). 1,000,000 events is roughly 60× beyond any plausible near-term volume and was used as a stress case.

## Measured at 2,000 overlay rows and 1,000,000 events (events spread over 2,000 records, ~500 each)
| Item | Result |
|---|---|
| `knowledge_review_event` heap | 977 MB (~1 KB/row with ~700 B JSONB evidence) |
| Indexes | pkey 37 MB, `(catalog_id, created_at)` 94 MB, `(catalog_id)` 10 MB |
| `knowledge_review` total | 632 kB |
| `history(catalog_id)` (500 rows, cold) | 18 ms (bitmap scan + sort); typical per-record volume is tens of rows |
| `summary()` / `_rows()` full overlay read (2,000 rows) | 0.5 ms |
| `retrieve()` single row by primary key | 0.08 ms |
| stale filter (`review_required`) | 0.16 ms, index-only scan |
| Approval-gate lookup (latest validated event) | 0.7 ms |

## Findings and decisions
1. **No new index is justified.** Every real query shape is index-served or bounded by the 163-record catalog.
2. **Redundant index noted, left in place.** `ix_knowledge_review_event_catalog_id` is a prefix of `ix_knowledge_review_event_catalog_time`; the planner prefers the smaller one. Removing it would save ~10 MB per million events and needs a migration — not worth the churn now.
3. **`history()` has no pagination/limit.** Fine at governance volumes (18 ms for 500 rows). If a route exposing it is added, give it a `limit` and keyset on `(created_at, event_id)`. Not implemented: no such route exists today.
4. **No partitioning, no deletion.** Decision history is audit evidence and is protected by append-only triggers (UPDATE/DELETE/TRUNCATE are rejected), so row deletion is not an available retention mechanism by design. Retain indefinitely; revisit only past ~10M rows, and then via DDL (partitioning/detach) rather than DELETE.
5. **Metadata vs migration defaults.** The models use Python-side defaults, while the migration adds server defaults. Raw-SQL inserts into a `create_all` schema must supply `review_required`, timestamps etc. (hit while loading data). Not a runtime issue for the real migration path.

## Backup and recovery drill (full 1M-event data set)
- `pg_dump -Fc`: 34 s, **73 MB** dump (≈15× smaller than the 1.1 GB on-disk size).
- `pg_restore` into a new database: 92 s.
- Verified after restore: 2,000 overlay rows and 1,000,000 events (counts equal), both append-only triggers present, and a `DELETE` is still rejected (`knowledge_review_event is append-only (attempted DELETE)`). COPY-based restore is not blocked by the triggers.
- Not tested: point-in-time recovery/WAL archiving, the operational backup schedule, off-host copy, cross-version restore. RPO/RTO targets are an owner decision; the governance tables simply need to be inside whatever backup the operational PostgreSQL already has.

## Cleanup note
`eims_capacity` and `eims_capacity_restore` (~1.1 GB each) remain in the disposable container. Nothing was dropped. Dropping those two scratch databases, or removing the container, is safe for you to do whenever you like.
