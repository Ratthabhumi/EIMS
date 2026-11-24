"""Add knowledge governance overlay and append-only decision history.

Revision ID: a1c4e7b9d201
Revises: f7a1c3d9e502
Create Date: 2026-11-19

Content stays in the JSON catalogs; this migration adds governance state only.
The event table is append-only at the database level, mirroring the
``incident_verification`` protection pattern.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a1c4e7b9d201"
down_revision = "f7a1c3d9e502"
branch_labels = None
depends_on = None

LIFECYCLE_STATES = (
    "candidate",
    "source_verified",
    "validated",
    "approved",
    "rejected",
    "deprecated",
    "superseded",
)

APPEND_ONLY_FUNCTION_DDL = """
CREATE OR REPLACE FUNCTION knowledge_review_event_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'knowledge_review_event is append-only (attempted %)', TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql
"""

APPEND_ONLY_TRIGGER_DDL = """
CREATE TRIGGER trg_knowledge_review_event_append_only
BEFORE UPDATE OR DELETE ON knowledge_review_event
FOR EACH ROW EXECUTE FUNCTION knowledge_review_event_append_only()
"""

APPEND_ONLY_TRUNCATE_DDL = """
CREATE TRIGGER trg_knowledge_review_event_append_only_truncate
BEFORE TRUNCATE ON knowledge_review_event
FOR EACH STATEMENT EXECUTE FUNCTION knowledge_review_event_append_only()
"""


def upgrade() -> None:
    states = ", ".join(f"'{s}'" for s in LIFECYCLE_STATES)

    op.create_table(
        "knowledge_review",
        sa.Column("catalog_id", sa.String(length=160), nullable=False),
        sa.Column("catalog_source", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=24), nullable=False,
                  server_default="candidate"),
        sa.Column("product_version_scope", sa.String(length=255), nullable=True),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("concurrency_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("supersedes_catalog_id", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(f"lifecycle_status IN ({states})", name="ck_knowledge_review_lifecycle_valid"),
        sa.CheckConstraint("revision >= 1", name="ck_knowledge_review_revision_positive"),
        sa.PrimaryKeyConstraint("catalog_id", name="pk_knowledge_review"),
        comment="Sparse governance state; content stays in the JSON catalogs.",
    )
    op.create_index("ix_knowledge_review_lifecycle", "knowledge_review", ["lifecycle_status"])
    op.create_index("ix_knowledge_review_review_required", "knowledge_review", ["review_required"])

    op.create_table(
        "knowledge_review_event",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("catalog_id", sa.String(length=160), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(f"to_status IN ({states})", name="ck_knowledge_review_event_to_status_valid"),
        sa.PrimaryKeyConstraint("event_id", name="pk_knowledge_review_event"),
        comment="Append-only knowledge decisions; UPDATE/DELETE blocked.",
    )
    op.create_index("ix_knowledge_review_event_catalog_id", "knowledge_review_event", ["catalog_id"])
    op.create_index(
        "ix_knowledge_review_event_catalog_time",
        "knowledge_review_event",
        ["catalog_id", "created_at"],
    )

    op.execute(APPEND_ONLY_FUNCTION_DDL)
    op.execute(APPEND_ONLY_TRIGGER_DDL)
    op.execute(APPEND_ONLY_TRUNCATE_DDL)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_knowledge_review_event_append_only_truncate ON knowledge_review_event")
    op.execute("DROP TRIGGER IF EXISTS trg_knowledge_review_event_append_only ON knowledge_review_event")
    op.execute("DROP FUNCTION IF EXISTS knowledge_review_event_append_only()")
    op.drop_index("ix_knowledge_review_event_catalog_time", table_name="knowledge_review_event")
    op.drop_index("ix_knowledge_review_event_catalog_id", table_name="knowledge_review_event")
    op.drop_table("knowledge_review_event")
    op.drop_index("ix_knowledge_review_review_required", table_name="knowledge_review")
    op.drop_index("ix_knowledge_review_lifecycle", table_name="knowledge_review")
    op.drop_table("knowledge_review")
