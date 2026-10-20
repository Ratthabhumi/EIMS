"""Finalize an isolated Windows build; never copy data, install services or write USB.

Inputs: verified existing Full EIMS payload, prepared Python/Node dependencies,
Next.js standalone output from its sanitized Source ZIP, and docker-save images.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid
import zipfile

import build as full
from container_images import archive_identities


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def prepare(stage):
    stage = Path(stage).resolve()
    target = stage / 'Final_EIMS_Project'
    prepared = stage / 'Prepared'
    dashboard = stage / 'Build_App/clients/dashboard'
    outputs = list((dashboard / '.next/standalone').rglob('server.js'))
    outputs = [p for p in outputs if (p.parent / '.next/BUILD_ID').is_file()]
    if len(outputs) != 1:
        raise ValueError('Exactly one built standalone server is required')
    if (prepared / 'Frontend').exists() or (target / 'Tools/Prepared_Runtime.zip').exists():
        raise ValueError('Preserve the existing prepared build; no overwrite')
    # Dereference any Windows build-time junctions into ordinary portable files.
    shutil.copytree(outputs[0].parent, prepared / 'Frontend', symlinks=False,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(dashboard / '.next/static', prepared / 'Frontend/.next/static')
    if (dashboard / 'public').exists():
        shutil.copytree(dashboard / 'public', prepared / 'Frontend/public')
    for path in (dashboard / 'node_modules').rglob('*'):
        if path.is_file() and path.name.lower().startswith(('license', 'notice', 'copying', 'copyright')):
            dest = prepared / 'ThirdPartyNotices/npm' / path.relative_to(dashboard / 'node_modules')
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
    rows = []
    for p in sorted(prepared.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.suffix == '.pyc':
            continue
        if p.is_symlink() or p.is_junction():
            raise ValueError('Runtime must contain ordinary files, not build links')
        if p.name == '.env' or p.suffix.lower() in {'.dump', '.log', '.sqlite', '.db'}:
            raise ValueError('Private or generated runtime input: ' + p.name)
        rows.append({'path': p.relative_to(prepared).as_posix(), 'size': p.stat().st_size, 'sha256': sha(p)})
    (prepared / 'runtime-manifest.json').write_text(json.dumps({'format': 'eims-prepared-v1',
        'platform': 'Windows x64', 'python': '3.14.6', 'node': '24.18.0', 'files': rows}, indent=2), encoding='utf-8')
    with zipfile.ZipFile(target / 'Tools/Prepared_Runtime.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for row in rows:
            archive.write(prepared / row['path'], row['path'])
        archive.write(prepared / 'runtime-manifest.json', 'runtime-manifest.json')
    bootstrap = target / 'Tools/BootstrapPython'
    shutil.copytree(prepared / 'Python', bootstrap,
        ignore=shutil.ignore_patterns('site-packages', '__pycache__', '*.pyc'))
    for name in ('Runtime.ps1', 'Prerequisites.ps1', 'container_images.py', 'prepared_runtime.py', 'usb_backup.py', 'command_runner.py'):
        shutil.copyfile(full.TOOLS / name, target / 'Tools' / name)
    images = json.loads((stage / 'container-images.json').read_text())
    images = archive_identities(target / 'Tools/Container_Images.tar', images)
    (target / 'Tools/container-images.json').write_text(json.dumps(images, indent=2), encoding='utf-8')
    compose = (target / 'Tools/compose.yaml').read_text('utf-8')
    for image in images:
        compose = compose.replace('image: ' + image['upstream'], 'image: ' + image['tag'] + '\n    pull_policy: never')
    compose = compose.replace('pg_isready -U eims_user', 'pg_isready -h 127.0.0.1 -U eims_user')
    (target / 'Tools/compose.yaml').write_text(compose, encoding='utf-8')
    package_path = target / 'Tools/package.json'
    package = json.loads(package_path.read_text('utf-8-sig'))
    package.update(storageMode='USB_CHECKPOINT', mode='PREPARED_FULL_EIMS_CORE',
                   setup='PREPARED_OFFLINE_AFTER_DOCKER_PREREQUISITES', mediaId=uuid.uuid4().hex,
                   preparedRuntime='Tools/Prepared_Runtime.zip', backupIntervalSeconds=120)
    package_path.write_text(json.dumps(package, indent=2), encoding='utf-8')
    (target / 'USB_Backup_Status.bat').write_text('@echo off\n"%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -File "%~dp0Tools\\Runtime.ps1" -Action BackupStatus\npause\n', encoding='ascii')
    (target / 'START_HERE.txt').write_text('''EIMS - PREPARED USB HANDOVER
1. First use on each PC: SETUP.bat. Windows 11 x64 and approved Docker Desktop
   (Linux containers / WSL support) are required. Python and Node are bundled.
2. Later use: Start.bat. The app opens at http://127.0.0.1:13101/analyzer.
3. Live database and credentials use a protected working cache on this PC.
   Verified recovery copies, credentials and uploaded objects are saved under
   EIMS_Data beside this package, immediately after start and every 2 minutes.
4. USB_Backup_Status.bat shows whether the latest backup completed.
   If USB is unplugged, local work continues and the previous completed USB copy
   remains available. Unsaved changes remain on this PC, not on the USB.
5. Stop.bat saves a final checkpoint and stops this EIMS instance. Recommended
   before changing PCs; sudden unplugging does not remove the local database.
6. On another PC, SETUP restores the latest verified USB checkpoint into a new
   local working session. Earlier local sessions are preserved, never overwritten.
No npm install, frontend build or pip download runs on the prepared setup path.
Docker/WSL installation and licensing are machine requirements, not portable files.
Keep EIMS_Data private: it includes actual credentials, database and user records.
Never publish EIMS_Data to GitHub. NTFS and checksums are not encryption.
Redis cache is regenerated. DB dumps are transactional; live MinIO copying does
not assert a cross-service point-in-time snapshot. Final Stop quiesces the app.
''', encoding='utf-8')
    (target / 'PREPARED_SETUP_UPDATE.txt').write_text('This update supersedes old online-setup/dependency/local-only-data instructions.\n'
        'Runtime/dependencies, frontend and infrastructure images are bundled.\n'
        'Working data stays local; verified recovery snapshots travel on USB.\n'
        'Other guides describe the historical baseline; use START_HERE.txt first.\n', encoding='utf-8')
    source = target / 'Source_Code/EIMS_Source.zip'
    with zipfile.ZipFile(source) as archive:
        members = {n: archive.read(n) for n in archive.namelist()}
    updated = ['tools/handover/' + n for n in ('Runtime.ps1', 'prepared_runtime.py', 'usb_backup.py', 'command_runner.py', 'prepare_portable_setup.py')]
    updated += ['tools/tests/test_usb_backup.py', 'tools/tests/test_prepared_runtime.py', 'tools/tests/test_handover_process_identity.py']
    for rel in updated:
        members[rel] = (full.ROOT / rel).read_bytes()
    members['clients/dashboard/next.config.ts'] = (dashboard / 'next.config.ts').read_bytes()
    with zipfile.ZipFile(source, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(members.items()):
            archive.writestr(name, data)
    ledger_path = target / 'Tools/source-ledger.json'
    ledger = json.loads(ledger_path.read_text('utf-8'))
    for rel in updated + ['clients/dashboard/next.config.ts']:
        row = next((r for r in ledger['files'] if r['path'] == rel), None)
        if row is None:
            row = {'path': rel}
            ledger['files'].append(row)
        row.update(sha256=sha(full.ROOT / rel), deliveredSha256=hashlib.sha256(members[rel]).hexdigest(),
                   transforms=['delivery-only standalone build'] if rel.endswith('next.config.ts') else [])
    ledger['patch_scope'] = 'Prepared Windows runtimes, standalone frontend, pinned infrastructure image transfer and local working data with USB checkpoints.'
    ledger_path.write_text(json.dumps(ledger, indent=2), encoding='utf-8')
    (target / 'VERSION.txt').write_text('EIMS Prepared USB handover | ' + datetime.now(timezone.utc).isoformat() +
        '\nSource: ' + full.git('rev-parse', 'HEAD') + '\nModified source and delivery transforms: Tools/source-ledger.json\n'
        'Target: Windows 11 x64; clean second PC validation remains required.\n', encoding='utf-8')
    # Publication/copy remains blocked until an exact artifact review refreshes the gate.
    gate = json.loads((target / 'Tools/release-gate.json').read_text('utf-8'))
    gate['securityReview'] = 'PENDING'
    (target / 'Tools/release-gate.json').write_text(json.dumps(gate, indent=2), encoding='utf-8')
    full.PAYLOAD = target
    full.refresh_manifest()
    print(json.dumps({'candidate': str(target), 'files': len(rows), 'preparedZipSHA256': sha(target / 'Tools/Prepared_Runtime.zip')}))


if __name__ == '__main__':
    prepare(sys.argv[1])
