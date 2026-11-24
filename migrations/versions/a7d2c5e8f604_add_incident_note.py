"""Engineer notes on incidents (append-only observations with honest actor provenance).

Revision ID: a7d2c5e8f604
Revises: d4f7b0a2c503
Create Date: 2026-11-20

Additive. ``incident_note`` stores free-text observations. A note is never a diagnosis, remediation, verification or
status change: it has no state fields. Rows are append-only (UPDATE/DELETE/TRUNCATE are rejected by trigger) and carry
the actor and assurance derived server-side from the credential. The unified audit timeline (``incident_workflow_event``)
gains the record type ``note`` so notes appear in the same append-only history.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a7d2c5e8f604"
down_revision = "d4f7b0a2c503"
branch_labels = None
depends_on = None

ASSURANCES = ("unattributed", "shared-token", "verified-identity")

FUNCTION_DDL = """
CREATE OR REPLACE FUNCTION incident_note_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'incident_note is append-only: % is not permitted', TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql
"""
ROW_TRIGGER_DDL = """
CREATE TRIGGER trg_incident_note_append_only
BEFORE UPDATE OR DELETE ON incident_note
FOR EACH ROW EXECUTE FUNCTION incident_note_append_only()
"""
TRUNCATE_TRIGGER_DDL = """
CREATE TRIGGER trg_incident_note_append_only_truncate
BEFORE TRUNCATE ON incident_note
FOR EACH STATEMENT EXECUTE FUNCTION incident_note_append_only()
"""


def _in(values) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.create_table(
        "incident_note",
        sa.Column("note_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("incidents.incident_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("actor_assurance", sa.String(24), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("char_length(btrim(body)) BETWEEN 1 AND 4000", name="ck_incident_note_body_length"),
        sa.CheckConstraint(f"actor_assurance IN ({_in(ASSURANCES)})", name="ck_incident_note_assurance"),
        comment="Append-only engineer observations; never a diagnosis, remediation, verification or status change.",
    )
    op.create_index("ix_incident_note_incident_created", "incident_note", ["incident_id", "created_at", "note_id"])
    op.execute(FUNCTION_DDL)
    op.execute(ROW_TRIGGER_DDL)
    op.execute(TRUNCATE_TRIGGER_DDL)
    op.drop_constraint("ck_incident_workflow_event_type", "incident_workflow_event", type_="check")
    op.create_check_constraint(
        "ck_incident_workflow_event_type", "incident_workflow_event",
        "record_type IN ('diagnosis', 'remediation', 'note')")


def downgrade() -> None:
    # Notes are append-only evidence of what engineers observed; refuse to drop them silently.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM incident_workflow_event WHERE record_type = 'note') THEN
                RAISE EXCEPTION 'cannot downgrade: note audit events exist';
            END IF;
        END $$
    """)
    op.drop_constraint("ck_incident_workflow_event_type", "incident_workflow_event", type_="check")
    op.create_check_constraint(
        "ck_incident_workflow_event_type", "incident_workflow_event", "record_type IN ('diagnosis', 'remediation')")
    op.execute("DROP TRIGGER IF EXISTS trg_incident_note_append_only_truncate ON incident_note")
    op.execute("DROP TRIGGER IF EXISTS trg_incident_note_append_only ON incident_note")
    op.execute("DROP FUNCTION IF EXISTS incident_note_append_only()")
    op.drop_index("ix_incident_note_incident_created", table_name="incident_note")
    op.drop_table("incident_note")
