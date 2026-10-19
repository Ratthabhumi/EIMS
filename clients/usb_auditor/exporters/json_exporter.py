"""
exporters/json_exporter.py

Saves the complete audit result for one machine as a JSON file.

File naming convention:
    reports/ComputerName_YYYYMMDD_HHMMSS.json

Why this naming?
    - ComputerName  → identifies which machine was scanned
    - Timestamp     → ensures uniqueness (scan same machine twice = two files)
    - No spaces     → safe for all filesystems (FAT32 on USB drives included)

Why JSON as the primary storage format?
    - Human-readable and machine-readable
    - Language-agnostic → can be read by any tool in V2/V3
    - Easy to extend with new fields without breaking existing parsers
    - Acts as immutable audit log (write-once, never overwrite)

Immutability:
    We never overwrite existing reports. Each scan creates a new file.
    This provides a natural audit trail (non-repudiation).
"""

import json
import logging
import re
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path

from config.settings import REPORTS_DIR

logger = logging.getLogger(__name__)


def redact_secrets(value):
    """Exclude legacy secret fields and recovery passwords from saved evidence."""
    if isinstance(value, dict):
        return {key: redact_secrets(item) for key, item in value.items()
                if re.sub(r"[^a-z]", "", key.lower()) not in
                {"recoverykey", "recoverypassword", "password", "accesstoken", "secretkey"}}
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, str):
        return re.sub(r"(?<!\d)(?:\d{6}-){7}\d{6}(?!\d)", "[REDACTED]", value)
    return value


def save_report(
    system: dict,
    security: dict,
    services: dict,
    registry: dict,
    compliance: dict,
    setup_verify: dict | None = None,
    event_logs: dict | None = None,
    firewall_evidence: dict | None = None,
) -> Path:
    """
    Assemble all scan results into a single report dict and save as JSON.

    The report structure is designed to be self-contained:
        - system     → who/what was scanned
        - security   → Windows security check results
        - services   → Windows Services audit results
        - registry   → Registry security check results
        - compliance → Aggregated score and verdict
        - metadata   → Auditor version and report format version (for V2/V3 compatibility)

    Args:
        system     : Output from scanner/system_info.py
        security   : Output from scanner/security.py
        services   : Output from scanner/services.py
        registry   : Output from scanner/registry.py
        compliance : Output from scanner/compliance.py

    Returns:
        Path to the created JSON file.

    Raises:
        OSError: If the file cannot be written (e.g., USB is full or write-protected).
    """
    # ── Build filename ───────────────────────────────────────────────────────
    computer_name = system.get("computer_name", "UNKNOWN")
    timestamp_str = datetime.now().strftime("%d-%m-%Y_%H.%M.%S.%f") + "_" + uuid4().hex[:8]

    # Sanitize computer name: replace any character that's invalid in filenames
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in computer_name)
    filename = f"{safe_name}_{timestamp_str}.json"
    filepath = REPORTS_DIR / filename

    # ── Assemble report payload ──────────────────────────────────────────────
    report = {
        "metadata": {
            "auditor_version": "1.1.0",
            "report_format":   "1",
            "generated_at":    datetime.now(timezone.utc).isoformat(),
            "event_evidence_status": (event_logs or {}).get("status", "unavailable"),
        },
        "system":           system,
        "security":         security,
        "services":         services,
        "registry":         registry,
        "setup_verify":     setup_verify or {},
        "compliance_score": compliance["score"],
        "compliance":       compliance,
    }

    if event_logs is not None:
        report["event_logs"] = event_logs
    if firewall_evidence is not None:
        report['firewall_evidence'] = firewall_evidence

    # ── Write JSON ───────────────────────────────────────────────────────────
    # indent=2   → human-readable (important for audit review)
    # ensure_ascii=False → preserve Thai/Unicode characters in computer names
    # We do NOT use mode="w" with exist_ok — if the file exists, something is wrong.
    try:
        with open(filepath, "x", encoding="utf-8") as f:
            json.dump(redact_secrets(report), f, indent=2, ensure_ascii=False, default=str)

        logger.info("Report saved: %s", filepath)
        return filepath

    except OSError as exc:
        logger.error("Failed to write report '%s': %s", filepath, exc)
        raise
