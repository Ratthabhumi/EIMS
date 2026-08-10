import requests
import json
import os

BASE_URL = "http://localhost:8000/api/v1"

# We will test against local server, or fly.io server
# Let's use the local script but hit the fly.io server just to be sure.
BASE_URL = "https://log-analyst-bymew.fly.dev/api/v1"

xml_content = """<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
  <System>
    <Provider Name="Application Error" Guid="{a0e9b465-b939-57d7-b27d-95d8e925ff57}" />
    <EventID>1000</EventID>
    <Version>0</Version>
    <Level>2</Level>
    <Task>100</Task>
    <Opcode>0</Opcode>
    <Keywords>0x8000000000000000</Keywords>
    <TimeCreated SystemTime="2026-04-14T17:18:52.0608748Z" />
    <EventRecordID>27657</EventRecordID>
    <Correlation />
    <Execution ProcessID="12220" ThreadID="12224" />
    <Channel>Application</Channel>
    <Computer>Mew</Computer>
    <Security UserID="S-1-5-18" />
  </System>
  <EventData>
    <Data Name="AppName">AcerQAAgent.exe</Data>
    <Data Name="AppVersion">1.5.24.0</Data>
    <Data Name="ExceptionCode">c0000005</Data>
  </EventData>
</Event>"""

with open("test.xml", "w") as f:
    f.write(xml_content)

try:
    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": "admin", "password": "P@ssw0rd"}
    )
    token = login_response.json().get("access_token")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    with open("test.xml", "rb") as f:
        files = {"file": ("test.xml", f, "application/xml")}
        data = {"language": "th"}
        
        response = requests.post(
            f"{BASE_URL}/analyze/",
            files=files,
            data=data,
            headers=headers
        )
        
        print("Status Code:", response.status_code)
        print("Response:", json.dumps(response.json(), indent=2))
        
except Exception as e:
    print("Error:", e)
