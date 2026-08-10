# Log Analyst System Test Cases

## Test Plan
- Total: 20 test cases
- Coverage: Event IDs, formats, faulting apps, providers, languages
- Method: Manual testing via API

---

## Test Cases

### Test 1: Event ID 1000 - Application Error (AcerQAAgent)
**Input:**
```
Log Name: Application
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
Faulting application path: C:\Windows\system32\AcerQAAgent.exe
Faulting module path: C:\Windows\system32\AcerQAAgent.exe
Report Id: 044101fe-312a-4275-a3de-1a8887a6b732
```
**Expected:** Specific recommendations for Acer Quick Access (uninstall/update)
**Language:** TH

---

### Test 2: Event ID 10016 - DCOM Error
**Input:**
```
Log Name: System
Source: Microsoft-Windows-DistributedCOM
Date: 4/15/2026 1:00:00 AM
Event ID: 10016
Level: Error
Computer: Mew
Description:
The application-specific permission settings do not grant Local Activation permission for the COM Server application with CLSID {D63B10C5-BB46-4990-A94F-E40B9D520160}
```
**Expected:** DCOM-specific troubleshooting steps
**Language:** TH

---

### Test 3: Event ID 41 - Kernel-Power (System Crash)
**Input:**
```
Log Name: System
Source: Kernel-Power
Date: 4/15/2026 2:00:00 AM
Event ID: 41
Level: Critical
Computer: Mew
Description:
The system has rebooted without cleanly shutting down first. This error could be caused if the system stopped responding, crashed, or lost power unexpectedly.
```
**Expected:** Power/hardware troubleshooting steps
**Language:** TH

---

### Test 4: Event ID 4625 - Failed Login (Security)
**Input:**
```
Log Name: Security
Source: Microsoft-Windows-Security-Auditing
Date: 4/15/2026 3:00:00 AM
Event ID: 4625
Level: Information
Computer: Mew
Description:
An account failed to log on.
Account Name: Administrator
Failure Reason: Unknown user name or bad password
```
**Expected:** Security/audit recommendations
**Language:** TH

---

### Test 5: Event ID 1000 - NVIDIA Driver Crash
**Input:**
```
Log Name: Application
Source: Application Error
Date: 4/15/2026 4:00:00 AM
Event ID: 1000
Level: Error
Computer: Mew
Description:
Faulting application name: nvlddmkm.exe
Faulting module name: nvlddmkm.exe
Exception code: 0xc0000005
Faulting application path: C:\Windows\System32\DriverStore\FileRepository\nv_disp.inf_amd64_...
```
**Expected:** NVIDIA driver update/clean install recommendations
**Language:** TH

---

### Test 6: Event ID 1000 - AMD Driver Crash
**Input:**
```
Log Name: Application
Source: Application Error
Date: 4/15/2026 5:00:00 AM
Event ID: 1000
Level: Error
Computer: Mew
Description:
Faulting application name: atiumdag.dll
Faulting module name: atiumdag.dll
Exception code: 0xc0000005
```
**Expected:** AMD driver update/clean install recommendations
**Language:** TH

---

### Test 7: Event ID 1000 - Antivirus Crash
**Input:**
```
Log Name: Application
Source: Application Error
Date: 4/15/2026 6:00:00 AM
Event ID: 1000
Level: Error
Computer: Mew
Description:
Faulting application name: AvastSvc.exe
Faulting module name: AvastSvc.exe
Exception code: 0xc0000005
```
**Expected:** Antivirus update/disable/reinstall recommendations
**Language:** TH

---

### Test 8: Incomplete Format (No XML)
**Input:**
```
Event ID: 1000
Source: Application Error
Level: Error
Description: Faulting application name: test.exe
Exception code: 0xc0000005
```
**Expected:** Should still parse and provide general recommendations
**Language:** TH

---

### Test 9: Minimal Format (Only Event ID)
**Input:**
```
Event ID: 1000
```
**Expected:** Should provide generic Event ID 1000 information
**Language:** TH

---

### Test 10: Event ID 6008 - Unexpected Shutdown
**Input:**
```
Log Name: System
Source: EventLog
Date: 4/15/2026 7:00:00 AM
Event ID: 6008
Level: Error
Computer: Mew
Description:
The previous system shutdown at time was unexpected.
```
**Expected:** Unexpected shutdown troubleshooting
**Language:** TH

---

### Test 11: Event ID 7031 - Service Crash
**Input:**
```
Log Name: System
Source: Service Control Manager
Date: 4/15/2026 8:00:00 AM
Event ID: 7031
Level: Error
Computer: Mew
Description:
The Windows Update service terminated unexpectedly.
```
**Expected:** Service restart/repair recommendations
**Language:** TH

---

### Test 12: Event ID 1001 - Windows Error Reporting
**Input:**
```
Log Name: Application
Source: Windows Error Reporting
Date: 4/15/2026 9:00:00 AM
Event ID: 1001
Level: Information
Computer: Mew
Description:
Fault bucket 123456789, type 1
Event Name: APPCRASH
Response: Not available
```
**Expected:** WER analysis and crash reporting guidance
**Language:** TH

---

### Test 13: English Language Test
**Input:**
```
Log Name: Application
Source: Application Error
Event ID: 1000
Level: Error
Description: Faulting application name: test.exe
Exception code: 0xc0000005
```
**Expected:** Results in English
**Language:** EN

---

### Test 14: Event ID 1022 - .NET Runtime Error
**Input:**
```
Log Name: Application
Source: .NET Runtime
Date: 4/15/2026 10:00:00 AM
Event ID: 1022
Level: Error
Computer: Mew
Description:
.NET Runtime version 4.0.30319.0 - The profiler has requested that the CLR not load the profiler add-on.
```
**Expected:** .NET runtime/profiler troubleshooting
**Language:** TH

---

### Test 15: XML Format Only
**Input:**
```xml
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
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
</Event>
```
**Expected:** Should parse XML correctly
**Language:** TH

---

### Test 16: Multiple Faulting Apps in Description
**Input:**
```
Log Name: Application
Source: Application Error
Event ID: 1000
Level: Error
Description:
Faulting application name: svchost.exe
Faulting module name: ntdll.dll
Exception code: 0xc0000005
```
**Expected:** Should identify first faulting app (svchost.exe)
**Language:** TH

---

### Test 17: Unknown Event ID
**Input:**
```
Log Name: Application
Source: Unknown
Event ID: 99999
Level: Error
Description: Test unknown event
```
**Expected:** Should provide generic troubleshooting steps
**Language:** TH

---

### Test 18: Critical Level Detection
**Input:**
```
Log Name: System
Source: Kernel-Power
Event ID: 41
Level: Critical
Description: System rebooted unexpectedly
```
**Expected:** Should mark as critical in metadata
**Language:** TH

---

### Test 19: Special Characters in Description
**Input:**
```
Log Name: Application
Source: Application Error
Event ID: 1000
Level: Error
Description: Faulting application name: test-app_v2.exe (special: chars)
Exception code: 0xc0000005
```
**Expected:** Should handle special characters correctly
**Language:** TH

---

### Test 20: Empty/Null Input
**Input:**
```
```
**Expected:** Should return error or default response
**Language:** TH

---

## Test Execution Template

| Test # | Event ID | Format | Language | Expected | Actual | Pass/Fail | Notes |
|--------|----------|--------|----------|----------|--------|-----------|-------|
| 1 | 1000 | Complete | TH | Acer-specific recs | | | |
| 2 | 10016 | Complete | TH | DCOM troubleshooting | | | |
| 3 | 41 | Complete | TH | Power/hardware recs | | | |
| 4 | 4625 | Complete | TH | Security recs | | | |
| 5 | 1000 | Complete | TH | NVIDIA recs | | | |
| 6 | 1000 | Complete | TH | AMD recs | | | |
| 7 | 1000 | Complete | TH | Antivirus recs | | | |
| 8 | 1000 | Incomplete | TH | General recs | | | |
| 9 | 1000 | Minimal | TH | Generic info | | | |
| 10 | 6008 | Complete | TH | Shutdown recs | | | |
| 11 | 7031 | Complete | TH | Service recs | | | |
| 12 | 1001 | Complete | TH | WER analysis | | | |
| 13 | 1000 | Complete | EN | English results | | | |
| 14 | 1022 | Complete | TH | .NET recs | | | |
| 15 | 1000 | XML | TH | XML parsing | | | |
| 16 | 1000 | Complete | TH | First app ID | | | |
| 17 | 99999 | Complete | TH | Generic recs | | | |
| 18 | 41 | Complete | TH | Critical marked | | | |
| 19 | 1000 | Special chars | TH | Handle chars | | | |
| 20 | Empty | Empty | TH | Error response | | | |

---

## Scoring Criteria

### Parser Accuracy (30%)
- Correct Event ID extraction
- Correct Provider extraction
- Correct Faulting App extraction
- Correct Level detection

### Recommendation Quality (40%)
- Specific recommendations for known apps
- Relevant troubleshooting steps
- Accurate cause identification
- Language quality (TH/EN)

### Format Handling (20%)
- Complete format support
- Incomplete format handling
- XML format support
- Minimal format handling

### Edge Cases (10%)
- Unknown Event IDs
- Special characters
- Empty input
- Critical level detection

---

## Test Results

*To be filled after execution*
