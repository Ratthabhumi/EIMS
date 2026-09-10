"""align_ai_knowledge_embedding_dimension

Revision ID: 8a2b4d6f9c1e
Revises: d6a97e3f2b15
Create Date: 2026-09-10 22:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "8a2b4d6f9c1e"
down_revision: Union[str, None] = "d6a97e3f2b15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "ai_knowledge",
        "embedding",
        existing_type=Vector(768),
        type_=Vector(384),
        postgresql_using="embedding::vector(384)",
    )


def downgrade() -> None:
    op.alter_column(
        "ai_knowledge",
        "embedding",
        existing_type=Vector(384),
        type_=Vector(768),
        postgresql_using="embedding::vector(768)",
    )