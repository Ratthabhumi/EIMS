import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from contextlib import asynccontextmanager
from unittest.mock import patch
import pytest
from backend.main import app
from sqlalchemy.ext.asyncio import AsyncEngine,AsyncSession
from sqlalchemy.engine import Engine
@asynccontextmanager
async def no_runtime(app):
    yield
async def denied_async(*a,**k):
    raise AssertionError('DELIVERY_AUDIT_FORBIDS_DATABASE_IO')
def denied(*a,**k):
    raise AssertionError('DELIVERY_AUDIT_FORBIDS_DATABASE_IO')
# In-process test transport only. Do not start main lifespan: it seeds and starts workers.
with patch.object(app.router,'lifespan_context',no_runtime), patch.object(AsyncSession,'execute',denied_async), patch.object(AsyncSession,'commit',denied_async), patch.object(AsyncEngine,'connect',denied), patch.object(Engine,'connect',denied):
    raise SystemExit(pytest.main(['tests/test_state_machine.py','tests/test_orm_models.py','tests/test_sprint13_evidence_ingestion.py','tests/test_api_controllers.py','tests/test_ocr_upload_pipeline.py','tests/test_global_search.py','tests/test_timeline.py','-q','-o','addopts=','--tb=short','--junitxml=test-results/project-audit-modules.xml']))
