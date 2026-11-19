"""Typed, bounded, reference-only envelope shared by the dispatcher and consumer."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping

from backend.domain.incident_ingest.models import MAX_PROVENANCE_BYTES, OUTBOX_SOURCE_TYPES

# Redis keys live under the approved ``eims:jobs:`` prefix (cache.py _validate_namespace),
# next to the EVTX job stream. They are deliberately separate from eims:events:alerts*.
INGEST_STREAM_KEY = "eims:jobs:incident-ingest:stream"
INGEST_GROUP = "eims:jobs:incident-ingest:workers"
INGEST_DEAD_LETTER_KEY = "eims:jobs:incident-ingest:dead-letter"
INGEST_ACTOR = "system:incident-ingest"

SOURCE_ID_MAX = 64
SOURCE_EVENT_KEY_MAX = 160
MAX_FIELD_CHARS = 2048
QUALIFYING_WINLOG_SEVERITIES = frozenset({"critical", "error", "warning"})
# Only these provenance keys are ever stored/forwarded; values are short scalars (never log text).
PROVENANCE_KEYS = frozenset({"origin", "event_id", "severity"})
_PROVENANCE_VALUE_MAX = 64


class EnvelopeError(ValueError):
    """The stream entry is not a valid ingest envelope (deterministic poison)."""


def qualifies_winlog_severity(severity: object) -> bool:
    return isinstance(severity, str) and severity.strip().lower() in QUALIFYING_WINLOG_SEVERITIES


def sanitize_provenance(provenance: Mapping[str, Any] | None) -> dict[str, Any]:
    """Allow-listed, size-bounded provenance. Unknown keys and non-scalars are dropped."""
    clean: dict[str, Any] = {}
    for key, value in (provenance or {}).items():
        if key not in PROVENANCE_KEYS or value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            continue
        clean[key] = value[:_PROVENANCE_VALUE_MAX] if isinstance(value, str) else value
    if len(json.dumps(clean, sort_keys=True)) > MAX_PROVENANCE_BYTES:
        raise EnvelopeError("provenance exceeds bound")
    return clean


def to_utc(value: datetime) -> datetime:
    """Naive values are legacy UTC-naive (analysis_history.created_at); aware values are converted."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_uuid(raw: str | None, name: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(raw))
    except (ValueError, AttributeError, TypeError):
        raise EnvelopeError(f"{name} is not a UUID") from None


@dataclass(frozen=True)
class IngestEnvelope:
    outbox_id: uuid.UUID
    source_type: str
    source_id: str
    observed_at: datetime
    source_event_key: str | None = None
    asset_id: uuid.UUID | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source_type not in OUTBOX_SOURCE_TYPES:
            raise EnvelopeError("unsupported source_type")
        if not self.source_id or not self.source_id.strip() or len(self.source_id) > SOURCE_ID_MAX:
            raise EnvelopeError("invalid source_id")
        if self.source_event_key is not None and (
                not self.source_event_key or len(self.source_event_key) > SOURCE_EVENT_KEY_MAX):
            raise EnvelopeError("invalid source_event_key")
        if self.observed_at.tzinfo is None:
            raise EnvelopeError("observed_at must be timezone-aware")

    def to_stream_fields(self) -> dict[str, str]:
        fields = {
            "outbox_id": str(self.outbox_id), "source_type": self.source_type,
            "source_id": self.source_id, "observed_at": to_utc(self.observed_at).isoformat(),
            "provenance": json.dumps(self.provenance, sort_keys=True),
        }
        if self.source_event_key is not None:
            fields["source_event_key"] = self.source_event_key
        if self.asset_id is not None:
            fields["asset_id"] = str(self.asset_id)
        return fields

    @classmethod
    def from_stream_fields(cls, fields: Mapping[str, str]) -> IngestEnvelope:
        for name, value in fields.items():
            if not isinstance(value, str) or len(value) > MAX_FIELD_CHARS:
                raise EnvelopeError(f"field {str(name)[:32]} is invalid or oversized")
        try:
            observed = datetime.fromisoformat(fields.get("observed_at", ""))
        except (ValueError, TypeError):
            raise EnvelopeError("observed_at is not ISO-8601") from None
        try:
            provenance = json.loads(fields.get("provenance") or "{}")
        except json.JSONDecodeError:
            raise EnvelopeError("provenance is not JSON") from None
        if not isinstance(provenance, dict):
            raise EnvelopeError("provenance must be an object")
        asset_raw = fields.get("asset_id")
        return cls(
            outbox_id=_parse_uuid(fields.get("outbox_id"), "outbox_id"),
            source_type=fields.get("source_type", ""),
            source_id=fields.get("source_id", ""),
            observed_at=observed,
            source_event_key=fields.get("source_event_key") or None,
            asset_id=_parse_uuid(asset_raw, "asset_id") if asset_raw else None,
            provenance=sanitize_provenance(provenance),
        )
