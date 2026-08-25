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
        
    @abstractmethod
    async def ping(self) -> bool:
        """Verifies connectivity to the object storage service."""
        pass
        
    @abstractmethod
    async def download_file(self, uri: str) -> dict:
        """Downloads file and returns a dictionary with 'body' and 'content_type'."""
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

    def _ensure_bucket_exists(self):
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404" or error_code == "NoSuchBucket":
                self.s3_client.create_bucket(Bucket=self.bucket)
                logger.info(f"Auto-created missing MinIO bucket: {self.bucket}")
            else:
                raise

    def _sync_ping(self) -> bool:
        try:
            self._ensure_bucket_exists()
            return True
        except Exception as e:
            logger.error(f"MinIO Ping Failed: {str(e)}")
            return False

    async def ping(self) -> bool:
        import asyncio
        try:
            return await asyncio.wait_for(run_in_threadpool(self._sync_ping), timeout=2.0)
        except Exception as e:
            logger.error(f"MinIO Health Diagnostic Failure: {e}")
            return False

    def _sync_download(self, object_name: str) -> dict:
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=object_name)
            return {
                "body": response["Body"].read(),
                "content_type": response["ContentType"]
            }
        except Exception as e:
            logger.error(f"Failed to download object {object_name}: {str(e)}")
            raise StorageUploadException(detail="Failed to fetch object from MinIO")

    async def download_file(self, uri: str) -> dict:
        object_name = uri.split("/")[-1]
        return await run_in_threadpool(self._sync_download, object_name)


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
        
    async def ping(self) -> bool:
        return True
        
    async def download_file(self, uri: str) -> dict:
        data = self.storage.get(uri)
        if not data:
            raise Exception("File not found")
        return {"body": b"stub_data", "content_type": data["content_type"]}

# Global singleton
object_storage = MinIOStorageManager()
