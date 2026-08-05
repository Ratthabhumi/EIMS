"""
==============================================================================
EIMS Pydantic BaseSettings Core Configuration
Governed by EIMS Documentation System (EDS v1.0.0)
==============================================================================
"""

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EIMSSettings(BaseSettings):
    """
    Authoritative runtime environment parameters and secrets management engine
    validated via strict Pydantic parsing rules.
    """
    # System Runtime Metrics
    ENVIRONMENT: str = Field(default="development", description="Execution tier: development, staging, or production")
    LOG_LEVEL: str = Field(default="INFO", description="Structured JSON logging diagnostic verbosity")
    
    # PostgreSQL & PgBouncer Transaction Pool Parameters (Core Law 3)
    DB_USER: str = Field(default="eims_user")
    DB_PASSWORD: str = Field(default="eims_secret_password")
    DB_HOST: str = Field(default="localhost", description="Target hostname for DB connection (use localhost for local venv)")
    DB_PORT: int = Field(default=6432, description="Connect directly through PgBouncer transaction pool port 6432")
    DB_NAME: str = Field(default="eims_registry")
    DB_POOL_SIZE: int = Field(default=20, description="Async SQLAlchemy internal network connection pool bounds")
    DB_MAX_OVERFLOW: int = Field(default=10)

    # Redis Telemetry Ingestion Queue & Cache Parameters (Core Law 4)
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB_INDEX: int = Field(default=0)
    REDIS_MAX_CONNECTIONS: int = Field(default=100)

    # Security & Cryptographic Auth Contracts (Core Law 5)
    JWT_SECRET_KEY: str = Field(
        default="09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7",
        description="HMAC SHA-256 / EdDSA asymmetric signature verification secret"
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXMIRES_MINUTES: int = Field(default=60)
    
    # Next.js Operational Dashboard CORS Configuration
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"],
        description="Allowed frontend operational origin URLs"
    )

    model_config = SettingsConfigDict(
        env_prefix="EIMS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """Constructs canonical asynchronous asyncpg connection URL."""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def redis_url(self) -> str:
        """Constructs canonical Redis connection URI string."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB_INDEX}"


# Global instantiated settings singleton
settings = EIMSSettings()
