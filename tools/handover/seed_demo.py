"""Populate only a new, explicitly demo-only handover through authenticated APIs."""
import json, os, sys, uuid
from pathlib import Path
import urllib.request


def seed(payload, private):
    package=json.loads((payload/'Tools/package.json').read_text())
    if package.get('demoOnly') is not True:raise ValueError('Not a demo-only package')
    api='http://127.0.0.1:18101'
    def req(path,data=None,headers=None):
        with urllib.request.urlopen(urllib.request.Request(api+path,data=data,headers=headers or {}),timeout=90) as response:
            return json.load(response)
    token=req('/api/v1/auth/login',json.dumps({'username':'admin','password':os.environ['EIMS_ADMIN_PASSWORD']}).encode(),
        {'Content-Type':'application/json'})['access_token']
    headers={'Authorization':'Bearer '+token}
    assets=req('/api/v1/assets?page_size=100',headers=headers)['data']
    if any(a.get('offline_report_data',{}).get('classification')!='SYNTHETIC_DEMO' for a in assets):
        raise ValueError('Existing non-demo asset found; no seeding or deletion performed')
    expected={'PC-DEMO-001','PC-DEMO-002','SRV-DEMO-001'}
    present={a['hostname'] for a in assets}
    for file in sorted((payload/'Demo/Reports').glob('*.json')):
        data=json.loads(file.read_text())
        if data['classification']!='SYNTHETIC_DEMO' or data['system']['computer_name'] not in expected:
            raise ValueError('Unapproved demo fixture')
        if data['system']['computer_name'] in present:continue
        boundary='demo'+uuid.uuid4().hex
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{file.name}"\r\nContent-Type: application/json\r\n\r\n').encode()+file.read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
        result=req('/api/v1/assets/import-report',body,{**headers,'Content-Type':'multipart/form-data; boundary='+boundary})
        if not result.get('event_ingestion',{}).get('events_new'):raise ValueError('Demo events did not import')
    assets=req('/api/v1/assets?page_size=100',headers=headers)['data']
    if {a['hostname'] for a in assets}!=expected:raise ValueError('Demo asset inventory mismatch')
    (private/'demo-seed-complete.json').write_text(json.dumps({'classification':'SYNTHETIC_DEMO','assets':3}))
    print('SYNTHETIC_DEMO: three fictional assets with event evidence are ready.')


if __name__=='__main__':seed(Path(sys.argv[1]),Path(sys.argv[2]))
