"""Tests for JSON report assembly with Sprint 13 event evidence.

Verifies:
   1. save_report accepts an optional `event_logs` payload and embeds it.
   2. Reports without `event_logs` stay byte-structurally unchanged (backward compat).
   3. No BitLocker recovery-password-like material can ride inside event_logs.
"""

import json

from exporters import json_exporter

BASE_SYSTEM = {"computer_name": "TEST-PC", "ip_address": "10.0.0.5", "mac_address": "AA:BB:CC:DD:EE:FF"}
BASE_SECURITY = {"firewall": {"status": "PASS", "enabled": True}}
BASE_SERVICES = {"WinDefend": {"status": "PASS", "actual_state": "Running"}}
BASE_REGISTRY = {"UAC": {"status": "PASS", "actual": 1}}
BASE_COMPLIANCE = {"score": 95, "verdict": "Compliant", "pass_count": 5, "warning_count": 0, "fail_count": 0}

FAKE_RECOVERY_LIKE = "000000-000000-000000-000000-000000-000000-000000-000000"


def _simple_report(event_logs=None) -> dict:
    return {"system": BASE_SYSTEM,
            "security": BASE_SECURITY,
            "services": BASE_SERVICES,
            "registry": BASE_REGISTRY,
            "compliance": BASE_COMPLIANCE,
            "event_logs": event_logs}


def _save(system=None, security=None, services=None, registry=None, compliance=None, event_logs=None, tmp_path=None):
    import config.settings as settings
    if tmp_path is not None:
        json_exporter.REPORTS_DIR = tmp_path / "reports"
        json_exporter.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return json_exporter.save_report(
        system or BASE_SYSTEM,
        security or BASE_SECURITY,
        services or BASE_SERVICES,
        registry or BASE_REGISTRY,
        compliance or BASE_COMPLIANCE,
        event_logs=event_logs,
    )


class TestSaveReportEventLogs:
    def test_with_event_logs(self, tmp_path):
        event_logs = {
            "enabled": True,
            "collection_hours": 24,
            "max_records": 500,
            "channels": ["System", "Application"],
            "levels": [1, 2, 3],
            "collected": 1,
            "status": "ok",
            "events": [{"event_id": 10016, "provider": "DistributedCOM", "severity": "Error", "channel": "System", "record_id": 9, "occurrence_time": "2026-09-14T10:00:00", "message": "DCOM"}],
        }
        path = _save(event_logs=event_logs, tmp_path=tmp_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["event_logs"]["collected"] == 1
        assert data["event_logs"]["events"][0]["event_id"] == 10016

    def test_without_event_logs_backward_compat(self, tmp_path):
        path = _save(tmp_path=tmp_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "event_logs" not in data
        assert data["compliance_score"] == 95
        assert data["metadata"]["report_format"] == "1"

    def test_event_logs_none_omitted(self, tmp_path):
        path = _save(event_logs=None, tmp_path=tmp_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "event_logs" not in data

    def test_no_recovery_key_in_event_logs(self, tmp_path):
        event_logs = {
            "enabled": True,
            "status": "ok",
            "collected": 1,
            "events": [{"event_id": 10016, "provider": "DistributedCOM", "severity": "Error", "channel": "System", "record_id": 1, "occurrence_time": "t", "message": "msg"}],
        }
        path = _save(event_logs=event_logs, tmp_path=tmp_path)
        raw = path.read_text(encoding="utf-8")
        assert FAKE_RECOVERY_LIKE not in raw
        assert "recovery_password" not in raw.lower()