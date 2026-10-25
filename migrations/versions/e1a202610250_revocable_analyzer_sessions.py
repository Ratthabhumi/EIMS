"""Revocable Analyzer sessions and login windows; operator-applied migration."""
from alembic import op
import sqlalchemy as sa

revision = 'e1a202610250'
down_revision = '8a2b4d6f9c1e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('analyzer_sessions',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('credential_version', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True)))
    op.create_index('ix_analyzer_sessions_user_id','analyzer_sessions',['user_id'])
    op.create_index('ix_analyzer_sessions_expires_at','analyzer_sessions',['expires_at'])
    op.create_table('analyzer_login_windows',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    # Operator-only rollback; these auth rows are independent of History.
    op.drop_table('analyzer_login_windows')
    op.drop_table('analyzer_sessions')
