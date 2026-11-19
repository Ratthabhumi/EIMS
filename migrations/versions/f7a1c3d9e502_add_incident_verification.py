"""Add append-only incident verification bound to a remediation cycle.

Revision ID: f7a1c3d9e502
Revises: c4e8a1f7b932
Create Date: 2026-11-19

Why
---
Incident Core v1 could move an incident to ``resolved`` on a caller command
alone. This revision adds the persisted proof required to close that gap:

* ``incidents.remediation_cycle`` / ``remediation_started_at`` bind verification
  to one remediation cycle. A genuine reopen (resolved -> investigating)
  increments the cycle exactly once and re-bases the start instant.
* ``incident_verification`` stores one immutable record per
  (incident, cycle, evidence). Rows are append-only: a PostgreSQL trigger
  rejects UPDATE/DELETE so the application role cannot rewrite history even
  through raw SQL.
* ``ON DELETE RESTRICT`` on both foreign keys keeps historical verification
  reachable; reopening makes old rows inapplicable by cycle, it never deletes
  them.

Legacy rows
-----------
Existing incidents keep their status. ``remediation_cycle`` defaults to 0 and
``remediation_started_at`` is backfilled from ``created_at`` (never ``now()``)
so pre-existing evidence is judged against when it was actually created. No
verification row is fabricated: an already-resolved incident is **not**
retroactively marked verified.

Downgrade
---------
Destructive and intentionally limited: dropping ``incident_verification``
discards verification history. Take a backup and obtain approval before
downgrading a database that carries real incident history.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f7a1c3d9e502"
down_revision = "c4e8a1f7b932"
branch_labels = None
depends_on = None

TRIGGER_FUNCTION = "incident_verification_append_only"
TRIGGER_NAME = "trg_incident_verification_append_only"

APPEND_ONLY_FUNCTION_DDL = f"""
CREATE OR REPLACE FUNCTION {TRIGGER_FUNCTION}() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'incident_verification is append-only (attempted %)', TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql
"""

APPEND_ONLY_TRIGGER_DDL = f"""
CREATE TRIGGER {TRIGGER_NAME}
BEFORE UPDATE OR DELETE ON incident_verification
FOR EACH ROW EXECUTE FUNCTION {TRIGGER_FUNCTION}()
"""

APPEND_ONLY_TRUNCATE_DDL = f"""
CREATE TRIGGER {TRIGGER_NAME}_truncate
BEFORE TRUNCATE ON incident_verification
FOR EACH STATEMENT EXECUTE FUNCTION {TRIGGER_FUNCTION}()
"""

RESOLUTION_TRIGGER_FUNCTION = "incident_resolution_requires_verification"

RESOLUTION_FUNCTION_DDL = f"""
CREATE OR REPLACE FUNCTION {RESOLUTION_TRIGGER_FUNCTION}() RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'resolved' AND OLD.status IS DISTINCT FROM 'resolved' THEN
        IF NOT EXISTS (
            SELECT 1
            FROM incident_verification v
            JOIN incident_evidence e ON e.evidence_id = v.evidence_id
            WHERE v.incident_id = NEW.incident_id
              AND v.remediation_cycle = NEW.remediation_cycle
              AND v.outcome = 'passed'
              AND e.incident_id = NEW.incident_id
              AND v.evidence_digest = e.evidence_digest
              AND v.verifier_id <> e.added_by
              AND e.created_at >= NEW.remediation_started_at
        ) THEN
            RAISE EXCEPTION
                'incident % cannot be resolved without verification for cycle %',
                NEW.incident_id, NEW.remediation_cycle
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""

RESOLUTION_TRIGGER_DDL = f"""
CREATE TRIGGER trg_incident_resolution_requires_verification
BEFORE UPDATE OF status ON incidents
FOR EACH ROW EXECUTE FUNCTION {RESOLUTION_TRIGGER_FUNCTION}()
"""

CYCLE_GUARD_FUNCTION = "incident_remediation_cycle_guard"

CYCLE_GUARD_FUNCTION_DDL = f"""
CREATE OR REPLACE FUNCTION {CYCLE_GUARD_FUNCTION}() RETURNS trigger AS $$
BEGIN
    -- 'closed' is terminal in the service transition map; a raw UPDATE must not
    -- resurrect it, otherwise closed -> open -> resolved replays verification.
    IF OLD.status = 'closed' AND NEW.status <> 'closed' THEN
        RAISE EXCEPTION 'closed incidents are terminal; they cannot be moved to %', NEW.status
            USING ERRCODE = 'check_violation';
    END IF;

    -- Leaving 'resolved' for a live state must start a new cycle, otherwise a
    -- raw resolved -> open -> resolved sequence replays the old verification.
    -- resolved -> closed stays legal without a bump.
    IF OLD.status = 'resolved' AND NEW.status NOT IN ('resolved', 'closed')
       AND NEW.remediation_cycle IS NOT DISTINCT FROM OLD.remediation_cycle THEN
        RAISE EXCEPTION 'leaving resolved requires a new remediation cycle'
            USING ERRCODE = 'check_violation';
    END IF;

    -- The cycle may only advance by exactly one, on a reopen.
    IF NEW.remediation_cycle IS DISTINCT FROM OLD.remediation_cycle THEN
        IF NOT (
            OLD.status = 'resolved'
            AND NEW.status NOT IN ('resolved', 'closed')
            AND NEW.remediation_cycle = OLD.remediation_cycle + 1
        ) THEN
            RAISE EXCEPTION
                'remediation_cycle may only advance by one on a reopen (was %, attempted %)',
                OLD.remediation_cycle, NEW.remediation_cycle
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    -- The cycle start moves only together with a valid bump, so a crafted
    -- status update cannot widen the evidence-freshness window.
    IF NEW.remediation_started_at IS DISTINCT FROM OLD.remediation_started_at
       AND NEW.remediation_cycle IS NOT DISTINCT FROM OLD.remediation_cycle THEN
        RAISE EXCEPTION 'remediation_started_at may only change with a new cycle'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""

CYCLE_GUARD_TRIGGER_DDL = f"""
CREATE TRIGGER trg_incident_remediation_cycle_guard
BEFORE UPDATE OF status, remediation_cycle, remediation_started_at ON incidents
FOR EACH ROW EXECUTE FUNCTION {CYCLE_GUARD_FUNCTION}()
"""

INSERT_GUARD_FUNCTION = "incident_insert_state_guard"

INSERT_GUARD_FUNCTION_DDL = f"""
CREATE OR REPLACE FUNCTION {INSERT_GUARD_FUNCTION}() RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'resolved' THEN
        RAISE EXCEPTION 'incidents must be created in a non-resolved state'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.remediation_cycle IS DISTINCT FROM 0 THEN
        RAISE EXCEPTION 'remediation_cycle must start at 0'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""

INSERT_GUARD_TRIGGER_DDL = f"""
CREATE TRIGGER trg_incident_insert_state_guard
BEFORE INSERT ON incidents
FOR EACH ROW EXECUTE FUNCTION {INSERT_GUARD_FUNCTION}()
"""


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("remediation_cycle", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "incidents",
        sa.Column(
            "remediation_started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Truthful backfill for legacy rows; never fabricate a later start instant.
    op.execute("UPDATE incidents SET remediation_started_at = created_at")
    op.create_check_constraint(
        "ck_incident_remediation_cycle_non_negative",
        "incidents",
        "remediation_cycle >= 0",
    )

    op.create_table(
        "incident_verification",
        sa.Column("verification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("remediation_cycle", sa.Integer(), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_digest", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("verifier_id", sa.String(length=255), nullable=False),
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "outcome IN ('passed', 'failed')",
            name="ck_incident_verification_outcome_valid",
        ),
        sa.CheckConstraint(
            "remediation_cycle >= 0",
            name="ck_incident_verification_cycle_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.incident_id"],
            name="fk_incident_verification_incident_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["incident_evidence.evidence_id"],
            name="fk_incident_verification_evidence_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("verification_id", name="pk_incident_verification"),
        sa.UniqueConstraint(
            "incident_id",
            "remediation_cycle",
            "evidence_id",
            name="uq_incident_verification_cycle_evidence",
        ),
        comment="Append-only verified-remediation records bound to one cycle.",
    )
    op.create_index(
        "ix_incident_verification_incident_id",
        "incident_verification",
        ["incident_id"],
        unique=False,
    )
    op.create_index(
        "ix_incident_verification_evidence_id",
        "incident_verification",
        ["evidence_id"],
        unique=False,
    )
    op.create_index(
        "ix_incident_verification_incident_cycle",
        "incident_verification",
        ["incident_id", "remediation_cycle"],
        unique=False,
    )
    op.execute(APPEND_ONLY_FUNCTION_DDL)
    op.execute(RESOLUTION_FUNCTION_DDL)
    op.execute(CYCLE_GUARD_FUNCTION_DDL)
    op.execute(INSERT_GUARD_FUNCTION_DDL)
    op.execute(APPEND_ONLY_TRIGGER_DDL)
    op.execute(APPEND_ONLY_TRUNCATE_DDL)
    op.execute(RESOLUTION_TRIGGER_DDL)
    op.execute(CYCLE_GUARD_TRIGGER_DDL)
    op.execute(INSERT_GUARD_TRIGGER_DDL)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_incident_insert_state_guard ON incidents")
    op.execute(f"DROP FUNCTION IF EXISTS {INSERT_GUARD_FUNCTION}()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_incident_remediation_cycle_guard ON incidents"
    )
    op.execute(f"DROP FUNCTION IF EXISTS {CYCLE_GUARD_FUNCTION}()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_incident_resolution_requires_verification ON incidents"
    )
    op.execute(f"DROP FUNCTION IF EXISTS {RESOLUTION_TRIGGER_FUNCTION}()")
    op.execute(
        f"DROP TRIGGER IF EXISTS {TRIGGER_NAME}_truncate ON incident_verification"
    )
    op.execute(f"DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON incident_verification")
    op.execute(f"DROP FUNCTION IF EXISTS {TRIGGER_FUNCTION}()")
    op.drop_index("ix_incident_verification_incident_cycle", table_name="incident_verification")
    op.drop_index("ix_incident_verification_evidence_id", table_name="incident_verification")
    op.drop_index("ix_incident_verification_incident_id", table_name="incident_verification")
    op.drop_table("incident_verification")
    op.drop_constraint(
        "ck_incident_remediation_cycle_non_negative", "incidents", type_="check"
    )
    op.drop_column("incidents", "remediation_started_at")
    op.drop_column("incidents", "remediation_cycle")
