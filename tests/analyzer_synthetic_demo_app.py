"""TEST HARNESS ONLY: real HTTP/DB transport, no operational app startup.

Launch explicitly with EIMS_TEST_DATABASE_URL and uvicorn on loopback. Uses
synthetic JWT keys, real auth verification and a dedicated test database only.
Do not deploy or use with company data. Only named synthetic fixture accounts
in the dedicated DB. No operational seeding, model, RAG or vector writes.
"""
import hashlib
import json
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.api.routers.analyzer import admin, analyze, feedback, history, knowledge, stats
from backend.api.routers.analyzer import auth as auth_api
from backend.core.health_probe import HealthProbeCoordinator
from backend.domain.analyzer import auth
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.models.knowledge import KnowledgeEntry, KnowledgeSourceCandidate, KnowledgeSourceEvent
from backend.domain.analyzer.models.session import AnalyzerSession, LoginWindow
from backend.domain.analyzer.models.user import User
from backend.domain.asset_registry.models import AuditLog, InfrastructureAsset
from backend.domain.incident_ingest.models import IncidentIngestOutbox
from backend.domain.analyzer.services import summary, vector_db
from backend.domain.analyzer.services.vendor_knowledge import vendor_reference_results
from backend.infrastructure.cache import cache_manager
from backend.infrastructure.database import database_engine, get_db_session
from backend.infrastructure.object_store import object_storage
from tests.test_analyzer_postgres_integration import (
    TEST_KEY,
    TEST_PASSWORD,
    dedicated_url,
)

engine = create_async_engine(
    dedicated_url(os.environ['EIMS_TEST_DATABASE_URL']),
    pool_size=2,
    max_overflow=0,
    pool_pre_ping=True,
)
_health_probe = HealthProbeCoordinator(ttl_seconds=20.0, degraded_ttl_seconds=3.0)
# Route the production lifecycle-safe health probe to this explicitly verified
# disposable engine; never let the synthetic harness touch the global DSN.
database_engine._engine = engine
# Keep readiness probes off the deliberately constrained request pool (2 connections).
database_engine._health_engine = create_async_engine(
    dedicated_url(os.environ['EIMS_TEST_DATABASE_URL']),
    pool_size=1, max_overflow=0, pool_timeout=1.0, pool_pre_ping=False,
)
sessions = async_sessionmaker(engine, expire_on_commit=False)
auth.settings.AUTH_MODE = os.environ.get('EIMS_SYNTHETIC_AUTH_MODE', 'secure')
auth.settings.ADMIN_TOKEN = 'synthetic-test-admin-token-only'
auth.SECRET_KEY = TEST_KEY
auth.ALGORITHM = 'HS256'


def local_refs(event, provider, **kw):
    refs = vendor_reference_results(kw.get('diagnostic_code') or '', kw.get('evidence_text') or '', 'en')
    return refs, '\n'.join(r.snippet for r in refs)


async def no_rag(*a, **kw):
    return []


async def no_export(*a, **kw):
    return None


def forbidden(*a, **kw):
    raise RuntimeError('External inference forbidden in synthetic demo harness')


analyze.search_solutions = local_refs
summary.search_similar_logs = no_rag
summary._translate = lambda text, target: text  # deterministic core only
vector_db.add_solution = no_export


def test_token(username, role='user', session_id=None):
    # Keep the JWT valid; PostgreSQL owns the shorter synthetic-expiry boundary.
    return auth.create_access_token(username, role, session_id=session_id)
auth_api.create_access_token = test_token


@asynccontextmanager
async def lifespan(app):
    try:
        await cache_manager.initialize()
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: AnalysisHistory.__table__.create(c, checkfirst=True))
            await conn.run_sync(lambda c: KnowledgeEntry.__table__.create(c, checkfirst=True))
            await conn.run_sync(lambda c: User.__table__.create(c, checkfirst=True))
            await conn.run_sync(lambda c: AnalyzerSession.__table__.create(c, checkfirst=True))
            await conn.run_sync(lambda c: LoginWindow.__table__.create(c, checkfirst=True))
            # v1.1: analyzer inserts write incident_ingest_outbox in the same transaction (F1).
            await conn.run_sync(lambda c: InfrastructureAsset.__table__.create(c, checkfirst=True))
            await conn.run_sync(lambda c: IncidentIngestOutbox.__table__.create(c, checkfirst=True))
            # Expire only the synthetic-expiry PostgreSQL session row after 2s;
            # its signed JWT remains valid so this tests server-side revocation/expiry.
            await conn.execute(text("""
                CREATE OR REPLACE FUNCTION eims_test_expire_synthetic_session()
                RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    IF NEW.username = 'synthetic-expiry' THEN
                        NEW.expires_at := NOW() + INTERVAL '2 seconds';
                    END IF;
                    RETURN NEW;
                END;
                $$
            """))
            await conn.execute(text("DROP TRIGGER IF EXISTS eims_test_expire_synthetic_session ON analyzer_sessions"))
            await conn.execute(text("""
                CREATE TRIGGER eims_test_expire_synthetic_session
                BEFORE INSERT ON analyzer_sessions
                FOR EACH ROW EXECUTE FUNCTION eims_test_expire_synthetic_session()
            """))
        async with sessions() as session:
            # The URL was validated against dedicated_url()'s explicit allowlist;
            # never fall back to application database settings. Preserve append-only
            # Knowledge/Lifecycle and Analysis History evidence across reruns; reset
            # only ephemeral login sessions and throttling windows for deterministic auth.
            fixture_names = ['synthetic-browser-review', 'synthetic-browser-other', 'synthetic-expiry', 'synthetic-browser-admin']
            await session.execute(AnalyzerSession.__table__.delete().where(AnalyzerSession.username.in_(fixture_names)))
            await session.execute(LoginWindow.__table__.delete())
            for name in fixture_names:
                role = 'admin' if name == 'synthetic-browser-admin' else 'user'
                user = (await session.execute(select(User).where(User.username == name))).scalars().first()
                reviewer_capability = name == 'synthetic-browser-review'
                if user is None:
                    session.add(User(username=name, password=auth.hash_password(TEST_PASSWORD), role=role,
                                     knowledge_reviewer=reviewer_capability))
                else:
                    # Dedicated acceptance identities are deterministic fixtures, never production users.
                    user.password = auth.hash_password(TEST_PASSWORD)
                    user.role = role
                    user.knowledge_reviewer = reviewer_capability

            # A disposable source row lets Chromium exercise a real Reviewer state transition
            # without changing any of the 20 imported vendor candidates awaiting human review.
            fixture_key = 'eims-synthetic-browser-review-fixture'
            fixture = await session.scalar(select(KnowledgeSourceCandidate).where(
                KnowledgeSourceCandidate.source_key == fixture_key
            ))
            if fixture is None:
                payload = {
                    'id': fixture_key, 'vendor': 'EIMS Synthetic',
                    'product': 'Browser Acceptance Harness', 'version_scope': 'synthetic-only',
                    'domain': 'test-only', 'identity': 'EIMS-SYNTHETIC-BROWSER-REVIEW',
                    'title': 'Synthetic Browser Review Fixture — Not Domain Evidence',
                    'url': 'https://example.com/synthetic-eims-browser-acceptance',
                    'applicability': 'Synthetic browser acceptance only; not a vendor reference.',
                    'prerequisites': ['Disposable acceptance database only'],
                    'evidence': ['Synthetic fixture row; not incident or vendor evidence'],
                    'limitations': ['Must never be promoted to Approved Knowledge'],
                    'next_checks': ['Verify the Reviewer action and append-only event'],
                    'validation': ['Confirm state and audit event through the API and UI'],
                    'rollback': ['No operational rollback; fixture is isolated to this database'],
                    'risk': 'low', 'review_state': 'pending_domain_review',
                    'evidence_status': 'synthetic_test_fixture',
                }
                source_hash = hashlib.sha256(json.dumps(
                    payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')
                ).encode('utf-8')).hexdigest()
                fixture = KnowledgeSourceCandidate(
                    source_key=fixture_key, vendor=payload['vendor'], product=payload['product'],
                    version_scope=payload['version_scope'], domain=payload['domain'],
                    identity=payload['identity'], title=payload['title'], source_url=payload['url'],
                    applicability=payload['applicability'], prerequisites=payload['prerequisites'],
                    evidence=payload['evidence'], limitations=payload['limitations'],
                    next_checks=payload['next_checks'], validation=payload['validation'],
                    rollback=payload['rollback'], risk_level='low',
                    evidence_status='synthetic_test_fixture', review_state='pending_domain_review',
                    catalog_schema_version='synthetic-fixture-v1', source_hash=source_hash,
                    source_payload=payload, imported_by='synthetic-browser-acceptance',
                )
                session.add(fixture)
                await session.flush()
                session.add(KnowledgeSourceEvent(
                    source_candidate_id=fixture.id, action='test_fixture_created',
                    from_state=None, to_state='pending_domain_review', source_hash=source_hash,
                    note='Synthetic browser fixture only; not vendor evidence and not Approved Knowledge.',
                    changed_by='synthetic-browser-acceptance',
                ))
            elif fixture.review_state != 'pending_domain_review':
                previous_state = fixture.review_state
                fixture.review_state = 'pending_domain_review'
                fixture.reviewed_by = None
                fixture.reviewed_at = None
                fixture.review_note = ''
                session.add(KnowledgeSourceEvent(
                    source_candidate_id=fixture.id, action='test_fixture_reset',
                    from_state=previous_state, to_state='pending_domain_review',
                    source_hash=fixture.source_hash,
                    note='Synthetic fixture reset for repeatable browser acceptance; vendor candidates remain untouched.',
                    changed_by='synthetic-browser-acceptance',
                ))
            await session.commit()

        # Warm the independent readiness path before accepting browser traffic.
        # This prevents the first authenticated page's concurrent session/history
        # requests from racing a cold asyncpg connection and the first MinIO probe.
        readiness = await _health_probe.check(
            database_engine.ping, cache_manager.ping, object_storage.ping
        )
        if not all(readiness):
            raise RuntimeError('Synthetic acceptance dependencies failed startup readiness.')
        logging.getLogger('uvicorn.error').info(json.dumps({
            'event': 'eims_synthetic_startup_readiness',
            'database': readiness[0], 'redis': readiness[1], 'minio': readiness[2],
        }))
        yield
    finally:
        await cache_manager.close()
        await engine.dispose()
        if database_engine._health_engine is not None:
            await database_engine._health_engine.dispose()
            database_engine._health_engine = None
        database_engine._engine = None


app = FastAPI(lifespan=lifespan)
request_logger = logging.getLogger('uvicorn.error')

@app.middleware('http')
async def request_correlation(request, call_next):
    request_id = request.headers.get('x-request-id', '')
    if not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', request_id, re.I):
        request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    request_logger.info(json.dumps({'event':'eims_backend_request','requestId':request_id,
        'method':request.method,'path':request.url.path,'status':response.status_code,
        'durationMs':round((time.perf_counter()-started)*1000,1)}))
    return response

@app.get('/api/v1/__test__/diagnostics', tags=['Synthetic Demo Observability'])
async def read_acceptance_diagnostics():
    """Expose only safe pool and pg_stat_activity counters for isolated acceptance."""
    pool = engine.pool
    checked_out_before = pool.checkedout()
    async with engine.connect() as connection:
        row = (await connection.execute(text("""
            SELECT current_database() AS database_name, current_user AS database_user,
                   count(*) FILTER (WHERE state = 'active') AS active_connections,
                   count(*) FILTER (WHERE state = 'idle') AS idle_connections
            FROM pg_stat_activity WHERE datname = current_database()
        """))).mappings().one()
        reviewer_audit_count = await connection.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.action_verb.in_(['GRANT_KNOWLEDGE_REVIEWER', 'REVOKE_KNOWLEDGE_REVIEWER'])
        ))
    return {
        'database': row['database_name'],
        'database_user': row['database_user'],
        'pg_stat_activity': {'active': row['active_connections'], 'idle': row['idle_connections']},
        'pool': {'size': pool.size(), 'checked_out_before': checked_out_before,
                 'checked_out_after': pool.checkedout(), 'overflow': pool.overflow()},
        'reviewer_capability_audit_events': int(reviewer_audit_count or 0),
    }

app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3009'],
                   allow_methods=['GET', 'POST', 'OPTIONS'], allow_headers=['*'])
app.include_router(analyze.router, prefix='/api/v1/analyze')
app.include_router(history.router, prefix='/api/v1/history')
app.include_router(knowledge.router, prefix='/api/v1/knowledge')
app.include_router(auth_api.router, prefix='/api/v1/auth')
app.include_router(stats.router, prefix='/api/v1/stats')
app.include_router(feedback.router, prefix='/api/v1/feedback')
app.include_router(admin.router, prefix='/api/v1/admin')

@app.get('/api/v1/health', tags=['Synthetic Demo Observability'])
async def read_synthetic_health() -> JSONResponse:
    """Probe the dedicated test database and real local Redis/MinIO services."""
    database_ok, redis_ok, minio_ok = await _health_probe.check(
        database_engine.ping, cache_manager.ping, object_storage.ping
    )
    healthy = database_ok and redis_ok and minio_ok
    request_logger.info(json.dumps({
        'event': 'eims_synthetic_health_components',
        'database': database_ok, 'redis': redis_ok, 'minio': minio_ok,
        'status': 'HEALTHY' if healthy else 'DEGRADED',
    }))
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "system": "EIMS Synthetic Analyzer Acceptance",
            "version": app.version,
            "status": "HEALTHY" if healthy else "DEGRADED",
            "licensing_model": "Dedicated loopback test database with real local Redis and MinIO probes",
            "components": {
                # Production/UI contract key; value is still derived from the dedicated test DB probe.
                "postgresql_pgbouncer_tier": "UP" if database_ok else "DOWN",
                "redis_volatile_lru_tier": "UP" if redis_ok else "DOWN",
                "minio_object_storage_tier": "UP" if minio_ok else "DOWN",
            },
        },
    )


async def db():
    async with sessions() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[analyze.get_db] = db
app.dependency_overrides[knowledge.get_db] = db
app.dependency_overrides[get_db_session] = db
