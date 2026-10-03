"""Source-aware classification for the canonical EIMS Analyzer.

Every raw log is assigned a source family BEFORE any product-specific
parsing runs.  The critical invariant:

    unknown_text MUST NEVER silently fall through to Windows Event parsing.

Windows parsing additionally requires positive Windows evidence (see
_has_windows_evidence).  All returned fields are optional-safe: historical
AnalysisHistory rows without them keep working.
"""

import re
from typing import Dict, Optional

# Canonical source families.  Order matters only for documentation;
# detection order is defined in classify_source().
SOURCE_FAMILIES = (
    "windows_event",
    "veeam_vbr",
    "vmware",
    "fortinet",
    "cisco_asa",
    "linux_syslog",
    "json",
    "unknown_text",
)

_VEEAM_MARKERS = (
    r"veeam\.backup",
    r"veeam_mp",
    r"veeam backup & replication",
    r"\bjob type\b",
    r"job target type",
    r"revertsnapshot",
    r"cvisnapreplica",
    r"\bvimapi\b",
    r"processing object",
    r"task session",
    r"job session",
    r"deleting helper snapshot",
    r"backup & replication console",
    r"scheduleoptions",
    r"retry times on failure",
    r"proxydetector",
    r"use fast fail on socket exception",
    r"vcp deployer",
)

_VMWARE_MARKERS = (
    r"disklib-",
    r"ctk_ctkunlink",
    r"disklibunlinkint",
    r"invalidsnapshotformat",
    r"\.ctk\.vmdk",
    r"\bvmx\b",
    r"\bhostd\b",
    r"\bvpxd\b",
    r"vmware\.log",
    r"could not delete change tracking file",
    r"failed to lock the file",
    r"no such file or directory",
)

# Positive Windows evidence.  A bare number or the word "event" alone is
# NOT enough: require a numeric Event ID together with a provider/log/
# computer/channel field, or genuine EVTX/XML structure.
_WINDOWS_XML_MARKERS = (
    r"<event\s+xmlns",
    r"<provider\s+name=",
    r"<eventid",
    r"timecreated\s+systemtime=",
)
_EVENT_ID_RE = re.compile(r"event\s*id\s*[:\s=]+\(?(\d{1,6})\)?", re.IGNORECASE)
_WINDOWS_FIELD_RES = (
    re.compile(r"provider\s*name\s*[:\s=]+\S", re.IGNORECASE),
    re.compile(r"(?:^|\s)source\s*[:\s=]+\S", re.IGNORECASE),
    re.compile(r"log\s*name\s*[:\s=]+\S", re.IGNORECASE),
    re.compile(r"computer\s*[:\s=]+\S", re.IGNORECASE),
    re.compile(r"channel\s*[:\s=]+\S", re.IGNORECASE),
    re.compile(r"level\s*[:\s=]+\S", re.IGNORECASE),
)


def _count_hits(lowered: str, markers) -> int:
    """Count regex marker hits (markers are regexes, not plain substrings)."""
    return sum(1 for m in markers if re.search(m, lowered))


def _has_windows_evidence(text: str) -> bool:
    lowered = text.lower()
    if any(m in lowered for m in _WINDOWS_XML_MARKERS):
        return True
    if _EVENT_ID_RE.search(text) and any(rx.search(text) for rx in _WINDOWS_FIELD_RES):
        return True
    return False


def classify_source(text: str, filename_hint: str = "") -> Dict[str, object]:
    """Classify raw log text into a source family.

    Returns a dict with: sourceFamily, product, diagnosticCode (always ""
    here; vendor parsers refine it), parserConfidence (0.0-1.0),
    attributes (filename, length).
    """
    result: Dict[str, object] = {
        "sourceFamily": "unknown_text",
        "product": "",
        "diagnosticCode": "",
        "parserConfidence": 0.3,
        "attributes": {
            "filename": filename_hint or "",
            "length": len(text or ""),
        },
    }
    if not text or not text.strip():
        return result

    lowered = text.lower()
    name = (filename_hint or "").lower()

    def _set(family: str, product: str, confidence: float) -> Dict[str, object]:
        result["sourceFamily"] = family
        result["product"] = product
        result["parserConfidence"] = confidence
        return result

    # JSON is handled by the structured parser; keep the family label here
    # so downstream code can branch without re-sniffing.
    stripped = text.strip()
    if (stripped.startswith("{") and stripped.endswith("}")) or (
        stripped.startswith("[") and stripped.endswith("]")
    ):
        try:
            import json as _json

            _json.loads(stripped)
            return _set("json", "JSON structured log", 0.85)
        except Exception:
            pass

    # Filename hints are weak signals: they only reinforce content markers.
    html_hint = name.endswith((".html", ".htm"))

    # Veeam BEFORE VMware: Veeam logs quote VMware snapshot APIs.
    veeam_hits = _count_hits(lowered, _VEEAM_MARKERS)
    if veeam_hits >= 2 or (veeam_hits == 1 and ("veeam" in lowered or html_hint)):
        return _set("veeam_vbr", "Veeam Backup & Replication", 0.9 if veeam_hits >= 2 else 0.65)

    vmware_hits = _count_hits(lowered, _VMWARE_MARKERS)
    if vmware_hits >= 2 or (vmware_hits == 1 and ("vmware" in lowered or "esxi" in lowered)):
        return _set("vmware", "VMware vSphere/ESXi", 0.9 if vmware_hits >= 2 else 0.65)

    # Delegate to the existing product sniffers (imported lazily to avoid
    # circulars: parser.py imports this module).
    try:
        from backend.domain.analyzer.services import parser as _parser

        if _parser._is_fortinet_log(text):
            return _set("fortinet", "Fortinet FortiGate", 0.9)
        if _parser._is_cisco_asa(text):
            return _set("cisco_asa", "Cisco ASA/FTD", 0.9)
        if _parser._is_linux_syslog(text):
            return _set("linux_syslog", "Linux syslog", 0.85)
    except Exception:
        pass

    if _has_windows_evidence(text):
        return _set("windows_event", "Microsoft Windows", 0.85)

    return result


def is_known_vendor_family(source_family: Optional[str]) -> bool:
    return (source_family or "") in (
        "windows_event",
        "veeam_vbr",
        "vmware",
        "fortinet",
        "cisco_asa",
        "linux_syslog",
        "json",
    )
