"""Real isolated SQLite persistence through actual Analyzer/History API routes."""
from pathlib import Path
import sqlite3
import pytest
from fastapi.testclient import TestClient
from tools.history_sandbox import prepare_sandbox, validate_target, create_app


@pytest.mark.parametrize('target', [
    'postgresql+asyncpg://synthetic:synthetic@127.0.0.1:6432/eims',
    'postgresql+asyncpg://synthetic:synthetic@example.invalid/test',
    'sqlite+aiosqlite:///operational.sqlite3',
    'sqlite+aiosqlite:///:memory:',
])
def test_guard_rejects_operational_or_undeclared_targets(tmp_path, target):
    root=prepare_sandbox(tmp_path)
    with pytest.raises(ValueError):validate_target(root,target)


def test_guard_rejects_bad_identity_before_engine_creation(tmp_path):
    root=prepare_sandbox(tmp_path)
    (root/'sandbox.json').write_text('{}')
    with pytest.raises(ValueError):create_app(root)


def test_actual_api_persists_and_reads_synthetic_history(tmp_path):
    root=prepare_sandbox(tmp_path)
    app=create_app(root)
    text='Log Name: System\nSource: Microsoft-Windows-Kernel-Power\nEvent ID: 41\nDate: 2026-10-15T01:00:00Z\nUnclean restart. Synthetic evidence.'
    with TestClient(app) as client:
        assert client.get('/__sandbox').json()=={'purpose':'synthetic-history-only','dialect':'sqlite','operational_startup':False}
        preflight=client.options('/api/v1/analyze/bundle',headers={'Origin':'http://127.0.0.1:3115','Access-Control-Request-Method':'POST'})
        assert preflight.status_code==200
        assert preflight.headers['access-control-allow-origin']=='http://127.0.0.1:3115'
        denied=client.options('/api/v1/analyze/bundle',headers={'Origin':'https://example.invalid','Access-Control-Request-Method':'POST'})
        assert denied.status_code==400 and 'access-control-allow-origin' not in denied.headers
        from backend.infrastructure.database import database_engine
        import asyncio, asyncpg
        with pytest.raises(RuntimeError):asyncio.run(database_engine.initialize())
        with pytest.raises(RuntimeError):asyncio.run(asyncpg.connect('postgresql://localhost/eims'))
        response=client.post('/api/v1/analyze/',files={'file':('synthetic-shutdown.txt',text.encode(),'text/plain')},data={'language':'en'})
        assert response.status_code==200, response.text
        result=response.json()
        rows=client.get('/api/v1/history/').json()
        assert len(rows)==1 and rows[0]['id']==result['historyId']
        assert rows[0]['eventId']=='41' and rows[0]['eventMetadata']['sourceFamily']=='windows_event'
        assert rows[0]['solutionSummary']['causes']==[]
        assert 'Synthetic evidence.' in rows[0]['description']
        with sqlite3.connect(app.state.sandbox_db) as db:
            assert db.execute('select count(*) from analysis_history').fetchone()[0]==1
            assert db.execute('pragma database_list').fetchone()[2]==app.state.sandbox_db


def test_negative_veeam_fixture_keeps_provenance_in_real_history(tmp_path):
    root=prepare_sandbox(tmp_path)
    fixtures=Path(__file__).resolve().parents[1]/'EIMS_supervision_synthetic_demo_files_2026-10-09'
    with TestClient(create_app(root)) as client:
        response=client.post('/api/v1/analyze/bundle',files=[('files',(name,(fixtures/name).read_bytes(),'text/plain')) for name in ['01_report.txt','02_Task_long.log']],data={'language':'en'})
        assert response.status_code==200,response.text
        result=response.json()
        assert result['correlationConfidence']=='none'
        rows=client.get('/api/v1/history/').json()
        assert rows[0]['id']==result['historyId']
        assert rows[0]['correlationConfidence']=='none'
        items=rows[0]['solutionSummary']['evidenceItems']
        assert any(i['sourceFile']=='02_Task_long.log' and i['lineNumber']==1001 for i in items)
