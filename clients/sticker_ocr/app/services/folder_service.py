import logging
import shutil
import time
from pathlib import Path

from app.models.result import FolderResult

logger = logging.getLogger(__name__)



class FolderService:
    def create_job_folder(self, usb_root: Path, folder_name: str) -> FolderResult:
        """
        Create <usb_root>/<folder_name>/Picture/.
        Returns a FolderResult describing success, duplicate, or failure.
        """
        job_folder = usb_root / folder_name
        picture_folder = job_folder / "Picture"

        for attempt in range(3):
            try:
                # Check if drive root exists first
                if not usb_root.exists():
                    logger.warning("USB drive root not accessible (attempt %d/3)", attempt + 1)
                    time.sleep(1.0)
                    continue



                if job_folder.exists():
                    logger.info("Duplicate detected: %s", job_folder)
                    return FolderResult(success=False, folder_path=job_folder, is_duplicate=True)

                picture_folder.mkdir(parents=True, exist_ok=False)
                logger.info("Created: %s", picture_folder)
                return FolderResult(success=True, folder_path=job_folder)

            except OSError as exc:
                # WinError 21: The device is not ready (USB sleeping or unmounted)
                winerror = getattr(exc, "winerror", None)
                if winerror == 21 or "not ready" in str(exc).lower():
                    logger.warning("USB device not ready (attempt %d/3): %s", attempt + 1, exc)
                    time.sleep(1.0)
                    continue

                if isinstance(exc, PermissionError) or winerror == 5:
                    logger.error("Permission denied: %s — %s", job_folder, exc)
                    return FolderResult(success=False, error_message=f"Permission denied: {exc}")

                logger.error("OS error: %s — %s", job_folder, exc)
                return FolderResult(success=False, error_message=str(exc))

        return FolderResult(
            success=False,
            error_message="USB drive is not ready (WinError 21). Please check USB connection.",
        )
