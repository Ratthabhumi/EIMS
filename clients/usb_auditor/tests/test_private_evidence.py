import json
import subprocess
from types import SimpleNamespace

import pytest
from config import settings
from exporters import json_exporter as exporter
from scanner import event_logs


def test_repeated_scan_preserves_both_reports_and_legacy_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(exporter, 'REPORTS_DIR', tmp_path)
    args = ({'computer_name': 'SYNTHETIC'}, {}, {}, {}, {'score': 90})
    first = exporter.save_report(*args)
    second = exporter.save_report(*args)
    assert first != second
    assert first.exists() and second.exists()
    data = json.loads(second.read_text('utf-8'))
    assert data['system']['computer_name'] == 'SYNTHETIC'
    assert data['metadata']['event_evidence_status'] == 'unavailable'
    assert 'event_logs' not in data


def test_secrets_are_redacted_even_inside_event_messages():
    secret = '-'.join(['123456'] * 8)
    data = exporter.redact_secrets({'security': {'recovery_key': secret, 'protection_status': 'On'},
                                  'events': [{'message': secret, 'RecoveryPassword': secret}]})
    assert secret not in json.dumps(data)
    assert 'recovery_key' not in json.dumps(data)
    assert data['security']['protection_status'] == 'On'


def test_sync_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv('EIMS_AUTO_SYNC', raising=False)
    assert not settings.is_auto_sync_enabled()


def test_failed_process_cannot_be_a_successful_empty_collection(monkeypatch):
    monkeypatch.setattr(event_logs.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=1, stdout=''))
    with pytest.raises(RuntimeError):
        event_logs._run_powershell('synthetic')


def test_no_matching_events_remains_valid(monkeypatch):
    monkeypatch.setattr(settings, 'EVENT_LOG_ENABLED', True)
    monkeypatch.setattr(event_logs, '_run_powershell', lambda *a, **kw: '[]')
    result = event_logs.collect_event_logs()
    assert result['status'] == 'ok' and result['collected'] == 0
