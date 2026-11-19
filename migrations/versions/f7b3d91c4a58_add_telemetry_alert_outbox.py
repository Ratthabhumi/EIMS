"""Add transactional telemetry alert outbox.

Revision ID: f7b3d91c4a58
Revises: e4a9c8b12d77
Create Date: 2026-11-14 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f7b3d91c4a58"
down_revision: Union[str, None] = "e4a9c8b12d77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "telemetry_alert_outbox"
PENDING_INDEX = "idx_telemetry_alert_outbox_pending"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("alert_id", name="pk_telemetry_alert_outbox"),
    )
    op.create_index(PENDING_INDEX, TABLE, ["created_at"], unique=False,
                    postgresql_where=sa.text("published_at IS NULL"))


def downgrade() -> None:
    op.drop_index(PENDING_INDEX, table_name=TABLE)
    op.drop_table(TABLE)
