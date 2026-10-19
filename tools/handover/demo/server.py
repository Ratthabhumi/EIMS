"""Local-only evaluation adapter over EIMS pure parsers; no operational app/auth."""
import base64
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import TCPServer

PORT = 18115
ORIGIN = f'http://127.0.0.1:{PORT}'
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'App'))
from backend.domain.analyzer.services.parser import parse_event_metadata
from backend.domain.analyzer.services.bundle import validate_bundle, summarize_file_evidence, build_evidence_items, correlate_bundle
from backend.domain.analyzer.services.operational_catalog import entry_for_metadata
from backend.domain.analyzer.services.investigation import windows_investigation

DATA = Path(sys.argv[1])
TOKEN = os.environ['EIMS_DEMO_TOKEN']
DB = DATA / 'history.sqlite3'

def connection():
    return sqlite3.connect(DB, timeout=5)

def initialize():
    with connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, result TEXT NOT NULL)')

def analyze(files):
    if not isinstance(files, list) or not 1 <= len(files) <= 12:
        raise ValueError('Choose 1-12 UTF-8 text log files.')
    raw=[]
    for f in files:
        if not isinstance(f, dict) or not isinstance(f.get('data'), str) or len(f['data']) > 7_000_000:
            raise ValueError('Invalid or oversized upload.')
        name=f.get('name','')
        if not isinstance(name,str) or Path(name).suffix.lower() not in {'.txt','.log','.csv','.json'}:
            raise ValueError('Demo supports .txt, .log, .csv and .json UTF-8 text only. No EVTX, image or archive.')
        raw.append((name,base64.b64decode(f['data'],validate=True)))
    evidence=[]; metadata=[]; guidance=[]
    for name, content in validate_bundle(raw):
        text=content.decode('utf-8-sig')
        meta=parse_event_metadata(text,name)
        metadata.append(meta.model_dump(mode='json'))
        evidence.append(summarize_file_evidence(name,content,text,meta.sourceFamily or '',meta.product or '',meta.diagnosticCode or '',float(meta.parserConfidence or 0)))
        entry=entry_for_metadata(meta)
        # Catalog guidance is labeled as a reference, never an observed cause.
        if entry:
            guidance.append({'file':name,'title':entry.get('title',''),'description':entry.get('description',''), 'nextChecks':entry.get('investigation_steps',[]),'references':entry.get('official_references',[])})
        if meta.sourceFamily=='windows_event':
            note=windows_investigation(meta.eventId,meta.provider,text,'en')
            if note:guidance.append({'file':name,'windowsInvestigation':note.model_dump(mode='json')})
    return {'metadata':metadata,'evidence':build_evidence_items(evidence),'correlation':correlate_bundle(evidence),'guidance':guidance,
            'limitations':['Local evaluation adapter using real EIMS parsers, evidence extraction and static catalog. Not the full dashboard or full summary pipeline.','Parser match and cross-file association do not establish a root cause.','No cloud AI, web search, Vector RAG, OCR, EVTX, admin endpoints or company databases.','Use synthetic examples or files you are authorized to inspect; results remain on this PC.']}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass  # Uploaded content/tokens must not enter logs.
    def send(self,status,obj,html=False):
        body=obj if html else json.dumps(obj,ensure_ascii=False,default=str).encode()
        self.send_response(status)
        self.send_header('Content-Type','text/html; charset=utf-8' if html else 'application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers();self.wfile.write(body)
    def trusted_host(self):return self.headers.get('Host')==f'127.0.0.1:{PORT}'
    def do_GET(self):
        if not self.trusted_host():return self.send(403,{'error':'Local host required.'})
        if self.path=='/':return self.send(200,(ROOT/'index.html').read_bytes(),True)
        if self.path=='/health':return self.send(200,{'mode':'local-analyzer-demo','ready':True,'externalNetwork':'disabled','vectorRag':'not included'})
        if self.path=='/session':return self.send(200,{'token':TOKEN})
        if self.path=='/history':
            with connection() as db:rows=[json.loads(r[0]) for r in db.execute('SELECT result FROM history ORDER BY id DESC LIMIT 100')]
            return self.send(200,rows)
        self.send(404,{'error':'Not available in this demo.'})
    def do_POST(self):
        if not self.trusted_host() or self.headers.get('Origin')!=ORIGIN or not secrets.compare_digest(self.headers.get('X-EIMS-Demo',''),TOKEN):
            return self.send(403,{'error':'Same-origin demo session required.'})
        if self.headers.get('Transfer-Encoding') or not self.headers.get('Content-Length','').isdigit():return self.send(400,{'error':'Bounded content length required.'})
        size=int(self.headers['Content-Length'])
        if size>43_000_000:return self.send(413,{'error':'Request exceeds demo upload limit.'})
        if self.path=='/shutdown':
            self.send(200,{'stopping':True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
        if self.path!='/analyze':return self.send(404,{'error':'Not available in this demo.'})
        try:
            payload=json.loads(self.rfile.read(size));result=analyze(payload['files'])
            with connection() as db:
                row=db.execute('INSERT INTO history(result) VALUES (?)',(json.dumps(result,default=str),))
                result['id']=row.lastrowid
                db.execute('UPDATE history SET result=? WHERE id=?',(json.dumps(result,default=str),result['id']))
            self.send(200,result)
        except (ValueError,KeyError,TypeError,UnicodeError):self.send(400,{'error':'Invalid input. Use bounded UTF-8 text logs and supported filenames.'})
        except Exception:self.send(500,{'error':'Local analysis failed; no raw log or credential was printed.'})

def network_guard(event,args):
    if event in {'socket.connect','socket.getaddrinfo','socket.gethostbyaddr','socket.gethostbyname','socket.gethostbyname_ex','socket.sendto'}:raise RuntimeError('External/network clients are disabled in the demo server.')
    if event=='socket.bind' and args[1]!=( '127.0.0.1',PORT):raise RuntimeError('Only the declared loopback listener is permitted.')

class LocalServer(ThreadingHTTPServer):
    def server_bind(self):
        # HTTPServer normally reverse-resolves its listener name. This demo
        # already knows the loopback identity and must not perform DNS.
        TCPServer.server_bind(self)
        self.server_name='127.0.0.1';self.server_port=PORT

if __name__=='__main__':
    sys.stderr=open(DATA/'demo-server.log','a',encoding='utf-8',buffering=1)
    sys.addaudithook(network_guard)
    initialize()
    server=LocalServer(('127.0.0.1',PORT),Handler)
    server.timeout=2
    try:server.serve_forever(poll_interval=.2)
    finally:server.server_close()
