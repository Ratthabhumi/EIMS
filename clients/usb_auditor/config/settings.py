"""
config/settings.py

Central configuration for Portable Windows Compliance Auditor.
All constants live here — no magic numbers scattered across modules.

Design Principle:
    Single Source of Truth → change once, applies everywhere.
    Supports easy extension in Version 2/3 without touching scanner logic.
"""

import sys
from pathlib import Path

# ─────────────────────────────────────────────
# Base Paths
# ─────────────────────────────────────────────

# If running as a compiled PyInstaller EXE, sys.frozen is True.
# sys.executable gives the path to the EXE on the USB drive.
# If running as raw script, resolve via __file__.
if getattr(sys, "frozen", False):
    BASE_DIR: Path = Path(sys.executable).resolve().parent
else:
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

REPORTS_DIR: Path = BASE_DIR / "reports"
LOGS_DIR: Path = BASE_DIR / "logs"

# Ensure directories exist at import time
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# Log File
# ─────────────────────────────────────────────

LOG_FILE: Path = LOGS_DIR / "auditor.log"   # fallback (used if called outside main)

# ─────────────────────────────────────────────
# Compliance Score Weights
# ─────────────────────────────────────────────
# Each status maps to a numeric score.
# FAIL defaults to 0 (Fail-Safe: unknown = insecure assumption).
# This can be tuned per check in future versions.

SCORE_MAP: dict[str, int] = {
    "PASS": 100,
    "WARNING": 50,
    "FAIL": 0,
    "UNKNOWN": 0,  # Treat unknown as FAIL — Fail-Safe Default
}

# Threshold for Compliant/Non-Compliant verdict (percentage)
COMPLIANCE_THRESHOLD: int = 80

# ─────────────────────────────────────────────
# Windows Services to Audit
# ─────────────────────────────────────────────
# Format: { "service_name": "Human-Readable Label" }
#
# WinDefend   → Windows Defender Antivirus
# BITS        → Background Intelligent Transfer Service (used by Windows Update)
# wuauserv    → Windows Update
# RemoteRegistry → Allows remote registry access (should ideally be Stopped/Disabled)
# W32Time     → Windows Time sync (important for log correlation in SIEM)

SERVICES_TO_AUDIT: dict[str, str] = {
    "WinDefend": "Windows Defender",
    "BITS": "Background Intelligent Transfer Service",
    "wuauserv": "Windows Update",
    "RemoteRegistry": "Remote Registry",
    "W32Time": "Windows Time",
}

# ─────────────────────────────────────────────
# Registry Checks
# ─────────────────────────────────────────────
# Format:
#   key   → short identifier
#   hive  → winreg constant name (string, resolved in registry.py)
#   path  → registry key path
#   value → registry value name
#   expected → value that means "secure"
#   description → why we check this

REGISTRY_CHECKS: list[dict] = [
    {
        "key": "UAC",
        "hive": "HKEY_LOCAL_MACHINE",
        # EnableLUA = 1 → UAC is ON
        # UAC prevents unauthorized privilege escalation.
        # CIS Benchmark: Windows 10/11 → EnableLUA must be 1
        "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System",
        "value": "EnableLUA",
        "expected": 1,
        "description": "User Account Control (UAC) must be enabled",
    },
    {
        "key": "RDP",
        "hive": "HKEY_LOCAL_MACHINE",
        # fDenyTSConnections = 1 → RDP is DISABLED (secure state)
        # RDP (port 3389) is a common attack vector for brute-force & ransomware.
        # If RDP is not required, it must be OFF.
        "path": r"SYSTEM\CurrentControlSet\Control\Terminal Server",
        "value": "fDenyTSConnections",
        "expected": 1,
        "description": "Remote Desktop (RDP) should be disabled when not in use",
    },
    {
        "key": "SMBv1",
        "hive": "HKEY_LOCAL_MACHINE",
        # SMB1Protocol = 0 → SMBv1 is DISABLED (secure state)
        # SMBv1 is the protocol exploited by EternalBlue/WannaCry ransomware.
        # Microsoft officially deprecated SMBv1. It must be disabled.
        "path": r"SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters",
        "value": "SMB1Protocol",
        "expected": 0,
        "description": "SMBv1 must be disabled (EternalBlue/WannaCry mitigation)",
    },
]
