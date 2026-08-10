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

def run_audit():
    headers = login()
    
    with open("backend/tests/100_events.json", "r", encoding="utf-8") as f:
        events = json.load(f)
    
    # Get unique events based on ID
    unique_events = {}
    for evt in events:
        if evt['id'] not in unique_events:
            unique_events[evt['id']] = evt
            
    events_to_test = list(unique_events.values())
    
    results = []
    
    print(f"Starting Step Quality Audit for {len(events_to_test)} unique events (3s delay)...")
    
    for i, evt in enumerate(events_to_test):
        event_id = evt['id']
        provider = evt['provider']
        desc = evt['description']
        
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
        
        print(f"[{i+1}/{len(events_to_test)}] Auditing Event {event_id} - {provider}...")
        
        try:
            resp = requests.post(
                f"{BASE_URL}/analyze/", 
                data={"text": text_payload, "language": "th"}, 
                headers=headers, 
                timeout=45
            )
            
            if resp.status_code == 200:
                data = resp.json()
                ai_sum = data.get("aiSummary", "")
                
                # Check for fallback sentences
                if "ค้นหา Event ID นี้ใน Microsoft Learn" in ai_sum:
                    status = "FALLBACK (Poor Steps)"
                else:
                    status = "GOOD (Actionable Steps)"
                
                # Try to extract the steps part just for preview
                steps_part = ""
                if "✅ วิธีแก้ไข" in ai_sum:
                    steps_part = ai_sum.split("✅ วิธีแก้ไข")[1][:200].replace("\n", " ").strip()
                
                results.append({
                    "Test Number": i + 1,
                    "Event ID": event_id,
                    "Provider": provider,
                    "Step Quality": status,
                    "Steps Preview": steps_part + "..."
                })
            else:
                results.append({
                    "Test Number": i + 1,
                    "Event ID": event_id,
                    "Provider": provider,
                    "Step Quality": f"FAIL ({resp.status_code})",
                    "Steps Preview": "N/A"
                })
        except Exception as e:
            results.append({
                "Test Number": i + 1,
                "Event ID": event_id,
                "Provider": provider,
                "Step Quality": f"EXCEPTION",
                "Steps Preview": str(e)
            })
            
        time.sleep(3)

    csv_file = "steps_audit_results.csv"
    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ['Test Number', 'Event ID', 'Provider', 'Step Quality', 'Steps Preview']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for res in results:
            writer.writerow(res)
            
    # Print a quick summary
    good_count = sum(1 for r in results if r["Step Quality"] == "GOOD (Actionable Steps)")
    fallback_count = sum(1 for r in results if r["Step Quality"] == "FALLBACK (Poor Steps)")
    print(f"\n--- AUDIT COMPLETE ---")
    print(f"Total Unique Events: {len(events_to_test)}")
    print(f"Good Actionable Steps: {good_count} ({(good_count/len(events_to_test))*100:.1f}%)")
    print(f"Fallback/Poor Steps: {fallback_count} ({(fallback_count/len(events_to_test))*100:.1f}%)")
    print(f"Results saved to {csv_file}")

if __name__ == "__main__":
    run_audit()
