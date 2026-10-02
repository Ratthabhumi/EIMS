"""Deterministic evidence-first incident extraction.

Runs BEFORE any AI/RAG/web step.  It reports what the evidence shows:

- firstMeaningfulFailure: earliest high-signal failure line observed
- terminalFailure:       last high-signal failure / session outcome observed
- timeline / operationStage / diagnosticSignatures / evidence
- unknowns / nextEvidence: what is still missing and what to collect next

It never asserts that the first failure *caused* the later one unless the
input text contains explicit causal evidence.  Ordering is chronological.
"""

import re
from typing import Dict, List, Optional

# Lines matching any of these are operational noise, not causal evidence.
_NOISE_RES = (
    re.compile(r"successfully connected", re.IGNORECASE),
    re.compile(r"retry is not required", re.IGNORECASE),
    re.compile(r"processing finished successfully", re.IGNORECASE),
    re.compile(r"^\s*(info|debug|trace)[\s:|-]", re.IGNORECASE),
    re.compile(r"heartbeat", re.IGNORECASE),
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

_STAGE_RES = (
    (re.compile(r"prepare\s*target|preparing target", re.IGNORECASE), "PrepareTarget"),
    (re.compile(r"deleting helper snapshot", re.IGNORECASE), "DeletingHelperSnapshot"),
    (re.compile(r"revertsnapshot|revert.*snapshot|snapshot.*revert", re.IGNORECASE), "RevertSnapshot"),
    (re.compile(r"creating?\s+(helper\s+)?snapshot", re.IGNORECASE), "CreateSnapshot"),
    (re.compile(r"\bretry\b|\bretrying\b", re.IGNORECASE), "Retry"),
    (re.compile(r"processing finished", re.IGNORECASE), "SessionResult"),
)

# A path-like token: drive-letter, UNC, datastore bracket, or /.../... path.
_PATH_RE = re.compile(
    r"(?:[A-Za-z]:\\[^\s\"']+|\\\\[^\s\"']+|\[[^\]]+\]\s*[^\s\"']+|/(?:[^\s\"':;]+/)+[^\s\"':;]+)"
)

_GENERIC_NEXT_EVIDENCE = [
    "Original unmodified source log file",
    "Time-correlated logs from adjacent components",
]

_FAMILY_NEXT_EVIDENCE: Dict[str, List[str]] = {
    "veeam_vbr": [
        "Replica VM vmware.log",
        "ESXi hostd.log",
        "Datastore file listing",
        "Veeam Task/Job session logs (Export Logs from %ProgramData%\\Veeam\\Backup)",
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


def _is_noise(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 8:
        return True
    return any(rx.search(stripped) for rx in _NOISE_RES)


def _signal_strength(line: str) -> int:
    lowered = line.lower()
    if any(
        k in lowered
        for k in (
            "could not delete change tracking file",
            "invalidsnapshotformat",
            "a required file was not found",
            "invalid snapshot configuration",
        )
    ):
        return 3
    if re.search(r"\b(failed|failure|fatal|critical|exception)\b", lowered):
        return 2
    if any(rx.search(line) for rx in _SIGNAL_RES):
        return 1
    return 0


def extract_incident(text: str, source_family: str = "") -> Dict[str, object]:
    """Extract a deterministic incident sketch from raw log text."""
    lines = [(i, ln.strip()) for i, ln in enumerate((text or "").splitlines())]
    meaningful = [(i, ln) for i, ln in lines if ln and not _is_noise(ln)]

    scored = [(i, ln, _signal_strength(ln)) for i, ln in meaningful]
    failures = [(i, ln) for i, ln, s in scored if s >= 2]
    warnings = [(i, ln) for i, ln, s in scored if s == 1]

    first: Optional[str] = failures[0][1] if failures else (warnings[0][1] if warnings else None)
    terminal: Optional[str] = None
    if failures:
        # Last strong failure; prefer an explicit session outcome line.
        outcome = [ln for _, ln in failures if "processing finished" in ln.lower()]
        terminal = outcome[-1] if outcome else failures[-1][1]
    elif warnings:
        terminal = warnings[-1][1]

    timeline: List[str] = []
    for _, ln in failures:
        timeline.append(ln[:300])
    if len(timeline) < 8:
        for _, ln in warnings:
            if ln[:300] not in timeline:
                timeline.append(ln[:300])
            if len(timeline) >= 12:
                break

    stages: List[str] = []
    for rx, label in _STAGE_RES:
        if rx.search(text or "") and label not in stages:
            stages.append(label)
    stage = " / ".join(stages) if stages else ""

    signatures = sorted(
        {
            ln[:200]
            for _, ln in failures
            if any(
                k in ln.lower()
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

    evidence = [ln[:300] for _, ln in failures[:10]]

    unknowns: List[str] = [
        "Exact missing filename (unless a file path appears verbatim in the evidence above)",
        "Exact CTK/VMDK file that could not be deleted (unless named verbatim above)",
        "Whether the file was locked, corrupt, moved, renamed, or absent",
    ]
    # If a concrete path IS present in a failure line, it is observed, not unknown.
    observed_paths = sorted({m.group(0) for _, ln in failures for m in _PATH_RE.finditer(ln)})[:3]

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
