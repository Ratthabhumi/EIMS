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
    is_log_source_path,
    resource_paths_for_line,
    sha256_hex,
    summarize_file_evidence,
    validate_bundle,
)
from backend.domain.analyzer.services import evidence as evidence_mod
from backend.domain.analyzer.services.incident_extract import incident_from_records
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
    # reddit.com is not in any allowlist without community_domains arg — REJECT.
    assert summary_mod._classify_source(
        "https://www.reddit.com/r/x", "community"
    ) == "REJECT"
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
    ) == "REJECT"
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
    # terminal is 'processing finished with errors' (the explicit session outcome line).
    assert "processing finished" in incident["terminalFailure"].lower()
    assert incident["firstMeaningfulFailure"] != incident["terminalFailure"]
    import json as _json

    blob = _json.dumps(incident).lower()
    assert "caused by" not in blob
    assert incident["unknowns"] and incident["nextEvidence"]


# ---------------------------------------------------------------------------
# 6b + 12. Vendor knowledge + golden Veeam acceptance
# ---------------------------------------------------------------------------


def test_vendor_knowledge_entries_are_honest():
    for code, text in (
        ("VMWARE-CBT-DELETE-FAILED", _CBT_MINIMAL_TEXT),
        ("VMWARE-SNAPSHOT-FILE-MISSING", VMWARE_MISSING_TEXT),
        ("VEEAM-REPLICA-SNAPSHOT-CHAIN", VEEAM_RAW_TEXT),
    ):
        summary = get_vendor_summary(code, "en", text)
        assert summary is not None
        assert summary.confidence in ("high", "medium", "low")
        assert summary.evidence and summary.nextEvidence
    assert get_vendor_summary("NOPE", "en") is None
    # Fail-closed: no evidence means no claimed evidence strings.
    empty = get_vendor_summary("VEEAM-REPLICA-SNAPSHOT-CHAIN", "en", "")
    assert empty is not None
    assert empty.evidence == []


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
    import asyncio
    import io
    from backend.domain.analyzer.services.bundle import read_upload_bounded, UploadTooLarge

    class AsyncStream:
        def __init__(self, data: bytes, chunk_yield: int = 1):
            self._bio = io.BytesIO(data)
            self._chunk_yield = chunk_yield

        async def read(self, n: int = -1) -> bytes:
            to_read = min(n, self._chunk_yield) if n > 0 else self._chunk_yield
            return self._bio.read(to_read)

    # 1. Exact limit
    up = AsyncStream(b"exact", chunk_yield=2)
    res = asyncio.run(read_upload_bounded(up, 5))
    assert res == b"exact"

    # 2. Limit + 1 raises controlled UploadTooLarge
    up_overflow = AsyncStream(b"exact!", chunk_yield=2)
    try:
        asyncio.run(read_upload_bounded(up_overflow, 5))
        assert False, "expected UploadTooLarge"
    except UploadTooLarge as e:
        assert "exceeds maximum" in str(e).lower()

    # 3. Empty upload
    up_empty = AsyncStream(b"")
    res_empty = asyncio.run(read_upload_bounded(up_empty, 10))
    assert res_empty == b""

    # 4. Short-chunk stream (1 byte at a time)
    up_short = AsyncStream(b"hello", chunk_yield=1)
    res_short = asyncio.run(read_upload_bounded(up_short, 5))
    assert res_short == b"hello"


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
    # Unlisted domains are now REJECT, not 'community' — strict allowlist.
    assert summary_mod._classify_source(
        "https://notveeam.com/docs/x",
        "community",
        _official("veeam_vbr"),
        community_domains=_community("veeam_vbr"),
    ) == "REJECT"
    assert summary_mod._classify_source(
        "https://veeam.com.evil.example/docs",
        "community",
        _official("veeam_vbr"),
        community_domains=_community("veeam_vbr"),
    ) == "REJECT"


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


def test_cbt_entry_names_no_esa_article_without_environment():
    summary = get_vendor_summary("VMWARE-CBT-DELETE-FAILED", "en", VMWARE_CTK_TEXT)
    blob = " ".join(summary.steps)
    assert "442155" not in blob, f"CBT steps must not cite vSAN ESA article without vSAN+ESA evidence: {blob!r}"
    assert "411756" not in blob, f"CBT steps must not cite vVOLs article without vVOL evidence: {blob!r}"
    assert "418256" in blob
    gated = get_vendor_summary(
        "VMWARE-CBT-DELETE-FAILED",
        "en",
        "vSAN ESA cluster Could not delete change tracking file result:2620",
    )
    assert "442155" in " ".join(gated.steps)


# ---------------------------------------------------------------------------
# Phase 6 (final polish): evidence-exact vendor summaries
# ---------------------------------------------------------------------------

_CBT_MINIMAL_TEXT = (
    "2026-09-12T02:12:41.123Z In(05) vmx - DISKLIB-CTK: "
    "Could not delete change tracking file\n"
)


def test_cbt_minimal_names_no_unobserved_signatures():
    summary = get_vendor_summary("VMWARE-CBT-DELETE-FAILED", "en", _CBT_MINIMAL_TEXT)
    blob = " ".join([summary.overview] + summary.causes + summary.steps + summary.evidence)
    assert "2620" not in blob
    assert "CTK_CTKUNLINK" not in blob
    assert "442155" not in blob
    assert "411756" not in blob
    assert "Failed to lock the file" not in blob
    assert summary.evidence == ["Could not delete change tracking file"]


def test_cbt_rich_surfaces_observed_signatures_only():
    summary = get_vendor_summary("VMWARE-CBT-DELETE-FAILED", "en", VMWARE_CTK_TEXT)
    assert "2620" in summary.overview
    assert "CTK_CTKUNLINK" in summary.overview
    blob = " ".join(summary.steps)
    assert "442155" not in blob
    assert "411756" not in blob
    assert "Failed to lock the file" not in blob


def test_snapshot_missing_steps_match_retrieval_gates():
    summary = get_vendor_summary("VMWARE-SNAPSHOT-FILE-MISSING", "en", VMWARE_MISSING_TEXT)
    blob = " ".join(summary.steps)
    assert "424591" in blob
    assert "318905" not in blob
    assert "450780" not in blob
    assert "452165" not in blob
    assert "411756" not in blob


def test_snapshot_missing_causes_not_stated_as_facts():
    summary = get_vendor_summary("VMWARE-SNAPSHOT-FILE-MISSING", "en", VMWARE_MISSING_TEXT)
    blob = " ".join(summary.causes)
    assert "was deleted, moved, or renamed" not in blob


def test_snapshot_create_names_318905_only_in_context():
    text = (
        "Detected an invalid snapshot configuration error creating a snapshot "
        "CreateSnapshot failed A required file was not found invalidsnapshotformat"
    )
    summary = get_vendor_summary("VMWARE-SNAPSHOT-FILE-MISSING", "en", text)
    assert "318905" in " ".join(summary.steps)


def test_snapshot_delete_names_450780_only_in_context():
    text = (
        "Deleting snapshot: A required file was not found "
        "snapshot consolidation failed invalidsnapshotformat"
    )
    summary = get_vendor_summary("VMWARE-SNAPSHOT-FILE-MISSING", "en", text)
    assert "450780" in " ".join(summary.steps)


def test_snapshot_rename_names_452165_only_in_context():
    text = (
        "A required file was not found after manually renaming "
        "virtual machine folder invalidsnapshotformat"
    )
    summary = get_vendor_summary("VMWARE-SNAPSHOT-FILE-MISSING", "en", text)
    assert "452165" in " ".join(summary.steps)


def test_replica_chain_without_cbt_names_no_cbt_deletion():
    text = (
        "RevertSnapshot failed: InvalidSnapshotFormat\n"
        "Detected an invalid snapshot configuration\n"
        "A required file was not found\n"
    )
    summary = get_vendor_summary("VEEAM-REPLICA-SNAPSHOT-CHAIN", "en", text)
    blob = " ".join(summary.causes + summary.steps + summary.evidence)
    assert "change-tracking file deletion failed" not in blob
    assert "Could not delete change tracking file" not in summary.evidence
    assert "CBT deletion" not in blob


def test_replica_chain_with_cbt_keeps_noncausal_limitation():
    summary = get_vendor_summary("VEEAM-REPLICA-SNAPSHOT-CHAIN", "en", VEEAM_RAW_TEXT)
    blob = " ".join(summary.causes + summary.evidence)
    assert "change-tracking file deletion failed" in blob
    assert "Could not delete change tracking file" in summary.evidence
    assert any("NOT proven causal" in lim for lim in summary.limitations)


def test_component_tags_are_not_paths():
    incident = extract_incident(
        "[CViSnapReplica] RevertSnapshot failed: InvalidSnapshotFormat\n"
        "[VimApi] A required file was not found\n",
        "vmware",
    )
    assert incident["observedPaths"] == []


def test_bracket_datastore_path_surfaced_verbatim():
    incident = extract_incident(
        "RevertSnapshot failed [datastore1] VM01/VM01-000003.vmdk not found\n",
        "vmware",
    )
    assert any("VM01-000003.vmdk" in p for p in incident["observedPaths"])


def test_format_summary_uses_neutral_provenance_label():
    from backend.domain.analyzer.schemas.analyze import SolutionSummary

    probed = SolutionSummary(overview="o", causes=["c"], steps=["s"])
    en = summary_mod.format_summary_text(probed, "en")
    th = summary_mod.format_summary_text(probed, "th")
    assert en.splitlines()[0] == "Analysis summary:"
    assert th.splitlines()[0] == "สรุปการวิเคราะห์:"
    assert "web search" not in en
    assert "จากผลการค้นหา" not in th


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


def test_kb_precedence_guaranteed_even_with_three_official_web_results(monkeypatch):
    from backend.domain.analyzer.services.summary import search_solutions

    class MockDDGS:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def text(self, query, max_results=4):
            return [
                {
                    "title": f"Generic Official Result {i}",
                    "href": f"https://knowledge.broadcom.com/external/article/generic-{i}",
                    "body": f"Generic solution {i}",
                }
                for i in range(1, 4)
            ]

    monkeypatch.setattr("backend.domain.analyzer.services.summary.DDGS", MockDDGS)
    results, snippets = search_solutions(
        event_id="Unknown",
        provider="VMware",
        source_family="vmware",
        diagnostic_code="VMWARE-SNAPSHOT-FILE-MISSING",
        evidence_text="SNAPSHOT: RevertSnapshot failed. InvalidSnapshotFormat: A required file was not found",
        language="en",
    )
    assert len(results) == 3
    # Broadcom 424591 must be retained and at index 0 (top priority)
    assert any("424591" in r.link for r in results)
    assert "424591" in results[0].link
    assert results[0].sourceType == "official"


def test_source_aware_gemini_prompt_matrix(monkeypatch):
    from backend.domain.analyzer.services import summary as summary_mod

    recorded_prompts = []
    def mock_call_gemini(prompt, api_key):
        recorded_prompts.append(prompt)
        return '{"overview": "test", "causes": ["c1"], "steps": ["s1"]}'

    monkeypatch.setattr(summary_mod, "_call_gemini", mock_call_gemini)

    families = [
        "windows_event",
        "veeam_vbr",
        "vmware",
        "fortinet",
        "cisco_asa",
        "linux_syslog",
        "json",
        "unknown_text",
    ]

    for fam in families:
        recorded_prompts.clear()
        res = summary_mod._build_from_gemini(
            event_id="1001" if fam == "windows_event" else "ERR_TEST",
            provider="TestProvider",
            snippets="test web context",
            results=[],
            language="en",
            faulting_app="test.exe",
            api_key="mock-key",
            source_family=fam,
            diagnostic_code="DIAG-01",
            product="TestProd",
        )
        assert res is not None
        assert len(recorded_prompts) == 1
        prompt = recorded_prompts[0]

        if fam == "windows_event":
            assert "Windows Server Administrator" in prompt
            assert "Windows Event ID" in prompt
        else:
            assert "Windows Server Administrator" not in prompt
            assert "Windows Event ID" not in prompt

        if fam == "linux_syslog":
            assert "Linux/system context" in prompt or "Linux Systems Administrator" in prompt
        elif fam == "json":
            assert "structured application/service context" in prompt
        elif fam == "unknown_text":
            assert "conservative generic incident triage" in prompt


def test_rag_domain_identity_matrix():
    f = vector_db_mod._is_usable_knowledge_row

    # 1. Negative feedback is always excluded
    assert not f("1001", -1, "1001", "windows_event", 0.01)
    assert not f("1001", -1, "1001", "windows_event", 0.01, row_solution_json={"_knowledge": {"sourceFamily": "windows_event"}})

    # 2. Unknown text does no retrieval
    assert not f("1001", 5, "1001", "unknown_text", 0.01)

    # 3. Vendor isolation: veeam/vmware only answer exact same vendor code
    veeam_knowledge = {"_knowledge": {"sourceFamily": "veeam_vbr", "diagnosticIdentity": "VEEAM-REPLICA-SNAPSHOT-CHAIN"}}
    assert f("VEEAM-REPLICA-SNAPSHOT-CHAIN", 0, "VEEAM-REPLICA-SNAPSHOT-CHAIN", "veeam_vbr", 0.1, row_solution_json=veeam_knowledge)
    assert not f("VEEAM-REPLICA-SNAPSHOT-CHAIN", 5, "VMWARE-SNAPSHOT-FILE-MISSING", "vmware", 0.05, row_solution_json=veeam_knowledge)
    assert not f("VEEAM-REPLICA-SNAPSHOT-CHAIN", 5, "1129", "windows_event", 0.05, row_solution_json=veeam_knowledge)

    # 4. Cisco ASA isolation
    cisco_knowledge = {"_knowledge": {"sourceFamily": "cisco_asa", "diagnosticIdentity": "ASA-106015"}}
    assert f("ASA-106015", 0, "ASA-106015", "cisco_asa", 0.1, row_solution_json=cisco_knowledge)
    assert not f("ASA-106015", 5, "ASA-106015", "fortinet", 0.05, row_solution_json=cisco_knowledge)
    assert not f("ASA-106015", 5, "1129", "windows_event", 0.05, row_solution_json=cisco_knowledge)

    # 5. Fortinet isolation
    forti_knowledge = {"_knowledge": {"sourceFamily": "fortinet", "diagnosticIdentity": "0000000013"}}
    assert f("0000000013", 0, "0000000013", "fortinet", 0.1, row_solution_json=forti_knowledge)
    assert not f("0000000013", 5, "0000000013", "cisco_asa", 0.05, row_solution_json=forti_knowledge)

    # 6. Linux syslog isolation
    linux_knowledge = {"_knowledge": {"sourceFamily": "linux_syslog", "diagnosticIdentity": "sshd_failed"}}
    assert f("sshd_failed", 0, "sshd_failed", "linux_syslog", 0.1, row_solution_json=linux_knowledge)
    assert not f("sshd_failed", 5, "sshd_failed", "windows_event", 0.05, row_solution_json=linux_knowledge)

    # 7. JSON isolation
    json_knowledge = {"_knowledge": {"sourceFamily": "json", "diagnosticIdentity": "http_500"}}
    assert f("http_500", 0, "http_500", "json", 0.1, row_solution_json=json_knowledge)
    assert not f("http_500", 5, "http_500", "linux_syslog", 0.05, row_solution_json=json_knowledge)

    # 8. Legacy unmarked numeric row: Windows requests only
    assert f("1129", 0, "1129", "windows_event", 0.1, row_solution_json=None)
    assert not f("1129", 5, "1129", "linux_syslog", 0.05, row_solution_json=None)
    assert not f("1129", 5, "1129", "cisco_asa", 0.05, row_solution_json=None)
    assert not f("1129", 5, "VEEAM-REPLICA-SNAPSHOT-CHAIN", "veeam_vbr", 0.05, row_solution_json=None)


def test_semantic_bundle_vector_document():
    from backend.domain.analyzer.services.bundle import (
        build_bundle_semantic_document,
        derive_bundle_semantic_document_from_metadata,
    )

    doc = build_bundle_semantic_document(
        source_family="veeam_vbr",
        product="Veeam Backup & Replication",
        diagnostic_code="VEEAM-REPLICA-SNAPSHOT-CHAIN",
        operation_stage="Snapshot revert",
        diagnostic_signatures=["RevertSnapshot", "InvalidSnapshotFormat"],
        high_level_errors=["First failure at step 2", "Terminal revert failure"],
        correlation_confidence="strong",
    )
    assert "SourceFamily: veeam_vbr" in doc
    assert "VEEAM-REPLICA-SNAPSHOT-CHAIN" in doc
    assert "CorrelationConfidence: strong" in doc
    assert "RevertSnapshot" in doc

    # Redaction checks: secrets, raw IPs, datastore paths, session IDs must not leak
    doc_with_raw = build_bundle_semantic_document(
        source_family="vmware",
        product="ESXi",
        diagnostic_code="VMWARE-SNAPSHOT-FILE-MISSING",
        operation_stage="Reverting snapshot",
        diagnostic_signatures=["JobSessionID=48291 on host 10.0.0.5"],
        high_level_errors=["password=SecretKey fileName:'/vmfs/volumes/ds/vm.vmdk'"],
        correlation_confidence="medium",
    )
    assert "10.0.0.5" not in doc_with_raw
    assert "SecretKey" not in doc_with_raw
    assert "JobSessionID=<ID>" in doc_with_raw

    # Derivation from metadata dict
    meta = {
        "sourceFamily": "veeam_vbr",
        "product": "VBR",
        "diagnosticCode": "VEEAM-REPLICA-SNAPSHOT-CHAIN",
        "attributes": {
            "bundle": {
                "correlationConfidence": "strong"
            }
        }
    }
    sol = {
        "incident": {
            "operationStage": "cleanup",
            "diagnosticSignatures": ["RevertSnapshot"],
            "firstMeaningfulFailure": "First fail",
            "terminalFailure": "Term fail"
        }
    }
    derived = derive_bundle_semantic_document_from_metadata(meta, sol)
    assert "SourceFamily: veeam_vbr" in derived
    assert "DiagnosticCode: VEEAM-REPLICA-SNAPSHOT-CHAIN" in derived


def test_generic_veeam_rfc5424_parsing():
    from backend.domain.analyzer.services.vendor_parsers import parse_syslog_hinted

    raw_syslog = (
        '<14>1 2026-09-12T02:11:03Z backup01 Veeam_MP 1234 - [Veeam_MP@31023 '
        'instanceId="190" JobName="Daily Replication" JobResult="Failed" '
        'WillBeRetried="False" VbrVersion="12.1.0" SourceType="VM" '
        'Flags="0x04" description="Task failed: snapshot revert error"]'
    )
    res = parse_syslog_hinted(raw_syslog, "veeam_vbr")
    assert res is not None
    assert res["instanceid"] == "VEEAM-190"
    assert res["description"] == "Task failed: snapshot revert error"
    assert res["sourceFamily"] == "veeam_vbr"

    fields = res.get("fields", {})
    assert fields.get("JobName") == "Daily Replication"
    assert fields.get("JobResult") == "Failed"
    assert fields.get("WillBeRetried") == "False"
    assert fields.get("VbrVersion") == "12.1.0"
    assert fields.get("SourceType") == "VM"
    assert fields.get("Flags") == "0x04"

# ---------------------------------------------------------------------------
# Phase 11 — Sanitized field case: generic session failure
# ---------------------------------------------------------------------------

from tests._field_fixture_veeam import VEEAM_FIELD_FIXTURE as _VEEAM_FIELD_FIXTURE


def test_field_generic_session_failed_code():
    meta = parse_veeam(_VEEAM_FIELD_FIXTURE)
    assert meta.sourceFamily == "veeam_vbr"
    assert meta.diagnosticCode == "VEEAM-SESSION-FAILED"
    assert meta.eventId == "VEEAM-SESSION-FAILED"


def test_field_classifier_routes_fixture_to_veeam():
    result = classify_source(_VEEAM_FIELD_FIXTURE, "veeam_job.log")
    assert result["sourceFamily"] == "veeam_vbr", (
        f"Field fixture must classify as veeam_vbr end-to-end, got: {result!r}"
    )


def test_bundle_endpoint_names_resolve():
    import backend.api.routers.analyzer.analyze as analyze_mod

    for name in (
        "validate_bundle",
        "correlate_bundle",
        "summarize_file_evidence",
        "build_evidence_items",
        "read_upload_bounded",
        "derive_bundle_semantic_document_from_metadata",
    ):
        assert name in vars(analyze_mod), (
            f"submit_bundle references {name} but it is not imported"
        )


def test_field_first_failure_is_session_line():
    inc = extract_incident(_VEEAM_FIELD_FIXTURE, source_family="veeam_vbr")
    first = inc["firstMeaningfulFailure"] or ""
    assert "Task session" in first and "Failed" in first, f"Expected session Failed line, got: {first!r}"
    assert "Retry times on failure" not in first
    assert "Use fast fail on socket exception" not in first


def test_field_terminal_failure_not_config_line():
    inc = extract_incident(_VEEAM_FIELD_FIXTURE, source_family="veeam_vbr")
    terminal = inc["terminalFailure"] or ""
    assert "Use fast fail on socket exception" not in terminal
    assert "Retry times on failure" not in terminal


def test_field_operation_stage_not_retry_from_config():
    inc = extract_incident(_VEEAM_FIELD_FIXTURE, source_family="veeam_vbr")
    stage = inc["operationStage"]
    assert stage != "Retry", f"Stage should not be Retry from config text; got: {stage!r}"
    assert stage in ("", "SessionResult"), f"Unexpected stage: {stage!r}"


def test_field_no_html_fragment_paths():
    inc = extract_incident(_VEEAM_FIELD_FIXTURE, source_family="veeam_vbr")
    paths = inc["observedPaths"]
    for p in paths:
        assert "/b>" not in p, f"HTML fragment in path: {p!r}"
        assert "/td>" not in p, f"HTML fragment in path: {p!r}"
        assert "/tr>" not in p, f"HTML fragment in path: {p!r}"
        assert "/span>" not in p, f"HTML fragment in path: {p!r}"
    assert paths == [], f"Expected no paths for this fixture, got: {paths}"


def test_field_severity_not_error_from_config_only():
    from backend.domain.analyzer.services.vendor_parsers import _severity
    config_only = "Job ScheduleOptions:\nRetry times on failure: [3]\nRetry timeout: [10 min]\nUse fast fail on socket exception: True\n"
    level = _severity(config_only)
    assert level != "Error", f"Expected non-Error severity for config-only text, got: {level!r}"


def test_field_logname_no_raw_head():
    meta = parse_veeam(_VEEAM_FIELD_FIXTURE)
    assert "Retry times on failure" not in meta.logName
    assert "ProxyDetector" not in meta.logName
    assert meta.logName == "Veeam Backup & Replication Log"


# ---------------------------------------------------------------------------
# Phase 12 — Search domain rejection regression
# ---------------------------------------------------------------------------


def test_search_domain_reject_thaiticketmajor():
    from backend.domain.analyzer.services.summary import _classify_source, FAMILY_OFFICIAL_DOMAINS, FAMILY_COMMUNITY_DOMAINS
    official = FAMILY_OFFICIAL_DOMAINS.get("veeam_vbr", ())
    community = FAMILY_COMMUNITY_DOMAINS.get("veeam_vbr", ())
    result = _classify_source("https://www.thaiticketmajor.com/some-veeam-page", "official", official, community)
    assert result == "REJECT", f"thaiticketmajor.com must be REJECT for veeam_vbr, got: {result!r}"


def test_search_domain_accept_helpcenter_veeam():
    from backend.domain.analyzer.services.summary import _classify_source, FAMILY_OFFICIAL_DOMAINS, FAMILY_COMMUNITY_DOMAINS
    official = FAMILY_OFFICIAL_DOMAINS.get("veeam_vbr", ())
    community = FAMILY_COMMUNITY_DOMAINS.get("veeam_vbr", ())
    result = _classify_source("https://helpcenter.veeam.com/docs/backup/vsphere/replica_job.html", "official", official, community)
    assert result == "official"


def test_search_domain_accept_forums_veeam():
    from backend.domain.analyzer.services.summary import _classify_source, FAMILY_OFFICIAL_DOMAINS, FAMILY_COMMUNITY_DOMAINS
    official = FAMILY_OFFICIAL_DOMAINS.get("veeam_vbr", ())
    community = FAMILY_COMMUNITY_DOMAINS.get("veeam_vbr", ())
    result = _classify_source("https://forums.veeam.com/veeam-backup-replication-f2/topic-12345.html", "community", official, community)
    assert result == "community"


def test_search_domain_accept_knowledge_broadcom():
    from backend.domain.analyzer.services.summary import _classify_source, FAMILY_OFFICIAL_DOMAINS, FAMILY_COMMUNITY_DOMAINS
    official = FAMILY_OFFICIAL_DOMAINS.get("veeam_vbr", ())
    community = FAMILY_COMMUNITY_DOMAINS.get("veeam_vbr", ())
    result = _classify_source("https://knowledge.broadcom.com/external/article?articleNumber=424591", "official", official, community)
    assert result == "official"


def test_vendor_diagnostic_code_includes_session_failed():
    assert is_vendor_diagnostic_code("VEEAM-SESSION-FAILED")
    assert is_vendor_diagnostic_code("VEEAM-REPLICA-SNAPSHOT-CHAIN")
    assert is_vendor_diagnostic_code("VMWARE-CBT-DELETE-FAILED")
    assert not is_vendor_diagnostic_code("VEEAM-UNKNOWN")
    assert not is_vendor_diagnostic_code("")


# ---------------------------------------------------------------------------
# Engineer-grade field correlation: structured evidence fixtures
# (sanitized synthetic shapes only — fake names/IDs, no real hosts)
# ---------------------------------------------------------------------------

FIELD_A_OCT1 = """10/1/2026 1:53:30 AM [VeeamMP] Deleting helper snapshot
10/1/2026 1:54:02 AM [VeeamMP] Could not delete change tracking file
10/1/2026 1:55:10 AM [VeeamMP] Processing finished with errors
"""

FIELD_B_OCT2_KEEPER = """[02.10.2026 00:11:06.410] <09> Info [VeeamAgent] Creating job lease keeper
[02.10.2026 00:12:44.020] <09> Error [VeeamAgent] Task session 'SYNTH-TASK-02' has been completed, status: 'Failed'
"""

FIELD_C_OCT2_REVERT = """[02.10.2026 00:14:02.100] <09> Error [CViSnapReplica] Failed to revert VM name 'synth_replica', ref '19'
[02.10.2026 00:14:02.120] <09> Error [CViSnapReplica] RevertSnapshot failed: InvalidSnapshotFormat
[02.10.2026 00:14:02.140] <09> Error [CViSnapReplica] Detected an invalid snapshot configuration
[02.10.2026 00:14:02.160] <09> Error [VimApi] A required file was not found
"""

FIELD_D_QUOTED_VEEAM_PATH = (
    'log file="C:\\ProgramData\\Veeam\\Backup\\SYNTH-JOB\\Agent.synthetic.log" opened\n'
)

FIELD_E_PROGRAM_FILES = (
    "log dir C:\\Program Files\\Veeam\\Backup\\SYNTH-JOB\\Agent.synthetic.log opened\n"
)


def test_evidence_timestamp_formats():
    iso_raw, iso_key, iso_kind = evidence_mod.parse_evidence_timestamp(
        "2026-10-02T00:11:06Z Task session failed"
    )
    assert iso_kind == "iso8601"
    assert (iso_key.year, iso_key.month, iso_key.day) == (2026, 10, 2)
    assert iso_key.tzinfo is None
    raw_raw, raw_key, raw_kind = evidence_mod.parse_evidence_timestamp(
        "[02.10.2026 00:11:06.410] Task session failed"
    )
    assert raw_kind == "veeam_raw"
    assert (raw_key.year, raw_key.month, raw_key.day, raw_key.hour) == (2026, 10, 2, 0)
    rep_raw, rep_key, rep_kind = evidence_mod.parse_evidence_timestamp(
        "10/1/2026 1:53:30 AM Deleting helper snapshot"
    )
    assert rep_kind == "veeam_report"
    assert (rep_key.year, rep_key.month, rep_key.day, rep_key.hour) == (2026, 10, 1, 1)
    assert evidence_mod.parse_evidence_timestamp("no timestamp here")[1] is None


def test_oct1_sorts_before_oct2():
    recs = evidence_mod.build_evidence_records(
        [("b.log", FIELD_B_OCT2_KEEPER), ("a.log", FIELD_A_OCT1)]
    )
    ordered = evidence_mod.order_records(recs)
    assert ordered[0].source_file == "a.log"
    assert ordered[0].timestamp_kind == "veeam_report"
    assert ordered[-1].source_file == "b.log"


def test_chronology_unchanged_by_file_upload_permutation():
    files_fwd = [("a.log", FIELD_A_OCT1), ("c.log", FIELD_C_OCT2_REVERT)]
    files_rev = [("c.log", FIELD_C_OCT2_REVERT), ("a.log", FIELD_A_OCT1)]
    inc_fwd = incident_from_records(
        evidence_mod.build_evidence_records(files_fwd), "veeam_vbr"
    )
    inc_rev = incident_from_records(
        evidence_mod.build_evidence_records(files_rev), "veeam_vbr"
    )
    for key in (
        "firstMeaningfulFailure",
        "terminalFailure",
        "timeline",
        "operationStage",
        "diagnosticSignatures",
    ):
        assert inc_fwd[key] == inc_rev[key], f"upload order changed {key}"


def test_first_failure_never_follows_terminal_failure():
    # Oct-2 file supplied FIRST in upload order; Oct-1 second.
    inc = incident_from_records(
        evidence_mod.build_evidence_records(
            [("b.log", FIELD_B_OCT2_KEEPER), ("a.log", FIELD_A_OCT1)]
        ),
        "veeam_vbr",
    )
    assert "10/1/2026" in (inc["firstMeaningfulFailure"] or "")
    assert "02.10.2026" in (inc["terminalFailure"] or "")


def test_c_program_never_emitted_as_exact_path():
    paths = resource_paths_for_line(
        "log dir C:\\Program Files\\Veeam\\Backup\\SYNTH-JOB\\Agent.synthetic.log opened"
    )
    assert all(p != "C:\\Program" for p in paths)
    from backend.domain.analyzer.services.bundle import extract_observed_paths

    display = extract_observed_paths(
        "log dir C:\\Program Files\\Veeam\\Backup\\SYNTH-JOB\\Agent.synthetic.log opened"
    )
    assert all(p != "C:\\Program" for p in display)


def test_quoted_windows_path_captured_intact():
    paths = resource_paths_for_line(
        'log file="C:\\Program Files\\BackupVendor\\SYNTH-JOB\\Agent.synthetic.log" opened'
    )
    assert r"C:\Program Files\BackupVendor\SYNTH-JOB\Agent.synthetic.log" in paths
    # A Veeam evidence-source path stays displayable even though it never
    # counts as correlation identity.
    from backend.domain.analyzer.services.bundle import extract_observed_paths

    display = extract_observed_paths(
        'log file="C:\\ProgramData\\Veeam\\Backup\\SYNTH-JOB\\Agent.synthetic.log" opened'
    )
    assert r"C:\ProgramData\Veeam\Backup\SYNTH-JOB\Agent.synthetic.log" in display
    assert (
        r"C:\ProgramData\Veeam\Backup\SYNTH-JOB\Agent.synthetic.log"
        not in resource_paths_for_line(
            'log file="C:\\ProgramData\\Veeam\\Backup\\SYNTH-JOB\\Agent.synthetic.log" opened'
        )
    )


def test_veeam_log_source_path_excluded_from_correlation():
    assert is_log_source_path(
        r"C:\ProgramData\Veeam\Backup\SYNTH-JOB\Agent.synthetic.log"
    )
    assert is_log_source_path(r"%ProgramData%\Veeam\Backup\SYNTH-JOB\Agent.synthetic.log")
    assert not is_log_source_path(
        r"/vmfs/volumes/TEST-DS-01/TEST-VM-01/TEST-VM-01-000003.vmdk"
    )
    a = _bundle_entry(
        "job.log",
        "2026-10-01T01:53:30Z log dir C:\\ProgramData\\Veeam\\Backup\\SYNTH-JOB task started",
    )
    b = _bundle_entry(
        "task.log",
        "2026-10-01T01:54:30Z log dir C:\\ProgramData\\Veeam\\Backup\\SYNTH-JOB task running",
    )
    out = correlate_bundle([a, b])
    assert out["correlationConfidence"] == "none"


def test_shared_log_directory_alone_creates_no_correlation():
    a = _bundle_entry("a.log", "Error: backup stale C:\\ProgramData\\Veeam\\Backup")
    b = _bundle_entry("b.log", "Error: proxy busy C:\\ProgramData\\Veeam\\Backup")
    out = correlate_bundle([a, b])
    assert out["correlationConfidence"] == "none"


def test_vmfs_vmdk_is_correlation_grade():
    paths = resource_paths_for_line(
        "fileName:'/vmfs/volumes/TEST-DS-01/TEST-VM-01/TEST-VM-01-000003.vmdk'"
    )
    assert any("TEST-VM-01-000003.vmdk" in p for p in paths)


def test_bracket_datastore_vmdk_is_correlation_grade():
    paths = resource_paths_for_line("[datastore1] VM01/VM01-000003.vmdk missing")
    assert any("VM01-000003.vmdk" in p for p in paths)
    assert resource_paths_for_line("[CViSnapReplica] RevertSnapshot") == []


def test_shared_vm_identity_with_window_is_medium():
    a = _bundle_entry(
        "job.log",
        "2026-10-02T00:11:06Z vm name 'svrtv004_replica', ref '19' task started",
    )
    b = _bundle_entry(
        "task.log",
        "2026-10-02T00:12:44Z vm name 'svrtv004_replica', ref '19' task failed",
    )
    out = correlate_bundle([a, b])
    assert out["correlationConfidence"] == "medium"
    assert "job.log" in out["correlatedSources"]
    assert "task.log" in out["correlatedSources"]


def test_shared_snapshot_id_with_window_is_medium():
    a = _bundle_entry(
        "a.log",
        "2026-10-02T00:14:02Z snapshot 19-snapshot-5 revert started",
    )
    b = _bundle_entry(
        "b.log",
        "2026-10-02T00:14:20Z snapshot 19-snapshot-5 revert failed",
    )
    out = correlate_bundle([a, b])
    assert out["correlationConfidence"] == "medium"


def test_task_session_id_never_counts_as_strong():
    a = _bundle_entry(
        "a.log",
        "2026-10-02T00:12:44Z Task session 'SYNTH-TASK-02' has been completed, status: 'Failed'",
    )
    b = _bundle_entry(
        "b.log",
        "2026-10-02T00:13:44Z Task session 'SYNTH-TASK-02' referenced again",
    )
    out = correlate_bundle([a, b])
    assert out["correlationConfidence"] != "strong"


def test_lease_keeper_text_never_triggers_318905():
    ids = _kb_ids(
        "VMWARE-SNAPSHOT-FILE-MISSING",
        "Creating job lease keeper\n"
        "RevertSnapshot failed: InvalidSnapshotFormat\n"
        "A required file was not found",
    )
    assert "318905" not in ids
    assert "424591" in ids


def test_bundle_union_gates_operations_locally():
    bundle_text = (
        "===== FILE: a.log =====\n" + FIELD_A_OCT1 + "\n"
        "===== FILE: b.log =====\n" + FIELD_B_OCT2_KEEPER + "\n"
        "===== FILE: c.log =====\n" + FIELD_C_OCT2_REVERT
    )
    ids = _kb_ids("VEEAM-REPLICA-SNAPSHOT-CHAIN", bundle_text)
    assert "424591" in ids
    assert "318905" not in ids
    assert "450780" not in ids
    assert "452165" not in ids
    assert "442155" not in ids
    assert "411756" not in ids


def test_bundle_reference_set_stable_under_permutation():
    seg_a = "===== FILE: a.log =====\n" + FIELD_A_OCT1
    seg_b = "===== FILE: b.log =====\n" + FIELD_B_OCT2_KEEPER
    seg_c = "===== FILE: c.log =====\n" + FIELD_C_OCT2_REVERT
    order_one = "\n".join([seg_a, seg_b, seg_c])
    order_two = "\n".join([seg_c, seg_a, seg_b])
    ids_one = sorted(_kb_ids("VEEAM-REPLICA-SNAPSHOT-CHAIN", order_one))
    ids_two = sorted(_kb_ids("VEEAM-REPLICA-SNAPSHOT-CHAIN", order_two))
    assert ids_one == ids_two
    assert "424591" in ids_one


# ---------------------------------------------------------------------------
# Duplicate guard (must remain last)
# ---------------------------------------------------------------------------


def test_no_duplicate_test_function_names():
    import ast
    with open(__file__, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=__file__)
    top_level_tests = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    unique_names = set(top_level_tests)
    duplicates = [name for name in unique_names if top_level_tests.count(name) > 1]
    assert not duplicates, f"Duplicate top-level test functions found: {duplicates}"
    assert len(top_level_tests) == len(unique_names)
