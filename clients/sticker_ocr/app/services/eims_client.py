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

    def upload_image_async(self, image_path: Path):
        """Spawns a daemon thread to upload the image without blocking the UI."""
        thread = threading.Thread(
            target=self._upload_image,
            args=(image_path,),
            daemon=True,
            name=f"EIMSUpload-{image_path.name}"
        )
        thread.start()

    def _upload_image(self, image_path: Path):
        url = f"{self._config.eims_api_url.rstrip('/')}/api/v1/assets/ocr-upload"
        headers = {
            "x-client-cert-fingerprint": self._config.eims_client_fingerprint
        }
        
        try:
            with open(image_path, "rb") as f:
                # determine content type based on extension
                ext = image_path.suffix.lower()
                mime = "image/png" if ext == ".png" else "image/jpeg"
                files = {"file": (image_path.name, f, mime)}
                
                logger.info("Uploading %s to EIMS at %s", image_path.name, url)
                response = requests.post(url, headers=headers, files=files, timeout=30.0)
                
            if response.status_code in (200, 201, 202):
                data = response.json()
                logger.info("Successfully uploaded %s to EIMS. Task ID: %s", image_path.name, data.get("task_id"))
            else:
                logger.error("Failed to upload %s to EIMS: %s %s", image_path.name, response.status_code, response.text)
        except Exception as e:
            logger.error("EIMS upload exception for %s: %s", image_path.name, e)
