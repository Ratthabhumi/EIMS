"""${message}
==============================================================================
EIMS Database Schema Revision: ${up_revision}
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 4 Compliance
==============================================================================

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Executes forward declarative schema migrations."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Reverts schema mutations to previous down_revision state."""
    ${downgrades if downgrades else "pass"}
