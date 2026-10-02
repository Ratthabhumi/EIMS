"""Bounded evidence-aware log compaction.

Replaces the naive ``combined_text[:50000]`` head-only truncation, which
silently discarded failures located near the end of large logs.

Strategy (all bounds are constants below, DB/memory stays bounded):
  1. keep the product/session header (first HEADER_CHARS),
  2. keep chronological windows around high-signal Error/Warning/
     diagnostic-signature lines (WINDOW_RADIUS lines each side),
  3. keep the final task/session result + tail (TAIL_CHARS),
  4. deduplicate overlapping windows and exact-duplicate retry noise,
  5. append a compaction note recording what was kept vs dropped.

Total output is capped at MAX_CHARS.  The 5 MB upload guard in the router
is untouched.
"""

import re
from typing import List, Set

HEADER_CHARS = 3000
TAIL_CHARS = 8000
WINDOW_RADIUS = 12
MAX_CHARS = 60000
MAX_WINDOWS = 40

_SIGNAL_LINE_RE = re.compile(
    r"error|fail|critical|fatal|warning|warn|exception|"
    r"could not delete change tracking file|invalidsnapshotformat|"
    r"a required file was not found|invalid snapshot configuration|"
    r"deleting helper snapshot|processing finished with errors|"
    r"result\s*[:=]?\s*2620|ctk_ctkunlink",
    re.IGNORECASE,
)


def _is_signal(line: str) -> bool:
    return bool(line.strip()) and bool(_SIGNAL_LINE_RE.search(line))


def compact_log_evidence(text: str, max_chars: int = MAX_CHARS) -> str:
    """Compact a (possibly huge) log into bounded, evidence-preserving text."""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text

    lines = text.splitlines()
    total = len(lines)

    header = text[:HEADER_CHARS]
    tail = text[-TAIL_CHARS:]

    # Chronological signal windows.
    hit_indexes = [i for i, ln in enumerate(lines) if _is_signal(ln)]
    windows: List[str] = []
    covered: Set[int] = set()
    for idx in hit_indexes:
        if len(windows) >= MAX_WINDOWS:
            break
        lo = max(0, idx - WINDOW_RADIUS)
        hi = min(total, idx + WINDOW_RADIUS + 1)
        if any(i in covered for i in range(lo, hi)):
            continue
        covered.update(range(lo, hi))
        windows.append("\n".join(lines[lo:hi]))

    # Deduplicate exact-duplicate retry noise, keep chronological order.
    seen: Set[str] = set()
    unique_windows: List[str] = []
    for w in windows:
        key = w.strip()
        if key and key not in seen:
            seen.add(key)
            unique_windows.append(w)

    body = "\n\n[... signal window ...]\n\n".join(unique_windows)
    note = (
        f"\n\n[... compacted: kept header ({HEADER_CHARS} chars) + "
        f"{len(unique_windows)} signal windows + tail ({TAIL_CHARS} chars) "
        f"out of {len(text)} chars / {total} lines ...]"
    )
    out = header + "\n\n[... header above ...]\n\n" + body + "\n\n[... tail below ...]\n\n" + tail + note
    if len(out) > max_chars:
        # Hard cap: trim the middle windows first (header + tail win).
        overflow = len(out) - max_chars
        if len(body) > overflow + 500:
            body = body[: len(body) - overflow - 500] + "\n[... middle windows trimmed to fit bound ...]"
            out = header + "\n\n[... header above ...]\n\n" + body + "\n\n[... tail below ...]\n\n" + tail + note
        else:
            out = out[:max_chars] + "\n[... hard bound ...]"
    return out
