"""Hypothesis rejection/supersession, remediation knowledge link, incident knowledge proposals.

Revision ID: d4f7b0a2c503
Revises: c3e6a9d1f402
Create Date: 2026-11-19

Additive. Diagnosis rows gain two terminal states (rejected, superseded) with
who/why/when; a remediation may reference a canonical catalog record (snapshot
kept on the row); ``incident_knowledge_proposal`` records which existing Knowledge
review entry came from which incident, diagnosis and evidence. No canonical
catalog content is stored here and nothing is promoted automatically.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d4f7b0a2c503"
down_revision = "c3e6a9d1f402"
branch_labels = None
depends_on = None

ASSURANCES = ("unattributed", "shared-token", "verified-identity")


def _in(values) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.drop_constraint("ck_incident_diagnosis_status", "incident_diagnosis", type_="check")
    op.create_check_constraint(
        "ck_incident_diagnosis_status", "incident_diagnosis",
        "status IN ('hypothesis', 'confirmed', 'rejected', 'superseded')")
    op.add_column("incident_diagnosis", sa.Column("closed_by", sa.String(length=255), nullable=True))
    op.add_column("incident_diagnosis", sa.Column("closed_assurance", sa.String(length=24), nullable=True))
    op.add_column("incident_diagnosis", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("incident_diagnosis", sa.Column("closed_reason", sa.Text(), nullable=True))
    op.add_column("incident_diagnosis", sa.Column(
        "superseded_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_incident_diagnosis_superseded_by", "incident_diagnosis", "incident_diagnosis",
        ["superseded_by_id"], ["diagnosis_id"], ondelete="RESTRICT")
    op.create_check_constraint(
        "ck_incident_diagnosis_closure_consistent", "incident_diagnosis",
        "(status IN ('rejected', 'superseded')) = COALESCE(closed_by IS NOT NULL AND closed_at IS NOT NULL "
        "AND closed_reason IS NOT NULL AND closed_assurance IS NOT NULL, false)")
    op.create_check_constraint(
        "ck_incident_diagnosis_closed_fields_only_when_closed", "incident_diagnosis",
        "status IN ('rejected', 'superseded') OR (closed_by IS NULL AND closed_at IS NULL AND closed_reason IS NULL AND closed_assurance IS NULL AND superseded_by_id IS NULL)")
    op.create_check_constraint(
        "ck_incident_diagnosis_confirmed_fields_only_when_confirmed", "incident_diagnosis",
        "status = 'confirmed' OR (confirmed_by IS NULL AND confirmed_at IS NULL AND confirmed_assurance IS NULL)")
    op.create_check_constraint(
        "ck_incident_diagnosis_closed_assurance", "incident_diagnosis",
        f"closed_assurance IS NULL OR closed_assurance IN ({_in(ASSURANCES)})")
    op.create_check_constraint(
        "ck_incident_diagnosis_superseded_link", "incident_diagnosis",
        "(status = 'superseded') = (superseded_by_id IS NOT NULL) AND superseded_by_id IS DISTINCT FROM diagnosis_id")

    op.add_column("incident_remediation", sa.Column("catalog_id", sa.String(length=200), nullable=True))
    op.add_column("incident_remediation", sa.Column("knowledge", postgresql.JSONB(), nullable=True))

    op.create_table(
        "incident_knowledge_proposal",
        sa.Column("proposal_link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("diagnosis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("remediation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("knowledge_entry_id", sa.Integer(), nullable=False),
        sa.Column("remediation_cycle", sa.Integer(), nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("proposed_by", sa.String(length=255), nullable=False),
        sa.Column("proposed_assurance", sa.String(length=24), nullable=False),
        sa.Column("diagnosis_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"],
                                name="fk_incident_knowledge_proposal_incident", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["incident_diagnosis.diagnosis_id"],
                                name="fk_incident_knowledge_proposal_diagnosis", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["remediation_id"], ["incident_remediation.remediation_id"],
                                name="fk_incident_knowledge_proposal_remediation", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["knowledge_entry_id"], ["knowledge_entries.id"],
                                name="fk_incident_knowledge_proposal_entry", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("proposal_link_id", name="pk_incident_knowledge_proposal"),
        sa.UniqueConstraint("knowledge_entry_id", name="uq_incident_knowledge_proposal_entry"),
        sa.CheckConstraint(f"proposed_assurance IN ({_in(ASSURANCES)})",
                           name="ck_incident_knowledge_proposal_assurance"),
        comment="Links an incident to the existing Knowledge review entry it originated; no content copy.",
    )
    op.create_index("ix_incident_knowledge_proposal_incident", "incident_knowledge_proposal",
                    ["incident_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_incident_knowledge_proposal_incident", table_name="incident_knowledge_proposal")
    op.drop_table("incident_knowledge_proposal")
    op.drop_column("incident_remediation", "knowledge")
    op.drop_column("incident_remediation", "catalog_id")
    for name in ("ck_incident_diagnosis_confirmed_fields_only_when_confirmed",
                 "ck_incident_diagnosis_closed_fields_only_when_closed",
                 "ck_incident_diagnosis_superseded_link", "ck_incident_diagnosis_closed_assurance",
                 "ck_incident_diagnosis_closure_consistent"):
        op.drop_constraint(name, "incident_diagnosis", type_="check")
    op.drop_constraint("fk_incident_diagnosis_superseded_by", "incident_diagnosis", type_="foreignkey")
    for column in ("superseded_by_id", "closed_reason", "closed_at", "closed_assurance", "closed_by"):
        op.drop_column("incident_diagnosis", column)
    op.drop_constraint("ck_incident_diagnosis_status", "incident_diagnosis", type_="check")
    op.create_check_constraint(
        "ck_incident_diagnosis_status", "incident_diagnosis", "status IN ('hypothesis', 'confirmed')")
