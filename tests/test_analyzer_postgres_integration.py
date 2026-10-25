"""Real PostgreSQL + real secure JWT verification in an isolated ASGI app.

Only EIMS_TEST_DATABASE_URL is accepted, never application database settings.
All request commits are savepoints inside a test transaction rolled back at exit.
"""
import asyncio
import os
import socket
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.api.routers.analyzer import analyze, history
from backend.domain.analyzer import auth
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.services import summary, vector_db
from backend.domain.analyzer.services.vendor_knowledge import vendor_reference_results
from tools.demo_analyzer_investigation import hero_inputs

TEST_KEY = 'synthetic-integration-signing-key-only-20261025'


def dedicated_url(value):
    url = make_url(value)
    if (url.drivername != 'postgresql+asyncpg' or url.host not in {'127.0.0.1', 'localhost'}
            or url.database != 'eims_integration_test' or url.username != 'eims_test'
            or url.port in {None, 5432, 6432}):
        raise ValueError('Refusing database: require dedicated loopback test DB/user and non-operational port')
    return url


@pytest.fixture
def integrated(monkeypatch):
    value = os.environ.get('EIMS_TEST_DATABASE_URL')
    if not value:
        pytest.skip('Dedicated synthetic PostgreSQL URL not configured; no operational fallback')
    url = dedicated_url(value)
    original_connect = socket.socket.connect
    def loopback_only(sock, address):
        if isinstance(address, tuple) and address[0] not in {'127.0.0.1', 'localhost', '::1'}:
            raise AssertionError('External network forbidden in integration test')
        return original_connect(sock, address)
    monkeypatch.setattr(socket.socket, 'connect', loopback_only)
    # These process-scoped patches affect this temporary app only; no .env or
    # installed authentication setting/credential is read or modified.
    monkeypatch.setattr(auth.settings, 'AUTH_MODE', 'secure')
    monkeypatch.setattr(auth.settings, 'ADMIN_TOKEN', 'synthetic-test-admin-token-only')
    monkeypatch.setattr(auth, 'SECRET_KEY', TEST_KEY)
    monkeypatch.setattr(auth, 'ALGORITHM', 'HS256')
    calls = {'export_attempts': 0}
    async def no_export(*a, **kw):
        calls['export_attempts'] += 1
    async def no_rag(*a, **kw):
        return []
    def local(event, provider, **kw):
        refs = vendor_reference_results(kw.get('diagnostic_code') or '', kw.get('evidence_text') or '', 'en')
        return refs, '\n'.join(r.snippet for r in refs)
    monkeypatch.setattr(analyze, 'search_solutions', local)
    monkeypatch.setattr(summary, 'search_similar_logs', no_rag)
    monkeypatch.setattr(vector_db, 'add_solution', no_export)
    def forbidden(*a, **kw):
        raise AssertionError('External inference forbidden in integration test')
    monkeypatch.setattr(summary, '_call_gemini', forbidden)

    async def run(check):
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(lambda c: AnalysisHistory.__table__.create(c, checkfirst=True))
            async with engine.connect() as conn:
                outer = await conn.begin()
                session = AsyncSession(bind=conn, expire_on_commit=False, join_transaction_mode='create_savepoint')
                before = await conn.scalar(select(func.count()).select_from(AnalysisHistory))
                app = FastAPI()
                app.include_router(analyze.router, prefix='/analyze')
                app.include_router(history.router, prefix='/history')
                async def db():
                    yield session
                app.dependency_overrides[analyze.get_db] = db
                # Auth dependency is intentionally NOT overridden.
                try:
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://synthetic-test') as client:
                        await check(client, session, calls)
                finally:
                    await session.close()
                    await outer.rollback()
                assert await conn.scalar(select(func.count()).select_from(AnalysisHistory)) == before
        finally:
            await engine.dispose()
    return lambda check: asyncio.run(run(check))


def bearer(name='synthetic-owner', **claims):
    payload = {'sub': name, 'exp': datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
    return {'Authorization': 'Bearer ' + jwt.encode(payload, TEST_KEY, algorithm='HS256')}


def test_real_postgres_upload_commit_reopen_and_ownership(integrated):
    async def check(client, session, calls):
        text = 'Log Name: System\nSource: Microsoft-Windows-GroupPolicy\nEvent ID: 1129\nLevel: Error\nDescription: Group Policy failed; synthetic DC unavailable ภาษาไทย\n'
        response = await client.post('/analyze/', headers=bearer(), data={'language': 'en'}, files={'file': ('synthetic.txt', text.encode(), 'text/plain')})
        assert response.status_code == 200, response.text
        saved = response.json()
        assert saved['historyId']
        # Expunge ORM identity state, then perform a fresh SELECT after route commit.
        session.expunge_all()
        rows = (await client.get('/history/', headers=bearer())).json()
        assert len(rows) == 1
        assert rows[0]['solutionSummary'] == saved['solutionSummary']
        assert rows[0]['eventMetadata'] == saved['eventMetadata']
        refs = rows[0]['solutionSummary']['evidenceItems']
        assert any('ภาษาไทย' in r['message'] for r in refs)
        assert refs[0]['sourceContextOrigin'] == 'extracted_source_excerpt'
        assert (await client.get('/history/', headers=bearer('synthetic-other'))).json() == []
        assert (await client.get('/history/stats', headers=bearer('synthetic-other'))).json()['totalLogs'] == 0
        hid = saved['historyId']
        for method, path, kw in [('DELETE', f'/history/{hid}', {}),
                                 ('POST', f'/history/{hid}/feedback?score=1', {}),
                                 ('POST', '/analyze/followup', {'json': {'historyId': hid, 'question': 'What is observed?', 'language': 'en'}})]:
            r = await client.request(method, path, headers=bearer('synthetic-other'), **kw)
            assert r.status_code == 404, r.text
            assert text not in r.text
        assert len((await client.get('/history/', headers=bearer())).json()) == 1
        assert calls['export_attempts'] == 1  # disabled sink only; no vector write
    integrated(check)


def test_real_postgres_bundle_history_and_legacy_fields(integrated):
    async def check(client, session, calls):
        files = [('files', (name, raw, 'text/plain')) for name, (raw, _) in hero_inputs().items()]
        r = await client.post('/analyze/bundle', headers=bearer(), data={'language': 'en'}, files=files)
        assert r.status_code == 200, r.text
        saved = r.json()
        rows = (await client.get('/history/', headers=bearer())).json()
        assert rows[0]['solutionSummary'] == saved['solutionSummary']
        assert rows[0]['files'] == saved['files']
        assert saved['correlationConfidence'] == 'medium'
        assert {i['sourceFile'] for i in saved['solutionSummary']['evidenceItems']} == set(hero_inputs())
        legacy = AnalysisHistory(username='synthetic-owner', event_id='6005', provider='synthetic',
                                 solution_summary={'overview': 'legacy synthetic', 'futureUnsupported': 'ignored'},
                                 event_metadata={}, search_results=[])
        session.add(legacy)
        await session.commit()
        reopened = (await client.get('/history/', headers=bearer())).json()
        old = next(x for x in reopened if x['eventId'] == '6005')
        assert old['solutionSummary']['evidenceItems'] == []
        assert 'futureUnsupported' not in old['solutionSummary']
    integrated(check)


@pytest.mark.parametrize('headers', [{}, {'Authorization': 'Bearer invalid'}, bearer(exp=datetime.now(timezone.utc)-timedelta(seconds=5))])
def test_real_auth_rejects_missing_invalid_and_expired_tokens(integrated, headers):
    async def check(client, session, calls):
        r = await client.get('/history/', headers=headers)
        assert r.status_code == 401
        assert 'postgres' not in r.text.lower() and 'traceback' not in r.text.lower()
    integrated(check)


@pytest.mark.parametrize('kind', ['duplicate', 'encoding', 'oversized'])
def test_invalid_bundle_is_rejected_without_persistence(integrated, monkeypatch, kind):
    if kind == 'oversized':
        monkeypatch.setattr(analyze, 'BUNDLE_MAX_FILE_BYTES', 32)
    async def check(client, session, calls):
        files = [('files', ('safe.txt', b'synthetic-only', 'text/plain'))]
        if kind == 'duplicate':
            files *= 2
        elif kind == 'traversal':
            files = [('files', ('../synthetic.txt', b'synthetic-only', 'text/plain'))]
        elif kind == 'encoding':
            files = [('files', ('invalid.txt', b'\xff\xfe\x80', 'text/plain'))]
        else:
            files = [('files', ('large.txt', b'x'*33, 'text/plain'))]
        r = await client.post('/analyze/bundle', headers=bearer(), data={'language':'en'}, files=files)
        assert r.status_code in {400, 413}, r.text
        assert (await client.get('/history/', headers=bearer())).json() == []
        assert calls['export_attempts'] == 0
    integrated(check)


def test_path_components_are_neutralized_without_filesystem_access(integrated):
    async def check(client, session, calls):
        r = await client.post('/analyze/bundle', headers=bearer(), data={'language':'en'},
                              files=[('files', ('../synthetic.txt', b'synthetic-only', 'text/plain'))])
        assert r.status_code == 200
        assert r.json()['files'][0]['filename'] == 'synthetic.txt'
        assert '../' not in str(r.json()['eventMetadata']['attributes']['bundle']['files'])
    integrated(check)


@pytest.mark.parametrize('url', ['postgresql+asyncpg://eims_test:x@127.0.0.1:5432/eims_integration_test',
                               'postgresql+asyncpg://eims_test:x@remote:55439/eims_integration_test',
                               'postgresql+asyncpg://eims_test:x@127.0.0.1:55439/eims'])
def test_refuses_operational_or_remote_database(url):
    with pytest.raises(ValueError, match='Refusing database'):
        dedicated_url(url)
