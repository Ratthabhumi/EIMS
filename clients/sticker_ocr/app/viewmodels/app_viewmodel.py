import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2

from app.config import AppConfig
from app.constants import Event
from app.models.job import ProcessingJob, JobStatus
from app.models.result import OCRResult
from app.services.crop_service import crop_sticker
from app.services.eims_client import EIMSClient
from app.services.folder_service import FolderService
from app.services.logger_service import CSVLogger
from app.services.notifier import NotificationService
from app.services.ocr_engine import run_ocr
from app.services.queue_service import JobQueue
from app.services.usb_monitor import USBMonitor
from app.services.validator import validate_serial_number, validate_device_id, build_folder_name
from app.services.watch_service import WatchService

logger = logging.getLogger(__name__)


class AppViewModel:
    """
    Central ViewModel.  Owns all services, drives the processing pipeline,
    and exposes an observable interface to the View layer.

    Threading contract:
    - All public properties are safe to read from any thread.
    - notify() dispatches callbacks synchronously on the calling thread.
    - Views MUST wrap subscribed callbacks with widget.after(0, ...) before
      touching any CTk widget to ensure they run on the main thread.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._listeners: Dict[str, List[Callable]] = {}

        self._usb_path: Optional[Path] = None
        self._manual_usb_path: Optional[Path] = None
        self._history: List[ProcessingJob] = []
        self._stats: Dict[str, int] = {"success": 0, "duplicate": 0, "failed": 0}

        # Worker ↔ main-thread synchronisation for the preview dialog
        self._preview_event = threading.Event()
        self._preview_result: Optional[Tuple[str, str]] = None

        self._folder_svc = FolderService()
        self._csv_logger = CSVLogger(config.resolved_log_folder)
        self._notifier = NotificationService(config.notification_enabled)
        self._eims_client = EIMSClient(config)

        self._usb_monitor = USBMonitor(
            on_inserted=self._on_usb_inserted,
            on_removed=self._on_usb_removed,
        )
        self._job_queue = JobQueue(processor=self._process_job)
        self._watch_svc = WatchService(
            watch_folder=config.resolved_sticker_folder,
            callback=self._on_image_detected,
        )

        self._ensure_dirs()

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        # Restore today's history and statistics from daily log
        try:
            loaded_history = self._csv_logger.load_today_history()
            if loaded_history:
                self._history = loaded_history[:200]
                self._stats = {"success": 0, "duplicate": 0, "failed": 0}
                for job in self._history:
                    if job.status == JobStatus.SUCCESS:
                        self._stats["success"] += 1
                    elif job.status == JobStatus.DUPLICATE:
                        self._stats["duplicate"] += 1
                    else:
                        self._stats["failed"] += 1
                logger.info("Restored %d history jobs from today's log", len(self._history))
                self.notify(Event.HISTORY_UPDATED, list(self._history))
                self.notify(Event.STATS_UPDATED, dict(self._stats))
        except Exception:
            logger.exception("Failed to load today's history during startup")

        self._usb_monitor.start()
        self._job_queue.start()
        self._watch_svc.start()

        usb = self._usb_monitor.get_current()
        if usb:
            self._usb_path = usb
            self.notify(Event.USB_STATUS_CHANGED, usb)

        for img in self._watch_svc.scan_existing():
            self._on_image_detected(img)

    def stop(self) -> None:
        self._watch_svc.stop()
        self._job_queue.stop()
        self._usb_monitor.stop()

    # ------------------------------------------------------------------ #
    # Public interface for Views                                          #
    # ------------------------------------------------------------------ #

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def usb_path(self) -> Optional[Path]:
        if self._manual_usb_path and self._manual_usb_path.exists():
            return self._manual_usb_path
        return self._usb_path

    def set_manual_usb_drive(self, path: Optional[Path]) -> None:
        """Manually override the target USB drive."""
        self._manual_usb_path = path
        logger.info("Manual USB drive override: %s", path)
        self.notify(Event.USB_STATUS_CHANGED, self.usb_path)

    def get_available_usb_drives(self) -> list[Path]:
        """Return all detected external USB drives."""
        return self._usb_monitor.get_all_drives()

    @property
    def history(self) -> List[ProcessingJob]:
        return list(self._history)

    def clear_history(self) -> None:
        """Clear all in-memory job history."""
        self._history.clear()
        self.notify(Event.HISTORY_UPDATED, list(self._history))

    @property
    def stats(self) -> Dict[str, int]:
        return dict(self._stats)

    @property
    def pending_count(self) -> int:
        return self._job_queue.pending_count()

    @property
    def current_job(self) -> Optional[ProcessingJob]:
        return self._job_queue.current_job()

    def subscribe(self, event: str, callback: Callable[[Any], None]) -> None:
        self._listeners.setdefault(event, []).append(callback)

    def notify(self, event: str, data: Any = None) -> None:
        for cb in self._listeners.get(event, []):
            try:
                cb(data)
            except Exception:
                logger.exception("Listener error for event '%s'", event)

    def submit_preview(self, sn: str, device_id: str) -> None:
        """Called from the main thread when user confirms the preview dialog."""
        self._preview_result = (sn.strip().upper(), device_id.strip().upper())
        self._preview_event.set()

    def cancel_preview(self) -> None:
        """Called from the main thread when user skips a job."""
        self._preview_result = None
        self._preview_event.set()

    def update_config(self, new_config: AppConfig) -> None:
        self._config = new_config
        new_config.save()
        self._notifier.enabled = new_config.notification_enabled
        self.notify(Event.CONFIG_CHANGED, new_config)

    def retry_failed(self) -> None:
        failed = self._config.resolved_failed_folder.resolve()
        sticker_folder = self._config.resolved_sticker_folder.resolve()
        count = 0
        if failed.exists():
            for img in list(failed.iterdir()):
                if img.is_file() and not img.name.startswith("."):
                    dest = sticker_folder / img.name
                    self._watch_svc.forget(dest)
                    self._watch_svc.forget(img)
                    try:
                        shutil.move(str(img), str(dest))
                        count += 1
                        logger.info("Moved failed image for retry: %s -> %s", img.name, dest)
                    except Exception as exc:
                        logger.error("Failed to move image for retry: %s", exc)
        logger.info("Retrying %d failed image(s)", count)
        if count > 0:
            self._stats["failed"] = max(0, self._stats["failed"] - count)
            self.notify(Event.STATS_UPDATED, self._stats)

    # ------------------------------------------------------------------ #
    # USB callbacks (called from USBMonitor daemon thread)                #
    # ------------------------------------------------------------------ #

    def _on_usb_inserted(self, path: Path) -> None:
        self._usb_path = path
        self.notify(Event.USB_INSERTED, path)
        self.notify(Event.USB_STATUS_CHANGED, path)
        self._notifier.usb_inserted(str(path))

    def _on_usb_removed(self, path: Path) -> None:
        if self._usb_path == path:
            self._usb_path = None
        self.notify(Event.USB_REMOVED, path)
        self.notify(Event.USB_STATUS_CHANGED, None)
        self._notifier.usb_removed(str(path))

    # ------------------------------------------------------------------ #
    # Image detection callback (called from watchdog thread)              #
    # ------------------------------------------------------------------ #

    def _on_image_detected(self, image_path: Path) -> None:
        job = self._job_queue.enqueue(image_path)
        if job is not None:
            self.notify(Event.JOB_QUEUED, job)
            self.notify(Event.QUEUE_UPDATED, self._job_queue.pending_count())

    # ------------------------------------------------------------------ #
    # Processing pipeline (called from JobWorker thread)                  #
    # ------------------------------------------------------------------ #

    def _process_job(self, job: ProcessingJob) -> None:
        if not job.image_path.exists():
            logger.warning("Skipped job because image file no longer exists (already processed or removed): %s", job.image_path)
            self.notify(Event.QUEUE_UPDATED, self._job_queue.pending_count())
            return
        logger.info("Processing: %s", job.image_path.name)
        self.notify(Event.JOB_STARTED, job)

        # 1. Load & optionally crop the image
        image = self._load_image(job)
        if image is None:
            self._fail(job, JobStatus.ERROR, "Cannot read image file")
            return

        # 2. Run OCR
        ocr_result = run_ocr(image, self._config.ocr_language, self._config.ocr_use_gpu)
        logger.info("OCR: SN=%s  ID=%s", ocr_result.serial_number, ocr_result.device_id)

        # 3. Show preview dialog on main thread; block worker until user responds
        sn, did = self._await_preview(job, ocr_result)
        if sn is None:
            # User skipped
            self._fail(job, JobStatus.OCR_FAILED, "Skipped by user")
            return

        # 4. Validate
        if not validate_serial_number(sn) or not validate_device_id(did):
            self._fail(
                job, JobStatus.VALIDATION_FAILED,
                f"Invalid values: SN={sn!r}  ID={did!r}"
            )
            return

        job.serial_number = sn
        job.device_id = did

        # 5. Wait for USB if not present (up to 5 minutes)
        if not self._wait_for_usb(job):
            return

        job.usb_path = self._usb_path

        # 6. Create folder
        folder_name = build_folder_name(job.serial_number, job.device_id)
        result = self._folder_svc.create_job_folder(self._usb_path, folder_name)

        if result.is_duplicate:
            job.status = JobStatus.DUPLICATE
            job.processed_at = datetime.now()
            self._stats["duplicate"] += 1
            self._notifier.duplicate(folder_name)
        elif result.success:
            job.status = JobStatus.SUCCESS
            job.processed_at = datetime.now()
            self._stats["success"] += 1
            self._notifier.folder_created(folder_name)
        else:
            self._fail(job, JobStatus.ERROR, result.error_message or "Unknown error")
            return

        self._finalise(job)

    def _load_image(self, job: ProcessingJob):
        try:
            if self._config.crop_enabled:
                img = crop_sticker(job.image_path, self._config.crop_padding)
                if img is not None:
                    return img
            from app.services.crop_service import read_image_safe
            return read_image_safe(job.image_path)
        except Exception:
            logger.exception("Error loading image: %s", job.image_path)
            return None

    def _await_preview(
        self, job: ProcessingJob, ocr_result: OCRResult
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Signal the View to open the preview dialog, then block the worker
        thread until the user responds.
        """
        self._preview_event.clear()
        self._preview_result = None

        self.notify(Event.PREVIEW_READY, {"job": job, "ocr": ocr_result})
        self._preview_event.wait()

        if self._preview_result:
            return self._preview_result
        return None, None

    def _wait_for_usb(self, job: ProcessingJob, timeout: float = 300.0) -> bool:
        waited = 0.0
        step = 1.0
        while True:
            if self._usb_path is not None:
                try:
                    if self._usb_path.exists():
                        return True
                except Exception:
                    pass
            if waited == 0.0:
                logger.warning("USB not present or not ready — waiting (up to %.0fs)", timeout)
                self.notify(Event.USB_STATUS_CHANGED, None)
            self._preview_event.wait(timeout=step)  # reuse event object for sleep
            waited += step
            if waited >= timeout:
                self._fail(job, JobStatus.USB_MISSING, "USB not inserted within timeout")
                return False

    def _fail(self, job: ProcessingJob, status: JobStatus, message: str) -> None:
        job.status = status
        job.error_message = message
        job.processed_at = datetime.now()
        self._stats["failed"] += 1
        self._notifier.ocr_failed(job.image_path.name)
        self._finalise(job)

    def _finalise(self, job: ProcessingJob) -> None:
        self._csv_logger.log_job(job)
        self._move_image(job)
        
        if job.status in (JobStatus.SUCCESS, JobStatus.DUPLICATE):
            self._eims_client.upload_image_async(job.image_path)
            
        self._history.insert(0, job)
        if len(self._history) > 200:
            self._history.pop()
        self.notify(Event.JOB_COMPLETED, job)
        self.notify(Event.HISTORY_UPDATED, list(self._history))
        self.notify(Event.STATS_UPDATED, dict(self._stats))
        self.notify(Event.QUEUE_UPDATED, self._job_queue.pending_count())

    def _move_image(self, job: ProcessingJob) -> None:
        if job.status in (JobStatus.SUCCESS, JobStatus.DUPLICATE):
            dest_dir = self._config.resolved_processed_folder.resolve()
        else:
            dest_dir = self._config.resolved_failed_folder.resolve()

        dest_dir.mkdir(parents=True, exist_ok=True)
        src_path = job.image_path.resolve()

        if not src_path.exists():
            logger.warning("Source image missing before move: %s", src_path)
            return

        dest = dest_dir / src_path.name
        if dest.exists():
            stem, suffix = dest.stem, dest.suffix
            dest = dest_dir / f"{stem}_{datetime.now().strftime('%H%M%S')}{suffix}"

        # Retry moving in case file handle is held briefly by another process (LINE/OS)
        for attempt in range(5):
            try:
                self._watch_svc.forget(src_path)
                self._watch_svc.forget(dest)
                shutil.move(str(src_path), str(dest))
                job.image_path = dest
                logger.info("Moved %s → %s/", src_path.name, dest_dir.name)
                return
            except OSError as exc:
                if attempt == 4:
                    logger.error("Failed to move image after retries: %s — %s", src_path, exc)
                else:
                    threading.Event().wait(0.3)

    def _ensure_dirs(self) -> None:
        for folder in (
            self._config.resolved_sticker_folder,
            self._config.resolved_processed_folder,
            self._config.resolved_failed_folder,
            self._config.resolved_log_folder,
        ):
            folder.mkdir(parents=True, exist_ok=True)
