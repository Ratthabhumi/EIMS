"""Finalize an already staged, private prepared package. No downloads or USB writes.

Copy the verified prepared release to a NEW local staging directory first, then
place the official installers at the catalog paths below. Run with that path and
--baseline pointing to the original prepared release. Does not build runtimes,
install software, touch EIMS_Data, or modify the baseline.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

import build
from container_images import archive_identities

CATALOG = {
    'Docker': dict(path='Installers/Docker/Docker Desktop Installer.exe', version='4.85.0.235549',
        size=625139632, sha256='5417cedc1aeb16b488b8084025246b64a5e9da4d71388f324b107140dfe00699',
        publisherPattern=r'(?:CN|O)=Docker Inc\b',
        url='https://desktop.docker.com/win/main/amd64/235549/Docker%20Desktop%20Installer.exe',
        checksumSource='https://desktop.docker.com/win/main/amd64/235549/checksums.txt'),
    'WSL': dict(path='Installers/WSL/wsl.2.7.11.0.x64.msi', version='2.7.11.0',
        size=258990080, sha256='a611ddacee689d2fb1fb5319e58af7f3998864d86cdce632eadd8e61614a0f9d',
        publisherPattern=r'(?:CN|O)=Microsoft Corporation\b',
        url='https://github.com/microsoft/WSL/releases/download/2.7.11/wsl.2.7.11.0.x64.msi',
        checksumSource='https://api.github.com/repos/microsoft/WSL/releases/tags/2.7.11'),
}
SOURCE_PATHS = [
    'tools/handover/Runtime.ps1', 'tools/handover/Prerequisites.ps1',
    'tools/handover/build.py', 'tools/handover/prepare_offline_prerequisites.py',
    'tools/tests/test_offline_prerequisites.py',
    'tools/handover/container_images.py', 'tools/handover/prepare_portable_setup.py',
    'tools/tests/test_container_images.py',
]


def sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def verify_baseline(root: Path) -> dict:
    manifest = json.loads((root / 'MANIFEST.txt').read_text())
    expected = {r['path'] for r in manifest['files']} | {'MANIFEST.txt', 'SHA256SUMS.txt'}
    assert expected == {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    for row in manifest['files']:
        path = (root / row['path']).resolve()
        assert path.is_relative_to(root) and path.stat().st_size == row['size']
        assert sha(path) == row['sha256'], 'Baseline integrity failed: ' + row['path']
    return manifest


def forbidden(name: str) -> bool:
    if name in {'Sample_Logs/02_Task_long.log', 'EIMS_supervision_synthetic_demo_files_2026-10-09/02_Task_long.log'}:
        return False
    path = Path(name)
    return (path.name == '.env' or path.suffix.lower() in {'.dump','.log','.sqlite','.db','.bak','.xlsx','.docx'}
        or any(p in path.parts for p in ('EIMS_Data','.local-private','.git')))


def finalize(root: Path, baseline: Path) -> None:
    assert root != baseline and not root.is_relative_to(baseline) and not baseline.is_relative_to(root)
    original = verify_baseline(baseline)
    # Only these existing files may change. Everything else must stay byte-identical.
    mutable = {'Tools/Runtime.ps1','Source_Code/EIMS_Source.zip','Tools/source-ledger.json',
        'Tools/package.json','START_HERE.txt','Tools/security-review.json','Tools/release-gate.json',
        'Tools/container-images.json'}
    for row in original['files']:
        if row['path'] not in mutable:
            assert sha(root / row['path']) == row['sha256'], 'Unexpected payload change: ' + row['path']
    (root / 'Installers/installers.json').parent.mkdir(exist_ok=True)
    write_json(root / 'Installers/installers.json', CATALOG)
    # PowerShell's Authenticode implementation verifies the actual vendor binaries.
    quoted = str(root).replace("'", "''")
    source = str(build.TOOLS / 'Prerequisites.ps1').replace("'", "''")
    integrity = str(build.TOOLS / 'Integrity.ps1').replace("'", "''")
    subprocess.run(['powershell.exe','-NoProfile','-Command',
        f"$ErrorActionPreference='Stop'; . '{integrity}'; . '{source}'; [void](Assert-EimsInstaller '{quoted}' 'Docker'); [void](Assert-EimsInstaller '{quoted}' 'WSL')"], check=True)
    (root / 'Installers/INTERNAL_USE.txt').write_text(
        'Internal company handover only. Not a public redistribution package.\n'
        'Company IT must confirm Docker Desktop subscription eligibility, installer transfer\n'
        'permissions and authorized Windows component changes BEFORE running SETUP.\n'
        'No license is accepted automatically. Genuine vendor terms/UAC remain.\n'
        'https://docs.docker.com/subscription-billing/desktop-license/\n'
        'https://www.docker.com/legal/docker-subscription-service-agreement/\n'
        'https://learn.microsoft.com/en-us/windows/wsl/install#offline-install\n'
        'No clean-PC installation or legal compliance certification is claimed.\n', encoding='utf-8')
    for name in ('Runtime.ps1','Prerequisites.ps1','container_images.py'):
        (root / 'Tools' / name).write_bytes((build.TOOLS / name).read_bytes())
    records = json.loads((root / 'Tools/container-images.json').read_text())
    write_json(root / 'Tools/container-images.json', archive_identities(root / 'Tools/Container_Images.tar', records))
    package = json.loads((root / 'Tools/package.json').read_text())
    old_package = json.loads((baseline / 'Tools/package.json').read_text())
    for key in ('id','mediaId','storageMode','preparedRuntime','backupIntervalSeconds'):
        assert package[key] == old_package[key]
    package['setup'] = 'PREPARED_WITH_OFFLINE_PREREQUISITES'
    write_json(root / 'Tools/package.json', package)
    start = (baseline / 'START_HERE.txt').read_text()
    (root / 'START_HERE.txt').write_text(
        start if start.startswith('OFFLINE FIRST-RUN SETUP\n') else 'OFFLINE FIRST-RUN SETUP\n'
        'After company IT approval, double-click SETUP.bat. Existing working Docker is reused.\n'
        'If missing, official Docker/WSL installers are bundled in Installers; no download\n'
        'or typed INSTALL/YES is needed. Follow genuine vendor license and UAC dialogs.\n'
        'Windows feature activation may need an approved restart: rerun SETUP afterwards.\n'
        'BIOS virtualization and corporate policy blocks require IT. No forced reboot.\n'
        'Read Installers/INTERNAL_USE.txt before first use. Docker runs on the PC, not USB.\n'
        'The earlier guide below remains applicable to prepared runtime and recovery.\n\n' + start,
        encoding='utf-8')
    archive = root / 'Source_Code/EIMS_Source.zip'
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        members = {n: z.read(n) for n in z.namelist()}
    for rel in SOURCE_PATHS:
        members[rel] = (build.ROOT / rel).read_bytes()
    for name in members:
        assert not forbidden(name) and not Path(name).is_absolute() and '..' not in Path(name).parts
    for default in build.known_defaults():
        assert not any(default.encode() in data for data in members.values()), 'Historical default found'
    temp = archive.with_suffix('.tmp')
    with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(members.items()):
            z.writestr(name, data)
    temp.replace(archive)
    ledger_path = root / 'Tools/source-ledger.json'
    ledger = json.loads(ledger_path.read_text())
    for rel in SOURCE_PATHS:
        row = next((r for r in ledger['files'] if r['path'] == rel), None)
        if row is None:
            row = {'path':rel,'transforms':[]}
            ledger['files'].append(row)
        row.update(sha256=sha(build.ROOT / rel), deliveredSha256=hashlib.sha256(members[rel]).hexdigest())
    write_json(ledger_path, ledger)
    assert not any(forbidden(p.relative_to(root).as_posix()) for p in root.rglob('*') if p.is_file())
    # Prepared runtime/container images and all application source remain unchanged.
    with zipfile.ZipFile(root / 'Tools/Prepared_Runtime.zip') as z:
        assert z.testzip() is None and not any(forbidden(n) for n in z.namelist())
    excluded = {'MANIFEST.txt','SHA256SUMS.txt','Tools/security-review.json','Tools/release-gate.json'}
    review = dict(status='PASS', reviewedBy='Codex exact artifact review',
        reviewedAt=datetime.now(timezone.utc).isoformat(),
        scope='Baseline byte preservation, archive screening, official installer digests and Authenticode. '
              'No clean-PC, transitive vulnerability or company license certification.',
        files=[dict(path=p.relative_to(root).as_posix(),sha256=sha(p)) for p in sorted(root.rglob('*'))
               if p.is_file() and p.relative_to(root).as_posix() not in excluded])
    write_json(root / 'Tools/security-review.json', review)
    gate_path = root / 'Tools/release-gate.json'
    gate = json.loads(gate_path.read_text())
    assert gate['ownerAuthorizationSha256'] == sha(root / 'OWNER_HANDOVER_AUTHORIZATION.txt')
    gate.update(securityReview='PASS', acceptance='Internal-only staging; company Docker entitlement/transfer '
        'and IT approval required before setup. Fresh physical PC installation NOT RUN.')
    write_json(gate_path, gate)
    build.PAYLOAD = root
    build.refresh_manifest()
    print(json.dumps(dict(files=sum(p.is_file() for p in root.rglob('*')),
        bytes=sum(p.stat().st_size for p in root.rglob('*') if p.is_file()),manifest=sha(root / 'MANIFEST.txt'))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('staging', type=Path)
    parser.add_argument('--baseline', type=Path, required=True)
    args = parser.parse_args()
    finalize(args.staging.resolve(), args.baseline.resolve())
