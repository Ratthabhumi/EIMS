"""Focused tests for the offline-first EIMS auto-sync module.

Covers: disabled, success (correct endpoint/file/field), backend unavailable,
timeout, HTTP 4xx/5xx, invalid response JSON, URL normalization, and the
BitLocker secret-regression invariant (sync never logs/exposes or enriches
recovery-password-like material, and uploads exactly the saved local file).
"""

import json
import socket
from pathlib import Path
from urllib.error import URLError

import pytest

from config import settings
from sync import eims_sync

FAKE_RECOVERY_LIKE = "000000-000000-000000-000000-000000-000000-000000-000000"

BACKEND_RESPONSE_OK = json.dumps(
    {"hostname": "SYNC-TEST-01", "current_compliance_score": 92}
)


@pytest.fixture
def report_file(tmp_path, monkeypatch) -> Path:
    """A normal, scanner-safe local report (no secret fields)."""
    monkeypatch.setattr(settings, "EIMS_API_URL", "http://localhost:8000")
    monkeypatch.setattr(settings, "is_auto_sync_enabled", lambda: True)
    report = {
        "metadata": {"auditor_version": "1.0.0", "report_format": "1"},
        "system": {
            "computer_name": "SYNC-TEST-01",
            "ip_address": "192.0.2.10",
            "mac_address": "AA:BB:CC:DD:EE:FF",
        },
        "security": {
            "firewall": {"status": "PASS", "enabled": True},
            "bitlocker": {
                "status": "PASS",
                "protection_status": "On",
                "recovery_protector_present": True,
                "recovery_protector_count": 1,
            },
        },
        "services": {},
        "registry": {},
        "setup_verify": {},
        "compliance_score": 92,
        "compliance": {"score": 92, "verdict": "Compliant"},
    }
    path = tmp_path / "SYNC-TEST-01_2026-01-01_12.00.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ── 1. Disabled ──────────────────────────────────────────────────────────────

def test_auto_sync_disabled_makes_no_request(monkeypatch, report_file):
    monkeypatch.setattr(settings, "is_auto_sync_enabled", lambda: False)
    called = []

    def spy(*args, **kwargs):
        called.append(args)
        return 200, BACKEND_RESPONSE_OK

    monkeypatch.setattr(eims_sync, "_http_post_multipart", spy)
    result = eims_sync.sync_report(report_file)

    assert called == []
    assert result.attempted is False
    assert result.success is False
    assert report_file.is_file()


# ── 2. Successful sync ───────────────────────────────────────────────────────

def test_success_uploads_exact_saved_file(monkeypatch, report_file):
    captured = {}

    def fake_post(url, field_name, filename, filedata, timeout):
        captured.update(
            url=url, field_name=field_name, filename=filename,
            filedata=filedata, timeout=timeout,
        )
        return 200, BACKEND_RESPONSE_OK

    monkeypatch.setattr(eims_sync, "_http_post_multipart", fake_post)
    result = eims_sync.sync_report(report_file)

    assert result.success is True
    assert result.attempted is True
    assert result.status_code == 200
    assert result.asset_hostname == "SYNC-TEST-01"
    assert result.compliance_score == 92

    assert captured["url"] == "http://localhost:8000/api/v1/assets/import-report"
    assert captured["field_name"] == "file"
    assert captured["filename"] == report_file.name
    assert captured["timeout"] == eims_sync.DEFAULT_TIMEOUT_SECONDS
    # Uploaded bytes are EXACTLY the saved local file (evidence parity,
    # no re-serialization / no enrichment).
    assert captured["filedata"] == report_file.read_bytes()
    assert FAKE_RECOVERY_LIKE.encode("utf-8") not in captured["filedata"]


# ── 3. Backend unavailable ───────────────────────────────────────────────────

def test_backend_unavailable_is_non_fatal(monkeypatch, report_file):
    def connection_refused(*args, **kwargs):
        raise URLError(ConnectionRefusedError(10061, "Connection refused"))

    monkeypatch.setattr(eims_sync, "_http_post_multipart", connection_refused)
    result = eims_sync.sync_report(report_file)

    assert result.attempted is True
    assert result.success is False
    assert "unavailable" in result.message.lower()
    assert report_file.is_file()


# ── 4. Timeout ───────────────────────────────────────────────────────────────

def test_timeout_is_bounded_and_non_fatal(monkeypatch, report_file):
    def hang(*args, **kwargs):
        raise socket.timeout("timed out")

    monkeypatch.setattr(eims_sync, "_http_post_multipart", hang)
    result = eims_sync.sync_report(report_file)

    assert result.attempted is True
    assert result.success is False
    assert "timed out" in result.message.lower()
    assert report_file.is_file()


# ── 5/6. HTTP 4xx / 5xx ──────────────────────────────────────────────────────

@pytest.mark.parametrize("code", [400, 401, 403, 500, 503])
def test_http_error_statuses_are_safe_warnings(monkeypatch, report_file, code):
    def reject(*args, **kwargs):
        return code, "{}"

    monkeypatch.setattr(eims_sync, "_http_post_multipart", reject)
    result = eims_sync.sync_report(report_file)

    assert result.attempted is True
    assert result.success is False
    assert result.status_code == code
    assert str(code) in result.message
    assert report_file.is_file()


# ── 7. Invalid response JSON ─────────────────────────────────────────────────

def test_invalid_response_json_does_not_crash(monkeypatch, report_file):
    def garbage(*args, **kwargs):
        return 200, "<html>definitely not json"

    monkeypatch.setattr(eims_sync, "_http_post_multipart", garbage)
    result = eims_sync.sync_report(report_file)

    assert result.attempted is True
    assert result.status_code == 200
    assert result.success is True  # server accepted; unparseable body ignored
    assert result.asset_hostname is None


# ── 8. URL normalization ─────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "base,expected",
    [
        ("http://localhost:8000", "http://localhost:8000/api/v1/assets/import-report"),
        ("http://localhost:8000/", "http://localhost:8000/api/v1/assets/import-report"),
        (" https://eims.internal:8443/  ", "https://eims.internal:8443/api/v1/assets/import-report"),
        ("", "http://localhost:8000/api/v1/assets/import-report"),
    ],
)
def test_url_normalization(monkeypatch, base, expected):
    monkeypatch.setattr(settings, "EIMS_API_URL", "http://localhost:8000")
    assert eims_sync.build_import_endpoint(base) == expected


# ── 9. Secret regression ─────────────────────────────────────────────────────

def test_sync_never_logs_or_exposes_secret_material(caplog, monkeypatch, report_file):
    # Adversarial/local file that (hypothetically) contains recovery-looking
    # material in a benign field — the sync module must not echo it anywhere.
    report_file.write_text(
        json.dumps(
            {
                "metadata": {"auditor_version": "1.0.0", "report_format": "1"},
                "system": {"computer_name": "SYNC-TEST-01"},
                "notes": f"leftover value = {FAKE_RECOVERY_LIKE}",
                "compliance_score": 91,
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    def fake_post(url, field_name, filename, filedata, timeout):
        captured["filedata"] = filedata
        return 200, BACKEND_RESPONSE_OK

    monkeypatch.setattr(eims_sync, "_http_post_multipart", fake_post)
    result = eims_sync.sync_report(report_file)

    assert result.success is True
    # Never echoed into logs or into the console-ready result message.
    assert FAKE_RECOVERY_LIKE not in result.message
    assert FAKE_RECOVERY_LIKE not in caplog.text
    # Upload is a byte-for-byte copy of the local file: no enrichment, no
    # insertion of any secret field by the sync path.
    assert captured["filedata"] == report_file.read_bytes()


def test_auto_sync_settings_enabled_values():
    for raw in ("1", "true", "yes", "on", "TRUE", "Yes", "ON"):
        assert settings._parse_flag(raw) is True
    for raw in ("0", "false", "no", "off", "", "banana"):
        assert settings._parse_flag(raw) is False