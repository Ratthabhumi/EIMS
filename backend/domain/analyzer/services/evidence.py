"""Normalized evidence records shared by chronology, correlation, and KB gating.

One transient structured representation (stdlib dataclass, no DB table) so
chronology, correlation, and vendor-article applicability consume the same
normalized records instead of independently rescanning arbitrary bundle text.

Timestamp policy (explicit, no invented timezones):
- Offset-aware ISO-8601 timestamps are normalized to UTC and stored naive.
- Local timestamps without offset (Veeam raw ``[dd.mm.yyyy]``, Veeam report
  ``M/D/YYYY h:mm:ss AM/PM``) are compared as wall-clock values.  They are
  treated as one local-clock domain (the Veeam environment local time);
  mixing them with offset-aware stamps is NOT done — such pairs are
  incomparable and fall back to deterministic (source_file, line_number)
  order instead of faking chronology.
- Unparseable timestamps retain source/line order; chronology is never
  fabricated for them.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Timestamp formats
# ---------------------------------------------------------------------------

_ISO_RE = re.compile(
    r"^\s*\[?(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"
)
_VEEAM_RAW_RE = re.compile(
    r"^\s*\[(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]"
)
_VEEAM_REPORT_RE = re.compile(
    r"^\s*(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s*[AP]M)",
    re.IGNORECASE,
)
_VEEAM_REPORT_TRAILING_RE = re.compile(
    r"\bat\s+(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s*[AP]M)\s*$",
    re.IGNORECASE,
)
_SYSLOG_RE = re.compile(r"^\s*([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})")


def _to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def parse_evidence_timestamp(line: str) -> Tuple[str, Optional[datetime], str]:
    """Parse an explicit leading timestamp or Veeam outcome's trailing time.

    Returns (timestamp_raw, timestamp_key, timestamp_kind).  timestamp_key
    is a naive datetime (UTC for offset-aware input) or None when the line
    carries no parseable timestamp.  timestamp_raw preserves the original
    text separately; no timezone is ever invented.
    """
    text = line or ""
    m = _ISO_RE.match(text)
    if m:
        raw = m.group(1)
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return raw, _to_naive_utc(parsed), "iso8601"
        except ValueError:
            pass
    m = _VEEAM_RAW_RE.match(text)
    if m:
        raw = m.group(1)
        try:
            fmt = "%d.%m.%Y %H:%M:%S.%f" if "." in raw.split()[-1] else "%d.%m.%Y %H:%M:%S"
            return raw, datetime.strptime(raw, fmt), "veeam_raw"
        except ValueError:
            pass
    m = _VEEAM_REPORT_RE.match(text) or _VEEAM_REPORT_TRAILING_RE.search(text)
    if m:
        raw = m.group(1)
        try:
            return raw, datetime.strptime(raw.strip().upper(), "%m/%d/%Y %I:%M:%S %p"), "veeam_report"
        except ValueError:
            pass
    m = _SYSLOG_RE.match(text)
    if m:
        raw = m.group(1)
        try:
            return raw, datetime.strptime(raw, "%b %d %H:%M:%S"), "syslog"
        except ValueError:
            pass
    return "", None, ""


def timestamp_domain(raw: str, kind: str) -> str:
    """Clock identity; a missing offset never implies UTC."""
    if not raw:
        return ""
    if kind == "syslog":
        return "syslog_year_unknown"
    if kind == "iso8601" and re.search(r"(?:Z|[+-]\d{2}:?\d{2})$", raw):
        return "utc"
    return "local"


# ---------------------------------------------------------------------------
# Evidence records
# ---------------------------------------------------------------------------


@dataclass
class EvidenceRecord:
    """One log line with file provenance and parsed time identity."""

    source_file: str
    line_number: int  # 1-based within source_file
    raw_text: str
    timestamp_raw: str = ""
    timestamp_key: Optional[datetime] = None
    timestamp_kind: str = ""
    severity: str = ""
    signal_strength: int = 0
    signatures: List[str] = field(default_factory=list)
    observed_paths: List[str] = field(default_factory=list)
    resource_paths: List[str] = field(default_factory=list)
    operation_tags: List[str] = field(default_factory=list)


def _retained_source_lines(lines: List[str], max_chars: int) -> set:
    """Retain compaction's header, signal windows and tail by ORIGINAL index.

    Header/tail take priority. Context windows use the remaining character
    budget. Full source lines are retained (no synthetic lines/duplicates).
    """
    from backend.domain.analyzer.services.compaction import (
        HEADER_CHARS, TAIL_CHARS, MAX_WINDOWS, WINDOW_RADIUS, _is_signal,
    )

    selected = set()
    for indexes, budget in ((range(len(lines)), HEADER_CHARS),
                            (range(len(lines) - 1, -1, -1), TAIL_CHARS)):
        used = 0
        for idx in indexes:
            selected.add(idx)
            used += len(lines[idx]) + 1
            if used >= budget:
                break
    used = sum(len(lines[i]) + 1 for i in selected)
    covered = set()
    windows = 0
    for idx, line in enumerate(lines):
        if not _is_signal(line):
            continue
        span = set(range(max(0, idx - WINDOW_RADIUS), min(len(lines), idx + WINDOW_RADIUS + 1)))
        if covered & span:
            continue
        covered.update(span)
        windows += 1
        additional = span - selected
        cost = sum(len(lines[i]) + 1 for i in additional)
        if used + cost <= max_chars:
            selected.update(additional)
            used += cost
        if windows >= MAX_WINDOWS:
            break
    return selected


def build_evidence_records(files: List[Tuple[str, str]], max_chars: Optional[int] = None) -> List[EvidenceRecord]:
    """Build line records for (filename, text) inputs.  Line numbers are
    1-based within each file; record order is input order (callers sort).
    Optional compaction budget selects original lines without renumbering.
    """
    records: List[EvidenceRecord] = []
    for filename, text in files or []:
        lines = (text or "").splitlines()
        selected = _retained_source_lines(lines, max_chars) if max_chars and len(text or "") > max_chars else None
        for lineno, line in enumerate(lines, start=1):
            if selected is not None and lineno - 1 not in selected:
                continue
            stripped = line.strip()
            if not stripped:
                continue
            raw, key, kind = parse_evidence_timestamp(line)
            records.append(
                EvidenceRecord(
                    source_file=filename or "",
                    line_number=lineno,
                    raw_text=line,
                    timestamp_raw=raw,
                    timestamp_key=key,
                    timestamp_kind=kind,
                )
            )
    return records


def order_records(records: List[EvidenceRecord]) -> List[EvidenceRecord]:
    """Deterministic time order across files.

    Within one clock domain records sort by (timestamp, source_file, line_number);
    untimestamped records follow in (source_file, line_number) order so no
    chronology is fabricated for them. Mixed domains use source/line order
    for the entire set. The key is a total order derived
    only from record content — never from input/upload order.
    """

    domains = {timestamp_domain(r.timestamp_raw, r.timestamp_kind)
               for r in records if r.timestamp_key is not None}
    if len(domains) > 1:
        return sorted(records, key=lambda r: (r.source_file or "", r.line_number))

    def _key(rec: EvidenceRecord):
        if rec.timestamp_key is not None:
            return (0, rec.timestamp_key, rec.source_file or "", rec.line_number)
        return (1, datetime.max, rec.source_file or "", rec.line_number)

    return sorted(records, key=_key)


# ---------------------------------------------------------------------------
# Bundle file segments (upload-order-independent locality)
# ---------------------------------------------------------------------------

_FILE_SPLIT_RE = re.compile(r"^===== FILE:\s*(.*?)\s*=====\s*$", re.MULTILINE)


def split_file_segments(text: str) -> List[Tuple[Optional[str], str]]:
    """Split bundle combined_text into (filename, segment) pairs.

    Text without FILE markers yields a single (None, text) segment, so
    single-file behavior is unchanged.
    """
    matches = list(_FILE_SPLIT_RE.finditer(text or ""))
    if not matches:
        return [(None, text or "")]
    segments: List[Tuple[Optional[str], str]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text or "")
        segments.append((match.group(1) or None, (text or "")[start:end]))
    return segments


# ---------------------------------------------------------------------------
# Operation anchors + local diagnostic context
# ---------------------------------------------------------------------------

#: Broad anchor signals per diagnostic family.  Anchors are intentionally
#: broad — the precise article gates decide applicability on the window.
_ANCHOR_RES: Dict[str, Tuple[str, ...]] = {
    "VMWARE-CBT-DELETE-FAILED": (
        r"could not delete change tracking file",
        r"ctk_ctkunlink",
        r"result\s*:?\s*2620",
    ),
    "VMWARE-SNAPSHOT-FILE-MISSING": (
        r"a required file",
        r"not found",
        r"invalidsnapshotformat",
        r"invalid snapshot",
        r"revertsnapshot",
        r"createsnapshot",
        r"create snapshot",
        r"delet",
        r"consolidat",
        r"renam",
        r"folder",
        r"vvol",
        r"vsan",
    ),
    "VEEAM-REPLICA-SNAPSHOT-CHAIN": (
        r"a required file",
        r"not found",
        r"invalidsnapshotformat",
        r"invalid snapshot",
        r"revertsnapshot",
        r"could not delete change tracking file",
        r"deleting helper snapshot",
        r"snapshot consolidation",
        r"vvol",
        r"vsan",
    ),
}

#: Per-article anchor signals for bounded operation windows.  Environment
#: articles (442155/411756/418256) are evaluated per file segment instead.
_ARTICLE_ANCHOR_RES: Dict[str, Tuple[str, ...]] = {
    "424591": (
        r"required file",
        r"not found",
        r"invalidsnapshotformat",
        r"invalid snapshot",
        r"revert",
    ),
    "318905": (
        r"invalidsnapshotformat",
        r"invalid snapshot",
        r"createsnapshot",
        r"create snapshot",
        r"creating a snapshot",
        r"creating snapshot",
    ),
    "450780": (
        r"required file",
        r"not found",
        r"delet",
        r"consolidat",
        r"remov",
        r"snapshot",
    ),
    "452165": (
        r"required file",
        r"not found",
        r"renam",
        r"folder",
        r"path mismatch",
        r"move",
        r"moved",
        r"moving",
    ),
}

KB_WINDOW_RADIUS_LINES = 15


def _compile_anchor_res(patterns) -> List[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def anchor_line_indexes(lines: List[str], patterns) -> List[int]:
    """Line indexes matching any anchor pattern (case-insensitive)."""
    compiled = _compile_anchor_res(patterns)
    return [i for i, ln in enumerate(lines) if any(rx.search(ln) for rx in compiled)]


def window_texts(lines: List[str], anchor_idxs: List[int], radius: int = KB_WINDOW_RADIUS_LINES) -> List[str]:
    """Fixed bounded windows; overlapping anchors never grow a window."""
    spans = []
    seen = set()
    for idx in sorted(set(anchor_idxs)):
        start = max(0, idx - radius)
        end = min(len(lines), idx + radius + 1)
        if (start, end) not in seen:
            spans.append((start, end))
            seen.add((start, end))
    return ["\n".join(lines[s:e]) for s, e in spans]


_SESSION_RE = re.compile(
    r"\b(job(?:session)?id|task(?:session)?id)\s*[:=]\s*['\"]?([\w-]+)|"
    r"\b(task|job)\s+session\s+['\"]([^'\"]+)['\"]", re.IGNORECASE,
)
_OPERATION_RES = (
    ("revert", re.compile(r"revertsnapshot|revert.*snapshot|snapshot.*revert", re.I)),
    ("create", re.compile(r"createsnapshot|creat(?:e|ing)\s+(?:a\s+|helper\s+)?snapshot", re.I)),
    ("delete", re.compile(r"delet(?:e|ing|ion).*snapshot|snapshot.*(?:delet|consolidat)|consolidat.*snapshot", re.I)),
    ("manual_move", re.compile(r"manual(?:ly)?.*(?:renam|\bmov)|path mismatch", re.I)),
)


def operation_segments(records: List[EvidenceRecord]) -> List[List[EvidenceRecord]]:
    """Partition by source gaps, clock/time, session, and explicit operation.

    Untimed continuation lines stay with their operation. A date change,
    clock-domain change, >5 minute gap, new typed session, or different
    operation closes it. Missing evidence never joins disjoint windows.
    """
    segments = []
    current = []
    last_time = None
    last_domain = ""
    sessions = {}
    operation = ""
    previous = None
    for rec in sorted(records, key=lambda r: (r.source_file, r.line_number)):
        domain = timestamp_domain(rec.timestamp_raw, rec.timestamp_kind)
        observed_sessions = {}
        for match in _SESSION_RE.finditer(rec.raw_text):
            if match.group(1):
                observed_sessions[match.group(1).lower()] = match.group(2)
            else:
                observed_sessions[match.group(3).lower() + "sessionid"] = match.group(4)
        operations = {name for name, rx in _OPERATION_RES if rx.search(rec.raw_text)}
        next_operation = next(iter(operations)) if len(operations) == 1 else ""
        boundary = previous is not None and (
            rec.source_file != previous.source_file
            or rec.line_number - previous.line_number > KB_WINDOW_RADIUS_LINES
            or any(k in sessions and sessions[k] != v for k, v in observed_sessions.items())
            or bool(operation and next_operation and operation != next_operation)
        )
        if rec.timestamp_key is not None and last_time is not None:
            boundary = boundary or domain != last_domain or rec.timestamp_key.date() != last_time.date()
            boundary = boundary or abs((rec.timestamp_key - last_time).total_seconds()) > 300
        if boundary:
            if current:
                segments.append(current)
            current, last_time, last_domain, sessions, operation = [], None, "", {}, ""
        current.append(rec)
        sessions.update(observed_sessions)
        operation = next_operation or operation
        if rec.timestamp_key is not None:
            last_time, last_domain = rec.timestamp_key, domain
        previous = rec
    if current:
        segments.append(current)
    return segments


def diagnostic_local_context(
    records: List[EvidenceRecord],
    diagnostic_code: str,
    radius: int = KB_WINDOW_RADIUS_LINES,
) -> str:
    """Diagnostic-local evidence context from records.

    Windows stay inside one source file around anchor lines, so an
    operation can never satisfy a gate with keywords from an unrelated
    partition/window. Returns "" when the code has no anchors or
    no anchor line exists (callers fall back to the full evidence text).
    """
    patterns = _ANCHOR_RES.get((diagnostic_code or "").strip())
    if not patterns:
        return ""
    compiled = _compile_anchor_res(patterns)
    by_file: Dict[str, List[EvidenceRecord]] = {}
    for rec in records or []:
        by_file.setdefault(rec.source_file or "", []).append(rec)
    parts: List[str] = []
    for filename in sorted(by_file):
        file_recs = sorted(by_file[filename], key=lambda r: r.line_number)
        for segment in operation_segments(file_recs):
            lines = [r.raw_text for r in segment]
            idxs = [i for i, ln in enumerate(lines) if any(rx.search(ln) for rx in compiled)]
            for window in window_texts(lines, idxs, radius):
                # Every window has its own boundary, including disjoint
                # windows from the same file. Downstream re-windowing is safe.
                parts.append("===== FILE: %s =====" % (filename or "log"))
                parts.append(window)
    return "\n".join(parts)
