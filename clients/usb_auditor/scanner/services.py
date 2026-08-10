"""
scanner/services.py

Audits the status of critical Windows Services using psutil.

Why psutil instead of subprocess (sc query / Get-Service)?
    - psutil.win_service_get() returns a structured object (not raw text).
    - Faster than spawning a PowerShell process per service.
    - We already depend on psutil for system_info.py → no new dependency.
    - Handles encoding issues on non-English Windows automatically.

Service scoring logic:
    Each service has an "expected" state (Running or Stopped).
    PASS    → service is in the expected state
    WARNING → service exists but is in an unexpected state
    FAIL    → service not found (not installed) or access denied
"""

import logging
import psutil

from config.settings import SERVICES_TO_AUDIT

logger = logging.getLogger(__name__)

# ── Expected States per Service ──────────────────────────────────────────────
#
# Most services should be "running" to protect the system.
# RemoteRegistry is the exception: it SHOULD be stopped/disabled.
# Allowing remote registry access is a known lateral movement vector
# used in post-exploitation frameworks (e.g., Metasploit, Impacket).

EXPECTED_STATES: dict[str, str] = {
    "WinDefend":      "running",   # Defender must be active
    "BITS":           "running",   # Required by Windows Update downloader
    "wuauserv":       "running",   # Windows Update service
    "RemoteRegistry": "stopped",   # Must be OFF — remote registry = attack vector
    "W32Time":        "running",   # Time sync — required for Kerberos & log integrity
}


# ── Service Status Lookup ────────────────────────────────────────────────────

def _get_service_status(service_name: str) -> dict:
    """
    Query a single Windows service and return its current status.

    psutil.win_service_get(name) raises:
        psutil.NoSuchProcess  → service does not exist
        AccessDenied          → insufficient permissions (rare for service query)

    psutil service status strings (from Windows SCM):
        "running"  → SERVICE_RUNNING
        "stopped"  → SERVICE_STOPPED
        "paused"   → SERVICE_PAUSED
        "start_pending"  → starting
        "stop_pending"   → stopping

    Returns:
        {
            "service_name"  : str,
            "display_name"  : str,
            "status"        : "PASS" | "WARNING" | "FAIL",
            "actual_state"  : str (e.g. "running", "stopped"),
            "expected_state": str,
            "start_type"    : str (e.g. "automatic", "manual", "disabled"),
            "detail"        : str
        }
    """
    label = SERVICES_TO_AUDIT.get(service_name, service_name)
    expected = EXPECTED_STATES.get(service_name, "running")

    try:
        svc = psutil.win_service_get(service_name)
        info = svc.as_dict()

        actual_state: str = info.get("status", "unknown").lower()
        start_type: str   = info.get("start_type", "unknown").lower()
        display_name: str = info.get("display_name", label)

        # ── Determine audit result ───────────────────────────────────────
        if actual_state == expected:
            audit_status = "PASS"
            detail = f"{display_name} is {actual_state} (expected: {expected})"
        else:
            # Service exists but is not in the expected state
            audit_status = "WARNING"
            detail = (
                f"{display_name} is '{actual_state}' "
                f"but expected '{expected}'"
            )

        return {
            "service_name":   service_name,
            "display_name":   display_name,
            "status":         audit_status,
            "actual_state":   actual_state,
            "expected_state": expected,
            "start_type":     start_type,
            "detail":         detail,
        }

    except psutil.NoSuchProcess:
        # Service is not installed on this machine
        # Treated as FAIL because we cannot verify its security state
        logger.warning("Service not found: %s", service_name)
        return {
            "service_name":   service_name,
            "display_name":   label,
            "status":         "FAIL",
            "actual_state":   "not_found",
            "expected_state": expected,
            "start_type":     "unknown",
            "detail":         f"Service '{service_name}' is not installed on this machine",
        }

    except psutil.AccessDenied:
        # Querying services usually doesn't require Admin, but just in case
        logger.warning("Access denied when querying service: %s", service_name)
        return {
            "service_name":   service_name,
            "display_name":   label,
            "status":         "FAIL",
            "actual_state":   "access_denied",
            "expected_state": expected,
            "start_type":     "unknown",
            "detail":         f"Access denied when querying '{service_name}' — run as Administrator",
        }

    except Exception as exc:
        logger.error("Unexpected error querying service '%s': %s", service_name, exc)
        return {
            "service_name":   service_name,
            "display_name":   label,
            "status":         "FAIL",
            "actual_state":   "error",
            "expected_state": expected,
            "start_type":     "unknown",
            "detail":         f"Unexpected error: {exc}",
        }


# ── Public API ───────────────────────────────────────────────────────────────

def get_services_info() -> dict:
    """
    Audit all services defined in config/settings.py SERVICES_TO_AUDIT.

    Iterates over each service name, queries its state, and builds
    a result dictionary keyed by service name.

    Adding new services to audit → update SERVICES_TO_AUDIT in settings.py only.
    No changes needed here.

    Returns:
        {
            "WinDefend":      { status, actual_state, expected_state, ... },
            "BITS":           { ... },
            "wuauserv":       { ... },
            "RemoteRegistry": { ... },
            "W32Time":        { ... },
        }
    """
    logger.info("Starting Windows Services audit...")

    services_result: dict = {}

    for service_name in SERVICES_TO_AUDIT:
        services_result[service_name] = _get_service_status(service_name)

    # Summary log: how many PASS / WARNING / FAIL
    statuses = [v["status"] for v in services_result.values()]
    logger.info(
        "Services audit complete — PASS: %d | WARNING: %d | FAIL: %d",
        statuses.count("PASS"),
        statuses.count("WARNING"),
        statuses.count("FAIL"),
    )

    return services_result
