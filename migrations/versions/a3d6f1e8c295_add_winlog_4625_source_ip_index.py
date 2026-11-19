"""Add partial functional index for the 4625 brute-force window count.

Revision ID: a3d6f1e8c295
Revises: f7b3d91c4a58
Create Date: 2026-11-14 14:00:00.000000

Serves `event_id = 4625 AND evtx_metadata->>'source_network_ip' = :ip AND occurrence_time
BETWEEN ...` (TelemetryStreamConsumer._count_failed_logons). The existing GIN index cannot
satisfy the equality+range combination on a text extraction.

Built/dropped CONCURRENTLY inside an autocommit block (same pattern as e4a9c8b12d77). If a
build is interrupted PostgreSQL leaves an INVALID index; upgrade drops any leftover with the
same name before rebuilding, so re-running is safe. Nothing else is changed by this revision,
so a failed run needs no manual column cleanup.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "a3d6f1e8c295"
down_revision: Union[str, None] = "f7b3d91c4a58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "windows_event_logs"
INDEX = "idx_winlog_4625_src_ip_time"


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(INDEX, table_name=TABLE, postgresql_concurrently=True, if_exists=True)
        op.create_index(
            INDEX, TABLE,
            [sa.text("(evtx_metadata ->> 'source_network_ip')"), "occurrence_time"],
            unique=False, postgresql_concurrently=True,
            postgresql_where=sa.text("event_id = 4625"))


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(INDEX, table_name=TABLE, postgresql_concurrently=True, if_exists=True)
