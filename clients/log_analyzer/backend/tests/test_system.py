import requests
import json
from typing import Dict, List, Tuple
from datetime import datetime

BASE_URL = "https://log-analyst-bymew.fly.dev/api/v1"

TEST_CASES = [
    {
        "id": 1,
        "name": "Event ID 1000 - AcerQAAgent",
        "input": """Log Name: Application
Source: Application Error
Date: 4/15/2026 12:18:52 AM
Event ID: 1000
Task Category: Application Crashing Events
Level: Error
Keywords:  
User:  SYSTEM
Computer: Mew
Description:
Faulting application name: AcerQAAgent.exe, version: 1.5.24.0, time stamp: 0x6811c6dd
Faulting module name: AcerQAAgent.exe, version: 1.5.24.0, time stamp: 0x6811c6dd
Exception code: 0xc0000005
Fault offset: 0x00000000002eeba0
Faulting process id: 0x114C
Faulting application start time: 0x1DCCC32BFFF94C0
Faulting application path: C:\\Windows\\system32\\AcerQAAgent.exe
Faulting module path: C:\\Windows\\system32\\AcerQAAgent.exe
Report Id: 044101fe-312a-4275-a3de-1a8887a6b732""",
        "expected": "Acer",
        "language": "th"
    },
    {
        "id": 2,
        "name": "Event ID 10016 - DCOM Error",
        "input": """Log Name: System
Source: Microsoft-Windows-DistributedCOM
Date: 4/15/2026 1:00:00 AM
Event ID: 10016
Level: Error
Computer: Mew
Description:
The application-specific permission settings do not grant Local Activation permission for the COM Server application with CLSID {D63B10C5-BB46-4990-A94F-E40B9D520160}""",
        "expected": "DCOM",
        "language": "th"
    },
    {
        "id": 3,
        "name": "Event ID 41 - Kernel-Power",
        "input": """Log Name: System
Source: Kernel-Power
Date: 4/15/2026 2:00:00 AM
Event ID: 41
Level: Critical
Computer: Mew
Description:
The system has rebooted without cleanly shutting down first. This error could be caused if the system stopped responding, crashed, or lost power unexpectedly.""",
        "expected": "power",
        "language": "th"
    },
    {
        "id": 4,
        "name": "Event ID 4625 - Failed Login",
        "input": """Log Name: Security
Source: Microsoft-Windows-Security-Auditing
Date: 4/15/2026 3:00:00 AM
Event ID: 4625
Level: Information
Computer: Mew
Description:
An account failed to log on.
Account Name: Administrator
Failure Reason: Unknown user name or bad password""",
        "expected": "security",
        "language": "th"
    },
    {
        "id": 5,
        "name": "Event ID 1000 - NVIDIA Driver",
        "input": """Log Name: Application
Source: Application Error
Date: 4/15/2026 4:00:00 AM
Event ID: 1000
Level: Error
Computer: Mew
Description:
Faulting application name: nvlddmkm.exe
Faulting module name: nvlddmkm.exe
Exception code: 0xc0000005
Faulting application path: C:\\Windows\\System32\\DriverStore\\FileRepository\\nv_disp.inf_amd64""",
        "expected": "nvidia",
        "language": "th"
    },
    {
        "id": 6,
        "name": "Event ID 1000 - AMD Driver",
        "input": """Log Name: Application
Source: Application Error
Date: 4/15/2026 5:00:00 AM
Event ID: 1000
Level: Error
Computer: Mew
Description:
Faulting application name: atiumdag.dll
Faulting module name: atiumdag.dll
Exception code: 0xc0000005""",
        "expected": "amd",
        "language": "th"
    },
    {
        "id": 7,
        "name": "Event ID 1000 - Antivirus",
        "input": """Log Name: Application
Source: Application Error
Date: 4/15/2026 6:00:00 AM
Event ID: 1000
Level: Error
Computer: Mew
Description:
Faulting application name: AvastSvc.exe
Faulting module name: AvastSvc.exe
Exception code: 0xc0000005""",
        "expected": "antivirus",
        "language": "th"
    },
    {
        "id": 8,
        "name": "Incomplete Format",
        "input": """Event ID: 1000
Source: Application Error
Level: Error
Description: Faulting application name: test.exe
Exception code: 0xc0000005""",
        "expected": "1000",
        "language": "th"
    },
    {
        "id": 9,
        "name": "Minimal Format",
        "input": """Event ID: 1000""",
        "expected": "1000",
        "language": "th"
    },
    {
        "id": 10,
        "name": "Event ID 6008 - Unexpected Shutdown",
        "input": """Log Name: System
Source: EventLog
Date: 4/15/2026 7:00:00 AM
Event ID: 6008
Level: Error
Computer: Mew
Description:
The previous system shutdown at time was unexpected.""",
        "expected": "shutdown",
        "language": "th"
    },
    {
        "id": 11,
        "name": "Event ID 7031 - Service Crash",
        "input": """Log Name: System
Source: Service Control Manager
Date: 4/15/2026 8:00:00 AM
Event ID: 7031
Level: Error
Computer: Mew
Description:
The Windows Update service terminated unexpectedly.""",
        "expected": "service",
        "language": "th"
    },
    {
        "id": 12,
        "name": "Event ID 1001 - WER",
        "input": """Log Name: Application
Source: Windows Error Reporting
Date: 4/15/2026 9:00:00 AM
Event ID: 1001
Level: Information
Computer: Mew
Description:
Fault bucket 123456789, type 1
Event Name: APPCRASH
Response: Not available""",
        "expected": "wer",
        "language": "th"
    },
    {
        "id": 13,
        "name": "English Language",
        "input": """Log Name: Application
Source: Application Error
Event ID: 1000
Level: Error
Description: Faulting application name: test.exe
Exception code: 0xc0000005""",
        "expected": "1000",
        "language": "en"
    },
    {
        "id": 14,
        "name": "Event ID 1022 - .NET Runtime",
        "input": """Log Name: Application
Source: .NET Runtime
Date: 4/15/2026 10:00:00 AM
Event ID: 1022
Level: Error
Computer: Mew
Description:
.NET Runtime version 4.0.30319.0 - The profiler has requested that the CLR not load the profiler add-on.""",
        "expected": ".net",
        "language": "th"
    },
    {
        "id": 15,
        "name": "XML Format",
        "input": """<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
  <System>
    <Provider Name="Application Error" />
    <EventID>1000</EventID>
    <Level>2</Level>
    <Task>100</Task>
    <Channel>Application</Channel>
    <Computer>Mew</Computer>
  </System>
  <EventData>
    <Data Name="AppName">test.exe</Data>
    <Data Name="ExceptionCode">c0000005</Data>
  </EventData>
</Event>""",
        "expected": "1000",
        "language": "th"
    },
    {
        "id": 16,
        "name": "Multiple Faulting Apps",
        "input": """Log Name: Application
Source: Application Error
Event ID: 1000
Level: Error
Description:
Faulting application name: svchost.exe
Faulting module name: ntdll.dll
Exception code: 0xc0000005""",
        "expected": "svchost",
        "language": "th"
    },
    {
        "id": 17,
        "name": "Unknown Event ID",
        "input": """Log Name: Application
Source: Unknown
Event ID: 99999
Level: Error
Description: Test unknown event""",
        "expected": "99999",
        "language": "th"
    },
    {
        "id": 18,
        "name": "Critical Level",
        "input": """Log Name: System
Source: Kernel-Power
Event ID: 41
Level: Critical
Description: System rebooted unexpectedly""",
        "expected": "critical",
        "language": "th"
    },
    {
        "id": 19,
        "name": "Special Characters",
        "input": """Log Name: Application
Source: Application Error
Event ID: 1000
Level: Error
Description: Faulting application name: test-app_v2.exe (special: chars)
Exception code: 0xc0000005""",
        "expected": "1000",
        "language": "th"
    },
    {
        "id": 20,
        "name": "Empty Input",
        "input": "",
        "expected": "error",
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
    print("LOG ANALYST SYSTEM TEST REPORT")
    print("=" * 80)
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Tests: {len(TEST_CASES)}")
    print("=" * 80)
    print()
    
    results = []
    passed = 0
    failed = 0
    
    for test in TEST_CASES:
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
    print(f"Total: {len(TEST_CASES)}")
    print(f"Passed: {passed} ({passed/len(TEST_CASES)*100:.1f}%)")
    print(f"Failed: {failed} ({failed/len(TEST_CASES)*100:.1f}%)")
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
    with open("test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\nResults saved to test_results.json")

if __name__ == "__main__":
    main()
