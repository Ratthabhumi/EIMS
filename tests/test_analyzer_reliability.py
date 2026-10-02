"""Analyzer Reliability Upgrade — multi-source regression suite.

All fixtures are SANITIZED SYNTHETIC data shaped like observed incidents.
No real customer/company logs, hostnames, IPs, UUIDs, or credentials.
No network, no Gemini, no live DB: embeddings and DB sessions are faked.
"""

import asyncio

import pytest

from backend.domain.analyzer.schemas.analyze import EventMetadata, SolutionSummary
from backend.domain.analyzer.services import summary as summary_mod
from backend.domain.analyzer.services import vector_db as vector_db_mod
from backend.domain.analyzer.services.bundle import (
    BUNDLE_MAX_FILE_BYTES,
    BUNDLE_MAX_FILES,
    BUNDLE_MAX_TOTAL_BYTES,
    correlate_bundle,
    sha256_hex,
    summarize_file_evidence,
    validate_bundle,
)
from backend.domain.analyzer.services.compaction import MAX_CHARS, compact_log_evidence
from backend.domain.analyzer.services.incident_extract import extract_incident
from backend.domain.analyzer.services.parser import parse_event_metadata
from backend.domain.analyzer.services.source_classify import classify_source
from backend.domain.analyzer.services.vendor_knowledge import (
    get_vendor_summary,
    vendor_reference_results,
)
from backend.domain.analyzer.services.vendor_parsers import (
    html_to_text,
    is_vendor_diagnostic_code,
    parse_syslog_hinted,
    parse_veeam,
)

# ---------------------------------------------------------------------------
# Sanitized synthetic fixtures (structure only, fake hosts/IDs)
# ---------------------------------------------------------------------------

WIN1129_TEXT = """Log Name:      System
Source:        Microsoft-Windows-GroupPolicy
Date:          2026-09-10 08:14:22
Event ID:      1129
Task Category: None
Level:         Error
Computer:      SRV-TEST-01.example.local
Description:
The processing of Group Policy failed because of lack of network connectivity to a domain controller.
"""

VEEAM_RAW_TEXT = """[2026-09-12 02:11:03] <01> Info     [Veeam.Backup.Core] Job Type: Replica, Job Target Type: VMware vSphere
[2026-09-12 02:11:04] <07> Info     [VimApi] Processing object 'REPLICA-TEST-VM-01'
[2026-09-12 02:11:05] <07> Info     [Veeam.Backup.Core] Successfully connected to the replica target
[2026-09-12 02:12:41] <07> Error    [CViSnapReplica] Could not delete change tracking file
[2026-09-12 02:12:41] <07> Warning  [VimApi] Deleting helper snapshot, retry is not required
[2026-09-12 02:14:02] <09> Info     [Veeam.Backup.Core] Task session retry 1/3
[2026-09-12 02:15:44] <09> Error    [CViSnapReplica] RevertSnapshot failed: InvalidSnapshotFormat
[2026-09-12 02:15:44] <09> Error    [CViSnapReplica] Detected an invalid snapshot configuration
[2026-09-12 02:15:44] <09> Error    [VimApi] A required file was not found
[2026-09-12 02:15:45] <11> Error    [Veeam.Backup.Core] Processing finished with errors
"""

VEEAM_HTML_TEXT = """<html><head><title>Session Report</title></head><body>
<h1>Veeam Backup &amp; Replication — Replication Job TEST-REPLICA-01</h1>
<table><tr><td>02:12:41</td><td>Error</td><td>Could not delete change tracking file</td></tr>
<tr><td>02:12:41</td><td>Warning</td><td>Deleting helper snapshot</td></tr>
<tr><td>02:15:44</td><td>Error</td><td>RevertSnapshot failed: InvalidSnapshotFormat</td></tr>
<tr><td>02:15:44</td><td>Error</td><td>Detected an invalid snapshot configuration</td></tr>
<tr><td>02:15:44</td><td>Error</td><td>A required file was not found</td></tr>
<tr><td>02:15:45</td><td>Error</td><td>Processing finished with errors</td></tr></table>
<script>var x = 1;</script>
</body></html>
"""

VMWARE_CTK_TEXT = """2026-09-12T02:12:41.123Z In(05) vmx - DISKLIB-CTK: Could not delete change tracking file
2026-09-12T02:12:41.124Z In(05) vmx - DISKLIB-LIB_BLOCKTRACK: CTK_CTKUNLINK result:2620
2026-09-12T02:12:42.001Z In(05) vmx - Snapshot consolidation failed
"""

VMWARE_MISSING_TEXT = """2026-09-12T02:15:44.001Z Er(02) vmx - SNAPSHOT: RevertSnapshot failed with InvalidSnapshotFormat
2026-09-12T02:15:44.002Z Er(02) vmx - SNAPSHOT: A required file was not found
"""

FORTINET_TEXT = (
    'date=2026-09-12 time=02:11:03 devname="FG-TEST-01" logid="0000000013" '
    'type="traffic" subtype="forward" level="notice" action="accept" '
    'srcip=10.0.0.5 dstip=8.8.8.8 service="DNS" msg="DNS query allowed" policyid=1'
)

CISCO_TEXT = (
    'Sep 12 02:11:03 ASA-TEST-01 %ASA-4-106023: Deny tcp src inside:10.0.0.5/52341 '
    'dst outside:93.184.216.34/443 by access-group "OUTSIDE-IN"'
)

LINUX_TEXT = (
    "Sep 12 02:11:03 testhost sshd[1234]: Failed password for invalid user "
    "operator from 10.0.0.9 port 51234 ssh2"
)

UNKNOWN_TEXT = (
    "The quarterly inventory list needs stapler refills and the cafeteria "
    "menu changed on Friday. Nothing to see here."
)

FORBIDDEN_VEEAM_TOKENS = (
    "1129",
    "GroupPolicy",
    "DCOM",
    "Reddit",
    "learn.microsoft.com",
)


# ---------------------------------------------------------------------------
# Fakes (no DB, no embedding downloads, no network)
# ---------------------------------------------------------------------------


class _FakeRow:
    def __init__(self, event_id, feedback_score, solution_json):
        self.event_id = event_id
        self.feedback_score = feedback_score
        self.solution_json = solution_json


class _FakeResult:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single

    def all(self):
        return self._rows

    def scalars(self):
        return self

    def first(self):
        return self._single


class _FakeDB:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single
        self.added = []
        self.commits = 0

    async def execute(self, query):
        return _FakeResult(rows=self._rows, single=self._single)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        pass


@pytest.fixture
def no_embeddings(monkeypatch):
    monkeypatch.setattr(vector_db_mod, "_get_embedding", lambda *a, **k: [0.1] * 384)


# ---------------------------------------------------------------------------
# 1. Windows 1129 must remain Windows/GroupPolicy
# ---------------------------------------------------------------------------


def test_windows_1129_stays_windows_grouppolicy():
    meta = parse_event_metadata(WIN1129_TEXT)
    assert meta.sourceFamily == "windows_event"
    assert meta.eventId == "1129"
    assert "GroupPolicy" in meta.provider


def test_historical_metadata_still_deserializes():
    meta = EventMetadata(**{
        "eventId": "1129",
        "provider": "Microsoft-Windows-GroupPolicy",
        "level": "Error",
        "logName": "System",
        "timestamp": "2026-09-10",
        "computer": "SRV-TEST-01",
        "isCritical": True,
        "faultingApp": "",
    })
    assert meta.sourceFamily == ""
    assert meta.diagnosticCode == ""
    old = SolutionSummary(**{"overview": "o", "causes": ["c"], "steps": ["s"]})
    assert old.evidence == [] and old.confidence == ""


# ---------------------------------------------------------------------------
# 2-5. Veeam / VMware adapters
# ---------------------------------------------------------------------------


def test_veeam_raw_replication_log_diagnostic_chain():
    meta = parse_event_metadata(VEEAM_RAW_TEXT)
    assert meta.sourceFamily == "veeam_vbr"
    assert meta.product == "Veeam Backup & Replication"
    assert meta.diagnosticCode == "VEEAM-REPLICA-SNAPSHOT-CHAIN"
    assert meta.eventId == "VEEAM-REPLICA-SNAPSHOT-CHAIN"
    blob = " ".join([meta.provider, meta.logName])
    for token in ("1129", "GroupPolicy", "DCOM"):
        assert token not in blob


def test_veeam_html_report_same_failure_sequence():
    text = html_to_text(VEEAM_HTML_TEXT)
    assert "var x = 1" not in text  # script stripped
    assert "Could not delete change tracking file" in text
    meta = parse_veeam(text, "session-report.html")
    assert meta.sourceFamily == "veeam_vbr"
    assert meta.diagnosticCode == "VEEAM-REPLICA-SNAPSHOT-CHAIN"


def test_vmware_ctk_result_2620():
    meta = parse_event_metadata(VMWARE_CTK_TEXT)
    assert meta.sourceFamily == "vmware"
    assert meta.diagnosticCode == "VMWARE-CBT-DELETE-FAILED"


def test_vmware_snapshot_missing_file():
    meta = parse_event_metadata(VMWARE_MISSING_TEXT)
    assert meta.sourceFamily == "vmware"
    assert meta.diagnosticCode == "VMWARE-SNAPSHOT-FILE-MISSING"


def test_vendor_code_predicate():
    assert is_vendor_diagnostic_code("VEEAM-REPLICA-SNAPSHOT-CHAIN")
    assert not is_vendor_diagnostic_code("1129")
    assert not is_vendor_diagnostic_code("Unknown")


# ---------------------------------------------------------------------------
# 6-8. Existing families do not regress
# ---------------------------------------------------------------------------


def test_fortinet_sample_unchanged():
    meta = parse_event_metadata(FORTINET_TEXT)
    assert meta.sourceFamily == "fortinet"
    assert "FortiGate" in meta.provider


def test_cisco_asa_sample_unchanged():
    meta = parse_event_metadata(CISCO_TEXT)
    assert meta.sourceFamily == "cisco_asa"
    assert meta.eventId == "106023"


def test_linux_syslog_sample_unchanged():
    meta = parse_event_metadata(LINUX_TEXT)
    assert meta.sourceFamily == "linux_syslog"
    assert meta.eventId == "AUTH-FAIL"


# ---------------------------------------------------------------------------
# 9. Unknown text: honest, no Windows fabrication, no web search
# ---------------------------------------------------------------------------


def test_unknown_text_never_becomes_windows():
    meta = parse_event_metadata(UNKNOWN_TEXT)
    assert meta.sourceFamily == "unknown_text"
    assert meta.eventId == "Unknown"
    assert meta.provider == "Unknown"


def test_unknown_search_runs_no_query():
    results, snippets = summary_mod.search_solutions(
        "Unknown", "Unknown", source_family="unknown_text"
    )
    assert results == [] and snippets == ""


def test_unknown_build_summary_makes_no_windows_claims():
    summary = asyncio.run(
        summary_mod.build_summary(
            "Unknown",
            "Unknown",
            "",
            [],
            "en",
            "",
            None,
            UNKNOWN_TEXT,
            None,
            source_family="unknown_text",
        )
    )
    blob = " ".join([summary.overview] + summary.causes + summary.steps)
    assert "Windows event log entry" not in blob
    assert "Event ID" not in blob
    assert summary.causes and summary.steps


# ---------------------------------------------------------------------------
# 7b. Source classification honesty
# ---------------------------------------------------------------------------


def test_classify_source_only_vendor_domains_are_official():
    assert summary_mod._classify_source(
        "https://learn.microsoft.com/x", "community"
    ) == "official"
    assert summary_mod._classify_source(
        "https://www.reddit.com/r/x", "community"
    ) == "community"
    assert summary_mod._classify_source(
        "https://helpcenter.veeam.com/y",
        "community",
        summary_mod.FAMILY_OFFICIAL_DOMAINS["veeam_vbr"],
    ) == "official"
    # A Microsoft link must NOT be official for a Veeam diagnosis.
    assert summary_mod._classify_source(
        "https://learn.microsoft.com/x",
        "community",
        summary_mod.FAMILY_OFFICIAL_DOMAINS["veeam_vbr"],
    ) == "community"
    # Vendor-owned community (forums.veeam.com) is community by hostname equality.
    assert summary_mod._classify_source(
        "https://forums.veeam.com/topic/1",
        "community",
        summary_mod.FAMILY_OFFICIAL_DOMAINS["veeam_vbr"],
        community_domains=summary_mod.FAMILY_COMMUNITY_DOMAINS.get("veeam_vbr", ()),
    ) == "community"


def test_veeam_fallback_refs_contain_no_microsoft():
    import duckduckgo_search  # noqa: F401  (proves import surface only)

    def _boom(*a, **k):
        raise RuntimeError("offline")

    orig = summary_mod.DDGS
    summary_mod.DDGS = _boom
    try:
        results, _ = summary_mod.search_solutions(
            "VEEAM-REPLICA-SNAPSHOT-CHAIN",
            "Veeam Backup & Replication",
            source_family="veeam_vbr",
        )
    finally:
        summary_mod.DDGS = orig
    assert results, "expected vendor fallback references"
    for r in results:
        assert "learn.microsoft.com" not in r.link
        assert "support.microsoft.com" not in r.link


def test_classify_source_families():
    assert classify_source(VEEAM_RAW_TEXT)["sourceFamily"] == "veeam_vbr"
    assert classify_source(VMWARE_CTK_TEXT)["sourceFamily"] == "vmware"
    assert classify_source(FORTINET_TEXT)["sourceFamily"] == "fortinet"
    assert classify_source(CISCO_TEXT)["sourceFamily"] == "cisco_asa"
    assert classify_source(LINUX_TEXT)["sourceFamily"] == "linux_syslog"
    assert classify_source(WIN1129_TEXT)["sourceFamily"] == "windows_event"
    assert classify_source(UNKNOWN_TEXT)["sourceFamily"] == "unknown_text"


# ---------------------------------------------------------------------------
# 10-11. RAG contamination + feedback quarantine (faked DB, no network)
# ---------------------------------------------------------------------------


def test_rag_1129_never_answers_veeam(no_embeddings):
    win_row = (_FakeRow("1129", 5, {"overview": "GroupPolicy fix"}), 0.05)
    db = _FakeDB(rows=[win_row])
    out = asyncio.run(
        vector_db_mod.search_similar_logs(
            db=db,
            description=VEEAM_RAW_TEXT[:500],
            event_id="VEEAM-REPLICA-SNAPSHOT-CHAIN",
            source_family="veeam_vbr",
            diagnostic_code="VEEAM-REPLICA-SNAPSHOT-CHAIN",
        )
    )
    assert out == []


def test_rag_vendor_row_never_answers_windows(no_embeddings):
    veeam_row = (
        _FakeRow("VEEAM-REPLICA-SNAPSHOT-CHAIN", 5, {"overview": "Veeam fix"}),
        0.05,
    )
    db = _FakeDB(rows=[veeam_row])
    out = asyncio.run(
        vector_db_mod.search_similar_logs(
            db=db,
            description=WIN1129_TEXT,
            event_id="1129",
            source_family="windows_event",
        )
    )
    assert out == []


def test_rag_negative_feedback_rows_excluded(no_embeddings):
    bad = (_FakeRow("1129", -1, {"overview": "wrong fix"}), 0.01)
    good = (_FakeRow("1129", 3, {"overview": "right fix"}), 0.4)
    db = _FakeDB(rows=[bad, good])
    out = asyncio.run(
        vector_db_mod.search_similar_logs(
            db=db, description=WIN1129_TEXT, event_id="1129",
            source_family="windows_event",
        )
    )
    assert out == [{"overview": "right fix"}]


def test_rag_unverified_score_zero_requires_same_identity(no_embeddings):
    stranger = (_FakeRow("4625", 0, {"overview": "unverified 4625"}), 0.05)
    db = _FakeDB(rows=[stranger])
    out = asyncio.run(
        vector_db_mod.search_similar_logs(
            db=db, description=WIN1129_TEXT, event_id="1129",
            source_family="windows_event",
        )
    )
    assert out == []


def test_rag_unknown_source_retrieves_nothing(no_embeddings):
    row = (_FakeRow("1129", 9, {"overview": "verified"}), 0.01)
    db = _FakeDB(rows=[row])
    out = asyncio.run(
        vector_db_mod.search_similar_logs(
            db=db, description=UNKNOWN_TEXT, event_id="Unknown",
            source_family="unknown_text",
        )
    )
    assert out == []


def test_thumbs_down_quarantines_exact_row(no_embeddings):
    row = _FakeRow("1129", 0, {"overview": "needs review"})
    db = _FakeDB(single=row)
    asyncio.run(
        vector_db_mod.add_solution(
            db=db, event_id="1129", description="d",
            solution_summary={"overview": "needs review"}, feedback_score=-1,
        )
    )
    assert row.feedback_score == -1
    assert db.added == []  # no duplicate row inserted
    assert db.commits == 1


def test_thumbs_down_without_row_inserts_nothing(no_embeddings):
    db = _FakeDB(single=None)
    asyncio.run(
        vector_db_mod.add_solution(
            db=db, event_id="9999", description="d",
            solution_summary={"overview": "x"}, feedback_score=-1,
        )
    )
    assert db.added == []


def test_guardrail_predicate_matrix():
    f = vector_db_mod._is_usable_knowledge_row
    assert f("VEEAM-REPLICA-SNAPSHOT-CHAIN", 5, "VEEAM-REPLICA-SNAPSHOT-CHAIN", "veeam_vbr", 0.1)
    assert not f("1129", 5, "VEEAM-REPLICA-SNAPSHOT-CHAIN", "veeam_vbr", 0.01)
    assert not f("VEEAM-REPLICA-SNAPSHOT-CHAIN", 5, "1129", "windows_event", 0.01)
    assert not f("1129", -1, "1129", "windows_event", 0.01)
    assert f("1129", 0, "1129", "windows_event", 0.4)
    assert not f("4625", 0, "1129", "windows_event", 0.05)
    assert not f("1129", 5, "Unknown", "unknown_text", 0.01)


# ---------------------------------------------------------------------------
# 8b. Identifier redaction before embedding
# ---------------------------------------------------------------------------


def test_redact_masks_volatile_identifiers():
    red = vector_db_mod.redact_for_embedding(
        "Connection from 10.0.0.5 failed for JobSessionID=48291 with "
        "password=Sup3rSecret on host 550e8400-e29b-41d4-a716-446655440000"
    )
    assert "10.0.0.5" not in red
    assert "Sup3rSecret" not in red
    assert "550e8400-e29b-41d4-a716-446655440000" not in red
    assert "JobSessionID=<ID>" in red
    assert "password=<REDACTED>" in red


def test_redact_keeps_semantics_and_times():
    text = "Backup completed for Job Type: Replica at 12:34:56"
    assert vector_db_mod.redact_for_embedding(text) == text


# ---------------------------------------------------------------------------
# 4b. Compaction keeps the tail
# ---------------------------------------------------------------------------


def test_compaction_preserves_tail_failure_and_bound():
    filler = "".join(f"2026-09-12 02:00:{i % 60:02d} Info heartbeat ok {i}\n" for i in range(3000))
    big = (
        "VEEAM BACKUP SESSION HEADER id=session-1\n"
        + filler
        + "2026-09-12 03:59:59 Error TERMINAL-FAILURE-MARKER-XYZ: A required file was not found\n"
    )
    assert len(big) > MAX_CHARS
    out = compact_log_evidence(big)
    assert "VEEAM BACKUP SESSION HEADER" in out
    assert "TERMINAL-FAILURE-MARKER-XYZ" in out
    assert len(out) <= MAX_CHARS


def test_compaction_passthrough_for_small_logs():
    assert compact_log_evidence("short log") == "short log"


# ---------------------------------------------------------------------------
# 3b. Incident extractor: first vs terminal, no causal overclaim
# ---------------------------------------------------------------------------


def test_incident_first_vs_terminal_without_causal_claim():
    incident = extract_incident(VEEAM_RAW_TEXT, "veeam_vbr")
    assert incident["firstMeaningfulFailure"] is not None
    assert "change tracking" in incident["firstMeaningfulFailure"].lower()
    assert incident["terminalFailure"] is not None
    assert "required file was not found" in incident["terminalFailure"].lower()
    assert incident["firstMeaningfulFailure"] != incident["terminalFailure"]
    import json as _json

    blob = _json.dumps(incident).lower()
    assert "caused by" not in blob
    assert incident["unknowns"] and incident["nextEvidence"]


# ---------------------------------------------------------------------------
# 6b + 12. Vendor knowledge + golden Veeam acceptance
# ---------------------------------------------------------------------------


def test_vendor_knowledge_entries_are_honest():
    for code in (
        "VMWARE-CBT-DELETE-FAILED",
        "VMWARE-SNAPSHOT-FILE-MISSING",
        "VEEAM-REPLICA-SNAPSHOT-CHAIN",
    ):
        summary = get_vendor_summary(code, "en")
        assert summary is not None
        assert summary.confidence in ("high", "medium", "low")
        assert summary.evidence and summary.nextEvidence
    assert get_vendor_summary("NOPE", "en") is None


def test_golden_veeam_acceptance_semantics():
    meta = parse_event_metadata(VEEAM_RAW_TEXT)
    assert meta.sourceFamily == "veeam_vbr"
    code = meta.diagnosticCode
    assert code == "VEEAM-REPLICA-SNAPSHOT-CHAIN"

    summary = asyncio.run(
        summary_mod.build_summary(
            code,
            "Veeam Backup & Replication",
            "",
            [],
            "en",
            "",
            None,
            VEEAM_RAW_TEXT,
            None,
            source_family="veeam_vbr",
            diagnostic_code=code,
            product="Veeam Backup & Replication",
        )
    )
    blob = " ".join(
        [summary.overview] + summary.causes + summary.steps + summary.evidence
    )
    # Required semantics.
    assert "snapshot" in blob.lower()
    assert "change-tracking" in blob or "change tracking" in blob.lower()
    assert "required file was not found" in blob.lower()
    assert summary.confidence in ("high", "medium")
    assert any("vmware.log" in n.lower() for n in summary.nextEvidence)
    assert any("hostd" in n.lower() for n in summary.nextEvidence)
    # Honest unknowns, no invented specifics.
    assert summary.limitations, "must state what is still unknown"
    # Forbidden output.
    for token in FORBIDDEN_VEEAM_TOKENS:
        assert token not in blob, f"contamination: {token}"
    assert "file is locked" not in blob.lower()
    assert "file was locked" not in blob.lower()


# ---------------------------------------------------------------------------
# Phase 2.1: bounded upload reads + SHA256 + bundle limits
# ---------------------------------------------------------------------------


def test_bounded_upload_reads_exact():
    import io
    from backend.domain.analyzer.services.bundle import read_upload_bounded

    up = io.BytesIO(b"hello world")
    result = read_upload_bounded(up, 3)
    assert result == b"hel"

    up = io.BytesIO(b"hello world")
    result = read_upload_bounded(up, 100)
    assert result == b"hello world"

    up = io.BytesIO(b"hello world")
    result = read_upload_bounded(up, 0)
    assert result == b""


def test_bundle_sha256_known_vector():
    assert sha256_hex(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_bundle_rejects_unsupported_extension():
    try:
        validate_bundle([("archive.zip", b"data")])
    except ValueError as e:
        assert "ZIP" in str(e) or "Unsupported" in str(e)
    else:
        raise AssertionError("expected ValueError for .zip")


def test_bundle_path_traversal_neutralized():
    cleaned = validate_bundle([("../../etc/passwd.log", b"line")])
    assert cleaned[0][0] == "passwd.log"


def test_bundle_per_file_limit():
    try:
        validate_bundle([("big.log", b"x" * (BUNDLE_MAX_FILE_BYTES + 1))])
    except ValueError as e:
        assert "too large" in str(e).lower()
    else:
        raise AssertionError("expected ValueError for oversized file")


def test_bundle_total_limit():
    files = [(f"f{i}.log", b"x" * BUNDLE_MAX_FILE_BYTES) for i in range(7)]
    try:
        validate_bundle(files)
    except ValueError as e:
        assert "total" in str(e).lower() or "large" in str(e).lower()
    else:
        raise AssertionError("expected ValueError for oversized bundle")
    assert BUNDLE_MAX_TOTAL_BYTES == 30 * 1024 * 1024


def test_bundle_file_count_limit():
    files = [(f"f{i}.log", b"x") for i in range(BUNDLE_MAX_FILES + 1)]
    try:
        validate_bundle(files)
    except ValueError as e:
        assert "many" in str(e).lower() or "maximum" in str(e).lower()
    else:
        raise AssertionError("expected ValueError for too many files")


def test_kb_results_are_official_with_real_links():
    from backend.domain.analyzer.services.vendor_knowledge import vendor_reference_results

    results = vendor_reference_results(
        "VMWARE-SNAPSHOT-FILE-MISSING", VMWARE_MISSING_TEXT, "en"
    )
    assert results, "expected at least the 424591 reference"
    for r in results:
        assert r.sourceType == "official"
        assert r.link.startswith("https://knowledge.broadcom.com/external/article/")


def _veeam_vendor_summary():
    return get_vendor_summary("VEEAM-REPLICA-SNAPSHOT-CHAIN", "en")


def test_veeam_followup_retains_veeam_context():
    summary = _veeam_vendor_summary()
    assert summary is not None
    answer = summary_mod.build_followup_answer(
        "What caused this?",
        summary,
        [],
        "en",
        None,
        source_family="veeam_vbr",
        event_id="VEEAM-REPLICA-SNAPSHOT-CHAIN",
        provider="Veeam Backup & Replication",
        diagnostic_code="VEEAM-REPLICA-SNAPSHOT-CHAIN",
    )
    for token in FORBIDDEN_VEEAM_TOKENS:
        assert token not in answer, f"follow-up contamination: {token}"
    assert "DCOM" not in answer
    assert "GroupPolicy" not in answer


def test_vmware_followup_retains_vmware_context():
    summary = get_vendor_summary("VMWARE-SNAPSHOT-FILE-MISSING", "en")
    assert summary is not None
    answer = summary_mod.build_followup_answer(
        "What caused this?",
        summary,
        [],
        "en",
        None,
        source_family="vmware",
        event_id="VMWARE-SNAPSHOT-FILE-MISSING",
        provider="VMware ESXi",
        diagnostic_code="VMWARE-SNAPSHOT-FILE-MISSING",
    )
    assert "Event ID 1129" not in answer
    assert "GroupPolicy" not in answer
    assert "DCOM" not in answer


def test_unknown_followup_remains_unknown():
    summary = asyncio.run(
        summary_mod.build_summary(
            "Unknown",
            "Unknown",
            "",
            [],
            "en",
            "",
            None,
            UNKNOWN_TEXT,
            None,
            source_family="unknown_text",
        )
    )
    answer = summary_mod.build_followup_answer(
        "What caused this?", summary, [], "en", None,
        source_family="unknown_text",
    )
    blob = f"{summary.overview} {answer}"
    assert "Windows event log entry" not in blob


# ---------------------------------------------------------------------------
# Phase 2: provenance — hostname equality, community precedence
# ---------------------------------------------------------------------------


def _official(domains_key):
    return summary_mod.FAMILY_OFFICIAL_DOMAINS[domains_key]


def _community(domains_key):
    return summary_mod.FAMILY_COMMUNITY_DOMAINS.get(domains_key, ())


def test_helpcenter_veeam_is_official():
    assert summary_mod._classify_source(
        "https://helpcenter.veeam.com/docs/x", "community", _official("veeam_vbr")
    ) == "official"


def test_forums_veeam_is_community():
    assert summary_mod._classify_source(
        "https://forums.veeam.com/topic/1",
        "community",
        _official("veeam_vbr"),
        community_domains=_community("veeam_vbr"),
    ) == "community"


def test_lookalike_domain_is_not_official():
    assert summary_mod._classify_source(
        "https://notveeam.com/docs/x",
        "community",
        _official("veeam_vbr"),
        community_domains=_community("veeam_vbr"),
    ) == "community"
    assert summary_mod._classify_source(
        "https://veeam.com.evil.example/docs",
        "community",
        _official("veeam_vbr"),
        community_domains=_community("veeam_vbr"),
    ) == "community"


def test_vendor_community_domains_are_community():
    assert summary_mod._classify_source(
        "https://community.cisco.com/t5/x/1", "community",
        _official("cisco_asa"), community_domains=_community("cisco_asa"),
    ) == "community"
    assert summary_mod._classify_source(
        "https://community.fortinet.com/t5/x/1", "community",
        _official("fortinet"), community_domains=_community("fortinet"),
    ) == "community"
    assert summary_mod._classify_source(
        "https://communities.vmware.com/t5/x/1", "community",
        _official("vmware"), community_domains=_community("vmware"),
    ) == "community"


def test_linux_and_json_get_no_microsoft_fallback():
    def _boom(*a, **k):
        raise RuntimeError("offline")

    orig = summary_mod.DDGS
    summary_mod.DDGS = _boom
    try:
        for family in ("linux_syslog", "json"):
            results, _ = summary_mod.search_solutions(
                "Unknown", "sshd", source_family=family
            )
            assert results == [], f"{family} must yield no references offline"
            for r in results:
                assert "learn.microsoft.com" not in r.link
                assert "support.microsoft.com" not in r.link
    finally:
        summary_mod.DDGS = orig


# ---------------------------------------------------------------------------
# Phase 2: RFC5424 completeness
# ---------------------------------------------------------------------------

SYSLOG_VEEAM = (
    "<134>1 2026-09-12T02:11:03Z TESTHOST Veeam_MP 48291 "
    '[VeeamEvent@123 instanceId="1129" JobSessionID="48291" JobID="77" '
    'JobType="Replica" Platform="VMware vSphere" '
    'Description="Could not delete change tracking file"]'
)


def test_rfc5424_quoted_fields_parse():
    parsed = parse_syslog_hinted(SYSLOG_VEEAM, "veeam_vbr")
    assert parsed is not None
    assert parsed["jobsessionid"] == "VEEAM-48291"
    assert parsed["jobid"] == "VEEAM-77"
    assert parsed["jobtype"] == "Replica"
    assert parsed["platform"] == "VMware vSphere"
    assert parsed["description"] == "Could not delete change tracking file"


def test_numeric_instance_id_never_becomes_windows_event_id():
    parsed = parse_syslog_hinted(SYSLOG_VEEAM, "veeam_vbr")
    assert parsed is not None
    assert parsed["instanceid"] == "VEEAM-1129"
    meta = parse_event_metadata(SYSLOG_VEEAM)
    assert meta.eventId != "1129"
    assert meta.attributes.get("syslog", {}).get("instanceid") == "VEEAM-1129"


# ---------------------------------------------------------------------------
# Phase 2: exact paths — surfaced only when observed
# ---------------------------------------------------------------------------

PATH_TEXT = (
    "2026-09-12T02:15:44.001Z Er(02) vmx - SNAPSHOT: RevertSnapshot failed with InvalidSnapshotFormat\n"
    "2026-09-12T02:15:44.002Z Er(02) vmx - SNAPSHOT: A required file was not found\n"
    "2026-09-12T02:15:44.003Z Er(02) vmx - SNAPSHOT: fileName:'/vmfs/volumes/TEST-DS-01/TEST-VM-01/TEST-VM-01-000003.vmdk'\n"
)


def test_incident_exact_path_surfaced():
    incident = extract_incident(PATH_TEXT, "vmware")
    assert incident["observedPaths"], "exact observed path must be surfaced"
    assert any("TEST-VM-01-000003.vmdk" in p for p in incident["observedPaths"])


def test_no_path_means_no_filename_invented():
    incident = extract_incident(VMWARE_MISSING_TEXT, "vmware")
    assert incident["observedPaths"] == []
    blob = " ".join(incident["observedPaths"]).lower()
    assert ".ctk.vmdk" not in blob
    assert "-delta.vmdk" not in blob
    assert ".vmsd" not in blob
    assert any("filename" in u.lower() or "path" in u.lower() for u in incident["unknowns"])


# ---------------------------------------------------------------------------
# Phase 2: verified KB gates
# ---------------------------------------------------------------------------


def _kb_ids(code, text):
    return [r.link.rsplit("/", 1)[-1] for r in vendor_reference_results(code, text, "en")]


def test_revert_snapshot_selects_424591():
    ids = _kb_ids("VMWARE-SNAPSHOT-FILE-MISSING", VMWARE_MISSING_TEXT)
    assert "424591" in ids


def test_gated_articles_excluded_without_context():
    ids = _kb_ids("VMWARE-SNAPSHOT-FILE-MISSING", VMWARE_MISSING_TEXT)
    assert "442155" not in ids  # needs vSAN + ESA
    assert "411756" not in ids  # needs vVOL
    assert "318905" not in ids  # revert context, not create-snapshot
    assert "450780" not in ids  # no deletion/consolidation tokens
    assert "452165" not in ids  # no rename/move evidence


def test_vsan_esa_gate():
    text = (
        "vSAN ESA cluster snapshot usage is very high "
        "Could not delete change tracking file DISKLIB result:2620"
    )
    assert "442155" in _kb_ids("VMWARE-CBT-DELETE-FAILED", text)
    assert "442155" not in _kb_ids(
        "VMWARE-CBT-DELETE-FAILED", "vSAN cluster snapshot usage is very high"
    )
    assert "442155" not in _kb_ids(
        "VMWARE-CBT-DELETE-FAILED", "ESA partner snapshot cleanup guide"
    )


def test_vvol_gate():
    text = "Snapshot consolidation failed for VM on vVOLs storage vvol://datastore/1"
    assert "411756" in _kb_ids("VMWARE-CBT-DELETE-FAILED", text)
    assert "411756" not in _kb_ids("VMWARE-CBT-DELETE-FAILED", VMWARE_CTK_TEXT)


def test_create_snapshot_gate_for_318905():
    text = (
        "Detected an invalid snapshot configuration error creating a snapshot "
        "CreateSnapshot failed"
    )
    assert "318905" in _kb_ids("VMWARE-SNAPSHOT-FILE-MISSING", text)
    # Invalid config in a revert path must NOT select the create-snapshot article.
    assert "318905" not in _kb_ids("VMWARE-SNAPSHOT-FILE-MISSING", VMWARE_MISSING_TEXT)


def test_deletion_gate_for_450780():
    text = (
        "Deleting snapshot: A required file was not found "
        "snapshot consolidation failed"
    )
    assert "450780" in _kb_ids("VMWARE-SNAPSHOT-FILE-MISSING", text)
    assert "450780" not in _kb_ids("VMWARE-SNAPSHOT-FILE-MISSING", VMWARE_MISSING_TEXT)


def test_rename_move_gate_for_452165():
    text = (
        "A required file was not found after manually renaming the virtual "
        "machine folder and moving it to another datastore path mismatch"
    )
    assert "452165" in _kb_ids("VMWARE-SNAPSHOT-FILE-MISSING", text)
    # "remove" contains "mov" as a substring but is NOT move evidence.
    trap = "Please remove the snapshot: A required file was not found snapshot"
    assert "452165" not in _kb_ids("VMWARE-SNAPSHOT-FILE-MISSING", trap)
    assert "452165" not in _kb_ids("VMWARE-SNAPSHOT-FILE-MISSING", VMWARE_MISSING_TEXT)


def test_kb_results_are_official_with_real_links():
    results = vendor_reference_results(
        "VMWARE-SNAPSHOT-FILE-MISSING", VMWARE_MISSING_TEXT, "en"
    )
    assert results, "expected at least the 424591 reference"
    for r in results:
        assert r.sourceType == "official"
        assert r.link.startswith("https://knowledge.broadcom.com/external/article/")


# ---------------------------------------------------------------------------
# Phase 2: bundle safety limits + correlation tiers
# ---------------------------------------------------------------------------


def test_bundle_sha256_known_vector():
    assert sha256_hex(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_bundle_rejects_unsupported_extension():
    try:
        validate_bundle([("archive.zip", b"data")])
    except ValueError as e:
        assert "ZIP" in str(e) or "Unsupported" in str(e)
    else:
        raise AssertionError("expected ValueError for .zip")


def test_bundle_path_traversal_neutralized():
    cleaned = validate_bundle([("../../etc/passwd.log", b"line")])
    assert cleaned[0][0] == "passwd.log"


def test_bundle_per_file_limit():
    try:
        validate_bundle([("big.log", b"x" * (BUNDLE_MAX_FILE_BYTES + 1))])
    except ValueError as e:
        assert "too large" in str(e).lower()
    else:
        raise AssertionError("expected ValueError for oversized file")


def test_bundle_total_limit():
    files = [(f"f{i}.log", b"x" * BUNDLE_MAX_FILE_BYTES) for i in range(7)]
    try:
        validate_bundle(files)
    except ValueError as e:
        assert "total" in str(e).lower() or "large" in str(e).lower()
    else:
        raise AssertionError("expected ValueError for oversized bundle")
    assert BUNDLE_MAX_TOTAL_BYTES == 30 * 1024 * 1024


def test_bundle_file_count_limit():
    files = [(f"f{i}.log", b"x") for i in range(BUNDLE_MAX_FILES + 1)]
    try:
        validate_bundle(files)
    except ValueError as e:
        assert "many" in str(e).lower() or "maximum" in str(e).lower()
    else:
        raise AssertionError("expected ValueError for too many files")


def _bundle_entry(filename, text):
    return summarize_file_evidence(
        filename=filename, content=text.encode("utf-8"), text=text
    )


def test_bundle_strong_jobsession_correlation():
    a = _bundle_entry(
        "Job.log",
        "2026-09-12T02:11:03Z Veeam JobSessionID=48291 Job Type: Replica started",
    )
    b = _bundle_entry(
        "Task.log",
        "2026-09-12T02:12:41Z Veeam JobSessionID=48291 Could not delete change tracking file",
    )
    out = correlate_bundle([a, b])
    assert out["correlationConfidence"] == "strong"
    assert any("48291" in r for r in out["correlationReasons"])


def test_bundle_medium_path_plus_time_correlation():
    path = "/vmfs/volumes/TEST-DS-01/TEST-VM-01/TEST-VM-01-000003.vmdk"
    a = _bundle_entry(
        "vmware.log",
        f"2026-09-12T02:15:44Z SNAPSHOT: RevertSnapshot failed fileName:'{path}'",
    )
    b = _bundle_entry(
        "hostd.log",
        f"2026-09-12T02:15:45Z SNAPSHOT: A required file was not found fileName:'{path}'",
    )
    out = correlate_bundle([a, b])
    assert out["correlationConfidence"] == "medium"
    assert "vmware.log" in out["correlatedSources"]
    assert "hostd.log" in out["correlatedSources"]


def test_bundle_weak_correlation_never_proven_causal():
    a = _bundle_entry("a.log", "Error: A required file was not found")
    b = _bundle_entry("b.log", "Error: A required file was not found")
    out = correlate_bundle([a, b])
    assert out["correlationConfidence"] == "weak"
    blob = " ".join(out["correlationReasons"]).lower()
    assert "not proven" in blob


# ---------------------------------------------------------------------------
# Phase 2: schema backward compatibility
# ---------------------------------------------------------------------------


def test_solution_summary_backward_compatible():
    s = SolutionSummary(**{"overview": "legacy row"})
    assert s.incident is None
    assert s.evidenceItems == []
    assert s.evidence == []
