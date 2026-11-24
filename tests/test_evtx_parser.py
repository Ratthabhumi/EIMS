from collections import Counter
import hashlib
from pathlib import Path
import sys
import types

import pytest

from backend.domain.telemetry.evtx_parser import parse_evtx_records


def test_real_public_evtx_binary_fixture_matches_native_and_eims_records():
    from Evtx.Evtx import Evtx

    fixture = Path(__file__).parent / "fixtures" / "evtx" / "system.evtx"
    content = fixture.read_bytes()
    assert hashlib.md5(content).hexdigest() == "182de19fe6a25b928a34ad59af0bbf1e"
    assert hashlib.sha256(content).hexdigest() == "ccb83cfefc9038017224cd97b800b66e248fe14529649ddf47907e5a2021449e"

    with Evtx(str(fixture)) as native_log:
        native_count = sum(1 for _ in native_log.records())
    records = list(parse_evtx_records(content))

    assert native_count == 1601
    assert len(records) == native_count
    assert not any("parse_error" in record for record in records)
    event_ids = Counter(record["event_id"] for record in records)
    assert {7036, 7040, 6013, 7045}.issubset(event_ids)


def test_parser_uses_private_temp_file_for_python_evtx(monkeypatch):
    content = b"synthetic-evtx-binary"
    xml = """<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event"><System><EventID>1129</EventID><Level>2</Level><Channel>System</Channel><TimeCreated SystemTime="2026-11-13T10:00:00Z" /></System><EventData><Data Name="WorkstationName">EIMS-SYNTHETIC</Data></EventData></Event>"""
    observed = {}

    class FakeRecord:
        def xml(self):
            return xml

    class FakeEvtx:
        def __init__(self, path):
            observed["path"] = Path(path)
            assert observed["path"].is_file()
            assert observed["path"].read_bytes() == content
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def records(self):
            return [FakeRecord()]

    package = types.ModuleType("Evtx")
    module = types.ModuleType("Evtx.Evtx")
    module.Evtx = FakeEvtx
    monkeypatch.setitem(sys.modules, "Evtx", package)
    monkeypatch.setitem(sys.modules, "Evtx.Evtx", module)

    records = list(parse_evtx_records(content))

    assert records[0]["event_id"] == 1129
    assert records[0]["severity"] == "Error"
    assert records[0]["metadata"]["workstation_name"] == "EIMS-SYNTHETIC"
    assert not observed["path"].exists()


def _parse(monkeypatch, *xmls):
    class FakeRecord:
        def __init__(self, xml):
            self._xml = xml
        def xml(self):
            if isinstance(self._xml, Exception):
                raise self._xml
            return self._xml

    class FakeEvtx:
        def __init__(self, path):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def records(self):
            return [FakeRecord(x) for x in xmls]

    module = types.ModuleType("Evtx.Evtx")
    module.Evtx = FakeEvtx
    monkeypatch.setitem(sys.modules, "Evtx", types.ModuleType("Evtx"))
    monkeypatch.setitem(sys.modules, "Evtx.Evtx", module)
    return list(parse_evtx_records(b"synthetic"))


def _event(system="", body="", time='<TimeCreated SystemTime="2026-11-13T10:00:00Z" />', event_id="4625"):
    return ('<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event"><System>'
            f'<EventID>{event_id}</EventID><Channel>Security</Channel>{time}{system}</System>{body}</Event>')


def test_unnamed_event_data_values_are_kept_in_order(monkeypatch):
    [record] = _parse(monkeypatch, _event(
        body='<EventData><Data>first</Data><Data Name="Named">n</Data><Data /><Data>third</Data></EventData>'))
    assert record["metadata"]["evtx_event_data_values"] == ["first", "", "third"]
    assert record["metadata"]["Named"] == "n"


def test_user_data_is_nested_not_flattened(monkeypatch):
    body = ('<UserData><LogFileCleared xmlns="urn:synthetic-provider">'
            '<SubjectUserName>synthetic-admin</SubjectUserName>'
            '<Item k="1">a</Item><Item>b</Item></LogFileCleared></UserData>')
    [record] = _parse(monkeypatch, _event(body=body))
    meta = record["metadata"]
    assert "SubjectUserName" not in meta and "Item" not in meta
    cleared = meta["evtx_user_data"]["LogFileCleared"]
    assert cleared["@xmlns"] == "urn:synthetic-provider"
    assert cleared["SubjectUserName"] == "synthetic-admin"
    assert cleared["Item"] == [{"@k": "1", "#text": "a"}, "b"]


def test_level_zero_audit_failure_keywords_and_unknown_level(monkeypatch):
    audit_failure, level_seven, no_level = _parse(
        monkeypatch,
        _event("<Level>0</Level><Keywords>0x8010000000000000</Keywords>"),
        _event("<Level>7</Level><Keywords>0x8020000000000000</Keywords>"),
        _event())
    assert audit_failure["severity"] == "LogAlways"
    assert audit_failure["metadata"]["evtx_level"] == "0"
    assert audit_failure["metadata"]["evtx_keywords"] == "0x8010000000000000"
    assert audit_failure["metadata"]["evtx_audit_result"] == "Audit Failure"
    assert level_seven["severity"] == "Unknown"
    assert level_seven["metadata"]["evtx_level"] == "7"
    assert level_seven["metadata"]["evtx_audit_result"] == "Audit Success"
    assert no_level["severity"] == "Unknown"
    assert "evtx_keywords" not in no_level["metadata"]


def test_missing_time_and_bad_records_do_not_drop_neighbours(monkeypatch):
    records = _parse(
        monkeypatch,
        _event(time=""),
        _event(time='<TimeCreated SystemTime="  " />'),
        "<not-xml",
        ValueError("synthetic-corrupt-record"),
        _event("<Level>4</Level>"))
    assert [r["occurrence_time"] for r in records[:2]] == ["", ""]
    assert records[2] == {"parse_error": "xml-parse-error"}
    assert records[3] == {"parse_error": "record-unreadable:ValueError"}
    assert records[4]["occurrence_time"] == "2026-11-13T10:00:00Z"
    assert records[4]["severity"] == "Information"


# --- reliability contracts -----------------------------------------------------------

def _install_fake_evtx(monkeypatch, records_factory):
    class FakeRecord:
        def __init__(self, xml):
            self._xml = xml

        def xml(self):
            return self._xml

    class FakeEvtx:
        def __init__(self, path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def records(self):
            return records_factory(FakeRecord)

    module = types.ModuleType("Evtx.Evtx")
    module.Evtx = FakeEvtx
    monkeypatch.setitem(sys.modules, "Evtx", types.ModuleType("Evtx"))
    monkeypatch.setitem(sys.modules, "Evtx.Evtx", module)


def test_mid_iteration_failure_keeps_parsed_records_and_yields_sentinel(monkeypatch):
    def factory(record_cls):
        yield record_cls(_event("<Level>2</Level>"))
        yield record_cls(_event("<Level>4</Level>"))
        raise RuntimeError("synthetic-chunk-corruption")

    _install_fake_evtx(monkeypatch, factory)
    records = list(parse_evtx_records(b"synthetic"))
    assert len(records) == 3
    assert [r["severity"] for r in records[:2]] == ["Error", "Information"]
    assert records[2] == {"parse_error": "iteration-failed:RuntimeError"}


def test_records_call_failure_yields_single_sentinel(monkeypatch):
    def factory(record_cls):
        raise OSError("synthetic-open-failure")

    _install_fake_evtx(monkeypatch, factory)
    assert list(parse_evtx_records(b"synthetic")) == [{"parse_error": "iteration-failed:OSError"}]


@pytest.mark.parametrize("bad", ["１２３", "٣", "²", "12 3", "+4625", "-1", "0x10", "", "1" * 11])
def test_event_id_must_be_ascii_decimal(monkeypatch, bad):
    [record] = _parse(monkeypatch, _event(event_id=bad))
    assert record == {"parse_error": "invalid-event-id"}


def test_ascii_event_id_is_accepted(monkeypatch):
    [record] = _parse(monkeypatch, _event(event_id=" 4625 "))
    assert record["event_id"] == 4625


def test_deep_user_data_failure_is_isolated_to_its_record(monkeypatch):
    deep = "<a>" * 60 + "x" + "</a>" * 60
    before, deep_record, after = _parse(
        monkeypatch,
        _event("<Level>2</Level>"),
        _event("<Level>3</Level>", body=f"<UserData>{deep}</UserData>"),
        _event("<Level>4</Level>"))
    assert before["severity"] == "Error" and after["severity"] == "Information"
    assert deep_record["severity"] == "Warning" and deep_record["event_id"] == 4625
    assert "evtx_user_data" not in deep_record["metadata"]
    assert deep_record["metadata"]["evtx_user_data_error"] == "ValueError"


def test_duplicate_event_data_names_are_preserved_not_overwritten(monkeypatch):
    [record] = _parse(monkeypatch, _event(body=(
        '<EventData><Data Name="TargetUserName">first</Data>'
        '<Data Name="TargetUserName">second</Data>'
        '<Data Name="TargetUserName">third</Data></EventData>')))
    meta = record["metadata"]
    assert meta["TargetUserName"] == "first" and meta["target_user_name"] == "first"
    assert meta["evtx_event_data_conflicts"] == {"TargetUserName": ["second", "third"]}


def test_event_data_cannot_spoof_reserved_metadata(monkeypatch):
    [record] = _parse(monkeypatch, _event(
        "<Level>2</Level><Keywords>0x8010000000000000</Keywords>",
        body=('<EventData><Data Name="evtx_level">9</Data>'
              '<Data Name="EVTX_audit_result">Audit Success</Data>'
              '<Data Name="evtx_computer">spoofed</Data>'
              '<Data Name="source_network_ip">6.6.6.6</Data>'
              '<Data Name="target_user_name">spoofed-user</Data>'
              '<Data Name="WorkstationName">real-ws</Data></EventData>')))
    meta = record["metadata"]
    assert meta["evtx_level"] == "2"
    assert meta["evtx_audit_result"] == "Audit Failure"
    assert "EVTX_audit_result" not in meta and "evtx_computer" not in meta
    assert "source_network_ip" not in meta and "target_user_name" not in meta
    assert meta["workstation_name"] == "real-ws"
    assert meta["evtx_event_data_conflicts"] == {
        "evtx_level": ["9"], "EVTX_audit_result": ["Audit Success"], "evtx_computer": ["spoofed"],
        "source_network_ip": ["6.6.6.6"], "target_user_name": ["spoofed-user"]}


def test_system_metadata_is_preserved_under_namespaced_keys(monkeypatch):
    system = ('<Provider Name="Microsoft-Windows-Security-Auditing" Guid="{synthetic}" />'
              '<EventRecordID>4242</EventRecordID>'
              '<Execution ProcessID="652" ThreadID="1024" />'
              '<Computer>EIMS-SYNTHETIC-DC</Computer>'
              '<Security UserID="S-1-5-18" />')
    body = ('<EventData><Data Name="TargetUserName">synthetic-user</Data>'
            '<Data Name="WorkstationName">WS-1</Data>'
            '<Data Name="IpAddress">203.0.113.7</Data></EventData>')
    [record] = _parse(monkeypatch, _event(system, body))
    meta = record["metadata"]
    assert meta["evtx_provider_name"] == "Microsoft-Windows-Security-Auditing"
    assert meta["evtx_computer"] == "EIMS-SYNTHETIC-DC"
    assert meta["evtx_event_record_id"] == "4242"
    assert meta["evtx_execution"] == {"ProcessID": "652", "ThreadID": "1024"}
    assert meta["evtx_security_user_id"] == "S-1-5-18"
    # canonical extraction still works
    assert meta["target_user_name"] == "synthetic-user"
    assert meta["workstation_name"] == "WS-1"
    assert meta["source_network_ip"] == "203.0.113.7"
    assert "evtx_event_data_conflicts" not in meta


def test_winlog_timestamp_requires_timezone_and_normalizes_to_utc():
    from datetime import UTC, datetime
    from pydantic import ValidationError
    import pytest
    from backend.domain.telemetry.schemas import AgentWinlogRequest

    base = {"event_id": 4625, "severity": "Information", "event_channel": "Security", "metadata": {}}
    with pytest.raises(ValidationError, match="timezone offset"):
        AgentWinlogRequest(occurrence_time="2026-11-14T10:00:00", **base)
    payload = AgentWinlogRequest(occurrence_time="2026-11-14T17:00:00+07:00", **base)
    assert payload.occurrence_time == datetime(2026, 11, 14, 10, 0, tzinfo=UTC)
