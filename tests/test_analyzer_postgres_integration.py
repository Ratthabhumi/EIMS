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

from backend.api.routers.analyzer import analyze, history, auth as auth_api, stats, feedback, admin, obsidian
from backend.domain.analyzer import auth
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.models.user import User
from backend.domain.analyzer.services import summary, vector_db
from backend.domain.analyzer.services.vendor_knowledge import vendor_reference_results
from tools.demo_analyzer_investigation import hero_inputs
from backend.domain.search import controller as search_api
from backend.domain.search.providers.analysis_provider import AnalysisSearchProvider

TEST_KEY = 'synthetic-integration-signing-key-only-20261025'
TEST_PASSWORD = 'synthetic-test-password-only'


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
                await conn.run_sync(lambda c: User.__table__.create(c, checkfirst=True))
            async with engine.connect() as conn:
                outer = await conn.begin()
                session = AsyncSession(bind=conn, expire_on_commit=False, join_transaction_mode='create_savepoint')
                before = await conn.scalar(select(func.count()).select_from(AnalysisHistory))
                for username, role in [('synthetic-owner', 'user'), ('synthetic-other', 'user'), ('synthetic-admin', 'admin')]:
                    session.add(User(username=username, role=role, password=auth.hash_password(TEST_PASSWORD)))
                await session.flush()
                app = FastAPI()
                app.include_router(analyze.router, prefix='/analyze')
                app.include_router(history.router, prefix='/history')
                app.include_router(auth_api.router, prefix='/auth')
                app.include_router(stats.router, prefix='/stats')
                app.include_router(feedback.router, prefix='/feedback')
                app.include_router(admin.router, prefix='/admin')
                app.include_router(obsidian.router, prefix='/export')
                app.include_router(search_api.search_router, prefix='/global')
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


def test_login_session_deleted_account_and_current_admin_role(integrated):
    async def check(client, session, calls):
        bad = await client.post('/auth/login', json={'username':'synthetic-owner','password':'wrong'})
        assert bad.status_code == 401
        r = await client.post('/auth/login', json={'username':'synthetic-owner','password':TEST_PASSWORD})
        assert r.status_code == 200
        headers = {'Authorization':'Bearer '+r.json()['access_token']}
        assert (await client.get('/auth/session', headers=headers)).json()['username'] == 'synthetic-owner'
        changed = headers['Authorization'][:-5] + 'wrong'
        assert (await client.get('/history/', headers={'Authorization':changed})).status_code == 401
        admin_headers = bearer('synthetic-admin', role='admin')
        assert (await client.get('/admin/users', headers=admin_headers)).status_code == 200
        account = (await session.execute(select(User).where(User.username=='synthetic-admin'))).scalars().one()
        account.role = 'user'
        await session.commit()
        assert (await client.get('/admin/users', headers=admin_headers)).status_code == 403
        assert (await client.post('/export/obsidian/export', headers=admin_headers, json={'history_id':1})).status_code == 403
        account = (await session.execute(select(User).where(User.username=='synthetic-owner'))).scalars().one()
        await session.delete(account)
        await session.commit()
        assert (await client.get('/history/', headers=headers)).status_code == 401
    integrated(check)


def test_demo_mode_remains_shared_without_login(integrated, monkeypatch):
    monkeypatch.setattr(auth.settings, 'AUTH_MODE', 'demo')
    async def check(client, session, calls):
        assert (await client.get('/auth/session')).json() == {'username':'demo','mode':'demo'}
        assert (await client.get('/history/')).status_code == 200
    integrated(check)


def test_legacy_feedback_and_statistics_are_owner_scoped(integrated):
    async def check(client, session, calls):
        row = AnalysisHistory(username='synthetic-owner', event_id='6005', provider='synthetic',
                              solution_summary={'overview':'owner-only'}, event_metadata={},search_results=[])
        session.add(row)
        await session.commit()
        r = await client.post('/feedback/feedback', headers=bearer('synthetic-other'), json={'history_id':row.id,'score':-1})
        assert r.status_code == 404
        assert (await client.get('/stats/', headers=bearer('synthetic-other'))).json()['totalLogs'] == 0
        data = (await client.get('/stats/correlations', headers=bearer('synthetic-other'))).json()
        assert '6005' not in str(data)
    integrated(check)


def test_sensitive_credentials_are_not_returned_or_persisted(integrated):
    async def check(client, session, calls):
        text = ('2026-10-25T10:00:00Z Er(02) vmx - CTK_CTKUNLINK result:2620 '
                'password="SYNTHETIC_SECRET_ONLY" access_token=SYNTHETIC_ACCESS_ONLY '
                'Authorization: Bearer SYNTHETIC_BEARER_ONLY\n'
                'user=synthetic-user ip=192.0.2.9 path=/synthetic/private-only\n')
        r = await client.post('/analyze/', headers=bearer(), data={'language':'en'},files={'file':('privacy.txt',text.encode(),'text/plain')})
        assert r.status_code == 200
        for secret in ('SYNTHETIC_SECRET_ONLY','SYNTHETIC_ACCESS_ONLY','SYNTHETIC_BEARER_ONLY'):
            assert secret not in r.text
        stored = await session.get(AnalysisHistory, r.json()['historyId'])
        for secret in ('SYNTHETIC_SECRET_ONLY','SYNTHETIC_ACCESS_ONLY','SYNTHETIC_BEARER_ONLY'):
            assert secret not in str(stored.__dict__)
        metadata = r.json()['eventMetadata']['attributes']['evidencePrivacy']
        assert metadata['credentialsRedacted'] >= 3
        assert r.json()['solutionSummary']['evidenceItems'][0]['sourceContextOrigin'] == 'redacted_extracted_source_excerpt'
    integrated(check)


def test_global_search_history_is_owner_scoped(integrated, monkeypatch):
    # Isolate ownership from FTS availability for the red/green reproduction.
    async def fallback(self, db, query, limit):
        return await self._fallback_ilike(db, query, limit)
    monkeypatch.setattr(AnalysisSearchProvider, '_search_vector', fallback)
    async def check(client, session, calls):
        session.add(AnalysisHistory(username='synthetic-owner', event_id='1129', provider='synthetic',
                                    description='SYNTHETIC_PRIVATE_SEARCH_MARKER', event_metadata={},search_results=[]))
        await session.commit()
        endpoint='/global/api/v1/search?q=SYNTHETIC_PRIVATE_SEARCH_MARKER&type=analysis'
        owner=await client.get(endpoint,headers=bearer())
        assert owner.status_code == 200
        assert 'SYNTHETIC_PRIVATE_SEARCH_MARKER' in owner.text
        other=await client.get(endpoint,headers=bearer('synthetic-other'))
        assert other.status_code == 200
        assert 'SYNTHETIC_PRIVATE_SEARCH_MARKER' not in other.text
    integrated(check)


def test_global_search_missing_fts_column_rolls_back_then_filters(integrated):
    async def check(client, session, calls):
        session.add(AnalysisHistory(username='synthetic-owner', event_id='1129', provider='synthetic',
                                    description='SYNTHETIC_FALLBACK_MARKER', event_metadata={},search_results=[]))
        await session.commit()
        endpoint='/global/api/v1/search?q=SYNTHETIC_FALLBACK_MARKER&type=analysis'
        assert 'SYNTHETIC_FALLBACK_MARKER' in (await client.get(endpoint,headers=bearer())).text
        assert 'SYNTHETIC_FALLBACK_MARKER' not in (await client.get(endpoint,headers=bearer('synthetic-other'))).text
        assert (await client.get('/history/',headers=bearer())).status_code == 200
    integrated(check)
