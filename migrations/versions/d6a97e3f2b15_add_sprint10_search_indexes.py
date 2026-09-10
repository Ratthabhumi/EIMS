"""add_sprint10_search_indexes
==============================================================================
EIMS Database Schema Revision: d6a97e3f2b15
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 4 Compliance
==============================================================================

Revision ID: d6a97e3f2b15
Revises: 5811549d7120
Create Date: 2026-09-10 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd6a97e3f2b15'
down_revision: Union[str, None] = '5811549d7120'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adds Sprint 10 Global Search & Timeline index architecture (Core Law 4 §7.1)."""
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm;')

    # pg_trgm GIN indexes powering partial/substring matching on Asset search fields
    op.create_index(
        'idx_assets_hostname_trgm',
        'infrastructure_assets',
        ['hostname'],
        postgresql_using='gin',
        postgresql_ops={'hostname': 'gin_trgm_ops'},
    )
    op.create_index(
        'idx_assets_canonical_ip_trgm',
        'infrastructure_assets',
        ['canonical_ip'],
        postgresql_using='gin',
        postgresql_ops={'canonical_ip': 'gin_trgm_ops'},
    )
    # pg_trgm GIN index powering partial/exact matching on the immutable action_verb field
    op.create_index(
        'idx_audit_logs_action_trgm',
        'audit_logs',
        ['action_verb'],
        postgresql_using='gin',
        postgresql_ops={'action_verb': 'gin_trgm_ops'},
    )

    # Generated full-text search vector over Analysis History TEXT columns (secondary search domain)
    op.execute(
        """
        ALTER TABLE analysis_history
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(event_id, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(ai_summary, '')), 'C')
        ) STORED
        """
    )
    op.create_index(
        'idx_analysis_history_search_vector',
        'analysis_history',
        ['search_vector'],
        postgresql_using='gin',
    )


def downgrade() -> None:
    """Reverts Sprint 10 search indexes and the generated search_vector column.

    The pg_trgm extension is intentionally retained to mirror the existing
    `vector` extension precedent in revision 5811549d7120.
    """
    op.drop_index('idx_analysis_history_search_vector', table_name='analysis_history')
    op.execute('ALTER TABLE analysis_history DROP COLUMN IF EXISTS search_vector;')
    op.drop_index('idx_audit_logs_action_trgm', table_name='audit_logs')
    op.drop_index('idx_assets_canonical_ip_trgm', table_name='infrastructure_assets')
    op.drop_index('idx_assets_hostname_trgm', table_name='infrastructure_assets')