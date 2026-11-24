"""Add structured review evidence to the append-only knowledge decision history.

Revision ID: b2d5f8c0e301
Revises: a1c4e7b9d201
Create Date: 2026-11-19

Additive and nullable. ADD COLUMN does not fire the row-level append-only
UPDATE/DELETE trigger, and existing events remain untouched.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b2d5f8c0e301"
down_revision = "a1c4e7b9d201"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_review_event",
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_review_event", "evidence")
