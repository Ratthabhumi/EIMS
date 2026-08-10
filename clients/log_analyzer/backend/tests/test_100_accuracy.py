import requests
import json
import time
import csv
import io

BASE_URL = "https://log-analyst-backend.onrender.com/api/v1"

def login():
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "P@ssw0rd"})
    if resp.status_code == 200:
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}
    raise Exception(f"Login failed: {resp.text}")

def run_100_tests():
    headers = login()
    
    with open("backend/tests/100_events.json", "r", encoding="utf-8") as f:
        events = json.load(f)
    
    # Pad to exactly 100 events if less
    while len(events) < 100:
        events.append(events[len(events) % len(events)].copy())
        events[-1]['description'] += " (Variant)"

    results = []
    
    print(f"Starting to test {len(events)} events (3s delay each to prevent AI rate limiting)...")
    
    for i, evt in enumerate(events):
        event_id = evt['id']
        provider = evt['provider']
        desc = evt['description']
        
        text_payload = f"Log Name: System\nSource: {provider}\nEvent ID: {event_id}\nLevel: Error\nDescription: {desc}"
        
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
                results.append({
                    "Test Number": i + 1,
                    "Event ID": event_id,
                    "Provider": provider,
                    "Input Text": desc,
                    "Status": "PASS",
                    "AI Summary": ai_sum[:100] + "..." if len(ai_sum) > 100 else ai_sum
                })
            else:
                results.append({
                    "Test Number": i + 1,
                    "Event ID": event_id,
                    "Provider": provider,
                    "Input Text": desc,
                    "Status": f"FAIL ({resp.status_code})",
                    "AI Summary": resp.text
                })
        except Exception as e:
            results.append({
                "Test Number": i + 1,
                "Event ID": event_id,
                "Provider": provider,
                "Input Text": desc,
                "Status": f"EXCEPTION",
                "AI Summary": str(e)
            })
            
        # Delay to avoid DuckDuckGo DDGS rate limits
        time.sleep(3)

    # Write to CSV
    csv_file = "accuracy_100_results.csv"
    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ['Test Number', 'Event ID', 'Provider', 'Input Text', 'Status', 'AI Summary']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for res in results:
            writer.writerow(res)
            
    print(f"All 100 tests completed. Results saved to {csv_file}")

if __name__ == "__main__":
    run_100_tests()
