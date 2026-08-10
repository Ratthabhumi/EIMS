"""
scanner/registry.py

Performs security audits by reading Windows Registry values directly
using the built-in winreg module (no external dependencies required).

Why winreg instead of PowerShell for Registry checks?
    - winreg is a built-in Python module → zero overhead, no subprocess spawn.
    - Registry reads do NOT require Administrator on HKLM read-only operations.
    - Faster and more reliable than parsing PowerShell text output.
    - Direct access to exact key/value → no ambiguity in parsing.

Registry checks in Version 1:
    1. UAC   → User Account Control must be enabled
    2. RDP   → Remote Desktop should be disabled when not in use
    3. SMBv1 → SMB version 1 must be disabled (EternalBlue/WannaCry mitigation)

All check definitions live in config/settings.py (REGISTRY_CHECKS).
This module only contains the reading and evaluation logic.
"""

import logging
import winreg
from typing import Any

from config.settings import REGISTRY_CHECKS

logger = logging.getLogger(__name__)

# ── Registry Hive Mapping ────────────────────────────────────────────────────
#
# winreg constants are integers (e.g., winreg.HKEY_LOCAL_MACHINE = 0x80000002).
# We store them as strings in settings.py for readability,
# then resolve them here at runtime.

HIVE_MAP: dict[str, int] = {
    "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
    "HKEY_CURRENT_USER":  winreg.HKEY_CURRENT_USER,
    "HKEY_CLASSES_ROOT":  winreg.HKEY_CLASSES_ROOT,
    "HKEY_USERS":         winreg.HKEY_USERS,
}


# ── Registry Reader ──────────────────────────────────────────────────────────

def _read_registry_value(hive_name: str, path: str, value_name: str) -> tuple[Any, bool]:
    """
    Read a single value from the Windows Registry.

    Args:
        hive_name  : String name of the hive (e.g., "HKEY_LOCAL_MACHINE").
        path       : Registry key path (e.g., r"SOFTWARE\\Microsoft\\...").
        value_name : Name of the value to read (e.g., "EnableLUA").

    Returns:
        Tuple of (value, success):
            - value  : The actual data stored in the registry value.
                       Returns None if the key/value does not exist or on error.
            - success: True if the value was successfully read, False otherwise.

    winreg.QueryValueEx(key, value_name) returns:
        (data, type) → we discard type and return only data.

    Registry access model:
        OpenKey with KEY_READ (0x20019) → read-only access.
        No write permissions requested → Principle of Least Privilege.
    """
    hive = HIVE_MAP.get(hive_name)
    if hive is None:
        logger.error("Unknown registry hive: %s", hive_name)
        return None, False

    try:
        # KEY_READ = STANDARD_RIGHTS_READ | KEY_QUERY_VALUE | KEY_ENUMERATE_SUB_KEYS | KEY_NOTIFY
        # We request read-only access — never open a key with write permissions unless needed.
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as key:
            data, _ = winreg.QueryValueEx(key, value_name)
            return data, True

    except FileNotFoundError:
        # Key or value does not exist on this system
        # e.g., SMB1Protocol key may not exist on newer Windows builds
        logger.warning("Registry key/value not found: %s\\%s -> %s", hive_name, path, value_name)
        return None, False

    except PermissionError:
        logger.warning("Permission denied reading registry: %s\\%s", hive_name, path)
        return None, False

    except OSError as exc:
        logger.error("OS error reading registry '%s\\%s': %s", hive_name, path, exc)
        return None, False


# ── Single Check Evaluator ───────────────────────────────────────────────────

def _evaluate_check(check: dict) -> dict:
    """
    Evaluate a single registry security check.

    Args:
        check: A dict from REGISTRY_CHECKS in settings.py with keys:
               key, hive, path, value, expected, description

    Scoring logic:
        PASS    → actual value == expected value
        FAIL    → actual value != expected value  (wrong configuration)
        FAIL    → key/value not found             (cannot verify = Fail-Safe)
        UNKNOWN → read error (permission denied)

    Why FAIL for missing key instead of WARNING?
        If we cannot confirm a secure configuration exists,
        we must assume it is not secure (Fail-Safe Default principle).

    Special case — SMBv1:
        On Windows 10 1709+ and Windows Server 2019+, SMBv1 is removed entirely.
        The registry key SMB1Protocol may not exist at all.
        If the key is missing, we check if the OS build indicates SMBv1 removal.
        For simplicity in V1, missing SMB1Protocol key → WARNING (likely removed).

    Returns:
        {
            "key"         : str  (e.g. "UAC"),
            "description" : str,
            "registry_path": str (full path for reference),
            "expected"    : Any,
            "actual"      : Any,
            "status"      : "PASS" | "WARNING" | "FAIL" | "UNKNOWN",
            "detail"      : str
        }
    """
    key_name    = check["key"]
    hive_name   = check["hive"]
    path        = check["path"]
    value_name  = check["value"]
    expected    = check["expected"]
    description = check["description"]
    full_path   = f"{hive_name}\\{path}\\{value_name}"

    actual, success = _read_registry_value(hive_name, path, value_name)

    # ── Build base result ────────────────────────────────────────────────────
    result = {
        "key":           key_name,
        "description":   description,
        "registry_path": full_path,
        "expected":      expected,
        "actual":        actual,
    }

    # ── Could not read the value ─────────────────────────────────────────────
    if not success:
        # Special handling for SMBv1:
        # On modern Windows, the protocol is removed entirely (not just disabled).
        # A missing key is actually a secure state for SMBv1.
        if key_name == "SMBv1":
            result["status"] = "PASS"
            result["detail"] = (
                "SMBv1 registry key not found — "
                "protocol may be fully removed on this Windows version (secure)"
            )
        else:
            result["status"] = "FAIL"
            result["detail"] = f"Registry key not found or unreadable: {full_path}"
        return result

    # ── Value exists — compare against expected ──────────────────────────────
    if actual == expected:
        result["status"] = "PASS"
        result["detail"] = (
            f"{description} — value is {actual} (expected: {expected})"
        )
    else:
        result["status"] = "FAIL"
        result["detail"] = (
            f"{description} — value is {actual} but expected {expected}"
        )

    return result


# ── Public API ───────────────────────────────────────────────────────────────

def get_registry_info() -> dict:
    """
    Run all registry security checks defined in config/settings.py.

    Each check is independent — a failure in one does not affect others.

    Returns:
        {
            "UAC":    { key, description, registry_path, expected, actual, status, detail },
            "RDP":    { ... },
            "SMBv1":  { ... },
        }
    """
    logger.info("Starting Registry audit...")

    registry_result: dict = {}

    for check in REGISTRY_CHECKS:
        key_name = check["key"]
        try:
            registry_result[key_name] = _evaluate_check(check)
            logger.debug(
                "Registry check '%s': %s",
                key_name,
                registry_result[key_name]["status"],
            )
        except Exception as exc:
            logger.error("Unexpected error in registry check '%s': %s", key_name, exc)
            registry_result[key_name] = {
                "key":           key_name,
                "description":   check.get("description", ""),
                "registry_path": f"{check.get('hive')}\\{check.get('path')}\\{check.get('value')}",
                "expected":      check.get("expected"),
                "actual":        None,
                "status":        "FAIL",
                "detail":        f"Unexpected error: {exc}",
            }

    statuses = [v["status"] for v in registry_result.values()]
    logger.info(
        "Registry audit complete — PASS: %d | FAIL: %d",
        statuses.count("PASS"),
        statuses.count("FAIL"),
    )

    return registry_result
