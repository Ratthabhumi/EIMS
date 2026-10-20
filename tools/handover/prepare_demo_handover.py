"""Finalize an isolated demo candidate after its frontend build. No USB writes.
Reuses existing Python/Node/images. Replaces only frontend and handover adapters.
"""
from datetime import datetime, timezone
import hashlib, json, shutil, sys, uuid, zipfile
from pathlib import Path
import build
from prepare_offline_prerequisites import sha, write_json, forbidden
from synthetic_demo import write as write_demo

SOURCES=['tools/handover/HandoverAuthGate.tsx','tools/handover/Runtime.ps1','tools/handover/build.py',
    'tools/handover/run_backend.py','tools/handover/usb_backup.py','tools/handover/handover_session.py',
    'tools/handover/seed_demo.py','tools/handover/synthetic_demo.py','tools/handover/prepare_demo_handover.py',
    'tools/tests/test_handover_session.py','tools/tests/test_usb_backup.py','tools/tests/test_handover_process_identity.py']


def prepare(root, dashboard):
    root,dashboard=Path(root).resolve(),Path(dashboard).resolve()
    servers=[p for p in (dashboard/'.next/standalone').rglob('server.js') if (p.parent/'.next/BUILD_ID').exists()]
    if len(servers)!=1:raise ValueError('Expected one complete standalone build')
    archive=root/'Tools/Prepared_Runtime.zip'
    with zipfile.ZipFile(archive) as z:
        original=json.loads(z.read('runtime-manifest.json'))
        old={n:z.read(n) for n in z.namelist() if not n.startswith('Frontend/') and n!='runtime-manifest.json'}
    # Read frontend assets through build-time links; ZIP entries are ordinary files.
    for folder,prefix in [(servers[0].parent,'Frontend'),(dashboard/'.next/static','Frontend/.next/static'),(dashboard/'public','Frontend/public')]:
        if folder.exists():
            for p in folder.rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts:
                    old[prefix+'/'+p.relative_to(folder).as_posix()]=p.read_bytes()
    rows=[{'path':n,'size':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(old.items())]
    original['files']=rows
    old['runtime-manifest.json']=json.dumps(original,indent=2).encode()
    temp=archive.with_suffix('.new')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in sorted(old.items()):
            if forbidden(n):raise ValueError('Private artifact in prepared runtime')
            z.writestr(n,b)
    with zipfile.ZipFile(temp) as z:
        assert z.testzip() is None
        js=b''.join(z.read(n) for n in z.namelist() if n.endswith('.js') and n.startswith('Frontend/'))
        assert b'eims-bootstrap' in js and b'Local administrator password' not in js
    temp.replace(archive)
    for name in ['Runtime.ps1','run_backend.py','usb_backup.py','handover_session.py','seed_demo.py','synthetic_demo.py']:
        shutil.copy2(build.TOOLS/name,root/'Tools'/name)
    source=root/'Source_Code/EIMS_Source.zip'
    with zipfile.ZipFile(source) as z:members={n:z.read(n) for n in z.namelist()}
    for n in SOURCES:members[n]=(build.ROOT/n).read_bytes()
    members['clients/dashboard/src/components/HandoverAuthGate.tsx']=(build.TOOLS/'HandoverAuthGate.tsx').read_bytes()
    css='clients/dashboard/src/app/globals.css'
    members[css]=members[css].replace(b'@import "tailwindcss";',b'@import "tailwindcss" source("../");')
    defaults=build.known_defaults()
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in sorted(members.items()):
            if forbidden(n):raise ValueError('Private source artifact')
            for secret in defaults:
                if secret.encode() in b:raise ValueError('Known default in source')
            z.writestr(n,b)
    ledger=json.loads((root/'Tools/source-ledger.json').read_text())
    css_row=next(r for r in ledger['files'] if r['path']==css)
    css_row['deliveredSha256']=hashlib.sha256(members[css]).hexdigest()
    css_row['transforms']=sorted(set(css_row['transforms']+['scope-css-discovery-to-dashboard-src']))
    for n in SOURCES:
        row=next((r for r in ledger['files'] if r['path']==n),None)
        if row is None:row={'path':n,'transforms':[]};ledger['files'].append(row)
        row.update(sha256=sha(build.ROOT/n),deliveredSha256=hashlib.sha256(members[n]).hexdigest())
    write_json(root/'Tools/source-ledger.json',ledger)
    package=json.loads((root/'Tools/package.json').read_text())
    package.update(id='eims-'+hashlib.sha256(b'EIMS-SYNTHETIC-DEMO-2026-10-20-v1').hexdigest()[:16],
        mediaId=uuid.uuid4().hex,mode='PREPARED_SYNTHETIC_DEMO',demoOnly=True,localPasswordless=True)
    write_json(root/'Tools/package.json',package)
    setup=root/'SETUP.bat';text=setup.read_text()
    text=text.replace('if not defined EIMS_NONINTERACTIVE pause',
        'if not "%EIMS_RESULT%"=="0" if not defined EIMS_NONINTERACTIVE pause')
    setup.write_bytes(text.replace('\r\n','\n').replace('\n','\r\n').encode('ascii'))
    write_demo(root/'Demo/Reports')
    (root/'Demo/SYNTHETIC_DEMO.txt').write_text('All example devices, companies and findings are fictional. No live scanner or AI evaluation is claimed.\n')
    (root/'Demo/Firewall_Synthetic.txt').write_text('SYNTHETIC_DEMO\ndate=2026-10-20 time=01:00:00 devname="FW-DEMO-001" type="traffic" subtype="forward" srcip=192.0.2.10 dstip=198.51.100.20 action="deny" msg="Synthetic policy example; does not establish malicious activity"\n')
    (root/'START_HERE.txt').write_text('EIMS - SYNTHETIC DEMO ONLY\nFirst use: double-click SETUP.bat. Later: Start.bat.\nThe authorized Windows user/session opens the Dashboard automatically.\nNo manual EIMS password entry. A session lasts 15 minutes; use Start again when needed.\nBackend APIs remain authenticated. Private recovery credentials stay confidential.\nExamples are fictional: PC-DEMO-001, PC-DEMO-002 and SRV-DEMO-001.\nInventory, Import JSON, Windows events, Analyzer and History remain available.\nDocker/WSL prompts and approved restarts remain genuine Windows requirements.\nUse Stop.bat before moving PCs. USB checkpoints belong only to this new demo identity.\nThe previous operational data has been preserved privately outside this USB.\n')
    (root/'VERSION.txt').write_text('EIMS SYNTHETIC_DEMO handover 2026-10-20\nAdapters and prepared frontend updated; operational credentials/data not included.\n')
    demo_instructions='1. Run SETUP.bat once on an approved Windows PC.\n2. The authorized Windows session opens EIMS directly. Later use Start.bat.\n3. Explore the three fictional Inventory devices and their Windows events.\n4. Open an event in Analyzer; review evidence, limitations and History.\n5. Import Demo/Reports JSON if desired; records are SYNTHETIC_DEMO.\n6. Stop.bat saves the demo checkpoint before changing PCs.\nSession expired? Run Start.bat again. No manual EIMS password is needed.\n'
    (root/'Demo/DEMO_STEPS.txt').write_text(demo_instructions)
    build.guide_pdf(root/'EIMS_Handover_Guide.pdf',[
        ('Start and review',demo_instructions),
        ('Data and access','All delivered examples are fictional, not live scan results or user-evaluation findings. API authentication remains enabled. Local sign-in requires the authorized Windows user/session. The previous operational data is preserved privately off USB.'),
        ('Prerequisites and recovery','Company IT must authorize Docker licensing and Windows changes. Follow genuine installer/UAC prompts and rerun SETUP after an approved restart. Demo recovery checkpoints use a separate package/media identity. Stop before moving PCs; newly collected real reports are confidential.')],
        subtitle='20 October 2026 | SYNTHETIC DEMO')
    refresh(root)


def refresh(root):
    root=Path(root)
    excluded={'MANIFEST.txt','SHA256SUMS.txt','Tools/security-review.json','Tools/release-gate.json'}
    review=dict(status='PASS',reviewedBy='Codex exact demo artifact review',reviewedAt=datetime.now(timezone.utc).isoformat(),
        scope='Synthetic fixture/source/archive screening; local authentication and release tests recorded separately.',
        files=[dict(path=p.relative_to(root).as_posix(),sha256=sha(p)) for p in sorted(root.rglob('*')) if p.is_file() and p.relative_to(root).as_posix() not in excluded])
    write_json(root/'Tools/security-review.json',review)
    gate=json.loads((root/'Tools/release-gate.json').read_text());gate['securityReview']='PASS'
    gate['acceptance']='SYNTHETIC_DEMO only; clean second physical PC remains NOT RUN; no production approval.'
    write_json(root/'Tools/release-gate.json',gate)
    build.PAYLOAD=root;build.refresh_manifest()
    print(json.dumps({'manifest':sha(root/'MANIFEST.txt'),'files':sum(p.is_file() for p in root.rglob('*')),'package':json.loads((root/'Tools/package.json').read_text())['id']}))


if __name__=='__main__':prepare(Path(sys.argv[1]),Path(sys.argv[2]))
