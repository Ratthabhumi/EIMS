"""Reuse reviewed Full EIMS and maintained Auditor; never write to USB or Git."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import socket
import sys
import zipfile

import build as full

ROOT = full.ROOT
AREA = ROOT / 'Final_CO-OP/Two_USB'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    baseline = ROOT / 'Final_CO-OP/Payload/Full_EIMS'
    target = AREA / 'Final_EIMS_Project'
    baseline_rows = json.loads((baseline / 'MANIFEST.txt').read_text())['files']
    if target.exists():
        mutable = {'Source_Code/EIMS_Source.zip', 'Tools/source-ledger.json', 'Tools/Integrity.ps1',
                   'MANIFEST.txt', 'SHA256SUMS.txt', 'PACKAGE_TYPE', 'TWO_USB_README.txt'}
        expected = {r['path'] for r in baseline_rows} | mutable
        actual = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
        if ('--resume-incomplete' not in sys.argv or (AREA / 'release-review.json').exists()
                or not actual <= expected):
            raise RuntimeError('Existing package must be preserved/reviewed before rebuild.')
        for row in baseline_rows:
            if row['path'] not in mutable and sha(target / row['path']) != row['sha256']:
                raise RuntimeError('Incomplete package changed; preserve and inspect.')
    for entry in baseline_rows:
        if sha(baseline / entry['path']) != entry['sha256']:
            raise RuntimeError('Full baseline changed; inspect before copying.')
    if not target.exists():
        shutil.copytree(baseline, target)
    defaults = full.known_defaults()
    tracked = full.git('ls-files').splitlines()
    extras = [p.relative_to(ROOT).as_posix() for p in (ROOT / 'tools/handover').rglob('*')
              if p.is_file() and '__pycache__' not in p.parts]
    extras += ['Clone_USB_Auditor.bat', 'Clone_EIMS_Handover.bat', 'Flashdrive_Clone.bat', 'tools/Run-Private-Audit.ps1',
               'tools/Run-EIMS-Audit.bat', 'tools/build_usb_package.py', 'tools/tests/test_build_usb_package.py',
               'tools/Build-EIMS-USB.bat', 'tools/Build-EIMS-USB.ps1',
               'backend/domain/analyzer/services/provider_knowledge.py', 'tests/test_windows_provider_collision.py',
               'clients/usb_auditor/scanner/firewall_evidence.py',
               'clients/usb_auditor/tests/test_private_evidence.py',
               'clients/usb_auditor/tests/test_firewall_evidence.py']
    paths = sorted({p for p in tracked + extras if full.allowed(p) or p in extras})
    rows, members = [], {}
    for rel in paths:
        p = ROOT / rel
        if p.is_symlink() or not p.is_file():
            raise RuntimeError('Missing/link source: ' + rel)
        original = p.read_bytes()
        delivered, changes = full.transform(rel, original, defaults)
        if any(v.encode() in delivered for v in defaults):
            raise RuntimeError('Historical default remains: ' + rel)
        members[rel] = delivered
        rows.append({'path': rel, 'sha256': sha(p), 'deliveredSha256': full.digest(delivered), 'transforms': changes})
    members['clients/dashboard/src/components/HandoverAuthGate.tsx'] = (full.TOOLS / 'HandoverAuthGate.tsx').read_bytes()
    package = json.loads((target / 'Tools/package.json').read_text())
    package['id'] = 'eims-' + full.digest(json.dumps(rows, sort_keys=True).encode())[:16]
    full.write(target / 'Tools/package.json', json.dumps(package, indent=2))
    with zipfile.ZipFile(target / 'Source_Code/EIMS_Source.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for rel, data in sorted(members.items()):
            z.writestr(rel, data)
    full.write(target / 'Tools/source-ledger.json', json.dumps({
        'revision': full.git('rev-parse', 'HEAD'), 'branch': full.git('branch', '--show-current'),
        'trackedPathsHash': full.digest('\n'.join(tracked).encode()), 'files': rows}, indent=2))
    shutil.copy2(full.TOOLS / 'Integrity.ps1', target / 'Tools/Integrity.ps1')
    full.write(target / 'PACKAGE_TYPE', 'EIMS_HANDOVER\n')
    full.write(target / 'TWO_USB_README.txt', '''USB 2: FULL EIMS, existing dashboard and API.
SETUP.bat -> Start.bat -> Stop.bat. First setup needs online dependencies and approved Docker.
USB 1 is a separate read-only collector. Import its JSON using Inventory's existing import.
Reports without event_logs contain inventory only, not analyzed Windows events.
Collector event channels are System/Application; Security file-access auditing is not collected.
Event 41 does not establish a power outage; rule/listener observations do not establish intrusion.
No production credentials, company reports or database dumps are shipped.
No current human usability or clean Windows Server test is claimed.
See Developer_Docs/ACCEPTANCE.md for historical measured Full lifecycle evidence.
''')
    auditor = ROOT / 'dist/usb-auditor/EIMS_USB_Auditor'
    sys.path.insert(0, str(ROOT / 'tools'))
    import build_usb_package as usb
    if usb.find_problems(auditor):
        raise RuntimeError('Auditor integrity failed')
    # Review the actual bytes, including every source-archive member.
    for base in (target, auditor):
        for p in base.rglob('*'):
            if not p.is_file():
                continue
            rel = p.relative_to(base).as_posix()
            if any(part.lower() in {'reports', 'logs', '.env', '.git'} or part.startswith('~$')
                   for part in Path(rel).parts) or p.suffix.lower() in {'.xlsx', '.bak', '.dmp'}:
                raise RuntimeError('Private/generated artifact: ' + rel)
            blobs = [(rel, p.read_bytes())]
            if p.suffix == '.zip' and 'Source_Code' in p.parts:
                with zipfile.ZipFile(p) as z:
                    if z.testzip():
                        raise RuntimeError('Corrupt source ZIP')
                    blobs = [(n, z.read(n)) for n in z.namelist()]
            for name, data in blobs:
                if socket.gethostname().lower().encode() in data.lower():
                    raise RuntimeError('Actual device identifier in payload: ' + name)
                if any(value.encode() in data for value in defaults):
                    raise RuntimeError('Historical credential in payload: ' + name)
    now = datetime.now(timezone.utc).isoformat()
    reviewed = [{'path': p.relative_to(target).as_posix(), 'sha256': sha(p)}
                for p in sorted(target.rglob('*')) if p.is_file() and p.relative_to(target).as_posix()
                not in {'MANIFEST.txt', 'SHA256SUMS.txt', 'Tools/security-review.json', 'Tools/release-gate.json'}]
    full.write(target / 'Tools/security-review.json', json.dumps({
        'status': 'PASS', 'reviewedBy': 'Codex - targeted two-USB payload review', 'reviewedAt': now,
        'scope': 'Reviewed baseline plus changed source, private-path/device/default screening; internal transfer only.',
        'findings': [], 'files': reviewed}, indent=2))
    full.PAYLOAD = target
    full.refresh_manifest()
    packages = [{'kind': kind, 'source': base.relative_to(ROOT).as_posix(), 'security': 'PASS',
                 'manifestSha256': sha(base / 'MANIFEST.txt')}
                for kind, base in [('USB_AUDITOR', auditor), ('EIMS_HANDOVER', target)]]
    full.write(AREA / 'release-review.json', json.dumps({'utc': now, 'packages': packages,
                'sourceFiles': [{'path': r['path'], 'sha256': r['sha256']} for r in rows]}, indent=2))
    print(json.dumps({'packages': packages, 'source_files': len(rows), 'usb_written': False}))


if __name__ == '__main__':
    build()
