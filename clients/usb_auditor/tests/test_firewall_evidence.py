import json
from types import SimpleNamespace
from scanner import firewall_evidence as f


def test_unsupported_checks_do_not_claim_empty_success(monkeypatch):
    monkeypatch.setattr(f.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=1, stdout=''))
    result = f.collect_firewall_evidence()
    assert result['status'] == 'partial'
    assert all(result[k]['status'] == 'unavailable' for k in f.QUERIES)


def test_bounded_read_only_rows_and_explicit_truncation(monkeypatch):
    commands = []
    def run(args, **kwargs):
        commands.append(args[-1])
        return SimpleNamespace(returncode=0, stdout=json.dumps([{'LocalPort': 123}] * 501))
    monkeypatch.setattr(f.subprocess, 'run', run)
    result = f.collect_firewall_evidence()
    assert result['tcp_listeners']['truncated']
    assert len(result['tcp_listeners']['records']) == 500
    assert len(result['inbound_rules']['records']) == 200
    assert all('Select-Object -First' in c for c in commands)
    assert not any(verb in c for c in commands for verb in ('Set-Net', 'New-Net', 'Remove-Net'))
