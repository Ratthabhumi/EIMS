import json
import pytest

from backend.domain.analyzer.services import vendor_diagnostics as vd
from backend.domain.analyzer.services.operational_catalog import OPERATIONAL_CATALOG
from backend.domain.analyzer.services.parser import parse_event_metadata
from backend.domain.analyzer.services.operational_catalog import entry_for_metadata

REC = vd.DIAGNOSTIC_CANDIDATES
BY = {r["candidate_id"]: r for r in REC}


ORIGINAL_IDS = {"cisco-iosxe:interface:link-flap", "cisco-ios:bgp:neighbor-down", "cisco-ios:ospf:neighbor-stuck-exstart",
                "cisco-ios:interface:errdisable", "fortinet-fortios:ipsec:ike-negotiation-failure",
                "veeam-vbr:hotadd:stuck-vmdk-on-proxy"}


def test_unique_ids_only_four_core_vendors_and_original_ids_preserved():
    assert len(BY) == len(REC)  # no duplicate candidate ids
    assert ORIGINAL_IDS <= set(BY)
    # The four core commercial vendors plus PostgreSQL, whose records are tied to the jsonlog parser path.
    assert {r["vendor"] for r in REC} <= {"Microsoft", "Cisco", "Fortinet", "Veeam", "PostgreSQL Global Development Group"}
    assert {"Microsoft", "Cisco", "Fortinet", "Veeam"} <= {r["vendor"] for r in REC}


def test_every_record_declares_a_distinct_scenario():
    keys = [(r["vendor"], r["product"], r["symptom"]) for r in REC]
    assert len(keys) == len(set(keys))  # no artificial duplicates created to inflate counts


def test_no_overclaim_and_no_parser_reachability():
    s = vd.diagnostic_candidate_summary()
    assert s["source_verified"] == s["validated"] == s["approved"] == 0
    assert {r["lifecycle_status"] for r in REC} == {"candidate"}
    assert all(r["parser_mapping"] != "existing_parser_existing_signature" for r in REC)
    assert all("human re-read pending" in r["evidence_basis"] for r in REC)
    ids = {e["catalog_id"] for e in OPERATIONAL_CATALOG}
    assert not ids & set(BY)


def test_every_command_has_expected_evidence_and_sources_are_https():
    for r in REC:
        assert all(c["expected_evidence"] for c in r["diagnostic_commands"])
        assert all(s["url"].startswith("https://") and s["page_date"] for s in r["official_sources"])
        assert r["verification_steps"] and r["operational_risk"]


def test_version_scopes_are_explicit_and_not_overgeneralised():
    forti = BY["fortinet-fortios:ipsec:ike-negotiation-failure"]
    assert "6.2" in forti["version_scope"] and "NOT" in forti["version_scope"]
    assert "NX-OS" in BY["cisco-ios:bgp:neighbor-down"]["version_scope"]
    assert "12.2(24a)" in BY["cisco-ios:ospf:neighbor-stuck-exstart"]["version_scope"]
    assert "Catalyst 9200" in BY["cisco-iosxe:interface:link-flap"]["version_scope"]


def test_vendor_stated_cautions_are_preserved():
    assert "do NOT select" in " ".join(BY["veeam-vbr:hotadd:stuck-vmdk-on-proxy"]["remediation"])
    assert "datastore" in BY["veeam-vbr:hotadd:stuck-vmdk-on-proxy"]["operational_risk"]
    assert "soft-reconfiguration" in BY["cisco-ios:bgp:neighbor-down"]["operational_risk"]
    assert "30 minutes" in BY["fortinet-fortios:ipsec:ike-negotiation-failure"]["operational_risk"]
    assert "re-enabled before the root problem" in BY["cisco-ios:interface:errdisable"]["operational_risk"]


@pytest.mark.parametrize("text", ["%LINK-3-UPDOWN: Interface GigabitEthernet1/0/1, changed state to down",
                                  "%BGP-5-ADJCHANGE: neighbor 192.0.2.1 Down Interface flap"])
def test_ios_syslog_is_truthfully_unmapped(text):
    # No IOS parser exists: the Analyzer must not resolve these to any catalog record.
    assert entry_for_metadata(parse_event_metadata(text)) is None


def test_loader_rejects_overclaim_and_missing_evidence(tmp_path):
    base = json.loads(json.dumps(REC[0]))
    for patch in ({"evidence_maturity": "validated"}, {"parser_mapping": "existing_parser_existing_signature"},
                  {"diagnostic_commands": [{"command": "x"}]}, {"official_sources": [{"url": "http://x"}]},
                  {"lifecycle_status": "approved"}):
        p = tmp_path / "c.json"
        p.write_text(json.dumps({"schema_version": 1, "records": [dict(base, **patch)]}), encoding="utf-8")
        with pytest.raises(ValueError):
            vd.load_diagnostic_candidates(p)


def test_tranche7_version_scopes_and_vendor_cautions():
    f = BY["fortinet-fortios:traffic:packet-flow-debug"]
    assert "6.2.0" in f["version_scope"] and "not established" in f["version_scope"] and "6.2.14" in f["version_scope"]
    assert "significant amount of data" in f["operational_risk"]
    assert any("fastpath disable" in c["command"] for c in f["diagnostic_commands"])
    assert "6.2.0" in BY["fortinet-fortios:ipsec:tunnel-state-and-ha-sync"]["version_scope"]
    h = BY["microsoft-hyper-v:vm:fails-to-migrate-start-or-inaccessible"]
    assert "2019" in h["version_scope"] and "2025" in h["version_scope"]
    assert "retained" in h["operational_risk"] and "backed up" in h["operational_risk"]
    assert "do not leave" in " ".join(BY["microsoft-windows-failover-cluster:service:fails-to-start"]["remediation"]).lower() or \
        "not to leave" in " ".join(BY["microsoft-windows-failover-cluster:service:fails-to-start"]["remediation"]).lower()
    for cid in ("veeam-vbr:proxy:no-proxy-available-vmware", "veeam-vbr:sobr:no-extent-available"):
        assert "KB1857" in BY[cid]["version_scope"] or "KB" in BY[cid]["version_scope"]
        assert all(s["url"] == "https://www.veeam.com/kb1857" for s in BY[cid]["official_sources"])
    assert "do not" in BY["veeam-vbr:sobr:no-extent-available"]["operational_risk"].lower()


def test_scm_7011_keeps_the_underlying_cause_warning():
    from tests.catalog_expectations import WINDOWS
    rec = next(e for e in WINDOWS if e["provider"] == "Service Control Manager" and e["event_id"] == "7011")
    risk = rec["diagnostic_guidance"]["risk"]
    assert "symptom of another problem" in risk and "indiscriminately" in risk and "underlying cause" in risk


def test_bgp_fast_external_fallover_is_not_a_generic_fix():
    r = BY["cisco-ios:bgp:session-reset-on-interface-flap"]
    text = " ".join(r["remediation"])
    assert "no bgp fast-external-fallover" in text and "not present it as a generic fix" in text
    assert "Inference" in r["operational_risk"] and "assess" in text.lower()
    assert "NX-OS" in r["version_scope"]


def test_cisco_ospf_scope_and_states():
    r = BY["cisco-ios:ospf:neighbor-missing-down-or-init"]
    assert "10.0" in r["version_scope"] and "IOS XE and NX-OS" in r["version_scope"]
    assert "FULL" in r["verification_steps"][0]


def test_veeam_helpcenter_records_carry_build_and_page_dates_and_cautions():
    hc = [r for r in REC if r["candidate_id"].startswith("veeam-vbr:") and any("helpcenter.veeam.com" in s["url"] for s in r["official_sources"])]
    assert len(hc) >= 7
    for r in hc:
        assert "13.1.2.57" in r["version_scope"] and all(s["page_date"][:2] == "20" for s in r["official_sources"])
    chain = BY["veeam-vbr:backup-chain:missing-file-or-manual-delete"]
    assert "Do not delete separate backup files manually" in " ".join(chain["remediation"])
    assert "verified recovery plan" in BY["veeam-vbr:health-check:capacity-tier-corrupted-chain"]["operational_risk"]
    assert "active full" in " ".join(BY["veeam-vbr:health-check:corruption-detected"]["remediation"]).lower()
    assert BY["veeam-vbr:immutability:cannot-delete-or-modify"]["remediation"][0].startswith("No remediation")


def test_veeam_restore_verification_and_guest_processing_records():
    ir = BY["veeam-vbr:instant-recovery:considerations-and-failures"]
    assert "RAM of the recovered VM plus 200 MB" in " ".join(ir["likely_causes"]) and "vVol" in " ".join(ir["likely_causes"])
    sb = BY["veeam-vbr:surebackup:verification-failed"]
    assert "troubleshooting mode" in sb["remediation"][0].lower() and "powered on until you stop it manually" in sb["operational_risk"]
    aa = BY["veeam-vbr:application-aware:processing-unsupported-or-failing"]
    assert "gMSA" in " ".join(aa["likely_causes"]) and "pre-freeze and post-thaw" in " ".join(aa["remediation"])
    tl = BY["veeam-vbr:transaction-log:truncation-conflicts"]
    assert "chain of transaction logs will be broken" in " ".join(tl["likely_causes"])
    mm = BY["veeam-vbr:sobr:maintenance-mode-breaks-active-chain"]
    assert "do NOT" in " ".join(mm["likely_causes"]) and "full backup manually" in " ".join(mm["remediation"])
    assert BY["veeam-vbr:sobr:sealed-extent-forces-active-full"]["remediation"][0].startswith("No remediation")


def test_asa_failover_split_brain_is_asa_scoped_and_keeps_cautions():
    r = BY["cisco-asa:failover:split-brain"]
    assert r["product_family"] == "Cisco ASA" and "IOS" in r["limitations"] and "NX-OS" in r["limitations"]
    assert "removes redundancy" in r["operational_risk"] and "no failover" in " ".join(r["remediation"])
    assert "Comm Failure" in " ".join(r["signatures"])


def test_fortinet_debug_records_state_exact_stop_sequences_and_version():
    s = BY["fortinet-fortios:sslvpn:handshake-debug"]
    cmds = " ".join(c["command"] for c in s["diagnostic_commands"])
    assert "diagnose debug disable" in cmds and "diagnose debug reset" in cmds and "6.2.0" in s["version_scope"]
    a = BY["fortinet-fortios:authentication:remote-user-fnbamd-debug"]
    assert "no diagnose debug disable appears" in " ".join(c["expected_evidence"] for c in a["diagnostic_commands"])


def test_sslvpn_records_state_version_basis_and_vendor_values():
    ids = [i for i in BY if i.startswith("fortinet-fortios:sslvpn:")]
    assert len(ids) >= 6
    for i in ids:
        r = BY[i]
        urls = {s["url"] for s in r["official_sources"]}
        if i != "fortinet-fortios:sslvpn:handshake-debug":
            assert any("6.2.14" in u for u in urls) and any("6.2.0" in u for u in urls)
        assert "6.2" in r["version_scope"] and "not established" in r["version_scope"]
    t = " ".join(BY["fortinet-fortios:sslvpn:hangs-or-disconnects-at-98-percent"]["remediation"])
    assert "login-timeout 180" in t and "dtls-hello-timeout 60" in t
    assert "FortiOS 6.0.0 or earlier" in " ".join(BY["fortinet-fortios:sslvpn:tunnel-drops-after-seconds-multi-wan"]["remediation"])


def test_sobr_and_capacity_tier_limitation_records_keep_destructive_warnings():
    d = BY["veeam-vbr:sobr:forget-or-remove-missing-restore-point-deletes-offloaded-data"]
    assert "Data-loss risk" in d["operational_risk"] and d["verification_steps"][0].startswith("Not applicable")
    assert "GFS" in " ".join(BY["veeam-vbr:capacity-tier:offload-not-happening-or-import-blocked"]["likely_causes"])
    assert "do not rename" not in BY["veeam-vbr:sobr:rescan-import-fails-vbm-path-characters"]["remediation"][0].lower()
    assert "underscore" in BY["veeam-vbr:sobr:rescan-import-fails-vbm-path-characters"]["remediation"][0]
    assert "verified recovery plan" in BY["veeam-vbr:sobr:cannot-add-repository-as-extent-or-extent-limits"]["operational_risk"] or \
        "verified recovery plan" in " ".join(BY["veeam-vbr:sobr:cannot-add-repository-as-extent-or-extent-limits"]["operational_risk"])


# --- PostgreSQL candidates linked to the jsonlog parser by SQLSTATE -------------------------------------------------
import asyncio as _asyncio  # noqa: E402

from backend.domain.analyzer.services import catalog_diagnostics as _cd  # noqa: E402
from backend.domain.analyzer.services import summary as _summary  # noqa: E402

PG_LINKED = [r for r in REC if r["parser_mapping"] == "parser_linked_by_sqlstate"]


def _pg_json(code):
    return json.dumps({"timestamp": "2026-11-20 10:00:00.123 UTC", "user": "demo", "dbname": "demo", "pid": 7, "session_id": "s.1",
                       "line_num": 1, "error_severity": "ERROR", "state_code": code, "message": "synthetic fixture", "backend_type": "client backend"})


def test_postgres_candidates_are_pg16_scoped_and_sourced_from_postgresql_docs():
    pg = [r for r in REC if r["vendor"] == "PostgreSQL Global Development Group"]
    assert len(pg) >= 8
    for r in pg:
        assert "PostgreSQL 16" in r["version_scope"] and "other major versions were not compared" in r["version_scope"]
        assert all(s["url"].startswith(("https://www.postgresql.org/docs/16/", "https://github.com/postgres/postgres/blob/REL_16_STABLE/")) for s in r["official_sources"])
        assert "human re-read pending" in r["evidence_basis"] and "PostgreSQL 16 only" in r["limitations"]


def test_linked_candidates_reference_documented_non_success_sqlstates_with_a_stated_basis():
    assert {c for r in PG_LINKED for c in r["sqlstate_codes"]} == {"40P01", "53100", "28P01", "57P01", "53300"}
    assert all(r["sqlstate_mapping_basis"] and "condition name" in r["sqlstate_mapping_basis"] for r in PG_LINKED)
    for r in REC:
        if r["vendor"] == "PostgreSQL Global Development Group" and r["parser_mapping"] not in ("parser_linked_by_sqlstate", "parser_linked_by_message", "state_telemetry_evaluator"):
            assert r["parser_mapping"] == "candidate_for_future_integration" and "cannot match this record" in r["limitations"]


@pytest.mark.parametrize("rec", PG_LINKED, ids=lambda r: r["candidate_id"])
def test_linked_candidate_reaches_the_analyzer_summary_labelled_unreviewed(rec):
    for code in rec["sqlstate_codes"]:
        text = _pg_json(code)
        sol = _cd.catalog_summary("json", text, "en")
        blob = sol.model_dump_json()
        assert rec["candidate_id"] in blob and "unreviewed" in blob and "Documented possibility, not established" in blob
        assert "Documented definition (not a diagnosis" in blob and rec["operational_risk"][:40] in blob
        full = _asyncio.run(_summary.build_summary("", "PostgreSQL", "", [], language="en", source_family="json", evidence_text=text))
        assert rec["candidate_id"] in full.model_dump_json()
        assert _cd.catalog_references("json", text)[0].link.startswith("https://www.postgresql.org/docs/16/errcodes")


def test_unlinked_sqlstate_stays_definition_only():
    sol = _cd.catalog_summary("json", _pg_json("23505"), "en")
    assert "Linked diagnostic candidate" not in sol.model_dump_json() and len(sol.causes) == 1


def test_loader_rejects_bad_sqlstate_links(tmp_path):
    base = json.loads(json.dumps(PG_LINKED[0]))
    for patch in ({"sqlstate_codes": ["00000"]}, {"sqlstate_codes": ["ZZ999"]}, {"sqlstate_codes": []}, {"sqlstate_mapping_basis": ""}):
        p = tmp_path / "c.json"
        p.write_text(json.dumps({"schema_version": 1, "records": [dict(base, **patch)]}), encoding="utf-8")
        with pytest.raises(ValueError):
            vd.load_diagnostic_candidates(p)


def test_postgres_vendor_cautions_and_values_are_preserved():
    assert "consistent order" in " ".join(BY["postgresql:locks:deadlock-detected"]["remediation"]) and "retry" in " ".join(BY["postgresql:locks:deadlock-detected"]["remediation"]).lower()
    assert "PANIC" in BY["postgresql:wal:archive-command-failing-pg-wal-fills"]["operational_risk"]
    assert "max_slot_wal_keep_size" in " ".join(BY["postgresql:replication:slot-retains-wal-filling-pg-wal"]["remediation"])
    assert "table bloat" in BY["postgresql:replication:standby-query-canceled-recovery-conflict"]["operational_risk"]
    assert "restart" in BY["postgresql:connections:too-many-connections"]["operational_risk"]
    assert "emergencies" in BY["postgresql:server:administrator-shutdown-or-terminate"]["operational_risk"]


def test_postgres_vacuum_checkpoint_lag_records_keep_vendor_specifics():
    w = BY["postgresql:vacuum:xid-wraparound-warning-or-refusal"]
    assert "not necessary or desirable to stop the postmaster" in " ".join(w["remediation"]) and "VACUUM FULL" in " ".join(w["remediation"])
    assert "rebuilt" in w["operational_risk"] and "forty million" in w["meaning"] and "three million" in w["meaning"]
    c = BY["postgresql:checkpoint:wal-size-triggered-too-frequently"]
    assert "crash recovery" in c["operational_risk"] and "30 seconds" in c["meaning"]
    lag = BY["postgresql:replication:standby-lag-measurement"]
    assert "not thresholds" in lag["operational_risk"] and any("replay_lag" in x["command"] for x in lag["diagnostic_commands"])
    assert w["parser_mapping"] == c["parser_mapping"] == "parser_linked_by_message"  # see test_documented_pg_message_parsing
    assert lag["parser_mapping"] == "state_telemetry_evaluator" and "PostgreSQL 16" in lag["version_scope"]
    assert "PostgreSQL 16" in w["version_scope"]


# --- documented PostgreSQL server messages on syslog-forwarded lines ---------------------------------------------------
WRAP_WARN = 'Nov 20 10:00:00 dbhost postgres[123]: [4-1] WARNING:  database "mydb" must be vacuumed within 39985967 transactions'
WRAP_ERR = 'Nov 20 10:00:00 dbhost postgres[123]: [5-1] ERROR:  database is not accepting commands to avoid wraparound data loss in database "mydb"'


@pytest.mark.parametrize("text,key", [(WRAP_WARN, "pg_xid_wraparound_warning"), (WRAP_ERR, "pg_xid_wraparound_refusal")])
def test_documented_pg_message_parsing(text, key):
    meta = parse_event_metadata(text)
    assert meta.sourceFamily == "linux_syslog" and meta.attributes["codeType"] == "documented_message"
    assert meta.attributes["messageKey"] == key and meta.attributes["database"] == "mydb"
    sol = _cd.catalog_summary("linux_syslog", text, "en")
    blob = sol.model_dump_json()
    assert "postgresql:vacuum:xid-wraparound-warning-or-refusal" in blob and "Message wording confirmed by the vendor documentation or upstream source" in blob
    assert "unreviewed" in blob and "Documented possibility, not established" in blob and "No root cause is established" in blob
    assert "VACUUM FULL" in blob  # vendor caution preserved
    assert [r.link for r in _cd.catalog_references("linux_syslog", text)] == ["https://www.postgresql.org/docs/16/routine-vacuuming.html"]
    full = _asyncio.run(_summary.build_summary("", "Linux/postgres", "", [], language="en", source_family="linux_syslog", evidence_text=text))
    assert "xid-wraparound" in full.model_dump_json()


@pytest.mark.parametrize("text", [
    WRAP_WARN.replace("postgres[123]", "sshd[123]"),                                        # not a postgres program
    WRAP_WARN.replace("must be vacuumed within 39985967 transactions", "needs attention"),  # wording not quoted by the docs
    'Nov 20 10:00:00 dbhost postgres[1]: [1-1] LOG:  checkpoints are happening very often (12 seconds apart)',      # wording not in the source
    "2026-11-20 10:00:00 UTC [123] " + WRAP_WARN.split("]: ", 1)[1],                          # no syslog prefix: not classified
])
def test_pg_message_lookalikes_never_resolve(text):
    assert _cd.catalog_summary("linux_syslog", text, "en") is None
    assert _cd.catalog_references("linux_syslog", text) == []


def test_loader_rejects_bad_message_links(tmp_path):
    base = json.loads(json.dumps(BY["postgresql:vacuum:xid-wraparound-warning-or-refusal"]))
    for patch in ({"documented_messages": ["not_a_parser_key"]}, {"documented_messages": []}, {"message_mapping_basis": ""}):
        p = tmp_path / "c.json"
        p.write_text(json.dumps({"schema_version": 1, "records": [dict(base, **patch)]}), encoding="utf-8")
        with pytest.raises(ValueError):
            vd.load_diagnostic_candidates(p)


def test_existing_syslog_behaviour_is_unchanged_by_pg_message_support():
    ssh = "Oct  8 10:00:00 host-synthetic sshd[10]: Failed password for demo from 192.0.2.10 port 1000 ssh2"
    meta = parse_event_metadata(ssh)
    assert meta.attributes["codeType"] == "general_signature" and _cd.catalog_summary("linux_syslog", ssh, "en") is not None


UPSTREAM = [
    ('Nov 20 10:00:00 dbhost postgres[1]: [2-1] LOG:  checkpoints are occurring too frequently (12 seconds apart)', "pg_checkpoint_too_frequent", "postgresql:checkpoint:wal-size-triggered-too-frequently", "seconds", "12"),
    ('Nov 20 10:00:00 dbhost postgres[1]: [3-1] LOG:  checkpoints are occurring too frequently (1 second apart)', "pg_checkpoint_too_frequent", "postgresql:checkpoint:wal-size-triggered-too-frequently", "seconds", "1"),
    ('Nov 20 10:00:00 dbhost postgres[1]: [4-1] LOG:  archive command failed with exit code 1', "pg_archive_command_failed", "postgresql:wal:archive-command-failing-pg-wal-fills", "exitCode", "1"),
    ('Nov 20 10:00:00 dbhost postgres[1]: [5-1] WARNING:  archiving write-ahead log file "000000010000000000000042" failed too many times, will try again later', "pg_archive_failed_too_many_times", "postgresql:wal:archive-command-failing-pg-wal-fills", "walFile", "000000010000000000000042"),
    ('Nov 20 10:00:00 dbhost postgres[1]: [6-1] ERROR:  canceling statement due to conflict with recovery', "pg_recovery_conflict_cancel", "postgresql:replication:standby-query-canceled-recovery-conflict", None, None),
    ('Nov 20 10:00:00 dbhost postgres[1]: [7-1] FATAL:  terminating connection due to conflict with recovery', "pg_recovery_conflict_terminate", "postgresql:replication:standby-query-canceled-recovery-conflict", None, None),
]


@pytest.mark.parametrize("text,key,cid,attr,value", UPSTREAM)
def test_upstream_source_confirmed_pg_messages_reach_their_candidates(text, key, cid, attr, value):
    meta = parse_event_metadata(text)
    assert meta.attributes["messageKey"] == key and (attr is None or meta.attributes[attr] == value)
    sol = _cd.catalog_summary("linux_syslog", text, "en")
    assert cid in sol.model_dump_json() and "Documented possibility, not established" in sol.model_dump_json()
    links = [r.link for r in _cd.catalog_references("linux_syslog", text)]
    assert links and any("postgresql.org/docs/16/" in u for u in links) and any("github.com/postgres/postgres/blob/REL_16_STABLE" in u for u in links)


def test_pg_message_linked_candidates_cite_the_upstream_source_file_and_state_scope():
    for cid in ("postgresql:checkpoint:wal-size-triggered-too-frequently", "postgresql:wal:archive-command-failing-pg-wal-fills",
                "postgresql:replication:standby-query-canceled-recovery-conflict"):
        r = BY[cid]
        assert r["parser_mapping"] == "parser_linked_by_message" and "REL_16_STABLE" in r["message_mapping_basis"]
        assert any("REL_16_STABLE" in s["url"] for s in r["official_sources"]) and "PostgreSQL 16 only" in r["limitations"]


def test_veeam_object_storage_hardened_and_replica_records_keep_vendor_warnings():
    o = BY["veeam-vbr:object-storage:immutability-bucket-configuration-errors"]
    assert "data loss" in o["operational_risk"] and "lifecycle" in " ".join(o["likely_causes"]).lower()
    h = BY["veeam-vbr:hardened-repository:unsupported-configuration"]
    assert "0700" in " ".join(h["likely_causes"]) and "attack surface" in h["operational_risk"]
    r = BY["veeam-vbr:replication:job-limitations-and-restore-point-loss"]
    assert "21 days" in " ".join(r["likely_causes"]) and "delete" in " ".join(r["likely_causes"]).lower()
    for x in (o, h, r):
        assert "13.1.2.57" in x["version_scope"] and x["parser_mapping"] == "candidate_for_future_integration"


def test_nxos_record_is_nexus7000_scoped_old_page_and_unmapped():
    r = BY["cisco-nxos:ospf:adjacency-problems-nexus-7000"]
    assert "Nexus 7000" in r["version_scope"] and "2013-09-06" in r["version_scope"] and "6.2(2)" in r["version_scope"]
    assert "IOS XE" in r["version_scope"] and r["parser_mapping"] == "missing_parser"
    assert any("event-history adjacency" in c["command"] for c in r["diagnostic_commands"])
    assert "undebugged" in " ".join(c["expected_evidence"] for c in r["diagnostic_commands"]) or "undebugged" in r["operational_risk"]
    assert entry_for_metadata(parse_event_metadata("%OSPF-4-BADLSA: Bad LSA type")) is None


def test_fortios_ha_logging_policy_records_are_620_scoped_and_do_not_invent():
    for cid in ("fortinet-fortios:ha:split-brain-or-formation-failure", "fortinet-fortios:ha:config-out-of-sync",
                "fortinet-fortios:logging:fortianalyzer-connection-check", "fortinet-fortios:firewall:traffic-dropped-no-matching-policy"):
        r = BY[cid]
        assert "6.2.0" in r["version_scope"] and "not established" in r["version_scope"] and "6.2.14" in r["version_scope"]
        assert all("6.2.0" in s["url"] for s in r["official_sources"]) and r["parser_mapping"] == "candidate_for_future_integration"
    assert "no resolution command" in " ".join(BY["fortinet-fortios:ha:config-out-of-sync"]["remediation"])
    assert "policy 0" in " ".join(BY["fortinet-fortios:firewall:traffic-dropped-no-matching-policy"]["alternative_causes"])
    assert "conn_verified=Y" in " ".join(c["expected_evidence"] for c in BY["fortinet-fortios:logging:fortianalyzer-connection-check"]["diagnostic_commands"])


def test_veeam_snapshot_hunter_record_keeps_destructive_consolidation_warning():
    r = BY["veeam-vbr:snapshot:phantom-or-orphaned-vm-snapshots"]
    assert "Delete all snapshots" in r["operational_risk"] and "4 times" in " ".join(r["remediation"]) and "13.1.2.57" in r["version_scope"]


# --- tranche 18: field-linked Fortinet candidates, state candidates, review status -----------------------------------
def _fgt(subtype, action, policyid="0"):
    return (f'date=2026-11-20 time=10:00:00 devname="FGT-SYN" devid="FGT0000000001" logid="0000000013" type="traffic" subtype="{subtype}" '
            f'level="notice" srcip=192.0.2.10 dstip=198.51.100.5 policyid={policyid} service="HTTPS" action="{action}"')


def test_every_candidate_is_pending_human_review_and_none_claims_approval():
    assert all(r.get("review_status") == "PENDING_HUMAN_REVIEW" for r in REC)
    assert all(r["lifecycle_status"] == "candidate" and r["evidence_maturity"] in vd.ALLOWED_MATURITY for r in REC)


def test_policyid_0_local_traffic_is_not_called_implicit_deny():
    text = _fgt("local", "accept")
    meta = parse_event_metadata(text)
    assert meta.attributes["policyid"] == "0" and meta.attributes["subtype"] == "local"
    blob = _cd.catalog_summary("fortinet", text, "en").model_dump_json()
    assert "fortinet-fortios:traffic:policyid-0-local-traffic" in blob and "NOT the same as implicit deny" in blob
    assert "Log fields documented by the vendor" in blob and "Documented possibility, not established" in blob


def test_policyid_0_forward_deny_enriches_the_existing_summary_without_replacing_it():
    text = _fgt("forward", "deny")
    blob = _cd.catalog_summary("fortinet", text, "en").model_dump_json()
    assert "Forward traffic fields describe a session" in blob            # original conclusions kept
    assert "fortinet-fortios:traffic:policyid-0-forward-implicit-deny" in blob and "ret-no-match" in blob


@pytest.mark.parametrize("text", [_fgt("forward", "accept"), _fgt("forward", "deny", policyid="5"), _fgt("local", "accept", policyid="7")])
def test_policyid_0_candidates_do_not_match_other_field_combinations(text):
    sol = _cd.catalog_summary("fortinet", text, "en")
    assert sol is None or "policyid-0" not in sol.model_dump_json()


def test_fortios_620_version_scope_is_never_overclaimed_for_tranche18_records():
    for cid in ("fortinet-fortios:traffic:policyid-0-local-traffic", "fortinet-fortios:traffic:policyid-0-forward-implicit-deny",
                "fortinet-fortios:ha:failover-reason-from-ha-status", "fortinet-fortios:ha:unexpected-failover-causes"):
        r = BY[cid]
        assert "6.2" in r["version_scope"] and ("not established" in r["version_scope"] or "not stated" in r["version_scope"] or "not mentioned" in r["version_scope"])
        assert all(s["url"].startswith("https://community.fortinet.com/") for s in r["official_sources"])
        assert "NOT established" in r["limitations"] or "not established" in r["limitations"]


def test_state_candidates_are_separate_from_log_parser_candidates():
    states = [r for r in REC if r.get("detection_kind") in vd.STATE_KINDS]
    assert {r["candidate_id"] for r in states} >= {"postgresql:replication:slot-retains-wal-filling-pg-wal", "postgresql:replication:standby-lag-measurement",
                                                    "fortinet-fortios:ha:failover-reason-from-ha-status", "fortinet-fortios:ha:unexpected-failover-causes"}
    for r in states:
        assert r["parser_mapping"] in ("state_telemetry_evaluator", "candidate_for_future_integration")
        assert r["detection_signals"] and r["false_positive_risks"] and r["validation_method"] and "documented_thresholds" in r


def test_loader_rejects_state_candidates_that_claim_a_log_parser(tmp_path):
    base = json.loads(json.dumps(BY["postgresql:replication:standby-lag-measurement"]))
    for patch in ({"parser_mapping": "parser_linked_by_message", "documented_messages": ["pg_checkpoint_too_frequent"], "message_mapping_basis": "x"},
                  {"detection_signals": []}, {"false_positive_risks": []}, {"validation_method": ""}, {"evaluator": "does_not_exist"},
                  {"review_status": "APPROVED"}, {"detection_kind": "unknown_kind"}):
        p = tmp_path / "c.json"
        p.write_text(json.dumps({"schema_version": 1, "records": [dict(base, **patch)]}), encoding="utf-8")
        with pytest.raises(ValueError):
            vd.load_diagnostic_candidates(p)
    p = tmp_path / "f.json"
    f = json.loads(json.dumps(BY["fortinet-fortios:traffic:policyid-0-local-traffic"]))
    p.write_text(json.dumps({"schema_version": 1, "records": [dict(f, field_conditions={})]}), encoding="utf-8")
    with pytest.raises(ValueError):
        vd.load_diagnostic_candidates(p)
