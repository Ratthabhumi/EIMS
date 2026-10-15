"""Disposable SQLite History API harness; never boots backend.main or workers.

Only synthetic data. Deliberately excludes PostgreSQL, vector persistence,
external reference search, AI and operational auth. Not deployment validation.
"""
from contextlib import asynccontextmanager
from pathlib import Path
import argparse
import json
import uuid


def prepare_sandbox(parent: Path) -> Path:
    root = parent.resolve() / ('eims-test-' + uuid.uuid4().hex)
    root.mkdir(parents=True, exist_ok=False)
    (root / 'sandbox.json').write_text(json.dumps({'purpose': 'synthetic-history-only', 'root': str(root)}), encoding='utf-8')
    return root


def validate_target(root: Path, url: str) -> Path:
    from sqlalchemy.engine import make_url
    root = root.resolve()
    if not root.name.startswith('eims-test-') or str(root).startswith(('\\\\', '//')):
        raise ValueError('A dedicated local sandbox directory is required')
    marker = json.loads((root / 'sandbox.json').read_text(encoding='utf-8'))
    if marker != {'purpose': 'synthetic-history-only', 'root': str(root)}:
        raise ValueError('Sandbox identity mismatch')
    parsed = make_url(url)
    if parsed.drivername != 'sqlite+aiosqlite' or parsed.host or parsed.username or parsed.password or parsed.query:
        raise ValueError('Only credential-free local SQLite is permitted; network databases are forbidden')
    target = Path(parsed.database or '').resolve()
    if target != root / 'history-test.sqlite3' or target.is_symlink():
        raise ValueError('Database must be the dedicated sandbox file')
    return target


def create_app(root: Path):
    # Validate before importing application components or constructing an engine.
    from sqlalchemy.engine import URL
    url = URL.create('sqlite+aiosqlite', database=str(root.resolve() / 'history-test.sqlite3')).render_as_string(hide_password=False)
    target = validate_target(root, url)
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from unittest.mock import patch
    from backend.infrastructure.database import get_db_session, database_engine
    from backend.domain.analyzer.auth import get_current_user
    from backend.domain.analyzer.models.history import AnalysisHistory
    from backend.api.routers.analyzer import analyze, history
    from backend.domain.analyzer.services import vector_db, summary
    from backend.domain.analyzer.schemas.analyze import SolutionSummary
    import asyncpg
    import requests

    def forbidden(*a, **kw):
        raise RuntimeError('Operational DB, network references and full application startup are forbidden in the sandbox')

    async def forbidden_async(*a, **kw):
        forbidden()

    async def no_vector(*a, **kw):
        return None

    async def no_similar(*a, **kw):
        return []

    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def session_dependency():
        validate_target(root, url)
        async with sessions() as session:
            yield session

    @asynccontextmanager
    async def lifespan(app):
        # Patches are restored at teardown; no global production app is started.
        from contextlib import ExitStack
        with ExitStack() as stack:
            for owner, name, replacement in [
                (database_engine, 'initialize', forbidden_async),
                (database_engine, 'get_session', forbidden),
                (asyncpg, 'connect', forbidden_async),
                (asyncpg, 'create_pool', forbidden),
                (requests.sessions.Session, 'request', forbidden),
                (analyze, 'search_solutions', lambda *a, **kw: ([], '')),
                (vector_db, 'add_solution', no_vector),
                (summary, 'search_similar_logs', no_similar),
                (summary, '_build_from_gemini', forbidden),
                (summary, 'DDGS', forbidden),
                (summary, '_translate', lambda value, *a, **kw: value),
                (summary, '_build_from_web', lambda *a, **kw: SolutionSummary(
                    overview='Sandbox: no deterministic finding available.',
                    limitations=['External references and AI are disabled in this synthetic sandbox.'])),
            ]:
                stack.enter_context(patch.object(owner, name, replacement))
            async with engine.begin() as connection:
                # Only this actual ORM table, never the complete operational schema.
                await connection.run_sync(AnalysisHistory.__table__.create, checkfirst=True)
            app.state.sandbox_db = str(target)
            try:
                yield
            finally:
                await engine.dispose()

    app = FastAPI(title='EIMS synthetic History sandbox', lifespan=lifespan)
    app.dependency_overrides[get_db_session] = session_dependency
    app.dependency_overrides[get_current_user] = lambda: 'synthetic-evaluation'
    app.include_router(analyze.router, prefix='/api/v1/analyze')
    app.include_router(history.router, prefix='/api/v1/history')
    @app.get('/__sandbox')
    async def sandbox_identity():
        return {'purpose': 'synthetic-history-only', 'dialect': 'sqlite', 'operational_startup': False}
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=3116)
    args = parser.parse_args()
    root = prepare_sandbox(Path(__file__).resolve().parents[1] / '.local-private' / 'test-environments')
    print('Synthetic SQLite sandbox:', root, flush=True)
    import uvicorn
    uvicorn.run(create_app(root), host='127.0.0.1', port=args.port, log_level='warning')
