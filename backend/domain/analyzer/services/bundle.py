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

import asyncio
import hashlib
import inspect
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


class UploadTooLarge(ValueError):
    """Raised when an upload exceeds its maximum byte budget."""
    pass


async def read_upload_bounded(upload, max_bytes: int, chunk_size: int = 64 * 1024) -> bytes:
    """Read an UploadFile or stream asynchronously up to max_bytes + 1.

    Reads in bounded chunks. If total bytes exceed max_bytes, raises UploadTooLarge.
    Never silently truncates.
    """
    data = bytearray()
    limit_plus_one = max_bytes + 1
    reader = getattr(upload, "read", None)
    if reader is None:
        return b""

    while len(data) < limit_plus_one:
        to_read = min(chunk_size, limit_plus_one - len(data))
        if to_read <= 0:
            break
        chunk = reader(to_read)
        if inspect.isawaitable(chunk):
            chunk = await chunk
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > max_bytes:
            raise UploadTooLarge(f"File exceeds maximum allowed size of {max_bytes} bytes.")

    return bytes(data)


def build_bundle_semantic_document(
    source_family: Optional[str] = None,
    product: Optional[str] = None,
    diagnostic_code: Optional[str] = None,
    operation_stage: Optional[str] = None,
    diagnostic_signatures: Optional[List[str]] = None,
    high_level_errors: Optional[List[str]] = None,
    correlation_confidence: Optional[str] = None,
) -> str:
    """Build deterministic semantic vector document for multi-file bundles.

    Excludes raw log contents, GUIDs, datastore paths, JobSessionIDs, IPs,
    and hostnames, preserving only high-level semantic failure properties.
    """
    parts = []
    if source_family:
        parts.append(f"SourceFamily: {str(source_family).strip()}")
    if product:
        parts.append(f"Product: {str(product).strip()}")
    if diagnostic_code:
        parts.append(f"DiagnosticCode: {str(diagnostic_code).strip()}")
    if operation_stage:
        parts.append(f"OperationStage: {str(operation_stage).strip()}")
    if correlation_confidence:
        parts.append(f"CorrelationConfidence: {str(correlation_confidence).strip()}")
    if diagnostic_signatures:
        clean_sigs = [str(s).strip() for s in diagnostic_signatures if str(s).strip()]
        if clean_sigs:
            parts.append(f"Signatures: {', '.join(clean_sigs[:6])}")
    if high_level_errors:
        clean_errs = [str(e).strip() for e in high_level_errors if str(e).strip()]
        if clean_errs:
            parts.append(f"Errors: {', '.join(clean_errs[:6])}")

    doc = " | ".join(parts) if parts else "Evidence Bundle Analysis"
    from backend.domain.analyzer.services.vector_db import redact_for_embedding
    return redact_for_embedding(doc)


def derive_bundle_semantic_document_from_metadata(meta_dict: dict, sol_dict: dict) -> str:
    """Derive the deterministic bundle semantic document from stored AnalysisHistory JSON."""
    meta = meta_dict if isinstance(meta_dict, dict) else {}
    sol = sol_dict if isinstance(sol_dict, dict) else {}
    incident = sol.get("incident") or {}
    if not isinstance(incident, dict):
        incident = getattr(incident, "model_dump", lambda: {})() or {}

    attrs = meta.get("attributes") or {}
    bundle_attr = attrs.get("bundle") or {} if isinstance(attrs, dict) else {}

    source_family = meta.get("sourceFamily")
    product = meta.get("product")
    diagnostic_code = meta.get("diagnosticCode")
    correlation_confidence = bundle_attr.get("correlationConfidence") or sol.get("confidence")

    operation_stage = incident.get("operationStage")
    diagnostic_signatures = incident.get("diagnosticSignatures") or []
    first_failure = incident.get("firstMeaningfulFailure")
    terminal_failure = incident.get("terminalFailure")
    high_level_errors = [e for e in (first_failure, terminal_failure) if e]

    return build_bundle_semantic_document(
        source_family=source_family,
        product=product,
        diagnostic_code=diagnostic_code,
        operation_stage=operation_stage,
        diagnostic_signatures=diagnostic_signatures,
        high_level_errors=high_level_errors,
        correlation_confidence=correlation_confidence,
    )


FAILURE_LINE = re.compile(
    r"\b(error|failed|failure|exception|critical|"
    r"could not|cannot|unable to|invalid|missing|not found|"
    r"locked|corrupt|mismatch|timeout|denied|abort)\b",
    re.IGNORECASE,
)

# Exact observed paths only.  Quoted values after file-ish keys, /vmfs/
# tokens, Windows drive paths, or quoted names with known extensions.
# Quoted key=value pairs come first so values containing spaces are
# captured intact (e.g. file="C:\Program Files\...").
# Unquoted Windows drive-letter token (stops at whitespace; truncation is
# filtered by _is_truncated_drive_prefix in display extraction).
_DRIVE_PATH_RE = re.compile(r"([A-Za-z]:\\[^\s'\";,]+)")

PATH_PATTERNS = (
    re.compile(
        r"""(?:fileName|filename|file|path|log|directory|dir)\s*[:=]\s*["']([^"']+)["']""",
        re.IGNORECASE,
    ),
    re.compile(r"(?:fileName|filename|file|path)\s*[:=]\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"(/vmfs/[^\s'\";,]+)"),
    _DRIVE_PATH_RE,
    re.compile(r"['\"]([^'\"]+\.(?:vmdk|vmx|vmsd|log|txt))['\"]"),
)

# A drive-letter candidate with no further separator that is visibly cut
# off by a space (e.g. "C:\Program" from "C:\Program Files\...") is a
# truncated prefix, never an exact path.  It must not be emitted as one
# and must never drive correlation identity.
_TRUNCATED_WINDOWS_PREFIX_RE = re.compile(r"^[A-Za-z]:\\[^\\/]+$")


def is_log_source_path(path: str) -> bool:
    """True when a path is a Veeam evidence-source location, not an
    infrastructure-resource identity.

    Job/component/service log paths under %ProgramData%\\Veeam\\Backup
    (any drive or env-var spelling) identify WHERE evidence was collected,
    not WHICH vm/disk/snapshot failed.  They stay displayable but must
    never increase bundle correlation confidence.
    """
    lowered = (path or "").lower().replace("/", "\\")
    return "veeam\\backup" in lowered or "program files\\veeam" in lowered

# Leading timestamps: ISO-8601, Veeam [dd.mm.yyyy HH:MM:SS[.mmm]],
# Veeam report M/D/YYYY h:mm:ss AM/PM, syslog.
TS_PATTERNS = (
    re.compile(r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"),
    re.compile(r"^\[(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2})(?:\.\d+)?\]"),
    re.compile(
        r"^(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s*[AP]M)",
        re.IGNORECASE,
    ),
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


def _is_truncated_drive_prefix(value: str, line: str, match_end: int) -> bool:
    """Detect a drive-letter candidate cut off by whitespace.

    "C:\\Program" from "C:\\Program Files\\..." is a prefix, not an exact
    path: the match visibly continues after a space.  Such candidates are
    dropped instead of being emitted (and can never drive correlation).
    """
    if not _TRUNCATED_WINDOWS_PREFIX_RE.match(value):
        return False
    return re.match(r"^\s+\S", line[match_end:]) is not None


def extract_observed_paths(line: str) -> List[str]:
    found: List[str] = []
    text = line or ""
    for pattern in PATH_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(1) if match.lastindex else match.group(0)
            value = value.strip().strip(".,;")
            if not value or value in found:
                continue
            if _is_truncated_drive_prefix(value, text, match.end()):
                continue
            found.append(value)
    return found


def extract_leading_timestamp(line: str) -> str:
    for pattern in TS_PATTERNS:
        match = pattern.search(line.strip())
        if match:
            return match.group(1)
    return ""


def _parse_timestamp_key(raw: str) -> Optional[datetime]:
    """Best-effort sort key; only for explicit formats.  None otherwise.

    All keys are naive datetimes (offset-aware input is normalized to UTC
    first), so per-file min/max never mixes aware and naive values and
    cross-file window comparison cannot raise.
    """
    from backend.domain.analyzer.services.evidence import parse_evidence_timestamp

    _, key, _ = parse_evidence_timestamp(raw or "")
    return key


# VM identity as observed in hypervisor lines: name 'X', ref '19'.
# The name AND ref travel together as one pair identity.
VM_NAME_REF_RE = re.compile(
    r"""name\s*['"]([^'"]{1,80})['"]\s*,\s*ref\s*['"]?(\d+)['"]?""",
    re.IGNORECASE,
)
# Snapshot object identity: 19-snapshot-5.
SNAPSHOT_ID_RE = re.compile(r"\b(\d+-snapshot-\d+)\b")
# Task session outcome identity: Task session 'GUID' ...  Quoted form only,
# so "Task session retry 1/3" never matches.  This is a DIFFERENT identity
# from job-session and job IDs and must never be equated with them.
TASK_SESSION_ID_RE = re.compile(
    r"""task\s+session\s+['"]([A-Za-z0-9][A-Za-z0-9\-_]{2,})['"]""",
    re.IGNORECASE,
)


def correlation_ids(text: str) -> Dict[str, str]:
    """Normalized Veeam correlation identifiers observed in text.

    Identity types stay separate: task-session, job-session, and job IDs
    are different identities and are never equated.  Random GUIDs without
    an identity label are never captured.
    """
    out: Dict[str, str] = {}
    lowered = text or ""
    for key, pattern in (
        ("jobsessionid", JOBSESSION_RE),
        ("jobsessionid", JOBSESSION_BARE_RE),
        ("jobid", JOBID_RE),
        ("jobid", JOBID_BARE_RE),
        ("task_session_id", TASK_SESSION_ID_RE),
    ):
        match = pattern.search(lowered)
        if match:
            raw = match.group(1).strip().strip("\"'")
            if raw.upper().startswith("VEEAM-"):
                raw = raw[6:]
            if raw and key not in out:
                out[key] = raw
    vm_match = VM_NAME_REF_RE.search(text or "")
    if vm_match:
        out.setdefault(
            "vm", f"{vm_match.group(1).strip()}\x00{vm_match.group(2).strip()}"
        )
    snap_match = SNAPSHOT_ID_RE.search(text or "")
    if snap_match:
        out.setdefault("snapshot_id", snap_match.group(1))
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
    # Correlation-grade resource paths: infrastructure identities (VMFS
    # paths, datastore bracket paths, quoted fileName paths, complete
    # drive paths).  Display-only locations (Veeam log-source roots,
    # truncated prefixes) are in `paths` but never here.
    resource_paths: List[str] = field(default_factory=list)
    timeMin: Optional[datetime] = None
    timeMax: Optional[datetime] = None
    hasTimestamps: bool = False


# Bracket datastore form for correlation identity: the part after ] must be
# path-like (separator or storage extension).  Bare component tags such as
# [CViSnapReplica] RevertSnapshot never qualify (see incident_extract).
_BRACKET_RESOURCE_RE = re.compile(
    r"\[[^\]]{1,80}\]\s*(?:[^\s'\";,/]*[\\/][^\s'\";,]{1,120}|[^\s'\";,]*\.(?:vmdk|vmx|vmsd|nvram|log|txt))"
)


def resource_paths_for_line(line: str) -> List[str]:
    """Correlation-grade resource paths observed in one line.

    Display-only evidence-source locations (Veeam log roots) and truncated
    prefixes are excluded here even though they stay displayable.
    """
    found: List[str] = []
    text = line or ""
    for match in _BRACKET_RESOURCE_RE.finditer(text):
        value = match.group(0).strip().strip(".,;")
        if (
            value
            and value not in found
            and not is_log_source_path(value)
        ):
            found.append(value)
    for pattern in PATH_PATTERNS:
        is_drive_match = pattern is _DRIVE_PATH_RE
        for match in pattern.finditer(text):
            value = match.group(1) if match.lastindex else match.group(0)
            value = value.strip().strip(".,;")
            if not value or value in found:
                continue
            if _is_truncated_drive_prefix(value, text, match.end()):
                continue
            if is_log_source_path(value):
                continue
            # Unquoted bare drive roots without a separator beyond X:\ are
            # not infrastructure identities (quoted key=value forms stay
            # explicit and are kept).
            if is_drive_match and re.match(r"^[A-Za-z]:\\[^\\/]+$", value):
                continue
            found.append(value)
    return found


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
    resource_paths: List[str] = []
    keys: List[datetime] = []
    has_ts = False
    for line in text.splitlines():
        if extract_leading_timestamp(line):
            has_ts = True
        for path in extract_observed_paths(line):
            if path not in paths:
                paths.append(path)
        for resource in resource_paths_for_line(line):
            if resource not in resource_paths:
                resource_paths.append(resource)
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
        resource_paths=resource_paths,
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


def _windows_overlap(
    a_min, a_max, b_min, b_max, epsilon_seconds: int = BUNDLE_TIME_EPSILON_SECONDS
) -> Optional[bool]:
    """True when two file time windows overlap (epsilon tolerance).

    Returns None when overlap cannot be verified (missing bounds).
    All bounds are naive datetimes by construction, so no aware/naive
    mixing is possible here.
    """
    if not (a_min and a_max and b_min and b_max):
        return None
    from datetime import timedelta as _td

    eps = _td(seconds=epsilon_seconds)
    try:
        return max(a_min, b_min) - eps <= min(a_max, b_max) + eps
    except TypeError:
        return None


def correlate_bundle(files: List[BundleFileEvidence]) -> Dict[str, object]:
    """Conservative cross-file correlation.  Never invents causality.

    Confidence ladder (deterministic under any file order):
    - STRONG: same semantic JobSessionID / JobID in >= 2 files.  Task
      session IDs are a different identity and never count here, and
      unlabeled GUIDs are never captured at all.
    - MEDIUM: the same correlation-grade resource (exact datastore path,
      VM name/ref pair, snapshot object id) in >= 2 files within a
      compatible time window.
    - WEAK: the same meaningful diagnostic signature when nothing
      stronger holds.  Generic words ("Error", "Failed") are not
      signatures and never correlate.
    - none: nothing valid relates the files.  Veeam log-source locations
      (%ProgramData%\\Veeam\\Backup and siblings), truncated prefixes
      such as C:\\Program, and generic status words NEVER raise
      confidence — shared log directories prove shared collection, not a
      shared incident.
    """
    reasons: List[str] = []
    correlated: List[str] = []
    confidence = "none"

    entries = list(files or [])
    if len(entries) < 2:
        return {
            "correlationConfidence": "none",
            "correlationReasons": ["Only one file supplied; nothing to correlate."],
            "correlatedSources": [f.filename for f in entries],
        }

    def _names(entity_files) -> List[str]:
        return sorted({e.filename for e in entity_files})

    # STRONG: exact shared JobSessionID / JobID.  Task session IDs are a
    # different identity and are deliberately not consulted here.
    for id_key in ("jobsessionid", "jobid"):
        groups: Dict[str, List[str]] = {}
        for entry in entries:
            value = entry.ids.get(id_key)
            if value:
                groups.setdefault(value, []).append(entry.filename)
        for value in sorted(groups):
            names = sorted(set(groups[value]))
            if len(names) >= 2:
                confidence = "strong"
                correlated = sorted(set(correlated) | set(names))
                reasons.append(
                    f"Strong: exact {id_key} '{value}' observed in "
                    + ", ".join(names)
                    + "."
                )

    def _medium_or_weak(
        label: str, names: List[str], file_entries: List
    ) -> None:
        """Record a resource/entity relationship with window honesty."""
        nonlocal confidence, correlated, reasons
        timed = [e for e in file_entries if e.timeMin and e.timeMax]
        overlap: Optional[bool] = None
        if len(timed) >= 2:
            overlap = True
            for left in timed:
                for right in timed:
                    if left is right:
                        continue
                    result = _windows_overlap(
                        left.timeMin, left.timeMax, right.timeMin, right.timeMax
                    )
                    if result is False:
                        overlap = False
        if overlap:
            confidence = "medium"
            correlated = sorted(set(correlated) | set(names))
            reasons.append(
                f"Medium: {label} observed in "
                + ", ".join(names)
                + " with overlapping timestamp windows "
                + f"(±{BUNDLE_TIME_EPSILON_SECONDS // 60} min tolerance; "
                + "original timestamps preserved)."
            )
        else:
            if confidence == "none":
                confidence = "weak"
            correlated = sorted(set(correlated) | set(names))
            reasons.append(
                f"Weak: {label} observed in "
                + ", ".join(names)
                + " but timestamp overlap cannot be verified; "
                + "shared evidence only, causality NOT proven."
            )

    # MEDIUM: exact shared correlation-grade resource path.
    if confidence != "strong":
        path_groups: Dict[str, List] = {}
        for entry in entries:
            for path in entry.resource_paths:
                path_groups.setdefault(path, []).append(entry)
        for path in sorted(path_groups):
            file_entries = path_groups[path]
            unique = _names(file_entries)
            if len(unique) < 2:
                continue
            _medium_or_weak(f"exact path '{path}'", unique, file_entries)

    # MEDIUM: same VM name/ref pair or snapshot object identity.
    if confidence != "strong":
        for entity_key, entity_label in (
            ("vm", "VM identity"),
            ("snapshot_id", "snapshot object"),
        ):
            groups: Dict[str, List] = {}
            for entry in entries:
                value = entry.ids.get(entity_key)
                if value:
                    groups.setdefault(value, []).append(entry)
            for value in sorted(groups):
                file_entries = groups[value]
                unique = _names(file_entries)
                if len(unique) < 2:
                    continue
                display = (
                    value.replace("\x00", " ref ")
                    if entity_key == "vm"
                    else value
                )
                _medium_or_weak(
                    f"same {entity_label} '{display}'", unique, file_entries
                )

    # WEAK: shared error signature only (signatures are specific
    # diagnostic phrases; generic words never qualify).
    if confidence == "none":
        sig_groups: Dict[str, List[str]] = {}
        for entry in entries:
            for sig in entry.signatures:
                sig_groups.setdefault(sig, []).append(entry.filename)
        for sig in sorted(sig_groups):
            unique = sorted(set(sig_groups[sig]))
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
        correlated = [f.filename for f in entries]

    if confidence == "weak":
        reasons.append(
            "Weak correlation must NOT be read as a proven causal chain."
        )

    return {
        "correlationConfidence": confidence,
        "correlationReasons": reasons,
        "correlatedSources": correlated,
    }
