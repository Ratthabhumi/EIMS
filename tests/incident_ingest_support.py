"""Disposable PostgreSQL/Redis gate for Incident Core v1.1 ingestion tests.

Only a NEW, explicitly provisioned loopback PostgreSQL database/role and Redis instance are accepted.
Both must prove their identity with a sentinel written at provisioning time (see the engineering-memory
snapshot for the provisioning commands). There is no fallback to application/operational settings,
and no existing service (including the Incident Core v1 test database) is accepted.
"""
from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.domain.incident_ingest.models import IncidentIngestOutbox
from backend.domain.telemetry.models import TelemetryMetric, WindowsEventLog
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.infrastructure.database import Base
from tests.incident_db_support import INCIDENT_TABLES, scoped_engine, session_factory

PG_PORT = 56460
REDIS_PORT = 56461
PG_DATABASE = "eims_ingest_v11_test"
PG_USER = "eims_ingest_v11_app"  # NOSUPERUSER, no CREATEROLE
PG_URL_ENV = "EIMS_INGEST_TEST_DATABASE_URL"
REDIS_URL_ENV = "EIMS_INGEST_TEST_REDIS_URL"
SENTINEL_ENV = "EIMS_INGEST_TEST_SENTINEL"
REDIS_SENTINEL_KEY = "eims:disposable:incident-ingest-v11"

INGEST_TABLES = [
    *INCIDENT_TABLES, AnalysisHistory.__table__, WindowsEventLog.__table__,
    TelemetryMetric.__table__, IncidentIngestOutbox.__table__,
]

_verified: set[str] = set()


def _sentinel() -> str:
    value = os.environ.get(SENTINEL_ENV)
    if not value:
        pytest.skip(f"{SENTINEL_ENV} is not configured; disposable services are required")
    return value


def require_pg_url() -> str:
    value = os.environ.get(PG_URL_ENV)
    if not value:
        pytest.skip(f"{PG_URL_ENV} is not configured; disposable PostgreSQL is required")
    url = make_url(value)
    if (url.drivername != "postgresql+asyncpg" or url.host not in {"127.0.0.1", "localhost"}
            or url.port != PG_PORT or url.database != PG_DATABASE or url.username != PG_USER):
        raise ValueError("Refusing database: not the dedicated Incident Ingest v1.1 disposable target")
    return value


def require_redis_url() -> str:
    value = os.environ.get(REDIS_URL_ENV)
    if not value:
        pytest.skip(f"{REDIS_URL_ENV} is not configured; disposable Redis is required")
    url = make_url(value.replace("redis://", "postgresql://", 1))  # reuse URL parsing only
    if url.host not in {"127.0.0.1", "localhost"} or url.port != REDIS_PORT:
        raise ValueError("Refusing Redis: not the dedicated Incident Ingest v1.1 disposable target")
    return value


async def verify_pg_identity(url: str) -> None:
    if "pg" in _verified:
        return
    expected = f"EIMS-DISPOSABLE-INGEST-V11:{_sentinel()}"
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            comment = await conn.scalar(text(
                "SELECT shobj_description(oid, 'pg_database') FROM pg_database "
                "WHERE datname = current_database()"))
            is_super = await conn.scalar(text(
                "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"))
    finally:
        await engine.dispose()
    if comment != expected:
        raise ValueError("Refusing database: disposable sentinel mismatch")
    if is_super:
        raise ValueError("Refusing database: test role must be non-superuser")
    _verified.add("pg")


async def verify_redis_identity(client) -> None:
    if "redis" in _verified:
        return
    stored = await client.get(REDIS_SENTINEL_KEY)
    stored = stored.decode() if isinstance(stored, bytes) else stored
    if stored != _sentinel():
        raise ValueError("Refusing Redis: disposable sentinel mismatch")
    _verified.add("redis")


async def create_ingest_schema(url: str):
    """Unique schema (retained, never dropped) with every table the ingestion path touches."""
    await verify_pg_identity(url)
    schema = "eims_ingest_" + uuid.uuid4().hex
    bootstrap = create_async_engine(url, poolclass=NullPool)
    try:
        async with bootstrap.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    finally:
        await bootstrap.dispose()
    engine = scoped_engine(url, schema)
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=INGEST_TABLES))
    return schema, engine


@asynccontextmanager
async def redis_client(url: str):
    import redis.asyncio as aioredis
    client = aioredis.from_url(url, decode_responses=False)
    try:
        await verify_redis_identity(client)
        yield client
    finally:
        await client.aclose()


__all__ = ["session_factory", "create_ingest_schema", "redis_client", "require_pg_url", "require_redis_url"]
