"""
==============================================================================
EIMS Core Gateway & Telemetry Collector Application Root
Governed by EIMS Documentation System (EDS v1.0.0)
Source-Available All Rights Reserved Policy
==============================================================================
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core.config import settings
from backend.core.exceptions import EIMSProblemException, eims_problem_exception_handler, global_unhandled_exception_handler
from backend.core.logger import get_logger
from backend.infrastructure.database import database_engine
from backend.infrastructure.cache import cache_manager

logger = get_logger("eims.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Asynchronous lifecycle context manager handling core connection bootstrapping
    and graceful termination across relational and in-memory persistence tiers.
    """
    logger.info("Initializing EIMS Core Gateway Services (v0.2.0-dev)...")
    logger.info(f"Connecting to Postgres Relational Pool at: {settings.DB_HOST}:{settings.DB_PORT}")
    await database_engine.initialize()
    
    logger.info(f"Connecting to Redis Telemetry Broker at: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    await cache_manager.initialize()
    
    logger.info("EIMS Backend infrastructure initialized successfully. Ready to receive high-velocity diagnostic telemetry.")
    yield
    
    logger.info("Initiating graceful shutdown sequence for EIMS backend infrastructure...")
    await cache_manager.close()
    await database_engine.close()
    logger.info("All persistent connections drained. EIMS shutdown complete.")


app = FastAPI(
    title="Enterprise Infrastructure Management System (EIMS) API Gateway",
    description=(
        "Authoritative Core Gateway and Telemetry Ingestion interface for compute discovery, "
        "hardware inventory tracking, automated OCR asset registration, continuous Windows log analysis, "
        "and rules-based compliance auditing. Governed strictly under EDS v1.0.0 and Core Law 5."
    ),
    version="0.2.0-dev",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Register RFC 7807 Problem Details global exception middlewares
app.add_exception_handler(EIMSProblemException, eims_problem_exception_handler)
app.add_exception_handler(Exception, global_unhandled_exception_handler)

# Configure Cross-Origin Resource Sharing for Next.js Operational Dashboard UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health", tags=["Operational Observability"])
async def read_system_health() -> JSONResponse:
    """
    Returns live diagnostic health evaluation metrics covering relational database
    transaction pooling, Redis stream reachability, and architectural compliance status.
    """
    db_ok = await database_engine.ping()
    cache_ok = await cache_manager.ping()
    
    status_code = 200 if (db_ok and cache_ok) else 503
    status_msg = "HEALTHY" if status_code == 200 else "DEGRADED"
    
    return JSONResponse(
        status_code=status_code,
        content={
            "system": "EIMS Core Gateway",
            "version": app.version,
            "status": status_msg,
            "licensing_model": "Source-Available (All Rights Reserved)",
            "components": {
                "postgresql_pgbouncer_tier": "UP" if db_ok else "DOWN",
                "redis_volatile_lru_tier": "UP" if cache_ok else "DOWN",
            }
        }
    )
