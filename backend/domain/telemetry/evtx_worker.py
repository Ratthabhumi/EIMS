"""
==============================================================================
EIMS EVTX Background Parsing Worker
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5
==============================================================================
"""

import asyncio
import json
import logging

from backend.domain.telemetry.broker import RedisTelemetryStreamBroker
from backend.domain.telemetry.evtx_parser import parse_evtx_records
from backend.domain.telemetry.schemas import AgentWinlogRequest
from backend.infrastructure.cache import cache_manager
from backend.infrastructure.object_store import MinIOStorageManager, object_storage

logger = logging.getLogger("eims.worker.evtx")

class EVTXBackgroundWorker:
    def __init__(self, polling_interval: int = 5):
        self.polling_interval = polling_interval
        self._running = False
        self._task = None
        self.broker = RedisTelemetryStreamBroker(cache_manager=cache_manager)

    async def start(self):
        if self._running:
            return
        self._running = True
        logger.info("EVTX Background Worker started.")
        self._task = asyncio.create_task(self._loop())

    async def _loop(self):
        while self._running:
            try:
                await self._process_pending_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"EVTX Worker loop error: {e}")
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
        logger.info("EVTX Background Worker stopped.")

    async def _process_pending_tasks(self):
        # Pop job from Redis list
        task_data = await cache_manager.redis.rpop("eims:jobs:evtx")
        if not task_data:
            return

        try:
            task_payload = json.loads(task_data.decode("utf-8") if isinstance(task_data, bytes) else task_data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.error(f"EVTX Worker received malformed task payload: {task_data}")
            return

        minio_uri = task_payload.get("minio_uri")
        job_id = task_payload.get("job_id")
        if not minio_uri:
            logger.error(f"EVTX Task missing minio_uri: {task_payload}")
            return

        logger.info(f"Processing EVTX Task (job_id={job_id}): {minio_uri}")

        try:
            file_data = None
            if isinstance(object_storage, MinIOStorageManager):
                object_name = minio_uri.split("/")[-1]
                response = object_storage.s3_client.get_object(Bucket=object_storage.bucket, Key=object_name)
                file_data = response["Body"].read()

            if file_data:
                records = parse_evtx_records(file_data)
                count = 0
                for record in records:
                    payload = AgentWinlogRequest(**record)
                    await self.broker.publish_winlog(payload=payload, cert_fingerprint="eims-evtx-upload-system")
                    count += 1
                logger.info(f"Successfully processed EVTX {minio_uri}, enqueued {count} winlog events.")
            else:
                logger.error(f"Failed to read EVTX file from MinIO: {minio_uri}")
        except Exception as e:
            logger.error(f"Failed to process EVTX Task {minio_uri} (job_id={job_id}): {e}")

# Singleton worker instance
evtx_worker = EVTXBackgroundWorker()
