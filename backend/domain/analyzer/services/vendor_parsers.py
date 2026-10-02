"""Deterministic Veeam / VMware adapters for the canonical EIMS Analyzer.

Only stdlib is used (``re`` + ``html.parser``).  No network, no ML.

Diagnostic codes are stable product-specific identities stored in the
existing string ``event_id`` field (no migration):

- ``VEEAM-REPLICA-SNAPSHOT-CHAIN`` — replication reached snapshot
  cleanup/revert and the replica snapshot chain is unhealthy.
- ``VMWARE-CBT-DELETE-FAILED`` — "Could not delete change tracking file".
- ``VMWARE-SNAPSHOT-FILE-MISSING`` — InvalidSnapshotFormat + a required
  file was not found.

Causality discipline: the extractor reports an *observed sequence*
(first failure -> later terminal failure).  It never asserts the first
failure caused the second unless the evidence proves it.
"""

import re
from html.parser import HTMLParser
from typing import Dict, List, Optional

from backend.domain.analyzer.schemas.analyze import EventMetadata

# ---------------------------------------------------------------------------
# Diagnostic codes
# ---------------------------------------------------------------------------

DIAG_VEEAM_REPLICA_SNAPSHOT_CHAIN = "VEEAM-REPLICA-SNAPSHOT-CHAIN"
DIAG_VMWARE_CBT_DELETE_FAILED = "VMWARE-CBT-DELETE-FAILED"
DIAG_VMWARE_SNAPSHOT_FILE_MISSING = "VMWARE-SNAPSHOT-FILE-MISSING"

VENDOR_DIAGNOSTIC_CODES = (
    DIAG_VEEAM_REPLICA_SNAPSHOT_CHAIN,
    DIAG_VMWARE_CBT_DELETE_FAILED,
    DIAG_VMWARE_SNAPSHOT_FILE_MISSING,
)


def is_vendor_diagnostic_code(value: Optional[str]) -> bool:
    return str(value or "") in VENDOR_DIAGNOSTIC_CODES


# ---------------------------------------------------------------------------
# Signal patterns (lowercased input)
# ---------------------------------------------------------------------------

_SIG_CBT_DELETE = "could not delete change tracking file"
_SIG_INVALID_SNAPSHOT = "invalidsnapshotformat"
_SIG_REQUIRED_FILE = "a required file was not found"
_SIG_INVALID_CONFIG = "invalid snapshot configuration"
_SIG_HELPER_SNAPSHOT = "deleting helper snapshot"
_SIG_REVERT = "revertsnapshot"
_SIG_REPLICA = ("replica", "replication")
_RESULT_2620 = "2620"

_VEEAM_PRODUCT = "Veeam Backup & Replication"
_VMWARE_PRODUCT = "VMware vSphere/ESXi"


def resolve_vendor_diagnostic(text: str, source_family: str) -> str:
    """Return the best stable diagnostic code, or "" when unrecognized."""
    lowered = (text or "").lower()
    has_cbt = _SIG_CBT_DELETE in lowered
    has_invalid = _SIG_INVALID_SNAPSHOT in lowered
    has_missing = _SIG_REQUIRED_FILE in lowered
    has_bad_config = _SIG_INVALID_CONFIG in lowered
    has_helper = _SIG_HELPER_SNAPSHOT in lowered
    has_revert = _SIG_REVERT in lowered
    has_replica = any(k in lowered for k in _SIG_REPLICA)

    if source_family == "veeam_vbr":
        if (has_revert or has_helper or has_bad_config) and (
            has_invalid or has_missing or has_bad_config
        ):
            return DIAG_VEEAM_REPLICA_SNAPSHOT_CHAIN
        if has_cbt:
            return DIAG_VMWARE_CBT_DELETE_FAILED
        if has_invalid and has_missing:
            return DIAG_VMWARE_SNAPSHOT_FILE_MISSING
        return ""
    if source_family == "vmware":
        if has_cbt:
            return DIAG_VMWARE_CBT_DELETE_FAILED
        if has_invalid and has_missing:
            return DIAG_VMWARE_SNAPSHOT_FILE_MISSING
        return ""
    return ""


# ---------------------------------------------------------------------------
# stdlib HTML -> text (script/style skipped, no JS execution)
# ---------------------------------------------------------------------------


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: List[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        elif tag in ("br", "p", "tr", "div", "li", "h1", "h2", "h3", "h4"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
        elif tag in ("p", "tr", "div", "li", "h1", "h2", "h3", "h4", "table"):
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def text(self) -> str:
        collapsed = re.sub(r"[ \t\xa0]+", " ", "".join(self._parts))
        collapsed = re.sub(r"\n\s*\n+", "\n", collapsed)
        return collapsed.strip()


def html_to_text(html: str) -> str:
    """Best-effort HTML report -> plain text using only stdlib."""
    if not html:
        return ""
    extractor = _TextExtractor()
    try:
        extractor.feed(html)
        extractor.close()
    except Exception:
        # Fall back to tag stripping rather than failing the analysis.
        return re.sub(r"<[^>]+>", " ", html)
    return extractor.text()


def looks_like_html(text: str, filename_hint: str = "") -> bool:
    name = (filename_hint or "").lower()
    if name.endswith((".html", ".htm")):
        return True
    head = (text or "")[:2000].lower()
    return "<html" in head or "<!doctype html" in head


# ---------------------------------------------------------------------------
# Field extraction helpers
# ---------------------------------------------------------------------------

_VEEAM_TS_RES = (
    re.compile(r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?)"),
    re.compile(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?)"),
)

_VEEAM_SEVERITY_RES = (
    (re.compile(r"\b(failed|failure|error|critical)\b", re.IGNORECASE), "Error"),
    (re.compile(r"\b(warning|warn)\b", re.IGNORECASE), "Warning"),
)


def _first_match(patterns, text: str, default: str = "") -> str:
    for rx in patterns:
        m = rx.search(text)
        if m:
            return m.group(1).strip()
    return default


def _severity(text: str, default: str = "Information") -> str:
    for rx, label in _VEEAM_SEVERITY_RES:
        if rx.search(text):
            return label
    return default


def _job_name(text: str) -> str:
    m = re.search(r"(?:job(?: name)?|replication job)\s*[:=]\s*([^\r\n]{1,80})", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"processing object\s+['\"]?([^\r\n'\"]{1,80})", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""


# ---------------------------------------------------------------------------
# Family parsers -> EventMetadata
# ---------------------------------------------------------------------------


def parse_veeam(text: str, filename_hint: str = "") -> EventMetadata:
    """Parse Veeam Backup & Replication raw log / HTML report / syslog text."""
    code = resolve_vendor_diagnostic(text, "veeam_vbr")
    job = _job_name(text)
    timestamp = _first_match(_VEEAM_TS_RES, text)
    level = _severity(text)
    head = " ".join((text or "").split()[:40])
    return EventMetadata(
        eventId=code or "VEEAM-UNKNOWN",
        provider=_VEEAM_PRODUCT,
        level=level,
        logName=(f"Job: {job} | " if job else "") + head[:150],
        timestamp=timestamp,
        computer="",
        isCritical=(level in ("Error", "Critical")),
        faultingApp="",
        sourceFamily="veeam_vbr",
        product=_VEEAM_PRODUCT,
        diagnosticCode=code,
        parserConfidence=0.9 if code else 0.65,
        attributes={"filename": filename_hint or ""},
    )


def parse_vmware(text: str, filename_hint: str = "") -> EventMetadata:
    """Parse VMware ESXi/host/vmware.log style text."""
    code = resolve_vendor_diagnostic(text, "vmware")
    timestamp = _first_match(_VEEAM_TS_RES, text)
    if not timestamp:
        m = re.search(
            r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)", text
        )
        timestamp = m.group(1) if m else ""
    level = _severity(text)
    head = " ".join((text or "").split()[:40])
    return EventMetadata(
        eventId=code or "VMWARE-UNKNOWN",
        provider=_VMWARE_PRODUCT,
        level=level,
        logName=head[:150],
        timestamp=timestamp,
        computer="",
        isCritical=(level in ("Error", "Critical")),
        faultingApp="",
        sourceFamily="vmware",
        product=_VMWARE_PRODUCT,
        diagnosticCode=code,
        parserConfidence=0.9 if code else 0.65,
        attributes={"filename": filename_hint or ""},
    )


def parse_unknown_text(text: str, filename_hint: str = "") -> EventMetadata:
    """Honest fallback: unrecognized text is unknown_text, never Windows."""
    head = " ".join((text or "").split()[:30])
    return EventMetadata(
        eventId="Unknown",
        provider="Unknown",
        level="",
        logName=head[:150],
        timestamp="",
        computer="",
        isCritical=False,
        faultingApp="",
        sourceFamily="unknown_text",
        product="",
        diagnosticCode="",
        parserConfidence=0.3,
        attributes={"filename": filename_hint or ""},
    )


def parse_syslog_hinted(text: str, source_family: str) -> Optional[Dict[str, str]]:
    """Extract Veeam RFC 5424 syslog fields when present.

    Numeric vendor instance IDs are prefixed so they can never collide
    with Windows Event IDs.
    """
    lowered = (text or "").lower()
    if "veeam_mp" not in lowered and "veeam" not in lowered:
        return None
    out: Dict[str, str] = {}
    for key in ("instanceid", "jobsessionid", "jobid"):
        m = re.search(rf"{key}\s*[:=]\s*([^\s,;]+)", text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            out[key] = f"VEEAM-{raw}" if raw.isdigit() else raw
    m = re.search(r"description\s*[:=]\s*([^\r\n]{1,200})", text, re.IGNORECASE)
    if m:
        out["description"] = m.group(1).strip()
    out["sourceFamily"] = source_family
    return out or None
