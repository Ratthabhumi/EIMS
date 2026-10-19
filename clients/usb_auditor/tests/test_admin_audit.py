from types import SimpleNamespace
import importlib.util
from pathlib import Path
from scanner import security, registry, services, compliance


def test_unreadable_controls_are_unknown(monkeypatch):
    monkeypatch.setattr(security, '_run_powershell', lambda *a, **k: '')
    assert security._check_firewall()['status'] == 'UNKNOWN'
    assert security._check_defender()['status'] == 'UNKNOWN'
    assert security._check_bitlocker()['status'] == 'UNKNOWN'
    monkeypatch.setattr(registry, '_read_registry_value', lambda *a: (None, False))
    result = registry._evaluate_check(dict(key='SMBv1', hive='HKEY_LOCAL_MACHINE', path='synthetic', value='SMB1', expected=0, description='synthetic'))
    assert result['status'] == 'UNKNOWN'


def test_demand_start_service_is_not_a_proven_violation(monkeypatch):
    monkeypatch.setattr(services.psutil, 'win_service_get', lambda *a: SimpleNamespace(as_dict=lambda: {'status':'stopped', 'start_type':'manual'}))
    assert services._get_service_status('BITS')['status'] == 'NOT APPLICABLE'
    assert services._get_service_status('wuauserv')['status'] == 'NOT APPLICABLE'


def test_unknown_does_not_count_as_proven_failure_or_compliance():
    result = compliance.calculate_compliance({'firewall': {'status':'UNKNOWN'}}, {}, {}, {})
    assert result['verdict'] == 'Partial'
    assert result['unknown_count'] == 1 and result['fail_count'] == 0


def test_all_nine_stages_preserve_json_and_export(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location('audit_entry_test', Path(__file__).parents[1] / 'main.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    from exporters import json_exporter, excel_exporter
    monkeypatch.setattr(m, 'LOGS_DIR', tmp_path)
    monkeypatch.setattr(json_exporter, 'REPORTS_DIR', tmp_path)
    monkeypatch.setattr(excel_exporter, 'REPORTS_DIR', tmp_path)
    monkeypatch.setattr(m, 'parse_args', lambda: SimpleNamespace(authorized=True, only_export=False, export=False))
    monkeypatch.setattr(m, 'setup_logging', lambda *a: None)
    monkeypatch.setattr(m, 'is_admin', lambda: True)
    monkeypatch.setattr(m, 'get_system_info', lambda: dict(computer_name='SYNTHETIC', username='synthetic', windows_edition='Windows test'))
    for name in ('get_security_info', 'get_services_info', 'get_registry_info', 'get_setup_verify_info'):
        monkeypatch.setattr(m, name, lambda: {})
    monkeypatch.setattr(m, 'collect_firewall_evidence', lambda: {'status':'ok'})
    monkeypatch.setattr(m, 'collect_event_logs', lambda: {'status':'ok', 'collected':0, 'events':[]})
    monkeypatch.setattr(m, 'sync_report', lambda *a: SimpleNamespace(attempted=False))
    assert m.main() == 3  # No applicable checks is not a positive security certification.
    out = capsys.readouterr().out
    assert all(f'[{i}/9]' in out for i in range(1,10))
    assert len(list(tmp_path.glob('*.json'))) == 1
    assert len(list(tmp_path.glob('*.xlsx'))) == 1
    assert 'No automatic network upload was performed.' in out
