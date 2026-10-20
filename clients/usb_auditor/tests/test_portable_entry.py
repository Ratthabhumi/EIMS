import json
from pathlib import Path
import pytest
import portable_entry as entry
from scanner.event_logs import _parse_events
from exporters.json_exporter import redact_secrets


def test_local_evidence_private_and_previous_reports_survive(tmp_path):
    evidence = entry.prepare_output(tmp_path)
    entry.verify_private_acl(evidence)
    prior = evidence / 'reports/prior-synthetic.json'
    prior.write_text('{"synthetic": true}', encoding='utf-8')
    assert entry.prepare_output(tmp_path) == evidence
    assert prior.read_text('utf-8') == '{"synthetic": true}'


def test_missing_parent_and_network_destinations_fail_before_collection(tmp_path):
    for bad in [tmp_path / 'missing/Evidence', Path(r'\\synthetic-share\audit\Evidence')]:
        with pytest.raises((ValueError, OSError)):
            entry.prepare_output(tmp_path, str(bad))


def test_non_acl_media_requires_explicit_encryption_approval_record(tmp_path, monkeypatch):
    monkeypatch.setattr(entry, 'volume_info', lambda p: (2, False))
    with pytest.raises(PermissionError):
        entry.prepare_output(tmp_path)
    assert not (tmp_path / 'Evidence').exists()
    (tmp_path / 'audit-policy.json').write_text(json.dumps({
        'encrypted_removable_media_approved': True, 'approval_reference': 'SYNTHETIC-UNIT-TEST-ONLY'}))
    assert entry.prepare_output(tmp_path) == tmp_path / 'Evidence'


def test_ntfs_usb_defaults_to_beside_exe_and_preserves_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(entry, 'volume_info', lambda p: (2, True))
    evidence = entry.prepare_output(tmp_path)
    assert evidence == tmp_path / 'Evidence'
    entry.verify_private_acl(evidence, portable=True)
    prior = evidence / 'reports' / 'synthetic.json'
    prior.write_text('{}', encoding='utf-8')
    assert entry.prepare_output(tmp_path) == evidence
    assert prior.read_text('utf-8') == '{}'


def test_low_space_fails_before_creating_evidence(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(entry.shutil, 'disk_usage', lambda p: SimpleNamespace(free=0))
    with pytest.raises(OSError):
        entry.prepare_output(tmp_path)
    assert not (tmp_path / 'Evidence').exists()


def test_unwritable_output_fails_and_never_redirects(tmp_path, monkeypatch):
    original = Path.open
    def denied(path, *args, **kwargs):
        if '.write-check-' in path.name:
            raise PermissionError('synthetic denied destination')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', denied)
    with pytest.raises(PermissionError):
        entry.prepare_output(tmp_path)
    assert list(tmp_path.rglob('*.json')) == []


def test_complete_long_message_and_explicit_utf8_cap():
    text = 'Synthetic complete message ' * 100
    rows = _parse_events(json.dumps([{'Id': 11, 'Message': text}]))
    assert rows[0]['message'] == text and not rows[0]['message_truncated']
    rows = _parse_events(json.dumps([{'Id': 11, 'Message': 'ก' * 30000}]))
    assert len(rows[0]['message'].encode('utf-8')) <= 65536
    assert rows[0]['message_truncated'] and rows[0]['message_original_bytes'] == 90000


def test_total_message_budget_retains_record_identity():
    rows = _parse_events(json.dumps([{'Id': 11, 'RecordId': i, 'Message': 'x' * 70000} for i in range(130)]))
    assert len(rows) == 130 and rows[-1]['record_id'] == 129
    assert sum(r['message_saved_bytes'] for r in rows) <= 8 * 1024 * 1024
    assert rows[-1]['message_truncation_reason'] == 'collection_message_limit'


def test_embedded_secrets_not_retained_in_messages():
    text = 'password="SYNTHETIC_SECRET" access_token=SYNTHETIC_TOKEN'
    cleaned = redact_secrets(text)
    assert 'SYNTHETIC_SECRET' not in cleaned and 'SYNTHETIC_TOKEN' not in cleaned


def test_portable_acl_not_bound_to_current_machine_sid(tmp_path,monkeypatch):
    folder=tmp_path/'Portable';folder.mkdir()
    entry.protect_new_directory(folder,portable=True)
    entry.verify_private_acl(folder,portable=True)
    monkeypatch.setattr(entry,'current_sid',lambda:'S-1-5-21-111-222-333-1001')
    entry.verify_private_acl(folder,portable=True)
