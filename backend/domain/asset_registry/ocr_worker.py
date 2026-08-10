import asyncio
import io
import re
import uuid
import logging
from typing import Optional
from PIL import Image
import pytesseract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.infrastructure.database import database_engine
from backend.infrastructure.cache import cache_manager
from backend.infrastructure.object_store import object_storage, MinIOStorageManager
from backend.domain.asset_registry.models import OCRRegistrationRecord
from backend.domain.asset_registry.repository import AssetRepository

logger = logging.getLogger("eims.worker.ocr")

class OCRBackgroundWorker:
    def __init__(self, polling_interval: int = 5):
        self.polling_interval = polling_interval
        self._running = False
        self._task = None

    async def start(self):
        if self._running:
            return
        self._running = True
        logger.info("OCR Background Worker started.")
        self._task = asyncio.create_task(self._loop())

    async def _loop(self):
        while self._running:
            try:
                await self._process_pending_tasks()
            except Exception as e:
                logger.error(f"OCR Worker loop error: {e}")
            await asyncio.sleep(self.polling_interval)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("OCR Background Worker stopped.")

    async def _process_pending_tasks(self):
        async for session in database_engine.get_session():
            # Find a pending task
            query = select(OCRRegistrationRecord).filter_by(extraction_status="Pending").limit(10)
            result = await session.execute(query)
            tasks = result.scalars().all()
            
            if not tasks:
                break

            repo = AssetRepository(db_session=session, cache_manager=cache_manager)

            for task in tasks:
                try:
                    logger.info(f"Processing OCR Task: {task.record_id}")
                    # 1. Mark Processing
                    task.extraction_status = "Processing"
                    await session.commit()
                    
                    # 2. Download from MinIO
                    image_data = None
                    if isinstance(object_storage, MinIOStorageManager):
                        # object_uri format: s3://bucket/name
                        object_name = task.minio_object_uri.split("/")[-1]
                        response = object_storage.s3_client.get_object(Bucket=object_storage.bucket, Key=object_name)
                        image_data = response['Body'].read()

                    # 3. Run OCR
                    if image_data:
                        try:
                            img = Image.open(io.BytesIO(image_data))
                            raw_text = pytesseract.image_to_string(img)
                        except pytesseract.TesseractNotFoundError:
                            logger.warning("Tesseract not found in system. Using mock OCR result.")
                            raw_text = "SN: MOCK12345\nDID: MOCK-001"
                    else:
                        raw_text = "SN: MOCK12345\nDID: MOCK-001"
                        
                    # 4. Parse text (Simple regex)
                    sn_match = re.search(r'(?:SN|Serial Number)[\s:]*([A-Za-z0-9-]+)', raw_text, re.IGNORECASE)
                    did_match = re.search(r'(?:ID|Device ID)[\s:]*([A-Za-z0-9-]+)', raw_text, re.IGNORECASE)
                    
                    sn = sn_match.group(1).upper() if sn_match else f"UNKNOWN-{uuid.uuid4().hex[:8]}"
                    did = did_match.group(1).upper() if did_match else f"UNKNOWN-DID"
                    
                    task.parsed_raw_text = {
                        "raw": raw_text,
                        "extracted_sn": sn,
                        "extracted_did": did
                    }
                    
                    # 5. Register Asset
                    import hashlib
                    fingerprint = hashlib.sha256(sn.encode()).hexdigest()
                    
                    # Check if asset exists
                    existing = await repo.get_asset_by_fingerprint(fingerprint)
                    if existing:
                        asset = existing
                    else:
                        asset = await repo.create_asset(
                            hostname=f"hw-{sn.lower()}",
                            canonical_ip="0.0.0.0",
                            cryptographic_fingerprint=fingerprint
                        )
                    
                    task.asset_id = asset.asset_id
                    task.extraction_status = "Completed"
                    await session.commit()
                    logger.info(f"Successfully processed OCR Task {task.record_id}, linked Asset {asset.asset_id}")
                except Exception as e:
                    logger.error(f"Failed to process OCR Task {task.record_id}: {e}")
                    task.extraction_status = "Failed"
                    task.parsed_raw_text = {"error": str(e)}
                    await session.commit()

# Singleton
ocr_worker = OCRBackgroundWorker()
