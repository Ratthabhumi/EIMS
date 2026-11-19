"""Add append-only outcome feedback for knowledge reuse.

Revision ID: d2f6b8c1e305
Revises: d1e5a7c9b204
Create Date: 2026-11-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2f6b8c1e305"
down_revision: str | None = "d1e5a7c9b204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("knowledge_entry_id", sa.Integer(), nullable=False),
        sa.Column("history_id", sa.Integer(), nullable=False),
        sa.Column("history_hash", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("reported_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "outcome IN ('resolved', 'partially_resolved', 'not_resolved', 'not_attempted')",
            name="ck_knowledge_usage_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_entry_id"], ["knowledge_entries.id"],
            name="fk_knowledge_usage_knowledge_entry_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["history_id"], ["analysis_history.id"],
            name="fk_knowledge_usage_history_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_usage"),
        sa.UniqueConstraint(
            "knowledge_entry_id", "history_id", "reported_by",
            name="uq_knowledge_usage_entry_history_reporter",
        ),
    )
    op.create_index(
        "ix_knowledge_usage_entry_created",
        "knowledge_usage",
        ["knowledge_entry_id", sa.text("created_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_usage_entry_created", table_name="knowledge_usage")
    op.drop_table("knowledge_usage")
