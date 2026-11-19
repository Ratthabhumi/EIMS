"""
==============================================================================
EIMS Core Gateway & Telemetry Collector Application Root
Governed by EIMS Documentation System (EDS v1.0.0)
Source-Available All Rights Reserved Policy
==============================================================================
"""

import asyncio
import json
import os
import re
import time
import uuid
from pathlib import Path
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from backend.api.routers import evaluations
from backend.core.config import settings
from backend.core.exceptions import (
    EIMSProblemException,
    eims_problem_exception_handler,
    global_unhandled_exception_handler,
    validation_problem_exception_handler,
)
from backend.core.health_probe import HealthProbeCoordinator
from backend.core.logger import get_logger
from backend.domain.analyzer.auth import seed_users
from backend.domain.asset_registry import asset_router
from backend.domain.asset_registry.audit_controller import audit_router
from backend.domain.asset_registry.ocr_worker import ocr_worker
from backend.domain.incident.controller import incident_router
from backend.domain.incident_ingest.consumer import incident_ingest_consumer
from backend.domain.search.controller import search_router
from backend.domain.telemetry import telemetry_router
from backend.domain.telemetry.evtx_worker import evtx_worker
from backend.domain.telemetry.query_controller import telemetry_query_router
from backend.domain.telemetry.worker import telemetry_worker
from backend.domain.telemetry.ws_controller import redis_pubsub_listener, ws_router
from backend.domain.timeline.controller import timeline_router
from backend.infrastructure.cache import cache_manager
from backend.infrastructure.database import database_engine

logger = get_logger("eims.main")

# Same-origin demo console for the 2026-11-24 demonstration (no mock data).
_DEMO_CONSOLE = Path(__file__).resolve().parent / "api" / "static" / "demo_console.html"

# Dashboard health refreshes every 15s. Reuse healthy dependency evidence for 20s;
# retry degraded snapshots quickly so recovery is visible without a thundering herd.
_health_probe = HealthProbeCoordinator(ttl_seconds=20.0, degraded_ttl_seconds=3.0)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Asynchronous lifecycle context manager handling core connection bootstrapping
    and graceful termination across relational and in-memory persistence tiers.
    """
    logger.info("Initializing EIMS Core Gateway Services (v0.3.0)...")
    logger.info(f"Connecting to Postgres Relational Pool at: {settings.DB_HOST}:{settings.DB_PORT}")
    await database_engine.initialize()
    # Fail closed on a live connection that is not the configured runtime
    # identity; readiness must not report "up" for a mis-targeted database.
    try:
        await database_engine.verify_runtime_identity()
    except Exception:
        await database_engine.close()
        raise
    
    logger.info(f"Connecting to Redis Telemetry Broker at: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    soft = (os.environ.get("EIMS_DEMO_SOFT_DEPS") or "").strip() == "1"
    if soft:
        logger.warning(
            "EIMS_DEMO_SOFT_DEPS=1: cache, object storage and background workers "
            "are optional. This mode is for the isolated demo environment only."
        )
    try:
        await cache_manager.initialize()
    except Exception as exc:  # noqa: BLE001
        if not soft:
            raise
        logger.warning("cache unavailable in soft-deps mode: %s", type(exc).__name__)

    logger.info("Seeding admin bootstrap account...")
    await seed_users()

    pubsub_task: asyncio.Task | None = None
    started_workers = False
    if not soft:
        # Start Redis WebSocket PubSub Listener
        pubsub_task = asyncio.create_task(redis_pubsub_listener())

        logger.info("Starting background workers...")
        await ocr_worker.start()
        await evtx_worker.start()
        await telemetry_worker.start()
        await incident_ingest_consumer.start()
        started_workers = True
    else:
        logger.warning("background workers are not started in soft-deps mode")

    logger.info("EIMS Backend infrastructure initialized successfully. Ready to receive high-velocity diagnostic telemetry.")
    yield
    
    logger.info("Initiating graceful shutdown sequence for EIMS backend infrastructure...")
    if pubsub_task is not None:
        pubsub_task.cancel()
        try:
            await asyncio.wait_for(pubsub_task, timeout=1.5)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        except Exception as e:
            logger.warning(f"Redis PubSub Listener shutdown: {e}")
    # Stop the incident consumer first: it drains its in-flight batch (bounded); unacked entries
    # stay pending in Redis and are reclaimed on the next start, so no work is lost.
    if started_workers:
        await incident_ingest_consumer.stop()
        await telemetry_worker.stop()
        await evtx_worker.stop()
        await ocr_worker.stop()
    try:
        await cache_manager.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache close failed during shutdown: %s", type(exc).__name__)
    await database_engine.close()
    from backend.infrastructure.object_store import object_storage
    await object_storage.close()
    logger.info("All persistent connections drained. EIMS shutdown complete.")


app = FastAPI(
    title="Enterprise Infrastructure Management System (EIMS) API Gateway",
    description=(
        "Authoritative Core Gateway and Telemetry Ingestion interface for compute discovery, "
        "hardware inventory tracking, automated OCR asset registration, continuous Windows log analysis, "
        "and rules-based compliance auditing. Governed strictly under EDS v1.0.0 and Core Law 5."
    ),
    version="0.3.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_correlation(request, call_next):
    """Propagate a validated request ID and emit secret-free timing/status evidence."""
    request_id = request.headers.get("x-request-id", "")
    if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", request_id, re.I):
        request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("eims_backend_request_failed %s", json.dumps({
            "requestId": request_id, "method": request.method, "path": request.url.path,
            "durationMs": round((time.perf_counter() - started) * 1000, 1),
        }))
        raise
    response.headers["X-Request-ID"] = request_id
    logger.info("eims_backend_request %s", json.dumps({
        "requestId": request_id, "method": request.method, "path": request.url.path,
        "status": response.status_code, "durationMs": round((time.perf_counter() - started) * 1000, 1),
    }))
    return response


# Instrument FastAPI to expose Prometheus metrics on /metrics
Instrumentator().instrument(app).expose(app)

# Register RFC 7807 Problem Details global exception middlewares
app.add_exception_handler(EIMSProblemException, eims_problem_exception_handler)
app.add_exception_handler(RequestValidationError, validation_problem_exception_handler)
app.add_exception_handler(Exception, global_unhandled_exception_handler)

# Configure Cross-Origin Resource Sharing for Next.js Operational Dashboard UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.api.routers import agents, evaluations

# Register Modular Domain APIRouters (Core Law 5 Compliance)
app.include_router(asset_router)
app.include_router(telemetry_router)
app.include_router(ws_router)
app.include_router(evaluations.router)
app.include_router(agents.router)

# Register Sprint 10 Query Layer Routers (Global Search & Timeline Phase D.1)
app.include_router(search_router)
app.include_router(timeline_router)
app.include_router(audit_router)
app.include_router(telemetry_query_router)

# Incident Core v1 (backend-only; evidence references, no payload copies)
app.include_router(incident_router)

from backend.api.routers.analyzer import (
    admin,
    analyze,
    feedback,
    history,
    knowledge,
    obsidian,
    stats,
)
from backend.api.routers.analyzer import auth as analyzer_auth

app.include_router(analyzer_auth.router, prefix="/api/v1/auth", tags=["Analyzer Auth"])
app.include_router(analyze.router, prefix="/api/v1/analyze", tags=["Analyzer"])
app.include_router(history.router, prefix="/api/v1/history", tags=["Analyzer History"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["Verified Knowledge"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["Analyzer Stats"])
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Analyzer Feedback"])
app.include_router(obsidian.router, prefix="/api/v1/obsidian", tags=["Analyzer Obsidian"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Analyzer Admin"])


@app.get("/demo", include_in_schema=False)
async def demo_console() -> FileResponse:
    """Thin same-origin console for the 2026-11-24 demonstration.

    It calls the real API with a real bearer token; there is no mock data and no
    embedded credential. Served by the API so there is a single HTTPS origin and
    no CORS surface.
    """
    return FileResponse(_DEMO_CONSOLE)


@app.get("/api/v1/ready", tags=["Operational Observability"])
async def readiness() -> JSONResponse:
    """Readiness for the demo deployment: the database is the only required tier.

    ``/health`` reports every dependency and is intentionally DEGRADED when the
    optional cache/storage tiers are absent (``EIMS_DEMO_SOFT_DEPS=1``). A load
    balancer must not treat that as "not ready", so this endpoint answers for the
    required tier only.
    """
    if database_engine._engine is None:
        return JSONResponse(status_code=503, content={"status": "starting", "database": False})
    ok = await database_engine.ping()
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ready" if ok else "database_unavailable", "database": ok},
    )


@app.get("/api/v1/health", tags=["Operational Observability"])
async def read_system_health() -> JSONResponse:
    """
    Returns live diagnostic health evaluation metrics covering relational database
    transaction pooling, Redis stream reachability, Object Storage, and architectural compliance status.
    """
    from backend.infrastructure.object_store import object_storage

    db_ok, cache_ok, storage_ok = await _health_probe.check(
        database_engine.ping, cache_manager.ping, object_storage.ping
    )
    
    status_code = 200 if (db_ok and cache_ok and storage_ok) else 503
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
                "minio_object_storage_tier": "UP" if storage_ok else "DOWN",
            }
        }
    )



