"""
scanner/setup_verify.py

Post-Clone Setup Verification Scanner

Verifies that Windows setup steps performed after imaging/cloning
have been completed correctly per the organization's deployment checklist.

Checks (aligned to Post-Clone Checklist):
    - Computer Name : Must match BIOS serial number (Step 3)
    - Timezone      : Must be UTC+07:00 Bangkok (Step 5)
    - Non-Unicode   : System locale must be Thai (ACP=874) (Step 4)
    - DHCP          : LAN and WLAN must be DHCP, not static (Step 7)
    - Date & Time   : System time must be NTP-synced (Step 9)
    - Thai Keyboard : Thai keyboard layout must be installed (Step 11)
    - NetLogon.reg  : Machine should be domain-joined (Step 18, KYBT Only)
    - Default Apps  : Outlook (email), Adobe Reader (PDF) (Step 19)
    - SentinelOne   : Agent service must be running (Steps 22/23)
    - WiFi Profiles : Must be 0 saved profiles (Step 24)
    - New Outlook   : Must be uninstalled (Step 31)
    - Xbox App      : Must be uninstalled (Step 32)

Scoring:
    PASS    = requirement met
    WARNING = uncertain / could not determine
    FAIL    = requirement not met

Design:
    Uses PowerShell for AppX and WiFi checks (no native Python equivalent).
    Uses psutil for SentinelOne service check (consistent with services.py).
"""

import logging
import subprocess

import psutil

logger = logging.getLogger(__name__)


# ── PowerShell Helper ─────────────────────────────────────────────────────────

def _run_powershell(command: str, timeout: int = 15) -> str:
    """
    Run a PowerShell command and return stripped stdout.
    Returns empty string on any failure.
    """
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


# ── Individual Checks ─────────────────────────────────────────────────────────

def _check_computer_name_serial() -> dict:
    """
    Verify that the Computer Name matches the machine's BIOS serial number.

    Expected: computer name equals serial number (or starts with it if a
    location/department suffix has been appended, e.g. "5CD0141N35-Int3").

    Scoring:
        PASS    = computer name exactly equals BIOS serial number
        WARNING = computer name starts with serial number (suffix present)
        FAIL    = computer name does not contain the serial number

    Why check this?
        Deployment SOP requires the machine be renamed to its serial number
        immediately after cloning for asset tracking and SCCM/WSUS compliance.
    """
    serial = _run_powershell(
        "$ErrorActionPreference = 'SilentlyContinue'; "
        "(Get-CimInstance Win32_BIOS).SerialNumber"
    ).strip()

    import socket
    computer_name = socket.gethostname().upper()

    if not serial:
        return {
            "status": "WARNING",
            "detail": "Could not read BIOS serial number",
            "computer_name": computer_name,
            "serial_number": None,
        }

    serial_upper = serial.upper()

    if computer_name == serial_upper:
        return {
            "status": "PASS",
            "detail": f"Computer name matches serial number ({serial})",
            "computer_name": computer_name,
            "serial_number": serial,
        }
    elif computer_name.startswith(serial_upper):
        suffix = computer_name[len(serial_upper):]
        return {
            "status": "WARNING",
            "detail": (
                f"Computer name starts with serial number but has suffix '{suffix}' "
                f"— acceptable if intentional (e.g. location code)"
            ),
            "computer_name": computer_name,
            "serial_number": serial,
        }
    else:
        return {
            "status": "FAIL",
            "detail": (
                f"Computer name '{computer_name}' does not match "
                f"serial number '{serial}' — rename the machine"
            ),
            "computer_name": computer_name,
            "serial_number": serial,
        }


def _check_timezone() -> dict:
    """
    Verify system timezone is set to UTC+07:00 Bangkok.

    Expected Windows timezone ID: "SE Asia Standard Time"

    Why check this?
        Incorrect timezone causes log timestamps to be wrong,
        which breaks audit trail correlation and Kerberos authentication.
    """
    output = _run_powershell("(Get-TimeZone).Id")
    expected = "SE Asia Standard Time"

    if output == expected:
        return {
            "status": "PASS",
            "detail": f"Timezone correctly set to UTC+07:00 Bangkok ({output})",
            "timezone_id": output,
        }
    elif output:
        return {
            "status": "FAIL",
            "detail": f"Timezone is '{output}' — expected '{expected}' (UTC+07:00 Bangkok)",
            "timezone_id": output,
        }
    else:
        return {
            "status": "WARNING",
            "detail": "Could not read timezone — check may need Admin rights",
            "timezone_id": "Unknown",
        }


def _check_sentinelone() -> dict:
    """
    Verify SentinelOne endpoint protection agent is installed and running.

    Service name: SentinelAgent
    Expected state: running

    Why check this?
        SentinelOne is the primary EDR (Endpoint Detection and Response)
        solution. A machine without a running agent is unprotected and
        invisible to the security operations center (SOC).
    """
    service_name = "SentinelAgent"
    try:
        svc = psutil.win_service_get(service_name)
        info = svc.as_dict()
        state = info.get("status", "unknown")

        if state == "running":
            return {
                "status": "PASS",
                "detail": "SentinelOne agent is installed and running",
                "actual_state": state,
            }
        else:
            return {
                "status": "FAIL",
                "detail": f"SentinelOne agent is installed but NOT running (state: {state})",
                "actual_state": state,
            }

    except psutil.NoSuchProcess:
        return {
            "status": "FAIL",
            "detail": "SentinelOne agent is NOT installed on this machine",
            "actual_state": "not_installed",
        }
    except Exception as exc:
        logger.warning("SentinelOne check failed: %s", exc)
        return {
            "status": "WARNING",
            "detail": f"Could not check SentinelOne status: {exc}",
            "actual_state": "unknown",
        }


def _check_wifi_profiles() -> dict:
    """
    Verify that all WiFi profiles have been deleted after setup.

    Expected: 0 saved profiles (all forgotten before handover).

    Why check this?
        Saved WiFi profiles may contain corporate or personal SSIDs/credentials
        from the imaging environment. They should be purged before deployment.
    """
    output = _run_powershell(
        "(netsh wlan show profiles | Select-String 'All User Profile').Count"
    )

    try:
        count = int(output)
    except (ValueError, TypeError):
        # No WiFi adapter or WLAN service not running
        return {
            "status": "WARNING",
            "detail": "Could not determine WiFi profile count (no WLAN adapter or service disabled)",
            "profile_count": -1,
        }

    if count == 0:
        return {
            "status": "PASS",
            "detail": "All WiFi profiles have been removed (0 profiles saved)",
            "profile_count": 0,
        }
    else:
        return {
            "status": "FAIL",
            "detail": f"{count} WiFi profile(s) still saved — must be 0 before handover",
            "profile_count": count,
        }


def _check_appx_uninstalled(package_name: str, display_name: str) -> dict:
    """
    Verify that an AppX/MSIX package is NOT installed for the current user.

    Uses $ErrorActionPreference = 'SilentlyContinue' to suppress any
    PowerShell errors going to stdout (which would cause false FAILs).

    PASS = package not found for current user
    FAIL = package still installed for current user

    Args:
        package_name : AppX package Name (e.g., "Microsoft.GamingApp")
        display_name : Human-readable label for messages
    """
    output = _run_powershell(
        f"$ErrorActionPreference = 'SilentlyContinue'; "
        f"(Get-AppxPackage -Name '{package_name}').Name"
    )

    # Strip any stray whitespace; treat empty as not installed
    is_installed = bool(output.strip())

    if is_installed:
        return {
            "status": "FAIL",
            "detail": f"{display_name} is still installed — should be uninstalled",
            "installed": True,
        }
    else:
        return {
            "status": "PASS",
            "detail": f"{display_name} is not installed",
            "installed": False,
        }



def _check_non_unicode_thai() -> dict:
    return {"status": "WARNING", "detail": "Check not implemented"}

def _check_dhcp() -> dict:
    return {"status": "WARNING", "detail": "Check not implemented"}

def _check_datetime_sync() -> dict:
    return {"status": "WARNING", "detail": "Check not implemented"}

def _check_thai_keyboard() -> dict:
    return {"status": "WARNING", "detail": "Check not implemented"}

def _check_netlogon_reg() -> dict:
    return {"status": "WARNING", "detail": "Check not implemented"}

def _check_default_apps() -> dict:
    return {"status": "WARNING", "detail": "Check not implemented"}

# ── Public API ────────────────────────────────────────────────────────────────

def get_setup_verify_info() -> dict:
    """
    Run all post-clone setup verification checks.

    Results include checks for:
        - BIOS Serial/Computer Name
        - Timezone (Bangkok)
        - Non-Unicode language (Thai)
        - DHCP configuration
        - Datetime NTP synchronization
        - Thai keyboard layout
        - NetLogon.reg (domain join)
        - Default apps (Outlook/Adobe)
        - SentinelOne agent
        - WiFi profiles
        - Unwanted AppX packages (New Outlook, Xbox)

    Returns:
        dict with check results for each verification item.
        Each value contains at minimum: status, detail.
    """
    logger.info("Starting post-clone setup verification...")

    results = {
        "computer_name_serial": _check_computer_name_serial(),
        "timezone":       _check_timezone(),
        "non_unicode_thai": _check_non_unicode_thai(),
        "dhcp":           _check_dhcp(),
        "datetime_sync":  _check_datetime_sync(),
        "thai_keyboard":  _check_thai_keyboard(),
        "netlogon_reg":   _check_netlogon_reg(),
        "default_apps":   _check_default_apps(),
        "sentinelone":    _check_sentinelone(),
        "wifi_profiles":  _check_wifi_profiles(),
        "new_outlook":    _check_appx_uninstalled(
            "Microsoft.OutlookForWindows", "New Outlook"
        ),
        "xbox":           _check_appx_uninstalled(
            "Microsoft.GamingApp", "Xbox / Gaming App"
        ),
    }

    pass_count = sum(1 for v in results.values() if v["status"] == "PASS")
    warn_count = sum(1 for v in results.values() if v["status"] == "WARNING")
    fail_count = sum(1 for v in results.values() if v["status"] == "FAIL")

    logger.info(
        "Setup verification complete -- PASS: %d | WARNING: %d | FAIL: %d",
        pass_count, warn_count, fail_count,
    )

    return results
