"""Handover-only Windows ACL/session proof, single-use 60s grant, 15min JWT.
The protected signing key never travels to USB, HTML, browser storage or URLs.
The one-use proof uses a URL fragment, scrubbed before exchange; never HTTP logs.
"""
import base64, ctypes, hashlib, hmac, json, os, secrets, sys, threading, time, webbrowser
from pathlib import Path

ORIGIN = 'http://127.0.0.1:13101'


def windows_identity(app):
    sys.path.insert(0, str(app))
    from clients.usb_auditor.portable_entry import current_sid, verify_private_acl
    session = ctypes.c_ulong()
    if not ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session)):
        raise PermissionError('Cannot verify Windows session')
    return current_sid(), session.value, verify_private_acl


def proof(context, now=None):
    now = int(time.time()) if now is None else now
    data = dict(server=context['server'],sid=context['sid'],logon=context['logon'],
        nonce=secrets.token_hex(24),issued=now,until=now+60)
    body = base64.urlsafe_b64encode(json.dumps(data,separators=(',',':')).encode()).decode().rstrip('=')
    return body + '.' + hmac.new(bytes.fromhex(context['key']),body.encode(),hashlib.sha256).hexdigest()


class Broker:
    def __init__(self, context):
        self.context, self.used, self.lock = context, {}, threading.Lock()

    def consume(self, value, origin, now=None):
        now = int(time.time()) if now is None else now
        if origin != ORIGIN or not isinstance(value,str) or len(value)>1024:
            raise PermissionError('Invalid local session proof')
        try:
            body, signature = value.split('.')
            expected = hmac.new(bytes.fromhex(self.context['key']),body.encode(),hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature,expected):raise ValueError()
            data = json.loads(base64.urlsafe_b64decode(body+'='*(-len(body)%4)))
            if any(data[k]!=self.context[k] for k in ('server','sid','logon')):raise ValueError()
            if not (0<=now-data['issued']<=60 and now<data['until']<=data['issued']+60):raise ValueError()
            with self.lock:
                self.used={k:v for k,v in self.used.items() if v>now}
                if data['nonce'] in self.used or len(self.used)>=4096:raise ValueError()
                self.used[data['nonce']]=data['until']
        except (ValueError,KeyError,TypeError):
            raise PermissionError('Expired or invalid local session proof') from None


def attach(application, app, private):
    from fastapi import Request, HTTPException
    from fastapi.responses import JSONResponse
    from backend.domain.analyzer import auth
    import jwt
    if auth.AUTH_MODE!='secure':raise PermissionError('Local handover requires secure authentication')
    sid,logon,verify_acl=windows_identity(app);verify_acl(private)
    if json.loads((private/'local-session-enabled.json').read_text('utf-8-sig'))!={'sid':sid,'logon':logon}:
        raise PermissionError('Local launcher Windows identity mismatch')
    context=dict(sid=sid,logon=logon,server=secrets.token_hex(24),key=secrets.token_hex(32))
    target=private/'browser-session.json'
    if target.is_symlink() or target.is_junction():raise PermissionError('Linked session file')
    from clients.usb_auditor.portable_entry import protect_new_directory
    target.touch(exist_ok=True)
    protect_new_directory(target)
    verify_acl(target)
    target.write_text(json.dumps(context),encoding='utf-8')
    broker=Broker(context)

    @application.post('/api/v1/handover/session',include_in_schema=False)
    async def local_session(request: Request):
        try:
            raw=b''
            async for chunk in request.stream():
                raw+=chunk
                if len(raw)>2048:raise PermissionError()
            body=json.loads(raw)
            if not isinstance(body,dict):raise PermissionError()
            broker.consume(body.get('proof'),request.headers.get('origin'))
            username=await auth.verify_credentials('admin',os.environ['EIMS_ADMIN_PASSWORD'])
            if username is None:raise PermissionError()
            token=jwt.encode(dict(sub=username,role=await auth.get_user_role(username),exp=int(time.time())+900),
                auth.SECRET_KEY,algorithm=auth.ALGORITHM)
            return JSONResponse(dict(access_token=token,expires_in=900),headers={'Cache-Control':'no-store','Pragma':'no-cache'})
        except (PermissionError,ValueError,KeyError,TypeError):
            raise HTTPException(401,'Open EIMS with Start.bat from the authorized Windows session') from None


def launch(app, private):
    sid,logon,verify_acl=windows_identity(app);verify_acl(private)
    verify_acl(private/'browser-session.json')
    context=json.loads((private/'browser-session.json').read_text())
    if context['sid']!=sid or context['logon']!=logon:raise PermissionError('Use the Windows user/session that started EIMS')
    if not webbrowser.open(ORIGIN+'/analyzer#eims-bootstrap='+proof(context)):
        raise RuntimeError('Browser could not open; rerun Start.bat')


if __name__=='__main__':
    if sys.argv[1]!='launch':raise SystemExit('Expected launch')
    launch(Path(sys.argv[2]),Path(sys.argv[3]))
