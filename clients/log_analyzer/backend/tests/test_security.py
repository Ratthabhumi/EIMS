import os
import requests
import json
import io

BASE_URL = "http://localhost:8001/api/v1"

# We'll test against the local server to see if it handles the vulnerabilities safely.

def test_large_file_upload(token):
    print("\n--- Testing Large File Upload (Memory Exhaustion) ---")
    # Generate a dummy 6MB file in memory (assuming limit is 5MB)
    large_content = b"x" * (6 * 1024 * 1024)
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("large_file.evtx", io.BytesIO(large_content), "application/octet-stream")}
    
    try:
        response = requests.post(f"{BASE_URL}/analyze/", files=files, headers=headers)
        print("Status Code:", response.status_code)
        resp_json = response.json() if response.status_code == 200 else {}
        if response.status_code == 413 or (response.status_code == 200 and "too large" in str(resp_json.get("description", "")).lower()):
            print("[PASS] Server rejected the large file as expected.")
        else:
            print("[FAIL] Server accepted the large file or returned unexpected status.")
    except Exception as e:
        print("[FAIL] Exception:", e)

def test_xml_billion_laughs(token):
    print("\n--- Testing XML Billion Laughs (XXE DoS) ---")
    # A classic billion laughs payload
    xml_payload = """<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ELEMENT lolz (#PCDATA)>
 <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
 <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
 <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
]>
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
  <System>
    <Provider Name="Application Error" />
    <EventID>&lol4;</EventID>
  </System>
</Event>"""
    
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("malicious.xml", io.BytesIO(xml_payload.encode()), "application/xml")}
    
    try:
        response = requests.post(f"{BASE_URL}/analyze/", files=files, headers=headers)
        print("Status Code:", response.status_code)
        # defusedxml should raise an exception causing a 400 or a controlled error, not hang or OOM.
        print("[INFO] Response Text:", response.text[:200])
        print("[PASS] System did not crash (if it crashed, we wouldn't see this).")
    except requests.exceptions.ConnectionError:
        print("[FAIL] Server crashed or dropped connection due to DoS!")
    except Exception as e:
        print("[FAIL] Exception:", e)

def test_large_text_input(token):
    print("\n--- Testing Large Text Input (DB Bloat) ---")
    large_text = "Event ID: 1000\n" + "A" * 60000
    headers = {"Authorization": f"Bearer {token}"}
    data = {"text": large_text, "language": "th"}
    
    try:
        response = requests.post(f"{BASE_URL}/analyze/", data=data, headers=headers)
        print("Status Code:", response.status_code)
        if response.status_code == 200:
            resp_json = response.json()
            description = resp_json.get("description", "")
            if len(description) < 55000:
                print(f"[PASS] Text was truncated. Length: {len(description)}")
            else:
                print(f"[FAIL] Text was NOT truncated! Length: {len(description)}")
        else:
            print("[FAIL] Unexpected status code.")
    except Exception as e:
        print("[FAIL] Exception:", e)

if __name__ == "__main__":
    try:
        login = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "P@ssw0rd"})
        if login.status_code != 200:
            print("Failed to login. Start local server.")
            exit(1)
        token = login.json().get("access_token")
        
        test_large_file_upload(token)
        test_xml_billion_laughs(token)
        test_large_text_input(token)
        
    except Exception as e:
        print("Could not connect to server. Is it running locally?", e)
