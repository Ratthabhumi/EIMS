"""Add applicability and safe-remediation metadata to reviewed knowledge.

Revision ID: d1e5a7c9b204
Revises: c9a4e7b2d610
Create Date: 2026-11-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1e5a7c9b204"
down_revision: str | None = "c9a4e7b2d610"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("knowledge_entries", sa.Column("product_name", sa.String(length=128), nullable=True))
    op.add_column("knowledge_entries", sa.Column("product_version", sa.String(length=64), nullable=True))
    op.add_column("knowledge_entries", sa.Column("environment", sa.String(length=64), nullable=True))
    op.add_column("knowledge_entries", sa.Column("prerequisites", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")))
    op.add_column("knowledge_entries", sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="medium"))
    op.add_column("knowledge_entries", sa.Column("validation_steps", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")))
    op.add_column("knowledge_entries", sa.Column("rollback_steps", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")))
    op.create_check_constraint(
        "ck_knowledge_entries_risk_level",
        "knowledge_entries",
        "risk_level IN ('low', 'medium', 'high', 'critical')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_knowledge_entries_risk_level", "knowledge_entries", type_="check")
    op.drop_column("knowledge_entries", "rollback_steps")
    op.drop_column("knowledge_entries", "validation_steps")
    op.drop_column("knowledge_entries", "risk_level")
    op.drop_column("knowledge_entries", "prerequisites")
    op.drop_column("knowledge_entries", "environment")
    op.drop_column("knowledge_entries", "product_version")
    op.drop_column("knowledge_entries", "product_name")
