"""Windows-owned local demo process tree; kill-on-close Job Object."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request

ROOT=Path(__file__).resolve().parent
PORT=18115
URL=f'http://127.0.0.1:{PORT}'
k=C.WinDLL('kernel32',use_last_error=True)
SIZE=C.c_size_t
class Basic(C.Structure):
    _fields_=[('processTime',C.c_int64),('jobTime',C.c_int64),('flags',W.DWORD),('minWorking',SIZE),('maxWorking',SIZE),('active',W.DWORD),('affinity',SIZE),('priority',W.DWORD),('scheduling',W.DWORD)]
class IO(C.Structure):_fields_=[(name,C.c_uint64) for name in ['readOps','writeOps','otherOps','readBytes','writeBytes','otherBytes']]
class Extended(C.Structure):_fields_=[('basic',Basic),('io',IO),('processMemory',SIZE),('jobMemory',SIZE),('peakProcessMemory',SIZE),('peakJobMemory',SIZE)]
class Startup(C.Structure):
    _fields_=[('cb',W.DWORD),('reserved',W.LPWSTR),('desktop',W.LPWSTR),('title',W.LPWSTR),('x',W.DWORD),('y',W.DWORD),('xsize',W.DWORD),('ysize',W.DWORD),('xchars',W.DWORD),('ychars',W.DWORD),('fill',W.DWORD),('flags',W.DWORD),('show',W.WORD),('reservedSize',W.WORD),('reservedBytes',C.POINTER(C.c_byte)),('stdin',W.HANDLE),('stdout',W.HANDLE),('stderr',W.HANDLE)]
class Process(C.Structure):_fields_=[('process',W.HANDLE),('thread',W.HANDLE),('pid',W.DWORD),('tid',W.DWORD)]
def api(name,restype,args):
    f=getattr(k,name);f.restype=restype;f.argtypes=args;return f
create_job=api('CreateJobObjectW',W.HANDLE,[C.c_void_p,W.LPCWSTR])
set_job=api('SetInformationJobObject',W.BOOL,[W.HANDLE,C.c_int,C.c_void_p,W.DWORD])
assign=api('AssignProcessToJobObject',W.BOOL,[W.HANDLE,W.HANDLE])
close=api('CloseHandle',W.BOOL,[W.HANDLE])
wait=api('WaitForSingleObject',W.DWORD,[W.HANDLE,W.DWORD])
resume=api('ResumeThread',W.DWORD,[W.HANDLE])
terminate=api('TerminateProcess',W.BOOL,[W.HANDLE,W.UINT])
create=api('CreateProcessW',W.BOOL,[W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,C.c_void_p,W.LPCWSTR,C.POINTER(Startup),C.POINTER(Process)])
mutex_api=api('CreateMutexW',W.HANDLE,[C.c_void_p,W.BOOL,W.LPCWSTR])
release_mutex=api('ReleaseMutex',W.BOOL,[W.HANDLE])
HANDLER=C.WINFUNCTYPE(W.BOOL,W.DWORD)
set_handler=api('SetConsoleCtrlHandler',W.BOOL,[HANDLER,W.BOOL])

def checked(value):
    if not value:raise C.WinError(C.get_last_error())
    return value

def verify_package():
    package=ROOT.parent
    manifest=json.loads((package/'MANIFEST.txt').read_text(encoding='utf-8-sig'))
    expected={'MANIFEST.txt','SHA256SUMS.txt'}
    for entry in manifest['files']:
        rel=entry['path'];p=package/rel
        if '\\' in rel or ':' in rel or '..' in Path(rel).parts or Path(rel).is_absolute() or rel in expected:raise RuntimeError('Unsafe manifest path.')
        expected.add(rel)
        if p.is_symlink() or not p.is_file() or p.stat().st_size!=entry['size'] or hashlib.sha256(p.read_bytes()).hexdigest()!=entry['sha256']:raise RuntimeError('Package integrity failed: '+rel)
    actual={p.relative_to(package).as_posix() for p in package.rglob('*') if p.is_file()}
    if actual!=expected:raise RuntimeError('Unexpected or missing package files.')
    if any(p.is_symlink() or p.is_junction() for p in package.rglob('*')):raise RuntimeError('Package links are not permitted.')
    gate=json.loads((package/'Tools/release-gate.json').read_text())
    receipt=json.loads((package/'Tools/security-review.json').read_text())
    if gate.get('status')!='OWNER_AUTHORIZED_INTERNAL' or gate.get('securityReview')!='PASS' or receipt.get('status')!='PASS' or not receipt.get('reviewedAt') or not receipt.get('reviewedBy'):raise RuntimeError('Owner authorization or independent payload security review is incomplete.')
    if hashlib.sha256((package/'OWNER_HANDOVER_AUTHORIZATION.txt').read_bytes()).hexdigest()!=gate.get('ownerAuthorizationSha256'):raise RuntimeError('Owner authorization changed since review.')
    reviewed={r['path']:r['sha256'] for r in receipt['files']}
    covered={r['path']:r['sha256'] for r in manifest['files'] if r['path'] not in {'Tools/security-review.json','Tools/release-gate.json'}}
    if len(reviewed)!=len(receipt['files']) or reviewed!=covered:raise RuntimeError('Payload changed since independent security review.')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--no-browser','-NoBrowser',action='store_true');parser.add_argument('--data-root','-DataRoot',type=Path)
    args=parser.parse_args()
    if os.name!='nt' or C.sizeof(C.c_void_p)!=8:raise RuntimeError('Windows x64 is required. Ask IT if this executable is blocked.')
    verify_package();print('[OK] Demo files found',flush=True)
    base=Path(os.environ['LOCALAPPDATA'])
    data=args.data_root or base/'EIMS-Local-Demo'
    if args.data_root and (data.parent!=base/'EIMS-Local-Demo-Tests' or not data.name.startswith('eims-demo-test-')):raise RuntimeError('Test data must use the dedicated local demo test directory.')
    mutex=checked(mutex_api(None,True,'Local\\EIMSLocalDemo-'+hashlib.sha256(str(data.absolute()).lower().encode()).hexdigest()[:20]))
    if C.get_last_error()==183:
        close(mutex);raise RuntimeError('EIMS demo is already running. Use its launcher window; no duplicate was started.')
    job=None;child=Process();stopping=threading.Event();token=secrets.token_hex(32)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def stop_gracefully():
        stopping.set()
        try:
            request=urllib.request.Request(URL+'/shutdown',data=b'',headers={'Origin':URL,'X-EIMS-Demo':token},method='POST')
            opener.open(request,timeout=2).close()
        except Exception:pass
    @HANDLER
    def console_event(event):
        nonlocal job
        if event in (0,1):stopping.set();return True
        if event in (2,5,6):
            stop_gracefully()
            if child.process:wait(child.process,2000)
            if job:
                owned=job;job=None;close(owned)
            return True
        return False
    try:
        if data.exists():
            if data.is_symlink() or not (data/'identity.json').is_file() or json.loads((data/'identity.json').read_text())!={'purpose':'eims-local-demo','schema':1}:raise RuntimeError('Unrecognized local data. Nothing was overwritten.')
        else:
            data.mkdir(parents=True);(data/'identity.json').write_text(json.dumps({'purpose':'eims-local-demo','schema':1}))
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',PORT))
        job=checked(create_job(None,None));info=Extended();info.basic.flags=0x2000
        checked(set_job(job,9,C.byref(info),C.sizeof(info)))
        checked(set_handler(console_event,True))
        os.environ['EIMS_DEMO_TOKEN']=token
        si=Startup();si.cb=C.sizeof(si);si.flags=1;si.show=0
        command=C.create_unicode_buffer(subprocess.list2cmdline([sys.executable,'-B',str(ROOT/'server.py'),str(data)]))
        checked(create(sys.executable,command,None,None,False,0x4|0x200,None,str(ROOT),C.byref(si),C.byref(child)))
        if not assign(job,child.process):
            terminate(child.process,2);raise C.WinError(C.get_last_error())
        resume(child.thread);close(child.thread)
        (data/'runtime.json').write_text(json.dumps({'supervisor':os.getpid(),'backend':child.pid,'port':PORT}))
        ready=False
        for _ in range(150):
            if stopping.is_set() or wait(child.process,0)==0:break
            try:
                with opener.open(URL+'/health',timeout=1) as response:ready=json.load(response).get('mode')=='local-analyzer-demo'
            except Exception:pass
            if ready:break
            time.sleep(.2)
        if not ready:raise RuntimeError('Demo did not become ready. Review local demo logs or ask IT; no system setting was changed.')
        print('[OK] Local backend ready\n[OK] Web interface ready\n\nEIMS is running.\nPress Ctrl+C to stop EIMS. You may also close this window.',flush=True)
        if not args.no_browser:os.startfile(URL)
        while not stopping.wait(.2):
            if wait(child.process,0)==0:raise RuntimeError('Demo backend stopped unexpectedly.')
        stop_gracefully();wait(child.process,7000)
        print('EIMS stopped. Local History is preserved.',flush=True)
    finally:
        if job:close(job)
        if child.process:wait(child.process,5000);close(child.process)
        release_mutex(mutex);close(mutex)
    return 0

if __name__=='__main__':
    print('====================================\n EIMS - LOCAL DEMO\n====================================',flush=True)
    try:sys.exit(main())
    except Exception as exc:print('[STOP] '+str(exc)+'\nAsk company IT if execution is blocked; do not bypass Windows protection.',flush=True);sys.exit(2)
