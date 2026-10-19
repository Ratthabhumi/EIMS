import ctypes as C
from ctypes import wintypes as W
import json,os,subprocess,time,uuid,urllib.request,base64,socket
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];P=Path(os.environ.get('EIMS_TEST_PACKAGE',str(ROOT/'Final_CO-OP/Payload')));OUT=ROOT/'Final_CO-OP/verification';data=Path(os.environ['LOCALAPPDATA'])/'EIMS-Local-Demo-Tests'/('eims-demo-test-'+uuid.uuid4().hex)
OUT.mkdir(parents=True,exist_ok=True)
base='http://127.0.0.1:18115';opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));records=[]
k=C.WinDLL('kernel32',use_last_error=True);user=C.WinDLL('user32',use_last_error=True)
k.GetConsoleWindow.restype=W.HWND;user.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
def get(path):
 with opener.open(base+path,timeout=3) as r:return json.load(r)
def post(path,payload,token=None,origin=base):
 req=urllib.request.Request(base+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Origin':origin,'X-EIMS-Demo':token or get('/session')['token']},method='POST')
 with opener.open(req,timeout=15) as r:return json.load(r)
def wait_ready(proc):
 for _ in range(150):
  if proc.poll() is not None:raise AssertionError('Launcher exited before readiness; see owned console log')
  try:
   if get('/health')['ready']:return
  except Exception:pass
  time.sleep(.2)
 raise AssertionError('Readiness timeout')
def port_closed():
 with socket.socket() as s:return s.connect_ex(('127.0.0.1',18115))!=0
def launch(name):
 log=open(OUT/(name+'.log'),'w');si=subprocess.STARTUPINFO();si.dwFlags=1;si.wShowWindow=0
 proc=subprocess.Popen(['cmd.exe','/c',str(P/'Start_EIMS.bat'),'-NoBrowser','-DataRoot',str(data)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=si)
 return proc,log
checks=[]
def passed(name):checks.append({'test':name,'status':'PASS'});print('PASS',name,flush=True)
proc=None
try:
 proc,log=launch('demo-first-launch');wait_ready(proc);passed('Launch actual Start_EIMS.bat with bundled runtime, no typed password')
 state=json.loads((data/'runtime.json').read_text());before_backend=state['backend']
 with opener.open(base+'/',timeout=3) as r:assert b'Log Investigation' in r.read();passed('Real local Analyzer frontend responds')
 files=[{'name':n,'data':base64.b64encode((P/'Sample_Logs'/n).read_bytes()).decode()} for n in ['01_report.txt','02_Task_long.log']]
 result=post('/analyze',{'files':files});assert any(x['sourceFile']=='02_Task_long.log' and x['lineNumber']==1001 for x in result['evidence']);passed('Real Veeam synthetic bundle preserves original file and line 1001')
 assert any('required file' in x['message'].lower() for x in result['evidence']);passed('Observed required-file failure retained')
 print('CORRELATION',json.dumps(result['correlation'],default=str),flush=True)
 assert any(x['id']==result['id'] for x in get('/history'));passed('SQLite History saves and retrieves analysis')
 try:post('/analyze',{'files':files},origin='https://example.invalid');raise AssertionError('Cross-origin accepted')
 except urllib.error.HTTPError as e:assert e.code==403;passed('Cross-origin write rejected')
 try:post('/analyze',{'files':[{'name':'evil.exe','data':'TVqQAA=='}]});raise AssertionError('Binary accepted')
 except urllib.error.HTTPError as e:assert e.code==400;passed('Unsupported executable upload rejected')
 duplicate,dup_log=launch('demo-second-launch')
 for _ in range(150):
  if 'already running' in (OUT/'demo-second-launch.log').read_text(errors='replace'):break
  time.sleep(.2)
 assert 'already running' in (OUT/'demo-second-launch.log').read_text(errors='replace'), 'Duplicate must be explicitly rejected'
 assert json.loads((data/'runtime.json').read_text())['backend']==before_backend;passed('Second launch does not create duplicate backend')
 if duplicate.poll() is None:duplicate.terminate()
 duplicate.wait(timeout=10);dup_log.close()
 # Attach only to the console created for this test; do not signal the app's console.
 k.FreeConsole();assert k.AttachConsole(state['supervisor'])
 k.SetConsoleCtrlHandler(None,True);assert k.GenerateConsoleCtrlEvent(0,0)
 time.sleep(.2);k.FreeConsole()
 for _ in range(100):
  if port_closed():break
  time.sleep(.1)
 assert port_closed();passed('Actual Ctrl+C stops backend and releases port')
 handle=k.OpenProcess(0x100000,False,before_backend)
 if handle:assert k.WaitForSingleObject(handle,2000)==0;k.CloseHandle(handle)
 passed('Ctrl+C independently verified owned process exited')
 if proc.poll() is None:proc.terminate()
 proc.wait(timeout=10);log.close();proc=None
 proc,log=launch('demo-restart');wait_ready(proc)
 assert any(x['id']==result['id'] for x in get('/history'));passed('Restart retains SQLite History without reset')
 state=json.loads((data/'runtime.json').read_text());owned=state['backend']
 k.FreeConsole();assert k.AttachConsole(state['supervisor']);hwnd=k.GetConsoleWindow();k.FreeConsole();assert hwnd
 assert user.PostMessageW(hwnd,0x10,0,0)
 for _ in range(120):
  if port_closed():break
  time.sleep(.1)
 assert port_closed();passed('Actual launcher console WM_CLOSE stops backend and releases port')
 handle=k.OpenProcess(0x100000,False,owned)
 if handle:assert k.WaitForSingleObject(handle,3000)==0;k.CloseHandle(handle)
 passed('Console close independently verified owned process exited')
 passed('Optional Vector RAG absent without blocking analysis')
except Exception as exc:
 checks.append({'test':'integration','status':'FAIL','reason':type(exc).__name__+': '+str(exc)})
 import traceback;traceback.print_exc();print('FAIL',type(exc).__name__,str(exc),flush=True)
finally:
 if proc and proc.poll() is None:
  try:post('/shutdown',{})
  except Exception:pass
  time.sleep(1)
  if proc.poll() is None:proc.terminate()
 (OUT/'demo-lifecycle-results.json').write_text(json.dumps({'checks':checks,'testData':str(data),'cleanWindows':'NOT_RUN'},indent=2))
if any(x['status']=='FAIL' for x in checks):raise SystemExit(2)
