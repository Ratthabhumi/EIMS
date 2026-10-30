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
from backend.domain.analyzer.models.session import AnalyzerSession, LoginWindow
from backend.domain.analyzer.services import session_security
from backend.domain.analyzer.services import summary, vector_db
from backend.domain.analyzer.services.vendor_knowledge import vendor_reference_results
from tools.demo_analyzer_investigation import hero_inputs
from backend.domain.search import controller as search_api
from backend.domain.search.providers.analysis_provider import AnalysisSearchProvider
from backend.api.routers import evaluations
from backend.domain.evaluation.models import ServiceSession, ServiceEvaluation
from backend.domain.asset_registry.controller import asset_router
from backend.domain.asset_registry.audit_controller import audit_router
from backend.domain.telemetry.query_controller import telemetry_query_router
from backend.domain.timeline.controller import timeline_router
from backend.domain.telemetry.controller import telemetry_router

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
    monkeypatch.setattr(session_security, 'THROTTLE_NAMESPACE', 'pytest-isolated')
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
                await conn.run_sync(lambda c: AnalyzerSession.__table__.create(c, checkfirst=True))
                await conn.run_sync(lambda c: LoginWindow.__table__.create(c, checkfirst=True))
                await conn.run_sync(lambda c: ServiceSession.__table__.create(c, checkfirst=True))
                await conn.run_sync(lambda c: ServiceEvaluation.__table__.create(c, checkfirst=True))
            async with engine.connect() as conn:
                outer = await conn.begin()
                session = AsyncSession(bind=conn, expire_on_commit=False, join_transaction_mode='create_savepoint')
                before = await conn.scalar(select(func.count()).select_from(AnalysisHistory))
                for username, role in [('synthetic-owner', 'user'), ('synthetic-other', 'user'), ('synthetic-admin', 'admin')]:
                    account = User(username=username, role=role, password=auth.hash_password(TEST_PASSWORD))
                    session.add(account)
                    await session.flush()
                    now = datetime.now(timezone.utc)
                    session.add(AnalyzerSession(id=session_security.digest('synthetic-session-'+username), user_id=account.id,
                        username=username, credential_version=session_security.digest(account.password),
                        created_at=now, last_seen=now, expires_at=now+timedelta(minutes=10)))
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
                for router in [evaluations.router, asset_router, audit_router, telemetry_query_router, timeline_router, telemetry_router]:
                    app.include_router(router)
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
    payload = {'sub': name, 'sid':'synthetic-session-'+name, 'exp': datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
    return {'Authorization': 'Bearer ' + jwt.encode(payload, TEST_KEY, algorithm='HS256')}


def test_login_logout_revokes_copied_token_only(integrated):
    async def check(client, session, calls):
        async def login():
            r = await client.post('/auth/login', json={'username':'synthetic-owner', 'password':TEST_PASSWORD})
            assert r.status_code == 200, r.text
            return {'Authorization':'Bearer '+r.json()['access_token']}
        first, second = await login(), await login()
        assert first != second
        assert (await client.get('/auth/session', headers=first)).status_code == 200
        assert (await client.post('/auth/logout', headers=first)).status_code == 200
        assert (await client.get('/history/', headers=first)).status_code == 401
        assert (await client.get('/history/', headers=second)).status_code == 200
        payload = jwt.decode(first['Authorization'][7:], TEST_KEY, algorithms=['HS256'])
        row = await session.get(AnalyzerSession, session_security.digest(payload['sid']))
        assert row.revoked_at is not None
        assert row.id != payload['sid']
    integrated(check)


@pytest.mark.parametrize('reason', ['idle', 'absolute', 'password', 'account_id', 'sidless'])
def test_session_invalidated_by_lifecycle_boundaries(integrated, reason):
    async def check(client, session, calls):
        row = await session.get(AnalyzerSession, session_security.digest('synthetic-session-synthetic-owner'))
        if reason == 'idle':
            row.last_seen = datetime.now(timezone.utc)-timedelta(seconds=session_security.IDLE_SECONDS+1)
        elif reason == 'absolute':
            row.expires_at = datetime.now(timezone.utc)-timedelta(seconds=1)
        elif reason == 'password':
            user = (await session.execute(select(User).where(User.username=='synthetic-owner'))).scalar_one()
            user.password = auth.hash_password('synthetic-new-password')
        elif reason == 'account_id':
            row.user_id += 100000
        await session.commit()
        headers = bearer(sid=None) if reason == 'sidless' else bearer()
        assert (await client.get('/history/', headers=headers)).status_code == 401
    integrated(check)


def test_background_probe_does_not_extend_idle_but_activity_does(integrated):
    async def check(client, session, calls):
        key = session_security.digest('synthetic-session-synthetic-owner')
        row = await session.get(AnalyzerSession, key)
        old = datetime.now(timezone.utc)-timedelta(seconds=60)
        row.last_seen = old
        await session.commit()
        assert (await client.get('/auth/session', headers=bearer())).status_code == 200
        await session.refresh(row)
        assert row.last_seen == old
        assert (await client.get('/history/', headers=bearer())).status_code == 200
        await session.refresh(row)
        assert row.last_seen > old
    integrated(check)


def test_login_throttle_persists_failed_attempts_and_recovers(integrated):
    async def check(client, session, calls):
        data = {'username':'synthetic-owner', 'password':'wrong-synthetic-only'}
        missing = await client.post('/auth/login', json={**data,'username':'synthetic-nonexistent'})
        for _ in range(session_security.ACCOUNT_LIMIT):
            denied = await client.post('/auth/login', json=data)
            assert denied.status_code == 401
            assert denied.json() == missing.json()
        limited = await client.post('/auth/login', json={**data,'password':TEST_PASSWORD})
        assert limited.status_code == 429
        assert 1 <= int(limited.headers['retry-after']) <= 61
        key = session_security.digest(session_security.THROTTLE_NAMESPACE+':account:synthetic-owner')
        window = await session.get(LoginWindow, key)
        assert window.attempts == session_security.ACCOUNT_LIMIT+1
        window.started_at = datetime.now(timezone.utc)-timedelta(seconds=61)
        await session.commit()
        recovered = await client.post('/auth/login', json={**data,'password':TEST_PASSWORD})
        assert recovered.status_code == 200
    integrated(check)


def test_deleted_account_cannot_inherit_retained_history(integrated):
    async def check(client, session, calls):
        account = (await session.execute(select(User).where(User.username=='synthetic-owner'))).scalar_one()
        session.add(AnalysisHistory(username=account.username,event_id='synthetic',provider='synthetic',
                                    solution_summary={},event_metadata={},search_results=[]))
        await session.commit()
        assert (await client.delete(f'/admin/users/{account.id}', headers=bearer('synthetic-admin'))).status_code == 200
        assert (await client.get('/history/', headers=bearer())).status_code == 401
        r = await client.post('/admin/users', headers=bearer('synthetic-admin'), json={
            'username':'synthetic-owner','password':TEST_PASSWORD})
        assert r.status_code == 409
        assert (await session.execute(select(User).where(User.username=='synthetic-owner'))).scalar_one_or_none() is None
    integrated(check)


def test_orgwide_search_requires_current_admin_including_unfiltered_query(integrated, monkeypatch):
    from backend.domain.search.providers.evaluation_provider import EvaluationSearchProvider
    from backend.domain.search.provider import SearchResult
    calls_to_private = []
    async def private(self, **kw):
        calls_to_private.append(True)
        return [SearchResult(type='evaluation',id='synthetic',title='SYNTHETIC_PRIVATE_ORG',
            subtitle='synthetic only',url='/evaluations/admin/synthetic',timestamp=None,relevance=1.0)]
    monkeypatch.setattr(EvaluationSearchProvider, 'search', private)
    async def check(client, session, calls):
        query = '/global/api/v1/search?q=SYNTHETIC_PRIVATE_ORG'
        denied = await client.get(query+'&type=evaluation', headers=bearer())
        assert denied.status_code == 403
        unfiltered = await client.get(query, headers=bearer())
        assert unfiltered.status_code == 200 and 'SYNTHETIC_PRIVATE_ORG' not in unfiltered.text
        assert calls_to_private == []
        permitted = await client.get(query+'&type=evaluation', headers=bearer('synthetic-admin'))
        assert permitted.status_code == 200 and 'SYNTHETIC_PRIVATE_ORG' in permitted.text
        assert calls_to_private == [True]
    integrated(check)


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


def test_direct_org_routes_cannot_bypass_search_admin_gate(integrated):
    async def check(client, session, calls):
        created=await client.post('/api/v1/evaluations/sessions',headers=bearer('synthetic-admin'),
            json={'title':'SYNTHETIC_PRIVATE','customer_name':'synthetic-customer'})
        assert created.status_code==201,created.text
        sid=created.json()['session_id']
        paths=['/api/v1/assets','/api/v1/assets/ocr-history','/api/v1/assets/ocr-history/image?object_key=synthetic',
               '/api/v1/audit-logs','/api/v1/telemetry/metrics','/api/v1/telemetry/winlogs',
               '/api/v1/timeline','/api/v1/evaluations/sessions?skip=1',
               f'/api/v1/evaluations/sessions/{sid}', f'/api/v1/evaluations/sessions/{sid}/responses']
        for headers,expected in [(bearer(),403),(bearer('synthetic-other'),403),({},401),({'Authorization':'Bearer tampered'},401)]:
            for path in paths:
                r=await client.get(path,headers=headers)
                assert r.status_code==expected,(path,r.status_code,r.text)
                assert 'synthetic-customer' not in r.text
        rows=await client.get('/api/v1/evaluations/sessions',headers=bearer('synthetic-admin'))
        assert rows.status_code==200 and 'synthetic-customer' in rows.text
        for headers,expected in [(bearer(),403),({},401)]:
            r=await client.post('/api/v1/telemetry/upload/evtx',headers={**headers,'X-Client-Cert-Fingerprint':'a'*64},
                files={'file':('synthetic.evtx',b'synthetic-only','application/octet-stream')})
            assert r.status_code==expected
    integrated(check)


def test_auth_retention_preserves_active_rows_and_history_and_rolls_back(integrated, monkeypatch):
    from backend.domain.analyzer.services.session_maintenance import cleanup_auth_records
    async def check(client, session, calls):
        now = datetime.now(timezone.utc)
        old = now-timedelta(days=8)
        row = await session.get(AnalyzerSession, session_security.digest('synthetic-session-synthetic-other'))
        row.expires_at = old
        window = LoginWindow(id='synthetic-expired-window',attempts=9,started_at=old)
        session.add(window)
        session.add(LoginWindow(id='synthetic-live-window',attempts=8,started_at=now))
        await session.commit()
        original_execute = session.execute
        async def fail_second_delete(statement, *args, **kwargs):
            if getattr(statement,'is_delete',False) and statement.table.name == 'analyzer_login_windows':
                raise RuntimeError('synthetic rollback control')
            return await original_execute(statement,*args,**kwargs)
        monkeypatch.setattr(session,'execute',fail_second_delete)
        with pytest.raises(RuntimeError,match='rollback control'):
            await cleanup_auth_records(session,retention_seconds=7*86400,now=now)
        monkeypatch.setattr(session,'execute',original_execute)
        assert await session.get(AnalyzerSession,session_security.digest('synthetic-session-synthetic-other')) is not None
        await session.commit()
        preview=await cleanup_auth_records(session,retention_seconds=7*86400,batch_size=1,now=now,dry_run=True)
        assert preview == {'analyzer_sessions':1,'analyzer_login_windows':1}
        assert await session.get(LoginWindow,'synthetic-expired-window') is not None
        await session.commit()
        counts=await cleanup_auth_records(session,retention_seconds=7*86400,batch_size=1,now=now)
        assert counts == {'analyzer_sessions':1,'analyzer_login_windows':1}
        assert await session.get(LoginWindow,'synthetic-live-window') is not None
        assert (await client.get('/history/',headers=bearer())).status_code == 200
    integrated(check)


def test_actual_auth_migration_reconnect_and_concurrent_maintenance(integrated):
    """Execute the actual Alembic revision in a fresh retained synthetic schema.

    No downgrade/drop: generated test-only auth rows remain for inspection. The
    operational URL cannot pass dedicated_url. The old application data is not used.
    """
    import uuid
    from sqlalchemy import text, inspect
    from alembic.config import Config
    from alembic import command
    from backend.domain.analyzer.services.session_maintenance import cleanup_auth_records
    async def check(unused_client, unused_session, calls):
        url=dedicated_url(os.environ['EIMS_TEST_DATABASE_URL'])
        schema='eims_rehearsal_'+uuid.uuid4().hex
        engine=create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA {schema}'))  # generated identifier only
                await conn.execute(text(f'SET LOCAL search_path TO {schema}'))
                await conn.run_sync(lambda c: User.__table__.create(c))
                await conn.run_sync(lambda c: AnalysisHistory.__table__.create(c))
                def migrate(c):
                    assert not inspect(c).has_table('analyzer_sessions',schema=schema)
                    config=Config()
                    config.set_main_option('script_location','migrations')
                    config.attributes['connection']=c
                    command.stamp(config,'8a2b4d6f9c1e')
                    command.upgrade(config,'head')
                    assert c.scalar(text('SELECT version_num FROM alembic_version'))=='e1a202610250'
                    assert {i['name'] for i in inspect(c).get_indexes('analyzer_sessions',schema=schema)} == {
                        'ix_analyzer_sessions_user_id','ix_analyzer_sessions_expires_at'}
                    assert inspect(c).has_table('analyzer_login_windows',schema=schema)
                await conn.run_sync(migrate)
        finally:
            await engine.dispose()
        def new_engine():
            return create_async_engine(url,connect_args={'server_settings':{'search_path':schema}})
        engine=new_engine()
        try:
            async with AsyncSession(engine) as db:
                db.add(User(username='synthetic-migration',password=auth.hash_password(TEST_PASSWORD),role='user'))
                await db.commit()
            app=FastAPI()
            app.include_router(auth_api.router,prefix='/auth')
            async def migrated_db():
                async with AsyncSession(engine,expire_on_commit=False) as db:
                    yield db
            app.dependency_overrides[auth_api.get_db_session]=migrated_db
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://synthetic-test') as client:
                login=await client.post('/auth/login',json={'username':'synthetic-migration','password':TEST_PASSWORD})
                assert login.status_code==200,login.text
                headers={'Authorization':'Bearer '+login.json()['access_token']}
                assert (await client.get('/auth/session',headers=headers)).status_code==200
                await engine.dispose()  # new physical connections, not ORM identity reuse
                engine=new_engine()
                assert (await client.get('/auth/session',headers=headers)).status_code==200
                assert (await client.post('/auth/logout',headers=headers)).status_code==200
                assert (await client.get('/auth/session',headers=headers)).status_code==401
                assert (await client.post('/auth/login',json={'username':'synthetic-migration','password':TEST_PASSWORD})).status_code==200
            # Real PostgreSQL contention using independently committed connections.
            async def attempt():
                async with AsyncSession(engine) as db:
                    try:
                        await session_security.reserve_login(db,'synthetic-concurrent','loopback-test')
                        return 200
                    except Exception as exc:
                        if getattr(exc,'status_code',None)==429:
                            return 429
                        raise
            attempts=await asyncio.gather(*(attempt() for _ in range(20)))
            assert attempts.count(200)==8 and attempts.count(429)==12
            async with AsyncSession(engine) as db:
                db.add(LoginWindow(id='synthetic-old-window',attempts=1,started_at=datetime.now(timezone.utc)-timedelta(days=8)))
                await db.commit()
            async with AsyncSession(engine) as lock, AsyncSession(engine) as worker:
                await lock.execute(select(LoginWindow).where(LoginWindow.id=='synthetic-old-window').with_for_update())
                assert (await cleanup_auth_records(worker,retention_seconds=7*86400))['analyzer_login_windows']==0
                await lock.rollback()
                assert (await cleanup_auth_records(worker,retention_seconds=7*86400))['analyzer_login_windows']==1
                # Both migration-issued sessions remain: revoked retention is not yet elapsed.
                assert await worker.scalar(select(func.count()).select_from(AnalyzerSession))==2
        finally:
            await engine.dispose()
    integrated(check)


@pytest.mark.parametrize("state, expected", [("revoked",401),("expired",401),("demoted",403)])
def test_shared_api_rechecks_admin_session_before_reads_and_customer_writes(integrated, state, expected):
    async def check(client, session, calls):
        headers=bearer('synthetic-admin')
        created=await client.post('/api/v1/evaluations/sessions',headers=headers,
            json={'title':'SYNTHETIC_SCOPED','customer_name':'synthetic-private'})
        assert created.status_code==201
        sid=created.json()['session_id']
        if state=='demoted':
            user=(await session.execute(select(User).where(User.username=='synthetic-admin'))).scalar_one()
            user.role='user'
        else:
            row=await session.get(AnalyzerSession,session_security.digest('synthetic-session-synthetic-admin'))
            if state=='revoked': row.revoked_at=datetime.now(timezone.utc)
            else: row.expires_at=datetime.now(timezone.utc)-timedelta(minutes=1)
        await session.commit()
        for path in ['/api/v1/assets','/api/v1/telemetry/winlogs','/api/v1/timeline',
                     f'/api/v1/evaluations/sessions/{sid}',f'/api/v1/evaluations/sessions/{sid}/responses']:
            response=await client.get(path,headers=headers)
            assert response.status_code==expected,(path,response.text)
            assert 'synthetic-private' not in response.text
        response=await client.post(f'/api/v1/evaluations/sessions/{sid}/evaluate',headers=headers,
            json={'responder_name':'synthetic-only','rating_scores':[{'question_id':'q1','score':5}]})
        assert response.status_code==expected,response.text
        assert await session.scalar(select(func.count()).select_from(ServiceEvaluation).where(ServiceEvaluation.session_id==sid))==0
    integrated(check)


def test_full_migration_lineage_from_empty_isolated_schema(integrated):
    import uuid
    from sqlalchemy import text, inspect
    from alembic.config import Config
    from alembic import command
    async def check(client, session, calls):
        schema='eims_full_lineage_'+uuid.uuid4().hex
        engine=create_async_engine(dedicated_url(os.environ['EIMS_TEST_DATABASE_URL']))
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA {schema}'))
                extension_schema=await conn.scalar(text("SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector'"))
                suffix=(', '+conn.dialect.identifier_preparer.quote(extension_schema)) if extension_schema else ''
                await conn.execute(text(f'SET LOCAL search_path TO {schema}{suffix}'))
                def migrate(c):
                    assert inspect(c).get_table_names(schema=schema)==[]
                    config=Config(); config.set_main_option('script_location','migrations')
                    config.attributes['connection']=c
                    config.attributes['version_table_schema']=schema
                    command.upgrade(config,'head')
                    assert c.scalar(text(f'SELECT version_num FROM {schema}.alembic_version'))=='e1a202610250'
                    assert {'users','analysis_history','analyzer_sessions','analyzer_login_windows',
                            'infrastructure_assets','service_sessions','service_evaluations'}.issubset(
                                set(inspect(c).get_table_names(schema=schema)))
                await conn.run_sync(migrate)
        finally:
            await engine.dispose()
    integrated(check)


def test_populated_parent_upgrade_preserves_history_ownership_and_sessions(integrated):
    """Real parent revision and synthetic rows; no operational URL or reset."""
    import uuid
    from sqlalchemy import text
    from alembic.config import Config
    from alembic import command
    async def check(unused_client, unused_session, calls):
        schema='eims_populated_'+uuid.uuid4().hex
        url=dedicated_url(os.environ['EIMS_TEST_DATABASE_URL'])
        engine=create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA {schema}'))
                ext=await conn.scalar(text("SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector'"))
                suffix=(', '+conn.dialect.identifier_preparer.quote(ext)) if ext else ''
                await conn.execute(text(f'SET LOCAL search_path TO {schema}{suffix}'))
                def migrate(c, target):
                    config=Config(); config.set_main_option('script_location','migrations')
                    config.attributes.update(connection=c,version_table_schema=schema)
                    command.upgrade(config,target)
                await conn.run_sync(lambda c:migrate(c,'8a2b4d6f9c1e'))
                assert await conn.scalar(text(f'SELECT version_num FROM {schema}.alembic_version'))=='8a2b4d6f9c1e'
                for name in ['synthetic-pre-owner','synthetic-pre-other']:
                    await conn.execute(text('INSERT INTO users (username,password,role) VALUES (:u,:p,:r)'),
                        {'u':name,'p':auth.hash_password(TEST_PASSWORD),'r':'user'})
                    await conn.execute(text("INSERT INTO analysis_history (event_id,provider,username,description,solution_summary,search_results,created_at) VALUES ('1129','synthetic',:u,'SYNTHETIC ONLY',CAST(:s AS json),'[]',CURRENT_TIMESTAMP)"),
                        {'u':name,'s':'{"overview":"synthetic retained evidence","evidence":["line 1"]}'})
                before=(await conn.execute(text('SELECT row_to_json(h)::text FROM analysis_history h ORDER BY id'))).scalars().all()
                await conn.run_sync(lambda c:migrate(c,'head'))
                after=(await conn.execute(text('SELECT row_to_json(h)::text FROM analysis_history h ORDER BY id'))).scalars().all()
                assert after==before
                assert await conn.scalar(text(f'SELECT version_num FROM {schema}.alembic_version'))=='e1a202610250'
        finally:
            await engine.dispose()
        def reconnect():
            return create_async_engine(url,connect_args={'server_settings':{'search_path':schema}})
        engine=reconnect()
        try:
            app=FastAPI();app.include_router(auth_api.router,prefix='/auth');app.include_router(history.router,prefix='/history')
            async def db():
                async with AsyncSession(engine,expire_on_commit=False) as s: yield s
            app.dependency_overrides[auth_api.get_db_session]=db
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://synthetic-test') as client:
                for name in ['synthetic-pre-owner','synthetic-pre-other']:
                    login=await client.post('/auth/login',json={'username':name,'password':TEST_PASSWORD})
                    assert login.status_code==200,login.text
                    headers={'Authorization':'Bearer '+login.json()['access_token']}
                    rows=await client.get('/history/',headers=headers)
                    assert rows.status_code==200,rows.text
                    assert len(rows.json())==1 and rows.json()[0]['username']==name
                    await engine.dispose();engine=reconnect()
                    assert (await client.get('/auth/session',headers=headers)).status_code==200
                    assert (await client.post('/auth/logout',headers=headers)).status_code==200
                    assert (await client.get('/auth/session',headers=headers)).status_code==401
            async with engine.connect() as conn:
                assert (await conn.execute(text('SELECT row_to_json(h)::text FROM analysis_history h ORDER BY id'))).scalars().all()==before
        finally:
            await engine.dispose()
    integrated(check)

@pytest.mark.parametrize('language', ['th', 'en'])
@pytest.mark.parametrize('cid', ['bundle_related', 'esxi_heartbeat'])
def test_no_failure_postgres_history_reopen(integrated, language, cid):
    from evaluation.analyzer import runner
    doc, payloads = runner.load_manifest(runner.REPO / 'evaluation/analyzer/gold/manifest.v1.json')
    files = payloads[cid]
    async def check(client, session, calls):
        uploads = [(name.rsplit('/', 1)[-1], raw, 'text/plain') for name, (raw, _) in files.items()]
        if len(uploads) > 1:
            response = await client.post('/analyze/bundle', headers=bearer(), data={'language': language},
                                         files=[('files', f) for f in uploads])
        else:
            response = await client.post('/analyze/', headers=bearer(), data={'language': language}, files={'file': uploads[0]})
        assert response.status_code == 200, response.text
        saved = response.json()
        expected = 'ไม่พบความล้มเหลว' if language == 'th' else 'No failure observed'
        assert expected in saved['solutionSummary']['overview']
        assert saved['solutionSummary']['causes'] == []
        session.expunge_all()
        rows = (await client.get('/history/', headers=bearer())).json()
        assert rows[0]['solutionSummary'] == saved['solutionSummary']
        assert rows[0]['aiSummary'] == saved['aiSummary']
        assert (await client.get('/history/', headers=bearer('synthetic-other'))).json() == []
    integrated(check)
