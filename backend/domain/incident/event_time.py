"""Event-time semantics for Incident correlation (pure functions, no I/O).

Three different clocks must never be confused:

* ``event_time``  - when the event occurred, parsed ONLY from a structured source field whose semantics are known.
* ``ingested_at`` - when EIMS received the evidence (``incident_evidence.created_at``). Never an event time.
* ``observed_at`` - legacy/caller-supplied observation timestamp. Kept for compatibility, not trusted for correlation.

``time_basis`` records where the selected event time came from and ``time_confidence`` how far it can be trusted:

``exact``      explicit UTC/offset in the source, or a local time with an explicitly declared zone.
``asserted``   a structured timestamp supplied by an authenticated collector through the API (no source text to check).
``ambiguous``  a time exists but cannot be placed on the UTC axis (local time without zone, day/month order unclear,
               timestamp in the future beyond clock skew, time-of-day without a date).
``missing``    no timestamp, or it is malformed.

Only ``exact`` and ``asserted`` event times take part in correlation windows. No zone is ever guessed and a date is
never inferred from a time-of-day.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

CORRELATION_ELIGIBLE = frozenset({"exact", "asserted"})
MAX_FUTURE_SKEW = timedelta(minutes=5)

_ISO = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})[T ](?P<time>\d{2}:\d{2}:\d{2})(?:[.,](?P<frac>\d{1,9}))?"
    r"\s*(?P<zone>Z|[+-]\d{2}:?\d{2}|UTC|GMT)?$", re.IGNORECASE)
_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LOCAL_US = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}[ ,]+\d{1,2}:\d{2}(:\d{2})?\s*([AP]M)?$", re.IGNORECASE)
_TIME_ONLY = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?(\s*[AP]M)?$", re.IGNORECASE)
_OFFSET = re.compile(r"^(?P<sign>[+-])(?P<h>\d{2}):?(?P<m>\d{2})$")


@dataclass(frozen=True)
class EventTime:
    event_time: datetime | None
    basis: str
    confidence: str
    original: str | None

    @property
    def eligible(self) -> bool:
        return self.event_time is not None and self.confidence in CORRELATION_ELIGIBLE


def _zone(declared: str | None):
    """tzinfo for an explicitly declared zone ('UTC', '+07:00', 'Asia/Bangkok'); None when absent or unusable."""
    value = (declared or "").strip()
    if not value:
        return None
    if value.upper() in {"UTC", "Z", "GMT"}:
        return UTC
    match = _OFFSET.match(value)
    if match:
        if int(match["h"]) > 23 or int(match["m"]) > 59:
            return None
        delta = timedelta(hours=int(match["h"]), minutes=int(match["m"]))
        return timezone(delta if match["sign"] == "+" else -delta)
    try:
        return ZoneInfo(value)
    except Exception:  # noqa: BLE001 - unknown zone name: treated as not declared
        return None


def parse_event_time(raw, *, declared_zone: str | None = None, now: datetime | None = None) -> EventTime:
    """Classify a source timestamp. ``declared_zone`` must come from structured source metadata, never be guessed."""
    if isinstance(raw, datetime):
        if raw.tzinfo is None or raw.utcoffset() is None:
            zone = _zone(declared_zone)
            if zone is None:
                return EventTime(None, "naive_datetime_without_zone", "ambiguous", raw.isoformat())
            return _finish(raw.replace(tzinfo=zone), "source_local_with_declared_zone", raw.isoformat(), now)
        return _finish(raw, "source_datetime_with_offset", raw.isoformat(), now)

    text = str(raw).strip() if raw is not None else ""
    if not text or text.casefold() in {"none", "null", "unknown", "n/a", "-"}:
        return EventTime(None, "no_timestamp", "missing", None)

    match = _ISO.match(text)
    if match:
        frac = (match["frac"] or "")[:6].ljust(6, "0")
        try:
            naive = datetime.strptime(f"{match['date']} {match['time']}.{frac}", "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            return EventTime(None, "malformed_timestamp", "missing", text)
        zone_text = match["zone"]
        if zone_text:
            explicit = _zone(zone_text)
            if explicit is None:  # an impossible offset such as +99:99
                return EventTime(None, "malformed_timestamp", "missing", text[:200])
            return _finish(naive.replace(tzinfo=explicit), "source_timestamp_explicit_zone", text, now)
        zone = _zone(declared_zone)
        if zone is not None:
            return _finish(naive.replace(tzinfo=zone), "source_local_with_declared_zone", text, now)
        return EventTime(None, "local_time_without_zone", "ambiguous", text)

    if _DATE_ONLY.match(text):
        return EventTime(None, "date_without_time", "ambiguous", text)
    if _TIME_ONLY.match(text):
        return EventTime(None, "time_of_day_without_date", "ambiguous", text)
    if _LOCAL_US.match(text):
        return EventTime(None, "local_time_day_month_order_unclear", "ambiguous", text)
    return EventTime(None, "malformed_timestamp", "missing", text[:200])


def _dst_problem(value: datetime) -> str | None:
    """'ambiguous' (clocks repeated) or 'nonexistent' (clocks skipped) for a wall time in a zoneinfo zone, else None."""
    zone = value.tzinfo
    if not isinstance(zone, ZoneInfo):
        return None
    first, second = value.replace(fold=0), value.replace(fold=1)
    wall = value.replace(tzinfo=None)
    if first.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != wall:
        return "nonexistent_dst_gap"  # checked first: in a gap the two folds also differ
    if first.utcoffset() != second.utcoffset():
        return "ambiguous_dst_overlap"
    return None


def _finish(value: datetime, basis: str, original: str, now: datetime | None) -> EventTime:
    problem = _dst_problem(value) if basis == "source_local_with_declared_zone" else None
    if problem:  # never pick a side of a DST fold and never accept a wall time that did not exist
        return EventTime(None, "local_time_" + problem, "ambiguous", original)
    utc = value.astimezone(UTC)
    reference = now or datetime.now(UTC)
    if utc > reference + MAX_FUTURE_SKEW:
        return EventTime(None, "timestamp_in_the_future", "ambiguous", original)
    return EventTime(utc, basis, "exact", original)


def asserted_event_time(value: datetime | None, original: str | None = None) -> EventTime:
    """A structured timestamp supplied by an authenticated collector (no source text available to verify)."""
    if value is None:
        return EventTime(None, "no_timestamp", "missing", original)
    if value.tzinfo is None or value.utcoffset() is None:
        return EventTime(None, "naive_datetime_without_zone", "ambiguous", original or value.isoformat())
    return EventTime(value.astimezone(UTC), "caller_supplied_structured_timestamp", "asserted",
                     original or value.isoformat())
