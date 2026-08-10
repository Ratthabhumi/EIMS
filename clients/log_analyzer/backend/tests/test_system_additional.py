import requests
import json
from typing import Dict, List, Tuple
from datetime import datetime

BASE_URL = "https://log-analyst-bymew.fly.dev/api/v1"

ADDITIONAL_TEST_CASES = [
    {
        "id": 21,
        "name": "Event ID 7 - Bad Block (Disk Error)",
        "input": """Log Name: System
Source: Disk
Date: 4/15/2026 11:00:00 AM
Event ID: 7
Level: Error
Computer: Mew
Description:
The device, \\Device\\Harddisk0\\DR0, has a bad block.""",
        "expected": "disk",
        "language": "th"
    },
    {
        "id": 22,
        "name": "Event ID 51 - Disk Error",
        "input": """Log Name: System
Source: Disk
Date: 4/15/2026 12:00:00 PM
Event ID: 51
Level: Warning
Computer: Mew
Description:
An error was detected on device \\Device\\Harddisk0\\DR0 during a paging operation.""",
        "expected": "disk",
        "language": "th"
    },
    {
        "id": 23,
        "name": "Event ID 20 - Windows Update Failed",
        "input": """Log Name: System
Source: Windows Update Agent
Date: 4/15/2026 1:00:00 PM
Event ID: 20
Level: Error
Computer: Mew
Description:
Installation Failure: Windows failed to install the following update with error 0x80072efe.""",
        "expected": "update",
        "language": "th"
    },
    {
        "id": 24,
        "name": "Event ID 1000 - DLL Error (ntdll.dll)",
        "input": """Log Name: Application
Source: Application Error
Date: 4/15/2026 2:00:00 PM
Event ID: 1000
Level: Error
Computer: Mew
Description:
Faulting application name: explorer.exe
Faulting module name: ntdll.dll
Exception code: 0xc0000005
Faulting application path: C:\\Windows\\explorer.exe
Faulting module path: C:\\Windows\\System32\\ntdll.dll""",
        "expected": "dll",
        "language": "th"
    },
    {
        "id": 25,
        "name": "Event ID 1000 - Chrome Crash",
        "input": """Log Name: Application
Source: Application Error
Date: 4/15/2026 3:00:00 PM
Event ID: 1000
Level: Error
Computer: Mew
Description:
Faulting application name: chrome.exe
Faulting module name: chrome.exe
Exception code: 0xc0000005
Faulting application path: C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe""",
        "expected": "chrome",
        "language": "th"
    },
    {
        "id": 26,
        "name": "Event ID 1000 - Firefox Crash",
        "input": """Log Name: Application
Source: Application Error
Date: 4/15/2026 4:00:00 PM
Event ID: 1000
Level: Error
Computer: Mew
Description:
Faulting application name: firefox.exe
Faulting module name: xul.dll
Exception code: 0xc0000005""",
        "expected": "firefox",
        "language": "th"
    },
    {
        "id": 27,
        "name": "Event ID 1000 - svchost.exe Crash",
        "input": """Log Name: Application
Source: Application Error
Date: 4/15/2026 5:00:00 PM
Event ID: 1000
Level: Error
Computer: Mew
Description:
Faulting application name: svchost.exe
Faulting module name: ntdll.dll
Exception code: 0xc0000005
Faulting application path: C:\\Windows\\System32\\svchost.exe""",
        "expected": "svchost",
        "language": "th"
    },
    {
        "id": 28,
        "name": "Event ID 1000 - Runtime Error",
        "input": """Log Name: Application
Source: .NET Runtime
Date: 4/15/2026 6:00:00 PM
Event ID: 1000
Level: Error
Computer: Mew
Description:
Application: MyApp.exe
Framework Version: v4.0.30319
Description: The process was terminated due to an unhandled exception.""",
        "expected": ".net",
        "language": "th"
    },
    {
        "id": 29,
        "name": "Event ID 1001 - WerReport",
        "input": """Log Name: Application
Source: Windows Error Reporting
Date: 4/15/2026 7:00:00 PM
Event ID: 1001
Level: Information
Computer: Mew
Description:
Fault bucket 123456789, type 1
Event Name: BEX
Response: Not available
Cab Id: 0
Problem signature:
P1: MyApp.exe
P2: 1.0.0.0
P3: 12345678
P4: MyModule.dll
P5: 1.0.0.0
P6: 87654321
P7: 00000000
P8: c0000005
P9: 00000000
P10: 1234""",
        "expected": "wer",
        "language": "th"
    },
    {
        "id": 30,
        "name": "Event ID 1003 - DHCP Error",
        "input": """Log Name: System
Source: Dhcp-Client
Date: 4/15/2026 8:00:00 PM
Event ID: 1003
Level: Warning
Computer: Mew
Description:
Your computer was not able to obtain an IP address from the DHCP server.""",
        "expected": "dhcp",
        "language": "th"
    }
]

def run_test(test_case: Dict) -> Tuple[bool, str, Dict]:
    """Run a single test case"""
    try:
        # Login first to get token
        login_response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "admin", "password": "P@ssw0rd"}
        )
        
        if login_response.status_code != 200:
            return False, "Login failed", {}
        
        token = login_response.json().get("access_token")
        
        # Test analyze endpoint
        data = {
            "text": test_case["input"],
            "language": test_case["language"]
        }
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.post(
            f"{BASE_URL}/analyze/",
            data=data,
            headers=headers
        )
        
        if response.status_code != 200:
            return False, f"API returned {response.status_code}", {}
        
        result = response.json()
        
        # Check if expected keyword is in the response
        response_text = json.dumps(result).lower()
        expected_found = test_case["expected"].lower() in response_text
        
        return expected_found, "Success" if expected_found else "Expected keyword not found", result
        
    except Exception as e:
        return False, f"Exception: {str(e)}", {}

def main():
    """Run all tests and generate report"""
    print("=" * 80)
    print("ADDITIONAL LOG ANALYST SYSTEM TEST REPORT")
    print("=" * 80)
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Tests: {len(ADDITIONAL_TEST_CASES)}")
    print("=" * 80)
    print()
    
    results = []
    passed = 0
    failed = 0
    
    for test in ADDITIONAL_TEST_CASES:
        print(f"Running Test {test['id']}: {test['name']}...")
        success, message, result = run_test(test)
        
        if success:
            passed += 1
            status = "✅ PASS"
        else:
            failed += 1
            status = "❌ FAIL"
        
        results.append({
            "id": test["id"],
            "name": test["name"],
            "status": status,
            "message": message,
            "expected": test["expected"]
        })
        
        print(f"  {status} - {message}")
        print()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total: {len(ADDITIONAL_TEST_CASES)}")
    print(f"Passed: {passed} ({passed/len(ADDITIONAL_TEST_CASES)*100:.1f}%)")
    print(f"Failed: {failed} ({failed/len(ADDITIONAL_TEST_CASES)*100:.1f}%)")
    print("=" * 80)
    print()
    
    # Detailed Results
    print("DETAILED RESULTS")
    print("=" * 80)
    print(f"{'ID':<5} {'Status':<10} {'Test Name':<40} {'Expected':<15} {'Message'}")
    print("-" * 80)
    for r in results:
        print(f"{r['id']:<5} {r['status']:<10} {r['name']:<40} {r['expected']:<15} {r['message']}")
    print("=" * 80)
    
    # Save results to file
    with open("test_results_additional.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\nResults saved to test_results_additional.json")

if __name__ == "__main__":
    main()
