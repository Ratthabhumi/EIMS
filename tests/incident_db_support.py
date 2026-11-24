"""Disposable PostgreSQL helpers for Incident Core tests.

Only an explicitly configured loopback test database with the disposable
Incident Core role is accepted. There is no fallback to application or
operational database settings. Every helper creates a uniquely named schema
and retains it for inspection; no schema or row cleanup is performed.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.models.session import AnalyzerSession
from backend.domain.analyzer.models.user import User
from backend.domain.asset_registry.models import AuditLog, InfrastructureAsset
from backend.domain.incident.models import (
    Incident,
    IncidentEvidence,
    IncidentVerification,
)
from backend.domain.incident.workflow_models import (
    IncidentDiagnosis,
    IncidentKnowledgeProposal,
    IncidentNote,
    IncidentRemediation,
    IncidentWorkflowEvent,
)
from backend.domain.analyzer.models.knowledge import KnowledgeEntry
from backend.infrastructure.database import Base

ALLOWED_DATABASES = {"eims_incident_test"}
ALLOWED_USERS = {"eims_incident_test"}

INCIDENT_TABLES = [
    User.__table__,
    AnalyzerSession.__table__,
    AnalysisHistory.__table__,
    InfrastructureAsset.__table__,
    AuditLog.__table__,
    Incident.__table__,
    IncidentEvidence.__table__,
    IncidentVerification.__table__,
    IncidentDiagnosis.__table__,
    IncidentRemediation.__table__,
    IncidentWorkflowEvent.__table__,
    IncidentNote.__table__,
    KnowledgeEntry.__table__,
    IncidentKnowledgeProposal.__table__,
]

DISPOSABLE_PASSWORD_MARKER = "EIMS_TEST_DATABASE_URL"


def require_database_url() -> str:
    """Returns the explicitly allowlisted disposable URL or skips the test."""
    value = os.environ.get(DISPOSABLE_PASSWORD_MARKER)
    if not value:
        pytest.skip(
            "EIMS_TEST_DATABASE_URL is not configured; disposable PostgreSQL is required"
        )
    url = make_url(value)
    if (
        url.drivername != "postgresql+asyncpg"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.database not in ALLOWED_DATABASES
        or url.username not in ALLOWED_USERS
        or url.port in {None, 5432, 6432}
    ):
        raise ValueError(
            "Refusing database: require the disposable Incident Core loopback "
            "role/database on a non-operational port"
        )
    return value


def scoped_engine(url: str, schema: str):
    """Engine whose every connection resolves unqualified names to `schema`."""
    return create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": f'"{schema}"'}},
    )


def session_factory(engine):
    return async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )


def point_settings_at(monkeypatch, url: str) -> None:
    """Points the real application settings at the disposable database.

    ``settings.database_url`` is a read-only property, so patching that name has
    no effect (it silently keeps the default target). Patch the fields the
    property reads, and callers must assert the resulting database identity.
    """
    from backend.core.config import settings

    parsed = make_url(url)
    monkeypatch.setattr(settings, "DB_USER", parsed.username)
    monkeypatch.setattr(settings, "DB_PASSWORD", parsed.password)
    monkeypatch.setattr(settings, "DB_HOST", parsed.host)
    monkeypatch.setattr(settings, "DB_PORT", parsed.port)
    monkeypatch.setattr(settings, "DB_NAME", parsed.database)


async def create_schema(url: str, *, tables=None) -> tuple[str, object]:
    """Creates a unique schema and the requested ORM tables inside it."""
    schema = "eims_incident_" + uuid.uuid4().hex
    bootstrap = create_async_engine(url, poolclass=NullPool)
    try:
        async with bootstrap.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = scoped_engine(url, schema)
        selected = list(INCIDENT_TABLES if tables is None else tables)
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=selected))
        return schema, engine
    finally:
        await bootstrap.dispose()


async def create_asset(engine, hostname: str = "synthetic-incident-host") -> uuid.UUID:
    """Inserts one synthetic asset using a unique fake fingerprint."""
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    async with session_factory(engine)() as db:
        asset = InfrastructureAsset(
            hostname=hostname,
            canonical_ip="127.0.0.1",
            cryptographic_fingerprint=fingerprint,
        )
        db.add(asset)
        await db.commit()
        return asset.asset_id


async def create_user(
    engine,
    username: str,
    *,
    role: str = "user",
    knowledge_reviewer: bool = False,
    password: str = "synthetic-incident-password-only",
) -> User:
    from backend.domain.analyzer.auth import hash_password
    from backend.domain.analyzer.services.session_security import digest

    async with session_factory(engine)() as db:
        user = User(
            username=username,
            role=role,
            knowledge_reviewer=knowledge_reviewer,
            password=hash_password(password),
        )
        db.add(user)
        await db.flush()
        now = datetime.now(UTC)
        db.add(
            AnalyzerSession(
                id=digest(session_id(username)),
                user_id=user.id,
                username=username,
                credential_version=digest(user.password),
                created_at=now,
                last_seen=now,
                expires_at=now + timedelta(days=1),
            )
        )
        await db.commit()
        return user


def session_id(username: str) -> str:
    return f"synthetic-incident-session-{username}"


# The guard DDL lives in the migration. Test schemas are built from ORM
# metadata, so the exact same statements are imported from the migration module
# and installed here. Importing the migration keeps one source of truth and
# prevents silent drift between the schema the tests exercise and the schema
# that ships.
def _verification_migration():
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "f7a1c3d9e502_add_incident_verification.py"
    )
    spec = importlib.util.spec_from_file_location("_verification_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_VERIFICATION_MIGRATION = _verification_migration()

APPEND_ONLY_FUNCTION_DDL = _VERIFICATION_MIGRATION.APPEND_ONLY_FUNCTION_DDL
APPEND_ONLY_TRIGGER_DDL = _VERIFICATION_MIGRATION.APPEND_ONLY_TRIGGER_DDL
APPEND_ONLY_TRUNCATE_DDL = _VERIFICATION_MIGRATION.APPEND_ONLY_TRUNCATE_DDL
RESOLUTION_FUNCTION_DDL = _VERIFICATION_MIGRATION.RESOLUTION_FUNCTION_DDL
RESOLUTION_TRIGGER_DDL = _VERIFICATION_MIGRATION.RESOLUTION_TRIGGER_DDL
CYCLE_GUARD_FUNCTION_DDL = _VERIFICATION_MIGRATION.CYCLE_GUARD_FUNCTION_DDL
CYCLE_GUARD_TRIGGER_DDL = _VERIFICATION_MIGRATION.CYCLE_GUARD_TRIGGER_DDL
INSERT_GUARD_FUNCTION_DDL = _VERIFICATION_MIGRATION.INSERT_GUARD_FUNCTION_DDL
INSERT_GUARD_TRIGGER_DDL = _VERIFICATION_MIGRATION.INSERT_GUARD_TRIGGER_DDL

_GUARD_TRIGGERS = (
    "trg_incident_verification_append_only|incident_verification",
    "trg_incident_verification_append_only_truncate|incident_verification",
    "trg_incident_resolution_requires_verification|incidents",
    "trg_incident_remediation_cycle_guard|incidents",
    "trg_incident_insert_state_guard|incidents",
)


async def install_verification_append_only(engine) -> None:
    """Installs the migration's guards on a test schema (idempotent)."""
    async with engine.begin() as conn:
        for ddl in (
            APPEND_ONLY_FUNCTION_DDL,
            RESOLUTION_FUNCTION_DDL,
            CYCLE_GUARD_FUNCTION_DDL,
            INSERT_GUARD_FUNCTION_DDL,
        ):
            await conn.execute(text(ddl))
        for name_table in _GUARD_TRIGGERS:
            name, table = name_table.split("|")
            await conn.execute(text(f"DROP TRIGGER IF EXISTS {name} ON {table}"))
        for ddl in (
            APPEND_ONLY_TRIGGER_DDL,
            APPEND_ONLY_TRUNCATE_DDL,
            RESOLUTION_TRIGGER_DDL,
            CYCLE_GUARD_TRIGGER_DDL,
            INSERT_GUARD_TRIGGER_DDL,
        ):
            await conn.execute(text(ddl))


async def create_analysis_observation(
    engine,
    *,
    asset_id=None,
    username: str = "synthetic-verifier",
    description: str = "SYNTHETIC REMEDIATION OBSERVATION",
) -> str:
    """Inserts one synthetic analysis_history row and returns its id as text."""
    async with session_factory(engine)() as db:
        row = AnalysisHistory(
            event_id="4625",
            provider="synthetic",
            username=username,
            description=description,
            asset_id=asset_id,
        )
        db.add(row)
        await db.commit()
        return str(row.id)


async def attach_analysis_evidence(
    engine,
    incident_id,
    *,
    actor: str = "engineer",
    asset_id=None,
) -> uuid.UUID:
    """Attaches one verification-grade analysis reference; returns evidence_id."""
    from backend.domain.incident.service import EvidenceInput, IncidentService

    source_id = await create_analysis_observation(engine, asset_id=asset_id)
    async with session_factory(engine)() as db:
        await IncidentService(db).attach_evidence(
            incident_id,
            [
                EvidenceInput(
                    source_type="analysis",
                    source_id=source_id,
                    observed_at=datetime.now(UTC),
                )
            ],
            actor=actor,
        )
    async with session_factory(engine)() as db:
        row = (
            await db.execute(
                select(IncidentEvidence).where(IncidentEvidence.source_id == source_id)
            )
        ).scalars().first()
        if row is None:
            raise AssertionError("evidence was not attached")
        return row.evidence_id
