import logging
import threading
from pathlib import Path
import requests

from app.config import AppConfig

logger = logging.getLogger(__name__)


class EIMSClient:
    """
    Background HTTP client to stream images to the EIMS OCR API.
    """
    def __init__(self, config: AppConfig):
        self._config = config

    def upload_image_async(self, image_path: Path, sn: str = None, did: str = None, error_message: str = None):
        """Spawns a daemon thread to upload the image without blocking the UI."""
        thread = threading.Thread(
            target=self._upload_image,
            args=(image_path, sn, did, error_message),
            daemon=True,
            name=f"EIMSUpload-{image_path.name}"
        )
        thread.start()

    def _upload_image(self, image_path: Path, sn: str = None, did: str = None, error_message: str = None):
        url = f"{self._config.eims_api_url.rstrip('/')}/api/v1/assets/ocr-upload"
        headers = {
            "x-client-cert-fingerprint": self._config.eims_client_fingerprint
        }
        data = {}
        if sn: data["serial_number"] = sn
        if did: data["device_id"] = did
        if error_message: data["error_message"] = error_message
        
        try:
            with open(image_path, "rb") as f:
                # determine content type based on extension
                ext = image_path.suffix.lower()
                mime = "image/png" if ext == ".png" else "image/jpeg"
                files = {"file": (image_path.name, f, mime)}
                
                logger.info("Uploading %s to EIMS at %s", image_path.name, url)
                response = requests.post(url, headers=headers, files=files, data=data, timeout=30.0)
                
            if response.status_code in (200, 201, 202):
                data = response.json()
                logger.info("Successfully uploaded %s to EIMS. Task ID: %s", image_path.name, data.get("task_id"))
            else:
                logger.error("Failed to upload %s to EIMS: %s %s", image_path.name, response.status_code, response.text)
        except Exception as e:
            logger.error("EIMS upload exception for %s: %s", image_path.name, e)

    def clear_ocr_history_async(self):
        """Spawns a daemon thread to clear OCR history on backend without blocking UI."""
        thread = threading.Thread(
            target=self._clear_ocr_history,
            daemon=True,
            name="EIMSClearHistory"
        )
        thread.start()

    def _clear_ocr_history(self):
        url = f"{self._config.eims_api_url.rstrip('/')}/api/v1/assets/ocr-history"
        headers = {
            "x-client-cert-fingerprint": self._config.eims_client_fingerprint
        }
        try:
            response = requests.delete(url, headers=headers, timeout=10.0)
            if response.status_code in (200, 204):
                logger.info("Successfully cleared EIMS OCR history.")
            else:
                logger.error("Failed to clear EIMS OCR history: %s %s", response.status_code, response.text)
        except Exception as e:
            logger.error("EIMS clear history exception: %s", e)
