from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class OCRResult:
    serial_number: Optional[str] = None
    device_id: Optional[str] = None
    raw_text: str = ""

    @property
    def is_complete(self) -> bool:
        return bool(self.serial_number and self.device_id)


@dataclass
class FolderResult:
    success: bool = False
    folder_path: Optional[Path] = None
    is_duplicate: bool = False
    error_message: Optional[str] = None
