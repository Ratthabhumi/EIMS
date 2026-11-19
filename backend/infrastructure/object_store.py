"""
==============================================================================
EIMS S3 Object Storage Gateway (Core Law 4 Section 6.2)
==============================================================================
"""

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi.concurrency import run_in_threadpool

from backend.core.config import settings
from backend.core.exceptions import EIMSProblemException

logger = logging.getLogger("eims.infrastructure.object_store")

_PING_AWAIT_TIMEOUT = 3.0  # bounded to the dashboard's 5s health-fetch budget


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
    _ping_executor: ThreadPoolExecutor | None = None
    _ping_inflight: tuple | None = None

    def __init__(self):
        self.bucket = settings.MINIO_BUCKET_NAME
        scheme = "https" if settings.MINIO_SECURE else "http"
        endpoint = f"{scheme}://{settings.MINIO_ENDPOINT}"
        self._endpoint = endpoint
        self._health_client = None  # lazily built; separate from upload/download client
        self._ping_executor: ThreadPoolExecutor | None = None  # dedicated, max_workers=1
        self._ping_inflight: tuple | None = None  # (future, timing, submit_ts)

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

    def _build_health_client(self):
        """Dedicated read-only probe client with bounded 2s connect/read, no retries."""
        return boto3.client(
            "s3",
            endpoint_url=self._endpoint,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name="us-east-1",
            config=Config(
                connect_timeout=2,
                read_timeout=2,
                retries={"total_max_attempts": 1},
            ),
        )

    def _sync_ping(self, timing: dict | None = None) -> bool:
        """Strictly read-only: head_bucket only; never creates the bucket.

        ``timing`` (optional) receives monotonic timestamps ``worker_start``,
        ``head_start`` and ``head_end`` for measurement-only diagnostics.
        """
        if timing is not None:
            timing["worker_start"] = time.monotonic()
        try:
            if self._health_client is None:
                if timing is not None:
                    timing["client_start"] = time.monotonic()
                self._health_client = self._build_health_client()
                if timing is not None:
                    timing["client_end"] = time.monotonic()
            if timing is not None:
                timing["head_start"] = time.monotonic()
            try:
                self._health_client.head_bucket(Bucket=self.bucket)
            finally:
                if timing is not None:
                    timing["head_end"] = time.monotonic()
            return True
        except Exception as e:
            logger.error("MinIO Ping Failed: phase=head_bucket error_class=%s", type(e).__name__)
            return False

    @staticmethod
    def _ms(a: float | None, b: float | None) -> str:
        return "na" if a is None or b is None else f"{(b - a) * 1000:.1f}"

    def _log_ping_timeout(self, timing: dict, submit: float, loop_lag: float | None,
                          timed_out_at: float, error_class: str) -> None:
        """Measurement-only. Emits durations/classes only: no endpoint, bucket or credentials."""
        ws = timing.get("worker_start")
        cs, ce = timing.get("client_start"), timing.get("client_end")
        hs, he = timing.get("head_start"), timing.get("head_end")
        queue_s = (ws - submit) if ws is not None else None
        client_s = (ce - cs) if cs is not None and ce is not None else None
        head_s = (he - hs) if hs is not None and he is not None else None

        if ws is None:
            suspect = "threadpool_queue"
        elif hs is None:
            suspect = "health_client_init"
        elif he is None:
            suspect = "minio_request"
        elif max((v for v in (queue_s, client_s, head_s) if v is not None), default=0.0) > _PING_AWAIT_TIMEOUT:
            # The worker completed, but one measured phase itself exceeded the outer
            # deadline. Do not mislabel a slow MinIO request as event-loop wakeup.
            phase_costs = {
                "threadpool_queue": queue_s or 0.0,
                "health_client_init": client_s or 0.0,
                "minio_request": head_s or 0.0,
            }
            suspect = max(phase_costs, key=phase_costs.get)
        elif he - submit > _PING_AWAIT_TIMEOUT:
            suspect = "probe_budget_exceeded"
        else:
            # The worker completed within budget; only the event-loop waiter resumed late.
            suspect = "event_loop_or_wakeup"

        logger.error(
            "MinIO Health Diagnostic Failure: phase=await error_class=%s suspect=%s "
            "submit_to_start_ms=%s client_build_ms=%s head_bucket_ms=%s "
            "submit_loop_lag_ms=%s total_ms=%s wait_overshoot_ms=%.1f",
            error_class, suspect,
            self._ms(submit, ws), self._ms(cs, ce), self._ms(hs, he),
            "na" if loop_lag is None else f"{loop_lag * 1000:.1f}",
            self._ms(submit, timed_out_at),
            max(0.0, (timed_out_at - submit - _PING_AWAIT_TIMEOUT) * 1000),
        )

    def _submit_ping(self) -> tuple:
        """Return the in-flight probe ``(future, timing, submit)``, starting one only if idle.

        Runs on the event loop thread only. The dedicated single-worker executor is
        independent of the AnyIO/default pools. A new probe is submitted only when the
        previous one has finished, so there is never more than one queued/running job and
        a timed-out (but still running) probe is never doubled up by a second worker.
        """
        inflight = self._ping_inflight
        if inflight is not None and not inflight[0].done():
            return inflight
        if self._ping_executor is None:
            self._ping_executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="minio-health"
            )
        timing: dict = {}
        submit = time.monotonic()
        future = self._ping_executor.submit(self._sync_ping, timing)
        self._ping_inflight = (future, timing, submit)
        return self._ping_inflight

    async def close(self) -> None:
        """Release the dedicated probe executor (app shutdown). Idempotent.

        Queued work is cancelled; a running probe is bounded by the 2s connect/read
        timeouts, so we wait for it (bounded) so the worker thread exits cleanly.
        """
        executor, self._ping_executor = self._ping_executor, None
        inflight, self._ping_inflight = self._ping_inflight, None
        if executor is None:
            return
        executor.shutdown(wait=False, cancel_futures=True)
        if inflight is not None and not inflight[0].done():
            try:
                await asyncio.wait_for(
                    asyncio.shield(asyncio.wrap_future(inflight[0])), timeout=_PING_AWAIT_TIMEOUT
                )
            except Exception:
                pass

    async def ping(self) -> bool:
        loop = asyncio.get_running_loop()
        call_start = time.monotonic()
        lag_box: list = []
        # Loop responsiveness at submission: how late the loop runs a call_soon callback.
        loop.call_soon(lambda: lag_box.append(time.monotonic() - call_start))
        timing: dict = {}
        submit = call_start
        future = None
        try:
            future, timing, submit = self._submit_ping()
            # shield: cancelling/timing out this waiter must not cancel the shared probe.
            try:
                return await asyncio.wait_for(
                    asyncio.shield(asyncio.wrap_future(future)), timeout=_PING_AWAIT_TIMEOUT
                )
            except asyncio.TimeoutError:
                # If the event loop was busy, wait_for may run its timeout callback late
                # even though the worker completed within the original deadline. Check
                # the concurrent future and its worker timestamp before declaring 503.
                completed_at = timing.get("head_end")
                if (future.done() and completed_at is not None
                        and completed_at - submit <= _PING_AWAIT_TIMEOUT):
                    result = future.result()
                    logger.warning(
                        "MinIO Health Probe Completed Within Deadline; event loop resumed late "
                        "head_bucket_ms=%s total_ms=%s wait_overshoot_ms=%.1f",
                        self._ms(timing.get("head_start"), completed_at),
                        self._ms(submit, time.monotonic()),
                        max(0.0, (time.monotonic() - submit - _PING_AWAIT_TIMEOUT) * 1000),
                    )
                    return result
                raise
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._log_ping_timeout(timing, submit, lag_box[0] if lag_box else None,
                                   time.monotonic(), type(e).__name__)
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
