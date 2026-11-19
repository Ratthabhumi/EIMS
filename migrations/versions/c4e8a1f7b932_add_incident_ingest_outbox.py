"""Add incident_ingest_outbox (Incident Core v1.1 event-to-incident ingestion).

Revision ID: c4e8a1f7b932
Revises: b8d3f5c1a720
Create Date: 2026-11-16

Additive only. Reference-only transactional outbox written in the same transaction as the
source row (analysis_history / windows_event_logs). No existing table or index is altered.
asset_id is nullable (analyzer submit/bundle never resolve an asset) and ON DELETE RESTRICT.

Downgrade drops only this table; undelivered intents in the outbox are discarded with it.
Take a backup and obtain approval before downgrading a database with pending outbox rows.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c4e8a1f7b932"
down_revision = "b8d3f5c1a720"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incident_ingest_outbox",
        sa.Column("outbox_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("source_event_key", sa.String(length=160), nullable=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("source_type IN ('analysis', 'winlog')",
                           name="ck_incident_ingest_outbox_source_type"),
        sa.CheckConstraint("octet_length(provenance::text) <= 1024",
                           name="ck_incident_ingest_outbox_provenance_bounded"),
        sa.ForeignKeyConstraint(["asset_id"], ["infrastructure_assets.asset_id"],
                                name="fk_incident_ingest_outbox_asset_id", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("outbox_id", name="pk_incident_ingest_outbox"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_incident_ingest_outbox_source"),
        comment="Reference-only transactional outbox feeding Incident Core ingestion.",
    )
    op.create_index(
        "idx_incident_ingest_outbox_pending", "incident_ingest_outbox", ["created_at"],
        unique=False, postgresql_where=sa.text("published_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_incident_ingest_outbox_pending", table_name="incident_ingest_outbox",
                  postgresql_where=sa.text("published_at IS NULL"))
    op.drop_table("incident_ingest_outbox")
