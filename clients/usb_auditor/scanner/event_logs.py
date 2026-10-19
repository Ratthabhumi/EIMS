"""
scanner/event_logs.py

Collects a bounded set of Windows Event Log entries (System + Application)
for offline evidence collection. Events are structured for downstream
AI analysis via the EIMS backend.

Design:
    - Uses PowerShell Get-WinEvent (same subprocess pattern as security.py)
    - Channels: System, Application (Security requires admin + audit policy)
    - Levels: Critical(1), Error(2), Warning(3)
    - Default: last 24h, max 500 events
    - Collection failure is ALWAYS non-fatal
    - No BitLocker recovery keys are ever collected

Env vars:
    EIMS_EVENT_LOG_ENABLED     → true/false (default: true)
    EIMS_EVENT_LOG_HOURS       → 1..168 (default: 24)
    EIMS_EVENT_LOG_MAX_RECORDS → 1..5000 (default: 500)
"""

import json
import logging
import subprocess
from scanner.processes import run_readonly
from datetime import datetime, timedelta, timezone

from config.settings import (
    EVENT_LOG_ENABLED,
    EVENT_LOG_HOURS,
    EVENT_LOG_MAX_RECORDS,
)
from config import settings
from exporters.json_exporter import redact_secrets

logger = logging.getLogger(__name__)

# Levels to collect: Critical=1, Error=2, Warning=3
_LEVELS = [1, 2, 3]

# Channels to query (Security excluded — requires admin + audit policy)
_CHANNELS = ["System", "Application"]

# Fields extracted from Get-WinEvent
_SELECT_FIELDS = "TimeCreated, Id, ProviderName, LevelDisplayName, LogName, RecordId, Message"

# Hard caps (never exceeded regardless of env)
_HARD_MAX_HOURS = 168
_HARD_MAX_RECORDS = 5000


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _run_powershell(command: str, timeout: int = 30) -> str:
    """
    Execute a PowerShell command and return stdout as a stripped string.
    Non-fatal: returns empty string on any failure.
    """
    try:
        result = run_readonly(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command",
             "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); " + command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError("Event query failed; check permissions and channel availability")
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning("PowerShell Get-WinEvent timed out after %ds", timeout)
        raise RuntimeError("Event query timed out") from None
    except FileNotFoundError:
        logger.error("PowerShell executable not found on PATH")
        raise RuntimeError("PowerShell unavailable") from None
    except (OSError, UnicodeError):
        raise RuntimeError("Event query unavailable") from None


def _build_powershell_command(hours: int, max_records: int) -> str:
    """
    Build a PowerShell command that retrieves bounded Windows Event Log entries
    from System and Application channels with Critical/Error/Warning levels.
    """
    start_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )
    levels = ",".join(str(lvl) for lvl in _LEVELS)
    channels = "@(" + ",".join(f'"{ch}"' for ch in _CHANNELS) + ")"
    fields = _SELECT_FIELDS

    return (
        "$ErrorActionPreference='Stop'; try { "
        f"$start = [DateTime]::Parse('{start_time}Z').ToLocalTime(); "
        f"Get-WinEvent -FilterHashtable @{{LogName={channels}; "
        f"StartTime=$start; Level=@({levels})}} "
        f"-MaxEvents {max_records} "
        f"| Select-Object {fields} "
        f"| ConvertTo-Json -Compress -Depth 1"
        " } catch { if ($_.FullyQualifiedErrorId -like 'NoMatchingEventsFound*') { '[]' } else { exit 1 } }"
    )


def _parse_occurrence_time(value) -> str:
    """
    Normalize a PowerShell TimeCreated value to ISO-8601 UTC.
    Windows PowerShell 5.1 ConvertTo-Json serializes DateTime as
    "/Date(<epoch-ms>)/" (WMI style); PowerShell 7 emits ISO-8601.
    """
    if not value:
        return ""
    try:
        text = str(value).strip()
        if text.startswith("/Date(") and text.endswith(")/"):
            millis = int(text[len("/Date("):-len(")/")].strip())
            return datetime.fromtimestamp(millis / 1000, tz=timezone.utc).isoformat(timespec="seconds")
        return text
    except (TypeError, ValueError, OSError):
        return ""


def _parse_events(raw_json: str) -> list[dict]:
    """
    Parse PowerShell JSON output into normalized event dicts.
    Handles both single-object (1 event) and array (N events) responses.
    Filters out any recovery-password-like fields (BitLocker boundary).
    """
    if not raw_json:
        return []

    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        raise ValueError("Invalid event response") from None

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        raise ValueError("Invalid event response type")
    events = []
    remaining = 8 * 1024 * 1024
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Invalid event record")
        raw_message = str(item.get('Message') or '')
        original = redact_secrets(raw_message)
        original_bytes = len(original.encode('utf-8'))
        message = _truncate_message(original, min(65536, remaining))
        saved_bytes = len(message.encode('utf-8'))
        remaining -= saved_bytes
        event = {
            "occurrence_time": _parse_occurrence_time(item.get("TimeCreated")),
            "event_id": item.get("Id"),
            "provider": item.get("ProviderName", "Unknown"),
            "severity": item.get("LevelDisplayName", "Unknown"),
            "channel": item.get("LogName", "Unknown"),
            "record_id": item.get("RecordId"),
            "message": message,
            "message_original_bytes": original_bytes,
            "message_saved_bytes": saved_bytes,
            "message_redacted": original != raw_message,
            "message_truncated": saved_bytes < original_bytes,
            "message_truncation_reason": ('collection_message_limit' if remaining == 0 else 'per_event_limit') if saved_bytes < original_bytes else '',

        }
        events.append(event)

    return redact_secrets(events)


def _truncate_message(message: str, max_length: int = 65536) -> str:
    """UTF-8 byte cap; callers retain explicit truncation metadata."""
    return str(message or '').encode('utf-8')[:max(0, max_length)].decode('utf-8', errors='ignore')


def collect_event_logs() -> dict:
    """
    Collect bounded Windows Event Log evidence.

    Returns:
        {
            "enabled": bool,
            "collection_hours": int,
            "max_records": int,
            "channels": [...],
            "levels": [...],
            "collected": int,
            "status": "ok" | "error" | "disabled",
            "message": str,
            "events": [...]
        }

    Non-fatal: returns status="error" with events=[] on any failure.
    """
    if not settings.EVENT_LOG_ENABLED:
        return {
            "enabled": False,
            "collection_hours": settings.EVENT_LOG_HOURS,
            "max_records": settings.EVENT_LOG_MAX_RECORDS,
            "channels": list(_CHANNELS),
            "levels": list(_LEVELS),
            "collected": 0,
            "status": "disabled",
            "message": "Event log collection disabled via EIMS_EVENT_LOG_ENABLED=false",
            "events": [],
        }

    hours = _clamp(settings.EVENT_LOG_HOURS, 1, _HARD_MAX_HOURS)
    max_records = _clamp(settings.EVENT_LOG_MAX_RECORDS, 1, _HARD_MAX_RECORDS)

    try:
        command = _build_powershell_command(hours, max_records)
        raw_output = _run_powershell(command, timeout=30)

        if not raw_output:
            raise RuntimeError("No event response; collection was not verified")
        if raw_output == "[]":
            return {
                "enabled": True,
                "collection_hours": hours,
                "max_records": max_records,
                "channels": list(_CHANNELS),
                "levels": list(_LEVELS),
                "collected": 0,
                "status": "ok",
                "message": "No events found in the specified time window",
                "events": [],
            }

        events = _parse_events(raw_output)

        return {
            "enabled": True,
            "collection_hours": hours,
            "max_records": max_records,
            "channels": list(_CHANNELS),
            "levels": list(_LEVELS),
            "collected": len(events),
            "possibly_truncated": len(events) >= max_records,
            "message_limits": {"per_event_bytes": 65536, "total_message_bytes": 8 * 1024 * 1024},
            "status": "ok",
            "message": f"Collected {len(events)} events from {len(_CHANNELS)} channels",
            "events": events,
        }

    except Exception as exc:
        logger.error("Event log collection failed: %s", exc)
        return {
            "enabled": True,
            "collection_hours": hours,
            "max_records": max_records,
            "channels": list(_CHANNELS),
            "levels": list(_LEVELS),
            "collected": 0,
            "status": "error",
            "message": f"Collection failed: {exc}",
            "events": [],
        }
