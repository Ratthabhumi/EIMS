"""
scanner/compliance.py

Compliance score engine — aggregates results from all scanners
into a single numeric score and a Pass/Fail verdict.

Scoring Model:
    PASS    = 100 points
    WARNING = 50  points
    FAIL    = 0   points
    UNKNOWN = 0   points  (Fail-Safe Default)

    Compliance Score (%) = (total earned points / max possible points) × 100

    Verdict:
        >= 80% → "Compliant"
        <  80% → "Non-Compliant"

Why 80% threshold?
    Common industry baseline (CIS Controls, NIST CSF) uses tiered thresholds.
    80% allows one WARNING without failing compliance,
    but any FAIL on critical checks should be flagged clearly.

Design:
    - Each check (security, service, registry) contributes equally by default.
    - Scores are extracted by looking for a "status" key in nested dicts.
    - This module is purely functional — no I/O, no side effects.
"""

import logging
from config.settings import SCORE_MAP, COMPLIANCE_THRESHOLD

logger = logging.getLogger(__name__)


# ── Score Extraction ─────────────────────────────────────────────────────────

def _extract_statuses(data: dict) -> list[str]:
    """
    Walk a dict of check results and collect all "status" values.

    Handles two shapes of data:
        Shape A (security): { "firewall": { "status": "PASS", ... }, ... }
        Shape B (services): { "WinDefend": { "status": "PASS", ... }, ... }
        Shape C (registry): { "UAC": { "status": "PASS", ... }, ... }

    All three shapes are the same structure — a flat dict where each value
    is a dict containing a "status" key.

    Args:
        data: dict of check results from any scanner module.

    Returns:
        List of status strings (e.g., ["PASS", "WARNING", "FAIL"]).
    """
    statuses: list[str] = []
    for check_result in data.values():
        if isinstance(check_result, dict) and "status" in check_result:
            statuses.append(check_result["status"])
    return statuses


def _score_statuses(statuses: list[str]) -> tuple[int, int]:
    """
    Convert a list of status strings into earned and max possible points.

    Args:
        statuses: List of "PASS" / "WARNING" / "FAIL" / "UNKNOWN" strings.

    Returns:
        Tuple of (earned_points, max_possible_points).
        max_possible = len(statuses) × SCORE_MAP["PASS"]
    """
    if not statuses:
        return 0, 0

    earned = sum(SCORE_MAP.get(s, 0) for s in statuses)
    max_possible = len(statuses) * SCORE_MAP["PASS"]
    return earned, max_possible


# ── Public API ───────────────────────────────────────────────────────────────

def calculate_compliance(
    security: dict,
    services: dict,
    registry: dict,
    setup_verify: dict | None = None,
) -> dict:
    """
    Calculate overall compliance score from all scanner results.

    Args:
        security      : Result dict from scanner/security.py
        services      : Result dict from scanner/services.py
        registry      : Result dict from scanner/registry.py
        setup_verify  : Result dict from scanner/setup_verify.py (optional)

    Returns:
        {
            "score"        : int   (0-100, percentage),
            "verdict"      : str   ("Compliant" | "Non-Compliant"),
            "total_checks" : int   (number of individual checks evaluated),
            "pass_count"   : int,
            "warning_count": int,
            "fail_count"   : int,
            "breakdown": {
                "security"     : { "score": int, "checks": int },
                "services"     : { "score": int, "checks": int },
                "registry"     : { "score": int, "checks": int },
                "setup_verify" : { "score": int, "checks": int },
            }
        }
    """
    logger.info("Calculating compliance score...")

    # ── Collect statuses per domain ──────────────────────────────────────────
    security_statuses     = _extract_statuses(security)
    services_statuses     = _extract_statuses(services)
    registry_statuses     = _extract_statuses(registry)
    setup_verify_statuses = _extract_statuses(setup_verify) if setup_verify else []

    all_statuses = (
        security_statuses
        + services_statuses
        + registry_statuses
        + setup_verify_statuses
    )

    # ── Per-domain scores for breakdown ─────────────────────────────────────
    def domain_score(statuses: list[str]) -> int:
        """Return 0-100 score for a single domain."""
        earned, maximum = _score_statuses(statuses)
        if maximum == 0:
            return 0
        return round((earned / maximum) * 100)

    # ── Overall score ────────────────────────────────────────────────────────
    total_earned, total_max = _score_statuses(all_statuses)

    if total_max == 0:
        # No checks at all — treat as completely non-compliant
        overall_score = 0
        logger.warning("No checks were evaluated — score defaulting to 0")
    else:
        overall_score = round((total_earned / total_max) * 100)

    # ── Verdict ──────────────────────────────────────────────────────────────
    verdict = "Compliant" if overall_score >= COMPLIANCE_THRESHOLD else "Non-Compliant"

    # ── Count totals ────────────────────────────────────────────────────────
    pass_count    = all_statuses.count("PASS")
    warning_count = all_statuses.count("WARNING")
    fail_count    = sum(1 for s in all_statuses if s in ("FAIL", "UNKNOWN"))

    result = {
        "score":         overall_score,
        "verdict":       verdict,
        "total_checks":  len(all_statuses),
        "pass_count":    pass_count,
        "warning_count": warning_count,
        "fail_count":    fail_count,
        "breakdown": {
            "security": {
                "score":  domain_score(security_statuses),
                "checks": len(security_statuses),
            },
            "services": {
                "score":  domain_score(services_statuses),
                "checks": len(services_statuses),
            },
            "registry": {
                "score":  domain_score(registry_statuses),
                "checks": len(registry_statuses),
            },
            "setup_verify": {
                "score":  domain_score(setup_verify_statuses),
                "checks": len(setup_verify_statuses),
            },
        },
    }

    logger.info(
        "Compliance result: %d%% — %s (PASS: %d | WARNING: %d | FAIL: %d)",
        overall_score, verdict, pass_count, warning_count, fail_count,
    )

    return result
