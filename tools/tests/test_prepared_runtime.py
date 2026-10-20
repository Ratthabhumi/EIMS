import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

spec = importlib.util.spec_from_file_location('prepared_runtime', Path(__file__).parents[1] / 'handover/prepared_runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def bundle(path):
    files = {name: b'synthetic' for name in ('Python/python.exe', 'Node/node.exe', 'Frontend/server.js', 'Frontend/.next/BUILD_ID')}
    rows = [{'path': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name, data in files.items()]
    with zipfile.ZipFile(path, 'w') as z:
        for name, data in files.items():
            z.writestr(name, data)
        z.writestr('runtime-manifest.json', json.dumps({'files': rows}))


def test_install_and_reverify_without_installers_or_data_changes(tmp_path):
    source = tmp_path / 'runtime.zip'
    bundle(source)
    private = tmp_path / 'Private'
    private.mkdir()
    sentinel = private / 'existing-data.txt'
    sentinel.write_text('preserve synthetic history')
    runtime.install(source, tmp_path / 'Runtime')
    runtime.verify(tmp_path / 'Runtime')
    assert sentinel.read_text() == 'preserve synthetic history'
    with pytest.raises(FileExistsError):
        runtime.install(source, tmp_path / 'Runtime')


def test_tamper_is_rejected(tmp_path):
    source = tmp_path / 'runtime.zip'
    bundle(source)
    target = tmp_path / 'Runtime'
    runtime.install(source, target)
    (target / 'Node/node.exe').write_bytes(b'changed')
    with pytest.raises(ValueError, match='integrity'):
        runtime.verify(target)


def test_injected_module_is_rejected(tmp_path):
    source = tmp_path / 'runtime.zip'
    bundle(source)
    target = tmp_path / 'Runtime'
    runtime.install(source, target)
    (target / 'Python/unreviewed.py').write_text('# synthetic unexpected module')
    with pytest.raises(ValueError, match='Unexpected'):
        runtime.verify(target)


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'C:/escape', 'folder\\escape'])
def test_zip_escape_is_rejected_without_external_writes(tmp_path, name):
    with pytest.raises(ValueError):
        runtime.safe_path(tmp_path, name)
    if chr(92) in name:
        return  # ZipInfo normalizes Windows separators when writing archives.
    source = tmp_path / 'runtime.zip'
    with zipfile.ZipFile(source, 'w') as z:
        z.writestr(name, b'synthetic')
    with pytest.raises(ValueError):
        runtime.install(source, tmp_path / 'Runtime')
    assert not (tmp_path / 'escape').exists()
