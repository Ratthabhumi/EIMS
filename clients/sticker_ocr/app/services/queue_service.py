import logging
import os
import queue
import threading
from pathlib import Path
from typing import Callable, Optional

from app.models.job import ProcessingJob, JobStatus

logger = logging.getLogger(__name__)


class JobQueue:
    def __init__(self, processor: Callable[[ProcessingJob], None]) -> None:
        self._queue: queue.Queue[Optional[ProcessingJob]] = queue.Queue()
        self._processor = processor
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._current: Optional[ProcessingJob] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="JobWorker")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=10)

    def enqueue(self, image_path: Path) -> Optional[ProcessingJob]:
        norm_path = os.path.normcase(os.path.abspath(str(image_path)))
        with self._lock:
            if self._current and os.path.normcase(os.path.abspath(str(self._current.image_path))) == norm_path:
                logger.debug("Ignoring duplicate enqueue for image currently being processed: %s", image_path.name)
                return None
            for existing_job in list(self._queue.queue):
                if existing_job is not None and os.path.normcase(os.path.abspath(str(existing_job.image_path))) == norm_path:
                    logger.debug("Ignoring duplicate enqueue for image already in queue: %s", image_path.name)
                    return None
        job = ProcessingJob(image_path=image_path)
        self._queue.put(job)
        logger.info("Enqueued %s (pending: %d)", image_path.name, self._queue.qsize())
        return job

    def pending_count(self) -> int:
        return self._queue.qsize()

    def current_job(self) -> Optional[ProcessingJob]:
        with self._lock:
            return self._current

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if job is None:
                break

            with self._lock:
                self._current = job
            try:
                job.status = JobStatus.PROCESSING
                self._processor(job)
            except Exception:
                logger.exception("Unhandled error in job processor: %s", job.image_path)
                job.status = JobStatus.ERROR
            finally:
                with self._lock:
                    self._current = None
                self._queue.task_done()
