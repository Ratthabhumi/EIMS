"""Add the reviewed incident knowledge lifecycle.

Revision ID: c9a4e7b2d610
Revises: b7c2e9a4f601
Create Date: 2026-11-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9a4e7b2d610"
down_revision: str | None = "b7c2e9a4f601"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_history_id", sa.Integer(), nullable=False),
        sa.Column("source_history_hash", sa.String(length=64), nullable=False),
        sa.Column("source_family", sa.String(length=64), nullable=False),
        sa.Column("diagnostic_identity", sa.String(length=256), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("resolution_status", sa.String(length=32), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("solution_steps", sa.JSON(), nullable=False),
        sa.Column("impact", sa.Text(), nullable=False, server_default=""),
        sa.Column("prevention", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence_notes", sa.JSON(), nullable=False),
        sa.Column("references", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("proposed_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_knowledge_entries_status",
        ),
        sa.CheckConstraint(
            "resolution_status IN ('resolved', 'partially_resolved', 'unresolved')",
            name="ck_knowledge_entries_resolution_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_history_id"], ["analysis_history.id"],
            name="fk_knowledge_entries_source_history_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_entries"),
        sa.UniqueConstraint(
            "source_history_id", name="uq_knowledge_entries_source_history_id"
        ),
    )
    op.create_index(
        "ix_knowledge_entries_status",
        "knowledge_entries",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_entries_status_family_identity_reviewed",
        "knowledge_entries",
        ["status", "source_family", "diagnostic_identity", sa.text("reviewed_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_entries_status_family_identity_reviewed",
        table_name="knowledge_entries",
    )
    op.drop_index("ix_knowledge_entries_status", table_name="knowledge_entries")
    op.drop_table("knowledge_entries")
