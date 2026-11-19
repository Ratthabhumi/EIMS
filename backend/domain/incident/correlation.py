"""
==============================================================================
EIMS Incident Correlation - deterministic, pure classification (v1)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 4 Compliance
Source-Available All Rights Reserved Policy
==============================================================================

This module contains no I/O and no randomness. Every decision is a pure
function of (asset identity, source identity, observed time, configured
window). It deliberately does NOT reuse the analyzer's 300 s bundle file
epsilon: incident correlation uses an explicit, configurable window.

Confidence vocabulary:
  strong - same concrete asset AND same signature within the window
  medium - same concrete asset within the window with a differing signature,
           OR same signature within the window while asset identity is unresolved
  weak   - same signature inside the expanded (2x) window, or explicit
           single-source evidence
  none   - everything else, including any pair of different concrete assets

Confidence is correlation evidence, never a causal assertion.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

DEFAULT_WINDOW_SECONDS = 900
EXPANDED_WINDOW_MULTIPLIER = 2

CONFIDENCE_STRONG = "strong"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_WEAK = "weak"
CONFIDENCE_NONE = "none"

CONFIDENCE_RANK = {
    CONFIDENCE_NONE: 0,
    CONFIDENCE_WEAK: 1,
    CONFIDENCE_MEDIUM: 2,
    CONFIDENCE_STRONG: 3,
}

UNRESOLVED_ASSET_TOKEN = "unresolved"


def normalize_observed_at(value: datetime) -> datetime:
    """Coerces a datetime to timezone-aware UTC.

    Naive values are interpreted as UTC rather than guessed local time, matching
    the stored column contract and keeping classification deterministic.
    """
    if not isinstance(value, datetime):
        raise TypeError("observed_at must be a datetime")
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def normalize_signature(source_type: str, event_identity: str) -> str:
    """Builds the canonical signature for an evidence item.

    The signature is `<source_type>:<event identity>` with surrounding
    whitespace removed and case folded, so the same event cannot fragment into
    two signatures because of presentation differences.
    """
    source = (source_type or "").strip().lower()
    identity = (event_identity or "").strip().casefold()
    if not source:
        raise ValueError("source_type is required to build a signature")
    if not identity:
        raise ValueError("event identity is required to build a signature")
    return f"{source}:{identity}"


def asset_token(asset_id: uuid.UUID | None) -> str:
    """Returns the canonical asset component of the dedupe material."""
    return str(asset_id) if asset_id is not None else UNRESOLVED_ASSET_TOKEN


def window_bucket(observed_at: datetime, window_seconds: int = DEFAULT_WINDOW_SECONDS) -> int:
    """Returns the deterministic floor bucket for an observation time."""
    seconds = max(int(window_seconds), 1)
    return int(normalize_observed_at(observed_at).timestamp() // seconds)


def build_dedupe_key(
    asset_id: uuid.UUID | None,
    signature: str,
    observed_at: datetime,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
) -> str:
    """SHA-256 of `asset-or-unresolved:signature:window_bucket`.

    Deterministic and free of random input; the same tuple always produces the
    same key, which is what makes the service upsert idempotent.
    """
    material = f"{asset_token(asset_id)}:{signature}:{window_bucket(observed_at, window_seconds)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_evidence_digest(source_type: str, source_id: str, observed_at: datetime) -> str:
    """SHA-256 of the source identity and observation time (never the payload)."""
    moment = normalize_observed_at(observed_at).isoformat()
    material = f"{source_type.strip().lower()}:{source_id.strip()}:{moment}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CorrelationInput:
    """Minimal identity of one evidence item used for classification."""
    asset_id: uuid.UUID | None
    source_type: str
    source_id: str
    signature: str
    observed_at: datetime

    @property
    def source_label(self) -> str:
        return f"{self.source_type}:{self.source_id}"


@dataclass(frozen=True)
class CorrelationAssessment:
    """Pure classification result persisted into incidents.summary['correlation']."""
    confidence: str
    reasons: tuple[str, ...]
    sources: tuple[str, ...]
    window_seconds: int
    window_bucket: int
    dedupe_key: str
    asset_key: str

    @property
    def mergeable(self) -> bool:
        """Evidence is grouped while any positive correlation exists."""
        return self.confidence != CONFIDENCE_NONE

    def as_summary(self, signature: str, asset_id: uuid.UUID | None) -> dict:
        """Serialises the bounded correlation block stored on the incident."""
        return {
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "sources": list(self.sources),
            "signature": signature,
            "window_seconds": self.window_seconds,
            "window_bucket": self.window_bucket,
            "asset_state": "resolved" if asset_id is not None else UNRESOLVED_ASSET_TOKEN,
        }


def _reasons_for(
    *,
    same_asset: bool,
    unresolved_asset: bool,
    different_assets: bool,
    same_signature: bool,
    within_window: bool,
    within_expanded_window: bool,
    single_source: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if different_assets:
        reasons.append("different_asset_ids")
    elif same_asset:
        reasons.append("same_asset_id")
    elif unresolved_asset:
        reasons.append("asset_unresolved")
    reasons.append("same_signature" if same_signature else "different_signature")
    if within_window:
        reasons.append("within_window")
    elif within_expanded_window:
        reasons.append("within_expanded_window")
    else:
        reasons.append("outside_expanded_window")
    if single_source:
        reasons.append("single_source_evidence")
    return tuple(reasons)


def classify(
    candidate: CorrelationInput,
    existing: CorrelationInput,
    *,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    single_source: bool = False,
) -> CorrelationAssessment:
    """Classifies one evidence item against one existing evidence identity.

    Never returns a mergeable result for two different concrete assets. Missing
    asset identity stays explicit in `reasons` and is not guessed.
    """
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")

    candidate_time = normalize_observed_at(candidate.observed_at)
    existing_time = normalize_observed_at(existing.observed_at)
    delta_seconds = abs((candidate_time - existing_time).total_seconds())

    different_assets = (
        candidate.asset_id is not None
        and existing.asset_id is not None
        and candidate.asset_id != existing.asset_id
    )
    same_asset = (
        candidate.asset_id is not None
        and existing.asset_id is not None
        and candidate.asset_id == existing.asset_id
    )
    unresolved_asset = candidate.asset_id is None or existing.asset_id is None
    same_signature = candidate.signature == existing.signature
    within_window = delta_seconds <= window_seconds
    within_expanded = delta_seconds <= window_seconds * EXPANDED_WINDOW_MULTIPLIER

    if different_assets:
        confidence = CONFIDENCE_NONE
    elif same_asset and same_signature and within_window:
        confidence = CONFIDENCE_STRONG
    elif same_asset and within_window:
        confidence = CONFIDENCE_MEDIUM
    elif same_signature and within_window and unresolved_asset:
        confidence = CONFIDENCE_MEDIUM
    elif same_signature and within_expanded:
        confidence = CONFIDENCE_WEAK
    elif single_source:
        confidence = CONFIDENCE_WEAK
    else:
        confidence = CONFIDENCE_NONE

    reasons = _reasons_for(
        same_asset=same_asset,
        unresolved_asset=unresolved_asset,
        different_assets=different_assets,
        same_signature=same_signature,
        within_window=within_window,
        within_expanded_window=within_expanded,
        single_source=single_source,
    )
    return CorrelationAssessment(
        confidence=confidence,
        reasons=reasons,
        sources=(existing.source_label, candidate.source_label),
        window_seconds=int(window_seconds),
        window_bucket=window_bucket(candidate_time, window_seconds),
        dedupe_key=build_dedupe_key(
            candidate.asset_id, candidate.signature, candidate_time, window_seconds
        ),
        asset_key=asset_token(candidate.asset_id),
    )
