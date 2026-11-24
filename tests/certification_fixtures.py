"""Synthetic positive/negative matching fixtures for certification classes B and D.

Every text is synthetic (documentation-shaped values, RFC 5737 addresses). Fixtures describe *inputs and expectations
only*; results come from running them through the real parser/Analyzer path (``tools/run_certification_matching.py``).
Nothing here is a certification: a passing fixture is automated technical evidence for a human reviewer.

A fixture is: record_key, resolver, positive (text), negatives (list of {"why", "text"}).
Resolvers: ``legacy`` (parse_event_metadata -> entry_for_metadata), ``summary`` (catalog_summary with a family),
``evaluator`` (state_diagnostics function over a synthetic row; synthetic-row evidence only).
"""
from __future__ import annotations

import csv
import io
import json

FIXTURE_SCHEMA = 1


# ---------------------------------------------------------------- Cisco ASA (12 legacy records) -----------------
def _asa(severity, mid, body):
    return f"%ASA-{severity}-{mid}: {body}"


ASA_POSITIVE = {
    "105005": _asa(4, 105005, "(Primary) Lost Failover communications with mate on interface inside"),
    "106001": _asa(2, 106001, "Inbound TCP connection denied from 192.0.2.10/50000 to 198.51.100.5/80 flags SYN on interface outside"),
    "106015": _asa(6, 106015, "Deny TCP (no connection) from 192.0.2.10/50000 to 198.51.100.5/80 flags RST on interface outside"),
    "106023": _asa(4, 106023, 'Deny tcp src outside:192.0.2.10/50000 dst inside:198.51.100.5/80 by access-group "OUT_ACL" [0x0, 0x0]'),
    "106024": _asa(2, 106024, "Access rules memory exhausted"),
    "106100": _asa(6, 106100, "access-list OUT_ACL denied tcp outside/192.0.2.10(50000) -> inside/198.51.100.5(80) hit-cnt 1 first hit [0x0, 0x0]"),
    "113005": _asa(6, 113005, "AAA user authentication Rejected : reason = Invalid password : server = 192.0.2.20 : user = synthetic : user IP = 192.0.2.30"),
    "113019": _asa(4, 113019, "Group = g, Username = u, IP = 192.0.2.40, Session disconnected. Session Type: SVC, Duration: 0h:05m:00s, Bytes xmt: 1, Bytes rcv: 1, Reason: User Requested"),
    "302013": _asa(6, 302013, "Built inbound TCP connection 1 for outside:192.0.2.10/50000 (192.0.2.10/50000) to inside:198.51.100.5/80 (198.51.100.5/80)"),
    "302014": _asa(6, 302014, "Teardown TCP connection 1 for outside:192.0.2.10/50000 to inside:198.51.100.5/80 duration 0:00:01 bytes 100 TCP FINs"),
    "411001": _asa(4, 411001, "Line protocol on interface outside changed state to up"),
    "411002": _asa(4, 411002, "Line protocol on interface outside changed state to down"),
}


def _asa_negatives(mid: str, text: str) -> list[dict]:
    return [
        {"why": "message ID absent from the catalog (same shape, ID 999999)", "text": text.replace(mid, "999999")},
        {"why": "ID quoted in free text without the ASA message prefix",
         "text": f"operator note: ticket mentions {mid} but this is not a firewall log line"},
    ]


# ------------------------------------------------------------------------- Fortinet (5 legacy records) ----------
def _fg(ftype: str, subtype: str, extra: str = "") -> str:
    return (f'date=2026-11-20 time=10:00:00 devname="FGT-SYN" devid="FGT0000000001" logid="0000000013" '
            f'type="{ftype}" subtype="{subtype}" level="notice" {extra}').strip()


FORTINET = {
    "traffic/forward": _fg("traffic", "forward", 'srcip=192.0.2.10 dstip=198.51.100.5 policyid=3 service="HTTPS" action="accept"'),
    "utm/ips": _fg("utm", "ips", 'srcip=192.0.2.10 dstip=198.51.100.5 attack="Synthetic.Attack" severity="high" action="dropped"'),
    "event/vpn": _fg("event", "vpn", 'action="tunnel-down" msg="IPsec tunnel down"'),
    "event/user": _fg("event", "user", 'action="login" status="failed" msg="Administrator login failed"'),
    "event/system": _fg("event", "system", 'action="edit" msg="Configuration changed"'),
}
FORTINET_NEG_TEXT = {
    "traffic/forward": _fg("traffic", "sniffer", 'srcip=192.0.2.10 dstip=198.51.100.5 action="accept"'),
    "utm/ips": _fg("utm", "webfilter", 'srcip=192.0.2.10 dstip=198.51.100.5 action="blocked"'),
    "event/vpn": _fg("event", "wad", 'action="info" msg="synthetic wad event"'),
    "event/user": _fg("event", "wad", 'action="info" msg="synthetic wad event"'),
    "event/system": _fg("event", "wad", 'action="info" msg="synthetic wad event"'),
}


# ----------------------------------------------------------------------------- Palo Alto (4 legacy records) -----
def pan_line(typ: str, **overrides) -> str:
    n = {"TRAFFIC": 53, "THREAT": 60, "SYSTEM": 23, "CONFIG": 14}[typ]
    f = [""] * n
    f[:7] = ["1", "2026/10/08 10:00:00", "000000000001", typ,
             {"TRAFFIC": "end", "THREAT": "vulnerability", "SYSTEM": "general", "CONFIG": "0"}[typ], "0", "2026/10/08 10:00:00"]
    if typ in ("TRAFFIC", "THREAT"):
        for i, v in {7: "192.0.2.10", 8: "198.51.100.20", 11: "Synthetic, rule", 14: "web-browsing", 30: "deny"}.items():
            f[i] = v
        if typ == "THREAT":
            f[31:35] = ["Synthetic, quoted description", "Synthetic signature (999999)", "any", "medium"]
            f[59] = "PAN-SYNTHETIC"
        else:
            f[52] = "PAN-SYNTHETIC"
    elif typ == "SYSTEM":
        f[8], f[12], f[13], f[14], f[22] = "1129", "general", "high", 'Synthetic message, with "quotes"', "PAN-SYNTHETIC"
    else:
        f[7:14] = ["192.0.2.10", "vsys1", "edit", "demo-admin", "Web", "Succeeded", "/synthetic/config/path"]
    for i, val in overrides.items():
        f[int(i)] = val
    out = io.StringIO()
    csv.writer(out, lineterminator="").writerow(f)
    return out.getvalue()


PAN_TYPES = ("TRAFFIC", "THREAT", "SYSTEM", "CONFIG")


# -------------------------------------------------------------- Veeam / VMware / Linux (legacy) -----------------
VEEAM_REPLICA = """[2026-09-12 02:11:03] <01> Info     [Veeam.Backup.Core] Job Type: Replica, Job Target Type: VMware vSphere
[2026-09-12 02:12:41] <07> Error    [CViSnapReplica] Could not delete change tracking file
[2026-09-12 02:12:41] <07> Warning  [VimApi] Deleting helper snapshot, retry is not required
[2026-09-12 02:15:44] <09> Error    [CViSnapReplica] RevertSnapshot failed: InvalidSnapshotFormat
[2026-09-12 02:15:44] <09> Error    [CViSnapReplica] Detected an invalid snapshot configuration
[2026-09-12 02:15:44] <09> Error    [VimApi] A required file was not found
"""
VEEAM_NEG_NO_FAILURE = """[2026-09-12 02:11:03] <01> Info     [Veeam.Backup.Core] Job Type: Backup, Job Target Type: VMware vSphere
[2026-09-12 02:11:05] <07> Info     [Veeam.Backup.Core] Successfully connected to the backup target
[2026-09-12 02:20:00] <09> Info     [Veeam.Backup.Core] Task session 'SYNTH' has been completed, status: 'Success'
"""
VEEAM_SESSION_FAILED = """[02.10.2026 00:11:06.410] <09> Info [Veeam.Backup.Core] Job Type: Backup
[02.10.2026 00:12:44.020] <09> Error [VeeamAgent] Task session 'SYNTH-TASK-02' has been completed, status: 'Failed'
"""
VEEAM_CBT = """[2026-09-12 02:11:03] <01> Info     [Veeam.Backup.Core] Job Type: Backup, Job Target Type: VMware vSphere
[2026-09-12 02:12:41] <07> Error    [VimApi] Could not delete change tracking file
"""
VEEAM_SNAPSHOT_MISSING = """[2026-09-12 02:11:03] <01> Info     [Veeam.Backup.Core] Job Type: Backup, Job Target Type: VMware vSphere
[2026-09-12 02:15:44] <09> Error    [VimApi] InvalidSnapshotFormat
[2026-09-12 02:15:44] <09> Error    [VimApi] A required file was not found
"""
VMWARE_CBT = """2026-09-12T02:12:41.123Z In(05) vmx - DISKLIB-CTK: Could not delete change tracking file
2026-09-12T02:12:41.124Z In(05) vmx - DISKLIB-LIB_BLOCKTRACK: CTK_CTKUNLINK result:2620
"""
VMWARE_MISSING = """2026-09-12T02:15:44.001Z Er(02) vmx - SNAPSHOT: RevertSnapshot failed with InvalidSnapshotFormat
2026-09-12T02:15:44.002Z Er(02) vmx - SNAPSHOT: A required file was not found
"""
VMWARE_NEG = "2026-09-12T02:15:44.001Z In(05) vmx - SNAPSHOT: Snapshot created successfully\n"
AUTH_FAIL_POS = "Nov 20 10:00:00 testhost sshd[1234]: Failed password for invalid user admin from 192.0.2.10 port 50000 ssh2"
AUTH_FAIL_NEG = "Nov 20 10:00:00 testhost sshd[1234]: Accepted password for admin from 192.0.2.10 port 50000 ssh2"


def _legacy(family, code_type, code, positive, negatives):
    return {"record_key": f"diagnostic_legacy:{family}:{code_type}:{code}", "resolver": "legacy",
            "expect": [family, code_type, code], "positive": positive, "negatives": negatives}


# ------------------------------------------------- new candidates: PostgreSQL / Fortinet field links --------------
def pg_json(code: str, message: str = "synthetic fixture") -> str:
    return json.dumps({"timestamp": "2026-11-20 10:00:00.123 UTC", "user": "demo", "dbname": "demo", "pid": 7, "session_id": "s.1",
                       "line_num": 1, "error_severity": "ERROR", "state_code": code, "message": message, "backend_type": "client backend"})


def _pg_syslog(body: str, program: str = "postgres[1]") -> str:
    return f"Nov 20 10:00:00 dbhost {program}: [2-1] {body}"


PG_SQLSTATE = {  # candidate_id -> a documented condition code the record is linked to
    "postgresql:auth:password-authentication-failed": "28P01",
    "postgresql:connections:too-many-connections": "53300",
    "postgresql:locks:deadlock-detected": "40P01",
    "postgresql:server:administrator-shutdown-or-terminate": "57P01",
    "postgresql:storage:data-disk-full": "53100",
}
PG_MESSAGE = {
    "postgresql:vacuum:xid-wraparound-warning-or-refusal": (
        _pg_syslog('WARNING:  database "mydb" must be vacuumed within 39985967 transactions'),
        [{"why": "same line from a non-postgres program", "text": _pg_syslog('WARNING:  database "mydb" must be vacuumed within 39985967 transactions', "sshd[1]")},
         {"why": "wording not quoted by the documentation", "text": _pg_syslog('WARNING:  database "mydb" needs attention')}]),
    "postgresql:checkpoint:wal-size-triggered-too-frequently": (
        _pg_syslog("LOG:  checkpoints are occurring too frequently (12 seconds apart)"),
        [{"why": "wording not present in the upstream source", "text": _pg_syslog("LOG:  checkpoints are happening very often (12 seconds apart)")},
         {"why": "no syslog prefix (not classified)", "text": "2026-11-20 10:00:00 UTC [1] LOG:  checkpoints are occurring too frequently (12 seconds apart)"}]),
    "postgresql:wal:archive-command-failing-pg-wal-fills": (
        _pg_syslog("LOG:  archive command failed with exit code 1"),
        [{"why": "different program", "text": _pg_syslog("LOG:  archive command failed with exit code 1", "cron[1]")},
         {"why": "wording changed", "text": _pg_syslog("LOG:  the archive step did not succeed")}]),
    "postgresql:replication:standby-query-canceled-recovery-conflict": (
        _pg_syslog("ERROR:  canceling statement due to conflict with recovery"),
        [{"why": "different cancellation reason", "text": _pg_syslog("ERROR:  canceling statement due to user request")},
         {"why": "different program", "text": _pg_syslog("ERROR:  canceling statement due to conflict with recovery", "sshd[1]")}]),
}


def build_fixtures() -> list[dict]:
    fx: list[dict] = []
    for mid, text in ASA_POSITIVE.items():
        fx.append(_legacy("cisco_asa", "official_message_id", mid, text, _asa_negatives(mid, text)))
    for cat, text in FORTINET.items():
        fx.append(_legacy("fortinet", "log_category", cat, text, [
            {"why": "adjacent subtype/type not in the catalog entry", "text": FORTINET_NEG_TEXT[cat]},
            {"why": "free text without key=value fields", "text": "operator note: forward traffic looked odd yesterday"}]))
    for typ in PAN_TYPES:
        other = PAN_TYPES[(PAN_TYPES.index(typ) + 1) % 4]
        fx.append(_legacy("palo_alto", "log_category", typ, pan_line(typ), [
            {"why": f"a different PAN log type ({other}) must not resolve to {typ}", "text": pan_line(other)},
            {"why": "truncated CSV row", "text": ",".join(pan_line(typ).split(",")[:6])}]))
    fx.append(_legacy("linux_syslog", "general_signature", "AUTH-FAIL", AUTH_FAIL_POS, [
        {"why": "successful authentication", "text": AUTH_FAIL_NEG}]))
    fx.append(_legacy("veeam_vbr", "eims_diagnostic", "VEEAM-REPLICA-SNAPSHOT-CHAIN", VEEAM_REPLICA, [
        {"why": "healthy job with a successful session", "text": VEEAM_NEG_NO_FAILURE}]))
    fx.append(_legacy("veeam_vbr", "eims_diagnostic", "VEEAM-SESSION-FAILED", VEEAM_SESSION_FAILED, [
        {"why": "session completed with Success", "text": VEEAM_NEG_NO_FAILURE}]))
    fx.append(_legacy("veeam_vbr", "eims_diagnostic", "VMWARE-CBT-DELETE-FAILED", VEEAM_CBT, [
        {"why": "healthy job with a successful session", "text": VEEAM_NEG_NO_FAILURE}]))
    fx.append(_legacy("veeam_vbr", "eims_diagnostic", "VMWARE-SNAPSHOT-FILE-MISSING", VEEAM_SNAPSHOT_MISSING, [
        {"why": "healthy job with a successful session", "text": VEEAM_NEG_NO_FAILURE}]))
    fx.append(_legacy("vmware", "eims_diagnostic", "VMWARE-CBT-DELETE-FAILED", VMWARE_CBT, [
        {"why": "unrelated healthy vmx line", "text": VMWARE_NEG}]))
    fx.append(_legacy("vmware", "eims_diagnostic", "VMWARE-SNAPSHOT-FILE-MISSING", VMWARE_MISSING, [
        {"why": "unrelated healthy vmx line", "text": VMWARE_NEG}]))

    for cid, code in PG_SQLSTATE.items():
        fx.append({"record_key": f"candidate:{cid}", "resolver": "summary", "family": "json", "candidate_id": cid,
                   "positive": pg_json(code),
                   "negatives": [{"why": "documented-but-unlinked SQLSTATE 23505 (unique_violation)", "text": pg_json("23505")},
                                 {"why": "success-class SQLSTATE 00000 is never surfaced", "text": pg_json("00000")}]})
    for cid, (pos, negs) in PG_MESSAGE.items():
        fx.append({"record_key": f"candidate:{cid}", "resolver": "summary", "family": "linux_syslog", "candidate_id": cid,
                   "positive": pos, "negatives": negs})
    fx.append({"record_key": "candidate:fortinet-fortios:traffic:policyid-0-local-traffic", "resolver": "summary", "family": "fortinet",
               "candidate_id": "fortinet-fortios:traffic:policyid-0-local-traffic",
               "positive": _fg("traffic", "local", 'srcip=192.0.2.10 dstip=198.51.100.5 policyid=0 service="HTTPS" action="accept"'),
               "negatives": [{"why": "local traffic with a user-defined policy id", "text": _fg("traffic", "local", 'policyid=7 service="HTTPS" action="accept"')},
                             {"why": "forward traffic, accept, policyid 0 is not the implicit deny", "text": _fg("traffic", "forward", 'policyid=0 service="HTTPS" action="accept"')}]})
    fx.append({"record_key": "candidate:fortinet-fortios:traffic:policyid-0-forward-implicit-deny", "resolver": "summary", "family": "fortinet",
               "candidate_id": "fortinet-fortios:traffic:policyid-0-forward-implicit-deny",
               "positive": _fg("traffic", "forward", 'srcip=192.0.2.10 dstip=198.51.100.5 policyid=0 service="HTTPS" action="deny"'),
               "negatives": [{"why": "forward deny matched by a real policy id", "text": _fg("traffic", "forward", 'policyid=5 service="HTTPS" action="deny"')},
                             {"why": "forward accept with policyid 0", "text": _fg("traffic", "forward", 'policyid=0 service="HTTPS" action="accept"')}]})

    # Class D (evaluator over a synthetic row). Synthetic-row evidence only: it exercises the evaluator logic and is NOT
    # evidence of PostgreSQL integration; real-database evidence is collected separately (tools/run_certification_pg_state.py).
    fx.append({"record_key": "candidate:postgresql:replication:slot-retains-wal-filling-pg-wal", "resolver": "evaluator",
               "function": "evaluate_replication_slot", "evidence_kind": "evaluator_synthetic_row",
               "positive": {"row": {"wal_status": "extended", "active": True, "safe_wal_size": 10}, "expect": {"state": "retaining_beyond_max_wal_size", "attention": True}},
               "negatives": [{"why": "row with no wal_status is not interpreted", "row": {"wal_status": None, "active": True}, "expect": {"state": "no_wal_status", "attention": False}},
                             {"why": "reserved and active is not flagged", "row": {"wal_status": "reserved", "active": True, "safe_wal_size": 1_000_000}, "expect": {"state": "within_max_wal_size", "attention": False}}]})
    fx.append({"record_key": "candidate:postgresql:replication:standby-lag-measurement", "resolver": "evaluator",
               "function": "evaluate_standby_lag", "evidence_kind": "evaluator_synthetic_row",
               "positive": {"row": {"write_lag": 0.2, "flush_lag": 0.5, "replay_lag": 120.0}, "thresholds": {"replay_lag": 30.0},
                            "expect": {"state": "caller_threshold_exceeded", "attention": True}},
               "negatives": [{"why": "all lag columns NULL is neither healthy nor failed", "row": {"write_lag": None, "flush_lag": None, "replay_lag": None},
                              "expect": {"state": "no_lag_measurement", "attention": False}},
                             {"why": "no caller threshold means no attention", "row": {"write_lag": 0.2, "flush_lag": 0.5, "replay_lag": 120.0},
                              "expect": {"state": "lag_measured", "attention": False}}]})
    fx.append({"record_key": "candidate:fortinet-fortios:ha:failover-reason-from-ha-status", "resolver": "evaluator",
               "function": "evaluate_fortigate_ha_selection", "evidence_kind": "evaluator_synthetic_row",
               "positive": {"line": "FGT-A is selected as the primary because its uptime is larger than peer member.", "expect": {"reason": "uptime_larger", "failover_cause": True}},
               "negatives": [{"why": "serial-number election is not a failover cause", "line": "FGT-A is selected as the primary because its serialno is larger than peer member.",
                              "expect": {"reason": "initial_election_serial_number", "failover_cause": False}},
                             {"why": "unquoted wording is not interpreted", "line": "FGT-A became primary for unknown reasons", "expect": {"reason": "unrecognized", "failover_cause": False}}]})
    return fx
