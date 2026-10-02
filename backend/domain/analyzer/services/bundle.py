"""Multi-file evidence bundle: validation, correlation, provenance.

Stdlib-only pure functions (validation, hashing, correlation) so the
regression suite can exercise them without a database or network.

Correlation is conservative by design:
  strong  - exact same JobSessionID / JobID (or other supported Veeam
            correlation identifier) observed in 2+ files.
  medium  - exact same VM/entity/path identifier in 2+ files PLUS an
            overlapping timestamp window.
  weak    - matching error signature (+ time proximity when timestamps
            exist).  NEVER reported as proven causality.
  none    - no link found.

Timestamps are preserved as originally observed; normalization happens
only when the format is explicit (ISO-8601 with timezone).  Otherwise
source order + original text are kept.

Exact paths (e.g. fileName:'/vmfs/.../VM-000003.vmdk') are surfaced only
when literally observed.  Related names (.ctk.vmdk, -delta.vmdk, .vmsd,
.vmx) are NEVER inferred.
"""

import hashlib
import ntpath
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

BUNDLE_MAX_FILES = 12
BUNDLE_MAX_FILE_BYTES = 5 * 1024 * 1024
BUNDLE_MAX_TOTAL_BYTES = 30 * 1024 * 1024

ALLOWED_EXTENSIONS = frozenset({".log", ".txt", ".html", ".htm", ".xml", ".csv", ".evtx"})

MAX_EVIDENCE_ITEMS_PER_FILE = 30
MAX_EVIDENCE_ITEMS_TOTAL = 120

# Timestamp windows are expanded by this epsilon (each side) when checking
# medium-correlation overlap.  Original timestamps are always preserved;
# the epsilon only decides whether two observed windows count as the same
# incident window.  Point events seconds apart must still correlate.
BUNDLE_TIME_EPSILON_SECONDS = 300

FAILURE_LINE = re.compile(
    r"\b(error|failed|failure|exception|critical|"
    r"could not|cannot|unable to|invalid|missing|not found|"
    r"locked|corrupt|mismatch|timeout|denied|abort)\b",
    re.IGNORECASE,
)

# Exact observed paths only.  Quoted values after file-ish keys, /vmfs/
# tokens, Windows drive paths, or quoted names with known extensions.
PATH_PATTERNS = (
    re.compile(r"(?:fileName|filename|file|path)\s*[:=]\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"(/vmfs/[^\s'\";,]+)"),
    re.compile(r"([A-Za-z]:\\[^\s'\";,]+)"),
    re.compile(r"['\"]([^'\"]+\.(?:vmdk|vmx|vmsd|log|txt))['\"]"),
)

# Leading timestamps: ISO-8601, Veeam [dd.mm.yyyy HH:MM:SS], syslog.
TS_PATTERNS = (
    re.compile(r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"),
    re.compile(r"^\[(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2})\]"),
    re.compile(r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"),
    re.compile(r"^(\d{2}:\d{2}:\d{2})"),
)

JOBSESSION_RE = re.compile(r"jobsession\s*id\s*[:=]\s*([A-Za-z0-9\-_]+)", re.IGNORECASE)
JOBID_RE = re.compile(r"(?<![a-z])job\s*id\s*[:=]\s*([A-Za-z0-9\-_]+)", re.IGNORECASE)
# Bare "JobSessionID=<...>" / "JobID=<...>" (RFC5424 / Task logs).
JOBSESSION_BARE_RE = re.compile(r"jobsessionid\s*[:=]\s*([A-Za-z0-9\-_]+)", re.IGNORECASE)
JOBID_BARE_RE = re.compile(r"(?<![a-z])jobid\s*[:=]\s*([A-Za-z0-9\-_]+)", re.IGNORECASE)

SIGNATURE_PHRASES = (
    "a required file was not found",
    "invalidsnapshotformat",
    "invalid snapshot configuration",
    "could not delete change tracking file",
    "detected an invalid snapshot configuration",
    "snapshot consolidation failed",
    "revertsnapshot",
    "createsnapshot",
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_basename(filename: str) -> str:
    """Strip any client path components; never trust them."""
    base = ntpath.basename((filename or "").replace("/", "\\"))
    return base.strip() or "unnamed"


def extension_of(filename: str) -> str:
    lower = (filename or "").lower()
    dot = lower.rfind(".")
    return lower[dot:] if dot >= 0 else ""


def validate_bundle(files: List[Tuple[str, bytes]]) -> List[Tuple[str, bytes]]:
    """Validate count / type / sizes.  Returns sanitized (basename, bytes).

    Raises ValueError with a clear, user-safe message on violation.
    """
    if not files:
        raise ValueError("No files supplied for the evidence bundle.")
    if len(files) > BUNDLE_MAX_FILES:
        raise ValueError(
            f"Too many files ({len(files)}). Maximum is {BUNDLE_MAX_FILES}."
        )
    total = 0
    cleaned: List[Tuple[str, bytes]] = []
    for name, content in files:
        base = safe_basename(name)
        ext = extension_of(base)
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{ext or base}'. Allowed: "
                + ", ".join(sorted(ALLOWED_EXTENSIONS))
                + ". ZIP archives are not supported."
            )
        size = len(content or b"")
        if size > BUNDLE_MAX_FILE_BYTES:
            raise ValueError(
                f"File '{base}' is too large ({size} bytes). "
                f"Maximum per file is {BUNDLE_MAX_FILE_BYTES} bytes."
            )
        total += size
        cleaned.append((base, content or b""))
    if total > BUNDLE_MAX_TOTAL_BYTES:
        raise ValueError(
            f"Bundle too large ({total} bytes). "
            f"Maximum total is {BUNDLE_MAX_TOTAL_BYTES} bytes."
        )
    return cleaned


def extract_observed_paths(line: str) -> List[str]:
    found: List[str] = []
    for pattern in PATH_PATTERNS:
        for match in pattern.findall(line):
            value = match.strip().strip(".,;")
            if value and value not in found:
                found.append(value)
    return found


def extract_leading_timestamp(line: str) -> str:
    for pattern in TS_PATTERNS:
        match = pattern.search(line.strip())
        if match:
            return match.group(1)
    return ""


def _parse_timestamp_key(raw: str) -> Optional[datetime]:
    """Best-effort sort key; only for explicit formats.  None otherwise."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        candidate = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(candidate)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        pass
    for fmt in ("%d.%m.%Y %H:%M:%S", "%b %d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def correlation_ids(text: str) -> Dict[str, str]:
    """Normalized Veeam correlation identifiers observed in text."""
    out: Dict[str, str] = {}
    lowered = text or ""
    for key, pattern in (
        ("jobsessionid", JOBSESSION_RE),
        ("jobsessionid", JOBSESSION_BARE_RE),
        ("jobid", JOBID_RE),
        ("jobid", JOBID_BARE_RE),
    ):
        match = pattern.search(lowered)
        if match:
            raw = match.group(1).strip().strip("\"'")
            if raw.upper().startswith("VEEAM-"):
                raw = raw[6:]
            if raw and key not in out:
                out[key] = raw
    return out


def error_signatures(text: str) -> List[str]:
    lowered = (text or "").lower()
    return [sig for sig in SIGNATURE_PHRASES if sig in lowered]


@dataclass
class BundleFileEvidence:
    filename: str
    sizeBytes: int
    sha256: str
    sourceFamily: str = ""
    product: str = ""
    diagnosticCode: str = ""
    parserConfidence: float = 0.0
    text: str = ""
    ids: Dict[str, str] = field(default_factory=dict)
    signatures: List[str] = field(default_factory=list)
    paths: List[str] = field(default_factory=list)
    timeMin: Optional[datetime] = None
    timeMax: Optional[datetime] = None
    hasTimestamps: bool = False


def summarize_file_evidence(
    filename: str,
    content: bytes,
    text: str,
    source_family: str = "",
    product: str = "",
    diagnostic_code: str = "",
    parser_confidence: float = 0.0,
) -> BundleFileEvidence:
    ids = correlation_ids(text)
    signatures = error_signatures(text)
    paths: List[str] = []
    keys: List[datetime] = []
    has_ts = False
    for line in text.splitlines():
        if extract_leading_timestamp(line):
            has_ts = True
        for path in extract_observed_paths(line):
            if path not in paths:
                paths.append(path)
        key = _parse_timestamp_key(extract_leading_timestamp(line))
        if key is not None:
            keys.append(key)
    return BundleFileEvidence(
        filename=filename,
        sizeBytes=len(content),
        sha256=sha256_hex(content),
        sourceFamily=source_family,
        product=product,
        diagnosticCode=diagnostic_code,
        parserConfidence=parser_confidence,
        text=text,
        ids=ids,
        signatures=signatures,
        paths=paths,
        timeMin=min(keys) if keys else None,
        timeMax=max(keys) if keys else None,
        hasTimestamps=has_ts,
    )


def build_evidence_items(
    files: List[BundleFileEvidence],
) -> List[Dict[str, object]]:
    """Failure-relevant lines with file provenance (line numbers 1-based)."""
    items: List[Dict[str, object]] = []
    for entry in files:
        count = 0
        for lineno, line in enumerate(entry.text.splitlines(), start=1):
            if len(items) >= MAX_EVIDENCE_ITEMS_TOTAL:
                return items
            if count >= MAX_EVIDENCE_ITEMS_PER_FILE:
                break
            if not FAILURE_LINE.search(line):
                continue
            stripped = line.strip()
            if len(stripped) > 500:
                stripped = stripped[:500]
            paths = extract_observed_paths(line)
            signature = ""
            lowered = line.lower()
            for sig in SIGNATURE_PHRASES:
                if sig in lowered:
                    signature = sig
                    break
            items.append(
                {
                    "sourceFile": entry.filename,
                    "lineNumber": lineno,
                    "timestamp": extract_leading_timestamp(line),
                    "message": stripped,
                    "signature": signature,
                    "observedPath": paths[0] if paths else "",
                }
            )
            count += 1
    return items


def correlate_bundle(files: List[BundleFileEvidence]) -> Dict[str, object]:
    """Conservative cross-file correlation.  Never invents causality."""
    reasons: List[str] = []
    correlated: List[str] = []
    confidence = "none"

    if len(files) < 2:
        return {
            "correlationConfidence": "none",
            "correlationReasons": ["Only one file supplied; nothing to correlate."],
            "correlatedSources": [f.filename for f in files],
        }

    # STRONG: exact shared JobSessionID / JobID.
    for id_key in ("jobsessionid", "jobid"):
        groups: Dict[str, List[str]] = {}
        for entry in files:
            value = entry.ids.get(id_key)
            if value:
                groups.setdefault(value, []).append(entry.filename)
        for value, names in groups.items():
            if len(names) >= 2:
                confidence = "strong"
                correlated = sorted(set(correlated) | set(names))
                reasons.append(
                    f"Strong: exact {id_key} '{value}' observed in "
                    + ", ".join(sorted(set(names)))
                    + "."
                )

    # MEDIUM: exact shared path + overlapping timestamp window.
    if confidence != "strong":
        path_groups: Dict[str, List[BundleFileEvidence]] = {}
        for entry in files:
            for path in entry.paths:
                path_groups.setdefault(path, []).append(entry)
        for path, entries in path_groups.items():
            unique = sorted({e.filename for e in entries})
            if len(unique) < 2:
                continue
            timed = [e for e in entries if e.timeMin and e.timeMax]
            overlap = False
            if len(timed) >= 2:
                from datetime import timedelta as _td

                eps = _td(seconds=BUNDLE_TIME_EPSILON_SECONDS)
                latest_start = max(e.timeMin for e in timed)  # type: ignore[operator]
                earliest_end = min(e.timeMax for e in timed)  # type: ignore[operator]
                overlap = (latest_start - eps) <= (earliest_end + eps)
            if overlap:
                confidence = "medium"
                correlated = sorted(set(correlated) | set(unique))
                reasons.append(
                    f"Medium: exact path '{path}' observed in "
                    + ", ".join(unique)
                    + " with overlapping timestamp windows "
                    + f"(±{BUNDLE_TIME_EPSILON_SECONDS // 60} min tolerance; "
                    + "original timestamps preserved)."
                )
            else:
                if confidence == "none":
                    confidence = "weak"
                correlated = sorted(set(correlated) | set(unique))
                reasons.append(
                    f"Weak: exact path '{path}' observed in "
                    + ", ".join(unique)
                    + " but timestamp overlap cannot be verified; "
                    + "shared path only, causality NOT proven."
                )

    # WEAK: shared error signature only.
    if confidence == "none":
        sig_groups: Dict[str, List[str]] = {}
        for entry in files:
            for sig in entry.signatures:
                sig_groups.setdefault(sig, []).append(entry.filename)
        for sig, names in sig_groups.items():
            unique = sorted(set(names))
            if len(unique) >= 2:
                confidence = "weak"
                correlated = sorted(set(correlated) | set(unique))
                reasons.append(
                    f"Weak: shared error signature '{sig}' in "
                    + ", ".join(unique)
                    + "; signature similarity only, causality NOT proven."
                )

    if confidence == "none":
        reasons.append("No shared identifiers, paths, or signatures found across files.")
        correlated = [f.filename for f in files]

    if confidence == "weak":
        reasons.append(
            "Weak correlation must NOT be read as a proven causal chain."
        )

    return {
        "correlationConfidence": confidence,
        "correlationReasons": reasons,
        "correlatedSources": correlated,
    }
