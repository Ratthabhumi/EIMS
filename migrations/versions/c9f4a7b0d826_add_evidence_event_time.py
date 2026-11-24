"""Separate event time from ingestion time on incident evidence.

Revision ID: c9f4a7b0d826
Revises: b8e3f6a9c715
Create Date: 2026-11-20

Additive. ``incident_evidence.created_at`` is the ingestion time. ``event_time`` is when the event occurred, only when
it was parsed from a source field with known semantics; ``time_basis`` / ``time_confidence`` say where it came from and
how far it can be trusted; ``time_original`` keeps the text as received. Existing rows keep ``observed_at`` untouched and
are marked ``unrecorded_legacy`` / ``missing``: no event time is fabricated for history, so legacy evidence is never
used as proof that two events were close together.
"""
from alembic import op
import sqlalchemy as sa

revision = "c9f4a7b0d826"
down_revision = "b8e3f6a9c715"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("incident_evidence", sa.Column("event_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column("incident_evidence", sa.Column(
        "time_basis", sa.String(48), nullable=False, server_default="unrecorded_legacy"))
    op.add_column("incident_evidence", sa.Column(
        "time_confidence", sa.String(16), nullable=False, server_default="missing"))
    op.add_column("incident_evidence", sa.Column("time_original", sa.String(200), nullable=True))
    op.create_check_constraint(
        "ck_incident_evidence_time_confidence", "incident_evidence",
        "time_confidence IN ('exact', 'asserted', 'ambiguous', 'missing')")
    op.create_check_constraint(
        "ck_incident_evidence_trusted_time_has_value", "incident_evidence",
        "time_confidence NOT IN ('exact', 'asserted') OR event_time IS NOT NULL")
    op.create_index("ix_incident_evidence_event_time", "incident_evidence", ["event_time"])


def downgrade() -> None:
    op.drop_index("ix_incident_evidence_event_time", table_name="incident_evidence")
    op.drop_constraint("ck_incident_evidence_trusted_time_has_value", "incident_evidence", type_="check")
    op.drop_constraint("ck_incident_evidence_time_confidence", "incident_evidence", type_="check")
    op.drop_column("incident_evidence", "time_original")
    op.drop_column("incident_evidence", "time_confidence")
    op.drop_column("incident_evidence", "time_basis")
    op.drop_column("incident_evidence", "event_time")
