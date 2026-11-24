"""Reference records that claim parser_mapped must be reachable through the real parser; nothing else may be."""
import asyncio
import json

import pytest

from backend.domain.analyzer.services import catalog_diagnostics as cd
from backend.domain.analyzer.services import summary
from backend.domain.analyzer.services.operational_catalog import entry_for_metadata
from backend.domain.analyzer.services.parser import parse_event_metadata
from backend.domain.analyzer.services.vendor_reference import REFERENCE_BY_ID, REFERENCE_CATALOG, reference_for_metadata

PG = [r for r in REFERENCE_CATALOG if r["product"] == "PostgreSQL"]
SD = [r for r in REFERENCE_CATALOG if r["product"] == "systemd"]


def pg_line(code, **extra):
    entry = {"timestamp": "2026-11-20 10:00:00.123 UTC", "user": "demo", "dbname": "demo", "pid": 321, "session_id": "s.1",
             "line_num": 1, "error_severity": "ERROR", "state_code": code, "message": "synthetic fixture", "backend_type": "client backend"}
    entry.update(extra)
    return json.dumps(entry)


def systemd_line(status, name, unit="demo.service", kind="Main process", daemon="systemd", code="exited"):
    return f"Nov 20 10:00:00 host-synthetic {daemon}[1]: {unit}: {kind} exited, code={code}, status={status}/{name}"


@pytest.mark.parametrize("rec", [r for r in PG if not r["code"].startswith("00")], ids=lambda r: r["code"])
def test_every_postgres_reference_resolves_from_jsonlog_to_itself(rec):
    meta = parse_event_metadata(pg_line(rec["code"]))
    assert meta.sourceFamily == "json" and meta.provider == "PostgreSQL" and meta.attributes["sqlState"] == rec["code"]
    assert reference_for_metadata(meta)["reference_id"] == rec["reference_id"]
    assert entry_for_metadata(meta) is None  # not a diagnostic-catalog identity


@pytest.mark.parametrize("rec", [r for r in SD if r["code"] != "0"], ids=lambda r: r["code"])
def test_every_systemd_reference_resolves_from_the_printed_status_to_itself(rec):
    printed = rec["name"].removeprefix("EXIT_")
    meta = parse_event_metadata(systemd_line(rec["code"], printed))
    assert meta.sourceFamily == "linux_syslog" and meta.attributes["exitStatus"] == rec["code"]
    assert reference_for_metadata(meta)["reference_id"] == rec["reference_id"]


def test_successful_states_are_not_surfaced():
    assert all(reference_for_metadata(parse_event_metadata(pg_line(r["code"]))) is None for r in PG if r["code"].startswith("00"))
    assert reference_for_metadata(parse_event_metadata(systemd_line("0", "SUCCESS"))) is None


@pytest.mark.parametrize("text", [
    pg_line("40P01", error_severity=None) if False else json.dumps({"state_code": "40P01", "message": "x", "error_severity": "ERROR"}),  # no identity key
    pg_line("40P01").replace('"error_severity"', '"sev"'),   # required key missing
    pg_line("4OP01x"),                                        # malformed SQLSTATE
    pg_line("zz999"),                                         # well formed but undocumented
    json.dumps({"eventId": "40P01", "provider": "app", "message": "deadlock detected"}),  # generic JSON
])
def test_lookalike_json_never_resolves(text):
    assert reference_for_metadata(parse_event_metadata(text)) is None


@pytest.mark.parametrize("text", [
    systemd_line("203", "EXEC", daemon="sshd"),              # not printed by systemd
    systemd_line("9", "KILL", code="killed"),                 # signal, not an exit status
    systemd_line("203", "FOO"),                               # printed name disagrees with the manual
    systemd_line("999", "EXEC"),                              # undocumented status
    "Nov 20 10:00:00 host-synthetic systemd[1]: demo.service: Failed with result 'exit-code'.",  # no explicit status
])
def test_lookalike_systemd_never_resolves(text):
    assert reference_for_metadata(parse_event_metadata(text)) is None


def test_missing_parser_records_are_unreachable_and_state_it():
    for r in REFERENCE_CATALOG:
        if r["parser_mapping"] != "parser_mapped":
            assert r["parser_mapping"] == "missing_parser" and r["product"] not in ("PostgreSQL", "systemd")
            assert r["reference_id"] in REFERENCE_BY_ID


def test_analyzer_summary_path_is_definition_only_for_both_formats():
    for text, family, provider in ((pg_line("23505"), "json", "PostgreSQL"), (systemd_line("203", "EXEC"), "linux_syslog", "Linux/systemd")):
        meta = parse_event_metadata(text)
        sol = asyncio.run(summary.build_summary(meta.eventId, provider, "", [], language="en", source_family=family, evidence_text=text))
        blob = sol.model_dump_json()
        assert "Documented definition (not a diagnosis" in blob and "No root cause is established" in blob
        assert "Definition-only reference" in blob
        assert not any(w in blob.lower() for w in ("restart the", "increase ", "run chkdsk"))  # no invented remediation
        refs = cd.catalog_references(family, text)
        assert refs and refs[0].link.startswith("https://") and refs[0].sourceType == "official"


def test_existing_json_and_syslog_behaviour_is_unchanged():
    generic = json.dumps({"eventId": "1129", "provider": "demo", "message": "Synthetic"})
    meta = parse_event_metadata(generic)
    assert meta.sourceFamily == "json" and meta.provider == "demo" and cd.catalog_summary("json", generic, "en") is None
    ssh = "Oct  8 10:00:00 host-synthetic sshd[10]: Failed password for demo from 192.0.2.10 port 1000 ssh2"
    assert entry_for_metadata(parse_event_metadata(ssh))["diagnostic_code"] == "AUTH-FAIL"
