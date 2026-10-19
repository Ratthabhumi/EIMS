"""Build/check the separate ONEDIR candidate. Never install on a target or write USB."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

import build_usb_package as legacy

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'dist/usb-auditor-exe'
PACKAGE = BUILD / 'package/EIMS_USB_Auditor'
SOURCE = ROOT / 'clients/usb_auditor'
NAMES = ('EIMS-Auditor-Standard.exe', 'EIMS-Auditor-Admin.exe')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def include_licenses(package):
    """Preserve the notices shipped by the exact installed build dependencies."""
    from shutil import copy2
    notices = package / 'ThirdPartyNotices'
    notices.mkdir(exist_ok=True)
    copy2(Path(sys.base_prefix) / 'LICENSE.txt', notices / 'CPython-LICENSE.txt')
    for folder in ('tcl8.6', 'tk8.6'):
        license_path = Path(sys.base_prefix) / 'tcl' / folder / 'license.terms'
        if license_path.is_file():
            copy2(license_path, notices / (folder + '-license.terms'))
    for name in ('psutil', 'openpyxl', 'et-xmlfile', 'pyinstaller'):
        dist = importlib.metadata.distribution(name)
        for file in dist.files or []:
            label = file.name.lower()
            if 'license' in label or 'licence' in label or label.startswith('copying'):
                copy2(dist.locate_file(file), notices / (name + '-' + file.name))


def manifest_level(path):
    import pefile
    with pefile.PE(str(path)) as pe:
        for resource in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            if resource.id == 24:
                data = resource.directory.entries[0].directory.entries[0].data.struct
                xml = pe.get_data(data.OffsetToData, data.Size).decode('utf-8')
                import xml.etree.ElementTree as ET
                for element in ET.fromstring(xml).iter():
                    if element.tag.endswith('requestedExecutionLevel'):
                        return element.attrib['level']
    raise ValueError('No Windows privilege manifest')


def check(package):
    sys.path.insert(0, str(SOURCE))
    from portable_entry import verify_package
    verify_package(package)
    for name, level in zip(NAMES, ('asInvoker', 'requireAdministrator')):
        if manifest_level(package / name) != level:
            raise ValueError('Wrong UAC manifest: ' + name)
    if (package / 'runtime').exists() or list(package.rglob('*.bat')) or list(package.rglob('*.ps1')):
        raise ValueError('EXE package contains an obsolete launcher/runtime')
    for path in package.rglob('*'):
        if path.is_file() and (path.relative_to(package).parts[0] == 'Evidence' or path.suffix.lower() in {'.log', '.xlsx', '.sqlite', '.bak'}):
            raise ValueError('Collected/private artifact in clean candidate')
    return {'package': str(package), 'files': len([p for p in package.rglob('*') if p.is_file()]),
            'manifest_sha256': sha(package / 'MANIFEST.txt'), 'windows_manifests': dict(zip(NAMES, ('asInvoker', 'requireAdministrator')))}


def build():
    if importlib.metadata.version('pyinstaller') != '6.22.3':
        raise RuntimeError('Use the pinned isolated build environment, PyInstaller 6.22.3')
    if PACKAGE.exists():
        raise RuntimeError('Candidate already exists; preserve/review it before any rebuild')
    BUILD.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([sys.executable, '-m', 'PyInstaller', str(SOURCE / 'PortableAuditors.spec'),
                             '--distpath', str(PACKAGE.parent), '--workpath', str(BUILD / 'work'), '--log-level', 'WARN'],
                            cwd=ROOT, timeout=600)
    if result.returncode:
        raise RuntimeError('Executable build failed')
    from shutil import copy2
    copy2(ROOT / 'LICENSE', PACKAGE / 'LICENSE')
    include_licenses(PACKAGE)
    (PACKAGE / 'PACKAGE_TYPE').write_text('USB_AUDITOR_EXE\n', encoding='ascii')
    (PACKAGE / 'README.txt').write_text('''EIMS Portable Windows Auditor 1.3.1 (Windows PC x64 candidate)
Choose EIMS-Auditor-Standard.exe (no elevation) or EIMS-Auditor-Admin.exe (normal UAC).
Both open the same GUI with optional business fields and module selection.
Start Audit, review immutable evidence, apply separate annotations, then Export.
New audit clears customer fields; profiles are never automatically reloaded.
Startup shows a live integrity check before any scanner runs. On unapproved
USB storage, choose an approved LOCAL parent for EIMS_Evidence explicitly.
The EXEs may run from USB; reports are not silently redirected to AppData.
Both use the SAME scanner/exporters. No Python/Node/Docker installation is needed.
Run only a trusted reviewed package. These EXEs are UNSIGNED; company IT must
approve signing/allowlisting if required. Hashes show consistency, not authenticity.
Do not run elevated code from a tampered/user-untrusted package. Never bypass EDR,
AppLocker, App Control, Windows UAC or PowerShell policy.

Copy the complete folder from an approved share to a writable local directory;
direct network-share execution/output is rejected. Default output is Evidence
beside these EXEs; there is NO silent AppData fallback. Local Evidence uses a
protected owner/SYSTEM ACL. Use --output-dir ABSOLUTE_APPROVED_DIRECTORY to select
an explicit local/removable destination (parent must already exist).
For removable/non-ACL media, IT must approve encryption and prepare audit-policy.json
from the example with an approval reference. This records approval; it does NOT
detect/establish encryption. Never approve plaintext media contrary to company policy.
Alternate-admin accounts may require a separate approved Evidence directory.

JSON, uniquely named Excel and unique execution logs remain in Evidence/reports
and Evidence/logs. Every JSON is preserved. No automatic upload occurs. Read-only
System/Application events and firewall evidence are bounded. Security channel is
NOT enabled. Messages use explicit 64 KiB/event, 8 MiB/collection UTF-8 limits;
truncation/redaction metadata is retained. Final JSON is capped at 16 MiB.
Exit codes: 0 saved/pass; 1 saved/findings; 3 partial; 2 failed. Review UNKNOWN.
The GUI stays open. Explicit --headless --no-wait is for CLI diagnostics.

PowerShell REMAINS REQUIRED by security/event/firewall/post-clone collectors.
Packaging as EXE does not remove that dependency. Blocked queries are unavailable.
No execution-policy bypass is used. Runtime DLL search paths are reset for child
Windows tools and restored within the application process.
Intentional writes: Evidence directories/ACL, write-probe creation/removal, JSON,
Excel and execution logs. Windows/EDR may record normal execution. Nothing clears
OS logs, changes services/registry/firewall/audit policy, or conceals execution.
No customer records are bundled. Windows Server/clean-PC/all-policy compatibility
is NOT established by this build. Keep the previously verified fallback until
actual release acceptance and owner-approved USB replacement are complete.
''', encoding='utf-8')
    (PACKAGE / 'audit-policy.example.json').write_text(json.dumps({
        'encrypted_removable_media_approved': False, 'approval_reference': ''}, indent=2), encoding='utf-8')
    files = [p for p in SOURCE.rglob('*.py') if '__pycache__' not in p.parts and 'tests' not in p.parts]
    files += [SOURCE / 'PortableAuditors.spec', Path(__file__), ROOT / 'tools/auditor_exe_requirements.txt']
    provenance = {'source_commit': legacy._git(ROOT, ['rev-parse', 'HEAD']),
                  'worktree': legacy._git(ROOT, ['status', '--porcelain', '--untracked-files=no']),
                  'source_files': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)} for p in sorted(files)],
                  'dependencies': {n: importlib.metadata.version(n) for n in ['pyinstaller', 'pyinstaller-hooks-contrib', 'psutil', 'openpyxl', 'et-xmlfile', 'pefile']}}
    (PACKAGE / 'BUILD_PROVENANCE.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    (PACKAGE / 'VERSION.txt').write_text('EIMS Portable Auditor 1.3.1\nMode: ONEDIR dual EXE, shared engine/runtime\n'
                                       + 'Source commit: ' + provenance['source_commit'] + '\n'
                                       + 'Worktree modifications recorded in BUILD_PROVENANCE.json\nPyInstaller 6.22.3; Python ' + sys.version.split()[0] + '\n', encoding='utf-8')
    legacy.write_manifest(PACKAGE)
    print(json.dumps(check(PACKAGE)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--check', type=Path)
    parser.add_argument('--slot', choices=['package', 'verified', 'gui', 'gui_final', 'gui_release', 'ready', 'startup_fix'], default='package')
    args = parser.parse_args()
    if args.build:
        PACKAGE = BUILD / args.slot / 'EIMS_USB_Auditor'
        build()
    elif args.check:
        print(json.dumps(check(args.check)))
    else:
        parser.print_help()
