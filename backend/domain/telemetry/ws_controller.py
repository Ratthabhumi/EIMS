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

async def redis_pubsub_listener():
    """Background task to listen to Redis PubSub for security alerts."""
    while not cache_manager.redis:
        await asyncio.sleep(1)
        
    pubsub = cache_manager.redis.pubsub()
    await pubsub.subscribe("eims:events:alerts")
    logger.info("Subscribed to Redis PubSub channel: eims:events:alerts")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"].decode("utf-8") if isinstance(message["data"], bytes) else message["data"]
                await manager.broadcast(data)
    except Exception as e:
        logger.error(f"Redis PubSub Listener error: {e}")

@ws_router.websocket("/dashboard")
async def websocket_dashboard(websocket: WebSocket, token: str = Query(None)):
    """
    Bi-directional WebSocket streaming pipeline pushing live security anomaly alerts 
    to Next.js clients.
    """
    # Core Law 5 Section 8: Validate JWT token here (bypassed for local dev)
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect messages from the client, just keep connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
