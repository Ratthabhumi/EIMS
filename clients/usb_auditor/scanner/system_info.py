"""
scanner/system_info.py

Collects hardware and operating system metadata from the current machine.
This module has no internal dependencies — it runs first in the audit pipeline.

Libraries used:
    platform  → OS name, version, build number, architecture (built-in)
    socket    → Hostname, primary IP address (built-in)
    uuid      → MAC address from network interface (built-in)
    psutil    → CPU label, total RAM, total disk size (third-party, no Admin needed)
    getpass   → Current logged-in username (built-in, safer than os.environ)
"""

import logging
import platform
import socket
import uuid
import getpass
from datetime import datetime, timezone

import psutil

logger = logging.getLogger(__name__)


def get_system_info() -> dict:
    """
    Collect hardware and OS metadata from the current Windows machine.

    Returns:
        dict: System information with the following keys:
            - computer_name  : NetBIOS / hostname
            - username       : Currently logged-in user
            - windows_edition: e.g. "Windows 10 Pro"
            - windows_version: e.g. "10.0.19045"
            - build_number   : e.g. "19045"
            - architecture   : e.g. "64bit"
            - cpu            : Processor brand string
            - ram_gb         : Total RAM in GB (rounded to 1 decimal)
            - disk_gb        : Total primary disk in GB (rounded to 1 decimal)
            - ip_address     : Primary IPv4 address
            - mac_address    : MAC address of primary adapter (XX:XX:XX:XX:XX:XX)
            - scan_timestamp : UTC ISO-8601 timestamp of when the scan ran
    """
    logger.info("Collecting system information...")

    info: dict = {}

    # ── Computer Name & Username ─────────────────────────────────────────────
    # socket.gethostname() → returns the machine's NetBIOS name
    # getpass.getuser()    → returns the OS-level username (not spoofable via env var)
    info["computer_name"] = socket.gethostname()
    info["username"] = getpass.getuser()

    # ── Windows OS Details ───────────────────────────────────────────────────
    # platform.system()      → "Windows"
    # platform.version()     → full version string e.g. "10.0.19045"
    # platform.win32_edition()→ edition e.g. "Pro", "Home", "Enterprise"
    # platform.machine()     → processor architecture e.g. "AMD64"
    try:
        edition = platform.win32_edition()                    # "Pro" / "Home" / "Enterprise"
        windows_name = f"Windows {platform.win32_ver()[0]}"  # "Windows 10" or "Windows 11"
        info["windows_edition"] = f"{windows_name} {edition}"
        info["windows_version"] = platform.version()         # "10.0.19045"
        info["build_number"] = platform.version().split(".")[-1]  # "19045"
        info["architecture"] = platform.machine()            # "AMD64"
    except Exception as exc:
        logger.warning("Could not read OS details: %s", exc)
        info["windows_edition"] = "Unknown"
        info["windows_version"] = "Unknown"
        info["build_number"] = "Unknown"
        info["architecture"] = "Unknown"

    # ── CPU ─────────────────────────────────────────────────────────────────
    # psutil.cpu_freq() → current/min/max frequency
    # platform.processor() → brand string e.g. "Intel64 Family 6..."
    # We prefer platform.processor() for human-readable CPU name.
    try:
        cpu_brand = platform.processor()
        info["cpu"] = cpu_brand if cpu_brand else "Unknown"
    except Exception as exc:
        logger.warning("Could not read CPU info: %s", exc)
        info["cpu"] = "Unknown"

    # ── RAM ─────────────────────────────────────────────────────────────────
    # psutil.virtual_memory().total → total RAM in bytes
    # Divide by 1024^3 to convert to GB
    try:
        ram_bytes = psutil.virtual_memory().total
        info["ram_gb"] = round(ram_bytes / (1024 ** 3), 1)
    except Exception as exc:
        logger.warning("Could not read RAM info: %s", exc)
        info["ram_gb"] = 0.0

    # ── Disk ─────────────────────────────────────────────────────────────────
    # psutil.disk_usage("C:\\").total → total bytes on C: drive
    # We always check C: because it is the system drive on Windows.
    # Note: This is total size, not free space.
    try:
        disk_bytes = psutil.disk_usage("C:\\").total
        info["disk_gb"] = round(disk_bytes / (1024 ** 3), 1)
    except Exception as exc:
        logger.warning("Could not read Disk info: %s", exc)
        info["disk_gb"] = 0.0

    # Enumerate local interfaces rather than sending hostname/DNS queries.
    info['network_adapters'] = []
    info['ip_address'] = 'Unknown'
    try:
        for name, addresses in list(psutil.net_if_addrs().items())[:100]:
            rows = [{'family': str(a.family), 'address': a.address, 'netmask': a.netmask}
                    for a in addresses[:20]]
            info['network_adapters'].append({'name': name, 'addresses': rows})
            for addr in addresses:
                if addr.family == socket.AF_INET and not addr.address.startswith('127.') and info['ip_address'] == 'Unknown':
                    info['ip_address'] = addr.address
    except Exception:
        logger.warning('Local network inventory unavailable')

    # ── MAC Address ──────────────────────────────────────────────────────────
    # uuid.getnode() → returns MAC as a 48-bit integer
    # We format it as XX:XX:XX:XX:XX:XX using format string trickery:
    #   %012X → 12 hex digits, zero-padded
    #   [i:i+2] slices → pairs every 2 chars → join with ":"
    try:
        mac_int = uuid.getnode()
        mac_hex = "%012X" % mac_int
        info["mac_address"] = ":".join(mac_hex[i:i+2] for i in range(0, 12, 2))
    except Exception as exc:
        logger.warning("Could not read MAC address: %s", exc)
        info["mac_address"] = "Unknown"

    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\BIOS', 0, winreg.KEY_READ) as key:
            info['manufacturer'] = winreg.QueryValueEx(key, 'SystemManufacturer')[0]
            info['model'] = winreg.QueryValueEx(key, 'SystemProductName')[0]
    except (OSError, ImportError):
        info['manufacturer'], info['model'] = 'Unknown', 'Unknown'
    try:
        import os
        info['disk_free_gb'] = round(psutil.disk_usage(os.environ.get('SystemDrive', 'C:') + '/').free / (1024 ** 3), 1)
    except Exception:
        info['disk_free_gb'] = None
    info['collection_limitations'] = [name + ' unavailable' for name in ('cpu', 'ram_gb', 'disk_gb', 'manufacturer', 'model')
                                      if info.get(name) in (None, '', 'Unknown', 0)]
    info["scan_timestamp"] = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    logger.info("System information collected: %s", info["computer_name"])
    return info
