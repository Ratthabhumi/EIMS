import requests
import json
from typing import Dict, List, Tuple
from datetime import datetime

BASE_URL = "https://log-analyst-bymew.fly.dev/api/v1"

EDGE_CASE_TESTS = [
    {
        "id": 31,
        "name": "Edge Case: Extremely Long Description",
        "input": "Log Name: Application\nSource: Application Error\nEvent ID: 1000\nLevel: Error\nDescription:\n" + ("A" * 50000),
        "expected": "1000",
        "language": "th"
    },
    {
        "id": 32,
        "name": "Edge Case: Emojis and Special Characters",
        "input": "Log Name: System\nSource: Disk 💾\nEvent ID: 7\nLevel: Error 🚨\nDescription:\nThe device \\Device\\Harddisk0\\DR0 has a bad block. 💀💥 ãéîôü 漢",
        "expected": "disk",
        "language": "th"
    },
    {
        "id": 33,
        "name": "Edge Case: Missing Event ID",
        "input": "Log Name: System\nSource: Unknown\nLevel: Warning\nDescription:\nSomething went wrong but there is no Event ID provided.",
        "expected": "unknown", 
        "language": "th"
    },
    {
        "id": 34,
        "name": "Edge Case: XML with missing fields",
        "input": "<Event><System><Provider Name=\"Test\"/><EventID>9999</EventID></System><EventData></EventData></Event>",
        "expected": "9999",
        "language": "th"
    },
    {
        "id": 35,
        "name": "Edge Case: Pure garbage input",
        "input": "This is just a random text that looks nothing like an event log.",
        "expected": "unknown",
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
    print("=" * 80)
    print("LOG ANALYST EDGE CASES TEST REPORT")
    print("=" * 80)
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Tests: {len(EDGE_CASE_TESTS)}")
    print("=" * 80)
    print()
    
    results = []
    passed = 0
    failed = 0
    
    for test in EDGE_CASE_TESTS:
        print(f"Running Test {test['id']}: {test['name']}...")
        success, message, result = run_test(test)
        
        if success:
            passed += 1
            status = "[PASS]"
        else:
            failed += 1
            status = "[FAIL]"
            
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
    print(f"Total: {len(EDGE_CASE_TESTS)}")
    print(f"Passed: {passed} ({passed/len(EDGE_CASE_TESTS)*100:.1f}%)")
    print(f"Failed: {failed} ({failed/len(EDGE_CASE_TESTS)*100:.1f}%)")
    print("=" * 80)
    print()
    
    with open("test_results_edge_cases.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("\nResults saved to test_results_edge_cases.json")

if __name__ == "__main__":
    main()
