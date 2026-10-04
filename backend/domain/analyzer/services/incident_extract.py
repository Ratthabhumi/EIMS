"""Deterministic evidence-first incident extraction.

Runs BEFORE any AI/RAG/web step.  It reports what the evidence shows:

- firstMeaningfulFailure: earliest high-signal failure line observed
- terminalFailure:       last high-signal failure / session outcome observed
- timeline / operationStage / diagnosticSignatures / evidence
- unknowns / nextEvidence: what is still missing and what to collect next

It never asserts that the first failure *caused* the later one unless the
input text contains explicit causal evidence.  Ordering is chronological.

Veeam-aware severity:
  A line is only promoted to a failure if it carries an explicit failure
  outcome token (e.g. status: 'Failed') OR a known high-confidence
  diagnostic keyword.  Configuration lines that merely *mention* words like
  "failure", "retry", or "exception" as part of a setting name are
  suppressed by _VEEAM_CONFIG_SUPPRESS patterns.
"""

import re
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Veeam configuration/informational lines that MUST NOT become failures.
# These patterns match lines that describe scheduler/proxy settings, not
# actual job outcomes.
# ---------------------------------------------------------------------------
_VEEAM_CONFIG_SUPPRESS = (
    re.compile(r"retry\s+times?\s+on\s+fail", re.IGNORECASE),
    re.compile(r"use\s+fast\s+fail\s+on\s+socket\s+exception", re.IGNORECASE),
    re.compile(r"retry\s+timeout", re.IGNORECASE),
    re.compile(r"scheduleoptions", re.IGNORECASE),
    re.compile(r"backupoptions", re.IGNORECASE),
    re.compile(r"joboptions", re.IGNORECASE),
    re.compile(r"proxysettings", re.IGNORECASE),
    # Generic key=value / colon patterns for config values
    re.compile(r"^\s*\w[\w\s]*:\s*\[?\d+\]?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\w[\w\s]*:\s*(true|false)\s*$", re.IGNORECASE),
)

# Lines matching any of these are operational noise, not causal evidence.
_NOISE_RES = (
    re.compile(r"successfully connected", re.IGNORECASE),
    re.compile(r"retry is not required", re.IGNORECASE),
    re.compile(r"processing finished successfully", re.IGNORECASE),
    # Explicit Info/Debug/Trace prefix (Veeam log format: [ts] <thread> [ctx] Info (N) ...)
    re.compile(r"^\s*\[?[\d/:.T\-\s]+\]?\s*<[^>]*>\s*\[[^\]]*\]\s*(Info|Debug|Trace)\b", re.IGNORECASE),
    re.compile(r"^\s*(info|debug|trace)\s*[\s:|-]", re.IGNORECASE),
    re.compile(r"heartbeat", re.IGNORECASE),
)

# High-confidence diagnostic keywords (rank 3) — specific failure signatures.
_HIGH_CONFIDENCE_KEYWORDS = (
    "could not delete change tracking file",
    "invalidsnapshotformat",
    "a required file was not found",
    "invalid snapshot configuration",
    "processing finished with errors",
)

# Explicit session/job failure outcome patterns (rank 2 — confirmed failures).
_SESSION_FAILED_RE = re.compile(
    r"(?:task|job)\s+session\s+['\"]?[^'\"]*['\"]?\s+has\s+been\s+completed[,\s]+status\s*:\s*['\"]?failed['\"]?",
    re.IGNORECASE,
)

_SIGNAL_RES = (
    re.compile(r"\b(failed|failure|fail|error|critical|fatal)\b", re.IGNORECASE),
    re.compile(r"\b(warning|warn)\b", re.IGNORECASE),
    re.compile(r"exception", re.IGNORECASE),
    re.compile(r"could not delete change tracking file", re.IGNORECASE),
    re.compile(r"invalidsnapshotformat", re.IGNORECASE),
    re.compile(r"a required file was not found", re.IGNORECASE),
    re.compile(r"invalid snapshot configuration", re.IGNORECASE),
    re.compile(r"deleting helper snapshot", re.IGNORECASE),
    re.compile(r"processing finished with errors", re.IGNORECASE),
)

# Stage patterns now require context from *signal lines*, not the whole file.
# A stage label is only emitted when the SAME line that triggers it is itself
# a signal line (score >= 1) — or when we find an explicit session outcome.
_STAGE_RES = (
    (re.compile(r"prepare\s*target|preparing target", re.IGNORECASE), "PrepareTarget"),
    (re.compile(r"deleting helper snapshot", re.IGNORECASE), "DeletingHelperSnapshot"),
    (re.compile(r"revertsnapshot|revert.*snapshot|snapshot.*revert", re.IGNORECASE), "RevertSnapshot"),
    (re.compile(r"creating?\s+(helper\s+)?snapshot", re.IGNORECASE), "CreateSnapshot"),
    # "Retry" stage only from actual retry outcome lines, NOT config lines.
    (re.compile(r"^\s*retrying\b|retrying\s+in\s+\d+", re.IGNORECASE), "Retry"),
    # Session completion → SessionResult
    (re.compile(
        r"(?:task|job)\s+session\s+['\"]?[^'\"]*['\"]?\s+has\s+been\s+completed",
        re.IGNORECASE,
    ), "SessionResult"),
    (re.compile(r"processing finished", re.IGNORECASE), "SessionResult"),
)

# ---------------------------------------------------------------------------
# Path extraction — only accept real filesystem paths.
# Generic Unix /.../... is intentionally excluded to prevent HTML fragment
# false-positives.  Accepted forms:
#   C:\...  \\server\share\...  [datastore] VM/VM.vmdk
#   /vmfs/volumes/...  /var/log/...  fileName='...'
# ---------------------------------------------------------------------------
_HTML_TAG_FRAG_RE = re.compile(r"/[a-z]+>", re.IGNORECASE)

_PATH_RE = re.compile(
    r"""(?x)
    (?:
        # Windows drive path
        [A-Za-z]:\\[^\s"'<>]+
        |
        # UNC path
        \\\\[^\s"'<>]+
        |
        # VMware datastore bracket notation — the part after ] must be
        # path-like (a separator, a storage filename extension, or a
        # directory/file shape).  Bare component tags such as
        # [CViSnapReplica] RevertSnapshot are NOT paths and must not match.
        \[[^\]]{1,80}\]\s*(?:[^\s"'<>]*/[^\s"'<>]{1,120}|[^\s"'<>]*\.(?:vmdk|vmx|vmsd|nvram|log|txt))
        |
        # VMware/Linux specific roots
        /vmfs/[^\s"'<>;]+
        |
        /var/log/[^\s"'<>;]+
        |
        /etc/[^\s"'<>;]+
        |
        # fileName= quoted path (any OS)
        filename\s*=\s*['"]([^'"]{4,})['"]\s*
    )
    """,
    re.IGNORECASE,
)

_GENERIC_NEXT_EVIDENCE = [
    "Original unmodified source log file",
    "Time-correlated logs from adjacent components",
]

_FAMILY_NEXT_EVIDENCE: Dict[str, List[str]] = {
    "veeam_vbr": [
        "Veeam Task log (Export Logs from %ProgramData%\\Veeam\\Backup)",
        "Veeam Job session log",
        "Agent/component log from the relevant Veeam component",
        "vmware.log / hostd.log when a VMware operation is implicated",
    ],
    "vmware": [
        "VM vmware.log",
        "ESXi hostd.log",
        "Datastore file listing (.vmdk / .ctk.vmdk state)",
    ],
    "windows_event": [
        "Full Event Viewer export (.evtx) around the failure time",
    ],
    "fortinet": ["Full FortiGate log segment with session close codes"],
    "cisco_asa": ["Full ASA syslog segment with connection teardown lines"],
    "linux_syslog": ["journalctl segment for the affected service"],
    "json": ["Complete structured event payload"],
    "unknown_text": ["Original file plus a note about which product emitted it"],
}


def _is_veeam_config_line(line: str) -> bool:
    """Return True if the line is a Veeam configuration/scheduler setting."""
    return any(rx.search(line) for rx in _VEEAM_CONFIG_SUPPRESS)


def _is_noise(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 8:
        return True
    if _is_veeam_config_line(stripped):
        return True
    return any(rx.search(stripped) for rx in _NOISE_RES)


def _signal_strength(line: str) -> int:
    """
    Return signal strength.

    3 = high-confidence specific diagnostic keyword
    2 = explicit session/job failure outcome OR strong error word on a
        non-config, non-Info line
    1 = warning / soft signal
    0 = no signal

    Config lines and explicit Info lines always return 0.
    """
    # Config suppression takes priority.
    if _is_veeam_config_line(line):
        return 0

    lowered = line.lower()

    # High-confidence diagnostic keywords.
    if any(k in lowered for k in _HIGH_CONFIDENCE_KEYWORDS):
        return 3

    # Explicit session/job failure outcome.
    if _SESSION_FAILED_RE.search(line):
        return 2

    # Explicit Veeam log-level prefix: [ts] <thread> [ctx] Warning/Error/...
    # A line with explicit "Error" or "Warning" prefix in Veeam format qualifies.
    veeam_level_m = re.search(
        r"\]\s*(Error|Warning|Critical|Fatal)\b",
        line,
        re.IGNORECASE,
    )
    if veeam_level_m:
        level = veeam_level_m.group(1).lower()
        if level in ("error", "critical", "fatal"):
            return 2
        if level == "warning":
            return 1

    # Generic failure words — but only when NOT on an Info/config line.
    # We already filtered Info prefix in _is_noise; here handle residual cases.
    if re.search(r"^\s*\[?[\d/:.T\-\s]+\]?\s*<[^>]*>\s*\[[^\]]*\]\s*Info\b", line, re.IGNORECASE):
        return 0

    if re.search(r"\b(failed|failure|fatal|critical|exception)\b", lowered):
        return 2
    if any(rx.search(line) for rx in _SIGNAL_RES):
        return 1
    return 0


def extract_incident(text: str, source_family: str = "") -> Dict[str, object]:
    """Extract a deterministic incident sketch from raw log text.

    Chronology is timestamp-derived (see evidence.order_records), never
    upload/concatenation order.  For chronologically ordered input the
    output is identical to line order.
    """
    from backend.domain.analyzer.services.evidence import build_evidence_records

    records = build_evidence_records([("", text or "")])
    return incident_from_records(records, source_family)


def incident_from_records(records, source_family: str = "") -> Dict[str, object]:
    """Incident sketch from normalized evidence records.

    Signal records order by parsed timestamp (source_file, line_number
    tiebreak); untimestamped signals keep source/line order without faking
    chronology.  The ordering key is a total order over record content, so
    the same files in any upload order yield the same incident.
    """
    from backend.domain.analyzer.services.evidence import order_records, timestamp_domain

    scored = []
    for rec in records or []:
        ln = rec.raw_text
        if not ln or _is_noise(ln):
            continue
        scored.append((rec, _signal_strength(ln)))
    failures = order_records([rec for rec, s in scored if s >= 2])
    warnings = order_records([rec for rec, s in scored if s == 1])

    first: Optional[str] = (
        failures[0].raw_text if failures
        else (warnings[0].raw_text if warnings else None)
    )
    terminal: Optional[str] = None
    if failures:
        terminal = failures[-1].raw_text
    elif warnings:
        terminal = warnings[-1].raw_text

    timeline: List[str] = [rec.raw_text[:300] for rec in order_records(failures + warnings)[:12]]

    # Stage: infer only from signal lines (score >= 1), not whole-file scan.
    # This prevents ScheduleOptions config text from driving operationStage.
    signal_text = "\n".join(rec.raw_text for rec, s in scored if s >= 1)
    stages: List[str] = []
    for rx, label in _STAGE_RES:
        if rx.search(signal_text) and label not in stages:
            stages.append(label)
    stage = " / ".join(stages) if stages else ""

    signatures = sorted(
        {
            rec.raw_text[:200]
            for rec in failures
            if any(
                k in rec.raw_text.lower()
                for k in (
                    "could not delete change tracking file",
                    "invalidsnapshotformat",
                    "a required file was not found",
                    "invalid snapshot configuration",
                    "deleting helper snapshot",
                    "result 2620",
                    "ctk_ctkunlink",
                )
            )
        }
    )

    evidence = [rec.raw_text[:300] for rec in failures[:10]]

    unknowns: List[str] = [
        "Exact missing filename (unless a file path appears verbatim in the evidence above)",
        "Exact CTK/VMDK file that could not be deleted (unless named verbatim above)",
        "Whether the file was locked, corrupt, moved, renamed, or absent",
    ]
    domains = {timestamp_domain(r.timestamp_raw, r.timestamp_kind)
               for r in failures + warnings if r.timestamp_key is not None}
    if len(domains) > 1:
        unknowns.insert(0, "Incomparable clock domains: source/line order used; first/terminal chronology is unverified")
    elif any(r.timestamp_key is None for r in failures + warnings):
        unknowns.insert(0, "Some signals have no parseable timestamp; their chronology is unverified")

    # Path extraction — only accepted filesystem paths; reject HTML fragments.
    path_lines = list(failures) + [w for w in warnings if w not in failures]
    _PATH_HINT_RE = re.compile(r"filename\s*[:=]|/vmfs/|[A-Za-z]:\\")
    seen_keys = {(rec.source_file, rec.line_number) for rec in path_lines}
    path_lines += [
        rec
        for rec, s in scored
        if s == 0
        and _PATH_HINT_RE.search(rec.raw_text)
        and (rec.source_file, rec.line_number) not in seen_keys
    ]

    raw_paths: List[str] = []
    from backend.domain.analyzer.services.bundle import extract_observed_paths
    for rec in path_lines:
        ln = rec.raw_text
        # Skip lines that look like they contain HTML fragments.
        if _HTML_TAG_FRAG_RE.search(ln):
            continue
        raw_paths.extend(extract_observed_paths(ln))

    observed_paths = sorted(set(raw_paths))[:3]

    next_evidence = list(_FAMILY_NEXT_EVIDENCE.get(source_family or "", _GENERIC_NEXT_EVIDENCE))

    return {
        "firstMeaningfulFailure": first,
        "terminalFailure": terminal,
        "timeline": timeline,
        "operationStage": stage,
        "diagnosticSignatures": signatures,
        "evidence": evidence,
        "observedPaths": observed_paths,
        "unknowns": unknowns,
        "nextEvidence": next_evidence,
    }
