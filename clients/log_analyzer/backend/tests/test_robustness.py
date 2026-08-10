import requests
import time
import os
import io

BASE_URL = "https://log-analyst-backend.onrender.com/api/v1"

# We will generate 100 test cases dynamically
test_cases = []

# --- 1. Text Cases (25) ---
# Normal logs
for i in range(1, 6):
    test_cases.append({"name": f"Valid Text {i}", "text": f"Error line {i}: process failed", "type": "text"})

# SQLi & XSS
sqli_payloads = ["' OR 1=1 --", "DROP TABLE users;", "UNION SELECT * FROM history"]
for i, payload in enumerate(sqli_payloads):
    test_cases.append({"name": f"SQLi {i}", "text": payload, "type": "text"})

xss_payloads = ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>"]
for i, payload in enumerate(xss_payloads):
    test_cases.append({"name": f"XSS {i}", "text": payload, "type": "text"})

# Very long text
test_cases.append({"name": "Huge Text 50k", "text": "A" * 50000, "type": "text"})
test_cases.append({"name": "Huge Text 100k", "text": "B" * 100000, "type": "text"})

# Fill remaining text cases to 25
while len([t for t in test_cases if t["type"] == "text"]) < 25:
    test_cases.append({"name": f"Random Text {len(test_cases)}", "text": f"Log warning {len(test_cases)}", "type": "text"})


# --- 2. XML Cases (25) ---
valid_xml = "<Event><System><EventID>1000</EventID></System></Event>"
for i in range(5):
    test_cases.append({"name": f"Valid XML {i}", "text": "", "file": ("test.xml", valid_xml, "text/xml"), "type": "file"})

corrupted_xml = "<Event><System><EventID>1000</EventID></System>"
for i in range(5):
    test_cases.append({"name": f"Corrupted XML {i}", "text": "", "file": ("test.xml", corrupted_xml, "text/xml"), "type": "file"})

# XXE Attempt
xxe_xml = """<?xml version="1.0" encoding="ISO-8859-1"?>
<!DOCTYPE foo [
  <!ELEMENT foo ANY >
  <!ENTITY xxe SYSTEM "file:///etc/passwd" >]>
<foo>&xxe;</foo>"""
test_cases.append({"name": "XXE Attack", "text": "", "file": ("test.xml", xxe_xml, "text/xml"), "type": "file"})

# Billion Laughs (XML Bomb)
bomb_xml = """<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ELEMENT lolz (#PCDATA)>
 <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
 <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<lolz>&lol3;</lolz>"""
test_cases.append({"name": "XML Bomb", "text": "", "file": ("test.xml", bomb_xml, "text/xml"), "type": "file"})

while len([t for t in test_cases if t.get("file") and "xml" in t["file"][0]]) < 25:
    test_cases.append({"name": f"Random XML {len(test_cases)}", "text": "", "file": (f"test_{len(test_cases)}.xml", valid_xml, "text/xml"), "type": "file"})


# --- 3. Image Cases (25) ---
dummy_image = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
for i in range(5):
    test_cases.append({"name": f"Valid Image {i}", "text": "", "file": ("test.png", dummy_image, "image/png"), "type": "file"})

corrupted_image = dummy_image[:10]
for i in range(5):
    test_cases.append({"name": f"Corrupted Image {i}", "text": "", "file": ("test.png", corrupted_image, "image/png"), "type": "file"})

fake_image = b"This is actually a text file but pretending to be an image."
test_cases.append({"name": "Fake Image", "text": "", "file": ("test.png", fake_image, "image/png"), "type": "file"})
test_cases.append({"name": "Fake Image Extension", "text": "", "file": ("test.jpg", dummy_image, "image/jpeg"), "type": "file"})

while len([t for t in test_cases if t.get("file") and ("png" in t["file"][0] or "jpg" in t["file"][0])]) < 25:
    test_cases.append({"name": f"Random Image {len(test_cases)}", "text": "", "file": (f"test_{len(test_cases)}.png", dummy_image, "image/png"), "type": "file"})


# --- 4. EVTX & Edge Cases (25) ---
dummy_evtx = b"ElfFile\x00\x00\x00\x00\x00\x00\x00\x00"  # Invalid header but enough to trigger EVTX parser
test_cases.append({"name": "Fake EVTX", "text": "", "file": ("test.evtx", dummy_evtx, "application/octet-stream"), "type": "file"})
test_cases.append({"name": "Empty File", "text": "", "file": ("empty.txt", b"", "text/plain"), "type": "file"})
test_cases.append({"name": "Mismatched MIME", "text": "", "file": ("test.xml", dummy_image, "text/xml"), "type": "file"})
test_cases.append({"name": "No data", "text": "", "type": "empty"})

# Large File (6MB) -> DoS attempt
large_file_data = b"A" * (6 * 1024 * 1024)
test_cases.append({"name": "Large File 6MB", "text": "", "file": ("large.txt", large_file_data, "text/plain"), "type": "file"})

while len(test_cases) < 100:
    test_cases.append({"name": f"Random Edge Case {len(test_cases)}", "text": "Edge case", "type": "text"})


# Authenticate first
print("Authenticating...")
auth_resp = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "P@ssw0rd"})
if auth_resp.status_code == 200:
    token = auth_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Authentication successful.")
else:
    print("Authentication failed:", auth_resp.text)
    exit(1)

# Run tests
results = {"passed": 0, "failed": 0, "crashed": 0, "details": []}

print(f"Starting {len(test_cases)} test cases against {BASE_URL}...")

for i, tc in enumerate(test_cases):
    name = tc["name"]
    try:
        if tc["type"] == "text":
            resp = requests.post(f"{BASE_URL}/analyze/", data={"text": tc["text"]}, headers=headers, timeout=30)
        elif tc["type"] == "file":
            file_tuple = tc["file"]
            resp = requests.post(f"{BASE_URL}/analyze/", data={"text": tc.get("text", "")}, files={"file": file_tuple}, headers=headers, timeout=30)
        elif tc["type"] == "empty":
            resp = requests.post(f"{BASE_URL}/analyze/", data={"text": ""}, headers=headers, timeout=30)
        
        status = resp.status_code
        if status == 200:
            results["passed"] += 1
            res_str = "PASS (200 OK)"
        elif status in [400, 413, 422]:
            results["passed"] += 1
            res_str = f"PASS (Handled correctly with {status})"
        elif status == 500:
            results["crashed"] += 1
            res_str = "CRASH (500 Internal Server Error)"
        elif status == 429:
            results["failed"] += 1
            res_str = "RATE LIMITED (429)"
        else:
            results["failed"] += 1
            res_str = f"FAIL ({status})"
            
        print(f"[{i+1}/100] {name}: {res_str}")
        results["details"].append(f"{name} -> {res_str}")
        
    except Exception as e:
        results["crashed"] += 1
        print(f"[{i+1}/100] {name}: EXCEPTION ({str(e)})")
        results["details"].append(f"{name} -> EXCEPTION: {e}")
        
    # Delay to avoid massive rate limiting (1.5 seconds)
    time.sleep(1.5)

print("\n--- TEST SUMMARY ---")
print(f"Total: {len(test_cases)}")
print(f"Passed (Handled gracefully): {results['passed']}")
print(f"Failed (Unexpected status): {results['failed']}")
print(f"Crashed (500 or Error): {results['crashed']}")

if results['crashed'] == 0 and results['failed'] == 0:
    print("SYSTEM IS ROBUST! ALL TESTS PASSED!")
else:
    print("SYSTEM HAS VULNERABILITIES OR ISSUES.")

with open("test_100_results.txt", "w", encoding="utf-8") as f:
    f.write(f"Passed: {results['passed']}, Failed: {results['failed']}, Crashed: {results['crashed']}\n\n")
    f.write("\n".join(results["details"]))
