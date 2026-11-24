"""Provider scope for approved Knowledge entries.

Revision ID: b8e3f6a9c715
Revises: a7d2c5e8f604
Create Date: 2026-11-20

Additive. ``provider`` holds the provider an entry was written for; ``provider_scope`` states how to read it:
``provider_specific`` (exact provider required), ``vendor_product`` (family-level code, no provider concept),
``generic`` (explicitly provider independent, contextual only), ``unknown`` (legacy / not recorded) and
``unverified`` (attribution doubtful). Existing rows become ``unknown``: no provider is fabricated and an
``unknown`` row is never an exact provider match for provider-bearing families.
"""
from alembic import op
import sqlalchemy as sa

revision = "b8e3f6a9c715"
down_revision = "a7d2c5e8f604"
branch_labels = None
depends_on = None

SCOPES = ("provider_specific", "vendor_product", "generic", "unknown", "unverified")


def upgrade() -> None:
    op.add_column("knowledge_entries", sa.Column("provider", sa.String(160), nullable=True))
    op.add_column("knowledge_entries", sa.Column(
        "provider_scope", sa.String(24), nullable=False, server_default="unknown"))
    values = ", ".join(f"'{s}'" for s in SCOPES)
    op.create_check_constraint(
        "ck_knowledge_entries_provider_scope", "knowledge_entries", f"provider_scope IN ({values})")
    op.create_check_constraint(
        "ck_knowledge_entries_provider_specific_needs_provider", "knowledge_entries",
        "provider_scope <> 'provider_specific' OR (provider IS NOT NULL AND length(btrim(provider)) > 0)")


def downgrade() -> None:
    op.drop_constraint("ck_knowledge_entries_provider_specific_needs_provider", "knowledge_entries", type_="check")
    op.drop_constraint("ck_knowledge_entries_provider_scope", "knowledge_entries", type_="check")
    op.drop_column("knowledge_entries", "provider_scope")
    op.drop_column("knowledge_entries", "provider")
