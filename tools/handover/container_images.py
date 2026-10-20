"""Offline, content-addressed Docker archive and local-image verification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile


def archive_identities(archive: Path, records: list[dict]) -> list[dict]:
    """Bind each transfer tag to its index, amd64 manifest, config and layers.

    No extraction, registry access, image loading or Docker mutation occurs here.
    Other platforms omitted by docker save need not be present; every archived
    content-addressed blob and every selected-platform dependency must validate.
    """
    with tarfile.open(archive) as tar:
        entries = tar.getmembers()
        names = [e.name for e in entries]
        if len(names) != len(set(names)) or any(e.issym() or e.islnk() for e in entries):
            raise ValueError('Duplicate or linked archive entries')
        for entry in entries:
            if entry.isfile() and entry.name.startswith('blobs/'):
                if not re.fullmatch(r'blobs/sha256/[a-f0-9]{64}', entry.name):
                    raise ValueError('Unsupported archive blob address')
                with tar.extractfile(entry) as stream:
                    actual = hashlib.file_digest(stream, 'sha256').hexdigest()
                if actual != entry.name.rsplit('/', 1)[1]:
                    raise ValueError('Archive blob digest mismatch')

        def read(name):
            member = tar.getmember(name)
            if not member.isfile() or member.size > 8 * 1024 * 1024:
                raise ValueError('Invalid archive metadata')
            return json.load(tar.extractfile(member))

        def blob(descriptor):
            digest = descriptor['digest']
            if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
                raise ValueError('Invalid descriptor digest')
            name = 'blobs/sha256/' + digest.split(':')[1]
            if tar.getmember(name).size != descriptor['size']:
                raise ValueError('Descriptor size mismatch')
            return read(name)

        index = read('index.json')
        legacy = read('manifest.json')
        result = []
        for record in records:
            tag = record['tag']
            roots = [d for d in index['manifests'] if
                d.get('annotations', {}).get('io.containerd.image.name') in {tag, 'docker.io/' + tag}]
            if len(roots) != 1 or roots[0]['digest'] != record['imageId']:
                raise ValueError('Archive tag/index mismatch: ' + tag)
            root = blob(roots[0])
            manifests = [m for m in root.get('manifests', []) if
                m.get('platform', {}).get('os') == 'linux' and
                m.get('platform', {}).get('architecture') == 'amd64']
            if len(manifests) != 1:
                raise ValueError('Exactly one linux/amd64 manifest required: ' + tag)
            manifest = blob(manifests[0])
            config = blob(manifest['config'])
            if config.get('os') != 'linux' or config.get('architecture') != 'amd64':
                raise ValueError('Archive config platform mismatch: ' + tag)
            rows = [r for r in legacy if tag in (r.get('RepoTags') or [])]
            expected_config = 'blobs/sha256/' + manifest['config']['digest'].split(':')[1]
            layers = ['blobs/sha256/' + d['digest'].split(':')[1] for d in manifest['layers']]
            if len(rows) != 1 or rows[0]['Config'] != expected_config or rows[0]['Layers'] != layers:
                raise ValueError('Docker/OCI archive mapping mismatch: ' + tag)
            for name, descriptor in zip(layers, manifest['layers']):
                if not tar.getmember(name).isfile() or tar.getmember(name).size != descriptor['size']:
                    raise ValueError('Missing/invalid platform layer: ' + tag)
            diff_ids = config['rootfs']['diff_ids']
            if config['rootfs']['type'] != 'layers' or len(diff_ids) != len(layers) or not all(
                re.fullmatch(r'sha256:[a-f0-9]{64}', value) for value in diff_ids):
                raise ValueError('Invalid root filesystem identity: ' + tag)
            identity = dict(indexDigest=record['imageId'], manifestDigest=manifests[0]['digest'],
                configDigest=manifest['config']['digest'], os='linux', architecture='amd64', diffIds=diff_ids)
            if 'verification' in record and record['verification'] != identity:
                raise ValueError('Catalog verification metadata differs from archive: ' + tag)
            result.append({**record, 'verification': identity})
        return result


def verify_inspection(record: dict, actual: dict) -> str:
    expected = record['verification']
    roles = {'index': expected['indexDigest'], 'manifest': expected['manifestDigest'], 'config': expected['configDigest']}
    role = next((name for name, value in roles.items() if value == actual.get('Id')), None)
    if role is None:
        raise ValueError('ID is not a verified index, platform manifest or config digest')
    if actual.get('Os') != expected['os'] or actual.get('Architecture') != expected['architecture']:
        raise ValueError('Local image platform mismatch')
    root = actual.get('RootFS', {})
    if root.get('Type') != 'layers' or root.get('Layers') != expected['diffIds']:
        raise ValueError('Local image filesystem layers mismatch')
    return role


def verify_local(payload: Path) -> int:
    records = json.loads((payload / 'Tools/container-images.json').read_text('utf-8-sig'))
    records = archive_identities(payload / 'Tools/Container_Images.tar', records)
    failed = False
    for record in records:
        inspected = subprocess.run(['docker.exe', 'image', 'inspect', record['tag']],
            capture_output=True, text=True, timeout=20)
        actual = {}
        try:
            if inspected.returncode:
                raise ValueError('Local tag absent or Docker inspection failed')
            rows = json.loads(inspected.stdout)
            if len(rows) != 1:
                raise ValueError('Ambiguous Docker inspection')
            actual = rows[0]
            role = verify_inspection(record, actual)
            print(f"VERIFIED {record['tag']} | {role}={actual['Id']} | linux/amd64 layers match")
        except (ValueError, KeyError, TypeError) as error:
            failed = True
            print(f"MISMATCH {record['tag']} | expected index={record['imageId']} "
                  f"config={record['verification']['configDigest']} | actual={actual.get('Id', 'unavailable')} | {error}")
    return 2 if failed else 0


if __name__ == '__main__':
    try:
        raise SystemExit(verify_local(Path(sys.argv[1])))
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError, subprocess.TimeoutExpired) as error:
        print('Image verification BLOCKED: ' + str(error))
        raise SystemExit(3)
