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
from datetime import datetime, timezone
from pathlib import Path

from config.settings import REPORTS_DIR

logger = logging.getLogger(__name__)


def save_report(
    system: dict,
    security: dict,
    services: dict,
    registry: dict,
    compliance: dict,
    setup_verify: dict | None = None,
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
    timestamp_str = datetime.now().strftime("%d-%m-%Y_%H.%M")

    # Sanitize computer name: replace any character that's invalid in filenames
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in computer_name)
    filename = f"{safe_name}_{timestamp_str}.json"
    filepath = REPORTS_DIR / filename

    # ── Remove old reports for same machine (1 machine = 1 file) ────────────
    # Each audit overwrites the previous one so Excel always shows one row
    # per machine, not one row per run.
    for old_file in REPORTS_DIR.glob(f"{safe_name}_*.json"):
        try:
            old_file.unlink()
            logger.info("Removed old report: %s", old_file.name)
        except OSError as exc:
            logger.warning("Could not remove old report '%s': %s", old_file.name, exc)

    # ── Assemble report payload ──────────────────────────────────────────────
    report = {
        "metadata": {
            "auditor_version": "1.0.0",
            "report_format":   "1",
            "generated_at":    datetime.now(timezone.utc).isoformat(),
        },
        "system":           system,
        "security":         security,
        "services":         services,
        "registry":         registry,
        "setup_verify":     setup_verify or {},
        "compliance_score": compliance["score"],
        "compliance":       compliance,
    }

    # ── Write JSON ───────────────────────────────────────────────────────────
    # indent=2   → human-readable (important for audit review)
    # ensure_ascii=False → preserve Thai/Unicode characters in computer names
    # We do NOT use mode="w" with exist_ok — if the file exists, something is wrong.
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        logger.info("Report saved: %s", filepath)
        return filepath

    except OSError as exc:
        logger.error("Failed to write report '%s': %s", filepath, exc)
        raise
