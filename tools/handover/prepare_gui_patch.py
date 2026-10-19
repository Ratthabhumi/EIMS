"""Stage reviewed source-only GUI/inventory changes on the existing Full handover.

No dependency installation, build, operational service action or USB writes.
The replacement remains approval-pending; the verified physical release is intact.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

import build as full


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(baseline, target, refresh=False):
    baseline,target=baseline.resolve(),target.resolve()
    if target.exists():
        if not refresh:raise RuntimeError('Preserve the existing candidate; no overwrite')
        previous=json.loads((target/'MANIFEST.txt').read_text('utf-8'))
        for entry in previous['files']:
            if sha(target/entry['path']) != entry['sha256']:raise RuntimeError('Candidate changed outside builder; preserve it')
    if not baseline.is_relative_to(full.ROOT/'Final_CO-OP') or not target.is_relative_to(full.ROOT/'Final_CO-OP'):
        raise ValueError('Only local staging directories are permitted')
    manifest=json.loads((baseline/'MANIFEST.txt').read_text('utf-8'))
    for row in manifest['files']:
        path=baseline/row['path']
        if path.is_symlink() or sha(path)!=row['sha256']:raise RuntimeError('Baseline integrity failure')
    changed=subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard'],cwd=full.ROOT,text=True).splitlines()
    paths=sorted({p for p in changed if full.allowed(p)})
    # Keep the frozen build/runtime dependencies and installation identity.
    allowed_roots=('clients/usb_auditor/','backend/domain/asset_registry/','backend/domain/analyzer/services/',
                   'clients/dashboard/src/','tests/','tools/handover/')
    paths=[p for p in paths if p.startswith(allowed_roots)]
    if not target.exists():shutil.copytree(baseline,target)
    archive=target/'Source_Code/EIMS_Source.zip'
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise RuntimeError('Corrupt baseline source ZIP')
        members={n:z.read(n) for n in z.namelist()}
    ledger_path=target/'Tools/source-ledger.json'
    ledger=json.loads(ledger_path.read_text('utf-8'))
    rows={row['path']:row for row in ledger['files']}
    defaults=full.known_defaults()
    for rel in paths:
        source=full.ROOT/rel
        if source.is_symlink() or not source.is_file():raise RuntimeError('Unsafe/deleted source requires review')
        raw=source.read_bytes()
        delivered,transforms=full.transform(rel,raw,defaults)
        members[rel]=delivered
        rows[rel]={'path':rel,'sha256':sha(source),'deliveredSha256':full.digest(delivered),'transforms':transforms}
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(members.items()):z.writestr(name,data)
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise RuntimeError('Updated source ZIP corrupt')
    ledger.update(files=[rows[key] for key in sorted(rows)],patch_scope='Source-only GUI/inventory/event review update; no dependency/runtime change')
    full.write(ledger_path,json.dumps(ledger,indent=2))
    # Reset prior package approval. New source requires independent release acceptance.
    gate={'status':'HANDOVER_APPROVAL_PENDING','securityReview':'SOURCE_UPDATE_ACCEPTANCE_PENDING',
          'reviewedBy':None,'reviewedAt':None,'evidence':[]}
    full.write(target/'Tools/release-gate.json',json.dumps(gate,indent=2))
    review={'status':'PENDING','scope':'Source-only changes staged; no live Full EIMS acceptance claimed',
            'files':[{'path':p.relative_to(target).as_posix(),'sha256':sha(p)} for p in sorted(target.rglob('*'))
                     if p.is_file() and p.relative_to(target).as_posix() not in {'MANIFEST.txt','SHA256SUMS.txt','Tools/security-review.json','Tools/release-gate.json'}]}
    full.write(target/'Tools/security-review.json',json.dumps(review,indent=2))
    full.PAYLOAD=target;full.refresh_manifest()
    for name in ('SETUP.bat','Start.bat','Stop.bat','Tools/Runtime.ps1','Tools/package.json','Tools/compose.yaml','Tools/requirements-handover.txt'):
        if sha(baseline/name)!=sha(target/name):raise RuntimeError('Frozen infrastructure changed')
    return {'candidate':str(target),'manifest_sha256':sha(target/'MANIFEST.txt'),'changed_sources':len(paths),
            'release_gate':'PENDING','physical_USB_changed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',required=True,type=Path)
    parser.add_argument('--target',required=True,type=Path)
    parser.add_argument('--refresh-reviewed',action='store_true')
    args=parser.parse_args()
    print(json.dumps(prepare(args.baseline,args.target,args.refresh_reviewed)))
