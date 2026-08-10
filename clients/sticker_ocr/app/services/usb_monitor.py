import ctypes
import logging
import os
import threading
from pathlib import Path
from typing import Callable, Optional, Set

import psutil

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 1.0


def _is_usb_device(mountpoint: str) -> bool:
    """Return True if drive is a USB Flash Drive or connected via USB bus."""
    clean = mountpoint.rstrip("\\").upper()
    if not hasattr(ctypes, "windll"):
        return True

    try:
        dt = ctypes.windll.kernel32.GetDriveTypeW(clean + "\\")
        if dt == 2:  # DRIVE_REMOVABLE (USB Flash Drives / DiskDeleter USB)
            return True
        if dt != 3:  # Skip Network (4) and CD-ROM (5)
            return False

        # For DRIVE_FIXED (3), check if Storage Bus Type is USB (BusTypeUsb = 7)
        # to filter out internal hard drive partitions (D:\, E:\, etc.)
        from ctypes import wintypes

        handle = ctypes.windll.kernel32.CreateFileW(
            f"\\\\.\\{clean}",
            0,
            1 | 2,  # FILE_SHARE_READ | FILE_SHARE_WRITE
            None,
            3,  # OPEN_EXISTING
            0,
            None,
        )
        if handle in (-1, 0, 4294967295):
            return False

        try:
            query = (ctypes.c_byte * 12)(0)
            output = (ctypes.c_byte * 1024)(0)
            bytes_ret = wintypes.DWORD()
            res = ctypes.windll.kernel32.DeviceIoControl(
                handle,
                0x002D1400,  # IOCTL_STORAGE_QUERY_PROPERTY
                query,
                len(query),
                output,
                len(output),
                ctypes.byref(bytes_ret),
                None,
            )
            if res and bytes_ret.value >= 29:
                bus_type = output[28]
                return bus_type == 7  # 7 = BusTypeUsb
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception as exc:
        logger.debug("USB bus check failed for %s: %s", clean, exc)

    return False


class USBMonitor:
    def __init__(
        self,
        on_inserted: Callable[[Path], None],
        on_removed: Callable[[Path], None],
    ) -> None:
        self._on_inserted = on_inserted
        self._on_removed = on_removed
        self._known: Set[str] = set()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        self._known = self._removable_drives()
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="USBMonitor"
        )
        self._thread.start()
        logger.info("USB monitor started. Drives: %s", self._known)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def get_current(self) -> Optional[Path]:
        drives = self._removable_drives()
        if not drives:
            return None
        # Sort so DRIVE_REMOVABLE (Flash drives) come before external fixed HDDs
        sorted_drives = sorted(
            drives,
            key=lambda d: 0 if ctypes.windll.kernel32.GetDriveTypeW(d) == 2 else 1
        )
        return Path(sorted_drives[0])

    def get_all_drives(self) -> list[Path]:
        """Return list of all connected USB drives sorted by priority."""
        drives = sorted(
            list(self._removable_drives()),
            key=lambda d: 0 if ctypes.windll.kernel32.GetDriveTypeW(d) == 2 else 1
        )
        return [Path(d) for d in drives]

    def _loop(self) -> None:
        while not self._stop.is_set():
            current = self._removable_drives()

            for d in current - self._known:
                logger.info("USB inserted: %s", d)
                try:
                    self._on_inserted(Path(d))
                except Exception:
                    logger.exception("USB inserted callback error")

            for d in self._known - current:
                logger.info("USB removed: %s", d)
                try:
                    self._on_removed(Path(d))
                except Exception:
                    logger.exception("USB removed callback error")

            self._known = current
            self._stop.wait(timeout=_POLL_INTERVAL)

    @staticmethod
    def _removable_drives() -> Set[str]:
        result: Set[str] = set()
        system_drive = os.environ.get("SystemDrive", "C:").upper().rstrip("\\") + "\\"
        app_drive = Path(__file__).anchor.upper()

        try:
            for part in psutil.disk_partitions(all=False):
                mount = part.mountpoint.upper()

                # Skip system drive (C:\) and app drive
                if mount.startswith(system_drive) or mount.startswith(app_drive):
                    continue

                if _is_usb_device(part.mountpoint):
                    result.add(part.mountpoint)
        except Exception:
            logger.exception("Failed to enumerate disk partitions")
        return result
