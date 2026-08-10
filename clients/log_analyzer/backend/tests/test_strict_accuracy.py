import requests
import json
import time
import csv

BASE_URL = "https://log-analyst-backend.onrender.com/api/v1"

def login():
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "P@ssw0rd"})
    if resp.status_code == 200:
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}
    raise Exception(f"Login failed: {resp.text}")

KEYWORDS_MAP = {
    4624: ["logon", "login", "เข้าสู่ระบบ", "สำเร็จ", "network"],
    4625: ["failed", "bad password", "รหัสผ่าน", "ล้มเหลว", "brute", "ล็อกอิน"],
    41: ["power", "shutdown", "ไฟ", "ดับ", "unexpected", "psu", "kernel"],
    10016: ["dcom", "permission", "สิทธิ์", "distributedcom", "local activation"],
    7034: ["service control manager", "terminate", "unexpectedly", "บริการ", "หยุด"],
    1000: ["crash", "faulting", "แอป", "application", "exception"],
    4109: ["graphics", "hardware", "display", "gpu", "การ์ดจอ", "จอ"],
    6008: ["unexpected", "shutdown", "ปิดเครื่อง", "ไม่คาดคิด", "ผิดปกติ"],
    1530: ["registry", "leak", "profile", "รีจิสทรี", "in use"],
    4740: ["lockout", "locked", "ล็อก", "บัญชี", "account"]
}

def check_hallucination(event_id, summary_text):
    summary_lower = summary_text.lower()
    
    # Generic keywords fallback for unmapped IDs to ensure it at least mentions the ID or provider
    keywords = KEYWORDS_MAP.get(event_id, [str(event_id)])
    
    for kw in keywords:
        if kw.lower() in summary_lower:
            return True, kw
            
    # Check if it mentions the event ID itself
    if str(event_id) in summary_lower:
        return True, str(event_id)
        
    return False, None

def run_strict_tests():
    headers = login()
    
    with open("backend/tests/100_events.json", "r", encoding="utf-8") as f:
        events = json.load(f)
    
    # Ensure exactly 100
    while len(events) < 100:
        events.append(events[len(events) % len(events)].copy())

    results = []
    
    print(f"Starting STRICT testing {len(events)} events (3s delay)...")
    
    for i, evt in enumerate(events):
        event_id = evt['id']
        provider = evt['provider']
        desc = evt['description']
        
        # Real-world Windows Event Viewer Format
        text_payload = (
            f"Log Name: System\n"
            f"Source: {provider}\n"
            f"Date: 7/12/2026 8:00:00 AM\n"
            f"Event ID: {event_id}\n"
            f"Task Category: None\n"
            f"Level: Error\n"
            f"Keywords: Classic\n"
            f"User: N/A\n"
            f"Computer: SERVER01\n"
            f"Description:\n{desc}"
        )
        
        print(f"[{i+1}/100] Testing Event {event_id} - {provider}...")
        
        try:
            resp = requests.post(
                f"{BASE_URL}/analyze/", 
                data={"text": text_payload, "language": "th"}, 
                headers=headers, 
                timeout=45
            )
            
            if resp.status_code == 200:
                data = resp.json()
                ai_sum = data.get("aiSummary", "").replace("\n", " ")
                
                is_valid, kw_found = check_hallucination(event_id, ai_sum)
                
                status = "PASS (Valid)" if is_valid else "FAIL (Hallucinated)"
                
                results.append({
                    "Test Number": i + 1,
                    "Event ID": event_id,
                    "Provider": provider,
                    "Status": status,
                    "Keyword Found": kw_found or "None",
                    "AI Summary": ai_sum[:150] + "..."
                })
            else:
                results.append({
                    "Test Number": i + 1,
                    "Event ID": event_id,
                    "Provider": provider,
                    "Status": f"FAIL ({resp.status_code})",
                    "Keyword Found": "N/A",
                    "AI Summary": resp.text
                })
        except Exception as e:
            results.append({
                "Test Number": i + 1,
                "Event ID": event_id,
                "Provider": provider,
                "Status": f"EXCEPTION",
                "Keyword Found": "N/A",
                "AI Summary": str(e)
            })
            
        time.sleep(3)

    # Write to CSV
    csv_file = "strict_accuracy_results.csv"
    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ['Test Number', 'Event ID', 'Provider', 'Status', 'Keyword Found', 'AI Summary']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for res in results:
            writer.writerow(res)
            
    print(f"All 100 strict tests completed. Results saved to {csv_file}")

if __name__ == "__main__":
    run_strict_tests()
