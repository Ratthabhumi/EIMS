from pathlib import Path

APP_NAME = "Disk Sanitization Assistant"
APP_VERSION = "1.0.1"

CONFIG_FILE = Path("config.json")

SUPPORTED_IMAGE_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}
)


class Event:
    USB_INSERTED = "usb_inserted"
    USB_REMOVED = "usb_removed"
    USB_STATUS_CHANGED = "usb_status_changed"
    JOB_QUEUED = "job_queued"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    PREVIEW_READY = "preview_ready"
    QUEUE_UPDATED = "queue_updated"
    HISTORY_UPDATED = "history_updated"
    STATS_UPDATED = "stats_updated"
    CONFIG_CHANGED = "config_changed"
