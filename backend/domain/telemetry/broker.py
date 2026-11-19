"""EIMS Redis Stream broker with consumer-group recovery and durable acknowledgements."""
from abc import ABC, abstractmethod
from datetime import UTC, datetime
import json
import uuid
from typing import Any

from fastapi import HTTPException, status
from redis.exceptions import ResponseError

from backend.core.logger import get_logger
from backend.domain.telemetry.schemas import AgentHeartbeatRequest, AgentWinlogRequest, StreamIngestionResponse
from backend.infrastructure.cache import AsynchronousCacheManager

logger = get_logger("eims.telemetry.broker")
TELEMETRY_STREAM_KEY = "eims:telemetry:ingestion"
TELEMETRY_CONSUMER_GROUP = "eims:telemetry:consumer"
TELEMETRY_DEAD_LETTER_STREAM_KEY = "eims:telemetry:dead-letter"
# Retained as a monitoring threshold only; MAXLEN is unsafe for pending entries.
MAX_STREAM_LENGTH = 100000
SOURCE_EVENT_KEY_MAX_LENGTH = 160


def is_nogroup_error(exc: BaseException) -> bool:
    """True for a Redis ResponseError meaning the stream/consumer group no longer exists."""
    return isinstance(exc, ResponseError) and "NOGROUP" in str(exc).upper()


class AbstractTelemetryBroker(ABC):
    """Transport contract shared by Redis and hermetic test brokers."""
    @abstractmethod
    async def publish_heartbeat(self, payload: AgentHeartbeatRequest, cert_fingerprint: str,
                                source_event_key: str | None = None) -> StreamIngestionResponse: ...
    @abstractmethod
    async def publish_winlog(self, payload: AgentWinlogRequest, cert_fingerprint: str,
                             source_event_key: str | None = None) -> StreamIngestionResponse: ...
    @abstractmethod
    async def fetch_stream_batch(self, stream_key: str, last_id: str, batch_size: int) -> tuple[list, str, str | None]: ...
    @abstractmethod
    async def ack_stream_messages(self, stream_key: str, message_ids: list[str]) -> None: ...
    @abstractmethod
    async def dead_letter_stream_message(self, stream_key: str, message_id: str,
                                         entry: dict[str, Any], reason: str) -> None: ...


class RedisTelemetryStreamBroker(AbstractTelemetryBroker):
    """At-least-once Redis Streams transport with stale-pending recovery."""
    def __init__(self, cache_manager: AsynchronousCacheManager, *, consumer_name: str | None = None,
                 group_name: str = TELEMETRY_CONSUMER_GROUP, reclaim_idle_ms: int = 30000):
        self._cache = cache_manager
        self.consumer_name = consumer_name or f"eims-{uuid.uuid4().hex[:12]}"
        self.group_name = group_name
        self.reclaim_idle_ms = max(0, int(reclaim_idle_ms))
        self._ready_groups: set[tuple[str, str]] = set()

    async def _ensure_group(self, client, stream_key: str) -> None:
        identity = (stream_key, self.group_name)
        if identity in self._ready_groups:
            return
        try:
            await client.xgroup_create(name=stream_key, groupname=self.group_name, id="0-0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc).upper():
                raise
        self._ready_groups.add(identity)

    async def _heal_missing_group(self, client, stream_key: str) -> None:
        """Redis lost the stream/group (NOGROUP): drop only this group's ready flag and recreate it.

        Never deletes streams/groups and never touches pending entries. Recreation failure is
        logged and swallowed; the flag stays cleared so the next poll (after the caller's
        polling interval) retries. There is deliberately no inner retry loop.
        """
        self._ready_groups.discard((stream_key, self.group_name))
        logger.warning("Telemetry consumer group missing (NOGROUP); recreating on next poll")
        try:
            await self._ensure_group(client, stream_key)
        except Exception:
            logger.exception("Telemetry consumer group recreation failed; will retry next poll")

    @staticmethod
    def _text(value):
        return value.decode("utf-8") if isinstance(value, bytes) else value

    async def _publish_to_stream(self, event_type: str, payload_json: str, cert_fingerprint: str,
                                 source_event_key: str | None = None) -> StreamIngestionResponse:
        self._cache._validate_namespace(TELEMETRY_STREAM_KEY)
        client = self._cache._redis_client
        if client is None:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="Telemetry ingestion temporarily unavailable",
                                headers={"Retry-After": "5"})
        if source_event_key is not None and (not source_event_key or len(source_event_key) > SOURCE_EVENT_KEY_MAX_LENGTH):
            raise HTTPException(status_code=422, detail="Invalid telemetry idempotency key")
        envelope = {"event_type": event_type, "cert_fingerprint": cert_fingerprint,
                    "payload": payload_json, "ingested_at": datetime.now(UTC).isoformat()}
        if source_event_key is not None:
            envelope["source_event_key"] = source_event_key
        try:
            # Never MAXLEN-trim: it can delete unacknowledged consumer-group entries.
            stream_id = await client.xadd(name=TELEMETRY_STREAM_KEY, fields=envelope)
            if not stream_id:
                raise RuntimeError("Redis did not return a stream identifier")
            return StreamIngestionResponse(status="accepted", stream_job_id=self._text(stream_id))
        except HTTPException:
            raise
        except Exception:
            logger.exception("Redis telemetry XADD failed; ingestion was not confirmed")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="Telemetry ingestion temporarily unavailable",
                                headers={"Retry-After": "5"}) from None

    async def publish_heartbeat(self, payload: AgentHeartbeatRequest, cert_fingerprint: str,
                                source_event_key: str | None = None) -> StreamIngestionResponse:
        return await self._publish_to_stream("heartbeat", payload.model_dump_json(), cert_fingerprint, source_event_key)

    async def publish_winlog(self, payload: AgentWinlogRequest, cert_fingerprint: str,
                             source_event_key: str | None = None) -> StreamIngestionResponse:
        return await self._publish_to_stream("winlog", payload.model_dump_json(), cert_fingerprint, source_event_key)

    async def fetch_stream_batch(self, stream_key: str, last_id: str, batch_size: int) -> tuple[list, str, str | None]:
        client = self._cache._redis_client
        if client is None:
            return [], stream_key, "broker-unavailable"
        try:
            await self._ensure_group(client, stream_key)
            claimed = await client.xautoclaim(
                name=stream_key, groupname=self.group_name, consumername=self.consumer_name,
                min_idle_time=self.reclaim_idle_ms, start_id="0-0", count=batch_size)
            pending = claimed[1] if isinstance(claimed, (tuple, list)) else claimed.get("messages", [])
            if pending:
                return [(self._text(mid), fields) for mid, fields in pending], stream_key, None
            streams = await client.xreadgroup(
                groupname=self.group_name, consumername=self.consumer_name,
                streams={stream_key: ">"}, count=batch_size, block=10)
        except ResponseError as exc:
            if is_nogroup_error(exc):
                await self._heal_missing_group(client, stream_key)
                return [], stream_key, "group-recreated"
            logger.exception("Telemetry consumer-group read/recovery failed")
            return [], stream_key, "stream-read-error"
        except Exception:
            logger.exception("Telemetry consumer-group read/recovery failed")
            return [], stream_key, "stream-read-error"
        if not streams:
            return [], stream_key, None
        messages = [(self._text(mid), fields)
                    for _, entries in streams for mid, fields in entries]
        return messages, stream_key, None

    async def ack_stream_messages(self, stream_key: str, message_ids: list[str]) -> None:
        client = self._cache._redis_client
        if client is None:
            raise RuntimeError("Redis unavailable; telemetry acknowledgement not confirmed")
        if not message_ids:
            return
        acknowledged = await client.xack(stream_key, self.group_name, *message_ids)
        if acknowledged != len(message_ids):
            raise RuntimeError(f"Redis acknowledged {acknowledged} of {len(message_ids)} telemetry entries")
        # Cleanup is best-effort only after the durable ACK has succeeded.
        try:
            await client.xdel(stream_key, *message_ids)
        except Exception:
            logger.warning("Telemetry entries were acknowledged but stream cleanup failed")

    async def dead_letter_stream_message(self, stream_key: str, message_id: str,
                                         entry: dict[str, Any], reason: str) -> None:
        client = self._cache._redis_client
        if client is None:
            raise RuntimeError("Redis unavailable; telemetry dead-letter write not confirmed")
        await client.xadd(TELEMETRY_DEAD_LETTER_STREAM_KEY, fields={
            "source_stream": stream_key, "source_stream_id": message_id,
            "reason": reason[:160], "entry": json.dumps(entry, ensure_ascii=False, default=str),
            "failed_at": datetime.now(UTC).isoformat()})


class StubTelemetryStreamBroker(AbstractTelemetryBroker):
    """In-memory at-least-once broker; entries remain until explicit ACK."""
    def __init__(self):
        self.stream_buffer: list[dict[str, Any]] = []
        self.dead_letter_buffer: list[dict[str, Any]] = []
        self._counter = 0

    async def _push(self, event_type: str, payload_json: str, cert_fingerprint: str,
                    source_event_key: str | None = None) -> StreamIngestionResponse:
        self._counter += 1
        job_id = f"stub-{int(datetime.now(UTC).timestamp() * 1000)}-{self._counter}"
        entry = {"sequence_id": job_id, "event_type": event_type, "cert_fingerprint": cert_fingerprint,
                 "payload": payload_json, "queued_at": datetime.now(UTC).isoformat()}
        if source_event_key is not None:
            entry["source_event_key"] = source_event_key
        self.stream_buffer.append(entry)
        return StreamIngestionResponse(status="accepted", stream_job_id=job_id, queued_at=entry["queued_at"])

    async def publish_heartbeat(self, payload: AgentHeartbeatRequest, cert_fingerprint: str,
                                source_event_key: str | None = None) -> StreamIngestionResponse:
        return await self._push("heartbeat", payload.model_dump_json(), cert_fingerprint, source_event_key)

    async def publish_winlog(self, payload: AgentWinlogRequest, cert_fingerprint: str,
                             source_event_key: str | None = None) -> StreamIngestionResponse:
        return await self._push("winlog", payload.model_dump_json(), cert_fingerprint, source_event_key)

    async def fetch_stream_batch(self, stream_key: str, last_id: str, batch_size: int) -> tuple[list, str, str | None]:
        batch = self.stream_buffer[:batch_size]
        return [(entry["sequence_id"], entry) for entry in batch], stream_key, None

    async def ack_stream_messages(self, stream_key: str, message_ids: list[str]) -> None:
        acknowledged = set(message_ids)
        self.stream_buffer[:] = [entry for entry in self.stream_buffer if entry["sequence_id"] not in acknowledged]

    async def dead_letter_stream_message(self, stream_key: str, message_id: str,
                                         entry: dict[str, Any], reason: str) -> None:
        self.dead_letter_buffer.append({"source_stream": stream_key, "source_stream_id": message_id,
                                        "entry": dict(entry), "reason": reason})
