import csv
import logging
import threading
from datetime import date, datetime
from pathlib import Path
from typing import List

from app.models.job import ProcessingJob, JobStatus

logger = logging.getLogger(__name__)

_FIELDS = ["Time", "SN", "ID", "Folder", "USB", "Status", "Error"]


class CSVLogger:
    def __init__(self, log_folder: Path) -> None:
        self._folder = log_folder
        self._lock = threading.Lock()

    def log_job(self, job: ProcessingJob) -> None:
        self._folder.mkdir(parents=True, exist_ok=True)
        log_file = self._folder / f"log_{date.today().strftime('%Y-%m-%d')}.csv"

        with self._lock:
            needs_header = not log_file.exists()
            try:
                with open(log_file, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=_FIELDS)
                    if needs_header:
                        writer.writeheader()
                    ts = job.processed_at or job.created_at
                    writer.writerow({
                        "Time": ts.strftime("%H:%M:%S"),
                        "SN": job.serial_number or "",
                        "ID": job.device_id or "",
                        "Folder": job.folder_name,
                        "USB": str(job.usb_path) if job.usb_path else "",
                        "Status": job.status.label(),
                        "Error": job.error_message or "",
                    })
            except OSError as exc:
                logger.error("CSV write failed: %s", exc)

    def load_today_history(self) -> List[ProcessingJob]:
        log_file = self._folder / f"log_{date.today().strftime('%Y-%m-%d')}.csv"
        jobs: List[ProcessingJob] = []
        if not log_file.exists():
            return jobs

        with self._lock:
            try:
                with open(log_file, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        sn = row.get("SN") or None
                        did = row.get("ID") or None
                        status_str = row.get("Status", "")
                        error = row.get("Error") or None
                        usb_str = row.get("USB") or ""
                        folder_name = row.get("Folder") or ""

                        status = JobStatus.SUCCESS
                        for s in JobStatus:
                            if s.label() == status_str:
                                status = s
                                break

                        img_path = Path(folder_name if folder_name else "Sticker Image")
                        job = ProcessingJob(
                            image_path=img_path,
                            status=status,
                            serial_number=sn,
                            device_id=did,
                            usb_path=Path(usb_str) if usb_str else None,
                            error_message=error,
                        )
                        try:
                            t_str = row.get("Time", "")
                            if t_str:
                                today = date.today()
                                pt = datetime.strptime(t_str, "%H:%M:%S").time()
                                job.processed_at = datetime.combine(today, pt)
                                job.created_at = job.processed_at
                        except Exception:
                            pass
                        jobs.insert(0, job)
            except Exception as exc:
                logger.error("Failed to load today's history from CSV: %s", exc)

        return jobs
