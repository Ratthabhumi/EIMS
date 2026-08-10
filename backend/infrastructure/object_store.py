"""
==============================================================================
EIMS S3 Object Storage Gateway (Core Law 4 Section 6.2)
==============================================================================
"""

import uuid
import logging
from typing import BinaryIO
from abc import ABC, abstractmethod

import boto3
from botocore.exceptions import ClientError
from fastapi.concurrency import run_in_threadpool

from backend.core.config import settings
from backend.core.exceptions import EIMSProblemException

logger = logging.getLogger("eims.infrastructure.object_store")


class StorageUploadException(EIMSProblemException):
    def __init__(self, detail: str):
        super().__init__(
            status=502,
            title="Object Storage Gateway Fault",
            detail=detail,
            type_uri="https://errors.eims.platform/v1/storage-gateway-fault"
        )


class AbstractObjectStorage(ABC):
    @abstractmethod
    async def upload_file(self, file_obj: BinaryIO, filename: str, content_type: str) -> str:
        """Asynchronously streams multipart binary to remote object storage."""
        pass


class MinIOStorageManager(AbstractObjectStorage):
    def __init__(self):
        self.bucket = settings.MINIO_BUCKET_NAME
        scheme = "https" if settings.MINIO_SECURE else "http"
        endpoint = f"{scheme}://{settings.MINIO_ENDPOINT}"
        
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name="us-east-1"
        )
        logger.info(f"Initialized MinIO S3 Object Storage Connector targeting bucket: {self.bucket}")

    def _sync_upload(self, file_obj: BinaryIO, object_name: str, content_type: str) -> str:
        try:
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket,
                object_name,
                ExtraArgs={"ContentType": content_type}
            )
            return f"s3://{self.bucket}/{object_name}"
        except ClientError as e:
            logger.error(f"S3 Upload Failed: {str(e)}")
            raise StorageUploadException(detail=f"Failed to stream payload to MinIO: {str(e)}")

    async def upload_file(self, file_obj: BinaryIO, filename: str, content_type: str) -> str:
        unique_name = f"{uuid.uuid4()}-{filename}"
        # Offload synchronous boto3 HTTP streams to threadpool to prevent blocking FastAPI asyncio event loop
        return await run_in_threadpool(self._sync_upload, file_obj, unique_name, content_type)


class StubObjectStorage(AbstractObjectStorage):
    """Hermetic storage manager for isolated offline testing."""
    def __init__(self):
        self.bucket = "stub-bucket"
        self.storage = {}

    async def upload_file(self, file_obj: BinaryIO, filename: str, content_type: str) -> str:
        unique_name = f"stub-{uuid.uuid4()}-{filename}"
        uri = f"s3://{self.bucket}/{unique_name}"
        file_obj.read()  # simulate reading the file
        self.storage[uri] = {"content_type": content_type, "size": 1024}
        return uri

# Global singleton
object_storage = MinIOStorageManager()
