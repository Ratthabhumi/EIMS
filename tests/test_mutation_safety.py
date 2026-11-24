"""Behavioral tests for destructive-operation safety (NF-1, NF-2, R-1, R-5, R-6).

No database, no network, no services: a fake session records the statements that
would have executed, so a denied path can be proven to issue no DELETE/TRUNCATE.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.domain.analyzer.services import session_maintenance
from backend.infrastructure import db_identity

REPO = Path(__file__).resolve().parents[1]


class _Result:
    def __init__(self, rows):
        self._rows = list(rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    @property
    def rowcount(self):
        return len(self._rows)


class _Tx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Minimal AsyncSession stand-in that records executed SQL text."""

    def __init__(self, identity=("eims_benchmark", "eims_app", "eims_app", None), fail_identity=False):
        self.identity = identity
        self.fail_identity = fail_identity
        self.statements: list[str] = []
        self.rolled_back = False
        self.info: dict = {}
        self.identity_queries = 0

    def begin(self):
        return _Tx(self)

    async def execute(self, statement, params=None):
        sql = str(statement)
        if "pg_database" in sql:
            self.identity_queries += 1
            if self.fail_identity:
                raise RuntimeError("identity unavailable")
            return _Result([self.identity])
        self.statements.append(sql)
        if "analyzer_sessions" in sql or "analyzer_login_windows" in sql:
            return _Result(["row-1", "row-2"])
        return _Result([])

    def destructive(self) -> list[str]:
        return [s for s in self.statements if "DELETE" in s.upper() or "TRUNCATE" in s.upper()]

    async def rollback(self):
        self.rolled_back = True

    def in_transaction(self):
        return False

    async def close(self):
        return None


@pytest.fixture(autouse=True)
def _clear_identity_env(monkeypatch):
    monkeypatch.delenv(db_identity.IDENTITY_ENV, raising=False)


# --- identity policy -------------------------------------------------------

def test_identity_read_uses_live_connection_row():
    session = FakeSession(identity=("eims_registry", "eims_app", "eims_app", None))
    identity = asyncio.run(db_identity.connection_identity(session))
    assert identity.database == "eims_registry"
    assert identity.user == "eims_app"
    assert identity.disposable is False


def test_denied_without_trusted_identity_or_disposable_marker():
    session = FakeSession(identity=("eims_registry", "eims_app", "eims_app", None))
    with pytest.raises(db_identity.MutationTargetError):
        asyncio.run(db_identity.require_destructive_target(session, operation="test"))


def test_same_database_name_wrong_role_is_denied(monkeypatch):
    monkeypatch.setenv(db_identity.IDENTITY_ENV, "eims_registry|eims_app")
    session = FakeSession(identity=("eims_registry", "other_role", "other_role", None))
    with pytest.raises(db_identity.MutationTargetError):
        asyncio.run(db_identity.require_destructive_target(session, operation="test"))


def test_matching_trusted_identity_is_allowed(monkeypatch):
    monkeypatch.setenv(db_identity.IDENTITY_ENV, "eims_benchmark|eims_app")
    session = FakeSession(identity=("eims_benchmark", "eims_app", "eims_app", None))
    identity = asyncio.run(db_identity.require_destructive_target(session, operation="test"))
    assert identity.database == "eims_benchmark"


def test_disposable_sentinel_is_allowed():
    session = FakeSession(identity=("eims_ingest_v11_test", "eims_ingest_v11_app",
                                    "eims_ingest_v11_app", "EIMS-DISPOSABLE-INGEST-V11:abc"))
    identity = asyncio.run(db_identity.require_destructive_target(session, operation="test"))
    assert identity.disposable is True


def test_identity_unavailable_fails_closed():
    session = FakeSession(fail_identity=True)
    with pytest.raises(db_identity.MutationTargetError):
        asyncio.run(db_identity.require_destructive_target(session, operation="test"))


# --- NF-2: session maintenance --------------------------------------------

def test_cleanup_default_is_dry_run_and_deletes_nothing():
    session = FakeSession()
    counts = asyncio.run(session_maintenance.cleanup_auth_records(
        session, retention_seconds=7 * 86400))
    assert session.destructive() == []
    assert counts


def test_cleanup_destructive_without_identity_is_denied_before_delete():
    session = FakeSession(identity=("eims_registry", "eims_app", "eims_app", None))
    with pytest.raises(db_identity.MutationTargetError):
        asyncio.run(session_maintenance.cleanup_auth_records(
            session, retention_seconds=7 * 86400, dry_run=False))
    assert session.destructive() == []


def test_cleanup_destructive_with_disposable_target_deletes(monkeypatch):
    monkeypatch.setenv(db_identity.IDENTITY_ENV, "eims_test|eims_test_app")
    session = FakeSession(identity=("eims_test", "eims_test_app", "eims_test_app", None))
    counts = asyncio.run(session_maintenance.cleanup_auth_records(
        session, retention_seconds=7 * 86400, dry_run=False))
    assert session.destructive(), "an accepted destructive run must reach DELETE"
    assert counts


# --- NF-1: clear_db is inert on import and refuses without opt-in ---------

def test_clear_db_import_does_not_connect_or_execute():
    code = ("import clear_db, backend.infrastructure.database as d; "
            "assert d.database_engine._engine is None, 'engine created at import'; "
            "print('inert')")
    result = subprocess.run([sys.executable, "-c", code], cwd=str(REPO),
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert "inert" in result.stdout


def test_clear_db_is_retired_and_executes_nothing(monkeypatch):
    monkeypatch.delenv("EIMS_ALLOW_DESTRUCTIVE_CLEAR", raising=False)
    import clear_db
    assert not hasattr(clear_db, "clear"), "the destructive entry point must be gone"
    with pytest.raises(SystemExit) as excinfo:
        raise SystemExit(clear_db.main())
    assert excinfo.value.code == 2
    assert "retired" in clear_db.RETIRED_MESSAGE.lower()


# --- Policy A: runtime identity at the request-session boundary -----------

def test_runtime_identity_unconfigured_is_marked_not_verified(monkeypatch):
    monkeypatch.delenv(db_identity.IDENTITY_ENV, raising=False)
    monkeypatch.delenv(db_identity.REQUIRED_ENV, raising=False)
    session = FakeSession()
    assert asyncio.run(db_identity.require_runtime_identity(session)) is None
    assert session.info["eims_identity_status"] == "unconfigured"
    assert session.statements == [], "no query when the deployment is unconfigured"


def test_runtime_identity_required_but_missing_fails_closed(monkeypatch):
    monkeypatch.delenv(db_identity.IDENTITY_ENV, raising=False)
    monkeypatch.setenv(db_identity.REQUIRED_ENV, "1")
    with pytest.raises(db_identity.MutationTargetError):
        asyncio.run(db_identity.require_runtime_identity(FakeSession()))


def test_runtime_identity_malformed_fails_closed(monkeypatch):
    monkeypatch.setenv(db_identity.IDENTITY_ENV, "no-pipe-here")
    with pytest.raises(db_identity.MutationTargetError):
        asyncio.run(db_identity.require_runtime_identity(FakeSession()))


def test_runtime_identity_mismatch_fails_closed(monkeypatch):
    monkeypatch.setenv(db_identity.IDENTITY_ENV, "eims_registry|eims_app")
    session = FakeSession(identity=("eims_registry", "other_role", "other_role", None))
    with pytest.raises(db_identity.MutationTargetError):
        asyncio.run(db_identity.require_runtime_identity(session))


def test_runtime_identity_match_is_cached_on_the_session(monkeypatch):
    monkeypatch.setenv(db_identity.IDENTITY_ENV, "eims_registry|eims_app")
    session = FakeSession(identity=("eims_registry", "eims_app", "eims_app", None))
    first = asyncio.run(db_identity.require_runtime_identity(session))
    second = asyncio.run(db_identity.require_runtime_identity(session))
    assert first is second
    assert session.info["eims_identity_status"] == "verified"
    assert len(session.statements) == 0, "no write statements; identity query only"
    assert session.identity_queries == 1, "identity is queried once per session"


# --- the wiring itself: get_session must run the guard before yielding -----

class _FakeCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


def test_get_session_refuses_before_yielding_on_identity_mismatch(monkeypatch):
    from backend.infrastructure.database import AsynchronousDatabaseEngine

    monkeypatch.setenv(db_identity.IDENTITY_ENV, "eims_registry|eims_app")
    session = FakeSession(identity=("eims_registry", "other_role", "other_role", None))
    engine = AsynchronousDatabaseEngine()
    engine._session_factory = lambda: _FakeCtx(session)

    async def drive():
        agen = engine.get_session()
        try:
            await agen.__anext__()
        finally:
            await agen.aclose()

    with pytest.raises(db_identity.MutationTargetError):
        asyncio.run(drive())


def test_get_session_yields_when_identity_matches(monkeypatch):
    from backend.infrastructure.database import AsynchronousDatabaseEngine

    monkeypatch.setenv(db_identity.IDENTITY_ENV, "eims_registry|eims_app")
    session = FakeSession(identity=("eims_registry", "eims_app", "eims_app", None))
    engine = AsynchronousDatabaseEngine()
    engine._session_factory = lambda: _FakeCtx(session)

    async def drive():
        agen = engine.get_session()
        yielded = await agen.__anext__()
        await agen.aclose()
        return yielded

    assert asyncio.run(drive()) is session
    assert session.info["eims_identity_status"] == "verified"


# --- workers build sessions from get_session_maker(), not from the dependency --

def _worker_engine(session):
    from backend.infrastructure.database import AsynchronousDatabaseEngine
    engine = AsynchronousDatabaseEngine()
    engine._session_factory = lambda: _FakeCtx(session)
    return engine


def test_worker_factory_refuses_on_identity_mismatch(monkeypatch):
    monkeypatch.setenv(db_identity.IDENTITY_ENV, "eims_registry|eims_app")
    session = FakeSession(identity=("eims_registry", "other_role", "other_role", None))
    factory = _worker_engine(session).get_session_maker()

    async def drive():
        async with factory() as _session:
            return _session

    with pytest.raises(db_identity.MutationTargetError):
        asyncio.run(drive())


def test_worker_factory_yields_on_identity_match(monkeypatch):
    monkeypatch.setenv(db_identity.IDENTITY_ENV, "eims_registry|eims_app")
    session = FakeSession(identity=("eims_registry", "eims_app", "eims_app", None))
    factory = _worker_engine(session).get_session_maker()

    async def drive():
        async with factory() as opened:
            return opened

    assert asyncio.run(drive()) is session
    assert session.info["eims_identity_status"] == "verified"


def test_worker_factory_is_stable_across_calls():
    session = FakeSession()
    engine = _worker_engine(session)
    assert engine.get_session_maker() is engine.get_session_maker()


# --- NF-1 caller inventory: nothing in the runtime imports the destructive
# helpers. This test fails if a future caller appears without review. -------

def test_no_runtime_caller_of_destructive_helpers():
    allowed = {
        "clear_db.py",
        "backend/infrastructure/db_identity.py",                 # defines the gate
        "backend/domain/analyzer/services/session_maintenance.py",  # defines the cleanup
        "tools/maintain_analyzer_sessions.py",
        "tools/seed_analyzer_incident.py",
        "tools/sprint11_benchmark.py",
        "tests/test_mutation_safety.py",
        "tests/test_analyzer_postgres_integration.py",
    }
    offenders = []
    for path in REPO.rglob("*.py"):
        rel = path.relative_to(REPO).as_posix()
        if rel.startswith(("venv/", "dist/", "clients/")) or "/site-packages/" in rel:
            continue
        if rel in allowed:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "cleanup_auth_records" in text or "require_destructive_target" in text:
            offenders.append(rel)
    assert offenders == [], f"unreviewed destructive callers: {offenders}"
