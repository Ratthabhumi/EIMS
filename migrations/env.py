"""
==============================================================================
EIMS Alembic Asynchronous Environment Script
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 3 & 4 Compliance
==============================================================================
"""
import asyncio
from logging.config import fileConfig
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from backend.core.config import settings
from backend.infrastructure.database import Base
# Import canonical domain ORM models so Alembic autogenerate discovers schemas
from backend.domain.asset_registry import InfrastructureAsset, HardwareInventory, AuditLog
from backend.domain.asset_registry.ocr_worker import OCRRegistrationRecord
from backend.domain.telemetry.models import TelemetryMetric, WindowsEventLog
from backend.domain.evaluation.models import ServiceSession, ServiceEvaluation
from backend.domain.analyzer.models.user import User
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.models.vector import VectorKnowledge

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Authoritative declarative target metadata for automatic diff generation
target_metadata = Base.metadata

# Inject dynamic Pydantic async database connection URL into Alembic config
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """
    Executes database migrations in 'offline' mode.
    Configures context with static SQL URL without requiring active network DB socket connection.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True, # Ensure field type mutations trigger migration upgrades
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Invokes target migration commands across verified active DB connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Asynchronous connection handler establishing pooled non-blocking sockets
    compatible with PgBouncer transaction engines and asyncpg protocols.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=None,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Enters asyncio execution loops when running in interactive online mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
