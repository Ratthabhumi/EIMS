# Human annotation review queue — v1

All 17 cases are AI-authored synthetic proposals and remain DRAFT. No human review has occurred. Do not use draft results as scientific accuracy. Heldout cases are reserved, not executed.

Review raw source family, diagnostic identity, exact evidence/first/terminal spans, uncertainty and official KB URLs. Blank applicable_kb is a proposal, not proof no KB applies. For a bundle the first listed file is the classification/identity target.

## win_policy (dev; DRAFT)
Scenario group: `network-policy`
```json
{
  "source_family": "windows_event",
  "diagnostic_code": "1129",
  "abstain_expected": false,
  "first_failure": {
    "file": "cases/win_policy/input.txt",
    "line": 5
  },
  "terminal_failure": {
    "file": "cases/win_policy/input.txt",
    "line": 5
  },
  "evidence": [
    {
      "file": "cases/win_policy/input.txt",
      "line": 5
    }
  ],
  "correlation_pairs": [],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/win_policy/input.txt`
```text
Log Name: System
Source: Microsoft-Windows-GroupPolicy
Event ID: 1129
Level: Error
Description: Group Policy could not contact a domain controller; network connectivity failed.
```
## win_boot (dev; DRAFT)
Scenario group: `event-service-start`
```json
{
  "source_family": "windows_event",
  "diagnostic_code": "6005",
  "abstain_expected": false,
  "first_failure": null,
  "terminal_failure": null,
  "evidence": [],
  "correlation_pairs": [],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/win_boot/input.txt`
```text
Log Name: System
Source: EventLog
Event ID: 6005
Level: Information
Description: The Event log service was started.
```
## veeam_tracker (dev; DRAFT)
Scenario group: `tracking-cleanup`
```json
{
  "source_family": "veeam_vbr",
  "diagnostic_code": "VMWARE-CBT-DELETE-FAILED",
  "abstain_expected": false,
  "first_failure": {
    "file": "cases/veeam_tracker/input.txt",
    "line": 2
  },
  "terminal_failure": {
    "file": "cases/veeam_tracker/input.txt",
    "line": 2
  },
  "evidence": [
    {
      "file": "cases/veeam_tracker/input.txt",
      "line": 2
    }
  ],
  "correlation_pairs": [],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/veeam_tracker/input.txt`
```text
[2026-10-20 04:01:00] Info [Veeam.Backup.Core] Replica task begins for LAB-TRACKER
[2026-10-20 04:01:07] Error [CViSnapReplica] Could not delete change tracking file
```
## veeam_options (dev; DRAFT)
Scenario group: `benign-retry-configuration`
```json
{
  "source_family": "veeam_vbr",
  "diagnostic_code": null,
  "abstain_expected": true,
  "first_failure": null,
  "terminal_failure": null,
  "evidence": [],
  "correlation_pairs": [],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/veeam_options/input.txt`
```text
[2026-10-20 05:02:00] Info [Veeam.Backup.Core] Loading backup schedule
[2026-10-20 05:02:01] Info ScheduleOptions: RetryFailedJob=true; RetryCount=4; ErrorThreshold=0
[2026-10-20 05:02:02] Info Configuration read successfully
```
## esxi_tracker (dev; DRAFT)
Scenario group: `tracking-cleanup`
```json
{
  "source_family": "vmware",
  "diagnostic_code": "VMWARE-CBT-DELETE-FAILED",
  "abstain_expected": false,
  "first_failure": {
    "file": "cases/esxi_tracker/input.txt",
    "line": 1
  },
  "terminal_failure": {
    "file": "cases/esxi_tracker/input.txt",
    "line": 2
  },
  "evidence": [
    {
      "file": "cases/esxi_tracker/input.txt",
      "line": 1
    },
    {
      "file": "cases/esxi_tracker/input.txt",
      "line": 2
    }
  ],
  "correlation_pairs": [],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/esxi_tracker/input.txt`
```text
2026-10-20T06:08:11Z Er(02) vmx - DISKLIB-CTK: Could not delete change tracking file for synthetic-disk
2026-10-20T06:08:12Z Er(02) vmx - CTK_CTKUNLINK result:2620
```
## esxi_heartbeat (dev; DRAFT)
Scenario group: `benign-hypervisor-heartbeat`
```json
{
  "source_family": "vmware",
  "diagnostic_code": null,
  "abstain_expected": true,
  "first_failure": null,
  "terminal_failure": null,
  "evidence": [],
  "correlation_pairs": [],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/esxi_heartbeat/input.txt`
```text
2026-10-20T08:22:00Z In(05) vmx - VMware ESXi hostd heartbeat received
2026-10-20T08:22:01Z In(05) vmx - VMware ESXi idle state confirmed
```
## fort_accept (dev; DRAFT)
Scenario group: `allowed-traffic`
```json
{
  "source_family": "fortinet",
  "diagnostic_code": "0000000013",
  "abstain_expected": false,
  "first_failure": null,
  "terminal_failure": null,
  "evidence": [],
  "correlation_pairs": [],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/fort_accept/input.txt`
```text
date=2026-10-20 time=09:30:00 devname="FG-LAB" logid="0000000013" type="traffic" subtype="forward" level="notice" action="accept" srcip=192.0.2.1 dstip=198.51.100.2 service="HTTPS" msg="Allowed synthetic flow"
```
## fort_config (dev; DRAFT)
Scenario group: `benign-firewall-configuration`
```json
{
  "source_family": "fortinet",
  "diagnostic_code": "0100044547",
  "abstain_expected": false,
  "first_failure": null,
  "terminal_failure": null,
  "evidence": [],
  "correlation_pairs": [],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/fort_config/input.txt`
```text
date=2026-10-20 time=09:41:00 devname="FG-LAB" logid="0100044547" type="event" subtype="system" level="information" action="edit" msg="Configuration setting error-log-retention=7 updated successfully"
```
## noise_filename (dev; DRAFT)
Scenario group: `filename-decoy`
```json
{
  "source_family": "unknown_text",
  "diagnostic_code": null,
  "abstain_expected": true,
  "first_failure": null,
  "terminal_failure": null,
  "evidence": [],
  "correlation_pairs": [],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/noise_filename/veeam_windows.txt`
```text
Inventory checklist for synthetic laboratory
Operator notes: storage labels will be printed tomorrow.
```
## json_info (dev; DRAFT)
Scenario group: `structured-benign-status`
```json
{
  "source_family": "json",
  "diagnostic_code": null,
  "abstain_expected": true,
  "first_failure": null,
  "terminal_failure": null,
  "evidence": [],
  "correlation_pairs": [],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/json_info/input.txt`
```text
{"timestamp":"2026-10-20T10:00:00Z","level":"info","message":"synthetic heartbeat completed","service":"demo"}
```
## bundle_related (dev; DRAFT)
Scenario group: `shared-operation-identity`
```json
{
  "source_family": "veeam_vbr",
  "diagnostic_code": null,
  "abstain_expected": true,
  "first_failure": null,
  "terminal_failure": null,
  "evidence": [],
  "correlation_pairs": [
    {
      "a": "cases/bundle_related/a.txt",
      "b": "cases/bundle_related/b.txt",
      "related": true,
      "rationale": "synthetic operation identity explicitly shared"
    }
  ],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/bundle_related/a.txt`
```text
[2026-10-20 11:00:00] Info [Veeam.Backup.Core] JobSessionID: eval-operation-alpha
```
Input: `cases/bundle_related/b.txt`
```text
[2026-10-20 11:00:05] Info [Veeam.Backup.Core] JobSessionID: eval-operation-alpha Replica processing started
```
## bundle_unrelated (dev; DRAFT)
Scenario group: `distinct-operation-identities`
```json
{
  "source_family": "veeam_vbr",
  "diagnostic_code": null,
  "abstain_expected": true,
  "first_failure": null,
  "terminal_failure": null,
  "evidence": [],
  "correlation_pairs": [
    {
      "a": "cases/bundle_unrelated/a.txt",
      "b": "cases/bundle_unrelated/b.txt",
      "related": false,
      "rationale": "different operation IDs and days"
    }
  ],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/bundle_unrelated/a.txt`
```text
[2026-10-20 12:00:00] Info [Veeam.Backup.Core] JobSessionID: eval-operation-bravo
```
Input: `cases/bundle_unrelated/b.txt`
```text
[2026-10-21 12:00:00] Info [Veeam.Backup.Core] JobSessionID: eval-operation-charlie Backup started
```
## win_auth_reserved (heldout; DRAFT)
Scenario group: `failed-authentication`
```json
{
  "source_family": "windows_event",
  "diagnostic_code": "4625",
  "abstain_expected": false,
  "first_failure": {
    "file": "cases/win_auth_reserved/input.txt",
    "line": 5
  },
  "terminal_failure": {
    "file": "cases/win_auth_reserved/input.txt",
    "line": 5
  },
  "evidence": [
    {
      "file": "cases/win_auth_reserved/input.txt",
      "line": 5
    }
  ],
  "correlation_pairs": [],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/win_auth_reserved/input.txt`
```text
Log Name: Security
Source: Microsoft-Windows-Security-Auditing
Event ID: 4625
Level: Information
Description: An account failed to log on in the synthetic laboratory.
```
## veeam_outcome_reserved (heldout; DRAFT)
Scenario group: `explicit-terminal-session`
```json
{
  "source_family": "veeam_vbr",
  "diagnostic_code": "VEEAM-SESSION-FAILED",
  "abstain_expected": false,
  "first_failure": {
    "file": "cases/veeam_outcome_reserved/input.txt",
    "line": 2
  },
  "terminal_failure": {
    "file": "cases/veeam_outcome_reserved/input.txt",
    "line": 2
  },
  "evidence": [
    {
      "file": "cases/veeam_outcome_reserved/input.txt",
      "line": 2
    }
  ],
  "correlation_pairs": [],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/veeam_outcome_reserved/input.txt`
```text
[2026-10-22 02:03:00] Info [Veeam.Backup.Core] Backup job opened
[2026-10-22 02:04:00] Error [Veeam.Backup.Core] Task session 'synthetic-outcome-7' has been completed, status: 'Failed'
```
## esxi_missing_reserved (heldout; DRAFT)
Scenario group: `snapshot-revert-missing-file`
```json
{
  "source_family": "vmware",
  "diagnostic_code": "VMWARE-SNAPSHOT-FILE-MISSING",
  "abstain_expected": false,
  "first_failure": {
    "file": "cases/esxi_missing_reserved/input.txt",
    "line": 1
  },
  "terminal_failure": {
    "file": "cases/esxi_missing_reserved/input.txt",
    "line": 2
  },
  "evidence": [
    {
      "file": "cases/esxi_missing_reserved/input.txt",
      "line": 1
    },
    {
      "file": "cases/esxi_missing_reserved/input.txt",
      "line": 2
    }
  ],
  "correlation_pairs": [],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/esxi_missing_reserved/input.txt`
```text
2026-10-22T03:04:00Z Er(02) vmx - VMware SNAPSHOT RevertSnapshot InvalidSnapshotFormat
2026-10-22T03:04:01Z Er(02) vmx - SNAPSHOT A required file was not found
```
## fort_deny_reserved (heldout; DRAFT)
Scenario group: `denied-traffic`
```json
{
  "source_family": "fortinet",
  "diagnostic_code": "0000000013",
  "abstain_expected": false,
  "first_failure": null,
  "terminal_failure": null,
  "evidence": [],
  "correlation_pairs": [],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/fort_deny_reserved/input.txt`
```text
date=2026-10-22 time=04:10:00 devname="FG-LAB" logid="0000000013" type="traffic" subtype="forward" level="warning" action="deny" srcip=192.0.2.10 dstip=198.51.100.10 msg="Denied synthetic flow by explicit policy"
```
## unknown_truncated_reserved (heldout; DRAFT)
Scenario group: `truncated-unidentified-evidence`
```json
{
  "source_family": "unknown_text",
  "diagnostic_code": null,
  "abstain_expected": true,
  "first_failure": null,
  "terminal_failure": null,
  "evidence": [],
  "correlation_pairs": [],
  "applicable_kb": [],
  "notes": "AI-proposed annotation, not independently validated. Identity is not root cause. Review official KB applicability independently."
}
```
Input: `cases/unknown_truncated_reserved/input.txt`
```text
[capture interrupted]
final record unavailable; source application and clock not captured
```
