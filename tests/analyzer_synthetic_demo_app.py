"""TEST HARNESS ONLY: real HTTP/DB transport, no operational app startup.

Launch explicitly with EIMS_TEST_DATABASE_URL and uvicorn on loopback. Uses
synthetic JWT keys, real auth verification and a dedicated test database only.
Do not deploy or use with company data. Only named synthetic fixture accounts
in the dedicated DB. No operational seeding, model, RAG or vector writes.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.test_analyzer_postgres_integration import dedicated_url, TEST_KEY, TEST_PASSWORD
from backend.api.routers.analyzer import analyze, history, auth as auth_api, stats, feedback
from backend.domain.analyzer import auth
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.models.user import User
from sqlalchemy import select
from backend.domain.analyzer.services import summary, vector_db
from backend.domain.analyzer.services.vendor_knowledge import vendor_reference_results

engine = create_async_engine(dedicated_url(os.environ['EIMS_TEST_DATABASE_URL']))
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
summary._call_gemini = forbidden
vector_db.add_solution = no_export
feedback.add_solution = no_export


def test_token(username, role='user'):
    # Real issuance with a short TTL for one synthetic expiry control only.
    previous = auth.TOKEN_EXPIRE_MINUTES
    try:
        if username == 'synthetic-expiry':
            auth.TOKEN_EXPIRE_MINUTES = 0.05
        return auth.create_access_token(username, role)
    finally:
        auth.TOKEN_EXPIRE_MINUTES = previous
auth_api.create_access_token = test_token


@asynccontextmanager
async def lifespan(app):
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: AnalysisHistory.__table__.create(c, checkfirst=True))
        await conn.run_sync(lambda c: User.__table__.create(c, checkfirst=True))
    async with sessions() as session:
        for name in ['synthetic-browser-review', 'synthetic-browser-other', 'synthetic-expiry']:
            if not (await session.execute(select(User).where(User.username == name))).scalars().first():
                session.add(User(username=name, password=auth.hash_password(TEST_PASSWORD), role='user'))
        await session.commit()
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3009'],
                   allow_methods=['GET', 'POST', 'OPTIONS'], allow_headers=['*'])
app.include_router(analyze.router, prefix='/api/v1/analyze')
app.include_router(history.router, prefix='/api/v1/history')
app.include_router(auth_api.router, prefix='/api/v1/auth')
app.include_router(stats.router, prefix='/api/v1/stats')
app.include_router(feedback.router, prefix='/api/v1/feedback')


async def db():
    async with sessions() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[analyze.get_db] = db
