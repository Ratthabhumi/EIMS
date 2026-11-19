"""Persist vendor source candidates separately from approved incident Knowledge.

Revision ID: f3c8a1d6b902
Revises: e5a7c9d2f416
Create Date: 2026-11-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3c8a1d6b902"
down_revision: str | None = "e5a7c9d2f416"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_source_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_key", sa.String(128), nullable=False),
        sa.Column("vendor", sa.String(128), nullable=False),
        sa.Column("product", sa.String(200), nullable=False),
        sa.Column("version_scope", sa.String(600), nullable=False),
        sa.Column("domain", sa.String(160), nullable=False),
        sa.Column("identity", sa.String(256), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("applicability", sa.Text(), nullable=False),
        sa.Column("prerequisites", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("next_checks", sa.JSON(), nullable=False),
        sa.Column("validation", sa.JSON(), nullable=False),
        sa.Column("rollback", sa.JSON(), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("evidence_status", sa.String(64), nullable=False),
        sa.Column("review_state", sa.String(32), nullable=False, server_default="pending_domain_review"),
        sa.Column("catalog_schema_version", sa.String(32), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("source_payload", sa.JSON(), nullable=False),
        sa.Column("imported_by", sa.String(128), nullable=False, server_default="catalogue-import"),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_by", sa.String(128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "review_state IN ('pending_domain_review', 'verified_reference', 'rejected', 'revalidation_required', 'withdrawn')",
            name="ck_knowledge_source_candidates_review_state",
        ),
        sa.CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_knowledge_source_candidates_risk_level",
        ),
        sa.UniqueConstraint("source_key", name="uq_knowledge_source_candidates_source_key"),
    )
    op.create_index(
        "ix_knowledge_source_candidates_vendor_state",
        "knowledge_source_candidates", ["vendor", "review_state", "product"],
    )
    op.create_index(
        "ix_knowledge_source_candidates_identity",
        "knowledge_source_candidates", ["identity", "vendor"],
    )
    op.create_table(
        "knowledge_source_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_candidate_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("from_state", sa.String(32), nullable=True),
        sa.Column("to_state", sa.String(32), nullable=True),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("changed_by", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["source_candidate_id"], ["knowledge_source_candidates.id"],
            name="fk_knowledge_source_events_candidate_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_knowledge_source_events_candidate_created",
        "knowledge_source_events",
        ["source_candidate_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_source_events_candidate_created", table_name="knowledge_source_events")
    op.drop_table("knowledge_source_events")
    op.drop_index("ix_knowledge_source_candidates_identity", table_name="knowledge_source_candidates")
    op.drop_index("ix_knowledge_source_candidates_vendor_state", table_name="knowledge_source_candidates")
    op.drop_table("knowledge_source_candidates")
