import json
import logging
from dataclasses import dataclass, asdict, field
from pathlib import Path

from app.constants import CONFIG_FILE

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    sticker_folder: str = "Sticker"
    processed_folder: str = "Sticker/Processed"
    failed_folder: str = "Sticker/Failed"
    log_folder: str = "Logs"
    ocr_language: str = "en"
    ocr_use_gpu: bool = False
    crop_enabled: bool = True
    crop_padding: int = 20
    notification_enabled: bool = True
    theme: str = "dark"
    large_display_font_size: int = 96
    large_display_hotkey: str = "F11"
    eims_api_url: str = "http://localhost:8000"
    eims_client_fingerprint: str = "test_agent_fingerprint_sha256"

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "AppConfig":
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
                return cls(**known)
            except Exception as exc:
                logger.warning("Failed to load config, using defaults: %s", exc)
        return cls()

    def save(self, path: Path = CONFIG_FILE) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
        except Exception as exc:
            logger.error("Failed to save config: %s", exc)

    @property
    def resolved_sticker_folder(self) -> Path:
        return Path(self.sticker_folder)

    @property
    def resolved_processed_folder(self) -> Path:
        return Path(self.processed_folder)

    @property
    def resolved_failed_folder(self) -> Path:
        return Path(self.failed_folder)

    @property
    def resolved_log_folder(self) -> Path:
        return Path(self.log_folder)
