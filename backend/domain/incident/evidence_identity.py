"""Durable evidence identity for Incident Core (pure functions, no I/O).

An evidence reference points at a *source record* (e.g. analysis_history.id). That id alone cannot tell whether two
records describe the same real event (the same file submitted twice) or different events with similar text. This
module derives:

* ``event_key``  - the correlation identity: ``<event id>[@<normalised provider>]``. The provider is part of the
  identity because the same Event ID means different things for different providers (1000, 1001, 1026, ...).
* ``fingerprint`` - a SHA-256 identity of the *event occurrence*. It is only produced when the source carries at least
  one occurrence-distinguishing field (record id or event time). Display text alone is never an identity: without a
  distinguishing field no fingerprint is produced and the record keeps its own source identity, so two events with
  identical text are never collapsed on text alone.

Strength vocabulary: ``occurrence`` (fingerprint produced) or ``source_only`` (no fingerprint).
"""
from __future__ import annotations

import hashlib
import re

_UNSPECIFIED = {"", "unknown", "none", "n/a", "-", "null"}


def norm(value) -> str:
    """Casefolded, whitespace-collapsed text; '' for unspecified placeholders."""
    text = re.sub(r"\s+", " ", str(value if value is not None else "")).strip().casefold()
    return "" if text in _UNSPECIFIED else text


def build_event_key(event_id, provider, caller_key: str | None = None) -> str | None:
    """``<event identity>[@<provider>]`` or None when no event identity is known."""
    base = (caller_key or "").strip() or str(event_id or "").strip()
    if not norm(base):
        return None
    if "@" in base:  # already qualified by the caller
        return base[:160]
    provider_key = norm(provider)
    key = f"{base}@{provider_key}" if provider_key else base
    return key[:160]


def message_hash(text) -> str:
    return hashlib.sha256(norm(text).encode("utf-8")).hexdigest()


def event_fingerprint(*, family="", provider="", event_id="", record_id="", occurred="", channel="",
                      computer="", message="") -> tuple[str | None, str]:
    """Return (digest, strength). No digest unless record id or event time distinguishes the occurrence."""
    record, when = norm(record_id), norm(occurred)
    if not record and not when:
        return None, "source_only"
    parts = {
        "family": norm(family), "provider": norm(provider), "event_id": norm(event_id), "record_id": record,
        "occurred": when, "channel": norm(channel), "computer": norm(computer), "message": message_hash(message),
    }
    material = "|".join(f"{k}={v or '-'}" for k, v in parts.items())
    return hashlib.sha256(material.encode("utf-8")).hexdigest(), "occurrence"


def analysis_fields(row) -> dict:
    """Identity-relevant fields of a persisted analysis_history row (shared by enrichment and verification)."""
    meta = row.event_metadata if isinstance(getattr(row, "event_metadata", None), dict) else {}
    attrs = meta.get("attributes") if isinstance(meta.get("attributes"), dict) else {}
    return {
        "event_id": getattr(row, "event_id", None) or meta.get("eventId"),
        "provider": getattr(row, "provider", None) or meta.get("provider"),
        "record_id": meta.get("record_id") or attrs.get("recordId") or attrs.get("eventRecordId"),
        "occurred": meta.get("occurrence_time") or meta.get("timestamp"),
        "family": meta.get("sourceFamily") or meta.get("source_type") or "",
        "channel": meta.get("logName") or meta.get("channel") or "",
        "computer": meta.get("computer") or "",
        "time_source": attrs.get("timeSource") or "",
        "timezone": meta.get("timezone") or meta.get("utcOffset") or attrs.get("timezone") or attrs.get("utcOffset") or "",
        "message": getattr(row, "description", None) or "",
    }


def analysis_fingerprint(row) -> str | None:
    """Occurrence fingerprint of an analysis row, or None when no record id / event time distinguishes it."""
    f = analysis_fields(row)
    from datetime import UTC, datetime
    from backend.domain.incident.event_time import parse_event_time
    # Coarse or ambiguous time text ("10:00:00", "2026-11-20") cannot distinguish occurrences across days.
    parsed = parse_event_time(f["occurred"], declared_zone=f.get("timezone"), now=datetime(9999, 1, 1, tzinfo=UTC))
    # A complete date+time string identifies an occurrence by equality even when its zone is unknown (identity is not
    # correlation); time-of-day-only, date-only and malformed text never do.
    full_stamp = parsed.event_time is not None or parsed.basis in {"local_time_without_zone", "local_time_day_month_order_unclear"}
    f["occurred"] = f["occurred"] if full_stamp else ""
    digest, _strength = event_fingerprint(
        family=f["family"], provider=f["provider"], event_id=f["event_id"], record_id=f["record_id"],
        occurred=f["occurred"], channel=f["channel"], computer=f["computer"], message=f["message"])
    return digest
