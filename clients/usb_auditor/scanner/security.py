"""
scanner/security.py

Audits Windows security components using PowerShell commands via subprocess.

Why PowerShell instead of Registry?
    - Firewall: Registry shows policy settings; PowerShell reflects actual runtime state.
    - Defender: Get-MpComputerStatus is the official API with accurate real-time status.
    - BitLocker: No direct Registry key; only accessible via BitLocker WMI/PowerShell API.
    - Windows Update: Registry stores settings; PowerShell retrieves actual patch history.

Why subprocess over pywin32/WMI?
    - No additional dependencies beyond stdlib + psutil
    - Easier to read and test
    - Output is plain text → easy to parse

Security note on subprocess usage:
    - Always pass args as a LIST, never as a shell string → prevents shell injection.
    - Always set timeout → prevents hanging on unresponsive systems.
    - capture_output=True → stdout/stderr captured, not printed to terminal.
"""

import logging
import subprocess
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── Subprocess Helper ────────────────────────────────────────────────────────

def _run_powershell(command: str, timeout: int = 10) -> str:
    """
    Execute a PowerShell command and return its stdout as a stripped string.

    Args:
        command : PowerShell expression to run.
        timeout : Seconds before the process is killed (default: 10).

    Returns:
        Stdout string on success, empty string on failure.

    Design:
        - '-NonInteractive' prevents PS from waiting for user input.
        - '-NoProfile'      skips user profile loading → faster startup.
        - '-Command'        executes the expression directly.
        Using a list (not shell=True) prevents shell injection attacks.
    """
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning("PowerShell command timed out: %s", command)
        return ""
    except FileNotFoundError:
        # PowerShell not found on PATH — extremely unlikely on Windows but defensive
        logger.error("PowerShell executable not found.")
        return ""
    except Exception as exc:
        logger.error("Unexpected error running PowerShell: %s", exc)
        return ""


# ── Individual Security Checks ───────────────────────────────────────────────

def _check_firewall() -> dict:
    """
    Check Windows Firewall status across all three profiles:
    Domain, Private, and Public.

    A machine is considered PASS only if ALL profiles are enabled.
    If ANY profile is off → WARNING (partial protection).
    If PowerShell fails → FAIL (Fail-Safe Default).

    Returns:
        {
            "status"  : "PASS" | "WARNING" | "FAIL",
            "detail"  : human-readable description,
            "profiles": { "Domain": True/False, "Private": True/False, "Public": True/False }
        }
    """
    logger.info("Checking Windows Firewall...")

    # Get-NetFirewallProfile returns one line per profile in format:
    #   Domain     True
    #   Private    True
    #   Public     False
    ps_command = (
        "Get-NetFirewallProfile | "
        "Select-Object -Property Name,Enabled | "
        "Format-Table -HideTableHeaders | "
        "Out-String"
    )
    output = _run_powershell(ps_command)

    if not output:
        return {
            "status": "FAIL",
            "detail": "Could not retrieve Firewall status",
            "profiles": {},
        }

    profiles: dict[str, bool] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            profile_name = parts[0]   # e.g. "Domain"
            enabled_str = parts[1]    # "True" or "False"
            profiles[profile_name] = enabled_str.lower() == "true"

    if not profiles:
        return {
            "status": "FAIL",
            "detail": "Could not parse Firewall profile data",
            "profiles": {},
        }

    all_enabled = all(profiles.values())
    any_enabled = any(profiles.values())

    if all_enabled:
        status = "PASS"
        detail = "All firewall profiles are enabled"
    elif any_enabled:
        disabled = [k for k, v in profiles.items() if not v]
        status = "WARNING"
        detail = f"Some profiles disabled: {', '.join(disabled)}"
    else:
        status = "FAIL"
        detail = "All firewall profiles are disabled"

    return {"status": status, "detail": detail, "profiles": profiles}


def _check_defender() -> dict:
    """
    Check Windows Defender Antivirus status.

    Key properties from Get-MpComputerStatus:
        AntivirusEnabled          → Is real-time protection ON?
        RealTimeProtectionEnabled → Is real-time scanning active?
        AntivirusSignatureAge     → Days since last definition update

    Scoring logic:
        PASS    → Enabled + RealTime ON + Signatures updated within 7 days
        WARNING → Enabled but signatures are old (> 7 days)
        FAIL    → Disabled or not available

    Returns:
        {
            "status"         : "PASS" | "WARNING" | "FAIL",
            "detail"         : human-readable description,
            "av_enabled"     : bool,
            "realtime"       : bool,
            "signature_age"  : int (days)
        }
    """
    logger.info("Checking Windows Defender...")

    ps_command = (
        "Get-MpComputerStatus | "
        "Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureAge | "
        "Format-List"
    )
    output = _run_powershell(ps_command)

    if not output:
        return {
            "status": "FAIL",
            "detail": "Could not retrieve Defender status (may require Admin)",
            "av_enabled": False,
            "realtime": False,
            "signature_age": -1,
        }

    # Parse "Key : Value" lines from Format-List output
    parsed: dict[str, str] = {}
    for line in output.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            parsed[key.strip()] = value.strip()

    av_enabled = parsed.get("AntivirusEnabled", "False").lower() == "true"
    realtime   = parsed.get("RealTimeProtectionEnabled", "False").lower() == "true"

    try:
        sig_age = int(parsed.get("AntivirusSignatureAge", "-1"))
    except ValueError:
        sig_age = -1

    if not av_enabled:
        return {
            "status": "FAIL",
            "detail": "Windows Defender Antivirus is disabled",
            "av_enabled": av_enabled,
            "realtime": realtime,
            "signature_age": sig_age,
        }

    if not realtime:
        return {
            "status": "WARNING",
            "detail": "Defender is enabled but Real-Time Protection is OFF",
            "av_enabled": av_enabled,
            "realtime": realtime,
            "signature_age": sig_age,
        }

    # Signatures older than 7 days → WARNING
    if sig_age > 7:
        return {
            "status": "WARNING",
            "detail": f"Defender signatures are {sig_age} days old (threshold: 7 days)",
            "av_enabled": av_enabled,
            "realtime": realtime,
            "signature_age": sig_age,
        }

    return {
        "status": "PASS",
        "detail": f"Defender active, signatures {sig_age} day(s) old",
        "av_enabled": av_enabled,
        "realtime": realtime,
        "signature_age": sig_age,
    }


def _check_bitlocker() -> dict:
    """
    Check BitLocker encryption status on the C: (system) drive.

    Get-BitLockerVolume returns ProtectionStatus:
        0 = Off (unprotected)
        1 = On  (protected)
        2 = Unknown

    Scoring logic:
        PASS    → ProtectionStatus is On (1)
        WARNING → BitLocker exists but protection is Unknown
        FAIL    → Not encrypted, or BitLocker not available (Home edition)

    Note:
        BitLocker is only available on Windows Pro/Enterprise/Education.
        Windows Home will return an error → treated as FAIL.

    Returns:
        {
            "status"              : "PASS" | "WARNING" | "FAIL",
            "detail"              : human-readable description,
            "protection_status"   : "On" | "Off" | "Unknown" | "Unavailable",
            "recovery_key"        : "ghp_..." | "Unavailable/Requires Admin"
        }
    """
    logger.info("Checking BitLocker...")

    ps_command = (
        "(Get-BitLockerVolume -MountPoint 'C:').ProtectionStatus"
    )
    output = _run_powershell(ps_command)

    status_map = {"0": "Off", "1": "On", "2": "Unknown"}
    protection = status_map.get(output, "Unavailable")

    recovery_key = "Unavailable"

    if protection == "On":
        # Attempt to retrieve Recovery Key (Requires Admin privileges)
        key_cmd = (
            "(Get-BitLockerVolume -MountPoint 'C:').KeyProtector | "
            "Where-Object {$_.KeyProtectorType -eq 'RecoveryPassword'} | "
            "Select-Object -ExpandProperty RecoveryPassword"
        )
        key_output = _run_powershell(key_cmd)
        if key_output:
            recovery_key = key_output
        else:
            recovery_key = "Requires Administrator Privileges"

        return {
            "status": "PASS",
            "detail": "BitLocker is enabled and protecting C: drive",
            "protection_status": protection,
            "recovery_key": recovery_key,
        }
    elif protection == "Unknown":
        return {
            "status": "WARNING",
            "detail": "BitLocker status is Unknown — may be suspended",
            "protection_status": protection,
            "recovery_key": "Unknown",
        }
    elif protection == "Off":
        return {
            "status": "FAIL",
            "detail": "BitLocker is OFF — C: drive is not encrypted",
            "protection_status": protection,
            "recovery_key": "None",
        }
    else:
        return {
            "status": "FAIL",
            "detail": "BitLocker not available (requires Windows Pro/Enterprise)",
            "protection_status": protection,
            "recovery_key": "None",
        }


def _check_windows_update() -> dict:
    """
    Check if the system has received recent Windows Updates.

    Strategy:
        Use Get-HotFix to find the most recently installed patch.
        If last patch is within 30 days  → PASS
        If last patch is 31–90 days old  → WARNING
        If last patch is over 90 days    → FAIL

    Why 30/90 days?
        Microsoft releases Patch Tuesday monthly.
        30 days = applied last month's patches.
        90 days = 3 missed cycles = significantly outdated.

    Returns:
        {
            "status"        : "PASS" | "WARNING" | "FAIL",
            "detail"        : human-readable description,
            "last_patch"    : ISO date string or "Unknown",
            "days_since"    : int
        }
    """
    logger.info("Checking Windows Update history...")

    # Sort by InstalledOn descending, take the first entry's date
    ps_command = (
        "Get-HotFix | "
        "Sort-Object InstalledOn -Descending | "
        "Select-Object -First 1 -ExpandProperty InstalledOn | "
        "Get-Date -Format 'yyyy-MM-dd'"
    )
    output = _run_powershell(ps_command)

    if not output:
        return {
            "status": "FAIL",
            "detail": "Could not retrieve Windows Update history",
            "last_patch": "Unknown",
            "days_since": -1,
        }

    try:
        last_patch_date = datetime.strptime(output, "%Y-%m-%d")
        today = datetime.now()
        days_since = (today - last_patch_date).days
        last_patch_str = output
    except ValueError:
        return {
            "status": "FAIL",
            "detail": f"Could not parse patch date: '{output}'",
            "last_patch": "Unknown",
            "days_since": -1,
        }

    if days_since <= 30:
        status = "PASS"
        detail = f"Last patch installed {days_since} day(s) ago ({last_patch_str})"
    elif days_since <= 90:
        status = "WARNING"
        detail = f"Last patch installed {days_since} day(s) ago — consider updating"
    else:
        status = "FAIL"
        detail = f"Last patch installed {days_since} day(s) ago — critically outdated"

    return {
        "status": status,
        "detail": detail,
        "last_patch": last_patch_str,
        "days_since": days_since,
    }


# ── Public API ───────────────────────────────────────────────────────────────

def get_security_info() -> dict:
    """
    Run all security checks and return a combined result dictionary.

    Each check is isolated in its own try/except so one failure
    does not prevent the others from running.

    Returns:
        {
            "firewall"       : { status, detail, profiles },
            "defender"       : { status, detail, av_enabled, realtime, signature_age },
            "bitlocker"      : { status, detail, protection_status },
            "windows_update" : { status, detail, last_patch, days_since }
        }
    """
    logger.info("Starting security audit...")

    security: dict = {}

    checks = {
        "firewall":       _check_firewall,
        "defender":       _check_defender,
        "bitlocker":      _check_bitlocker,
        "windows_update": _check_windows_update,
    }

    for check_name, check_fn in checks.items():
        try:
            security[check_name] = check_fn()
        except Exception as exc:
            # Unexpected error → FAIL with error message preserved for debugging
            logger.error("Security check '%s' failed unexpectedly: %s", check_name, exc)
            security[check_name] = {
                "status": "FAIL",
                "detail": f"Unexpected error: {exc}",
            }

    logger.info("Security audit complete.")
    return security
