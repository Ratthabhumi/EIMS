"""Explicit-allowlist co-op release builder. No network, Git mutation or USB I/O."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'tools' / 'handover'
STAGE = ROOT / 'Final_CO-OP'
PAYLOAD = STAGE / 'Payload'
SECRET_FIELDS = {'DB_PASSWORD','JWT_SECRET_KEY','ADMIN_TOKEN','ADMIN_PASSWORD','MINIO_ACCESS_KEY','MINIO_SECRET_KEY'}

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def git(*args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()

def allowed(path: str) -> bool:
    p=Path(path)
    if any(part in {'.git','.env','.local-private','node_modules','.next','__pycache__','Final_CO-OP','backups','dist'} for part in p.parts):
        return False
    if path in {'LICENSE','NOTICE','requirements.txt','pyproject.toml','alembic.ini','.env.example','README.md','docker-compose.yml','Flashdrive_Clone.bat','03_SOFTWARE_ARCHITECTURE_DOCUMENT.md','04_DATABASE_DESIGN.md','05_API_SPECIFICATION.md'}:
        return True
    if path.startswith('backend/'):
        return p.suffix in {'.py','.json'}
    if path.startswith('clients/dashboard/'):
        return p.suffix in {'.ts','.tsx','.json','.css','.mjs','.cjs','.js','.svg'}
    if path.startswith('clients/usb_auditor/'):
        return p.suffix in {'.py','.md','.txt'}
    if path.startswith('migrations/'):
        return p.suffix in {'.py','.mako'} or p.name=='README'
    if path.startswith('tests/'):
        return p.suffix in {'.py','.cjs','.txt'} and ('fixtures/' not in path or path=='tests/fixtures/windows_shutdown_synthetic.txt')
    if path.startswith('tools/handover/'):
        return p.suffix in {'.py','.ps1','.tsx','.md','.json','.txt','.html'}
    return path in {'deployments/observability/prometheus.yml','tools/history_sandbox.py','docs/engineering-process/REQUIREMENTS_TRACEABILITY_MATRIX.md','docs/engineering-process/SYSTEM_DESIGN.md','docs/engineering-process/PUBLIC_REPOSITORY_SECURITY_REVIEW.md','docs/engineering-process/ISOLATED_HISTORY_RUNBOOK.md'} or path.startswith('EIMS_supervision_synthetic_demo_files_2026-10-09/') and p.name in {'01_report.txt','02_Task_long.log'}

def known_defaults() -> set[str]:
    tree=ast.parse((ROOT/'backend/core/config.py').read_text('utf-8'))
    found=set()
    for node in ast.walk(tree):
        if isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name) and node.target.id in SECRET_FIELDS and isinstance(node.value,ast.Call):
            for kw in node.value.keywords:
                if kw.arg=='default' and isinstance(kw.value,ast.Constant) and isinstance(kw.value.value,str) and kw.value.value:
                    found.add(kw.value.value)
    return found

def transform(path: str, raw: bytes, defaults: set[str]) -> tuple[bytes,list[str]]:
    text=raw.decode('utf-8-sig')
    changes=[]
    # Remove every exact known developer default from the delivered snapshot,
    # including comparison fixtures; never print the removed values.
    for value in sorted(defaults,key=len,reverse=True):
        if value in text:
            text=text.replace(value,'');changes.append('removed-known-development-default')
    if path=='clients/dashboard/src/app/layout.tsx':
        text='import { HandoverAuthGate } from "@/components/HandoverAuthGate";\n'+text
        text=text.replace('<ThemeProvider ', '<HandoverAuthGate><ThemeProvider ',1).replace('</ThemeProvider>','</ThemeProvider></HandoverAuthGate>',1)
        changes.append('secure-handover-login-wrapper')
    if path.startswith('clients/dashboard/'):
        new=text.replace('http://localhost:8000','http://127.0.0.1:18101').replace('http://127.0.0.1:8000','http://127.0.0.1:18101')
        if new!=text: changes.append('isolated-local-api-address');text=new
    if path=='clients/dashboard/src/components/SidebarNav.tsx':
        # Do not send the receiving engineer to a different existing deployment.
        text=re.sub(r'<a\b[^>]*href="http://localhost:(?:3000|9001|9090)/?"[\s\S]*?</a>', '',text)
        changes.append('remove-links-to-uninstalled-optional-operator-consoles')
    if path=='clients/usb_auditor/config/settings.py':
        text=text.replace('http://localhost:8000','http://127.0.0.1:18101').replace('http://127.0.0.1:8000','http://127.0.0.1:18101')
        changes.append('isolated-local-collector-api-default')
    return text.encode('utf-8'),sorted(set(changes))

def write(path: Path,text: str):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8',newline='\n')

def runtime_pins() -> str:
    code="import importlib.metadata as m,json; print(json.dumps({x.metadata['Name'].lower():x.version for x in m.distributions()}))"
    packages={k.replace('_','-'):v for k,v in json.loads(subprocess.check_output([str(ROOT/'venv/Scripts/python.exe'),'-c',code],text=True)).items()}
    names=[]
    for line in (ROOT/'requirements.txt').read_text().splitlines():
        match=re.match(r'([A-Za-z0-9_-]+)',line)
        if match and match[1] not in {'fastembed','sentence-transformers'}:
            name=match[1].lower(); names.append(name)
    names+=['requests','beautifulsoup4','aiosqlite']
    missing=[n for n in names if n not in packages]
    if missing: raise RuntimeError('Cannot pin missing dependencies: '+', '.join(missing))
    return '# Direct requirements pinned from inspected developer environment; transitive wheel lock is NOT claimed.\n# Models/ML runtimes excluded; vector retrieval optional.\n'+'\n'.join(n+'=='+packages[n] for n in sorted(set(names)))+'\n'

def compose_text() -> str:
    images={}
    for tag in ['pgvector/pgvector:pg16','redis:7-alpine','minio/minio:latest']:
        values=json.loads(subprocess.check_output(['docker','image','inspect',tag,'--format','{{json .RepoDigests}}'],text=True))
        if not values: raise RuntimeError('A verified image digest is required: '+tag)
        images[tag]=values[0]
    return '''# Dedicated handover core; no existing container names, ports or volumes reused.
services:
  postgres:
    image: %s
    environment:
      POSTGRES_USER: eims_user
      POSTGRES_DB: eims_handover
      POSTGRES_PASSWORD: ${EIMS_DB_PASSWORD:?Private configuration required}
    ports: ["127.0.0.1:18543:5432"]
    volumes: ["${EIMS_DATA_ROOT}/postgres:/var/lib/postgresql/data"]
    healthcheck:
      test: [CMD-SHELL, "pg_isready -U eims_user -d eims_handover"]
      interval: 3s
      timeout: 3s
      retries: 30
  redis:
    image: %s
    command: [redis-server, --appendonly, "yes", --maxmemory, 256mb, --maxmemory-policy, volatile-lru]
    ports: ["127.0.0.1:16379:6379"]
    volumes: ["${EIMS_DATA_ROOT}/redis:/data"]
    healthcheck:
      test: [CMD, redis-cli, ping]
      interval: 3s
      timeout: 3s
      retries: 30
  minio:
    image: %s
    command: [server, /data, --console-address, ":9001"]
    environment:
      MINIO_ROOT_USER: ${EIMS_MINIO_ACCESS_KEY:?Private configuration required}
      MINIO_ROOT_PASSWORD: ${EIMS_MINIO_SECRET_KEY:?Private configuration required}
    ports: ["127.0.0.1:19000:9000", "127.0.0.1:19001:9001"]
    volumes: ["${EIMS_DATA_ROOT}/minio:/data"]
    healthcheck:
      test: [CMD, curl, -f, http://localhost:9000/minio/health/live]
      interval: 3s
      timeout: 3s
      retries: 30
''' % (images['pgvector/pgvector:pg16'],images['redis:7-alpine'],images['minio/minio:latest'])

def guide_pdf(path: Path, sections: list[tuple[str,str]], subtitle='Local engineering handover'):
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
    styles=getSampleStyleSheet()
    styles['Title'].textColor=colors.HexColor('#1E3A8A')
    styles['BodyText'].fontSize=10;styles['BodyText'].leading=14
    story=[Paragraph('EIMS - Engineering Handover',styles['Title']),Paragraph(escape(subtitle),styles['Normal']),Spacer(1,12)]
    for title,body in sections:
        story.append(KeepTogether([Paragraph(escape(title),styles['Heading2']),Paragraph(escape(body).replace('\n','<br/>'),styles['BodyText'])]));story.append(Spacer(1,9))
    def page_number(canvas,doc):
        canvas.setFillColor(colors.HexColor('#1E3A8A'));canvas.setFont('Helvetica',9)
        canvas.drawString(40,25,'EIMS | Internal handover | Not production-approved');canvas.drawRightString(555,25,str(doc.page))
    SimpleDocTemplate(str(path),pagesize=(595.28,841.89),rightMargin=40,leftMargin=40,topMargin=38,bottomMargin=42).build(story,onFirstPage=page_number,onLaterPages=page_number)

def build():
    if PAYLOAD.exists():
        if '--rebuild-reviewed' in sys.argv and (PAYLOAD/'MANIFEST.txt').is_file():
            old=json.loads((PAYLOAD/'MANIFEST.txt').read_text())
            for item in old['files']:
                existing=PAYLOAD/item['path']
                if not existing.is_file() or digest(existing.read_bytes())!=item['sha256']:
                    raise RuntimeError('Existing staged artifact changed outside builder; preserve/review first: '+item['path'])
            expected={item['path'] for item in old['files']}|{'MANIFEST.txt','SHA256SUMS.txt'}
            actual={p.relative_to(PAYLOAD).as_posix() for p in PAYLOAD.rglob('*') if p.is_file()}
            if actual!=expected:raise RuntimeError('Unreviewed staged files; preserve/review before rebuild')
        elif '--resume-incomplete' not in sys.argv or (PAYLOAD/'MANIFEST.txt').exists() or not (PAYLOAD/'Tools/source-ledger.json').is_file():
            raise RuntimeError('Payload already exists. Preserve/review it first; only a known incomplete build can resume with --resume-incomplete.')
        previous=json.loads((PAYLOAD/'Tools/source-ledger.json').read_text())
        if previous['revision'] != git('rev-parse','HEAD'):
            raise RuntimeError('Incomplete build revision differs; preserve and review it first.')
    tracked=git('ls-files').splitlines()
    extras=[p.relative_to(ROOT).as_posix() for p in TOOLS.rglob('*') if p.is_file() and '__pycache__' not in p.parts]+['Flashdrive_Clone.bat']
    paths=sorted(p for p in set(tracked+extras) if allowed(p))
    defaults=known_defaults()
    ledger=[]; members={}; transforms=[]
    for rel in paths:
        p=ROOT/rel
        if p.is_symlink() or not p.is_file(): raise RuntimeError('Missing/deleted/link source requires review: '+rel)
        data=p.read_bytes()
        if len(data)>4_000_000: raise RuntimeError('Unexpected large source file: '+rel)
        delivered,changes=transform(rel,data,defaults)
        if re.search(rb'-----BEGIN (?:RSA )?PRIVATE KEY-----[\r\n]+[A-Za-z0-9+/=]{32,}', delivered):
            raise RuntimeError('Private-key material detected; value not displayed: '+rel)
        if any(value.encode() in delivered for value in defaults): raise RuntimeError('Known credential remains: '+rel)
        members[rel]=delivered
        ledger.append({'path':rel,'sha256':digest(data),'deliveredSha256':digest(delivered),'transforms':changes})
        if changes:transforms.append({'path':rel,'changes':changes})
    members['clients/dashboard/src/components/HandoverAuthGate.tsx']=(TOOLS/'HandoverAuthGate.tsx').read_bytes()
    revision=git('rev-parse','HEAD')
    identity=digest(json.dumps(ledger,sort_keys=True).encode())[:16]
    PAYLOAD.mkdir(parents=True,exist_ok=True)
    for folder in ['Source_Code','Tools','Sample_Logs','Demo','Developer_Docs']:(PAYLOAD/folder).mkdir(exist_ok=True)
    archive=PAYLOAD/'Source_Code/EIMS_Source.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(members.items()):z.writestr(name,data)
    with zipfile.ZipFile(archive) as z:
        if z.testzip() or len(z.namelist())!=len(members):raise RuntimeError('Source ZIP verification failed')
    write(PAYLOAD/'Tools/source-ledger.json',json.dumps({'revision':revision,'branch':git('branch','--show-current'),'trackedPathsHash':digest('\n'.join(tracked).encode()),'files':ledger,'packageTransforms':transforms},indent=2)+'\n')
    write(PAYLOAD/'Tools/package.json',json.dumps({'id':'eims-'+identity,'mode':'GUIDED_FULL_EIMS_CORE','python':'3.14.6','node':'24.18.0','dockerDesktopObserved':'4.85.0','setup':'ONLINE_REQUIRED','portableVerified':False,'localPasswordless':True},indent=2)+'\n')
    write(PAYLOAD/'Tools/release-gate.json',json.dumps({'status':'HANDOVER_APPROVAL_PENDING','securityReview':'MANUAL_AND_HISTORICAL_CLOSURE_PENDING','reviewedBy':None,'reviewedAt':None,'evidence':[]},indent=2)+'\n')
    write(PAYLOAD/'Tools/requirements-handover.txt',runtime_pins())
    write(PAYLOAD/'Tools/compose.yaml',compose_text())
    for name in ['Runtime.ps1','Prerequisites.ps1','Integrity.ps1','run_backend.py','handover_session.py','smoke.py','command_runner.py']:shutil.copyfile(TOOLS/name,PAYLOAD/'Tools'/name)
    write(PAYLOAD/'OWNER_HANDOVER_AUTHORIZATION.txt',(TOOLS/'OWNER_HANDOVER_AUTHORIZATION.txt').read_text().replace('{REVISION}',revision))
    for batch,action in [('SETUP.bat','Setup'),('Start.bat','Start'),('Stop.bat','Stop')]:
        content='@echo off\r\nsetlocal EnableExtensions DisableDelayedExpansion\r\n"%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -File "%~dp0Tools\\Runtime.ps1" -Action '+action+' %*\r\nset "EIMS_RESULT=%ERRORLEVEL%"\r\nif not defined EIMS_NONINTERACTIVE pause\r\nexit /b %EIMS_RESULT%\r\n'
        if action == 'Setup':
            content=content.replace('if not defined EIMS_NONINTERACTIVE pause','if not "%EIMS_RESULT%"=="0" if not defined EIMS_NONINTERACTIVE pause')
        (PAYLOAD/batch).write_bytes(content.encode('ascii'))
    write(PAYLOAD/'VERSION.txt',f'EIMS co-op handover | {datetime.now(timezone.utc).isoformat()}\nRevision: {revision}\nBranch: {git("branch","--show-current")}\nReviewed current local file contents are included; see Tools/source-ledger.json.\nSnapshot transforms: known default removal, secure browser sign-in, isolated API/console references.\nClassification: owner permission recorded; independent payload review required. See release-gate.json and Developer_Docs/ACCEPTANCE.md. Clean Windows is NOT TESTED.\n')
    for name in ['01_report.txt','02_Task_long.log']:
        shutil.copyfile(ROOT/'EIMS_supervision_synthetic_demo_files_2026-10-09'/name,PAYLOAD/'Sample_Logs'/name)
    shutil.copyfile(ROOT/'tests/fixtures/windows_shutdown_synthetic.txt',PAYLOAD/'Sample_Logs/windows_shutdown_synthetic.txt')
    write(PAYLOAD/'Sample_Logs/README.txt','Synthetic examples only.\nVeeam: select Evidence Bundle, English; add 01_report.txt and 02_Task_long.log together. Expected observed required-file error, source 02_Task_long.log line 1001; cross-file association NONE. No shared cause is established.\nWindows: upload windows_shutdown_synthetic.txt. Event 41 indicates an unclean restart, not proof of power loss.\nNever import customer logs into this handover demonstration.\n')
    write(PAYLOAD/'Demo/DEMO_STEPS.txt','1. SETUP.bat once; the authorized Windows session opens the Dashboard automatically.\n2. Start.bat opens http://127.0.0.1:13101/analyzer.\n3. Select Evidence Bundle and English. Upload the two Veeam synthetic files.\n4. Analyze, review the observed required-file error and original line 1001.\n5. Reopen the saved synthetic result in History.\n6. Stop.bat preserves the isolated data.\nDo not describe a diagnostic match as a confirmed cause. No fabricated recording is supplied.\n')
    quick='''EIMS - QUICK START
==================
STATUS: Owner-authorized internal handover; independent payload scan required.
See Developer_Docs/ACCEPTANCE.md for actual application readiness.
DEFAULT: Guided Full EIMS core. NOT a verified portable product.
ONLINE SETUP REQUIRED. Clean Windows verification is pending.

FIRST TIME (copy this whole folder to your PC first):
1. Double-click SETUP.bat. Keep this whole folder intact.
2. IT must approve Docker Desktop/WSL, Python 3.14.6 and Node 24.18.0.
3. Approve the exact installation actions when prompted. No licenses are auto-accepted.
4. If an installer requires restart, restart yourself and run SETUP.bat again.
5. The authorized Windows session opens the Dashboard automatically.
   Use Start.bat again when the short local session expires.

NEXT TIME: Start.bat.     TO STOP: Stop.bat.
The application/data are installed under your user-local EIMS-Coop folder.
The USB is not used for databases, runtime logs or model caches.

TRY IT: Analyzer > Evidence Bundle > English > the two Veeam files in
Sample_Logs > Analyze > check original evidence > reopen History.
Vector RAG models, paid AI, OCR engine and monitoring consoles are excluded.
Use synthetic examples only. No production certification or human study is claimed.

DETAILS: EIMS_Handover_Guide.pdf and Developer_Docs/DEVELOPMENT.md.
If scripts are blocked, ask IT. Do not disable Windows security controls.
'''
    write(PAYLOAD/'START_HERE.txt',quick)
    sections=[
      ('Purpose and delivery mode','EIMS helps an infrastructure engineer inspect logs, review observed findings and verify source evidence. This release selects guided Full EIMS core: the real dashboard/API and isolated PostgreSQL, Redis and MinIO. Docker-free portability is NOT verified. The existing SQLite harness overrides authentication for synthetic tests and is not shipped as an operational product.'),
      ('Capabilities and boundaries','Windows text/EVTX and selected Veeam/firewall formats are supported by the existing parsers. PAN-OS support is bounded to known CSV families. Filename/line references and History are retained. Event 41 does not prove a power outage; file access does not prove exfiltration; shared identifiers do not prove causality. Formal engineer usability evaluation is still planned.'),
      ('Windows prerequisites','Target: Windows 11 x64 build 22631 or newer, at least 8 GiB free disk, online access to official package sources and Docker registries. Inspected runtime pins: Python 3.14.6, Node 24.18.0; Docker Desktop observed 4.85.0. Check current IT and Docker supported-platform/licensing requirements. ARM64, Windows Server and offline installation are not validated.'),
      ('First setup','Run SETUP.bat once after permission is granted. It checks dependencies and offers exact winget package identities/versions when missing. Installers remain interactive; no agreements, WSL feature changes or reboot are automated. Approve SETUP explicitly. Files install under %LOCALAPPDATA%/EIMS-Coop/<package-id>. Interrupted setup reuses the installation identity and saved credentials. Existing unrecognized data or missing credentials stops setup.'),
      ('Start, local session and stop','Use Start.bat after setup. It reuses installed dependencies and starts only the installation-specific Docker project plus owned localhost servers. Start requires actual core health and an authenticated synthetic smoke test before READY. Browser access uses a short-lived Windows-authorized local session; no manual password entry is required. Passwords/tokens are not logged or embedded in USB/PDF. Stop.bat requests backend drain and stops the owned frontend and named Docker project without deleting data.'),
      ('Synthetic demonstration and History','Use the two Veeam files in Sample_Logs as a bundle, in English. Expected observed failure: a required file was not found; original reference 02_Task_long.log:1001. Cross-file association remains none. The smoke test checks real authenticated analysis and stored History. The Windows sample illustrates unclean restart uncertainty. Do not mix unrelated cases or import confidential customer data.'),
      ('Knowledge and optional components','Curated local diagnostic references remain available. ML runtimes/models and cloud keys are not included; external HTTP is blocked in the isolated launcher environment. Optional Vector RAG must report unavailable honestly. Full OCR execution requires separately approved Tesseract configuration. Grafana, Prometheus, Loki and PgBouncer are not started in the handover core; the application already supports direct PostgreSQL access.'),
      ('Services and private variables','Frontend: 127.0.0.1:13101; backend: 127.0.0.1:18101. PostgreSQL: 18543, EIMS_DB_PASSWORD; Redis: 16379 (isolated local project, no generated password because the existing client has no Redis password support); MinIO: 19000/19001, EIMS_MINIO_ACCESS_KEY and EIMS_MINIO_SECRET_KEY. Auth: EIMS_JWT_SECRET_KEY, EIMS_ADMIN_TOKEN, EIMS_ADMIN_PASSWORD. CORS permits only the isolated frontend. All listeners bind loopback. This is single-user local isolation, not multi-tenant hardening.'),
      ('Source and developer handover','Source_Code/EIMS_Source.zip is an explicit file-allowlist snapshot, not Git history. Tools/source-ledger.json records original hashes, packaged hashes and transformations, including known default removal, isolated frontend API URLs and a secure login adapter. Original working files and uncommitted progress are preserved. No .env, operational DB, runtime caches, customer logs, binaries or models are redistributed. Some legacy optional clients/operator integrations are deliberately excluded; see allowlist.'),
      ('Verification and common failures','Historical targeted Analyzer/provenance/History and TypeScript checks passed. Those checks do not prove a clean installation. Read Developer_Docs/ACCEPTANCE.md for the final measured SETUP, dependency installation, build and lifecycle outcomes. Clean Windows remains NOT TESTED unless a separate machine was actually used. Setup commands stop after a bounded timeout and retain private logs. Do not disable TLS or Windows security, reset data, or replace the frontend to work around installation failures. Missing runtime: ask IT for the pinned version. Occupied ports or missing credentials: preserve data and review private logs.'),
      ('Owner authorization and separate security states','Read OWNER_HANDOVER_AUTHORIZATION.txt for the explicit owner-granted internal permission to KANEMATSU ELECTRONICS (THAILAND) engineers. This records a statement, not independently verified ownership or a signed agreement. LICENSE is unchanged; third-party rights still apply. Transfer also requires an independent payload security PASS and operator confirmation. Historical deployment credentials have NOT been verified rotated. Production readiness and company IT installation approval are separate from source transfer.'),
      ('Next work and primary references','Test fresh Windows installation and authenticated UI/lifecycle acceptance; separately confirm deployment credential rotation and company IT policy; then arrange human task evaluation. Docker/WSL licensing policy and wheel/runtime compatibility on company hardware can be researched separately. References: https://docs.docker.com/desktop/setup/install/windows-install/ ; https://learn.microsoft.com/en-us/windows/package-manager/winget/ ; https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/robocopy ; https://nextjs.org/docs/app/api-reference/config/next-config-js/output . Standalone is not claimed: this release uses a normal production Next.js build.')]
    guide_pdf(PAYLOAD/'EIMS_Handover_Guide.pdf',sections)
    write(PAYLOAD/'Developer_Docs/DEVELOPMENT.md','''# Developer handover

Unzip Source_Code/EIMS_Source.zip to a new development directory, never an active database deployment. Read LICENSE/NOTICE before internal use or modification.

## Entry points and runtime
backend/main.py initializes PostgreSQL, Redis, MinIO health and worker lifecycles. backend/api/routers/analyzer contains analyze/history/auth; backend/domain/analyzer/services contains parsing, bundle provenance and curated knowledge. clients/dashboard is Next.js 16.3.0 / React 19.2.8. migrations contains Alembic history.

The guided package uses PostgreSQL directly (current application default); SQLite is only the existing protected synthetic test harness. Source families: Windows, Veeam VBR, selected Fortinet/Cisco ASA and known PAN-OS CSV families. USB Auditor collection/import is a separate workflow. Test fixtures are not customer records.

## Snapshot transformations
See Tools/source-ledger.json. Credentials were removed only from the release snapshot; live credentials/history are not changed. The packaged UI adds HandoverAuthGate for the existing secure JWT endpoint. Tokens remain in memory and are only attached to the configured API origin. Known historical development defaults are not usable in this snapshot. Private credentials are generated locally, not delivered.

## Rebuild and tests
Build tooling is in tools/handover. On the owner repository use bundled Python with reportlab: python tools/handover/build.py. The builder refuses an existing Payload; preserve/review old artifacts before a deliberate rebuild. It reads current files and records their hashes, not merely HEAD.

Run python -m pytest --noconftest tests/test_investigation_quality.py tests/test_history_sandbox.py tests/test_upload_security.py with appropriate local Python dependencies. Do not run legacy TestClient lifespans against workplace storage. Run npx tsc --noEmit and npm run build inside the extracted dashboard after npm ci. API integration must use disposable storage and the documented isolation checks. Do not repurpose history_sandbox as a production deployment.

requirements-handover.txt pins direct packages from the inspected environment. A full hash-locked cross-platform transitive dependency set has NOT been established. Revalidate installer availability and wheel resolution on a clean target. No native runtime/model redistribution is claimed.

## Next engineering work
Finish release lifecycle and secure browser acceptance on fresh Windows, investigate installer/version policy, confirm historical credential rotation and company IT installation approval. Confirm original-line provenance and uncertainty before expanding vendor coverage. Collect real human task results; do not invent them.
''')
    write(PAYLOAD/'Developer_Docs/AUTHORIZATION_AND_SECURITY.md',"""# Internal handover and deployment security

Owner authorization: see OWNER_HANDOVER_AUTHORIZATION.txt. Original LICENSE unchanged. Ownership is not independently verified; no signed company approval is claimed.

Internal transfer requires an independent review bound to the exact files, the unchanged owner statement and operator confirmation. Checksums alone do not establish security. The gate stays pending until the review passes.

Production: NOT APPROVED. Historical exposed credentials have NOT been verified rotated/revoked. The sanitized ZIP excludes Git history but does not repair existing deployments. Rotate affected credentials separately. Company IT must approve Docker licensing, Windows/WSL, dependency installations and data handling. No operational database or original environment is delivered.
""")
    write(PAYLOAD/'Developer_Docs/RESEARCH_FOR_CHATGPT.md','''# Bounded follow-up research (not a completed finding)

1. Ask company IT whether Docker Desktop subscription, supported Windows build, WSL/virtualization and package identities/versions are approved. Use official Docker and Microsoft documentation. Do not infer company approval from public documentation.
2. Verify winget availability for Python.Python.3.14 3.14.6, OpenJS.NodeJS 24.18.0 and Docker.DockerDesktop 4.85.0; if unavailable, choose an explicitly tested supported version rather than silently installing latest.
3. Create a hash-locked Windows x64 dependency set and assess licenses/SBOM for a distributable offline runtime. Current direct pins are not a complete transitive lock.
4. Assess a standalone Docker-free Analyzer only after removing reliance on test-only authentication overrides through a designed, reviewed product boundary. Do not call the existing synthetic sandbox portable.

For each return official source URL, applicable version, concrete decision, and a minimal verification procedure. Do not research unrelated architecture or invent approval, portability or usability results.
''')
    write(PAYLOAD/'Developer_Docs/ACCEPTANCE.md','''# Measured acceptance

Measured on the owner PC: 20 package/copy safety checks PASS; 54 targeted Analyzer tests PASS, including actual isolated SQLite persistence and file/line provenance. Existing dashboard TypeScript PASS; new secure login adapter TypeScript PASS. Host preflight PASS. Batch clone dry run PASS. Start-before-setup rejection PASS; Stop with absent installation is idempotent (two PASS runs). ZIP integrity / known-default / private-path screen PASS; manual privacy/security closure PENDING.

Fresh source extraction PASS. Online npm dependency installation did not complete within the bounded attempt; offline retry status is in owner verification records. Production build and human/browser login acceptance of the delivered layout are NOT VERIFIED. Full SETUP, live delivered services, and Stop/restart with real isolated services are NOT RUN. Existing sandbox tests are not evidence those lifecycle scripts work end to end.

Exact commands and logs are retained in owner staging BUILD_REPORT.txt and verification records. No Windows security setting was bypassed. No operational database was reset, stopped or migrated.

Default mode: guided Full EIMS core. Portable Analyzer: NOT VERIFIED. Clean Windows machine: NOT RUN. Actual USB transfer: NOT RUN / permission gate pending. No production deployment, customer logs or operational databases were used to create this package.

SETUP, Start and Stop must be evaluated separately from package integrity. READY is emitted only by the runtime after actual service health, secure auth, synthetic analysis, source line and saved History pass. A package hash PASS alone does not make the application ready.
''')
    refresh_manifest()
    (STAGE/'verification').mkdir(exist_ok=True)
    write(STAGE/'BUILD_REPORT.txt',f'Build completed: {datetime.now(timezone.utc).isoformat()}\nSource files: {len(members)}\nSource revision: {revision}\nStatic known-default removal and forbidden-key screen: PASS\nManual source/privacy/authorization review: PENDING\nMode: guided Full EIMS core; Portable NOT VERIFIED\nClean Windows: NOT RUN\nActual USB: NOT RUN (gate pending)\nFull SETUP/runtime lifecycle: see verification records; do not infer PASS from package build.\nFinal classification: STAGED - HANDOVER APPROVAL PENDING\n')
    print(json.dumps({'source_files':len(members),'payload':str(PAYLOAD),'mode':'GUIDED_FULL_EIMS_CORE','authorization':'PENDING','revision':revision}))

def refresh_manifest():
    rows=[]
    for p in sorted(PAYLOAD.rglob('*')):
        if p.is_file() and p.relative_to(PAYLOAD).as_posix() not in {'MANIFEST.txt','SHA256SUMS.txt'}:
            raw=p.read_bytes();rows.append({'path':p.relative_to(PAYLOAD).as_posix(),'size':len(raw),'sha256':digest(raw)})
    write(PAYLOAD/'MANIFEST.txt',json.dumps({'format':'eims-handover-v1','files':rows},indent=2)+'\n')
    lines=[r['sha256']+'  '+r['path'] for r in rows]
    lines.append(digest((PAYLOAD/'MANIFEST.txt').read_bytes())+'  MANIFEST.txt')
    write(PAYLOAD/'SHA256SUMS.txt','\n'.join(lines)+'\n')

if __name__=='__main__':
    if '--refresh-manifest' in sys.argv:refresh_manifest()
    else:build()
