"""
==============================================================================
EIMS EVTX Background Parsing Worker
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5
==============================================================================
"""

import asyncio
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
            except Exception as e:
                logger.error(f"EVTX Worker loop error: {e}")
            await asyncio.sleep(self.polling_interval)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("EVTX Background Worker stopped.")

    async def _process_pending_tasks(self):
        # Pop job from Redis list
        task_data = await cache_manager.redis.rpop("eims:jobs:evtx")
        if not task_data:
            return

        minio_uri = task_data.decode("utf-8") if isinstance(task_data, bytes) else task_data
        logger.info(f"Processing EVTX Task: {minio_uri}")
        
        try:
            file_data = None
            if isinstance(object_storage, MinIOStorageManager):
                object_name = minio_uri.split("/")[-1]
                response = object_storage.s3_client.get_object(Bucket="eims-evtx-uploads", Key=object_name)
                file_data = response['Body'].read()

            if file_data:
                # Parse records and push directly to Telemetry Broker
                records = parse_evtx_records(file_data)
                count = 0
                for record in records:
                    payload = AgentWinlogRequest(**record)
                    # Emulate agent fingerprint for uploaded files
                    await self.broker.publish_winlog(payload=payload, cert_fingerprint="eims-evtx-upload-system")
                    count += 1
                logger.info(f"Successfully processed EVTX {minio_uri}, enqueued {count} winlog events.")
            else:
                logger.error(f"Failed to read EVTX file from MinIO: {minio_uri}")
        except Exception as e:
            logger.error(f"Failed to process EVTX Task {minio_uri}: {e}")

# Singleton worker instance
evtx_worker = EVTXBackgroundWorker()
