"""Add durable source-event idempotency keys to telemetry tables.

Revision ID: e4a9c8b12d77
Revises: e1a202610250
Create Date: 2026-11-13 20:00:00.000000

The unique indexes are built/dropped with CONCURRENTLY (no write lock on the hot
telemetry tables). CONCURRENTLY cannot run inside a transaction, so those steps run in
an Alembic autocommit block. Column adds/drops stay transactional. If an index build is
interrupted PostgreSQL leaves an INVALID index; the upgrade drops any such leftover
before rebuilding. The column add commits first (ADD COLUMN IF NOT EXISTS), so re-running
after an index-build failure is safe: the column step is a no-op and any INVALID index is
dropped then rebuilt. The column is nullable and the index is a plain unique index, so NULL
keys never conflict (PostgreSQL NULLs are distinct).
"""
from typing import Sequence, Union
from alembic import op

revision: str = "e4a9c8b12d77"
down_revision: Union[str, None] = "e1a202610250"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = (
    ("telemetry_metrics", "uq_telemetry_metrics_source_event_key"),
    ("windows_event_logs", "uq_windows_event_logs_source_event_key"),
)


def upgrade() -> None:
    for table, _ in _INDEXES:
        # IF NOT EXISTS: the autocommit block below commits this DDL before the index build, so
        # a rerun after an interrupted build must tolerate the already-committed column.
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS source_event_key VARCHAR(160)")
    with op.get_context().autocommit_block():
        for table, index in _INDEXES:
            # Remove an INVALID leftover from an interrupted earlier attempt, then build.
            op.drop_index(index, table_name=table, postgresql_concurrently=True, if_exists=True)
            op.create_index(index, table, ["source_event_key"], unique=True,
                            postgresql_concurrently=True)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for table, index in reversed(_INDEXES):
            op.drop_index(index, table_name=table, postgresql_concurrently=True, if_exists=True)
    for table, _ in reversed(_INDEXES):
        op.drop_column(table, "source_event_key")
