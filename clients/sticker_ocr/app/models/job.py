from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Optional


class JobStatus(Enum):
    PENDING = auto()
    PROCESSING = auto()
    SUCCESS = auto()
    DUPLICATE = auto()
    OCR_FAILED = auto()
    VALIDATION_FAILED = auto()
    USB_MISSING = auto()
    ERROR = auto()

    def label(self) -> str:
        return {
            JobStatus.PENDING: "Pending",
            JobStatus.PROCESSING: "Processing",
            JobStatus.SUCCESS: "Success",
            JobStatus.DUPLICATE: "Duplicate",
            JobStatus.OCR_FAILED: "OCR Failed",
            JobStatus.VALIDATION_FAILED: "Invalid Format",
            JobStatus.USB_MISSING: "USB Missing",
            JobStatus.ERROR: "Error",
        }[self]

    def color(self) -> str:
        return {
            JobStatus.PENDING: "#888888",
            JobStatus.PROCESSING: "#3b82f6",
            JobStatus.SUCCESS: "#22c55e",
            JobStatus.DUPLICATE: "#f59e0b",
            JobStatus.OCR_FAILED: "#ef4444",
            JobStatus.VALIDATION_FAILED: "#f97316",
            JobStatus.USB_MISSING: "#a855f7",
            JobStatus.ERROR: "#ef4444",
        }[self]


@dataclass
class ProcessingJob:
    image_path: Path
    status: JobStatus = JobStatus.PENDING
    serial_number: Optional[str] = None
    device_id: Optional[str] = None
    usb_path: Optional[Path] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None

    @property
    def folder_name(self) -> str:
        if self.serial_number and self.device_id:
            return f"{self.serial_number}({self.device_id})"
        return ""

    def is_terminal(self) -> bool:
        return self.status not in (JobStatus.PENDING, JobStatus.PROCESSING)
