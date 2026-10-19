"""Stage only the typed-SETUP removal. Never installs, writes USB or replaces data."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import build as full


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(baseline, target):
    baseline, target = baseline.resolve(), target.resolve()
    if target.exists():
        raise RuntimeError('Candidate already exists; preserve/review before rebuilding')
    original = json.loads((baseline / 'MANIFEST.txt').read_text('utf-8'))
    for row in original['files']:
        path = baseline / row['path']
        if path.is_symlink() or not path.resolve().is_relative_to(baseline) or sha(path) != row['sha256']:
            raise RuntimeError('Unverified baseline file')
    shutil.copytree(baseline, target)
    source = full.TOOLS / 'Runtime.ps1'
    old_runtime = (baseline / 'Tools/Runtime.ps1').read_text('utf-8')
    before = "        $answer=Read-Host 'SETUP will install pinned Python/npm dependencies and create an isolated Docker project. Type SETUP to authorize, or Enter to cancel'\n        if($answer -cne 'SETUP'){Write-Host 'Cancelled; no installation changes.';exit 0}"
    after = "        Write-Host 'SETUP launched by the operator: checking pinned dependencies and isolated EIMS. Required installer/license/IT approvals still apply.'"
    if old_runtime.replace(before, after) != source.read_text('utf-8'):
        raise RuntimeError('Runtime source differs beyond the reviewed SETUP prompt change')
    shutil.copy2(source, target / 'Tools/Runtime.ps1')
    archive = target / 'Source_Code/EIMS_Source.zip'
    with zipfile.ZipFile(archive) as z:
        if z.testzip():
            raise RuntimeError('Source archive corrupt')
        members = {n: z.read(n) for n in z.namelist()}
    rel = 'tools/handover/Runtime.ps1'
    members[rel] = source.read_bytes()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(members.items()):
            z.writestr(name, data)
    ledger_path = target / 'Tools/source-ledger.json'
    ledger = json.loads(ledger_path.read_text('utf-8'))
    for row in ledger['files']:
        if row['path'] == rel:
            row.update(sha256=sha(source), deliveredSha256=sha(source), transforms=[])
    ledger['patch_scope'] = 'SETUP typed prompt only; application, dependencies, installation identity and data preserved'
    full.write(ledger_path, json.dumps(ledger, indent=2))
    review = json.loads((target / 'Tools/security-review.json').read_text('utf-8'))
    review.update(reviewedAt=datetime.now(timezone.utc).isoformat(),
                  reviewedBy='Codex - reviewed two-line SETUP-only patch; baseline preserved',
                  scope='Only SETUP prompt/runtime source and derived archive/metadata. No new installation/lifecycle claim.')
    review['files'] = [{'path': p.relative_to(target).as_posix(), 'sha256': sha(p)} for p in sorted(target.rglob('*'))
                       if p.is_file() and p.relative_to(target).as_posix() not in
                       {'MANIFEST.txt', 'SHA256SUMS.txt', 'Tools/security-review.json', 'Tools/release-gate.json'}]
    full.write(target / 'Tools/security-review.json', json.dumps(review, indent=2))
    full.PAYLOAD = target
    full.refresh_manifest()
    for name in ['SETUP.bat', 'Start.bat', 'Stop.bat', 'Tools/package.json', 'Tools/compose.yaml', 'Tools/requirements-handover.txt']:
        if sha(baseline / name) != sha(target / name):
            raise RuntimeError('Unrelated Full EIMS component changed')
    with zipfile.ZipFile(baseline / 'Source_Code/EIMS_Source.zip') as old, zipfile.ZipFile(archive) as new:
        if old.namelist() != new.namelist() or any(old.read(n) != new.read(n) for n in old.namelist() if n != rel):
            raise RuntimeError('Application source changed beyond SETUP helper')
    result = {'candidate': str(target), 'manifest_sha256': sha(target / 'MANIFEST.txt'),
              'typed_setup_removed': True, 'start_stop_dependencies_identity_unchanged': True,
              'usb_modified': False, 'live_setup_execution': 'NOT RUN'}
    print(json.dumps(result))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.baseline, args.target)
