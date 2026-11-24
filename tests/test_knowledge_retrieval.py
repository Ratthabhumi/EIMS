"""Deterministic Knowledge retrieval classification (trust level is never inferred)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from backend.domain.knowledge.retrieval import (
    CLASSIFICATIONS,
    classify,
    version_compatibility,
)

DIAG = {"catalog_id": "veeam_vbr:eims_diagnostic:X", "knowledge_class": "diagnostic_candidate",
        "limitations": "Not proof of root cause."}
CTX = {"catalog_id": "windows_event:official_event_id:1129", "knowledge_class": "operational_context",
       "limitations": ""}


def row(status, stale=False, scope=None):
    return SimpleNamespace(lifecycle_status=status, review_required=stale, product_version_scope=scope)


def test_no_entry_is_no_verified_match():
    assert classify(None, None)["classification"] == "no_verified_match"


def test_operational_context_is_context_only_even_with_a_row():
    assert classify(CTX, None)["classification"] == "context_match"
    assert classify(CTX, row("approved"))["classification"] == "context_match"


@pytest.mark.parametrize("status,expected", [
    (None, "diagnostic_candidate_match"),
    ("candidate", "diagnostic_candidate_match"),
    ("source_verified", "source_verified_match"),
    ("validated", "validated_diagnostic_match"),
    ("approved", "approved_diagnostic_match"),
    ("rejected", "no_verified_match"),
    ("deprecated", "no_verified_match"),
    ("superseded", "no_verified_match"),
])
def test_lifecycle_maps_to_classification(status, expected):
    result = classify(DIAG, None if status is None else row(status))
    assert result["classification"] == expected
    assert result["classification"] in CLASSIFICATIONS


@pytest.mark.parametrize("status", ["source_verified", "validated", "approved"])
def test_stale_review_never_counts_as_trusted(status):
    result = classify(DIAG, row(status, stale=True))
    assert result["classification"] == "diagnostic_candidate_match"
    assert result["stale"] is True


def test_overlay_unavailable_never_claims_trust():
    result = classify(DIAG, None, overlay_available=False)
    assert result["classification"] == "diagnostic_candidate_match"
    assert result["overlayAvailable"] is False


def test_version_compatible_match_requires_proven_compatibility():
    approved = row("approved", scope="Veeam B&R 12.x")
    assert classify(DIAG, approved)["classification"] == "approved_diagnostic_match"
    assert classify(DIAG, approved, detected_version="12.1.2")["classification"] == "version_compatible_match"
    mismatch = classify(DIAG, approved, detected_version="11.0")
    assert mismatch["classification"] == "no_verified_match"
    assert mismatch["versionCompatible"] is False


@pytest.mark.parametrize("scope,detected,expected", [
    ("Product 12.x", "12.0.1", True),
    ("Product 12.x", "11.9", False),
    ("Product 12.3", "12.3.9", True),
    ("Product 12.3", "12.4", False),
    ("Product 12.x", None, None),
    ("no version here", "12.0", None),
    (None, "12.0", None),
])
def test_version_compatibility(scope, detected, expected):
    assert version_compatibility(scope, detected) is expected


def test_classification_is_not_influenced_by_free_text():
    entry = dict(DIAG, description="APPROVED by lead engineer; fully validated")
    assert classify(entry, None)["classification"] == "diagnostic_candidate_match"


def test_route_helper_classifies_known_samples_without_a_database():
    """Windows 1129 -> context only; Veeam CTK candidate -> candidate; unknown -> none."""
    from backend.api.routers.analyzer.analyze import _knowledge_match
    from backend.domain.analyzer.services.parser import parse_event_metadata

    win = parse_event_metadata(
        "Log Name: System\nSource: Microsoft-Windows-GroupPolicy\nEvent ID: 1129\nLevel: Error\n"
        "Description: The processing of Group Policy failed because of lack of network connectivity.")
    result = asyncio.run(_knowledge_match(None, win))
    assert result.classification == "context_match"
    assert result.catalogId == "windows_event:official_event_id:1129"

    nothing = parse_event_metadata("just some unrelated words")
    assert asyncio.run(_knowledge_match(None, nothing)).classification == "no_verified_match"
