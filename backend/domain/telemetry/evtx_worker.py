"""Durable EVTX job consumer using Redis Streams and replay-safe event keys."""
import asyncio
import base64
import hashlib
import json
import logging
from itertools import islice
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import unquote, urlparse

from pydantic import ValidationError
from redis.exceptions import ResponseError

from backend.domain.telemetry.broker import RedisTelemetryStreamBroker, is_nogroup_error
from backend.domain.telemetry.evtx_parser import parse_evtx_records
from backend.domain.telemetry.schemas import AgentWinlogRequest
from backend.infrastructure.cache import cache_manager
from backend.infrastructure.object_store import MinIOStorageManager, object_storage

logger = logging.getLogger("eims.worker.evtx")
EVTX_STREAM_KEY = "eims:jobs:evtx:stream"
EVTX_CONSUMER_GROUP = "eims:jobs:evtx:workers"
EVTX_DEAD_LETTER_STREAM_KEY = "eims:jobs:evtx:dead-letter"
LEGACY_EVTX_LIST_KEY = "eims:jobs:evtx"
INVALID_UPLOADER_REASON = "missing-or-invalid-uploader-fingerprint"
_SHA256_HEX = re.compile(r"^[a-fA-F0-9]{64}$")
MAX_EVTX_FILE_BYTES = 64 * 1024 * 1024
MAX_EVTX_RECORDS_PER_FILE = 100_000
_LEGACY_MIGRATE_LUA = """
local raw = redis.call('LINDEX', KEYS[1], -1)
if not raw then return nil end
local id = redis.call('XADD', KEYS[2], '*', 'payload', raw)
redis.call('RPOP', KEYS[1])
return id
"""


class EVTXBackgroundWorker:
    def __init__(self, polling_interval: int = 5, *, redis_client=None, broker=None,
                 consumer_name: str | None = None, reclaim_idle_ms: int = 30000,
                 max_delivery_attempts: int = 5):
        self.polling_interval = polling_interval
        self._running = False
        self._task = None
        self._redis_override = redis_client
        self.consumer_name = consumer_name or f"evtx-{uuid.uuid4().hex[:12]}"
        self.reclaim_idle_ms = max(0, int(reclaim_idle_ms))
        self.max_delivery_attempts = max(1, int(max_delivery_attempts))
        self._group_ready = False
        self.broker = broker or RedisTelemetryStreamBroker(cache_manager=cache_manager)

    def _client(self):
        return self._redis_override or cache_manager.redis

    async def _ensure_group(self, client):
        if self._group_ready:
            return
        try:
            await client.xgroup_create(name=EVTX_STREAM_KEY, groupname=EVTX_CONSUMER_GROUP,
                                       id="0-0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc).upper():
                raise
        self._group_ready = True

    async def _heal_missing_group(self, client):
        """Redis lost the stream/group (NOGROUP): clear the ready flag and recreate the group.

        Never deletes streams/groups or touches pending entries. A recreation failure is logged
        and the flag stays cleared; the next poll (after polling_interval) retries. No inner loop.
        """
        self._group_ready = False
        logger.warning("EVTX consumer group missing (NOGROUP); recreating")
        try:
            await self._ensure_group(client)
        except Exception as exc:
            logger.error("EVTX consumer group recreation failed (%s); will retry next poll",
                         type(exc).__name__)

    async def _migrate_legacy_list(self, client):
        # Atomic per item: XADD succeeds before RPOP, so a Redis failure cannot lose a legacy job.
        while await client.eval(_LEGACY_MIGRATE_LUA, 2, LEGACY_EVTX_LIST_KEY, EVTX_STREAM_KEY):
            continue

    async def _fetch_one(self, client):
        claimed = await client.xautoclaim(
            name=EVTX_STREAM_KEY, groupname=EVTX_CONSUMER_GROUP, consumername=self.consumer_name,
            min_idle_time=self.reclaim_idle_ms, start_id="0-0", count=1)
        pending = claimed[1] if isinstance(claimed, (tuple, list)) else claimed.get("messages", [])
        if pending:
            return pending[0]
        streams = await client.xreadgroup(
            groupname=EVTX_CONSUMER_GROUP, consumername=self.consumer_name,
            streams={EVTX_STREAM_KEY: ">"}, count=1, block=10)
        if not streams:
            return None
        return streams[0][1][0]

    async def _refresh_claim_loop(self, client, message_id: str) -> None:
        """Refresh a long-running job's pending idle time without incrementing delivery count."""
        refresh = getattr(client, "xclaim", None)
        if refresh is None:
            return  # Small hermetic fakes may omit XCLAIM; Redis clients always provide it.
        interval = max(1.0, self.reclaim_idle_ms / 3000)
        while True:
            await asyncio.sleep(interval)
            try:
                await refresh(name=EVTX_STREAM_KEY, groupname=EVTX_CONSUMER_GROUP,
                              consumername=self.consumer_name, min_idle_time=0,
                              message_ids=[message_id], idle=0, justid=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("EVTX claim refresh failed (%s); job remains pending", type(exc).__name__)
                if is_nogroup_error(exc):
                    self._group_ready = False
                    return

    async def _delivery_count(self, client, message_id: str) -> int:
        pending = await client.xpending_range(EVTX_STREAM_KEY, EVTX_CONSUMER_GROUP,
                                              message_id, message_id, 1)
        if not pending:
            return 0
        item = pending[0]
        return int(item.get("times_delivered", item.get(b"times_delivered", 1)))

    async def _ack_job(self, client, message_id: str):
        count = await client.xack(EVTX_STREAM_KEY, EVTX_CONSUMER_GROUP, message_id)
        if count != 1:
            raise RuntimeError("EVTX job ACK was not confirmed")
        try:
            await client.xdel(EVTX_STREAM_KEY, message_id)
        except Exception:
            logger.warning("EVTX job ACK confirmed but stream cleanup failed")

    async def _dead_letter(self, client, message_id: str, fields: dict, reason: str):
        await client.xadd(EVTX_DEAD_LETTER_STREAM_KEY, fields={
            "source_stream_id": message_id, "reason": reason[:160],
            "payload": json.dumps(fields, ensure_ascii=False, default=str),
            "failed_at": datetime.now(UTC).isoformat()})
        await self._ack_job(client, message_id)

    @staticmethod
    def _source_event_key(job_id: str, index: int, uploader: str, record: dict) -> str:
        metadata = record.get("metadata") or {}
        record_id = metadata.get("evtx_event_record_id")
        if record_id:
            # Stable across re-uploads of the same source event; scope to uploader, host, provider and channel.
            identity = "\x1f".join(str(value or "") for value in (
                uploader.lower(), metadata.get("evtx_computer"), metadata.get("evtx_provider_name"),
                record.get("event_channel"), record_id, record.get("occurrence_time"), record.get("event_id")))
            return "evtx:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
        raw = f"evtx:{job_id}:{index}"
        return raw if len(raw) <= 160 else "evtx:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _decode_text(item) -> tuple[str, bool]:
        """Decode a queue key/value; undecodable bytes are kept losslessly as 'base64:<data>'."""
        if not isinstance(item, bytes):
            return str(item), True
        try:
            return item.decode("utf-8"), True
        except UnicodeDecodeError:
            return "base64:" + base64.b64encode(item).decode("ascii"), False

    @classmethod
    def _decode_fields_checked(cls, fields: dict) -> tuple[dict[str, str], list[str]]:
        """Never raises on malformed UTF-8; returns (entry, names of undecodable fields)."""
        entry: dict[str, str] = {}
        undecodable: list[str] = []
        for key, value in fields.items():
            name, key_ok = cls._decode_text(key)
            decoded, value_ok = cls._decode_text(value)
            entry[name] = decoded
            if not (key_ok and value_ok):
                undecodable.append(name)
        return entry, undecodable

    @classmethod
    def _decode_fields(cls, fields: dict) -> dict[str, str]:
        return cls._decode_fields_checked(fields)[0]

    def _object_name(self, uri: str) -> str:
        parsed = urlparse(uri)
        if parsed.scheme != "s3" or parsed.netloc != object_storage.bucket:
            raise ValueError("EVTX object URI is outside the configured storage bucket")
        key = unquote(parsed.path.lstrip("/"))
        if not key or ".." in key.split("/"):
            raise ValueError("EVTX object key is invalid")
        return key

    def _download_object(self, object_name: str) -> bytes:
        if not isinstance(object_storage, MinIOStorageManager):
            raise RuntimeError("Configured object storage does not support EVTX worker downloads")
        response = object_storage.s3_client.get_object(Bucket=object_storage.bucket, Key=object_name)
        body = response["Body"]
        try:
            # Read at most one byte beyond the cap; never materialize an unbounded object.
            return body.read(MAX_EVTX_FILE_BYTES + 1)
        finally:
            body.close()

    async def start(self):
        if self._running:
            return
        self._running = True
        logger.info("EVTX Redis consumer-group worker started")
        self._task = asyncio.create_task(self._loop())

    async def _loop(self):
        while self._running:
            try:
                await self._process_pending_tasks()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if is_nogroup_error(exc):
                    # NOGROUP from a non-fetch call (e.g. XPENDING): next pass re-runs _ensure_group.
                    self._group_ready = False
                logger.error("EVTX job retained for retry (%s)", type(exc).__name__)
            try:
                await asyncio.sleep(self.polling_interval)
            except asyncio.CancelledError:
                break

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=0.5)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                pass
        logger.info("EVTX Redis consumer-group worker stopped")

    async def _process_pending_tasks(self):
        client = self._client()
        if client is None:
            raise RuntimeError("Redis unavailable; EVTX job not claimed")
        await self._ensure_group(client)
        await self._migrate_legacy_list(client)
        try:
            claimed = await self._fetch_one(client)
        except ResponseError as exc:
            if not is_nogroup_error(exc):
                raise
            await self._heal_missing_group(client)
            return
        if not claimed:
            return
        message_id, fields = claimed
        message_id = message_id.decode("utf-8") if isinstance(message_id, bytes) else str(message_id)
        entry, undecodable = self._decode_fields_checked(fields)
        if undecodable:
            # Poison by construction: redelivery can never decode it. Raw bytes are preserved as
            # base64 in the DLQ payload; the DLQ write + ACK happen here, so it is never reclaimed.
            await self._dead_letter(client, message_id, {**entry, "undecodable_fields": ",".join(undecodable)},
                                    "undecodable-queue-field")
            return
        try:
            task_payload = json.loads(entry.get("payload", ""))
            if not isinstance(task_payload, dict):
                raise ValueError("task payload must be a JSON object")
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            await self._dead_letter(client, message_id, entry, "malformed-task-payload")
            return

        job_id = task_payload.get("job_id")
        minio_uri = task_payload.get("minio_uri")
        if not isinstance(job_id, str) or not job_id or not isinstance(minio_uri, str) or not minio_uri:
            await self._dead_letter(client, message_id, entry, "missing-job-id-or-object-uri")
            return
        uploader = task_payload.get("uploader_fingerprint")
        if not isinstance(uploader, str) or not _SHA256_HEX.match(uploader):
            # Includes envelopes queued before identity propagation: never fabricate an identity.
            await self._dead_letter(client, message_id, entry, INVALID_UPLOADER_REASON)
            return
        lease_task = asyncio.create_task(self._refresh_claim_loop(client, message_id))
        try:
            try:
                object_name = self._object_name(minio_uri)
            except ValueError:
                await self._dead_letter(client, message_id, entry, "invalid-object-uri")
                return
            file_data = await asyncio.to_thread(self._download_object, object_name)
            if not file_data:
                await self._dead_letter(client, message_id, entry, "empty-evtx-object")
                return
            if len(file_data) > MAX_EVTX_FILE_BYTES:
                await self._dead_letter(client, message_id, entry, "evtx-file-size-limit-exceeded")
                logger.warning("EVTX job rejected by byte limit: job_id=%s limit=%d",
                               job_id, MAX_EVTX_FILE_BYTES)
                return
            records = await asyncio.to_thread(
                lambda: list(islice(parse_evtx_records(file_data), MAX_EVTX_RECORDS_PER_FILE + 1))
            )
            if len(records) > MAX_EVTX_RECORDS_PER_FILE:
                await self._dead_letter(client, message_id, entry, "evtx-record-limit-exceeded")
                logger.warning("EVTX job rejected by record limit: job_id=%s limit=%d",
                               job_id, MAX_EVTX_RECORDS_PER_FILE)
                return
            rejected = []
            for index, record in enumerate(records):
                source_event_key = self._source_event_key(job_id, index, uploader, record)
                reason = record.get("parse_error")
                if reason is None:
                    try:
                        payload = AgentWinlogRequest.model_validate(record)
                    except ValidationError as exc:
                        reason = "invalid-record:" + ".".join(map(str, exc.errors()[0]["loc"]))
                if reason is not None:
                    rejected.append((index, source_event_key, reason, record))
                    continue
                await self.broker.publish_winlog(
                    payload=payload, cert_fingerprint=uploader, source_event_key=source_event_key)
            # Record-level DLQ writes happen only after every valid record is published, and the
            # job is ACKed only after both; a crash in between replays (publishes dedupe by key).
            for index, source_event_key, reason, record in rejected:
                await client.xadd(EVTX_DEAD_LETTER_STREAM_KEY, fields={
                    "source_stream_id": message_id, "reason": reason[:160], "job_id": job_id,
                    "record_index": str(index), "source_event_key": source_event_key,
                    "payload": json.dumps(record, ensure_ascii=False, default=str),
                    "failed_at": datetime.now(UTC).isoformat()})
            await self._ack_job(client, message_id)
            logger.info("EVTX job completed: job_id=%s records=%d rejected=%d",
                        job_id, len(records) - len(rejected), len(rejected))
        except Exception as exc:
            attempts = await self._delivery_count(client, message_id)
            if attempts >= self.max_delivery_attempts:
                await self._dead_letter(client, message_id, entry, f"retry-limit:{type(exc).__name__}")
                logger.error("EVTX job moved to DLQ after %d attempts: job_id=%s", attempts, job_id)
                return
            logger.error("EVTX job retryable failure: job_id=%s attempt=%d error=%s",
                         job_id, attempts, type(exc).__name__)
            raise
        finally:
            lease_task.cancel()
            try:
                await lease_task
            except asyncio.CancelledError:
                pass


evtx_worker = EVTXBackgroundWorker()
