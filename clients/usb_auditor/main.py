# -*- coding: utf-8 -*-
"""
main.py — Portable Windows Compliance Auditor

Entry point for the auditor. Orchestrates all scanner modules,
saves the JSON report, and optionally exports the Excel summary.

Usage:
    python main.py          → Scan this machine and save JSON report
    python main.py --export → Scan + export Summary.xlsx from all reports
    python main.py --only-export → Export Summary.xlsx without scanning

Design:
    - Checks for Administrator privileges before scanning.
      Some checks (BitLocker, Defender) return better data with Admin rights.
    - Sets up file logging before any module runs.
    - All scanner modules are called sequentially (V1 is single-threaded).
    - Exit codes follow UNIX convention:
        0 = success (Compliant)
        1 = scan completed but Non-Compliant
        2 = fatal error (could not run)
"""

import argparse
import ctypes
import logging
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

from config.settings import LOGS_DIR
from scanner.system_info    import get_system_info
from scanner.security       import get_security_info
from scanner.services       import get_services_info
from scanner.registry       import get_registry_info
from scanner.setup_verify   import get_setup_verify_info
from scanner.compliance     import calculate_compliance
from exporters.json_exporter  import save_report
from exporters.excel_exporter import export_summary


# ── Logging Setup ────────────────────────────────────────────────────────────

def setup_logging(log_file: Path) -> None:
    """
    Configure logging to write to both:
        - Console (INFO level) -- operator sees progress in real time
        - Log file (DEBUG level) -- full detail for post-incident analysis

    Log filename: logs/{ComputerName}_{YYYYMMDD}.log
    Each machine gets its own log file -- no mixed entries.
    Rotating the log file is a V2 enhancement (use RotatingFileHandler).
    """
    log_format = "%(asctime)s [%(levelname)-8s] %(name)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Force stdout to UTF-8 so log messages with non-ASCII chars work on all terminals
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # Root logger at DEBUG -- handlers will filter by their own level
    logging.basicConfig(level=logging.DEBUG, format=log_format, datefmt=date_format,
                        handlers=[
                            # Console handler -- INFO and above
                            logging.StreamHandler(sys.stdout),
                            # File handler -- DEBUG and above (full trace)
                            logging.FileHandler(log_file, encoding="utf-8"),
                        ])

    # Silence overly verbose third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)


# ── Admin Check ──────────────────────────────────────────────────────────────

def is_admin() -> bool:
    """
    Check if the current process is running with Administrator privileges.

    Uses ctypes to call the Windows API IsUserAnAdmin().
    Returns False on non-Windows or if the check fails.

    Why check for Admin?
        Some PowerShell commands (Get-MpComputerStatus, Get-BitLockerVolume)
        return incomplete data or fail entirely without Admin rights.
        We warn the user but do NOT block execution — partial data is better
        than no data in a field audit scenario.
    """
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except AttributeError:
        return False


# ── CLI Argument Parser ──────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    """
    Define command-line interface arguments.

    --export       : After scanning, also export Summary.xlsx
    --only-export  : Skip scanning; only generate Summary.xlsx from existing JSONs
    """
    parser = argparse.ArgumentParser(
        prog="Windows Compliance Auditor",
        description=(
            "Portable Windows Security Compliance Auditor\n"
            "Scans this machine and saves results to the reports/ directory."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export Summary.xlsx after scanning",
    )
    parser.add_argument(
        "--only-export",
        action="store_true",
        dest="only_export",
        help="Skip scan; only export Summary.xlsx from existing reports",
    )
    return parser.parse_args()


# ── Banner ───────────────────────────────────────────────────────────────────

def print_banner() -> None:
    """Print a startup banner for operator clarity."""
    banner = """
+------------------------------------------------------+
|      Portable Windows Compliance Auditor  v1.0       |
|      DevSecOps Portfolio Project                     |
+------------------------------------------------------+
"""
    print(banner)


# ── Scan Pipeline ────────────────────────────────────────────────────────────

def run_scan(logger: logging.Logger) -> int:
    """
    Execute the full audit pipeline on the current machine.

    Pipeline:
        1. Collect system information
        2. Run security checks
        3. Audit Windows Services
        4. Audit Registry
        5. Post-clone Setup Verification
        6. Calculate compliance score
        7. Save JSON report

    Returns:
        Exit code: 0 = Compliant, 1 = Non-Compliant, 2 = Fatal error
    """
    print("\n[1/7] Collecting system information...")
    try:
        system = get_system_info()
        print(f"      [OK]  Computer : {system['computer_name']}")
        print(f"      [OK]  User     : {system['username']}")
        print(f"      [OK]  OS       : {system['windows_edition']}")
    except Exception as exc:
        logger.critical("FATAL: Could not collect system info: %s", exc)
        return 2

    print("\n[2/7] Auditing Windows Security...")
    try:
        security = get_security_info()
        for name, result in security.items():
            if result["status"] == "PASS":
                icon = "[OK]  "
            elif result["status"] == "WARNING":
                icon = "[WARN]"
            else:
                icon = "[FAIL]"
            print(f"      {icon} {name:<20} -> {result['status']}")
    except Exception as exc:
        logger.critical("FATAL: Security scan failed: %s", exc)
        return 2

    print("\n[3/7] Auditing Windows Services...")
    try:
        services = get_services_info()
        for svc_name, result in services.items():
            if result["status"] == "PASS":
                icon = "[OK]  "
            elif result["status"] == "WARNING":
                icon = "[WARN]"
            else:
                icon = "[FAIL]"
            print(f"      {icon} {svc_name:<20} -> {result['actual_state']}")
    except Exception as exc:
        logger.critical("FATAL: Services scan failed: %s", exc)
        return 2

    print("\n[4/7] Auditing Registry...")
    try:
        registry = get_registry_info()
        for key_name, result in registry.items():
            icon = "[OK]  " if result["status"] == "PASS" else "[FAIL]"
            print(f"      {icon} {key_name:<20} -> {result['status']} (actual: {result['actual']})")
    except Exception as exc:
        logger.critical("FATAL: Registry scan failed: %s", exc)
        return 2

    print("\n[5/7] Verifying Post-Clone Setup...")
    try:
        setup_verify = get_setup_verify_info()
        for check_name, result in setup_verify.items():
            if result["status"] == "PASS":
                icon = "[OK]  "
            elif result["status"] == "WARNING":
                icon = "[WARN]"
            else:
                icon = "[FAIL]"
            print(f"      {icon} {check_name:<20} -> {result['status']}")
    except Exception as exc:
        logger.critical("FATAL: Setup verification failed: %s", exc)
        return 2

    print("\n[6/7] Calculating Compliance Score...")
    try:
        compliance = calculate_compliance(security, services, registry, setup_verify)
        score   = compliance["score"]
        verdict = compliance["verdict"]
        icon    = "[OK]  " if verdict == "Compliant" else "[FAIL]"
        print(f"      {icon} Score  : {score}%")
        print(f"      {icon} Verdict: {verdict}")
        print(f"        PASS: {compliance['pass_count']} | "
              f"WARNING: {compliance['warning_count']} | "
              f"FAIL: {compliance['fail_count']}")
    except Exception as exc:
        logger.critical("FATAL: Compliance calculation failed: %s", exc)
        return 2

    print("\n[7/7] Saving JSON Report...")
    try:
        report_path = save_report(system, security, services, registry, compliance, setup_verify)
        print(f"      [OK]  Saved: {report_path}")
    except OSError as exc:
        logger.critical("FATAL: Could not save report: %s", exc)
        return 2

    # Return exit code based on compliance verdict
    return 0 if verdict == "Compliant" else 1


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    # ── Build per-machine log file path BEFORE setup_logging ────────────────
    # Use socket.gethostname() here (not get_system_info) to avoid
    # importing scanner before logging is ready.
    # Format: logs/COMPUTERNAME_YYYYMMDD.log
    computer_name = socket.gethostname()
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in computer_name)
    timestamp_str = datetime.now().strftime("%d-%m-%Y_%H.%M")
    log_file = LOGS_DIR / f"{safe_name}_{timestamp_str}.log"

    setup_logging(log_file)
    logger = logging.getLogger(__name__)

    print_banner()
    args = parse_args()

    # Admin warning (non-blocking)
    if not is_admin():
        print("  [WARN] Not running as Administrator.")
        print("    Some checks may return incomplete data.")
        print("    Recommend: Right-click -> Run as Administrator\n")

    exit_code = 0

    # ── Only export mode (no scan) ───────────────────────────────────────────
    if args.only_export:
        print("Export mode: generating Summary.xlsx from existing reports...\n")
        try:
            output = export_summary()
            print(f"\n[OK]  Summary.xlsx exported: {output}")
        except RuntimeError as exc:
            print(f"\n[FAIL] Export failed: {exc}")
            exit_code = 2
        except OSError as exc:
            logger.error("Export I/O error: %s", exc)
            exit_code = 2
        return exit_code

    # ── Normal scan mode ─────────────────────────────────────────────────────
    exit_code = run_scan(logger)

    # ── Optional Excel export ─────────────────────────────────────────────────
    if args.export or args.only_export:
        print("\n[+] Exporting Summary.xlsx...")
        try:
            output = export_summary()
            print(f"    [OK]  Exported: {output}")
        except RuntimeError as exc:
            print(f"    [SKIP] Export skipped: {exc}")
        except OSError as exc:
            logger.error("Export I/O error: %s", exc)

    print("\n" + "-" * 54)
    print(f"  Audit complete. Exit code: {exit_code}")
    print("-" * 54 + "\n")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
