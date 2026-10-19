import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('usb_backup', Path(__file__).parents[1] / 'handover/usb_backup.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def setup(tmp_path, monkeypatch):
    payload = tmp_path / 'USB/Final_EIMS_Project'
    (payload / 'Tools').mkdir(parents=True)
    (payload / 'Tools/package.json').write_text(json.dumps({'id': 'eims-0000000000000000', 'storageMode': 'USB_CHECKPOINT', 'mediaId': '00000000000000000000000000000000'}))
    install = tmp_path / 'Local'
    private = install / 'Private'
    private.mkdir(parents=True)
    (install / 'installation.json').write_text(json.dumps({'project': 'eims-synthetic'}))
    (private / '.env').write_text('EIMS_ADMIN_PASSWORD=SYNTHETIC_ONLY\n')
    (private / 'LOCAL_ADMIN.txt').write_text('SYNTHETIC_ONLY')
    monkeypatch.setattr(backup, 'object_client', lambda p: SimpleNamespace(list_buckets=lambda: {'Buckets': []}))
    def dump(command, **kwargs):
        kwargs['stdout'].write(b'PGDMP-SYNTHETIC-POSTGRES-DUMP')
    monkeypatch.setattr(backup.subprocess, 'run', dump)
    return payload, install


def test_complete_checkpoint_is_verified_and_failed_new_copy_preserves_it(tmp_path, monkeypatch):
    payload, install = setup(tmp_path, monkeypatch)
    first = backup.checkpoint(install, payload)
    backup.verified_checkpoint(first)
    def unplug(*args, **kwargs):
        raise OSError('synthetic unplug')
    monkeypatch.setattr(backup.subprocess, 'run', unplug)
    with pytest.raises(OSError):
        backup.checkpoint(install, payload)
    assert backup.latest(payload) == first
    assert (install / 'Private/.env').read_text().startswith('EIMS_ADMIN_PASSWORD=')


def test_corrupt_new_checkpoint_falls_back_to_previous_complete_copy(tmp_path, monkeypatch):
    payload, install = setup(tmp_path, monkeypatch)
    first = backup.checkpoint(install, payload)
    second = backup.checkpoint(install, payload)
    (second / 'database.dump').write_bytes(b'corrupt')
    assert backup.latest(payload) == first


def test_existing_local_credentials_are_never_overwritten(tmp_path, monkeypatch):
    payload, install = setup(tmp_path, monkeypatch)
    backup.checkpoint(install, payload)
    private = install / 'Private'
    prior = (private / '.env').read_bytes()
    assert not backup.stage_restore(payload, private)
    assert (private / '.env').read_bytes() == prior


def test_newer_usb_checkpoint_preserves_stale_local_session(tmp_path, monkeypatch):
    payload, install = setup(tmp_path, monkeypatch)
    cache = tmp_path / 'Cache'
    session = backup.select_install(payload, cache)
    session.mkdir()
    sentinel = session / 'local-work.txt'
    sentinel.write_text('preserve')
    assert backup.select_install(payload, cache) == session
    backup.checkpoint(install, payload)
    assert backup.select_install(payload, cache) != session
    assert sentinel.read_text() == 'preserve'


def test_disconnected_usb_never_erases_local_data(tmp_path, monkeypatch):
    payload, install = setup(tmp_path, monkeypatch)
    (payload / 'Tools/package.json').rename(payload / 'Tools/disconnected.json')
    with pytest.raises(FileNotFoundError):
        backup.checkpoint(install, payload)
    assert (install / 'Private/.env').exists()


def test_restore_resumes_objects_without_reimporting_completed_database(tmp_path, monkeypatch):
    payload, install = setup(tmp_path, monkeypatch)
    backup.checkpoint(install, payload)
    restored = tmp_path / 'AnotherPC'
    private = restored / 'Private'
    private.mkdir(parents=True)
    (restored / 'installation.json').write_text(json.dumps({'project': 'eims-restored-synthetic'}))
    assert backup.stage_restore(payload, private)
    assert (private / '.env').read_bytes() == (install / 'Private/.env').read_bytes()
    calls = []
    def db_restore(*args, **kwargs):
        calls.append(args[0])
    monkeypatch.setattr(backup.subprocess, 'run', db_restore)
    def interrupted(*args):
        raise OSError('synthetic interrupted object restore')
    monkeypatch.setattr(backup, '_restore_objects', interrupted)
    with pytest.raises(OSError):
        backup.restore(restored, payload)
    assert (private / 'database-restored.json').exists()
    assert not (private / 'restore-complete.json').exists()
    monkeypatch.setattr(backup, '_restore_objects', lambda *args: None)
    assert backup.restore(restored, payload)
    assert len(calls) == 1
    assert (private / 'restore-complete.json').exists()
