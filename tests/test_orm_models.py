"""
==============================================================================
EIMS Automated Test Suite — SQLAlchemy 2.0 ORM Models & GIN Indexing
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 4 Compliance
==============================================================================
"""

import pytest
from backend.infrastructure.database import Base
from backend.domain.asset_registry import InfrastructureAsset, HardwareInventory, AuditLog


def test_canonical_tables_present_in_metadata():
    """Asserts that all three Core Law 4 canonical tables are registered in SQLAlchemy Declarative Base."""
    tables = Base.metadata.tables
    expected_tables = ["infrastructure_assets", "hardware_inventories", "audit_logs"]
    for t_name in expected_tables:
        assert t_name in tables, f"Expected table '{t_name}' missing from ORM metadata!"


def test_hardware_inventory_gin_index_attached():
    """Verifies that hardware_inventories table possesses Generalized Inverted Index (GIN) on storage_topology."""
    hw_table = Base.metadata.tables["hardware_inventories"]
    gin_index = next((idx for idx in hw_table.indexes if idx.name == "idx_hardware_storage_gin"), None)
    assert gin_index is not None, "Required GIN index 'idx_hardware_storage_gin' missing!"
    assert [c.name for c in gin_index.columns] == ["storage_topology"]
    assert gin_index.dialect_options.get("postgresql", {}).get("using") == "gin"


def test_infrastructure_asset_constraints():
    """Confirms strict compliance score check bounds and cryptographic fingerprint uniqueness."""
    asset_table = Base.metadata.tables["infrastructure_assets"]
    check_constraints = [c.name for c in asset_table.constraints if c.name == "ck_asset_compliance_score_bounds"]
    assert len(check_constraints) == 1, "Missing CheckConstraint bounding current_compliance_score!"
    
    # Check column definitions
    fingerprint_col = asset_table.columns["cryptographic_fingerprint"]
    assert fingerprint_col.unique is True, "Cryptographic fingerprint column must enforce uniqueness!"
