"""Real authenticated HTTP smoke. Output contains no passwords/tokens/raw logs."""
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
import uuid

base = 'http://127.0.0.1:18101'
payload = Path(sys.argv[1])

def request(path, data=None, headers=None):
    req = urllib.request.Request(base + path, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.load(response)

try:
    request('/api/v1/history/')
except urllib.error.HTTPError as error:
    assert error.code == 401
else:
    raise AssertionError('Unauthenticated history access must be denied')
token = request('/api/v1/auth/login', json.dumps({'username':'admin','password':os.environ['EIMS_ADMIN_PASSWORD']}).encode(), {'Content-Type':'application/json'})['access_token']
auth = {'Authorization': 'Bearer ' + token}
# Repeat launches verify existing history instead of creating duplicate records.
rows = request('/api/v1/history/', headers=auth)
match = next((row for row in rows if row.get('eventId') == 'VEEAM-REPLICA-SNAPSHOT-CHAIN'), None)
if match is None:
    boundary = 'eims' + uuid.uuid4().hex
    parts=[]
    for name in ['01_report.txt','02_Task_long.log']:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{name}"\r\nContent-Type: text/plain\r\n\r\n'.encode() + (payload/'Sample_Logs'/name).read_bytes()+b'\r\n')
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="language"\r\n\r\nen\r\n--{boundary}--\r\n'.encode())
    result = request('/api/v1/analyze/bundle', b''.join(parts), {**auth,'Content-Type':'multipart/form-data; boundary='+boundary})
    assert result['correlationConfidence'] == 'none'
    rows = request('/api/v1/history/', headers=auth)
    match = next(row for row in rows if row['id']==result['historyId'])
assert match['correlationConfidence'] == 'none'
assert any(i['sourceFile']=='02_Task_long.log' and i['lineNumber']==1001 for i in match['solutionSummary']['evidenceItems'])
assert 'required file' in json.dumps(match['solutionSummary']).lower()
print('PASS: secure auth, actual synthetic analysis, original line 1001, persisted History. Root cause remains unconfirmed.')
