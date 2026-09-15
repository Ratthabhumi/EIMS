"""Tests for the USB Auditor event log collector (scanner/event_logs.py).

Covers: config clamping, PowerShell command construction, JSON parsing,
success/error/disabled paths, message truncation, env integration, and the
BitLocker secret-regression boundary (event_logs never contain recovery keys).
"""

import json

import pytest

from scanner.event_logs import (
    _clamp,
    _build_powershell_command,
    _parse_events,
    _parse_occurrence_time,
    _truncate_message,
    collect_event_logs,
)
import config.settings as settings


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------

class TestClamp:
    def test_mid_range(self):
        assert _clamp(50, 1, 100) == 50

    def test_below_min(self):
        assert _clamp(-10, 0, 100) == 0

    def test_above_max(self):
        assert _clamp(999, 1, 500) == 500

    def test_exact_bounds(self):
        assert _clamp(1, 1, 168) == 1
        assert _clamp(168, 1, 168) == 168


class TestTruncateMessage:
    def test_short_message_unchanged(self):
        assert _truncate_message("hello") == "hello"

    def test_long_message_truncated(self):
        result = _truncate_message("x" * 600)
        assert len(result) == 503  # 500 + "..."
        assert result.endswith("...")

    def test_empty_message(self):
        assert _truncate_message("") == ""
        assert _truncate_message(None) == ""

    def test_exact_boundary(self):
        msg = "a" * 500
        assert _truncate_message(msg) == msg


class TestBuildPowershellCommand:
    def test_basic_structure(self, monkeypatch):
        monkeypatch.setattr(settings, "EVENT_LOG_ENABLED", True)
        cmd = _build_powershell_command(24, 500)
        assert "Get-WinEvent" in cmd
        assert "-MaxEvents 500" in cmd
        assert "System" in cmd
        assert "Application" in cmd
        assert "Level=@(1,2,3)" in cmd

    def test_hours_reflected(self, monkeypatch):
        monkeypatch.setattr(settings, "EVENT_LOG_ENABLED", True)
        cmd = _build_powershell_command(72, 100)
        assert "-MaxEvents 100" in cmd


class TestParseOccurrenceTime:
    def test_wmi_epoch_ms_normalized(self):
        assert _parse_occurrence_time("/Date(0)/") == "1970-01-01T00:00:00+00:00"
        assert _parse_occurrence_time("/Date(1700000000000)/") == "2023-11-14T22:13:20+00:00"

    def test_iso_passthrough(self):
        assert _parse_occurrence_time("2026-09-14T10:00:00") == "2026-09-14T10:00:00"

    def test_empty_and_invalid(self):
        assert _parse_occurrence_time("") == ""
        assert _parse_occurrence_time(None) == ""
        assert _parse_occurrence_time("/Date(notanumber)/") == ""

    def test_wmi_time_in_parse_events(self):
        event = {
            "TimeCreated": "/Date(1700000000000)/",
            "Id": 10016,
            "ProviderName": "DistributedCOM",
            "LevelDisplayName": "Error",
            "LogName": "System",
            "RecordId": 12345,
            "Message": "DCOM error",
        }
        result = _parse_events(json.dumps(event))
        assert result[0]["occurrence_time"] == "2023-11-14T22:13:20+00:00"


class TestParseEvents:
    def test_empty_input(self):
        assert _parse_events("") == []
        assert _parse_events(None) == []

    def test_invalid_json(self):
        assert _parse_events("not json") == []

    def test_single_event(self):
        event = {
            "TimeCreated": "2026-09-14T10:00:00",
            "Id": 10016,
            "ProviderName": "DistributedCOM",
            "LevelDisplayName": "Error",
            "LogName": "System",
            "RecordId": 12345,
            "Message": "DCOM error message",
        }
        result = _parse_events(json.dumps(event))
        assert len(result) == 1
        assert result[0]["event_id"] == 10016
        assert result[0]["provider"] == "DistributedCOM"
        assert result[0]["severity"] == "Error"
        assert result[0]["channel"] == "System"
        assert result[0]["record_id"] == 12345

    def test_multiple_events(self):
        events = [
            {"TimeCreated": "t1", "Id": 41, "ProviderName": "Kernel-Power", "LevelDisplayName": "Critical", "LogName": "System", "RecordId": 1},
            {"TimeCreated": "t2", "Id": 7031, "ProviderName": "Service Control Manager", "LevelDisplayName": "Error", "LogName": "System", "RecordId": 2},
        ]
        result = _parse_events(json.dumps(events))
        assert len(result) == 2

    def test_message_truncation(self):
        event = {"Id": 1, "ProviderName": "Test", "LevelDisplayName": "Info", "LogName": "System", "Message": "x" * 600}
        result = _parse_events(json.dumps(event))
        assert len(result[0]["message"]) == 503


# ---------------------------------------------------------------------------
# collect_event_logs integration (env-driven)
# ---------------------------------------------------------------------------

class TestCollectEventLogs:
    def test_disabled_returns_disabled_status(self, monkeypatch):
        monkeypatch.setattr(settings, "EVENT_LOG_ENABLED", False)
        result = collect_event_logs()
        assert result["status"] == "disabled"
        assert result["events"] == []
        assert result["enabled"] is False
        assert result["collected"] == 0

    def test_enabled_calls_powershell(self, monkeypatch):
        monkeypatch.setattr(settings, "EVENT_LOG_ENABLED", True)
        monkeypatch.setattr(settings, "EVENT_LOG_HOURS", 24)
        monkeypatch.setattr(settings, "EVENT_LOG_MAX_RECORDS", 100)

        fake_event = {
            "TimeCreated": "2026-09-14T10:00:00",
            "Id": 41,
            "ProviderName": "Kernel-Power",
            "LevelDisplayName": "Critical",
            "LogName": "System",
            "RecordId": 1,
            "Message": "Kernel Power critical",
        }
        fake_output = json.dumps([fake_event])

        import scanner.event_logs as mod
        monkeypatch.setattr(mod, "_run_powershell", lambda cmd, timeout=30: fake_output)

        result = collect_event_logs()
        assert result["status"] == "ok"
        assert result["collected"] == 1
        assert len(result["events"]) == 1
        assert result["events"][0]["event_id"] == 41
        assert result["events"][0]["severity"] == "Critical"

    def test_powershell_failure_returns_error(self, monkeypatch):
        monkeypatch.setattr(settings, "EVENT_LOG_ENABLED", True)
        monkeypatch.setattr(settings, "EVENT_LOG_HOURS", 24)
        monkeypatch.setattr(settings, "EVENT_LOG_MAX_RECORDS", 100)

        import scanner.event_logs as mod
        monkeypatch.setattr(mod, "_run_powershell", lambda cmd, timeout=30: "")

        result = collect_event_logs()
        assert result["status"] == "ok"
        assert result["collected"] == 0
        assert result["events"] == []

    def test_unexpected_exception_returns_error(self, monkeypatch):
        monkeypatch.setattr(settings, "EVENT_LOG_ENABLED", True)
        monkeypatch.setattr(settings, "EVENT_LOG_HOURS", 24)
        monkeypatch.setattr(settings, "EVENT_LOG_MAX_RECORDS", 100)

        import scanner.event_logs as mod
        def bomb(cmd, timeout=30):
            raise RuntimeError("explode")
        monkeypatch.setattr(mod, "_run_powershell", bomb)

        result = collect_event_logs()
        assert result["status"] == "error"
        assert result["events"] == []

    def test_output_fields_present(self, monkeypatch):
        monkeypatch.setattr(settings, "EVENT_LOG_ENABLED", True)
        monkeypatch.setattr(settings, "EVENT_LOG_HOURS", 12)
        monkeypatch.setattr(settings, "EVENT_LOG_MAX_RECORDS", 50)

        import scanner.event_logs as mod
        monkeypatch.setattr(mod, "_run_powershell", lambda cmd, timeout=30: "[]")

        result = collect_event_logs()
        for key in ("enabled", "collection_hours", "max_records", "channels", "levels", "collected", "status", "message", "events"):
            assert key in result


# ---------------------------------------------------------------------------
# Security boundary: no BitLocker recovery keys
# ---------------------------------------------------------------------------

class TestNoRecoveryKeys:
    """Verify event_logs never stores RecoveryPassword / recovery_key fields."""

    def test_event_dict_has_no_recovery_fields(self, monkeypatch):
        monkeypatch.setattr(settings, "EVENT_LOG_ENABLED", True)
        monkeypatch.setattr(settings, "EVENT_LOG_HOURS", 24)
        monkeypatch.setattr(settings, "EVENT_LOG_MAX_RECORDS", 10)

        import scanner.event_logs as mod
        event = {
            "TimeCreated": "2026-09-14T10:00:00",
            "Id": 10016,
            "ProviderName": "DistributedCOM",
            "LevelDisplayName": "Error",
            "LogName": "System",
            "RecordId": 1,
            "Message": "DCOM error",
        }
        monkeypatch.setattr(mod, "_run_powershell", lambda cmd, timeout=30: json.dumps([event]))

        result = collect_event_logs()
        serialized = json.dumps(result)
        assert "RecoveryPassword" not in serialized
        assert "recovery_password" not in serialized
        assert "recovery_key" not in serialized
        assert "RECOVERYPASSWORD" not in serialized

    def test_output_never_exposes_ps_command(self, monkeypatch):
        """The raw PowerShell command must never leak into the output."""
        monkeypatch.setattr(settings, "EVENT_LOG_ENABLED", True)
        monkeypatch.setattr(settings, "EVENT_LOG_HOURS", 24)
        monkeypatch.setattr(settings, "EVENT_LOG_MAX_RECORDS", 10)

        import scanner.event_logs as mod
        monkeypatch.setattr(mod, "_run_powershell", lambda cmd, timeout=30: "[]")

        result = collect_event_logs()
        serialized = json.dumps(result)
        assert "Get-WinEvent" not in serialized
