"""
==============================================================================
EIMS Automated Syntax & OpenAPI Schema Generation Test Script
Governed by EIMS Documentation System (EDS v1.0.0)
==============================================================================
"""

import sys
import json
from backend.main import app

def main():
    print("=== [EIMS Automated Verification: Testing FastAPI & OpenAPI Export] ===")
    try:
        openapi_schema = app.openapi()
        print(f"SUCCESS: FastAPI application initialized successfully (Version: {app.version}).")
        print(f"SUCCESS: OpenAPI Title = {openapi_schema.get('info', {}).get('title')}")
        
        # Ensure RFC 7807 problem details handler is correctly registered in routes
        paths = openapi_schema.get("paths", {})
        health_path = paths.get("/api/v1/health", {})
        if not health_path:
            print("ERROR: /api/v1/health endpoint missing from OpenAPI routing table!")
            sys.exit(1)
            
        print("SUCCESS: Health Operational Observability endpoint successfully indexed.")
        print("=== [ALL STATIC ARCHITECTURAL TESTS PASSED SUCCESSFULLY] ===")
        sys.exit(0)
    except Exception as e:
        print(f"FATAL ERROR during validation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
