"""Real import/repository/analysis/history with synthetic SQLite, never backend.main."""
from contextlib import asynccontextmanager
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles, deregister
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.sql.elements import Cast

from tools.history_sandbox import create_app, prepare_sandbox, validate_target
from backend.domain.asset_registry import controller
from backend.domain.asset_registry.models import InfrastructureAsset, AuditLog
from backend.domain.asset_registry.repository import AssetRepository
from backend.domain.telemetry.models import WindowsEventLog


@pytest.fixture
def inventory_client(tmp_path):
    @compiles(JSONB, 'sqlite')
    def sqlite_json(element, compiler, **kw):
        return 'JSON'
    @compiles(Cast, 'sqlite')
    def sqlite_json_cast(element, compiler, **kw):
        # PostgreSQL JSONB cast is a no-op for SQLite's native JSON text.
        if isinstance(element.type, JSONB):
            return compiler.process(element.clause, **kw)
        return compiler.visit_cast(element, **kw)
    root = prepare_sandbox(tmp_path)
    app = create_app(root)
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        async with original(app):
            url = 'sqlite+aiosqlite:///' + str(root / 'history-test.sqlite3')
            validate_target(root, url)
            engine = create_async_engine(url)
            async with engine.begin() as connection:
                for table in (InfrastructureAsset.__table__, AuditLog.__table__, WindowsEventLog.__table__):
                    await connection.run_sync(table.create, checkfirst=True)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            app.state.inventory_sessions = sessions
            async def repo():
                async with sessions() as session:
                    yield AssetRepository(session, SimpleNamespace(set_value=AsyncMock(), get_value=AsyncMock(return_value=None)))
            app.dependency_overrides[controller.get_asset_repository] = repo
            try:
                yield
            finally:
                await engine.dispose()
    app.router.lifespan_context = lifespan
    app.include_router(controller.asset_router)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        deregister(JSONB)
        deregister(Cast)


def report(tmp_path, monkeypatch, events=True):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'clients/usb_auditor'))
    from exporters import json_exporter
    monkeypatch.setattr(json_exporter, 'REPORTS_DIR', tmp_path)
    collected = {'status':'ok', 'events':[dict(event_id=1129, provider='Microsoft-Windows-GroupPolicy',
                 channel='System', record_id=77, severity='Error', occurrence_time='2026-10-19T01:02:03+00:00',
                 message='The processing of Group Policy failed because of lack of network connectivity to a domain controller.')]} if events else None
    return json_exporter.save_report(dict(computer_name='SYNTHETIC-EXE-PC', ip_address='192.0.2.77',
                                         mac_address='02:00:00:00:00:77', collection_privileges='standard_user'),
                                    {}, {}, {}, {'score':95, 'verdict':'Compliant'}, event_logs=collected)


def test_exported_report_reaches_inventory_analysis_and_original_record(inventory_client, tmp_path, monkeypatch):
    path = report(tmp_path, monkeypatch)
    response = inventory_client.post('/api/v1/assets/import-report', files={'file':('synthetic.json',path.read_bytes(),'application/json')})
    assert response.status_code == 200, response.text
    asset = response.json()
    assert asset['hostname'] == 'SYNTHETIC-EXE-PC'
    assert asset['event_ingestion']['events_new'] == 1
    assert asset['event_ingestion']['events_analyzed'] == 1
    rows = inventory_client.get('/api/v1/history/', params={'asset_id':asset['asset_id']}).json()
    assert len(rows) == 1
    meta = rows[0]['eventMetadata']
    assert rows[0]['eventId'] == '1129' and meta['provider'] == 'Microsoft-Windows-GroupPolicy'
    provenance = rows[0]['provenance']
    assert provenance['asset_id'] == asset['asset_id']
    assert provenance['record_id'] == 77 and provenance['occurrence_time'].startswith('2026-10-19T01:02:03')
    assert provenance['event_source_id']


def test_old_inventory_only_report_never_claims_analyzed_events(inventory_client, tmp_path, monkeypatch):
    path = report(tmp_path, monkeypatch, events=False)
    response = inventory_client.post('/api/v1/assets/import-report', files={'file':('synthetic-legacy.json',path.read_bytes(),'application/json')})
    assert response.status_code == 200, response.text
    asset = response.json()
    assert asset['event_ingestion']['events_analyzed'] == 0
    assert inventory_client.get('/api/v1/history/', params={'asset_id':asset['asset_id']}).json() == []


def test_gui_metadata_edits_survive_refresh_reimport_and_reject_evidence_changes(inventory_client, tmp_path, monkeypatch):
    path = report(tmp_path, monkeypatch, events=False)
    data = json.loads(path.read_text())
    data.update(customer={'company':'Synthetic Company','contact_email':'it@example.invalid'},
                asset_context={'asset_tag':'PC-001'}, audit_context={'ticket_id':'INC-001'},
                manual_annotations=[{'finding_id':'security.defender','review_status':'Open','note':'Review needed'}])
    upload = lambda value: inventory_client.post('/api/v1/assets/import-report', files={'file':('synthetic.json',json.dumps(value),'application/json')})
    first = upload(data)
    assert first.status_code == 200, first.text
    asset = first.json(); target = '/api/v1/assets/'+asset['asset_id']
    assert asset['business_metadata']['customer']['contact_email'] == 'it@example.invalid'
    edited = asset['business_metadata']
    edited['customer']['company'] = 'Corrected Company'
    edited['manual_annotations'][0].update(review_status='Investigating',note='Separate engineer note')
    response = inventory_client.patch(target+'/business-context',json=edited)
    assert response.status_code == 200, response.text
    fresh = inventory_client.get(target).json()
    assert fresh['business_metadata'] == edited
    assert fresh['offline_report_data'] == data
    second = upload(data).json()
    assert second['asset_id'] == asset['asset_id'] and second['business_metadata'] == edited
    assert inventory_client.patch(target+'/business-context',json={'system':{'computer_name':'FORGED'}}).status_code == 422
    assert inventory_client.patch(target+'/business-context',json={'customer':{'password':'FORBIDDEN'}}).status_code == 422
    async def original_snapshots():
        from sqlalchemy import select
        async with inventory_client.app.state.inventory_sessions() as session:
            rows = (await session.execute(select(AuditLog).where(AuditLog.asset_id == asset['asset_id']))).scalars().all()
            return [r.immutable_payload for r in rows]
    # SQLite UUID adapter expects UUID, not an API string.
    import uuid
    original_id = asset['asset_id']; asset['asset_id'] = uuid.UUID(original_id)
    snapshots = inventory_client.portal.call(original_snapshots)
    assert sum(p.get('original_report') == data for p in snapshots) == 2
    assert any(p.get('operator') == 'synthetic-evaluation' and p.get('before') and p.get('after') for p in snapshots)


def test_selected_event_analysis_exact_result_dedup_and_cross_asset_rejection(inventory_client, tmp_path, monkeypatch):
    data = json.loads(report(tmp_path, monkeypatch).read_text())
    base = data['event_logs']['events'][0]
    base['message'] = 'Synthetic original event evidence beyond the former import text cap. ' * 60
    data['event_logs']['events'] = [{**base, 'record_id':n} for n in range(12)]
    response = inventory_client.post('/api/v1/assets/import-report',files={'file':('events.json',json.dumps(data),'application/json')})
    assert response.status_code == 200, response.text
    asset = response.json(); target='/api/v1/assets/'+asset['asset_id']
    assert asset['event_ingestion']['events_new'] == 12
    assert asset['event_ingestion']['events_analyzed'] == 10
    events = inventory_client.get(target+'/events').json()['events']
    assert len(events)==12 and sum(e['analysis_id'] is not None for e in events)==10
    remaining=next(e for e in events if not e['analysis_id'])
    url=target+'/events/'+remaining['log_id']+'/analyze'
    one=inventory_client.post(url);two=inventory_client.post(url)
    assert one.status_code == two.status_code == 200, one.text
    assert one.json()['analysis_id'] == two.json()['analysis_id']
    history=inventory_client.get('/api/v1/history/',params={'asset_id':asset['asset_id']}).json()
    assert len(history)==11
    exact=next(h for h in history if h['id']==one.json()['analysis_id'])
    assert exact['provenance']['event_source_id']==remaining['log_id']
    assert exact['provenance']['record_id']==remaining['evidence']['record_id']
    assert exact['description']==base['message']
    other=json.loads(json.dumps(data));other['system'].update(computer_name='SYNTHETIC-OTHER',mac_address='02:00:00:00:00:88')
    second=inventory_client.post('/api/v1/assets/import-report',files={'file':('other.json',json.dumps(other),'application/json')}).json()
    assert inventory_client.post('/api/v1/assets/'+second['asset_id']+'/events/'+remaining['log_id']+'/analyze').status_code==404


def test_secure_mode_rejects_unauthenticated_inventory_and_event_actions(inventory_client, monkeypatch):
    from backend.domain.analyzer import auth
    monkeypatch.setattr(auth.settings, 'AUTH_MODE', 'secure')
    inventory_client.app.dependency_overrides.pop(auth.get_current_user)
    asset='00000000-0000-0000-0000-000000000001'
    assert inventory_client.get('/api/v1/assets').status_code==401
    assert inventory_client.get(f'/api/v1/assets/{asset}/events').status_code==401
    assert inventory_client.patch(f'/api/v1/assets/{asset}/business-context',json={}).status_code==401
    assert inventory_client.post(f'/api/v1/assets/{asset}/events/{asset}/analyze').status_code==401


def test_import_keeps_long_original_message_and_explicit_utf8_truncation():
    from backend.domain.analyzer.services.import_pipeline import normalize_report_event, build_evtx_metadata
    original = 'Original evidence ' * 300
    event = normalize_report_event({'event_id':1129,'message':original,'message_truncated':False})
    assert event['message'] == original and not event['import_message_truncated']
    capped = normalize_report_event({'event_id':1129,'message':'ก'*30000,'message_truncated':False})
    assert len(capped['message'].encode('utf-8')) <= 65536
    assert capped['import_message_truncated'] and capped['import_message_original_bytes'] == 90000
    saved = build_evtx_metadata(capped, 'synthetic-dedup')
    assert saved['import_message_truncated'] and saved['message_truncated'] is False
