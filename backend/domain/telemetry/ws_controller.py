"""
==============================================================================
EIMS Telemetry WebSocket Controller
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Section 8
==============================================================================
"""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.core.logger import get_logger
from backend.infrastructure.cache import cache_manager
from backend.core.config import settings

logger = get_logger("eims.api.ws")

ws_router = APIRouter(prefix="/api/v1/ws", tags=["Real-Time Dashboard"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()


def _normalise_origin(value: str) -> str:
    return str(value or "").strip().rstrip("/").lower()


def websocket_origin_refusal(websocket) -> str | None:
    """Returns the reason a handshake must be refused, or None when it may proceed.

    Contract (independent of application login, which does not exist):
    * An ``Origin`` header, when present, must exactly match an entry of ``settings.CORS_ORIGINS`` (scheme, host,
      port). ``*`` and ``null`` never match, and an empty/misconfigured allowlist matches nothing (fail closed).
    * A missing ``Origin`` header is a non-browser client (a browser always sends it, so it cannot be a cross-site
      hijack). It is accepted in the default local/demo mode and refused when ``AUTH_MODE=secure``.
    """
    try:
        headers = websocket.headers
        origin = headers.get("origin") if headers is not None else None
    except Exception:
        return "unreadable handshake headers"
    if origin is None or str(origin).strip() == "":
        if str(settings.AUTH_MODE).lower() == "secure":
            return "missing Origin in secure mode"
        return None
    allowed = {_normalise_origin(o) for o in (settings.CORS_ORIGINS or []) if _normalise_origin(o) not in {"", "*", "null"}}
    if _normalise_origin(origin) in allowed:
        return None
    return "Origin not in allowlist"

async def redis_pubsub_listener():
    """Background task to listen to Redis PubSub for security alerts."""
    while not cache_manager.redis:
        try:
            await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            return

    pubsub = cache_manager.redis.pubsub()
    try:
        await pubsub.subscribe("eims:events:alerts")
        logger.info("Subscribed to Redis PubSub channel: eims:events:alerts")

        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"].decode("utf-8") if isinstance(message["data"], bytes) else message["data"]
                await manager.broadcast(data)
    except asyncio.CancelledError:
        logger.info("Redis PubSub Listener cancelled cleanly.")
    except Exception as e:
        logger.error(f"Redis PubSub Listener error: {e}")
    finally:
        try:
            await pubsub.unsubscribe("eims:events:alerts")
            await pubsub.aclose()
        except Exception:
            pass

@ws_router.websocket("/dashboard")
async def websocket_dashboard(websocket: WebSocket, token: str = Query(None)):
    """
    Bi-directional WebSocket streaming pipeline pushing live security anomaly alerts 
    to Next.js clients.
    """
    # Application login is not used (no user session is required), but the Origin boundary is independent of
    # login and stays fail-closed: a browser page on any other origin must not be able to open this stream.
    refusal = websocket_origin_refusal(websocket)
    if refusal:
        logger.warning(f"Dashboard WebSocket refused: {refusal}")
        await websocket.close(code=1008, reason="Origin not allowed")
        return
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect messages from the client, just keep connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
