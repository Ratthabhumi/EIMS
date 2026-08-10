import time
import json
import urllib.request
import urllib.error
import random

BASE_URL = "http://localhost:8000/api/v1"

def post_json(endpoint: str, payload: dict, fingerprint: str = None):
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer EIMS-CORE-LAW-5"
    }
    if fingerprint:
        headers["X-Client-Cert-Fingerprint"] = fingerprint

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Failed to post to {endpoint}: {e.code} {e.read().decode()}")
    except urllib.error.URLError as e:
        print(f"Failed to connect to backend at {BASE_URL}. Error: {e}")
    return None

def main():
    print("[*] Starting EIMS Telemetry Simulator...")
    print("Make sure the Backend (Uvicorn) is running on port 8000!")
    print("-" * 50)
    
    # Generate 3 valid 64-char SHA-256 hex strings for our mock endpoints
    endpoints = [
        {"hostname": "SRV-WEB-01", "ip": "10.0.0.10", "fingerprint": "a" * 64},
        {"hostname": "SRV-DB-01", "ip": "10.0.0.15", "fingerprint": "b" * 64},
        {"hostname": "WKST-USER-99", "ip": "192.168.1.55", "fingerprint": "c" * 64}
    ]
    
    print("[*] Registering Endpoints to Database...")
    for ep in endpoints:
        payload = {
            "hostname": ep["hostname"],
            "canonical_ip": ep["ip"],
            "cryptographic_fingerprint": ep["fingerprint"]
        }
        post_json("/assets", payload)
        print(f"  [+] Registered: {ep['hostname']} with fingerprint {ep['fingerprint'][:8]}...")
        time.sleep(1)
        
    print("-" * 50)
    print("[!] Generating Random Telemetry & Security Alerts (Press Ctrl+C to stop)")
    print("Go look at your Next.js Dashboard! You should see data flowing in real-time.")
    print("-" * 50)
    
    events = [
        (4625, "Critical", "Failed Login Attempt Detected"),
        (4625, "Critical", "Failed Login Attempt Detected"), # Higher probability of brute force
        (4625, "Critical", "Failed Login Attempt Detected"),
        (4624, "Information", "Successful Logon"),
        (4688, "Warning", "Suspicious Process Execution"),
        (1102, "Error", "Audit Log Cleared"),
        (7045, "Critical", "New Service Installed")
    ]
    
    try:
        while True:
            ep = random.choice(endpoints)
            
            # 1. Send Heartbeat (AgentHeartbeatRequest schema)
            heartbeat_payload = {
                "agent_version": "v1.2.4",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "metrics": {
                    "cpu_utilization": random.uniform(10.0, 95.0),
                    "ram_used_mb": random.randint(4096, 16384),
                    "ram_total_mb": 32768,
                    "disk_iops": random.randint(100, 5000)
                }
            }
            post_json("/telemetry/heartbeat", heartbeat_payload, fingerprint=ep["fingerprint"])
            
            # 2. Send Winlog Event
            ev = random.choice(events)
            winlog_payload = {
                "occurrence_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "event_id": ev[0],
                "severity": ev[1],
                "event_channel": "Security",
                "metadata": {
                    "workstation_name": ep["hostname"],
                    "source_network_ip": ep["ip"],
                    "description": ev[2]
                }
            }
            post_json("/telemetry/winlog", winlog_payload, fingerprint=ep["fingerprint"])
            
            print(f"  [{ev[1]}] {ep['hostname']} -> Event ID: {ev[0]} ({ev[2]})")
            
            # Fast loop to trigger quarantine (needs >5 events in 60s)
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n[!] Simulator stopped.")

if __name__ == "__main__":
    main()
