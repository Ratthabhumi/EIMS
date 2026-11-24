"""State/telemetry evaluators for conditions that are read from SQL views or metrics, not from log lines.

Each evaluator takes one already-collected row (a plain dict, for example one row of ``pg_replication_slots``) and
returns observations that the PostgreSQL 16 documentation supports. They never read a database, never apply a
threshold the documentation does not give, and never state a cause: callers must supply thresholds explicitly.
"""
from __future__ import annotations

from typing import Any, Mapping

DOC_SLOTS = "https://www.postgresql.org/docs/16/view-pg-replication-slots.html"
DOC_STAT_REPLICATION = "https://www.postgresql.org/docs/16/monitoring-stats.html"
DOC_MAX_SLOT_WAL_KEEP = "https://www.postgresql.org/docs/16/runtime-config-replication.html"

# Meanings copied from the pg_replication_slots documentation (wal_status column).
WAL_STATUS_MEANING = {
    "reserved": "the claimed WAL files are within max_wal_size",
    "extended": "max_wal_size is exceeded but the files are still retained, either by the replication slot or by wal_keep_size",
    "unreserved": "the slot no longer retains the required WAL files and some of them are to be removed at the next checkpoint (this state can return to reserved or extended)",
    "lost": "the slot is no longer usable",
}


def evaluate_replication_slot(row: Mapping[str, Any]) -> dict:
    """Interpret one ``pg_replication_slots`` row using only documented column semantics."""
    status = row.get("wal_status")
    active = row.get("active")
    notes: list[str] = []
    false_positive_risks: list[str] = []
    if status not in WAL_STATUS_MEANING:
        return {"state": "no_wal_status", "attention": False,
                "observations": ["wal_status is NULL or unknown; the documentation defines reserved, extended, unreserved and lost "
                                 "(a slot whose restart_lsn was never reserved has no retained WAL to evaluate)."],
                "false_positive_risks": [], "sources": [DOC_SLOTS]}
    notes.append(f"wal_status={status}: {WAL_STATUS_MEANING[status]}.")
    if status == "extended":
        false_positive_risks.append("extended can be caused by wal_keep_size rather than by this slot (documented), and an active slot may be "
                                    "transiently extended under heavy load; do not attribute the retention to the slot from this row alone.")
    if status == "unreserved":
        false_positive_risks.append("the documentation says this state can return to reserved or extended; it is not yet lost.")
    if row.get("safe_wal_size") is None and status != "lost":
        notes.append("safe_wal_size is NULL: documented to mean max_slot_wal_keep_size is -1 (unlimited retention), not that the slot is lost.")
        false_positive_risks.append("NULL safe_wal_size with a non-lost slot means retention is not capped; disk growth is bounded only by free space (see the pg_wal disk-full record).")
    elif isinstance(row.get("safe_wal_size"), (int, float)):
        notes.append(f"safe_wal_size={int(row['safe_wal_size'])} bytes can still be written to WAL before the slot is in danger of becoming lost (documented meaning; the documentation gives no alert threshold).")
    if active is False:
        notes.append("active=false: the slot is not currently being used by a session (active_pid is NULL).")
    attention = status in ("extended", "unreserved", "lost") or active is False
    state = {"reserved": "within_max_wal_size", "extended": "retaining_beyond_max_wal_size", "unreserved": "at_risk_of_wal_removal", "lost": "lost"}[status]
    return {"state": state, "attention": bool(attention) and not (status == "reserved" and active is not False),
            "observations": notes, "false_positive_risks": false_positive_risks, "sources": [DOC_SLOTS, DOC_MAX_SLOT_WAL_KEEP]}


def evaluate_standby_lag(row: Mapping[str, Any], thresholds: Mapping[str, float] | None = None) -> dict:
    """Interpret one ``pg_stat_replication`` row (lag columns as seconds, or None).

    The PostgreSQL documentation defines the three lag measurements but gives no alerting threshold, so no
    threshold is applied unless the caller passes one (for example ``{"replay_lag": 30.0}``).
    """
    lags = {k: row.get(k) for k in ("write_lag", "flush_lag", "replay_lag")}
    present = {k: float(v) for k, v in lags.items() if v is not None}
    obs: list[str] = []
    risks: list[str] = []
    if not present:
        return {"state": "no_lag_measurement", "attention": False,
                "observations": ["All lag columns are NULL: documented to mean the standby has entirely caught up with no WAL activity, or a "
                                 "logical decoding plugin does not emit tracking messages."],
                "false_positive_risks": ["Do not read NULL as healthy or as failed on its own; check state and LSN positions."], "sources": [DOC_STAT_REPLICATION]}
    largest = max(present, key=present.get)
    obs.append("Measured lag (seconds): " + ", ".join(f"{k}={v:g}" for k, v in present.items()) + f"; the largest stage is {largest}.")
    stage = {"write_lag": "time until the standby reports the WAL written", "flush_lag": "time until it reports the WAL written and flushed",
             "replay_lag": "time until it reports the WAL written, flushed and applied"}
    obs.append(f"Documented meaning of {largest}: {stage[largest]}.")
    for left, right in (("write_lag", "flush_lag"), ("flush_lag", "replay_lag")):
        if left in present and right in present and present[right] > present[left]:
            obs.append(f"{right} exceeds {left}: the additional delay occurs between those two stages (documented stage definitions).")
    risks.append("The documentation describes these as measurements of recent WAL, approximating commit delay for synchronous standbys and, for asynchronous standbys, the delay before recent transactions become visible; they are not a backlog size.")
    breached = []
    if thresholds:
        breached = [k for k, limit in thresholds.items() if k in present and present[k] > float(limit)]
        obs.append("Caller-supplied thresholds " + str(dict(thresholds)) + (" exceeded for: " + ", ".join(breached) if breached else " not exceeded") + ".")
    else:
        obs.append("No threshold applied: the documentation gives none.")
    return {"state": "lag_measured" if not breached else "caller_threshold_exceeded", "attention": bool(breached),
            "observations": obs, "false_positive_risks": risks, "sources": [DOC_STAT_REPLICATION]}


import re as _re  # noqa: E402

# Selection-reason strings quoted by the Fortinet Community article "Understanding FortiGate HA failover causes from HA
# status output" (2023-07-14, "Any supported version of FortiGate"; FortiOS 6.2 not stated) and, for the older wording,
# by the FortiOS 6.2.0 Cookbook "Check HA sync status" ("Master selected using ... least value ... of link-failure + pingsvr-failure").
_HA_SELECTION = (
    ("monitored_interface_or_ping_server", _re.compile(r"selected as the (?:primary|master) because (?:the value \d+ of link-failure \+ pingsvr-failure is less than peer member|it has the least value \d+ of link-failure \+ pingsvr-failure)", _re.I)),
    ("peer_member_down_only_member", _re.compile(r"selected as the primary because it'?s the only member in the cluster", _re.I)),
    ("override_priority_larger", _re.compile(r"selected as the primary because its override priority is larger than peer member", _re.I)),
    ("uptime_larger", _re.compile(r"selected as the primary because its uptime is larger than peer member", _re.I)),
    ("high_memory_on_peer", _re.compile(r"selected as the primary because there is high memory usage on peer member", _re.I)),
    ("manual_failover_flag", _re.compile(r"selected as the primary because EXE_FAIL_OVER flag is set on peer member", _re.I)),
    ("initial_election_serial_number", _re.compile(r"selected as the primary because its serialno is larger than peer member", _re.I)),
)
_HA_REASON_NOTE = {
    "monitored_interface_or_ping_server": "Linked by the article to a monitored interface going down (ping-server conditions are not explained).",
    "peer_member_down_only_member": "Linked by the article to a cluster member being down.",
    "override_priority_larger": "Override is enabled and the higher-priority member rejoined.",
    "uptime_larger": "Override disabled and the member with the larger uptime kept or took the primary role; the article says an HA uptime reset produces the same string.",
    "high_memory_on_peer": "Memory-based failover.",
    "manual_failover_flag": "The article ties this to `execute ha failover set`.",
    "initial_election_serial_number": "Initial election by serial number; the article does not list it as a failover cause.",
}


def evaluate_fortigate_ha_selection(line: str) -> dict:
    """Classify one 'selected as the primary because ...' line of `get sys ha status` using only strings the articles quote."""
    for reason, pattern in _HA_SELECTION:
        if pattern.search(line or ""):
            older = bool(_re.search(r"selected as the master", line, _re.I))
            return {"reason": reason, "note": _HA_REASON_NOTE[reason], "failover_cause": reason != "initial_election_serial_number",
                    "wording": "older (FortiOS 6.2.0 Cookbook) 'master' wording" if older else "'primary' wording of the 2023 article",
                    "false_positive_risks": ["A transition recorded here is not necessarily a fault (override, manual failover, uptime reset are normal operations).",
                                             "'Master' (6.2.0 Cookbook) and 'primary' (2023 article) wordings differ by version; the article's applicability to FortiOS 6.2.x is not stated."]}
    return {"reason": "unrecognized", "note": "The line matches none of the strings quoted by the cited sources; no interpretation is offered.",
            "failover_cause": False, "wording": "unknown", "false_positive_risks": []}
