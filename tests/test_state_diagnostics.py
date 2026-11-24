"""State/telemetry evaluators: synthetic rows only; documented semantics, no invented thresholds."""
import pytest

from backend.domain.analyzer.services import state_diagnostics as sd


@pytest.mark.parametrize("row,state,attention", [
    ({"wal_status": "reserved", "active": True, "safe_wal_size": 1_000_000}, "within_max_wal_size", False),
    ({"wal_status": "reserved", "active": False, "safe_wal_size": 5}, "within_max_wal_size", True),
    ({"wal_status": "extended", "active": True, "safe_wal_size": 10}, "retaining_beyond_max_wal_size", True),
    ({"wal_status": "unreserved", "active": False, "safe_wal_size": 0}, "at_risk_of_wal_removal", True),
    ({"wal_status": "lost", "active": False, "safe_wal_size": None}, "lost", True),
])
def test_slot_states_follow_the_documented_wal_status_values(row, state, attention):
    r = sd.evaluate_replication_slot(row)
    assert r["state"] == state and r["attention"] is attention
    assert sd.WAL_STATUS_MEANING[row["wal_status"]] in " ".join(r["observations"])
    assert all(u.startswith("https://www.postgresql.org/docs/16/") for u in r["sources"])


def test_slot_false_positive_risks_are_stated():
    ext = sd.evaluate_replication_slot({"wal_status": "extended", "active": True, "safe_wal_size": 1})
    assert any("wal_keep_size" in x for x in ext["false_positive_risks"])
    unlimited = sd.evaluate_replication_slot({"wal_status": "reserved", "active": True, "safe_wal_size": None})
    assert any("max_slot_wal_keep_size is -1" in x for x in unlimited["observations"] + unlimited["false_positive_risks"])
    unres = sd.evaluate_replication_slot({"wal_status": "unreserved", "active": True, "safe_wal_size": 0})
    assert any("not yet lost" in x for x in unres["false_positive_risks"])


@pytest.mark.parametrize("row", [{}, {"wal_status": None}, {"wal_status": "something_new"}])
def test_slot_without_a_documented_status_is_not_interpreted(row):
    r = sd.evaluate_replication_slot(row)
    assert r["state"] == "no_wal_status" and r["attention"] is False


def test_lag_all_null_is_not_called_healthy_or_failed():
    r = sd.evaluate_standby_lag({"write_lag": None, "flush_lag": None, "replay_lag": None})
    assert r["state"] == "no_lag_measurement" and r["attention"] is False
    assert any("Do not read NULL" in x for x in r["false_positive_risks"])


def test_lag_without_caller_threshold_applies_no_threshold():
    r = sd.evaluate_standby_lag({"write_lag": 0.2, "flush_lag": 0.5, "replay_lag": 120.0})
    assert r["state"] == "lag_measured" and r["attention"] is False
    assert "replay_lag" in r["observations"][0] and any("No threshold applied" in x for x in r["observations"])
    assert any("exceeds flush_lag" in x for x in r["observations"])


def test_lag_with_a_caller_supplied_threshold_reports_the_breach_only_for_that_threshold():
    r = sd.evaluate_standby_lag({"write_lag": 1.0, "flush_lag": 2.0, "replay_lag": 45.0}, thresholds={"replay_lag": 30.0})
    assert r["state"] == "caller_threshold_exceeded" and r["attention"] is True
    ok = sd.evaluate_standby_lag({"write_lag": 1.0, "flush_lag": 2.0, "replay_lag": 5.0}, thresholds={"replay_lag": 30.0})
    assert ok["attention"] is False and "not exceeded" in " ".join(ok["observations"])


@pytest.mark.parametrize("line,reason,cause", [
    ("2026-01-01 FGT-A is selected as the primary because the value 0 of link-failure + pingsvr-failure is less than peer member.", "monitored_interface_or_ping_server", True),
    ("FGT-B is selected as the master because it has the least value 0 of link-failure + pingsvr-failure.", "monitored_interface_or_ping_server", True),
    ("FGT-A is selected as the primary because it's the only member in the cluster.", "peer_member_down_only_member", True),
    ("FGT-A is selected as the primary because its override priority is larger than peer member.", "override_priority_larger", True),
    ("FGT-A is selected as the primary because its uptime is larger than peer member.", "uptime_larger", True),
    ("FGT-A is selected as the primary because there is high memory usage on peer member.", "high_memory_on_peer", True),
    ("FGT-A is selected as the primary because EXE_FAIL_OVER flag is set on peer member.", "manual_failover_flag", True),
    ("FGT-A is selected as the primary because its serialno is larger than peer member.", "initial_election_serial_number", False),
])
def test_ha_selection_strings_quoted_by_the_sources_are_classified(line, reason, cause):
    r = sd.evaluate_fortigate_ha_selection(line)
    assert r["reason"] == reason and r["failover_cause"] is cause and r["false_positive_risks"]


def test_ha_selection_old_and_new_wording_are_distinguished_and_unknown_lines_are_not_interpreted():
    assert "older" in sd.evaluate_fortigate_ha_selection("X is selected as the master because it has the least value 0 of link-failure + pingsvr-failure.")["wording"]
    assert "primary" in sd.evaluate_fortigate_ha_selection("X is selected as the primary because its uptime is larger than peer member")["wording"]
    r = sd.evaluate_fortigate_ha_selection("X became primary for reasons unknown")
    assert r["reason"] == "unrecognized" and r["failover_cause"] is False
