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
    r"^\s*(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"
)
_VEEAM_RAW_RE = re.compile(
    r"^\s*\[(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]"
)
_VEEAM_REPORT_RE = re.compile(
    r"^\s*(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s*[AP]M)",
    re.IGNORECASE,
)
_SYSLOG_RE = re.compile(r"^\s*([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})")


def _to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def parse_evidence_timestamp(line: str) -> Tuple[str, Optional[datetime], str]:
    """Parse a leading timestamp from one log line.

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
        core = re.sub(r"\.\d+$", "", raw)  # strip fractional seconds only
        try:
            return raw, datetime.strptime(core, "%d.%m.%Y %H:%M:%S"), "veeam_raw"
        except ValueError:
            pass
    m = _VEEAM_REPORT_RE.match(text)
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


def build_evidence_records(files: List[Tuple[str, str]]) -> List[EvidenceRecord]:
    """Build line records for (filename, text) inputs.  Line numbers are
    1-based within each file; record order is input order (callers sort)."""
    records: List[EvidenceRecord] = []
    for filename, text in files or []:
        for lineno, line in enumerate((text or "").splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            raw, key, kind = parse_evidence_timestamp(stripped)
            records.append(
                EvidenceRecord(
                    source_file=filename or "",
                    line_number=lineno,
                    raw_text=stripped[:500],
                    timestamp_raw=raw,
                    timestamp_key=key,
                    timestamp_kind=kind,
                )
            )
    return records


def order_records(records: List[EvidenceRecord]) -> List[EvidenceRecord]:
    """Deterministic time order across files.

    Timestamped records sort by (timestamp, source_file, line_number);
    untimestamped records follow in (source_file, line_number) order so no
    chronology is fabricated for them.  The key is a total order derived
    only from record content — never from input/upload order.
    """

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
    """Bounded line windows around anchors with overlaps merged."""
    spans: List[List[int]] = []
    for idx in sorted(set(anchor_idxs)):
        start = max(0, idx - radius)
        end = min(len(lines), idx + radius + 1)
        if spans and start <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], end)
        else:
            spans.append([start, end])
    return ["\n".join(lines[s:e]) for s, e in spans]


def diagnostic_local_context(
    records: List[EvidenceRecord],
    diagnostic_code: str,
    radius: int = KB_WINDOW_RADIUS_LINES,
) -> str:
    """Diagnostic-local evidence context from records.

    Windows stay inside one source file around anchor lines, so an
    operation in one file can never satisfy a gate with keywords from an
    unrelated file or attempt.  Returns "" when the code has no anchors or
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
        lines = [r.raw_text for r in file_recs]
        idxs = [i for i, ln in enumerate(lines) if any(rx.search(ln) for rx in compiled)]
        windows = window_texts(lines, idxs, radius)
        if not windows:
            continue
        # Preserve the file boundary with the same marker format that
        # split_file_segments parses, so downstream gates can never build
        # a window spanning two files.
        parts.append("===== FILE: %s =====" % (filename or "log"))
        parts.extend(windows)
    return "\n".join(parts)
