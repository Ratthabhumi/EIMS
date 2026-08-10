import logging
import threading

logger = logging.getLogger(__name__)


def _send(title: str, message: str) -> None:
    try:
        from winotify import Notification, audio

        toast = Notification(
            app_id="Disk Sanitization Assistant",
            title=title,
            msg=message,
            duration="short",
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
    except ImportError:
        logger.warning("winotify not installed — notification skipped")
    except Exception as exc:
        logger.warning("Notification failed: %s", exc)


class NotificationService:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def send(self, title: str, message: str) -> None:
        if not self.enabled:
            return
        threading.Thread(target=_send, args=(title, message), daemon=True).start()

    def folder_created(self, folder_name: str) -> None:
        self.send("✅ Folder Created", folder_name)

    def duplicate(self, folder_name: str) -> None:
        self.send("⚠️ Duplicate", f"{folder_name} already exists")

    def ocr_failed(self, filename: str) -> None:
        self.send("❌ OCR Failed", filename)

    def usb_inserted(self, drive: str) -> None:
        self.send("💾 USB Inserted", drive)

    def usb_removed(self, drive: str) -> None:
        self.send("📤 USB Removed", drive)
