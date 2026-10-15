"""Bounded end-to-end knowledge-only test in a disposable sandbox.

Spins up the REAL analyze/history routers on disposable SQLite
(`tools.history_sandbox`) as a subprocess with poisoned proxy variables,
so any external HTTP attempt (search, AI, translation, model download)
fails fast at the process level — on top of the sandbox's own code-level
stubs. Loopback stays allowed via NO_PROXY.

Proves with real HTTP + real parsers + real persistence:
- curated Windows knowledge answers with zero external calls;
- a supported Veeam diagnostic resolves deterministically;
- unknown input stays honestly unsupported (no fabricated RCA);
- malformed input degrades gracefully (never a 500 with traceback);
- every analysis persists through real routes and reopens from History;
- no operational application is reachable during the run (:8000 free).

Nothing here touches PostgreSQL, the network, or any human data.
"""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request

import pytest

SANDBOX_PORT = 3117
SANDBOX_URL = f"http://127.0.0.1:{SANDBOX_PORT}"

WIN_4625 = """Log Name: Security
Source: Microsoft-Windows-Security-Auditing
Event ID: 4625
Level: Error
Computer: SYNTH-TEST-01
Description: An account failed to log on (synthetic fixture)."""

VEEAM_TEXT = """[Veeam.Backup.Core] Job Type: Replica
[VimApi] Processing object 'SYNTH-REPLICA-01'
[CViSnapReplica] Could not delete change tracking file
[VimApi] Deleting helper snapshot
[CViSnapReplica] RevertSnapshot failed: InvalidSnapshotFormat
[CViSnapReplica] Detected an invalid snapshot configuration
[VimApi] A required file was not found
[Veeam.Backup.Core] Processing finished with errors"""

UNKNOWN_TEXT = "Synthetic cafeteria inventory prose with no log semantics at all."


def _port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _wait_ready(timeout_s: float = 60.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(SANDBOX_URL + "/__sandbox", timeout=3) as r:
                ident = json.load(r)
            assert ident.get("dialect") == "sqlite", ident
            assert ident.get("operational_startup") is False, ident
            return
        except Exception:
            time.sleep(1.0)
    raise RuntimeError("sandbox API did not become ready")


def _post_analysis(text: str):
    data = urllib.parse.urlencode({"text": text, "language": "en"}).encode()
    req = urllib.request.Request(
        SANDBOX_URL + "/api/v1/analyze/", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        assert r.status == 200
        return json.load(r)


@pytest.fixture(scope="module")
def sandbox_server():
    assert _port_free(8000), "operational app must be absent during offline E2E"
    assert _port_free(SANDBOX_PORT)
    env = dict(os.environ)
    env["HTTP_PROXY"] = "http://127.0.0.1:9"
    env["HTTPS_PROXY"] = "http://127.0.0.1:9"
    env["NO_PROXY"] = "127.0.0.1,localhost"
    env["no_proxy"] = "127.0.0.1,localhost"
    proc = subprocess.Popen(
        [sys.executable, "-m", "tools.history_sandbox", "--port", str(SANDBOX_PORT)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        _wait_ready()
        yield proc
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()
        for _ in range(15):
            if _port_free(SANDBOX_PORT):
                break
            time.sleep(1.0)
        assert _port_free(SANDBOX_PORT), "sandbox port must be released"


def test_proxy_denial_is_effective():
    """The poisoned proxy env itself must break external HTTP (loopback OK)."""
    env_blocked = {"HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9",
                   "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}
    code = (
        "import os, urllib.request; "
        f"os.environ.update({env_blocked!r}); "
        "urllib.request.urlopen('http://example.com', timeout=10)"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=60)
    assert proc.returncode != 0, "external HTTP must fail under poisoned proxy"


def test_e2e_curated_windows_knowledge_only(sandbox_server):
    body = _post_analysis(WIN_4625)
    assert body["eventId"] == "4625"
    assert body["solutionSummary"]["overview"], "curated answer must be present"
    assert body["historyId"], "analysis must persist"


def test_e2e_supported_veeam_diagnostic(sandbox_server):
    body = _post_analysis(VEEAM_TEXT)
    assert body["eventId"] == "VEEAM-REPLICA-SNAPSHOT-CHAIN"
    assert body["solutionSummary"]["confidence"] in ("high", "medium", "low")
    assert body["eventMetadata"]["sourceFamily"] == "veeam_vbr"


def test_e2e_unknown_stays_unsupported(sandbox_server):
    body = _post_analysis(UNKNOWN_TEXT)
    assert body["eventId"] == "Unknown"
    blob = " ".join([
        body["solutionSummary"]["overview"],
        *body["solutionSummary"]["causes"],
        *body["solutionSummary"]["steps"],
    ])
    assert "Windows event log entry" not in blob
    assert body["solutionSummary"]["confidence"] == ""


def test_e2e_malformed_input_degrades_gracefully(sandbox_server):
    data = urllib.parse.urlencode({"text": "", "language": "en"}).encode()
    req = urllib.request.Request(
        SANDBOX_URL + "/api/v1/analyze/", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            assert r.status in (200, 400, 422)
    except urllib.error.HTTPError as e:
        assert e.code in (400, 422), f"malformed input must not 500, got {e.code}"
        assert b"Traceback" not in e.read()


def test_e2e_history_round_trip(sandbox_server):
    with urllib.request.urlopen(SANDBOX_URL + "/api/v1/history/", timeout=30) as r:
        rows = json.load(r)
    ids = {row.get("eventId") for row in rows}
    assert {"4625", "VEEAM-REPLICA-SNAPSHOT-CHAIN", "Unknown"} <= ids
