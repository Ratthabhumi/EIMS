"""Knowledge-first / offline operation regression tests.

Every test in this module assumes EXTERNAL NETWORK IS DENIED: a fixture
blocks all TCP connection attempts, so any code path that requires a
cloud API, web search, translation service or model download fails loudly
instead of silently degrading into invented analysis.

What is proven here (hermetic, no DB, no keys, no network):
- curated Windows/vendor knowledge resolves with zero network attempts;
- unknown sources stay honest without network;
- Gemini is never invoked without an explicit per-request key;
- missing local embeddings degrade to empty RAG (no crash, no invention);
- the capabilities probe reports real status values;
- catalog results carry confidence while generic fallbacks do not.
"""

import asyncio
import socket

import pytest

from backend.api.routers.analyzer import analyze as analyze_router
from backend.domain.analyzer.services import summary as summary_mod
from backend.domain.analyzer.services import vector_db as vector_db_mod


@pytest.fixture
def no_network(monkeypatch):
    """Block every NON-LOOPBACK TCP connection attempt.

    External cloud/web/model-download traffic fails loudly, while loopback
    (asyncio internals, local test servers) keeps working. Any code path
    that transmits log text to an outside provider raises here.
    """
    import ipaddress

    def _is_loopback(host) -> bool:
        if not isinstance(host, str):
            return True
        h = host.strip().lower().strip("[]")
        if h in ("localhost", "::1") or h.startswith("127."):
            return True
        try:
            return ipaddress.ip_address(h).is_loopback
        except ValueError:
            # Unresolvable hostnames are treated as external (deny).
            return False

    def _boom_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, (tuple, list)) else address
        if _is_loopback(host):
            return _orig_connect(self, address, *args, **kwargs)
        raise OSError("network denied by offline test fixture")

    def _boom_create(address, *args, **kwargs):
        host = address[0] if isinstance(address, (tuple, list)) else address
        if _is_loopback(host):
            return _orig_create(address, *args, **kwargs)
        raise OSError("network denied by offline test fixture")

    _orig_connect = socket.socket.connect
    _orig_create = socket.create_connection
    monkeypatch.setattr(socket, "create_connection", _boom_create)
    monkeypatch.setattr("socket.socket.connect", _boom_connect)
    return True


@pytest.fixture
def no_embeddings(monkeypatch):
    monkeypatch.setattr(vector_db_mod, "_get_embedding", lambda *a, **k: [])


def test_curated_windows_knowledge_needs_no_network(no_network):
    summary = asyncio.run(
        summary_mod.build_summary(
            "4625", "Microsoft-Windows-Security-Auditing", "", [], "en",
            "", None, "synthetic failed logon", None,
            source_family="windows_event",
        )
    )
    assert summary.overview, "curated 4625 must resolve offline"
    blob = " ".join([summary.overview] + summary.causes + summary.steps)
    assert "4625" in blob or "logon" in blob.lower()


def test_vendor_diagnostic_needs_no_network(no_network):
    code = "VEEAM-REPLICA-SNAPSHOT-CHAIN"
    evidence = (
        "[Veeam.Backup.Core] Job Type: Replica\n"
        "[CViSnapReplica] Could not delete change tracking file\n"
        "[VimApi] Deleting helper snapshot\n"
        "[CViSnapReplica] RevertSnapshot failed: InvalidSnapshotFormat\n"
        "[CViSnapReplica] Detected an invalid snapshot configuration\n"
        "[VimApi] A required file was not found\n"
        "[Veeam.Backup.Core] Processing finished with errors"
    )
    summary = asyncio.run(
        summary_mod.build_summary(
            code, "Veeam Backup & Replication", "", [], "en",
            "", None, evidence, None,
            source_family="veeam_vbr", diagnostic_code=code,
            product="Veeam Backup & Replication",
            evidence_text=evidence,
        )
    )
    assert summary.confidence in ("high", "medium", "low")
    assert summary.evidence, "vendor knowledge must carry observed evidence"


def test_unknown_stays_honest_offline(no_network):
    summary = asyncio.run(
        summary_mod.build_summary(
            "Unknown", "Unknown", "", [], "en", "", None,
            "stapler inventory cafeteria menu prose", None,
            source_family="unknown_text",
        )
    )
    blob = " ".join([summary.overview] + summary.causes + summary.steps)
    assert "Windows event log entry" not in blob
    assert summary.confidence == "", "generic fallback must not fake confidence"


def test_gemini_never_called_without_key(no_network, monkeypatch):
    def _forbidden(*args, **kwargs):
        raise AssertionError("Gemini must not be invoked without a key")

    monkeypatch.setattr(summary_mod, "_call_gemini", _forbidden)
    summary = asyncio.run(
        summary_mod.build_summary(
            "99999", "SomeVendor", "", [], "en", "", None,
            "synthetic unrecognized device text", None,
            source_family="windows_event",
        )
    )
    assert isinstance(summary.overview, str) and summary.overview


def test_rag_degrades_without_embeddings(no_embeddings):
    class _FakeDB:
        async def execute(self, query):
            raise AssertionError("no DB access expected in this unit test")

    out = asyncio.run(
        vector_db_mod.search_similar_logs(
            db=_FakeDB(), description="anything", event_id="4625",
            source_family="windows_event",
        )
    )
    assert out == []


def test_search_falls_back_without_network(no_network):
    results, _snippets = summary_mod.search_solutions(
        "VEEAM-REPLICA-SNAPSHOT-CHAIN", "Veeam Backup & Replication",
        source_family="veeam_vbr",
    )
    assert results, "vendor fallback references must exist offline"
    assert all("learn.microsoft.com" not in r.link for r in results)


def test_capabilities_reports_real_status():
    caps = asyncio.run(analyze_router.analyzer_capabilities())
    assert set(caps) == {
        "localKnowledge", "catalogEntries", "vectorRetrieval", "externalAI",
    }
    assert caps["localKnowledge"] is True
    assert caps["catalogEntries"] == 163
    assert caps["vectorRetrieval"] in ("available", "not-cached", "unavailable")
    assert caps["externalAI"] == "disabled"
