"""Add auditable Knowledge revalidation lifecycle.

Revision ID: e5a7c9d2f416
Revises: d2f6b8c1e305
Create Date: 2026-11-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5a7c9d2f416"
down_revision: str | None = "d2f6b8c1e305"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_entries",
        sa.Column("lifecycle_state", sa.String(length=24), nullable=False, server_default="active"),
    )
    op.add_column(
        "knowledge_entries",
        sa.Column("lifecycle_reason", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "knowledge_entries",
        sa.Column("lifecycle_updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.add_column(
        "knowledge_entries",
        sa.Column("superseded_by_id", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_knowledge_entries_lifecycle_state",
        "knowledge_entries",
        "lifecycle_state IN ('active', 'revalidation_required', 'superseded', 'withdrawn')",
    )
    op.create_foreign_key(
        "fk_knowledge_entries_superseded_by_id",
        "knowledge_entries",
        "knowledge_entries",
        ["superseded_by_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_knowledge_entries_lifecycle_state",
        "knowledge_entries",
        ["lifecycle_state", "status", "source_family", "diagnostic_identity"],
    )
    op.create_table(
        "knowledge_lifecycle_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("knowledge_entry_id", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.String(length=24), nullable=True),
        sa.Column("to_state", sa.String(length=24), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("changed_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "to_state IN ('active', 'revalidation_required', 'superseded', 'withdrawn')",
            name="ck_knowledge_lifecycle_events_to_state",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_entry_id"], ["knowledge_entries.id"],
            name="fk_knowledge_lifecycle_events_entry_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_knowledge_lifecycle_events_entry_created",
        "knowledge_lifecycle_events",
        ["knowledge_entry_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_lifecycle_events_entry_created", table_name="knowledge_lifecycle_events")
    op.drop_table("knowledge_lifecycle_events")
    op.drop_index("ix_knowledge_entries_lifecycle_state", table_name="knowledge_entries")
    op.drop_constraint("fk_knowledge_entries_superseded_by_id", "knowledge_entries", type_="foreignkey")
    op.drop_constraint("ck_knowledge_entries_lifecycle_state", "knowledge_entries", type_="check")
    op.drop_column("knowledge_entries", "superseded_by_id")
    op.drop_column("knowledge_entries", "lifecycle_updated_at")
    op.drop_column("knowledge_entries", "lifecycle_reason")
    op.drop_column("knowledge_entries", "lifecycle_state")
