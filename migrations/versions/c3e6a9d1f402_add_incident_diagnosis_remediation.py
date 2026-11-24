"""Add incident diagnosis, remediation and append-only workflow events.

Revision ID: c3e6a9d1f402
Revises: b2d5f8c0e301
Create Date: 2026-11-19

Additive: three new tables, nothing existing is altered. Every record stores the
actor identifier AND an explicit ``actor_assurance`` (unattributed /
shared-token / verified-identity) so an audit reader can tell an unproven
open-access actor from a verified reviewer. ``incident_workflow_event`` is
append-only (UPDATE/DELETE/TRUNCATE rejected), mirroring incident_verification.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c3e6a9d1f402"
down_revision = "b2d5f8c0e301"
branch_labels = None
depends_on = None

ASSURANCES = ("unattributed", "shared-token", "verified-identity")
DIAGNOSIS_STATES = ("hypothesis", "confirmed")
REMEDIATION_STATES = ("proposed", "executed")
OUTCOMES = ("succeeded", "failed", "partial", "rolled_back")
CONFIDENCES = ("low", "medium", "high")
RECORD_TYPES = ("diagnosis", "remediation")


def _in(values) -> str:
    return ", ".join(f"'{v}'" for v in values)


APPEND_ONLY_FUNCTION_DDL = """
CREATE OR REPLACE FUNCTION incident_workflow_event_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'incident_workflow_event is append-only (attempted %)', TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql
"""

APPEND_ONLY_TRIGGER_DDL = """
CREATE TRIGGER trg_incident_workflow_event_append_only
BEFORE UPDATE OR DELETE ON incident_workflow_event
FOR EACH ROW EXECUTE FUNCTION incident_workflow_event_append_only()
"""

APPEND_ONLY_TRUNCATE_DDL = """
CREATE TRIGGER trg_incident_workflow_event_append_only_truncate
BEFORE TRUNCATE ON incident_workflow_event
FOR EACH STATEMENT EXECUTE FUNCTION incident_workflow_event_append_only()
"""


def upgrade() -> None:
    op.create_table(
        "incident_diagnosis",
        sa.Column("diagnosis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("remediation_cycle", sa.Integer(), nullable=False),
        sa.Column("hypothesis", sa.String(length=1000), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False, server_default=""),
        sa.Column("stated_confidence", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="hypothesis"),
        sa.Column("supporting_evidence_ids", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("contradicting_evidence_ids", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("knowledge", postgresql.JSONB(), nullable=True),
        sa.Column("analysis_history_id", sa.Integer(), nullable=True),
        sa.Column("proposed_by", sa.String(length=255), nullable=False),
        sa.Column("proposed_assurance", sa.String(length=24), nullable=False),
        sa.Column("record_digest", sa.String(length=64), nullable=False),
        sa.Column("confirmed_by", sa.String(length=255), nullable=True),
        sa.Column("confirmed_assurance", sa.String(length=24), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"],
                                name="fk_incident_diagnosis_incident", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("diagnosis_id", name="pk_incident_diagnosis"),
        sa.CheckConstraint(f"status IN ({_in(DIAGNOSIS_STATES)})", name="ck_incident_diagnosis_status"),
        sa.CheckConstraint(f"stated_confidence IN ({_in(CONFIDENCES)})", name="ck_incident_diagnosis_confidence"),
        sa.CheckConstraint(f"proposed_assurance IN ({_in(ASSURANCES)})", name="ck_incident_diagnosis_proposed_assurance"),
        sa.CheckConstraint(
            f"confirmed_assurance IS NULL OR confirmed_assurance = 'verified-identity'",
            name="ck_incident_diagnosis_confirmed_assurance"),
        sa.CheckConstraint(
            "(status = 'confirmed') = COALESCE(confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmed_assurance = 'verified-identity', false)",
            name="ck_incident_diagnosis_confirmation_consistent"),
        sa.CheckConstraint("confirmed_by IS NULL OR confirmed_by <> proposed_by",
                           name="ck_incident_diagnosis_confirmer_not_proposer"),
        comment="Root-cause hypotheses; 'confirmed' requires a verified-identity reviewer.",
    )
    op.create_index("ix_incident_diagnosis_incident", "incident_diagnosis", ["incident_id", "created_at"])
    op.create_index(
        "uq_incident_diagnosis_one_confirmed_per_cycle", "incident_diagnosis",
        ["incident_id", "remediation_cycle"], unique=True,
        postgresql_where=sa.text("status = 'confirmed'"))

    op.create_table(
        "incident_remediation",
        sa.Column("remediation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("diagnosis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("remediation_cycle", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=1000), nullable=False),
        sa.Column("preconditions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("affected_components", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("expected_outcome", sa.Text(), nullable=False, server_default=""),
        sa.Column("risk", sa.Text(), nullable=False),
        sa.Column("impact", sa.Text(), nullable=False, server_default=""),
        sa.Column("rollback_plan", sa.Text(), nullable=False),
        sa.Column("expected_verification_criteria", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="proposed"),
        sa.Column("proposed_by", sa.String(length=255), nullable=False),
        sa.Column("proposed_assurance", sa.String(length=24), nullable=False),
        sa.Column("record_digest", sa.String(length=64), nullable=False),
        sa.Column("executed_by", sa.String(length=255), nullable=True),
        sa.Column("executed_assurance", sa.String(length=24), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_action", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=True),
        sa.Column("outcome_notes", sa.Text(), nullable=True),
        sa.Column("execution_evidence_ids", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"],
                                name="fk_incident_remediation_incident", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["incident_diagnosis.diagnosis_id"],
                                name="fk_incident_remediation_diagnosis", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("remediation_id", name="pk_incident_remediation"),
        sa.CheckConstraint(f"status IN ({_in(REMEDIATION_STATES)})", name="ck_incident_remediation_status"),
        sa.CheckConstraint(f"proposed_assurance IN ({_in(ASSURANCES)})", name="ck_incident_remediation_proposed_assurance"),
        sa.CheckConstraint(
            f"executed_assurance IS NULL OR executed_assurance IN ({_in(ASSURANCES)})",
            name="ck_incident_remediation_executed_assurance"),
        sa.CheckConstraint(
            f"outcome IS NULL OR outcome IN ({_in(OUTCOMES)})", name="ck_incident_remediation_outcome"),
        sa.CheckConstraint(
            "(status = 'executed') = (executed_by IS NOT NULL AND executed_at IS NOT NULL "
            "AND outcome IS NOT NULL AND executed_assurance IS NOT NULL)",
            name="ck_incident_remediation_execution_consistent"),
        comment="Proposed vs executed remediation; never records verification (that is incident_verification).",
    )
    op.create_index("ix_incident_remediation_incident", "incident_remediation", ["incident_id", "created_at"])

    op.create_table(
        "incident_workflow_event",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_type", sa.String(length=16), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("actor_assurance", sa.String(length=24), nullable=False),
        sa.Column("record_digest", sa.String(length=64), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"],
                                name="fk_incident_workflow_event_incident", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("event_id", name="pk_incident_workflow_event"),
        sa.CheckConstraint(f"record_type IN ({_in(RECORD_TYPES)})", name="ck_incident_workflow_event_type"),
        sa.CheckConstraint(f"actor_assurance IN ({_in(ASSURANCES)})", name="ck_incident_workflow_event_assurance"),
        comment="Append-only audit of diagnosis/remediation operations with actor assurance.",
    )
    op.create_index("ix_incident_workflow_event_incident", "incident_workflow_event", ["incident_id", "created_at"])
    op.create_index("ix_incident_workflow_event_record", "incident_workflow_event", ["record_id"])

    op.execute(APPEND_ONLY_FUNCTION_DDL)
    op.execute(APPEND_ONLY_TRIGGER_DDL)
    op.execute(APPEND_ONLY_TRUNCATE_DDL)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_incident_workflow_event_append_only_truncate ON incident_workflow_event")
    op.execute("DROP TRIGGER IF EXISTS trg_incident_workflow_event_append_only ON incident_workflow_event")
    op.execute("DROP FUNCTION IF EXISTS incident_workflow_event_append_only()")
    op.drop_index("ix_incident_workflow_event_record", table_name="incident_workflow_event")
    op.drop_index("ix_incident_workflow_event_incident", table_name="incident_workflow_event")
    op.drop_table("incident_workflow_event")
    op.drop_index("ix_incident_remediation_incident", table_name="incident_remediation")
    op.drop_table("incident_remediation")
    op.drop_index("uq_incident_diagnosis_one_confirmed_per_cycle", table_name="incident_diagnosis")
    op.drop_index("ix_incident_diagnosis_incident", table_name="incident_diagnosis")
    op.drop_table("incident_diagnosis")
