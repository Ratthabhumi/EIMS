"""Add Incident Core v1 tables and analysis_history asset identity.

Revision ID: b8d3f5c1a720
Revises: a4b7c9d2e601
Create Date: 2026-11-16

Additive only:
- incidents / incident_evidence reference source records; no payload copies.
- analysis_history.asset_id is a nullable identity link. It is NOT backfilled.

Downgrade is therefore safe but restricted: dropping analysis_history.asset_id
discards explicitly recorded identity links (never inferred data). Dropping the
incident tables discards incident correlation state. Take a backup and obtain
approval before downgrading a database that carries real incident history.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b8d3f5c1a720"
down_revision = "a4b7c9d2e601"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------- identity
    op.add_column(
        "analysis_history",
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_analysis_history_asset_id",
        "analysis_history",
        "infrastructure_assets",
        ["asset_id"],
        ["asset_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_analysis_history_asset_id",
        "analysis_history",
        ["asset_id"],
        unique=False,
    )

    # ---------------------------------------------------------------- incidents
    op.create_table(
        "incidents",
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("confidence", sa.String(length=16), nullable=False, server_default="none"),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("dedupe_key", sa.String(length=128), nullable=False),
        sa.Column("root_cause_state", sa.String(length=24), nullable=False, server_default="unknown"),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('open', 'triage', 'investigating', 'resolved', 'closed')",
            name="ck_incident_status_valid",
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'low', 'medium', 'high', 'critical')",
            name="ck_incident_severity_valid",
        ),
        sa.CheckConstraint(
            "confidence IN ('strong', 'medium', 'weak', 'none')",
            name="ck_incident_confidence_valid",
        ),
        sa.CheckConstraint(
            "root_cause_state IN ('unknown', 'hypothesis', 'confirmed')",
            name="ck_incident_root_cause_state_valid",
        ),
        sa.CheckConstraint("last_seen >= first_seen", name="ck_incident_seen_window_ordered"),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["infrastructure_assets.asset_id"],
            name="fk_incidents_asset_id", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("incident_id", name="pk_incidents"),
        sa.UniqueConstraint("dedupe_key", name="uq_incidents_dedupe_key"),
        comment="Correlated incidents; evidence is referenced, not copied.",
    )
    op.create_index("ix_incidents_asset_id", "incidents", ["asset_id"], unique=False)
    op.create_index(
        "ix_incidents_status_last_seen", "incidents", ["status", "last_seen"], unique=False
    )
    op.create_index(
        "ix_incidents_severity_last_seen", "incidents", ["severity", "last_seen"], unique=False
    )

    # ------------------------------------------------------------- evidence refs
    op.create_table(
        "incident_evidence",
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("source_event_key", sa.String(length=160), nullable=True),
        sa.Column("evidence_digest", sa.String(length=64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("added_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "source_type IN ('analysis', 'winlog', 'telemetry', 'audit')",
            name="ck_incident_evidence_source_type_valid",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.incident_id"],
            name="fk_incident_evidence_incident_id", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("evidence_id", name="pk_incident_evidence"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_incident_evidence_source"),
        comment="Reference-only incident evidence; no copied source payloads.",
    )
    op.create_index(
        "ix_incident_evidence_incident_id", "incident_evidence", ["incident_id"], unique=False
    )
    op.create_index(
        "ix_incident_evidence_observed_at", "incident_evidence", ["observed_at"], unique=False
    )


def downgrade() -> None:
    # Destructive by nature; see the module docstring for the data-loss warning.
    op.drop_index("ix_incident_evidence_observed_at", table_name="incident_evidence")
    op.drop_index("ix_incident_evidence_incident_id", table_name="incident_evidence")
    op.drop_table("incident_evidence")

    op.drop_index("ix_incidents_severity_last_seen", table_name="incidents")
    op.drop_index("ix_incidents_status_last_seen", table_name="incidents")
    op.drop_index("ix_incidents_asset_id", table_name="incidents")
    op.drop_table("incidents")

    op.drop_index("ix_analysis_history_asset_id", table_name="analysis_history")
    op.drop_constraint("fk_analysis_history_asset_id", "analysis_history", type_="foreignkey")
    op.drop_column("analysis_history", "asset_id")
