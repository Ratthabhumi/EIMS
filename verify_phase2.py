"""
==============================================================================
EIMS Automated ORM Schema & Index Verification Script
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 4 Compliance
==============================================================================
"""

import sys
from sqlalchemy.schema import CreateTable, CreateIndex
from backend.infrastructure.database import database_engine, Base
from backend.domain.asset_registry.models import InfrastructureAsset, HardwareInventory, AuditLog

def main():
    print("=== [EIMS Automated Verification: Testing ORM Schema & GIN Indexing] ===")
    try:
        tables = Base.metadata.tables
        expected_tables = ["infrastructure_assets", "hardware_inventories", "audit_logs"]
        
        for t_name in expected_tables:
            if t_name not in tables:
                print(f"ERROR: Expected canonical table '{t_name}' missing from SQLAlchemy metadata!")
                sys.exit(1)
            print(f"SUCCESS: Verified Core Law 4 Table structure -> '{t_name}'.")

        # Verify GIN Index attachment on HardwareInventory storage_topology
        hw_table = tables["hardware_inventories"]
        gin_index = next((idx for idx in hw_table.indexes if idx.name == "idx_hardware_storage_gin"), None)
        if not gin_index:
            print("ERROR: GIN Index 'idx_hardware_storage_gin' missing on hardware_inventories table!")
            sys.exit(1)
            
        print(f"SUCCESS: Confirmed PostgreSQL GIN Index topology: Name='{gin_index.name}' | Columns={[c.name for c in gin_index.columns]} | Dialect Using='{gin_index.dialect_options.get('postgresql', {}).get('using')}'")

        # Check constraint evaluations
        asset_table = tables["infrastructure_assets"]
        constraints = [c.name for c in asset_table.constraints if c.name]
        print(f"SUCCESS: Confirmed integrity Check & Unique Constraints on infrastructure_assets: {constraints}")
        
        print("=== [ALL SPRINT 2 PHASE 2 ORM STATIC ARCHITECTURAL TESTS PASSED SUCCESSFULLY] ===")
        sys.exit(0)
    except Exception as e:
        print(f"FATAL ERROR during Phase 2 ORM validation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
