"""Add a user-scoped chronological index for Analyzer history.

Revision ID: b7c2e9a4f601
Revises: a3d6f1e8c295
Create Date: 2026-11-15

The index supports owner-scoped newest-first pagination and seven-day per-user aggregates.
It is built concurrently so incident writes are not blocked during deployment.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c2e9a4f601"
down_revision: str | None = "a3d6f1e8c295"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "analysis_history"
INDEX = "ix_analysis_history_username_created_at_id"


def upgrade() -> None:
    with op.get_context().autocommit_block():
        # Drop/rebuild also recovers an INVALID index left by an interrupted CONCURRENTLY build.
        op.drop_index(INDEX, table_name=TABLE, postgresql_concurrently=True, if_exists=True)
        op.create_index(
            INDEX,
            TABLE,
            ["username", sa.text("created_at DESC"), sa.text("id DESC")],
            unique=False,
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(INDEX, table_name=TABLE, postgresql_concurrently=True, if_exists=True)
