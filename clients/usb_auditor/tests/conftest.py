"""Pytest bootstrap: make the usb_auditor package importable."""

import sys
from pathlib import Path

USB_AUDITOR_ROOT = Path(__file__).resolve().parent.parent
if str(USB_AUDITOR_ROOT) not in sys.path:
    sys.path.insert(0, str(USB_AUDITOR_ROOT))