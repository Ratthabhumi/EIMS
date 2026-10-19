"""Local working databases with verified, append-only USB recovery checkpoints.

Never copy live PostgreSQL data files. Credentials and real objects belong only
in the private USB checkpoint area, never in the distributable package.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import time
import uuid


def atomic_json(path, value):
    path = Path(path)
    pending = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    pending.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(pending, path)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def usb_root(payload):
    payload = Path(payload)
    package = json.loads((payload / 'Tools/package.json').read_text('utf-8-sig'))
    if package.get('storageMode') != 'USB_CHECKPOINT' or not package.get('mediaId'):
        raise ValueError('Not a checkpoint-enabled USB package')
    if not re.fullmatch(r'eims-[a-f0-9]{16}', package.get('id', '')) or not re.fullmatch(r'[a-f0-9]{32}', package['mediaId']):
        raise ValueError('Invalid portable identity')
    return payload.parent / 'EIMS_Data' / package['id'] / package['mediaId']


def verified_checkpoint(path):
    path = Path(path)
    manifest = json.loads((path / 'checkpoint.json').read_text('utf-8'))
    if manifest.get('format') != 'eims-checkpoint-v1' or manifest.get('status') != 'COMPLETE':
        raise ValueError('Incomplete checkpoint')
    if manifest.get('id') != path.name.removeprefix('.pending-'):
        raise ValueError('Checkpoint identity mismatch')
    required = {'database.dump', 'private.env', 'LOCAL_ADMIN.txt', 'objects.json'}
    seen = set()
    for row in manifest['files']:
        name = row['path']
        target = path / name
        if name in seen or ':' in name or '\\' in name or name.startswith('/') or '..' in Path(name).parts:
            raise ValueError('Unsafe checkpoint path')
        seen.add(name)
        if not target.resolve().is_relative_to(path.resolve()) or target.is_symlink() or target.is_junction():
            raise ValueError('Linked checkpoint path')
        if target.stat().st_size != row['size'] or digest(target) != row['sha256']:
            raise ValueError('Checkpoint integrity mismatch')
    if not required <= seen:
        raise ValueError('Missing recovery files')
    return manifest


def latest(payload):
    snapshots = usb_root(payload) / 'Snapshots'
    if not snapshots.exists():
        return None
    # Incomplete writes never hide a previously verified recovery point.
    for path in sorted(snapshots.iterdir(), reverse=True):
        if path.name.startswith('.') or not path.is_dir():
            continue
        try:
            verified_checkpoint(path)
            return path
        except (OSError, ValueError, KeyError):
            continue
    if any(p.is_dir() and not p.name.startswith('.') for p in snapshots.iterdir()):
        raise ValueError('No valid USB recovery point; local data will not be replaced')
    return None


def select_install(payload, cache):
    """Reuse the current synchronized cache, preserve stale caches as separate sessions."""
    cache = Path(cache)
    checkpoint = latest(payload)
    checkpoint_id = checkpoint.name if checkpoint else None
    pointer = cache / 'current-session.json'
    if pointer.exists():
        record = json.loads(pointer.read_text('utf-8'))
        if not re.fullmatch(r'[a-f0-9]{32}', record.get('session', '')):
            raise ValueError('Invalid cache session')
        session = cache / 'Sessions' / record['session']
        if session.parent != cache / 'Sessions':
            raise ValueError('Invalid cache session')
        ack = session / 'Private/last-usb-checkpoint.json'
        synced = json.loads(ack.read_text('utf-8'))['id'] if ack.exists() else record.get('checkpoint')
        if synced == checkpoint_id:
            return session
    session_id = uuid.uuid4().hex
    cache.mkdir(parents=True, exist_ok=True)
    (cache / 'Sessions').mkdir(exist_ok=True)
    atomic_json(pointer, {'session': session_id, 'checkpoint': checkpoint_id})
    return cache / 'Sessions' / session_id


def environment(private):
    values = {}
    for line in (Path(private) / '.env').read_text('utf-8-sig').splitlines():
        if '=' in line and not line.startswith('#'):
            name, value = line.split('=', 1)
            values[name] = value
    return values


def compose(install, payload):
    identity = json.loads((Path(install) / 'installation.json').read_text('utf-8-sig'))
    return ['docker', 'compose', '--project-name', identity['project'], '--env-file',
            str(Path(install) / 'Private/.env'), '-f', str(Path(payload) / 'Tools/compose.yaml')]


def object_client(private):
    import boto3
    from botocore.config import Config
    values = environment(private)
    return boto3.client('s3', endpoint_url='http://127.0.0.1:19000',
                        aws_access_key_id=values['EIMS_MINIO_ACCESS_KEY'],
                        aws_secret_access_key=values['EIMS_MINIO_SECRET_KEY'],
                        config=Config(connect_timeout=5, read_timeout=30, retries={'max_attempts': 1}))


def stage_restore(payload, private):
    checkpoint = latest(payload)
    if checkpoint is None:
        return False
    private = Path(private)
    if (private / '.env').exists():
        return False  # Existing local credentials are never automatically overwritten.
    manifest = verified_checkpoint(checkpoint)
    shutil.copyfile(checkpoint / 'private.env', private / '.env')
    shutil.copyfile(checkpoint / 'LOCAL_ADMIN.txt', private / 'LOCAL_ADMIN.txt')
    atomic_json(private / 'restore-pending.json', {'checkpoint': str(checkpoint), 'id': manifest['id']})
    print('Verified USB checkpoint selected. Existing local sessions remain preserved.', flush=True)
    return True


def restore(install, payload):
    private = Path(install) / 'Private'
    pending = private / 'restore-pending.json'
    if not pending.exists() or (private / 'restore-complete.json').exists():
        return False
    record = json.loads(pending.read_text('utf-8'))
    checkpoint = usb_root(payload) / 'Snapshots' / record['id']
    verified_checkpoint(checkpoint)
    if not (private / 'database-restored.json').exists():
        with (checkpoint / 'database.dump').open('rb') as source, (private / 'usb-restore.log').open('ab') as log:
            subprocess.run(compose(install, payload) + ['exec', '-T', 'postgres', 'pg_restore',
                '--single-transaction', '--exit-on-error', '--no-owner', '--no-acl', '-U', 'eims_user', '-d', 'eims_handover'],
                stdin=source, stdout=log, stderr=log, check=True, timeout=300)
        # The DB transaction is complete; on a retry, only object restoration is repeated.
        atomic_json(private / 'database-restored.json', record)
    _restore_objects(private, checkpoint)
    atomic_json(private / 'restore-complete.json', record)
    atomic_json(private / 'last-usb-checkpoint.json', {'id': checkpoint.name})
    print('USB database and object recovery completed.', flush=True)
    return True


def _restore_objects(private, checkpoint):
    client = object_client(private)
    existing = {b['Name'] for b in client.list_buckets()['Buckets']}
    for obj in json.loads((checkpoint / 'objects.json').read_text('utf-8')):
        if obj['bucket'] not in existing:
            client.create_bucket(Bucket=obj['bucket'])
            existing.add(obj['bucket'])
        with (checkpoint / obj['file']).open('rb') as stream:
            client.put_object(Bucket=obj['bucket'], Key=obj['key'], Body=stream,
                              ContentType=obj.get('contentType', 'application/octet-stream'),
                              Metadata=obj.get('metadata', {}))


def checkpoint(install, payload):
    private = Path(install) / 'Private'
    root = usb_root(payload)
    snapshots = root / 'Snapshots'
    snapshots.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < 256 * 1024 * 1024:
        raise OSError('USB needs at least 256 MiB free before a checkpoint')
    identity = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid.uuid4().hex[:8]
    staging = snapshots / ('.pending-' + identity)
    staging.mkdir()
    with (staging / 'database.dump').open('xb') as output, (private / 'usb-backup-detail.log').open('ab') as log:
        subprocess.run(compose(install, payload) + ['exec', '-T', 'postgres', 'pg_dump', '-Fc',
            '--no-owner', '--no-acl', '-U', 'eims_user', '-d', 'eims_handover'],
            stdout=output, stderr=log, check=True, timeout=180)
    with (staging / 'database.dump').open('rb') as stream:
        if stream.read(5) != b'PGDMP':
            raise ValueError('Incomplete PostgreSQL archive; previous checkpoint preserved')
    with (staging / 'database.dump').open('rb') as source, (private / 'usb-backup-detail.log').open('ab') as log:
        subprocess.run(compose(install, payload) + ['exec', '-T', 'postgres', 'pg_restore', '--list'],
                       stdin=source, stdout=log, stderr=log, check=True, timeout=60)
    shutil.copyfile(private / '.env', staging / 'private.env')
    shutil.copyfile(private / 'LOCAL_ADMIN.txt', staging / 'LOCAL_ADMIN.txt')
    objects = []
    client = object_client(private)
    for bucket in client.list_buckets()['Buckets']:
        for page in client.get_paginator('list_objects_v2').paginate(Bucket=bucket['Name']):
            for obj in page.get('Contents', []):
                name = 'objects/' + uuid.uuid4().hex
                target = staging / name
                target.parent.mkdir(exist_ok=True)
                if shutil.disk_usage(root).free < obj['Size'] + 64 * 1024 * 1024:
                    raise OSError('Insufficient USB space; prior checkpoint preserved')
                response = client.get_object(Bucket=bucket['Name'], Key=obj['Key'], IfMatch=obj['ETag'])
                with response['Body'] as source, target.open('xb') as output:
                    shutil.copyfileobj(source, output)
                if target.stat().st_size != obj['Size']:
                    raise OSError('Incomplete object copy')
                objects.append({'bucket': bucket['Name'], 'key': obj['Key'], 'file': name,
                                'contentType': response.get('ContentType'), 'metadata': response.get('Metadata', {})})
    (staging / 'objects.json').write_text(json.dumps(objects), encoding='utf-8')
    rows = [{'path': p.relative_to(staging).as_posix(), 'size': p.stat().st_size, 'sha256': digest(p)}
            for p in sorted(staging.rglob('*')) if p.is_file()]
    atomic_json(staging / 'checkpoint.json', {'format': 'eims-checkpoint-v1', 'status': 'COMPLETE',
        'id': identity, 'files': rows, 'scope': 'Transactional PostgreSQL dump and copied MinIO objects; Redis cache is reconstructed. Cross-service point-in-time consistency is not asserted.'})
    verified_checkpoint(staging)
    complete = snapshots / identity
    staging.rename(complete)
    atomic_json(private / 'last-usb-checkpoint.json', {'id': identity})
    saved_at = datetime.now(timezone.utc).isoformat()
    atomic_json(private / 'usb-backup-status.json', {'status': 'SAVED', 'checkpoint': identity,
        'time': saved_at, 'lastSaved': saved_at})
    print('USB recovery checkpoint saved and verified.', flush=True)
    return complete


def watch(install, payload):
    private = Path(install) / 'Private'
    while not (private / 'usb-backup.stop').exists():
        try:
            checkpoint(install, payload)
        except Exception as exc:
            # Do not log exception text that might contain URLs, credentials or object names.
            status_path = private / 'usb-backup-status.json'
            previous = json.loads(status_path.read_text('utf-8')) if status_path.exists() else {}
            atomic_json(private / 'usb-backup-status.json', {'status': 'NOT_SAVED',
                'reason': type(exc).__name__, 'time': datetime.now(timezone.utc).isoformat(),
                'lastSaved': previous.get('lastSaved')})
            print('USB checkpoint unavailable; local data retained. Previous completed USB checkpoint preserved.', flush=True)
        for _ in range(120):
            if (private / 'usb-backup.stop').exists():
                return
            time.sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['select', 'stage-restore', 'restore', 'checkpoint', 'watch'])
    parser.add_argument('first')
    parser.add_argument('second')
    args = parser.parse_args()
    if args.action == 'select':
        print(select_install(args.first, args.second))
    elif args.action == 'stage-restore':
        stage_restore(args.first, args.second)
    else:
        globals()[args.action](args.first, args.second)
