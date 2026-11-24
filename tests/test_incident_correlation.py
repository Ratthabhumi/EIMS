"""Incident Core correlation matrix: deterministic, pure, asset-safe.

No database is required. These tests pin the v1 confidence rules and the
deterministic dedupe material so later refactors cannot silently weaken them.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from backend.domain.incident.correlation import (
    CONFIDENCE_MEDIUM,
    CONFIDENCE_NONE,
    CONFIDENCE_STRONG,
    CONFIDENCE_WEAK,
    DEFAULT_WINDOW_SECONDS,
    CorrelationInput,
    build_dedupe_key,
    classify,
    normalize_signature,
    window_bucket,
)

ASSET_A = UUID("11111111-1111-4111-8111-111111111111")
ASSET_B = UUID("22222222-2222-4222-8222-222222222222")
BASE = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
WINDOW = 900


def _input(asset_id, *, source_type="winlog", source_id="e-1", identity="4625", at=None):
    return CorrelationInput(
        asset_id=asset_id,
        source_type=source_type,
        source_id=source_id,
        signature=normalize_signature(source_type, identity),
        observed_at=at or BASE,
    )


def test_default_window_is_explicit_900_not_bundle_epsilon():
    assert DEFAULT_WINDOW_SECONDS == 900


def test_strong_same_asset_same_signature_inside_window():
    result = classify(_input(ASSET_A), _input(ASSET_A), window_seconds=WINDOW)
    assert result.confidence == CONFIDENCE_STRONG
    assert "same_asset_id" in result.reasons
    assert "same_signature" in result.reasons
    assert "within_window" in result.reasons
    assert result.mergeable is True


def test_strong_boundary_is_inclusive_of_window():
    later = BASE + timedelta(seconds=WINDOW)
    result = classify(_input(ASSET_A), _input(ASSET_A, at=later), window_seconds=WINDOW)
    assert result.confidence == CONFIDENCE_STRONG


def test_same_asset_same_signature_expanded_window_is_weak():
    later = BASE + timedelta(seconds=WINDOW + 300)
    result = classify(_input(ASSET_A), _input(ASSET_A, at=later), window_seconds=WINDOW)
    assert result.confidence == CONFIDENCE_WEAK
    assert "within_expanded_window" in result.reasons


def test_same_asset_same_signature_outside_expanded_window_is_none():
    later = BASE + timedelta(seconds=WINDOW * 2 + 1)
    result = classify(_input(ASSET_A), _input(ASSET_A, at=later), window_seconds=WINDOW)
    assert result.confidence == CONFIDENCE_NONE
    assert "outside_expanded_window" in result.reasons
    assert result.mergeable is False


def test_medium_same_asset_different_signature_inside_window():
    result = classify(
        _input(ASSET_A, identity="4625"),
        _input(ASSET_A, source_id="t-1", source_type="telemetry", identity="cpu-saturation"),
        window_seconds=WINDOW,
    )
    assert result.confidence == CONFIDENCE_MEDIUM
    assert "different_signature" in result.reasons
    assert "same_asset_id" in result.reasons


def test_medium_same_signature_inside_window_with_unresolved_asset():
    result = classify(_input(None), _input(None, source_id="e-2"), window_seconds=WINDOW)
    assert result.confidence == CONFIDENCE_MEDIUM
    assert "asset_unresolved" in result.reasons
    assert result.asset_key == "unresolved"


def test_medium_unresolved_candidate_keeps_existing_asset_context():
    result = classify(_input(None), _input(ASSET_A), window_seconds=WINDOW)
    assert result.confidence == CONFIDENCE_MEDIUM
    assert "asset_unresolved" in result.reasons


def test_weak_same_signature_within_expanded_window_unresolved():
    later = BASE + timedelta(seconds=WINDOW + 120)
    result = classify(_input(None), _input(None, at=later), window_seconds=WINDOW)
    assert result.confidence == CONFIDENCE_WEAK


def test_weak_explicit_single_source_evidence():
    result = classify(
        _input(ASSET_A),
        _input(ASSET_A, source_id="elsewhere", identity="different", at=BASE + timedelta(seconds=1000)),
        window_seconds=WINDOW,
        single_source=True,
    )
    assert result.confidence == CONFIDENCE_WEAK
    assert "single_source_evidence" in result.reasons


def test_different_assets_never_merge_even_with_identical_signature():
    result = classify(_input(ASSET_A), _input(ASSET_B), window_seconds=WINDOW)
    assert result.confidence == CONFIDENCE_NONE
    assert "different_asset_ids" in result.reasons
    assert result.mergeable is False


def test_different_assets_never_merge_even_as_single_source():
    result = classify(
        _input(ASSET_A), _input(ASSET_B), window_seconds=WINDOW, single_source=True
    )
    assert result.confidence == CONFIDENCE_NONE
    assert "different_asset_ids" in result.reasons


def test_ambiguous_asset_is_never_guessed():
    result = classify(_input(None), _input(None), window_seconds=WINDOW)
    assert result.asset_key == "unresolved"
    assert "asset_unresolved" in result.reasons
    assert "same_asset_id" not in result.reasons


def test_dedupe_key_is_deterministic_sha256_of_documented_material():
    import hashlib

    item = _input(ASSET_A)
    expected_material = (
        f"{ASSET_A}:{item.signature}:{window_bucket(BASE, WINDOW)}"
    )
    expected = hashlib.sha256(expected_material.encode("utf-8")).hexdigest()
    first = build_dedupe_key(ASSET_A, item.signature, BASE, WINDOW)
    second = build_dedupe_key(ASSET_A, item.signature, BASE, WINDOW)
    assert first == second == expected
    assert len(first) == 64


def test_dedupe_key_separates_unresolved_and_window_buckets():
    signature = normalize_signature("winlog", "4625")
    resolved = build_dedupe_key(ASSET_A, signature, BASE, WINDOW)
    unresolved = build_dedupe_key(None, signature, BASE, WINDOW)
    next_bucket = build_dedupe_key(ASSET_A, signature, BASE + timedelta(seconds=WINDOW), WINDOW)
    assert len({resolved, unresolved, next_bucket}) == 3


def test_signature_normalisation_is_presentation_insensitive():
    assert normalize_signature(" WinLog ", "  Event-4625 ") == normalize_signature(
        "winlog", "event-4625"
    )
    with pytest.raises(ValueError):
        normalize_signature("winlog", "   ")


def test_result_carries_bounded_reasons_and_sources():
    result = classify(
        _input(ASSET_A, source_id="win-1"),
        _input(ASSET_A, source_id="telemetry-9", source_type="telemetry", identity="cpu"),
        window_seconds=WINDOW,
    )
    assert result.sources == ("telemetry:telemetry-9", "winlog:win-1")
    assert isinstance(result.reasons, tuple)
    assert result.window_seconds == WINDOW
    assert result.dedupe_key == build_dedupe_key(ASSET_A, _input(ASSET_A).signature, BASE, WINDOW)
