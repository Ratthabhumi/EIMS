"""Add the local demo to the verified staging package; never update USB."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[3]
SPEC=importlib.util.spec_from_file_location('handover_build',ROOT/'tools/handover/build.py')
B=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(B)
P=B.PAYLOAD
V=B.STAGE/'verification'
D=P/'Demo_Runtime'

def fetch(url):
    with urllib.request.urlopen(url,timeout=30) as r:return r.read(40_000_000)

def manifest():
    B.refresh_manifest()
    path=P/'MANIFEST.txt';obj=json.loads(path.read_text());obj['mode']='LOCAL_DEMO_AND_FULL';B.write(path,json.dumps(obj,indent=2)+'\n')
    rows=[r['sha256']+'  '+r['path'] for r in obj['files']]
    rows.append(B.digest(path.read_bytes())+'  MANIFEST.txt')
    B.write(P/'SHA256SUMS.txt','\n'.join(rows)+'\n')

def snapshot():
    tracked=B.git('ls-files').splitlines()
    extras=[p.relative_to(ROOT).as_posix() for p in B.TOOLS.rglob('*') if p.is_file() and '__pycache__' not in p.parts]+['Flashdrive_Clone.bat']
    ledger=[];members={}
    for rel in sorted(set(tracked+extras)):
        if not B.allowed(rel):continue
        raw=(ROOT/rel).read_bytes();delivered,changes=B.transform(rel,raw,B.known_defaults())
        members[rel]=delivered;ledger.append({'path':rel,'sha256':B.digest(raw),'deliveredSha256':B.digest(delivered),'transforms':changes})
    members['clients/dashboard/src/components/HandoverAuthGate.tsx']=(B.TOOLS/'HandoverAuthGate.tsx').read_bytes()
    with zipfile.ZipFile(P/'Source_Code/EIMS_Source.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name,raw in sorted(members.items()):z.writestr(name,raw)
    B.write(P/'Tools/source-ledger.json',json.dumps({'revision':B.git('rev-parse','HEAD'),'branch':B.git('branch','--show-current'),'trackedPathsHash':B.digest('\n'.join(tracked).encode()),'files':ledger},indent=2)+'\n')

def build():
    if not (P/'Full_EIMS').exists():
        # Check and retain the exact previously verified package before moving
        # any launcher. One full-system copy is kept inside the combined pack.
        temporary=B.STAGE/'full-eims-preserved'
        if temporary.exists():raise RuntimeError('Existing preservation folder needs review; nothing overwritten.')
        command=f". '{B.TOOLS/'Integrity.ps1'}'; [void](Copy-VerifiedPackage '{P}' '{temporary}')"
        subprocess.run(['powershell.exe','-NoProfile','-Command',command],check=True)
        temporary.rename(P/'Full_EIMS')
    D.mkdir(exist_ok=True)
    runtime=D/'Python';runtime.mkdir(exist_ok=True)
    archive=V/'python-3.14.6-embed-amd64.zip'
    if not archive.exists():archive.write_bytes(fetch('https://www.python.org/ftp/python/3.14.6/python-3.14.6-embed-amd64.zip'))
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise RuntimeError('Corrupt official Python archive')
        z.extractall(runtime)
    B.write(runtime/'python314._pth','python314.zip\n.\nsite-packages\n')
    provenance=[{'package':'CPython embedded 3.14.6 x64','url':'https://www.python.org/ftp/python/3.14.6/python-3.14.6-embed-amd64.zip','sha256':B.digest(archive.read_bytes())}]
    sites=runtime/'site-packages';sites.mkdir(exist_ok=True)
    wheels=V/'demo-wheels';wheels.mkdir(exist_ok=True)
    for name,version in [('pydantic','2.13.5'),('pydantic-core','2.46.5'),('typing-extensions','4.16.0'),('typing-inspection','0.4.4'),('annotated-types','0.8.0')]:
        index=json.loads(fetch(f'https://pypi.org/pypi/{name}/{version}/json'))
        candidates=[x for x in index['urls'] if x['filename'].endswith(('py3-none-any.whl','py2.py3-none-any.whl','cp314-cp314-win_amd64.whl'))]
        if len(candidates)!=1:raise RuntimeError('Cannot uniquely select official wheel: '+name)
        item=candidates[0];wheel=wheels/item['filename']
        if not item['url'].startswith('https://files.pythonhosted.org/'):raise RuntimeError('Unexpected wheel origin')
        if not wheel.exists():wheel.write_bytes(fetch(item['url']))
        if B.digest(wheel.read_bytes())!=item['digests']['sha256']:raise RuntimeError('Wheel digest mismatch: '+name)
        with zipfile.ZipFile(wheel) as z:
            if z.testzip() or any(Path(n).is_absolute() or '..' in Path(n).parts for n in z.namelist()):raise RuntimeError('Invalid wheel archive')
            z.extractall(sites)
        provenance.append({'package':name,'version':version,'url':item['url'],'sha256':item['digests']['sha256'],'license':index['info'].get('license_expression') or index['info'].get('license')})
    B.write(D/'DEPENDENCY_PROVENANCE.json',json.dumps(provenance,indent=2)+'\n')
    B.write(D/'THIRD_PARTY_NOTICES.txt','CPython: Python/LICENSE.txt (includes bundled component notices).\nPydantic, pydantic-core, typing-extensions, typing-inspection and annotated-types: license files retained in Python/site-packages/*.dist-info/licenses.\nOfficial source URLs and verified wheel SHA-256 values: DEPENDENCY_PROVENANCE.json.\nThese dependencies keep their original licenses; EIMS owner permission does not replace them.\nPython embedding reference: https://docs.python.org/3.14/using/windows.html#the-embeddable-package\n')
    snapshot()
    with zipfile.ZipFile(P/'Source_Code/EIMS_Source.zip') as z:
        for name in z.namelist():
            if name.startswith('backend/') and Path(name).suffix in {'.py','.json'}:
                target=D/'App'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
    for name in ['server.py','supervisor.py','index.html']:shutil.copyfile(Path(__file__).parent/name,D/name)
    shutil.copyfile(B.TOOLS/'Integrity.ps1',P/'Tools/Integrity.ps1')
    obsolete=P/'Tools/DemoBootstrap.ps1'
    if obsolete.exists():obsolete.unlink() # Owned by this new demo builder only.
    batch='@echo off\r\nsetlocal EnableExtensions DisableDelayedExpansion\r\n"%~dp0Demo_Runtime\\Python\\python.exe" -B "%~dp0Demo_Runtime\\supervisor.py" %*\r\nset "EIMS_RESULT=%ERRORLEVEL%"\r\nif not "%EIMS_RESULT%"=="0" pause\r\nexit /b %EIMS_RESULT%\r\n'
    (P/'Start_EIMS.bat').write_bytes(batch.encode('ascii'))
    for name in ['SETUP.bat','Start.bat','Stop.bat']:
        target=P/name
        if target.exists():
            if target.read_bytes()!=(P/'Full_EIMS'/name).read_bytes():raise RuntimeError('Changed launcher needs review: '+name)
            target.unlink()
    B.write(P/'Tools/release-gate.json',json.dumps({'status':'OWNER_AUTHORIZED_INTERNAL','securityReview':'PENDING','ownerAuthorizationSha256':B.digest((P/'OWNER_HANDOVER_AUTHORIZATION.txt').read_bytes()),'productionReadiness':'NOT_APPROVED'},indent=2))
    manifest()
    print('Demo added locally. Independent security review and lifecycle tests are required. USB unchanged.')

if __name__=='__main__':build()
