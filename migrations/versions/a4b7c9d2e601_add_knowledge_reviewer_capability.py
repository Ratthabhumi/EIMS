"""Additive Knowledge Reviewer capability to users.

Revision ID: a4b7c9d2e601
Revises: f3c8a1d6b902
Create Date: 2026-11-15
"""
from alembic import op
import sqlalchemy as sa

revision = "a4b7c9d2e601"
down_revision = "f3c8a1d6b902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("knowledge_reviewer", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "knowledge_reviewer")
