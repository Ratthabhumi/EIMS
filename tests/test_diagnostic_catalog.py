"""Synthetic, hermetic multi-vendor catalog/parser/API regressions."""
import asyncio
import csv
import io
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.domain.analyzer.services.operational_catalog import (
    CATALOG_PATH, VENDOR_CATALOG_PATH, entry_for_metadata, get_catalog, get_catalog_entry, load_catalog,
)
from backend.domain.analyzer.services.parser import parse_event_metadata
from backend.domain.analyzer.services.panos_parser import panos_records
from backend.domain.analyzer.services.source_classify import classify_source
from backend.domain.analyzer.services.catalog_diagnostics import catalog_references
from backend.domain.analyzer.services import summary, vector_db
from backend.api.routers.analyzer import history


def pan_fixture(typ, **overrides):
    # Documentation-shaped values, no workplace records or real identifiers.
    n = {"TRAFFIC": 53, "THREAT": 60, "SYSTEM": 23, "CONFIG": 14}[typ]
    f = [""] * n
    f[:7] = ["1", "2026/10/08 10:00:00", "000000000001", typ,
             {"TRAFFIC": "end", "THREAT": "vulnerability", "SYSTEM": "general", "CONFIG": "0"}[typ], "0", "2026/10/08 10:00:00"]
    if typ in ("TRAFFIC", "THREAT"):
        for i, v in {7:"192.0.2.10",8:"198.51.100.20",11:"Synthetic, rule",14:"web-browsing",30:"deny"}.items():
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


@pytest.mark.parametrize("typ", ["TRAFFIC", "THREAT", "SYSTEM", "CONFIG"])
def test_pan_core_and_syslog_prefix(typ):
    text = pan_fixture(typ)
    for prefix in ("", "<134>Oct  8 10:00:00 PAN-SYNTHETIC ", "<134>1 2026-10-08T10:00:00Z PAN-SYNTHETIC app - - - "):
        meta = parse_event_metadata(prefix + text)
        assert meta.sourceFamily == "palo_alto"
        assert meta.diagnosticCode == typ
        assert meta.attributes["raw"] == prefix + text
        assert meta.attributes["lineNumber"] == 1
        assert "timezoneUncertainty" in meta.attributes
        assert entry_for_metadata(meta)["diagnostic_code"] == typ
        if typ in ("TRAFFIC", "THREAT"):
            assert meta.attributes["rule"] == "Synthetic, rule"
        if typ == "SYSTEM":
            assert meta.eventId == "1129"
            assert meta.attributes["description"] == 'Synthetic message, with "quotes"'
        if typ == "CONFIG":
            assert meta.attributes["result"] == "Succeeded"
            assert meta.attributes["command"] == "edit"


@pytest.mark.parametrize("typ,minimum", [("TRAFFIC",31),("THREAT",35),("SYSTEM",15),("CONFIG",14)])
def test_pan_optional_tail_absent(typ, minimum):
    f = next(csv.reader([pan_fixture(typ)]))[:minimum]
    out = io.StringIO()
    csv.writer(out, lineterminator="").writerow(f)
    assert parse_event_metadata(out.getvalue()).sourceFamily == "palo_alto"
    assert parse_event_metadata(out.getvalue()).computer == "000000000001"


@pytest.mark.parametrize("text", ["TRAFFIC deny", "palo alto Event ID: 1129", "1,bad,serial,SYSTEM,general,0,bad",
    pan_fixture("SYSTEM", **{"2":"not-a-serial"}), pan_fixture("SYSTEM", **{"13":"wrong"}),
    pan_fixture("TRAFFIC", **{"7":"not-an-ip"}), pan_fixture("CONFIG", **{"12":"unknown"}),
    pan_fixture("SYSTEM") + ',"unterminated', pan_fixture("SYSTEM") + "\nunrelated text"])
def test_invalid_pan_safe_unknown(text):
    assert not panos_records(text)
    assert parse_event_metadata(text).sourceFamily == "unknown_text"


def test_exact_windows_preservation_and_counts():
    original = json.loads(Path(CATALOG_PATH).read_text(encoding="utf-8"))
    windows = get_catalog("windows_event")
    assert len(windows) == len(original) == 141
    for old, entry in zip(original, windows):
        assert all(entry[key] == value for key, value in old.items())
    assert Counter(e["source_family"] for e in get_catalog()) == {
        "windows_event":141,"veeam_vbr":4,"vmware":2,"fortinet":5,"cisco_asa":6,"palo_alto":4,"linux_syslog":1}
    assert get_catalog("json") == []
    assert len({e["catalog_id"] for e in get_catalog()}) == len(get_catalog())
    assert get_catalog_entry("1129")["category"] == "Group Policy"
    assert get_catalog_entry("1129", "palo_alto") is None
    assert get_catalog_entry("106023", "cisco_asa", "official_message_id")
    assert get_catalog_entry("106023", "windows_event") is None
    assert get_catalog_entry("TRAFFIC", "palo_alto", "official_event_id") is None
    mutated = get_catalog()
    mutated[0]["title"] = "bad"
    assert get_catalog()[0]["title"] != "bad"


@pytest.mark.parametrize("fault", ["version", "not_list", "duplicate", "missing", "bad_reference", "bad_steps", "redefine_windows"])
def test_malformed_catalog_rejected(tmp_path, fault):
    data = json.loads(Path(VENDOR_CATALOG_PATH).read_text())
    if fault == "version": data["schema_version"] = 99
    elif fault == "not_list": data["entries"] = {}
    elif fault == "duplicate": data["entries"].append(data["entries"][0])
    elif fault == "missing": del data["entries"][0]["diagnostic_code"]
    elif fault == "bad_reference": data["entries"][0]["official_references"] = [{"url":"javascript:bad"}]
    elif fault == "bad_steps": data["entries"][0]["investigation_steps"] = [None]
    else: data["entries"][0]["source_family"] = "windows_event"
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError): load_catalog(CATALOG_PATH, path)


@pytest.mark.parametrize("code", ["traffic/forward", "utm/ips", "event/vpn", "event/user", "event/system"])
def test_fortinet_metadata_and_category(code):
    typ, sub = code.split("/")
    text = f'date=2026-10-08 time=10:00:00 devname="FG-SYNTHETIC" logid="0000000000" type="{typ}" subtype="{sub}" level="warning" action="deny" srcip=192.0.2.10 dstip=198.51.100.20 service="HTTPS" policyid=9 msg="Synthetic observation"'
    meta = parse_event_metadata(text)
    assert meta.sourceFamily == "fortinet"
    assert not meta.isCritical
    assert meta.eventId == "0000000000"
    assert meta.attributes["policyid"] == "9"
    assert entry_for_metadata(meta)["diagnostic_code"] == code
    sol = asyncio.run(summary.build_summary(meta.eventId, meta.provider, "", [], language="en", source_family=meta.sourceFamily, evidence_text=text))
    assert "No root cause" in sol.causes[0]
    assert not any("Group Policy" in v for v in sol.steps)


@pytest.mark.parametrize("code,sev", [("106023",4),("106024",2),("113005",6),("113019",4),("302013",6),("302014",6)])
def test_cisco_product_scope(code, sev):
    for product in ("ASA", "FTD", "PIX"):
        text = f"%{product}-{sev}-{code}: Synthetic documented-message fixture"
        meta = parse_event_metadata(text)
        assert meta.eventId == code
        assert meta.attributes["severity"] == sev
        assert bool(entry_for_metadata(meta)) == (product == "ASA")


def test_windows_linux_json_and_mixed_guardrails(monkeypatch):
    monkeypatch.setattr(summary, "_translate", lambda text, language: text)
    win = "Event ID: 1129\nSource: Microsoft-Windows-GroupPolicy\nLevel: Error"
    assert parse_event_metadata(win).sourceFamily == "windows_event"
    linux = "Oct  8 10:00:00 host-synthetic sshd[10]: Failed password for demo from 192.0.2.10 port 1000 ssh2"
    assert entry_for_metadata(parse_event_metadata(linux))["diagnostic_code"] == "AUTH-FAIL"
    assert entry_for_metadata(parse_event_metadata(linux.replace("sshd", "app"))) is None
    json_text = '{"eventId":"1129","provider":"demo","message":"Synthetic"}'
    assert parse_event_metadata(json_text).sourceFamily == "json"
    assert entry_for_metadata(parse_event_metadata(json_text)) is None
    for text in (win + "\n%ASA-4-106023: Synthetic", win + "\nlogid=1129 type=traffic subtype=forward", pan_fixture("SYSTEM") + "\n%ASA-4-106023: Synthetic"):
        meta = parse_event_metadata(text)
        assert meta.sourceFamily == "unknown_text"
        assert catalog_references("palo_alto", text) == []
    sol = asyncio.run(summary.build_summary("1129", "PAN-OS", "", [], language="en", source_family="palo_alto", evidence_text=pan_fixture("SYSTEM")))
    assert "Group Policy" not in sol.model_dump_json()
    assert "session/job failed" not in sol.model_dump_json()
    assert "PAN-OS" in summary._family_query("1129", "PAN-OS", "palo_alto")
    assert "Windows" not in summary._family_query("1129", "PAN-OS", "palo_alto")
    assert summary._classify_source("https://community.paloaltonetworks.com/a", "official", summary.FAMILY_OFFICIAL_DOMAINS["palo_alto"]) == "REJECT"
    for family in ("json", "palo_alto"):
        sol = asyncio.run(summary.build_summary("1129", "demo", "", [], language="en", source_family=family, diagnostic_code="VEEAM-SESSION-FAILED"))
        assert "Group Policy" not in sol.model_dump_json()
        assert "completed with" not in sol.overview


def test_panos_rag_isolation():
    allowed = vector_db._is_usable_knowledge_row
    row = {"_knowledge":{"sourceFamily":"windows_event","diagnosticIdentity":"1129"}}
    assert not allowed("1129", 5, "1129", "palo_alto", 0.01, row_solution_json=row)
    assert not allowed("1129", 5, "1129", "palo_alto", 0.01, row_solution_json=None)


def test_catalog_api_filters_and_history_totals():
    response = asyncio.run(history.get_operational_catalog(_user="demo", source_family="palo_alto"))
    assert response["count"] == 4
    assert response["classification"] == "OPERATIONAL_EVENT_CATALOG"
    rows = []
    for text in (pan_fixture("SYSTEM"), 'logid=4625 type=traffic subtype=forward level=warning devname=FG-SYNTHETIC'):
        meta = parse_event_metadata(text)
        rows.append(SimpleNamespace(id=len(rows)+1, event_id=meta.eventId, provider=meta.provider,
            event_metadata=meta.model_dump(), created_at=datetime.now(timezone.utc), search_time_ms=0,
            solution_summary={}, parse_method="text", description="Synthetic", ai_summary="", search_results=[],
            username="demo", feedback_by=None, feedback_score=None))
    class DB:
        async def execute(self, stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))
    legacy = SimpleNamespace(**vars(rows[0]))
    legacy.id, legacy.provider, legacy.event_metadata = 3, "Palo Alto Security", {}
    rows.append(legacy)
    stats = asyncio.run(history.get_history_stats(db=DB(), _user="demo"))
    assert stats["totalLogs"] == 3
    assert all(c["name"] != "Group Policy" and c["name"] != "Authentication" for c in stats["categoryStats"])
    assert {c["name"]:c["value"] for c in stats["categoryStats"]}["Unclassified"] == 1
    reloaded = asyncio.run(history.get_all_history(db=DB(), _user="demo"))
    assert reloaded[0]["eventMetadata"].sourceFamily == "palo_alto"
    assert reloaded[0]["eventMetadata"].attributes["eventId"] == "1129"


@pytest.mark.parametrize("typ", ["TRAFFIC", "THREAT", "SYSTEM", "CONFIG"])
def test_panos_csv_upload_preserves_csv(typ):
    from backend.api.routers.analyzer.analyze import _process_upload
    text = pan_fixture(typ)
    extracted, method = _process_upload(text.encode(), "pan-synthetic.csv", "text/csv")
    assert extracted == text
    assert "PAN-OS" in method
    assert parse_event_metadata(extracted).sourceFamily == "palo_alto"


@pytest.mark.parametrize("language", ["en", "th"])
def test_synthetic_raw_upload_reload_followup(language, monkeypatch):
    """Actual router workflow with an in-memory DB substitute, no production claims."""
    from backend.api.routers.analyzer import analyze
    from backend.domain.analyzer.schemas.analyze import FollowUpRequest
    async def no_export(**kwargs): pass
    monkeypatch.setattr(vector_db, "add_solution", no_export)
    monkeypatch.setattr(analyze, "search_solutions", lambda *args, **kwargs: (catalog_references(kwargs.get("source_family"), kwargs.get("evidence_text", "")), ""))
    class DB:
        def add(self, record): self.record = record
        async def commit(self): pass
        async def refresh(self, record): record.id = 99
        async def execute(self, stmt): return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: self.record))
    db = DB()
    result = asyncio.run(analyze.submit_analysis(text=pan_fixture("SYSTEM"), file=None, language=language, db=db, _user="demo", x_gemini_api_key=None))
    assert result.eventMetadata.sourceFamily == "palo_alto"
    assert result.historyId == 99
    assert db.record.event_metadata["attributes"]["eventId"] == "1129"
    answer = asyncio.run(analyze.followup_question(FollowUpRequest(question="How to investigate?", historyId=99, language=language), _user="demo", db=db, x_gemini_api_key=None))
    assert "Group Policy" not in answer.answer
    assert answer.answer


def test_windows_xml_upload_and_invalid_evtx_safe():
    from backend.api.routers.analyzer.analyze import _process_upload
    xml = '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event"><System><Provider Name="Microsoft-Windows-GroupPolicy"/><EventID>1129</EventID><Level>2</Level><Channel>System</Channel><Computer>WIN-SYNTHETIC</Computer></System></Event>'
    extracted, _ = _process_upload(xml.encode(), "synthetic.xml", "text/xml")
    meta = parse_event_metadata(extracted)
    assert meta.sourceFamily == "windows_event" and meta.eventId == "1129"
    with pytest.raises(ValueError):
        _process_upload(b"invalid synthetic bytes", "synthetic.evtx", "application/octet-stream")


def test_windows_and_veeam_bundle_router_workflows(monkeypatch):
    from fastapi import UploadFile
    from backend.api.routers.analyzer import analyze
    from tests.test_analyzer_reliability import WIN1129_TEXT, VEEAM_RAW_TEXT, VMWARE_CTK_TEXT
    async def no_export(**kwargs): pass
    async def no_retrieval(**kwargs): return []
    monkeypatch.setattr(summary, "search_similar_logs", no_retrieval)
    monkeypatch.setattr(vector_db, "add_solution", no_export)
    monkeypatch.setattr(analyze, "search_solutions", lambda *args, **kwargs: ([], ""))
    class DB:
        def add(self, record): self.record = record
        async def commit(self): pass
        async def refresh(self, record): record.id = 77
    db = DB()
    win = asyncio.run(analyze.submit_analysis(text=WIN1129_TEXT, file=None, language="en", db=db, _user="demo", x_gemini_api_key=None))
    assert win.eventMetadata.sourceFamily == "windows_event"
    assert win.eventMetadata.provider == "Microsoft-Windows-GroupPolicy"
    assert get_catalog_entry(win.eventId)["category"] == "Group Policy"
    bundle = asyncio.run(analyze.submit_bundle(files=[
        UploadFile(filename="veeam-synthetic.log", file=io.BytesIO(VEEAM_RAW_TEXT.encode())),
        UploadFile(filename="vmware-synthetic.log", file=io.BytesIO(VMWARE_CTK_TEXT.encode())),
    ], language="en", db=db, _user="demo", x_gemini_api_key=None))
    assert {f.sourceFamily for f in bundle.files} == {"veeam_vbr", "vmware"}
    assert bundle.solutionSummary.incident.firstMeaningfulFailure
    assert bundle.solutionSummary.incident.terminalFailure
    assert bundle.solutionSummary.evidenceItems
    assert all(e.sourceFile and e.lineNumber > 0 for e in bundle.solutionSummary.evidenceItems)
    assert "Group Policy" not in bundle.solutionSummary.model_dump_json()
    assert db.record.event_metadata["attributes"]["bundle"]["files"]
