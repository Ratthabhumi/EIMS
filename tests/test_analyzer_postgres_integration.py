"""Real PostgreSQL + real secure JWT verification in an isolated ASGI app.

Only EIMS_TEST_DATABASE_URL is accepted, never application database settings.
All request commits are savepoints inside a test transaction rolled back at exit.
"""
import asyncio
import os
import secrets
import socket
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.api.routers import evaluations
from backend.api.routers.analyzer import (
    admin,
    analyze,
    feedback,
    history,
    knowledge,
    obsidian,
    stats,
)
from backend.api.routers.analyzer import auth as auth_api
from backend.domain.analyzer import auth
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.models.knowledge import (
    KnowledgeEntry,
    KnowledgeLifecycleEvent,
    KnowledgeUsage,
    KnowledgeSourceCandidate,
    KnowledgeSourceEvent,
)
from backend.domain.analyzer.models.session import AnalyzerSession, LoginWindow
from backend.domain.analyzer.models.user import User
from backend.domain.analyzer.services import session_security, summary, vector_db
from backend.domain.analyzer.services.vendor_knowledge import vendor_reference_results
from backend.domain.asset_registry.audit_controller import audit_router
from backend.domain.asset_registry.models import AuditLog, InfrastructureAsset
from backend.domain.incident_ingest.models import IncidentIngestOutbox


def _alembic_head() -> str:
    """Single linear Alembic head from the script directory (no DB access)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config()
    cfg.set_main_option('script_location', 'migrations')
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert len(heads) == 1, heads
    return heads[0]
from backend.domain.asset_registry.controller import asset_router
from backend.domain.evaluation.models import ServiceEvaluation, ServiceSession
from backend.domain.search import controller as search_api
from backend.domain.search.providers.analysis_provider import AnalysisSearchProvider
from backend.domain.telemetry.controller import telemetry_router
from backend.domain.telemetry.query_controller import telemetry_query_router
from backend.domain.timeline.controller import timeline_router
from tools.demo_analyzer_investigation import hero_inputs

TEST_KEY = 'synthetic-integration-signing-key-only-20261025'
TEST_PASSWORD = 'synthetic-test-password-only'
ALLOWED_TEST_DATABASES = {
    'eims_integration_test',
    'eims_regression_test_20261115',
    'eims_finalization_20261115',
    'eims_analyzer_it',  # provisioned for the NON-superuser role below (no privileged credential needed)
}
ALLOWED_TEST_ROLES = {'eims_test', 'eims_incident_test'}


def dedicated_url(value):
    url = make_url(value)
    if (url.drivername != 'postgresql+asyncpg' or url.host not in {'127.0.0.1', 'localhost'}
            or url.database not in ALLOWED_TEST_DATABASES or url.username not in ALLOWED_TEST_ROLES
            or url.port in {None, 5432, 6432}):
        raise ValueError('Refusing database: require dedicated loopback test DB/user and non-operational port')
    return url


def configure_migration_test_auth(monkeypatch):
    """Keep standalone migration rehearsals in the same secure auth mode as integrated tests."""
    monkeypatch.setattr(auth.settings, 'AUTH_MODE', 'secure')
    monkeypatch.setattr(auth.settings, 'ADMIN_TOKEN', 'synthetic-test-admin-token-only')
    monkeypatch.setattr(auth, 'SECRET_KEY', TEST_KEY)
    monkeypatch.setattr(auth, 'ALGORITHM', 'HS256')
    monkeypatch.setattr(session_security, 'THROTTLE_NAMESPACE', 'pytest-isolated')
    original_connect = socket.socket.connect

    def loopback_only(sock, address):
        if isinstance(address, tuple) and address[0] not in {'127.0.0.1', 'localhost', '::1'}:
            raise AssertionError('External network forbidden in migration rehearsal')
        return original_connect(sock, address)

    monkeypatch.setattr(socket.socket, 'connect', loopback_only)


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

    async def run(check):
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                # The destructive-path gate requires proof of the live target.
                # This harness is already restricted to an explicitly dedicated
                # disposable URL (dedicated_url), so bind the identity to the
                # connection that was actually opened, not to the URL string.
                identity = (await conn.execute(
                    __import__('sqlalchemy').text(
                        "SELECT current_database(), current_user"))).first()
                # monkeypatch keeps this scoped to the test; a plain os.environ
                # assignment would leak a trusted identity into later tests.
                if identity[1] != 'eims_test':
                    # Non-superuser role: the database must carry the explicit disposable marker, be non-superuser
                    # and be on a non-operational port (checked in dedicated_url).
                    marker = (await conn.execute(__import__('sqlalchemy').text(
                        "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = current_database()"))).scalar()
                    is_super = (await conn.execute(__import__('sqlalchemy').text(
                        "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"))).scalar()
                    assert marker == 'EIMS_DISPOSABLE_TEST_DB' and not is_super, 'database is not provably disposable'
                monkeypatch.setenv('EIMS_DB_IDENTITY', f'{identity[0]}|{identity[1]}')
                # analysis_history references infrastructure_assets: parent table first (fresh disposable DB).
                await conn.run_sync(lambda c: InfrastructureAsset.__table__.create(c, checkfirst=True))
                await conn.run_sync(lambda c: AuditLog.__table__.create(c, checkfirst=True))
                await conn.run_sync(lambda c: AnalysisHistory.__table__.create(c, checkfirst=True))
                await conn.run_sync(lambda c: KnowledgeEntry.__table__.create(c, checkfirst=True))
                await conn.run_sync(lambda c: KnowledgeUsage.__table__.create(c, checkfirst=True))
                await conn.run_sync(lambda c: KnowledgeLifecycleEvent.__table__.create(c, checkfirst=True))
                await conn.run_sync(lambda c: KnowledgeSourceCandidate.__table__.create(c, checkfirst=True))
                await conn.run_sync(lambda c: KnowledgeSourceEvent.__table__.create(c, checkfirst=True))
                await conn.run_sync(lambda c: User.__table__.create(c, checkfirst=True))
                await conn.run_sync(lambda c: AnalyzerSession.__table__.create(c, checkfirst=True))
                await conn.run_sync(lambda c: LoginWindow.__table__.create(c, checkfirst=True))
                # v1.1: analyzer inserts write incident_ingest_outbox in the same transaction (F1).
                await conn.run_sync(lambda c: IncidentIngestOutbox.__table__.create(c, checkfirst=True))
                await conn.run_sync(lambda c: ServiceSession.__table__.create(c, checkfirst=True))
                await conn.run_sync(lambda c: ServiceEvaluation.__table__.create(c, checkfirst=True))
            async with engine.connect() as conn:
                outer = await conn.begin()
                # Keep analyzer assertions deterministic when the shared synthetic DB
                # already contains reviewed knowledge from Browser Acceptance. The
                # deletion is inside the outer transaction and is rolled back below.
                await conn.execute(delete(KnowledgeSourceEvent))
                await conn.execute(delete(KnowledgeSourceCandidate))
                await conn.execute(delete(KnowledgeUsage))
                await conn.execute(delete(KnowledgeEntry))
                session = AsyncSession(bind=conn, expire_on_commit=False, join_transaction_mode='create_savepoint')
                before = await conn.scalar(select(func.count()).select_from(AnalysisHistory))
                for username, role, can_review in [('synthetic-owner', 'user', False), ('synthetic-other', 'user', False), ('synthetic-reviewer', 'user', True), ('synthetic-admin', 'admin', False)]:
                    account = User(username=username, role=role, knowledge_reviewer=can_review, password=auth.hash_password(TEST_PASSWORD))
                    session.add(account)
                    await session.flush()
                    now = datetime.now(UTC)
                    session.add(AnalyzerSession(id=session_security.digest('synthetic-session-'+username), user_id=account.id,
                        username=username, credential_version=session_security.digest(account.password),
                        created_at=now, last_seen=now, expires_at=now+timedelta(minutes=10)))
                await session.flush()
                app = FastAPI()
                app.include_router(analyze.router, prefix='/analyze')
                app.include_router(history.router, prefix='/history')
                app.include_router(knowledge.router, prefix='/knowledge')
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
                app.dependency_overrides[knowledge.get_db] = db
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
    payload = {'sub': name, 'sid':'synthetic-session-'+name, 'exp': datetime.now(UTC) + timedelta(minutes=5), **claims}
    return {'Authorization': 'Bearer ' + jwt.encode(payload, TEST_KEY, algorithm='HS256')}


async def seed_owner_history(session):
    session.add(AnalysisHistory(username='synthetic-owner', event_id='6005', provider='synthetic',
                                description='SYNTHETIC_OWNER_ROW', solution_summary={}, event_metadata={}, search_results=[]))
    await session.commit()


async def history_owners(client, headers=None):
    """Usernames that own the rows this caller can read (200 is required: no-login never 401s ordinary reads)."""
    r = await client.get('/history/', headers=headers or {})
    assert r.status_code == 200, r.text
    return {x['username'] for x in r.json()}


def test_retired_login_is_gone_and_revoked_token_cannot_read_owner_history(integrated):
    """No-login contract: /auth/login is an explicit 410 (never a token), logout is harmless without a token,
    and a revoked session-bound token degrades to the shared open-access identity - it never keeps the owner's data."""
    async def check(client, session, calls):
        await seed_owner_history(session)
        for creds in ({'username':'synthetic-owner','password':TEST_PASSWORD}, {'username':'synthetic-owner','password':'wrong'},
                      {'username':'synthetic-nonexistent','password':'wrong'}):
            r = await client.post('/auth/login', json=creds)
            assert r.status_code == 410 and 'access_token' not in r.text
        # No account-existence oracle: identical bodies for a real and a missing account.
        a = await client.post('/auth/login', json={'username':'synthetic-owner','password':'x'})
        b = await client.post('/auth/login', json={'username':'synthetic-nonexistent','password':'x'})
        assert a.json() == b.json()
        assert (await client.post('/auth/logout')).json() == {'authenticated': False}
        first = bearer()
        assert history_owners_set(await client.get('/history/', headers=first)) == {'synthetic-owner'}
        assert (await client.post('/auth/logout', headers=first)).status_code == 200
        row = await session.get(AnalyzerSession, session_security.digest('synthetic-session-synthetic-owner'))
        assert row.revoked_at is not None
        assert await history_owners(client, first) == set()
        assert (await client.get('/auth/session', headers=first)).json()['username'] == 'demo'
    integrated(check)


def history_owners_set(response):
    assert response.status_code == 200, response.text
    return {x['username'] for x in response.json()}


@pytest.mark.parametrize('reason', ['idle', 'absolute', 'password', 'account_id', 'sidless'])
def test_session_invalidated_by_lifecycle_boundaries(integrated, reason):
    """An invalidated session-bound token must not keep the owner's identity or data (it degrades to open access)."""
    async def check(client, session, calls):
        await seed_owner_history(session)
        assert await history_owners(client, bearer()) == {'synthetic-owner'}   # control: the live token works
        row = await session.get(AnalyzerSession, session_security.digest('synthetic-session-synthetic-owner'))
        if reason == 'idle':
            row.last_seen = datetime.now(UTC)-timedelta(seconds=session_security.IDLE_SECONDS+1)
        elif reason == 'absolute':
            row.expires_at = datetime.now(UTC)-timedelta(seconds=1)
        elif reason == 'password':
            user = (await session.execute(select(User).where(User.username=='synthetic-owner'))).scalar_one()
            user.password = auth.hash_password('synthetic-new-password')
        elif reason == 'account_id':
            row.user_id += 100000
        await session.commit()
        headers = bearer(sid=None) if reason == 'sidless' else bearer()
        assert await history_owners(client, headers) == set()
        assert (await client.get('/auth/session', headers=headers)).json()['username'] == 'demo'
    integrated(check)


def test_background_probe_does_not_extend_idle_but_activity_does(integrated):
    async def check(client, session, calls):
        key = session_security.digest('synthetic-session-synthetic-owner')
        row = await session.get(AnalyzerSession, key)
        old = datetime.now(UTC)-timedelta(seconds=60)
        row.last_seen = old
        await session.commit()
        assert (await client.get('/auth/session', headers=bearer())).status_code == 200
        await session.refresh(row)
        assert row.last_seen == old
        assert (await client.get('/history/', headers=bearer())).status_code == 200
        await session.refresh(row)
        assert row.last_seen > old
    integrated(check)


def test_recent_activity_does_not_rewrite_session_row(integrated):
    async def check(client, session, calls):
        from sqlalchemy import text
        key = session_security.digest('synthetic-session-synthetic-owner')
        row = await session.get(AnalyzerSession, key)
        recent = datetime.now(UTC) - timedelta(seconds=5)
        row.last_seen = recent
        await session.commit()
        before_xmin = await session.scalar(text(
            'SELECT xmin::text FROM analyzer_sessions WHERE id = :id'
        ), {'id': key})

        # Authenticated activity within the touch interval validates read-only.
        assert (await client.get('/history/', headers=bearer())).status_code == 200
        await session.refresh(row)
        after_recent_xmin = await session.scalar(text(
            'SELECT xmin::text FROM analyzer_sessions WHERE id = :id'
        ), {'id': key})
        assert row.last_seen == recent
        assert after_recent_xmin == before_xmin, 'Recent activity must not UPDATE/lock the session row'

        # Background auth/session checks are also read-only.
        assert (await client.get('/auth/session', headers=bearer())).status_code == 200
        after_background_xmin = await session.scalar(text(
            'SELECT xmin::text FROM analyzer_sessions WHERE id = :id'
        ), {'id': key})
        assert after_background_xmin == before_xmin

        # Activity after the interval advances last_seen and keeps the idle window alive.
        stale = datetime.now(UTC) - timedelta(
            seconds=session_security.SESSION_TOUCH_INTERVAL_SECONDS + 5
        )
        row.last_seen = stale
        await session.commit()
        before_touch_xmin = await session.scalar(text(
            'SELECT xmin::text FROM analyzer_sessions WHERE id = :id'
        ), {'id': key})
        assert (await client.get('/history/', headers=bearer())).status_code == 200
        await session.refresh(row)
        after_touch_xmin = await session.scalar(text(
            'SELECT xmin::text FROM analyzer_sessions WHERE id = :id'
        ), {'id': key})
        assert row.last_seen > stale
        assert after_touch_xmin != before_touch_xmin, 'Stale active session should be touched'


def test_retired_login_creates_no_session_and_no_throttle_state(integrated):
    """The retired endpoint must not mint sessions or write throttle windows (reserve_login itself is still covered
    against real PostgreSQL contention in test_actual_auth_migration_reconnect_and_concurrent_maintenance)."""
    async def check(client, session, calls):
        sessions_before = await session.scalar(select(func.count()).select_from(AnalyzerSession))
        windows_before = await session.scalar(select(func.count()).select_from(LoginWindow))
        for _ in range(session_security.ACCOUNT_LIMIT + 3):
            r = await client.post('/auth/login', json={'username':'synthetic-owner','password':'wrong-synthetic-only'})
            assert r.status_code == 410
        r = await client.post('/auth/login', json={'username':'synthetic-owner','password':TEST_PASSWORD})
        assert r.status_code == 410 and 'access_token' not in r.text
        assert await session.scalar(select(func.count()).select_from(AnalyzerSession)) == sessions_before
        assert await session.scalar(select(func.count()).select_from(LoginWindow)) == windows_before
    integrated(check)


def test_deleted_account_cannot_inherit_retained_history(integrated):
    async def check(client, session, calls):
        account = (await session.execute(select(User).where(User.username=='synthetic-owner'))).scalar_one()
        session.add(AnalysisHistory(username=account.username,event_id='synthetic',provider='synthetic',
                                    solution_summary={},event_metadata={},search_results=[]))
        await session.commit()
        assert (await client.delete(f'/admin/users/{account.id}', headers=bearer('synthetic-admin'))).status_code == 200
        assert await history_owners(client, bearer()) == set()   # token of a deleted account never reads retained history
        r = await client.post('/admin/users', headers=bearer('synthetic-admin'), json={
            'username':'synthetic-owner','password':TEST_PASSWORD})
        assert r.status_code == 409
        assert (await session.execute(select(User).where(User.username=='synthetic-owner'))).scalar_one_or_none() is None
    integrated(check)


def test_orgwide_search_is_open_access_while_analysis_search_stays_owner_scoped(integrated, monkeypatch):
    """No-login contract: organization-wide providers answer the shared open-access identity (trusted deployment
    boundary is the control, not a user session). Analysis history is still owner-scoped."""
    from backend.domain.search.provider import SearchResult
    from backend.domain.search.providers.evaluation_provider import (
        EvaluationSearchProvider,
    )
    calls_to_private = []
    async def private(self, **kw):
        calls_to_private.append(True)
        return [SearchResult(type='evaluation',id='synthetic',title='SYNTHETIC_PRIVATE_ORG',
            subtitle='synthetic only',url='/evaluations/admin/synthetic',timestamp=None,relevance=1.0)]
    monkeypatch.setattr(EvaluationSearchProvider, 'search', private)
    async def check(client, session, calls):
        query = '/global/api/v1/search?q=SYNTHETIC_PRIVATE_ORG'
        for headers in ({}, bearer(), {'Authorization': 'Bearer tampered'}):
            calls_to_private.clear()
            r = await client.get(query+'&type=evaluation', headers=headers)
            assert r.status_code == 200 and 'SYNTHETIC_PRIVATE_ORG' in r.text and calls_to_private == [True]
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
        assert calls['export_attempts'] == 0  # analysis never publishes unreviewed knowledge
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


@pytest.mark.parametrize('headers', [{}, {'Authorization': 'Bearer invalid'}, bearer(exp=datetime.now(UTC)-timedelta(seconds=5))])
def test_missing_invalid_and_expired_tokens_resolve_to_open_access_never_to_the_owner(integrated, headers):
    async def check(client, session, calls):
        await seed_owner_history(session)
        r = await client.get('/history/', headers=headers)
        assert r.status_code == 200
        assert 'postgres' not in r.text.lower() and 'traceback' not in r.text.lower()
        assert r.json() == []   # never the named owner's rows; the open-access identity has none
        s = await client.get('/auth/session', headers=headers)
        assert s.json()['username'] == 'demo' and s.json()['application_login'] is False
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


def test_retired_login_and_admin_gate_follow_current_account_state(integrated):
    async def check(client, session, calls):
        await seed_owner_history(session)
        assert (await client.post('/auth/login', json={'username':'synthetic-owner','password':'wrong'})).status_code == 410
        headers = bearer()
        assert (await client.get('/auth/session', headers=headers)).json()['username'] == 'synthetic-owner'
        assert await history_owners(client, headers) == {'synthetic-owner'}
        tampered = {'Authorization': headers['Authorization'][:-5] + 'wrong'}
        assert await history_owners(client, tampered) == set()      # bad signature never yields the owner
        admin_headers = bearer('synthetic-admin', role='admin')
        # Explicit admin operations keep their real policy (not an application-login artefact).
        assert (await client.get('/admin/users')).status_code == 401
        assert (await client.get('/admin/users', headers=bearer())).status_code == 403
        assert (await client.get('/admin/users', headers=admin_headers)).status_code == 200
        account = (await session.execute(select(User).where(User.username=='synthetic-admin'))).scalars().one()
        account.role = 'user'
        await session.commit()
        assert (await client.get('/admin/users', headers=admin_headers)).status_code == 403   # JWT role claim is not trusted
        account = (await session.execute(select(User).where(User.username=='synthetic-owner'))).scalars().one()
        await session.delete(account)
        await session.commit()
        assert await history_owners(client, headers) == set()
    integrated(check)


@pytest.mark.parametrize('mode', ['demo', 'secure'])
def test_open_access_identity_is_honest_and_independent_of_auth_mode(integrated, monkeypatch, mode):
    monkeypatch.setattr(auth.settings, 'AUTH_MODE', mode)
    async def check(client, session, calls):
        assert (await client.get('/auth/session')).json() == {
            'username':'demo','mode':'open_access','application_login':False,'capabilities':{'knowledge_review':False}}
        assert (await client.get('/history/')).status_code == 200
        # A caller presenting no credential is never treated as a verified human.
        assert (await client.post('/auth/login', json={'username':'demo','password':'x'})).status_code == 410
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


def test_org_routes_are_open_access_and_invalid_tokens_never_elevate(integrated):
    """Approved no-login contract: organization-wide Portal reads are served to the shared open-access identity;
    a presented-but-invalid token does not change that (and is not an error)."""
    async def check(client, session, calls):
        created=await client.post('/api/v1/evaluations/sessions',headers=bearer('synthetic-admin'),
            json={'title':'SYNTHETIC_PRIVATE','customer_name':'synthetic-customer'})
        assert created.status_code==201,created.text
        sid=created.json()['session_id']
        paths=['/api/v1/assets','/api/v1/audit-logs',
               '/api/v1/evaluations/sessions',
               f'/api/v1/evaluations/sessions/{sid}', f'/api/v1/evaluations/sessions/{sid}/responses']
        for headers in (bearer(),bearer('synthetic-other'),{},{'Authorization':'Bearer tampered'}):
            for path in paths:
                r=await client.get(path,headers=headers)
                assert r.status_code==200,(path,r.status_code,r.text)
                assert 'traceback' not in r.text.lower()
    integrated(check)


def test_auth_retention_preserves_active_rows_and_history_and_rolls_back(integrated, monkeypatch):
    from backend.domain.analyzer.services.session_maintenance import (
        cleanup_auth_records,
    )
    async def check(client, session, calls):
        now = datetime.now(UTC)
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
            await cleanup_auth_records(session,retention_seconds=7*86400,now=now,dry_run=False)
        monkeypatch.setattr(session,'execute',original_execute)
        assert await session.get(AnalyzerSession,session_security.digest('synthetic-session-synthetic-other')) is not None
        await session.commit()
        preview=await cleanup_auth_records(session,retention_seconds=7*86400,batch_size=1,now=now,dry_run=True)
        assert preview == {'analyzer_sessions':1,'analyzer_login_windows':1}
        assert await session.get(LoginWindow,'synthetic-expired-window') is not None
        await session.commit()
        counts=await cleanup_auth_records(session,retention_seconds=7*86400,batch_size=1,now=now,dry_run=False)
        assert counts == {'analyzer_sessions':1,'analyzer_login_windows':1}
        assert await session.get(LoginWindow,'synthetic-live-window') is not None
        assert (await client.get('/history/',headers=bearer())).status_code == 200
    integrated(check)


async def mint_session(engine, name):
    """Issue a server-side session + bound token directly (the application /auth/login endpoint is retired)."""
    sid = secrets.token_urlsafe(24)
    now = datetime.now(UTC)
    async with AsyncSession(engine) as db:
        user = (await db.execute(select(User).where(User.username == name))).scalar_one()
        db.add(AnalyzerSession(id=session_security.digest(sid), user_id=user.id, username=name,
                               credential_version=session_security.digest(user.password),
                               created_at=now, last_seen=now, expires_at=now + timedelta(minutes=10)))
        await db.commit()
    return {'Authorization': 'Bearer ' + auth.create_access_token(name, 'user', sid)}


async def bind_live_identity(engine, monkeypatch):
    """Prove which database/role this rehearsal really talks to, then bind it for the destructive-path gate."""
    from sqlalchemy import text
    async with engine.connect() as conn:
        db_name, role = (await conn.execute(text('SELECT current_database(), current_user'))).first()
        marker = (await conn.execute(text(
            "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = current_database()"))).scalar()
        is_super = (await conn.execute(text('SELECT rolsuper FROM pg_roles WHERE rolname = current_user'))).scalar()
    assert marker == 'EIMS_DISPOSABLE_TEST_DB' and not is_super and role != 'postgres', 'database is not provably disposable'
    monkeypatch.setenv('EIMS_DB_IDENTITY', f'{db_name}|{role}')


def _required_test_url() -> str:
    value = os.environ.get("EIMS_TEST_DATABASE_URL")
    if not value:
        pytest.skip("EIMS_TEST_DATABASE_URL not configured; disposable PostgreSQL required")
    return value


def test_actual_auth_migration_reconnect_and_concurrent_maintenance(monkeypatch):
    """Execute the actual Alembic revision in a fresh retained synthetic schema.

    No downgrade/drop: generated test-only auth rows remain for inspection. The
    operational URL cannot pass dedicated_url. The old application data is not used.
    """
    configure_migration_test_auth(monkeypatch)
    import uuid

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect, text

    from backend.domain.analyzer.services.session_maintenance import (
        cleanup_auth_records,
    )
    async def check():
        url=dedicated_url(_required_test_url())
        schema='eims_rehearsal_'+uuid.uuid4().hex
        engine=create_async_engine(url)
        try:
            # Create only the isolated namespace in a short transaction. Alembic
            # must own its migration transaction because later revisions use
            # PostgreSQL autocommit blocks for CREATE INDEX CONCURRENTLY.
            async with engine.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA {schema}'))  # generated identifier only
            async with engine.connect() as conn:
                extension_schemas=(await conn.execute(text("SELECT DISTINCT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname IN ('vector','pg_trgm') ORDER BY n.nspname"))).scalars().all()
                suffix=''.join(', '+conn.dialect.identifier_preparer.quote(name) for name in extension_schemas)
                await conn.execute(text(f'SET search_path TO {schema}{suffix}'))
                await conn.commit()
                def migrate(c):
                    config=Config()
                    config.set_main_option('script_location','migrations')
                    config.attributes.update(connection=c,version_table_schema=schema)
                    command.upgrade(config,'8a2b4d6f9c1e')
                    assert c.scalar(text(f'SELECT version_num FROM {schema}.alembic_version'))=='8a2b4d6f9c1e'
                    assert not inspect(c).has_table('analyzer_sessions',schema=schema)
                    # Inspection starts SQLAlchemy autobegin; close it before the
                    # next Alembic invocation, whose revisions use autocommit DDL.
                    c.commit()
                    command.upgrade(config,'head')
                    assert c.scalar(text(f'SELECT version_num FROM {schema}.alembic_version'))==_alembic_head()
                    assert {i['name'] for i in inspect(c).get_indexes('analyzer_sessions',schema=schema)} == {
                        'ix_analyzer_sessions_user_id','ix_analyzer_sessions_expires_at'}
                    assert inspect(c).has_table('analyzer_login_windows',schema=schema)
                    assert inspect(c).has_table('telemetry_alert_outbox',schema=schema)
                await conn.run_sync(migrate)
        finally:
            await engine.dispose()
        def new_engine():
            return create_async_engine(url,connect_args={'server_settings':{'search_path':schema}})
        engine=new_engine()
        try:
            await bind_live_identity(engine, monkeypatch)
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
                assert (await client.post('/auth/login',json={'username':'synthetic-migration','password':TEST_PASSWORD})).status_code==410
                headers=await mint_session(engine,'synthetic-migration')
                assert (await client.get('/auth/session',headers=headers)).json()['username']=='synthetic-migration'
                await engine.dispose()  # new physical connections, not ORM identity reuse
                engine=new_engine()
                assert (await client.get('/auth/session',headers=headers)).json()['username']=='synthetic-migration'
                assert (await client.post('/auth/logout',headers=headers)).status_code==200
                assert (await client.get('/auth/session',headers=headers)).json()['username']=='demo'   # revoked: no identity kept
                await mint_session(engine,'synthetic-migration')
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
                db.add(LoginWindow(id='synthetic-old-window',attempts=1,started_at=datetime.now(UTC)-timedelta(days=8)))
                await db.commit()
            async with AsyncSession(engine) as lock, AsyncSession(engine) as worker:
                await lock.execute(select(LoginWindow).where(LoginWindow.id=='synthetic-old-window').with_for_update())
                assert (await cleanup_auth_records(worker,retention_seconds=7*86400,dry_run=False))['analyzer_login_windows']==0
                await lock.rollback()
                assert (await cleanup_auth_records(worker,retention_seconds=7*86400,dry_run=False))['analyzer_login_windows']==1
                # Both migration-issued sessions remain: revoked retention is not yet elapsed.
                assert await worker.scalar(select(func.count()).select_from(AnalyzerSession))==2
        finally:
            await engine.dispose()
    asyncio.run(check())


@pytest.mark.parametrize("state, expected", [("revoked",401),("expired",401),("demoted",403)])
def test_admin_operations_recheck_current_session_and_role_on_every_request(integrated, state, expected):
    """A revoked/expired session or a demoted account loses admin operations immediately. Ordinary Portal reads stay
    open-access (no-login contract) and neither succeed nor fail because of the stale admin credential."""
    async def check(client, session, calls):
        headers=bearer('synthetic-admin')
        assert (await client.get('/admin/users',headers=headers)).status_code==200
        if state=='demoted':
            user=(await session.execute(select(User).where(User.username=='synthetic-admin'))).scalar_one()
            user.role='user'
        else:
            row=await session.get(AnalyzerSession,session_security.digest('synthetic-session-synthetic-admin'))
            if state=='revoked': row.revoked_at=datetime.now(UTC)
            else: row.expires_at=datetime.now(UTC)-timedelta(minutes=1)
        await session.commit()
        assert (await client.get('/admin/users',headers=headers)).status_code==expected
        assert (await client.get('/api/v1/assets',headers=headers)).status_code==200
    integrated(check)


def test_full_migration_lineage_from_empty_isolated_schema():
    if not os.environ.get('EIMS_TEST_DATABASE_URL'):
        pytest.skip('Dedicated synthetic PostgreSQL URL not configured; no operational fallback')
    import uuid

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect, text
    async def check():
        schema='eims_full_lineage_'+uuid.uuid4().hex
        engine=create_async_engine(dedicated_url(_required_test_url()))
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA {schema}'))
            async with engine.connect() as conn:
                extension_schemas=(await conn.execute(text("SELECT DISTINCT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname IN ('vector','pg_trgm') ORDER BY n.nspname"))).scalars().all()
                suffix=''.join(', '+conn.dialect.identifier_preparer.quote(name) for name in extension_schemas)
                await conn.execute(text(f'SET search_path TO {schema}{suffix}'))
                await conn.commit()
                def migrate(c):
                    assert inspect(c).get_table_names(schema=schema)==[]
                    # Inspector queries autobegin on the caller-owned connection.
                    # Alembic must enter with no external transaction so its
                    # autocommit_block can manage CREATE INDEX CONCURRENTLY.
                    c.commit()
                    config=Config(); config.set_main_option('script_location','migrations')
                    config.attributes.update(connection=c,version_table_schema=schema)
                    command.upgrade(config,'head')
                    assert c.scalar(text(f'SELECT version_num FROM {schema}.alembic_version'))==_alembic_head()
                    assert {'users','analysis_history','analyzer_sessions','analyzer_login_windows',
                            'infrastructure_assets','service_sessions','service_evaluations',
                            'telemetry_metrics','windows_event_logs','telemetry_alert_outbox','knowledge_entries','knowledge_usage',
                            'knowledge_lifecycle_events','knowledge_source_candidates','knowledge_source_events'}.issubset(
                                set(inspect(c).get_table_names(schema=schema)))
                    knowledge_columns = {column['name'] for column in inspect(c).get_columns('knowledge_entries', schema=schema)}
                    assert {'product_name', 'product_version', 'environment', 'prerequisites', 'risk_level',
                            'validation_steps', 'rollback_steps', 'lifecycle_state', 'lifecycle_reason',
                            'lifecycle_updated_at', 'superseded_by_id'} <= knowledge_columns
                    user_columns = {column['name'] for column in inspect(c).get_columns('users', schema=schema)}
                    assert 'knowledge_reviewer' in user_columns
                await conn.run_sync(migrate)
        finally:
            await engine.dispose()
    asyncio.run(check())


def test_populated_parent_upgrade_preserves_history_ownership_and_sessions(monkeypatch):
    """Real parent revision and synthetic rows; no operational URL or reset."""
    configure_migration_test_auth(monkeypatch)
    import uuid

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    async def check():
        schema='eims_populated_'+uuid.uuid4().hex
        url=dedicated_url(_required_test_url())
        engine=create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA {schema}'))
            async with engine.connect() as conn:
                extension_schemas=(await conn.execute(text("SELECT DISTINCT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname IN ('vector','pg_trgm') ORDER BY n.nspname"))).scalars().all()
                suffix=''.join(', '+conn.dialect.identifier_preparer.quote(name) for name in extension_schemas)
                await conn.execute(text(f'SET search_path TO {schema}{suffix}'))
                await conn.commit()
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
                await conn.commit()
                await conn.run_sync(lambda c:migrate(c,'head'))
                after=(await conn.execute(text('SELECT row_to_json(h)::text FROM analysis_history h ORDER BY id'))).scalars().all()
                import json as _json
                for old_row, new_row in zip(before, after):
                    old_row, new_row = _json.loads(old_row), _json.loads(new_row)
                    added = set(new_row) - set(old_row)
                    assert added <= {'asset_id'} and all(new_row[k] is None for k in added), added   # additive nullable columns only
                    assert {k: new_row[k] for k in old_row} == old_row
                assert len(after)==len(before)==2
                assert await conn.scalar(text(f'SELECT version_num FROM {schema}.alembic_version'))==_alembic_head()
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
                    assert (await client.post('/auth/login',json={'username':name,'password':TEST_PASSWORD})).status_code==410
                    headers=await mint_session(engine,name)
                    rows=await client.get('/history/',headers=headers)
                    assert rows.status_code==200,rows.text
                    assert len(rows.json())==1 and rows.json()[0]['username']==name
                    await engine.dispose();engine=reconnect()
                    assert (await client.get('/auth/session',headers=headers)).json()['username']==name
                    assert (await client.post('/auth/logout',headers=headers)).status_code==200
                    assert (await client.get('/auth/session',headers=headers)).json()['username']=='demo'
            async with engine.connect() as conn:
                final=(await conn.execute(text('SELECT row_to_json(h)::text FROM analysis_history h ORDER BY id'))).scalars().all()
                assert final==after   # session activity changes nothing in history
        finally:
            await engine.dispose()
    asyncio.run(check())

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

@pytest.mark.parametrize('language',['th','en'])
@pytest.mark.parametrize('cid',['win_policy','esxi_tracker','fort_config'])
def test_priority_metadata_and_citation_postgres_roundtrip(integrated,language,cid):
    from evaluation.analyzer import runner
    _,payloads=runner.load_manifest(runner.REPO/'evaluation/analyzer/gold/manifest.v1.json')
    raw=next(iter(payloads[cid].values()))[0]
    async def check(client,session,calls):
        response=await client.post('/analyze/',headers=bearer(),data={'language':language},files={'file':('input.txt',raw,'text/plain')})
        assert response.status_code==200,response.text
        saved=response.json();meta=saved['eventMetadata'];s=saved['solutionSummary']
        if cid=='win_policy':
            assert meta['diagnosticCode']=='WINDOWS-GROUP-POLICY-CONNECTIVITY'
            assert 'UNKNOWN' in ' '.join(s['causes'])
        elif cid=='esxi_tracker':
            assert meta['level']=='Error' and meta['isCritical']
            assert 'UNKNOWN' in ' '.join(s['causes'])
        else:
            assert not meta['isCritical'] and not s['causes']
            item=s['evidenceItems'][0]
            assert item['sourceFile']=='input.txt' and item['lineNumber']==1
            assert item['message']==raw.decode().strip()
        session.expunge_all()
        rows=(await client.get('/history/',headers=bearer())).json()
        assert rows[0]['solutionSummary']==s
        assert rows[0]['eventMetadata']==meta and rows[0]['aiSummary']==saved['aiSummary']
        assert (await client.get('/history/',headers=bearer('synthetic-other'))).json()==[]
    integrated(check)
@pytest.mark.parametrize('kind,status', [('empty_text',400),('empty_file',400),('invalid_utf8',400),('oversize',413)])
def test_single_input_rejects_invalid_without_success_or_history(integrated,kind,status):
    async def check(client,session,calls):
        if kind=='empty_text':
            payload={'data':{'text':' \n\t '}}
        else:
            raw={'empty_file':b'', 'invalid_utf8':b'\xff\xfe\xff', 'oversize':b'x'*(5*1024*1024+1)}[kind]
            payload={'files':{'file':('invalid.txt',raw,'text/plain')}}
        response=await client.post('/analyze/',headers=bearer(),**payload)
        assert response.status_code==status,response.text
        assert response.json().get('detail')
        assert (await client.get('/history/',headers=bearer())).json()==[]
        assert calls['export_attempts']==0
    integrated(check)


@pytest.mark.parametrize('cid',['fort_config','esxi_tracker','win_policy'])
@pytest.mark.parametrize('language',['th','en'])
def test_paste_text_and_attach_file_preserve_same_diagnosis(integrated,cid,language):
    from evaluation.analyzer import runner
    _,payloads=runner.load_manifest(runner.REPO/'evaluation/analyzer/gold/manifest.v1.json')
    raw=next(iter(payloads[cid].values()))[0]
    async def check(client,session,calls):
        pasted=await client.post('/analyze/',headers=bearer(),data={'text':raw.decode(),'language':language})
        attached=await client.post('/analyze/',headers=bearer(),data={'language':language},files={'file':('input.txt',raw,'text/plain')})
        assert pasted.status_code==attached.status_code==200
        a,b=pasted.json(),attached.json()
        for key in ['eventId','diagnosticCode','level','timestamp','sourceFamily','isCritical']:
            assert a['eventMetadata'][key]==b['eventMetadata'][key]
        for key in ['overview','causes','steps','limitations']:
            assert a['solutionSummary'][key]==b['solutionSummary'][key]
        for result in [a,b]:
            assert result['historyId']
            assert result['solutionSummary']['evidenceItems']
        session.expunge_all()
        rows=(await client.get('/history/',headers=bearer())).json()
        for result in [a,b]:
            row=next(r for r in rows if r['id']==result['historyId'])
            assert row['solutionSummary']==result['solutionSummary']
        assert (await client.get('/history/',headers=bearer('synthetic-other'))).json()==[]
    integrated(check)


@pytest.mark.parametrize('name,mime,raw', [
    ('input.xml','application/xml',b'<Event>\xff</Event>'),
    ('input.html','text/html',b'<p>\xff</p>'),
    ('input.csv','text/csv',b'event,message\n1,\xff'),
    ('input.log','text/plain',b'Event ID: 1129\x00binary'),
    ('input.png','text/plain',b'Event ID: 1129'),
])
def test_single_upload_rejects_misidentified_content(integrated,name,mime,raw):
    async def check(client,session,calls):
        response=await client.post('/analyze/',headers=bearer(),files={'file':(name,raw,mime)})
        assert response.status_code==400,response.text
        assert (await client.get('/history/',headers=bearer())).json()==[]
        assert calls['export_attempts']==0
    integrated(check)


def test_single_image_missing_ocr_is_error_without_history(integrated,monkeypatch):
    import io

    import pytesseract
    from PIL import Image
    def unavailable(*args,**kwargs):
        raise pytesseract.TesseractNotFoundError()
    monkeypatch.setattr(pytesseract,'image_to_string',unavailable)
    stream=io.BytesIO()
    Image.new('RGB',(1000,10),'white').save(stream,format='PNG')
    async def check(client,session,calls):
        response=await client.post('/analyze/',headers=bearer(),files={'file':('image.png',stream.getvalue(),'image/png')})
        assert response.status_code==400,response.text
        assert 'Tesseract' in response.json()['detail']
        assert (await client.get('/history/',headers=bearer())).json()==[]
        assert calls['export_attempts']==0
    integrated(check)


def test_history_pagination_and_sql_aggregates_are_bounded_and_user_scoped(integrated):
    async def check(client, session, calls):
        now = datetime.now(UTC).replace(tzinfo=None)
        session.add_all([
            AnalysisHistory(
                username='synthetic-owner', event_id=event_id,
                provider='Microsoft-Windows-Security-Auditing',
                event_metadata={
                    'isCritical': critical,
                    'sourceFamily': 'windows_event',
                    'diagnosticCode': event_id,
                },
                search_time_ms=search_ms,
                created_at=now - timedelta(days=days_ago),
            )
            for event_id, critical, search_ms, days_ago in (
                ('4625', True, 1000, 0),
                ('4624', False, 2000, 1),
                ('1102', False, 3000, 2),
            )
        ])
        session.add(AnalysisHistory(
            username='synthetic-other', event_id='4625', provider='private-provider',
            event_metadata={'isCritical': True, 'sourceFamily': 'windows_event', 'diagnosticCode': '4625'},
            search_time_ms=9000,
        ))
        await session.flush()

        first_page = await client.get('/history/?limit=2&offset=0', headers=bearer())
        second_page = await client.get('/history/?limit=2&offset=2', headers=bearer())
        assert first_page.status_code == 200 and len(first_page.json()) == 2
        assert second_page.status_code == 200 and len(second_page.json()) == 1
        assert [row['eventId'] for row in first_page.json()] == ['4625', '4624']
        assert second_page.json()[0]['eventId'] == '1102'
        assert (await client.get('/history/?limit=201', headers=bearer())).status_code == 422
        other_history = await client.get('/history/', headers=bearer('synthetic-other'))
        assert other_history.status_code == 200
        assert len(other_history.json()) == 1
        assert other_history.json()[0]['provider'] == 'private-provider'

        stats_response = await client.get('/history/stats', headers=bearer())
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        assert stats_data['totalLogs'] == 3
        assert stats_data['criticalErrors'] == 1
        assert stats_data['avgSearchTimeSec'] == 2.0
        assert {row['name']: row['value'] for row in stats_data['categoryStats']} == {
            'Authentication': 2, 'Security': 1,
        }
        assert sum(row['count'] for row in stats_data['dailyTrends']) == 3
        assert sum(row['value'] for row in stats_data['providerStats']) == 3

        other_stats = await client.get('/history/stats', headers=bearer('synthetic-other'))
        assert other_stats.status_code == 200
        assert other_stats.json()['totalLogs'] == 1
        public_catalog = await client.get('/history/catalog')
        assert public_catalog.status_code == 200
        assert public_catalog.headers.get('cache-control', '').startswith('public, max-age=300')

    integrated(check)


def test_verified_knowledge_requires_owner_proposal_and_independent_admin_review(integrated):
    async def check(client, session, calls):
        source = AnalysisHistory(
            event_id="FGT-9001",
            provider="Fortinet",
            description="Synthetic private source log; never copied into shared knowledge.",
            ai_summary="Synthetic summary",
            solution_summary={"overview": "Synthetic initial analysis", "steps": ["Inspect policy"]},
            event_metadata={"sourceFamily": "fortinet", "diagnosticCode": "FGT-9001"},
            username="synthetic-owner",
        )
        session.add(source)
        await session.flush()
        payload = {
            "history_id": source.id,
            "title": "FortiGate policy lookup failure",
            "resolution_status": "resolved",
            "root_cause": "The service account lacked the policy-read permission.",
            "solution_steps": [
                "Confirm the service account mapped to the affected FortiGate administrator profile.",
                "Grant the minimum required policy-read permission and retest the API call.",
            ],
            "impact": "Policy inventory was incomplete for this collection run.",
            "prevention": "Add a least-privilege permission check to the deployment checklist.",
            "product_name": "FortiGate",
            "product_version": "7.4.x",
            "environment": "On-prem production",
            "prerequisites": ["Confirm the maintenance window and administrator access."],
            "risk_level": "high",
            "validation_steps": ["Run the policy inventory API and verify the expected rule count."],
            "rollback_steps": ["Revert the temporary permission grant and restore the previous administrator profile."],
            "evidence_notes": ["Synthetic request returned permission denied for the policy-read operation."],
            "references": ["https://docs.fortinet.com/"],
        }

        created = await client.post("/knowledge/proposals", headers=bearer(), json=payload)
        assert created.status_code == 201, created.text
        proposal = created.json()
        assert proposal["status"] == "pending"
        assert proposal["sourceFamily"] == "fortinet"
        assert proposal["diagnosticIdentity"] == "FGT-9001"
        unsafe_payload = {**payload, "rollback_steps": []}
        unsafe = await client.post("/knowledge/proposals", headers=bearer(), json=unsafe_payload)
        assert unsafe.status_code == 422
        assert proposal["productName"] == "FortiGate" and proposal["productVersion"] == "7.4.x"
        assert proposal["environment"] == "On-prem production" and proposal["riskLevel"] == "high"
        assert proposal["prerequisites"] and proposal["validationSteps"] and proposal["rollbackSteps"]
        assert len(proposal["sourceHistoryHash"]) == 64
        assert proposal["sourceHistoryId"] == source.id
        retained = await client.delete(f"/history/{source.id}", headers=bearer())
        assert retained.status_code == 409

        # Private raw input is not returned in either the proposal or the shared list.
        assert "Synthetic private source log" not in created.text
        # Both canonical forms are accepted; the BFF intentionally rejects redirects.
        assert (await client.get("/knowledge", headers=bearer())).status_code == 200
        assert (await client.get("/knowledge/", headers=bearer())).status_code == 200
        # The shared KB may already contain approved knowledge for other identities.
        # Assert absence only for this exact family/diagnostic, not a globally empty KB.
        scoped_empty = await client.get(
            "/knowledge/?source_family=fortinet&diagnostic_identity=FGT-9001",
            headers=bearer(),
        )
        assert scoped_empty.status_code == 200 and scoped_empty.json()["items"] == []
        pending_search = await client.get("/knowledge/?q=policy-read%20permission", headers=bearer())
        assert pending_search.status_code == 200 and pending_search.json()["items"] == []

        # Owner scoping applies to proposal creation and personal proposal lists.
        other_create = await client.post(
            "/knowledge/proposals", headers=bearer("synthetic-other"), json=payload
        )
        assert other_create.status_code == 404
        mine = await client.get("/knowledge/proposals/mine", headers=bearer())
        assert mine.status_code == 200 and [x["id"] for x in mine.json()["items"]] == [proposal["id"]]
        other_mine = await client.get("/knowledge/proposals/mine", headers=bearer("synthetic-other"))
        assert other_mine.status_code == 200 and other_mine.json()["items"] == []

        # A non-admin cannot review; an admin cannot review their own proposal.
        denied = await client.post(
            f"/knowledge/{proposal['id']}/review",
            headers=bearer(),
            json={"decision": "approve", "note": "Synthetic independent review note."},
        )
        assert denied.status_code == 403
        self_review = await client.post(
            f"/knowledge/{proposal['id']}/review",
            headers=bearer("synthetic-owner"),
            json={"decision": "approve", "note": "Synthetic independent review note."},
        )
        assert self_review.status_code == 403

        queue = await client.get("/knowledge/review-queue", headers=bearer("synthetic-admin"))
        assert queue.status_code == 200
        queue_ids = [x["id"] for x in queue.json()["items"]]
        assert proposal["id"] in queue_ids
        assert all(item["status"] == "pending" for item in queue.json()["items"])

        missing_review_note = await client.post(
            f"/knowledge/{proposal['id']}/review",
            headers=bearer("synthetic-admin"),
            json={"decision": "approve"},
        )
        assert missing_review_note.status_code == 422

        original_description = source.description
        source.description = original_description + " Synthetic post-proposal tampering."
        await session.commit()
        tampered_source_approval = await client.post(
            f"/knowledge/{proposal['id']}/review",
            headers=bearer("synthetic-admin"),
            json={"decision": "approve", "note": "Independent review attempted against changed source."},
        )
        assert tampered_source_approval.status_code == 409
        source.description = original_description
        await session.commit()

        approved = await client.post(
            f"/knowledge/{proposal['id']}/review",
            headers=bearer("synthetic-admin"),
            json={"decision": "approve", "note": "Reproduced and checked against the source evidence."},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"
        assert approved.json()["reviewedBy"] == "synthetic-admin"

        published = await client.get(
            "/knowledge/?source_family=fortinet&diagnostic_identity=FGT-9001",
            headers=bearer("synthetic-other"),
        )
        assert published.status_code == 200
        assert len(published.json()["items"]) == 1
        public_entry = published.json()["items"][0]
        assert "sourceHistoryId" not in public_entry
        assert public_entry["sourceHistoryHash"] == proposal["sourceHistoryHash"]
        assert "Synthetic private source log" not in published.text
        full_text = await client.get(
            "/knowledge/?q=minimum%20required%20policy-read%20permission",
            headers=bearer("synthetic-other"),
        )
        assert full_text.status_code == 200
        assert [item["id"] for item in full_text.json()["items"]] == [proposal["id"]]

        # A lifecycle review event immediately removes this entry from search and exact-identity reuse.
        require_review = await client.post(
            f"/knowledge/{proposal['id']}/lifecycle",
            headers=bearer("synthetic-admin"),
            json={
                "action": "require_review",
                "reason": "Vendor support status changed and applicability must be reconfirmed.",
                "note": "Pause automated reuse until the supported version range is checked.",
            },
        )
        assert require_review.status_code == 200, require_review.text
        assert require_review.json()["lifecycleState"] == "revalidation_required"
        stale_search = await client.get(
            "/knowledge/?q=minimum%20required%20policy-read%20permission",
            headers=bearer("synthetic-other"),
        )
        assert stale_search.status_code == 200 and stale_search.json()["items"] == []
        from backend.domain.analyzer.services.verified_knowledge import search_approved_knowledge
        assert await search_approved_knowledge(session, "fortinet", "FGT-9001") is None
        review_queue = await client.get(
            "/knowledge/lifecycle/review-queue",
            headers=bearer("synthetic-admin"),
        )
        assert review_queue.status_code == 200
        assert proposal["id"] in [item["id"] for item in review_queue.json()["items"]]

        revalidated = await client.post(
            f"/knowledge/{proposal['id']}/lifecycle",
            headers=bearer("synthetic-admin"),
            json={
                "action": "revalidate",
                "reason": "Vendor documentation confirms the recorded version and remediation remain applicable.",
                "note": "Checked official vendor guidance and repeated the validation procedure.",
            },
        )
        assert revalidated.status_code == 200, revalidated.text
        assert revalidated.json()["lifecycleState"] == "active"
        lifecycle_events = await client.get(
            f"/knowledge/{proposal['id']}/lifecycle/events",
            headers=bearer("synthetic-admin"),
        )
        assert lifecycle_events.status_code == 200
        assert [event["toState"] for event in lifecycle_events.json()["items"]] == [
            "revalidation_required", "active"
        ]

        outcome_history = AnalysisHistory(
            event_id="FGT-9002",
            provider="Fortinet",
            description="Synthetic follow-up incident after applying approved knowledge.",
            ai_summary="Synthetic follow-up analysis",
            solution_summary={"overview": "Synthetic repeat incident", "steps": ["Check policy permissions"]},
            event_metadata={"sourceFamily": "fortinet", "diagnosticCode": "FGT-9002"},
            username="synthetic-owner",
        )
        session.add(outcome_history)
        await session.flush()
        usage = await client.post(
            f"/knowledge/{proposal['id']}/usage",
            headers=bearer(),
            json={"history_id": outcome_history.id, "outcome": "resolved", "notes": "Synthetic validation confirmed the expected policy inventory."},
        )
        assert usage.status_code == 201, usage.text
        assert usage.json()["historyHash"] and usage.json()["outcome"] == "resolved"
        usage_summary = await client.get(f"/knowledge/{proposal['id']}/usage-summary", headers=bearer("synthetic-other"))
        assert usage_summary.status_code == 200
        assert usage_summary.json()["total"] == 1 and usage_summary.json()["outcomes"]["resolved"] == 1
        other_usage = await client.post(
            f"/knowledge/{proposal['id']}/usage",
            headers=bearer("synthetic-other"),
            json={"history_id": outcome_history.id, "outcome": "resolved"},
        )
        assert other_usage.status_code == 404
        duplicate_usage = await client.post(
            f"/knowledge/{proposal['id']}/usage",
            headers=bearer(),
            json={"history_id": outcome_history.id, "outcome": "resolved"},
        )
        assert duplicate_usage.status_code == 409

        # Secure-mode analysis can reuse only this approved exact-identity record.
        learned = await summary.build_summary(
            event_id="FGT-9001",
            provider="Fortinet",
            snippets="",
            results=[],
            language="en",
            description="Synthetic Fortinet policy read failure",
            db=session,
            source_family="fortinet",
            diagnostic_code="FGT-9001",
        )
        assert learned.overview == "The service account lacked the policy-read permission."
        assert learned.confidence == "high"
        assert any("minimum required policy-read permission" in step for step in learned.steps)
        assert any(step.startswith("Prerequisite:") for step in learned.steps)
        assert any(step.startswith("Validation:") for step in learned.steps)
        assert any(step.startswith("Rollback:") for step in learned.steps)
        assert any("On-prem production" in item for item in learned.limitations)
        assert any("risk level: high" in item for item in learned.limitations)

        # Exact source-family and diagnostic identity are mandatory.
        from backend.domain.analyzer.services.verified_knowledge import (
            search_approved_knowledge,
        )
        assert await search_approved_knowledge(session, "cisco_asa", "FGT-9001") is None
        assert await search_approved_knowledge(session, "fortinet", "FGT-OTHER") is None

        duplicate = await client.post("/knowledge/proposals", headers=bearer(), json=payload)
        assert duplicate.status_code == 409

        # Feedback is not approval and does not rewrite the immutable analysis.
        before_solution = dict(source.solution_summary)
        feedback_result = await client.post(
            f"/history/{source.id}/feedback?score=1", headers=bearer()
        )
        assert feedback_result.status_code == 200
        await session.refresh(source)
        assert source.solution_summary == before_solution
        assert (await session.execute(
            select(KnowledgeEntry).where(KnowledgeEntry.source_history_id == source.id)
        )).scalars().first().status == "approved"

    integrated(check)


def test_unresolved_knowledge_cannot_be_published_and_rejection_is_audited(integrated):
    async def check(client, session, calls):
        source = AnalysisHistory(
            event_id="ASA-UNRESOLVED-7",
            provider="Cisco ASA",
            description="Synthetic unresolved firewall incident.",
            ai_summary="No confirmed root cause",
            solution_summary={"overview": "Unresolved"},
            event_metadata={"sourceFamily": "cisco_asa", "diagnosticCode": "ASA-UNRESOLVED-7"},
            username="synthetic-owner",
        )
        session.add(source)
        await session.flush()
        payload = {
            "history_id": source.id,
            "title": "Unresolved ASA connection reset",
            "resolution_status": "unresolved",
            "root_cause": "The cause remains undetermined from the available evidence.",
            "solution_steps": ["Collect the adjacent firewall and upstream device events."],
            "evidence_notes": ["Synthetic trace shows reset but no matching deny record."],
        }
        created = await client.post("/knowledge/proposals", headers=bearer(), json=payload)
        assert created.status_code == 201
        entry_id = created.json()["id"]

        cannot_approve = await client.post(
            f"/knowledge/{entry_id}/review",
            headers=bearer("synthetic-admin"),
            json={"decision": "approve", "note": "Synthetic independent review note."},
        )
        assert cannot_approve.status_code == 422

        rejected = await client.post(
            f"/knowledge/{entry_id}/review",
            headers=bearer("synthetic-admin"),
            json={"decision": "reject", "note": "Insufficient evidence to establish a reusable fix."},
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"
        assert rejected.json()["reviewedBy"] == "synthetic-admin"
        assert rejected.json()["reviewedAt"]

        public = await client.get(
            "/knowledge/?source_family=cisco_asa&diagnostic_identity=ASA-UNRESOLVED-7",
            headers=bearer(),
        )
        assert public.status_code == 200 and public.json()["items"] == []

    integrated(check)


def test_knowledge_proposer_cannot_self_review_and_rejected_items_are_immutable(integrated):
    async def check(client, session, calls):
        source = AnalysisHistory(
            event_id="LINUX-SSHD-1",
            provider="Linux",
            description="Synthetic SSH authentication failure.",
            ai_summary="Synthetic",
            solution_summary={"overview": "Synthetic"},
            event_metadata={"sourceFamily": "linux_syslog", "diagnosticCode": "LINUX-SSHD-1"},
            username="synthetic-admin",
        )
        session.add(source)
        await session.flush()
        payload = {
            "history_id": source.id,
            "title": "SSH key permission mismatch",
            "resolution_status": "resolved",
            "root_cause": "The private key file permissions were broader than the SSH client permits.",
            "solution_steps": ["Restrict the private key file to owner read/write and retry."],
            "evidence_notes": ["Synthetic sshd trace reports an unprotected private key file."],
        }
        created = await client.post(
            "/knowledge/proposals", headers=bearer("synthetic-admin"), json=payload
        )
        assert created.status_code == 201
        denied = await client.post(
            f"/knowledge/{created.json()['id']}/review",
            headers=bearer("synthetic-admin"),
            json={"decision": "approve", "note": "Synthetic independent review note."},
        )
        assert denied.status_code == 409

    integrated(check)


def test_jwt_exp_is_required_and_enforced_independently_of_server_session(integrated):
    async def check(client, session, calls):
        live_session = await session.scalar(
            select(AnalyzerSession).where(
                AnalyzerSession.id == session_security.digest("synthetic-session-synthetic-owner")
            )
        )
        assert live_session is not None
        assert live_session.revoked_at is None
        assert live_session.expires_at > datetime.now(UTC)

        def token(exp=None, include_exp=True):
            payload = {
                "sub": "synthetic-owner",
                "sid": "synthetic-session-synthetic-owner",
            }
            if include_exp:
                payload["exp"] = exp
            return {"Authorization": "Bearer " + jwt.encode(payload, TEST_KEY, algorithm="HS256")}

        await seed_owner_history(session)
        future_exp = int(datetime.now(UTC).timestamp()) + 120
        accepted = await client.get("/history/", headers=token(future_exp))
        assert accepted.status_code == 200 and {x['username'] for x in accepted.json()} == {'synthetic-owner'}, accepted.text

        # RFC 7519: the token is invalid on and after its exp NumericDate.
        boundary_exp = int(datetime.now(UTC).timestamp())
        at_boundary = await client.get("/history/", headers=token(boundary_exp))
        assert at_boundary.status_code == 200 and at_boundary.json() == [], at_boundary.text

        expired = await client.get(
            "/history/",
            headers=token(int(datetime.now(UTC).timestamp()) - 30),
        )
        assert expired.status_code == 200 and expired.json() == [], expired.text

        missing_exp = await client.get("/history/", headers=token(include_exp=False))
        assert missing_exp.status_code == 200 and missing_exp.json() == [], missing_exp.text

        # The independent DB session is still valid; these failures are JWT-exp failures.
        await session.refresh(live_session)
        assert live_session.revoked_at is None
        assert live_session.expires_at > datetime.now(UTC)

    integrated(check)


def test_vendor_source_candidates_are_engineer_readable_and_reviewer_writable(integrated):
    async def check(client, session, calls):
        candidate = KnowledgeSourceCandidate(
            source_key="SYNTHETIC-MS-4625",
            vendor="Microsoft",
            product="Windows Security Auditing",
            version_scope="Synthetic Windows Server build range",
            domain="authentication",
            identity="Security Event ID 4625",
            title="Synthetic failed logon reference",
            source_url="https://learn.microsoft.com/windows/security/threat-protection/auditing/event-4625",
            applicability="Synthetic applicability statement for isolated integration test.",
            prerequisites=["Synthetic prerequisite: verify audit policy."],
            evidence=["Synthetic Status/SubStatus and LogonType evidence."],
            limitations=["A failed logon event alone is not root cause."],
            next_checks=["Correlate adjacent authentication events."],
            validation=["Confirm controlled authorized sign-in outcome."],
            rollback=["No source-directed change; restore only separately approved policy."],
            risk_level="low",
            evidence_status="official_source_verified",
            review_state="pending_domain_review",
            catalog_schema_version="1.0.0",
            source_hash="a" * 64,
            source_payload={"synthetic": True},
            imported_by="catalogue-import",
        )
        session.add(candidate)
        await session.flush()

        denied_list = await client.get("/knowledge/sources", headers=bearer())
        assert denied_list.status_code == 200
        admin_list = await client.get("/knowledge/sources?vendor=Microsoft", headers=bearer("synthetic-reviewer"))
        assert admin_list.status_code == 200, admin_list.text
        assert admin_list.json()["total"] == 1
        listed = admin_list.json()["items"][0]
        assert listed["sourceKey"] == "SYNTHETIC-MS-4625"
        assert listed["reviewState"] == "pending_domain_review"
        assert listed["catalogueRecordHash"] == "a" * 64

        denied_review = await client.post(
            f"/knowledge/sources/{candidate.id}/review",
            headers=bearer(),
            json={"decision": "verify_reference", "note": "Synthetic reviewer note with evidence."},
        )
        assert denied_review.status_code == 403

        verified = await client.post(
            f"/knowledge/sources/{candidate.id}/review",
            headers=bearer("synthetic-admin"),
            json={"decision": "verify_reference", "note": "Verified official source scope against the synthetic test evidence."},
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["reviewState"] == "verified_reference"
        assert verified.json()["reviewedBy"] == "synthetic-admin"

        # A verified vendor reference is still not an incident diagnosis or reusable KnowledgeEntry.
        assert await session.scalar(select(func.count()).select_from(KnowledgeEntry)) == 0

        events = await client.get(
            f"/knowledge/sources/{candidate.id}/events",
            headers=bearer("synthetic-admin"),
        )
        assert events.status_code == 200
        assert [item["toState"] for item in events.json()["items"]] == ["verified_reference"]

        revalidation = await client.post(
            f"/knowledge/sources/{candidate.id}/review",
            headers=bearer("synthetic-admin"),
            json={"decision": "require_revalidation", "note": "Synthetic version scope changed; recheck current vendor documentation."},
        )
        assert revalidation.status_code == 200
        assert revalidation.json()["reviewState"] == "revalidation_required"

        cannot_skip_review = await client.post(
            f"/knowledge/sources/{candidate.id}/review",
            headers=bearer("synthetic-admin"),
            json={"decision": "verify_reference", "note": "Rechecked current vendor build and confirmed source scope."},
        )
        assert cannot_skip_review.status_code == 200
        assert cannot_skip_review.json()["reviewState"] == "verified_reference"

        final_events = await client.get(
            f"/knowledge/sources/{candidate.id}/events",
            headers=bearer("synthetic-admin"),
        )
        assert [item["toState"] for item in final_events.json()["items"]] == [
            "verified_reference", "revalidation_required", "verified_reference"
        ]

    integrated(check)



def test_non_admin_knowledge_reviewer_capability_is_additive_and_self_review_stays_blocked(integrated):
    async def check(client, session, calls):
        candidate = KnowledgeSourceCandidate(
            source_key="SYNTHETIC-REVIEWER-CAPABILITY",
            vendor="Microsoft",
            product="Windows Security Auditing",
            version_scope="Synthetic integration fixture only",
            domain="authentication",
            identity="Security Event ID 4625",
            title="Synthetic reviewer capability reference",
            source_url="https://learn.microsoft.com/windows/security/threat-protection/auditing/event-4625",
            applicability="Synthetic test record only.",
            prerequisites=["Synthetic test prerequisite."],
            evidence=["Synthetic test evidence."],
            limitations=["Not a local incident diagnosis."],
            next_checks=["Inspect correlated events."],
            validation=["Validate with controlled synthetic sign-in."],
            rollback=["No remediation is authorized by this reference."],
            risk_level="low",
            evidence_status="official_source_verified",
            review_state="pending_domain_review",
            catalog_schema_version="1.0.0",
            source_hash="b" * 64,
            source_payload={"synthetic": True},
            imported_by="catalogue-import",
        )
        session.add(candidate)
        await session.flush()

        session_info = await client.get("/auth/session", headers=bearer("synthetic-reviewer"))
        assert session_info.status_code == 200
        assert session_info.json()["capabilities"]["knowledge_review"] is True
        assert (await client.get("/admin/users", headers=bearer("synthetic-reviewer"))).status_code == 403

        decision = await client.post(
            f"/knowledge/sources/{candidate.id}/review",
            headers=bearer("synthetic-reviewer"),
            json={"decision": "verify_reference", "note": "Synthetic reviewer confirmed source scope and limitations."},
        )
        assert decision.status_code == 200, decision.text
        assert decision.json()["reviewedBy"] == "synthetic-reviewer"

        history = await client.get(
            f"/knowledge/sources/{candidate.id}/events",
            headers=bearer("synthetic-owner"),
        )
        assert history.status_code == 200
        assert len(history.json()["items"]) == 1

    integrated(check)


def test_knowledge_reviewer_grant_revoke_are_audited_atomically(integrated):
    async def check(client, session, calls):
        reviewer = (await session.execute(
            select(User).where(User.username == "synthetic-reviewer")
        )).scalar_one()
        # The shared fixture starts reviewer=True; force a real grant transition.
        reviewer.knowledge_reviewer = False
        await session.flush()

        grant = await client.patch(
            f"/admin/users/{reviewer.id}/knowledge-reviewer",
            headers=bearer("synthetic-admin"),
            json={"enabled": True},
        )
        assert grant.status_code == 200, grant.text
        assert grant.json()["knowledge_reviewer"] is True

        grant_rows = (await session.execute(
            select(AuditLog).where(AuditLog.action_verb == "GRANT_KNOWLEDGE_REVIEWER")
        )).scalars().all()
        assert len(grant_rows) == 1
        grant_payload = grant_rows[0].immutable_payload
        assert grant_payload == {
            "event_type": "knowledge_reviewer_capability_changed",
            "actor_username": "synthetic-admin",
            "target_user_id": reviewer.id,
            "target_username": "synthetic-reviewer",
            "capability": "knowledge:review",
            "previous_enabled": False,
            "enabled": True,
        }

        # Repeating the same state is idempotent and must not fabricate another event.
        repeated = await client.patch(
            f"/admin/users/{reviewer.id}/knowledge-reviewer",
            headers=bearer("synthetic-admin"),
            json={"enabled": True},
        )
        assert repeated.status_code == 200
        assert await session.scalar(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.action_verb == "GRANT_KNOWLEDGE_REVIEWER"
            )
        ) == 1

        created = await client.post(
            "/admin/users",
            headers=bearer("synthetic-admin"),
            json={"username": "synthetic-created-reviewer", "password": TEST_PASSWORD,
                  "role": "user", "knowledge_reviewer": True},
        )
        assert created.status_code == 200, created.text
        assert created.json()["knowledge_reviewer"] is True
        all_grants = (await session.execute(
            select(AuditLog).where(AuditLog.action_verb == "GRANT_KNOWLEDGE_REVIEWER")
        )).scalars().all()
        created_grant = next(
            row for row in all_grants
            if row.immutable_payload.get("target_username") == "synthetic-created-reviewer"
        )
        assert created_grant.immutable_payload["grant_context"] == "account_created"

        admin_user = (await session.execute(
            select(User).where(User.username == "synthetic-admin")
        )).scalar_one()
        admin_revoke = await client.patch(
            f"/admin/users/{admin_user.id}/knowledge-reviewer",
            headers=bearer("synthetic-admin"), json={"enabled": False},
        )
        assert admin_revoke.status_code == 409

        revoke = await client.patch(
            f"/admin/users/{reviewer.id}/knowledge-reviewer",
            headers=bearer("synthetic-admin"),
            json={"enabled": False},
        )
        assert revoke.status_code == 200, revoke.text
        assert revoke.json()["knowledge_reviewer"] is False

        revoke_rows = (await session.execute(
            select(AuditLog).where(AuditLog.action_verb == "REVOKE_KNOWLEDGE_REVIEWER")
        )).scalars().all()
        assert len(revoke_rows) == 1
        assert revoke_rows[0].immutable_payload["actor_username"] == "synthetic-admin"
        assert revoke_rows[0].immutable_payload["target_username"] == "synthetic-reviewer"
        assert revoke_rows[0].immutable_payload["capability"] == "knowledge:review"
        assert revoke_rows[0].immutable_payload["previous_enabled"] is True
        assert revoke_rows[0].immutable_payload["enabled"] is False

        # A non-admin cannot grant or revoke capabilities.
        denied = await client.patch(
            f"/admin/users/{reviewer.id}/knowledge-reviewer",
            headers=bearer("synthetic-reviewer"),
            json={"enabled": True},
        )
        assert denied.status_code == 403

    integrated(check)


def test_single_analysis_and_history_carry_server_assigned_knowledge_match(integrated):
    """Route-level: trust level is set by the server, persisted, and survives reopen."""
    async def check(client, session, calls):
        text = ('Log Name: System\nSource: Microsoft-Windows-GroupPolicy\nEvent ID: 1129\nLevel: Error\n'
                'Description: The processing of Group Policy failed because of lack of network connectivity.\n')
        r = await client.post('/analyze/', headers=bearer(), data={'language': 'en'},
                              files={'file': ('gp.txt', text.encode(), 'text/plain')})
        assert r.status_code == 200, r.text
        saved = r.json()
        match = saved['solutionSummary']['knowledgeMatch']
        assert match['classification'] == 'context_match', match
        assert match['catalogId'] == 'windows_event:official_event_id:1129'
        session.expunge_all()
        rows = (await client.get('/history/', headers=bearer())).json()
        assert rows[0]['solutionSummary']['knowledgeMatch'] == match
    integrated(check)


def test_bundle_analysis_carries_knowledge_match_for_the_primary_identity(integrated):
    async def check(client, session, calls):
        files = [('files', (name, raw, 'text/plain')) for name, (raw, _) in hero_inputs().items()]
        r = await client.post('/analyze/bundle', headers=bearer(), data={'language': 'en'}, files=files)
        assert r.status_code == 200, r.text
        saved = r.json()
        match = saved['solutionSummary']['knowledgeMatch']
        assert match is not None, 'bundle response must carry a server-assigned knowledgeMatch'
        # An unreviewed catalog candidate can never be reported as trusted.
        assert match['classification'] in ('diagnostic_candidate_match', 'context_match', 'no_verified_match')
        assert match['classification'] not in ('approved_diagnostic_match', 'version_compatible_match',
                                               'validated_diagnostic_match', 'source_verified_match')
        session.expunge_all()
        rows = (await client.get('/history/', headers=bearer())).json()
        assert rows[0]['solutionSummary']['knowledgeMatch'] == match
    integrated(check)


def test_obsidian_export_is_owner_scoped_and_writes_only_inside_the_vault(integrated, tmp_path, monkeypatch):
    from backend.domain.analyzer.services import obsidian
    monkeypatch.setattr(obsidian, 'VAULT_PATH', str(tmp_path / 'vault'))
    async def check(client, session, calls):
        row = AnalysisHistory(username='synthetic-owner', event_id='../1129', provider='synthetic',
                              description='SYNTHETIC', solution_summary={'overview': 'o'}, event_metadata={}, search_results=[])
        session.add(row)
        await session.commit()
        body = {'history_id': row.id}
        assert (await client.post('/export/obsidian/export', headers=bearer('synthetic-other'), json=body)).status_code == 404
        assert (await client.post('/export/obsidian/export', json=body)).status_code == 404            # open-access 'demo' is not the owner
        ok = await client.post('/export/obsidian/export', headers=bearer(), json=body)
        assert ok.status_code == 200, ok.text
        import os
        assert os.path.dirname(os.path.realpath(ok.json()['filepath'])) == os.path.realpath(str(tmp_path / 'vault'))
    integrated(check)
