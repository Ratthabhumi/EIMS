# DEV Review — อีก 9 เคส (DRAFT)

ใช้คู่กับ packet สามเคสเดิม ไม่ใช่ผลคนตรวจ. ทุก decision ยังว่าง.
ศัพท์: failure = อาการล้มเหลวที่พบ; terminal outcome = ผลจบงานที่ระบุชัด; UNKNOWN = หลักฐานยังไม่พอ; KB = บทความอ้างอิง ไม่ใช่สาเหตุที่พิสูจน์แล้ว.
ให้ตรวจ claim ทีละข้อและตอบ ACCEPT/CORRECT/UNRESOLVED พร้อมเหตุผลและบรรทัดจริง; evidence list ว่างหมายถึงยังไม่มี citation ที่ผูกไว้ ไม่ใช่การรับรอง.


## bundle_related
Prediction SHA256: `bfce2e5f6c9855e0c3caa604fe205908a6410db728ab52dab8fde47428165291`


ต้นฉบับ `cases/bundle_related/a.txt`
```text
1: [2026-10-20 11:00:00] Info [Veeam.Backup.Core] JobSessionID: eval-operation-alpha
```


ต้นฉบับ `cases/bundle_related/b.txt`
```text
1: [2026-10-20 11:00:05] Info [Veeam.Backup.Core] JobSessionID: eval-operation-alpha Replica processing started
```


ข้อเสนอ AI (identity/failure/first-last/outcome/RCA):
```json
{
  "event_identity": null,
  "explicit_terminal_outcome": null,
  "failure_present": false,
  "failure_type": null,
  "first_observed_failure": null,
  "last_observed_failure": null,
  "legacy_signal_fields_preserved": true,
  "projection_policy": "existing _is_noise/_signal_strength >=2; last observed != explicit session outcome",
  "root_cause_status": "UNKNOWN",
  "source_family": "veeam_vbr",
  "uncertainty_reason": "Existing signal ranks and explicit status only; possible causes are not proven root cause."
}
```


Claims และคำแนะนำที่ต้องตรวจ — ห้ามถือว่ามีหลักฐานรองรับโดยอัตโนมัติ:

- `overview` (UNCERTAIN): Veeam Backup & Replication: No recognized diagnostic signature is present. The final task/session outcome is unknown from the supplied evidence.
  Evidence proposal: `[]`

- `causes-0` (HYPOTHESIS): The supplied evidence does not establish a specific root cause. Collect diagnostic records and the explicit final session/job outcome.
  Evidence proposal: `[]`

- `steps-0` (UNCERTAIN): Preserve the complete original log and record the event sequence
  Evidence proposal: `[]`

- `steps-1` (UNCERTAIN): Search the primary error line in Veeam Help Center
  Evidence proposal: `[]`

- `steps-2` (UNCERTAIN): Follow the references below; avoid destructive actions before preserving evidence
  Evidence proposal: `[]`


KB references ที่ระบบเสนอ (ไม่มีรายการ = ยังไม่มีแหล่งเฉพาะ):
```json
[]
```

Human decision: ______ | reviewer alias จริง: ______ | เหตุผล/แก้ fields/claims: ______


## bundle_unrelated
Prediction SHA256: `f6d071b0499f6f826e10b7b6bc1089e2238470eb78027d9c92d611fe0f9d35ca`


ต้นฉบับ `cases/bundle_unrelated/a.txt`
```text
1: [2026-10-20 12:00:00] Info [Veeam.Backup.Core] JobSessionID: eval-operation-bravo
```


ต้นฉบับ `cases/bundle_unrelated/b.txt`
```text
1: [2026-10-21 12:00:00] Info [Veeam.Backup.Core] JobSessionID: eval-operation-charlie Backup started
```


ข้อเสนอ AI (identity/failure/first-last/outcome/RCA):
```json
{
  "event_identity": null,
  "explicit_terminal_outcome": null,
  "failure_present": false,
  "failure_type": null,
  "first_observed_failure": null,
  "last_observed_failure": null,
  "legacy_signal_fields_preserved": true,
  "projection_policy": "existing _is_noise/_signal_strength >=2; last observed != explicit session outcome",
  "root_cause_status": "UNKNOWN",
  "source_family": "veeam_vbr",
  "uncertainty_reason": "Existing signal ranks and explicit status only; possible causes are not proven root cause."
}
```


Claims และคำแนะนำที่ต้องตรวจ — ห้ามถือว่ามีหลักฐานรองรับโดยอัตโนมัติ:

- `overview` (UNCERTAIN): Veeam Backup & Replication: No recognized diagnostic signature is present. The final task/session outcome is unknown from the supplied evidence.
  Evidence proposal: `[]`

- `causes-0` (HYPOTHESIS): The supplied evidence does not establish a specific root cause. Collect diagnostic records and the explicit final session/job outcome.
  Evidence proposal: `[]`

- `steps-0` (UNCERTAIN): Preserve the complete original log and record the event sequence
  Evidence proposal: `[]`

- `steps-1` (UNCERTAIN): Search the primary error line in Veeam Help Center
  Evidence proposal: `[]`

- `steps-2` (UNCERTAIN): Follow the references below; avoid destructive actions before preserving evidence
  Evidence proposal: `[]`


KB references ที่ระบบเสนอ (ไม่มีรายการ = ยังไม่มีแหล่งเฉพาะ):
```json
[]
```

Human decision: ______ | reviewer alias จริง: ______ | เหตุผล/แก้ fields/claims: ______


## esxi_heartbeat
Prediction SHA256: `a137e3bd0471b66edff9942aa7a2268cd61d6ebb62714881b5d636fa17fea5d3`


ต้นฉบับ `cases/esxi_heartbeat/input.txt`
```text
1: 2026-10-20T08:22:00Z In(05) vmx - VMware ESXi hostd heartbeat received
2: 2026-10-20T08:22:01Z In(05) vmx - VMware ESXi idle state confirmed
```


ข้อเสนอ AI (identity/failure/first-last/outcome/RCA):
```json
{
  "event_identity": null,
  "explicit_terminal_outcome": null,
  "failure_present": false,
  "failure_type": null,
  "first_observed_failure": null,
  "last_observed_failure": null,
  "legacy_signal_fields_preserved": true,
  "projection_policy": "existing _is_noise/_signal_strength >=2; last observed != explicit session outcome",
  "root_cause_status": "UNKNOWN",
  "source_family": "vmware",
  "uncertainty_reason": "Existing signal ranks and explicit status only; possible causes are not proven root cause."
}
```


Claims และคำแนะนำที่ต้องตรวจ — ห้ามถือว่ามีหลักฐานรองรับโดยอัตโนมัติ:

- `overview` (UNCERTAIN): VMware vSphere/ESXi: No recognized diagnostic signature is present. The final task/session outcome is unknown from the supplied evidence.
  Evidence proposal: `[]`

- `causes-0` (HYPOTHESIS): The supplied evidence does not establish a specific root cause. Collect diagnostic records and the explicit final session/job outcome.
  Evidence proposal: `[]`

- `steps-0` (UNCERTAIN): Preserve the complete original log and record the event sequence
  Evidence proposal: `[]`

- `steps-1` (UNCERTAIN): Search the primary error line in Broadcom Support
  Evidence proposal: `[]`

- `steps-2` (UNCERTAIN): Follow the references below; avoid destructive actions before preserving evidence
  Evidence proposal: `[]`


KB references ที่ระบบเสนอ (ไม่มีรายการ = ยังไม่มีแหล่งเฉพาะ):
```json
[]
```

Human decision: ______ | reviewer alias จริง: ______ | เหตุผล/แก้ fields/claims: ______


## fort_accept
Prediction SHA256: `0546e2befd552149e6cdb27d5aaef2d2637aea1233a82f128687af53e86d213d`


ต้นฉบับ `cases/fort_accept/input.txt`
```text
1: date=2026-10-20 time=09:30:00 devname="FG-LAB" logid="0000000013" type="traffic" subtype="forward" level="notice" action="accept" srcip=192.0.2.1 dstip=198.51.100.2 service="HTTPS" msg="Allowed synthetic flow"
```


ข้อเสนอ AI (identity/failure/first-last/outcome/RCA):
```json
{
  "event_identity": "0000000013",
  "explicit_terminal_outcome": null,
  "failure_present": false,
  "failure_type": null,
  "first_observed_failure": null,
  "last_observed_failure": null,
  "legacy_signal_fields_preserved": true,
  "projection_policy": "existing _is_noise/_signal_strength >=2; last observed != explicit session outcome",
  "root_cause_status": "UNKNOWN",
  "source_family": "fortinet",
  "uncertainty_reason": "Existing signal ranks and explicit status only; possible causes are not proven root cause."
}
```


Claims และคำแนะนำที่ต้องตรวจ — ห้ามถือว่ามีหลักฐานรองรับโดยอัตโนมัติ:

- `overview` (UNCERTAIN): Fortinet FortiGate: diagnostic 0000000013.
  Evidence proposal: `[]`

- `causes-0` (HYPOTHESIS): The supplied evidence does not establish a specific root cause. Collect diagnostic records and the explicit final session/job outcome.
  Evidence proposal: `[]`

- `steps-0` (UNCERTAIN): Preserve the complete original log and record the event sequence
  Evidence proposal: `[]`

- `steps-1` (UNCERTAIN): Search the primary error line in Fortinet Docs
  Evidence proposal: `[]`

- `steps-2` (UNCERTAIN): Follow the references below; avoid destructive actions before preserving evidence
  Evidence proposal: `[]`


KB references ที่ระบบเสนอ (ไม่มีรายการ = ยังไม่มีแหล่งเฉพาะ):
```json
[]
```

Human decision: ______ | reviewer alias จริง: ______ | เหตุผล/แก้ fields/claims: ______


## json_info
Prediction SHA256: `a99530c66f6010a5262ba0105ced4dc5a2ced52d2b920bd6bf2cd39db17f2aae`


ต้นฉบับ `cases/json_info/input.txt`
```text
1: {"timestamp":"2026-10-20T10:00:00Z","level":"info","message":"synthetic heartbeat completed","service":"demo"}
```


ข้อเสนอ AI (identity/failure/first-last/outcome/RCA):
```json
{
  "event_identity": null,
  "explicit_terminal_outcome": null,
  "failure_present": false,
  "failure_type": null,
  "first_observed_failure": null,
  "last_observed_failure": null,
  "legacy_signal_fields_preserved": true,
  "projection_policy": "existing _is_noise/_signal_strength >=2; last observed != explicit session outcome",
  "root_cause_status": "UNKNOWN",
  "source_family": "json",
  "uncertainty_reason": "Existing signal ranks and explicit status only; possible causes are not proven root cause."
}
```


Claims และคำแนะนำที่ต้องตรวจ — ห้ามถือว่ามีหลักฐานรองรับโดยอัตโนมัติ:

- `overview` (UNCERTAIN): JSON structured log diagnostic record (json).
  Evidence proposal: `[]`

- `causes-0` (HYPOTHESIS): The supplied evidence does not establish a specific root cause. Collect diagnostic records and the explicit final session/job outcome.
  Evidence proposal: `[]`

- `steps-0` (UNCERTAIN): Preserve the complete original log and record the event sequence
  Evidence proposal: `[]`

- `steps-1` (UNCERTAIN): Search the primary error line in the vendor documentation
  Evidence proposal: `[]`

- `steps-2` (UNCERTAIN): Follow the references below; avoid destructive actions before preserving evidence
  Evidence proposal: `[]`


KB references ที่ระบบเสนอ (ไม่มีรายการ = ยังไม่มีแหล่งเฉพาะ):
```json
[]
```

Human decision: ______ | reviewer alias จริง: ______ | เหตุผล/แก้ fields/claims: ______


## noise_filename
Prediction SHA256: `745e6a5869f9451f4a59cf4643a65b720830bdef63dffaff8cc65984444d41cb`


ต้นฉบับ `cases/noise_filename/veeam_windows.txt`
```text
1: Inventory checklist for synthetic laboratory
2: Operator notes: storage labels will be printed tomorrow.
```


ข้อเสนอ AI (identity/failure/first-last/outcome/RCA):
```json
{
  "event_identity": null,
  "explicit_terminal_outcome": null,
  "failure_present": false,
  "failure_type": null,
  "first_observed_failure": null,
  "last_observed_failure": null,
  "legacy_signal_fields_preserved": true,
  "projection_policy": "existing _is_noise/_signal_strength >=2; last observed != explicit session outcome",
  "root_cause_status": "UNKNOWN",
  "source_family": "unknown_text",
  "uncertainty_reason": "Existing signal ranks and explicit status only; possible causes are not proven root cause."
}
```


Claims และคำแนะนำที่ต้องตรวจ — ห้ามถือว่ามีหลักฐานรองรับโดยอัตโนมัติ:

- `overview` (UNCERTAIN): This log format has an unidentified source (unknown source), so no cause can be concluded yet. Please identify the emitting product.
  Evidence proposal: `[]`

- `causes-0` (HYPOTHESIS): The product/system that emitted this log is still unknown
  Evidence proposal: `[]`

- `causes-1` (HYPOTHESIS): The text does not match known Windows Event, Veeam, VMware, Fortinet, Cisco, or Linux syslog shapes
  Evidence proposal: `[]`

- `steps-0` (UNCERTAIN): Identify which software or appliance produced this log file and re-submit with the product name
  Evidence proposal: `[]`

- `steps-1` (UNCERTAIN): Preserve the complete original file instead of excerpts
  Evidence proposal: `[]`

- `steps-2` (UNCERTAIN): Search the vendor documentation with the primary error line
  Evidence proposal: `[]`


KB references ที่ระบบเสนอ (ไม่มีรายการ = ยังไม่มีแหล่งเฉพาะ):
```json
[]
```

Human decision: ______ | reviewer alias จริง: ______ | เหตุผล/แก้ fields/claims: ______


## veeam_options
Prediction SHA256: `dce96b66d5d4910ee1ad689dd7e461adfbe82708c8c596b1b180c88df94e0790`


ต้นฉบับ `cases/veeam_options/input.txt`
```text
1: [2026-10-20 05:02:00] Info [Veeam.Backup.Core] Loading backup schedule
2: [2026-10-20 05:02:01] Info ScheduleOptions: RetryFailedJob=true; RetryCount=4; ErrorThreshold=0
3: [2026-10-20 05:02:02] Info Configuration read successfully
```


ข้อเสนอ AI (identity/failure/first-last/outcome/RCA):
```json
{
  "event_identity": null,
  "explicit_terminal_outcome": null,
  "failure_present": false,
  "failure_type": null,
  "first_observed_failure": null,
  "last_observed_failure": null,
  "legacy_signal_fields_preserved": true,
  "projection_policy": "existing _is_noise/_signal_strength >=2; last observed != explicit session outcome",
  "root_cause_status": "UNKNOWN",
  "source_family": "veeam_vbr",
  "uncertainty_reason": "Existing signal ranks and explicit status only; possible causes are not proven root cause."
}
```


Claims และคำแนะนำที่ต้องตรวจ — ห้ามถือว่ามีหลักฐานรองรับโดยอัตโนมัติ:

- `overview` (UNCERTAIN): Veeam Backup & Replication: No recognized diagnostic signature is present. The final task/session outcome is unknown from the supplied evidence.
  Evidence proposal: `[]`

- `causes-0` (HYPOTHESIS): The supplied evidence does not establish a specific root cause. Collect diagnostic records and the explicit final session/job outcome.
  Evidence proposal: `[]`

- `steps-0` (UNCERTAIN): Preserve the complete original log and record the event sequence
  Evidence proposal: `[]`

- `steps-1` (UNCERTAIN): Search the primary error line in Veeam Help Center
  Evidence proposal: `[]`

- `steps-2` (UNCERTAIN): Follow the references below; avoid destructive actions before preserving evidence
  Evidence proposal: `[]`


KB references ที่ระบบเสนอ (ไม่มีรายการ = ยังไม่มีแหล่งเฉพาะ):
```json
[]
```

Human decision: ______ | reviewer alias จริง: ______ | เหตุผล/แก้ fields/claims: ______


## veeam_tracker
Prediction SHA256: `7020ec60ef49929770616bad9a9a450829b65f9ff26385c2eb9584bb1f57c7da`


ต้นฉบับ `cases/veeam_tracker/input.txt`
```text
1: [2026-10-20 04:01:00] Info [Veeam.Backup.Core] Replica task begins for LAB-TRACKER
2: [2026-10-20 04:01:07] Error [CViSnapReplica] Could not delete change tracking file
```


ข้อเสนอ AI (identity/failure/first-last/outcome/RCA):
```json
{
  "event_identity": null,
  "explicit_terminal_outcome": null,
  "failure_present": true,
  "failure_type": "VMWARE-CBT-DELETE-FAILED",
  "first_observed_failure": {
    "file": "cases/veeam_tracker/input.txt",
    "line": 2
  },
  "last_observed_failure": {
    "file": "cases/veeam_tracker/input.txt",
    "line": 2
  },
  "legacy_signal_fields_preserved": true,
  "projection_policy": "existing _is_noise/_signal_strength >=2; last observed != explicit session outcome",
  "root_cause_status": "UNKNOWN",
  "source_family": "veeam_vbr",
  "uncertainty_reason": "Existing signal ranks and explicit status only; possible causes are not proven root cause."
}
```


Claims และคำแนะนำที่ต้องตรวจ — ห้ามถือว่ามีหลักฐานรองรับโดยอัตโนมัติ:

- `overview` (UNCERTAIN): VMware could not delete a change-tracking (.ctk) file.
  Evidence proposal: `[{"coordinate_valid": true, "file": "cases/veeam_tracker/input.txt", "line": 2, "message": "[2026-10-20 04:01:07] Error [CViSnapReplica] Could not delete change tracking file", "origin": "native_bundle_citation"}]`

- `observed-0` (DIRECTLY_OBSERVED): [2026-10-20 04:01:07] Error [CViSnapReplica] Could not delete change tracking file
  Evidence proposal: `[{"coordinate_valid": true, "file": "cases/veeam_tracker/input.txt", "line": 2, "message": "[2026-10-20 04:01:07] Error [CViSnapReplica] Could not delete change tracking file", "origin": "native_bundle_citation"}]`

- `causes-0` (HYPOTHESIS): Physical root cause is UNKNOWN; an unsuccessful change-tracking deletion alone does not establish its cause
  Evidence proposal: `[]`

- `steps-0` (UNCERTAIN): Check the related .ctk.vmdk files in a datastore listing
  Evidence proposal: `[]`

- `steps-1` (UNCERTAIN): Inspect vmware.log and hostd.log around the failure time
  Evidence proposal: `[]`

- `steps-2` (UNCERTAIN): Refer to official Broadcom VMware CBT troubleshooting documentation — verify scope before applying
  Evidence proposal: `[]`

- `limitations-0` (UNCERTAIN): Do NOT claim the file is locked unless lock evidence exists
  Evidence proposal: `[]`

- `nextEvidence-0` (UNCERTAIN): VM vmware.log
  Evidence proposal: `[]`

- `nextEvidence-1` (UNCERTAIN): ESXi hostd.log
  Evidence proposal: `[]`

- `nextEvidence-2` (UNCERTAIN): Datastore file listing (.vmdk / .ctk.vmdk state)
  Evidence proposal: `[]`


KB references ที่ระบบเสนอ (ไม่มีรายการ = ยังไม่มีแหล่งเฉพาะ):
```json
[]
```

Human decision: ______ | reviewer alias จริง: ______ | เหตุผล/แก้ fields/claims: ______


## win_boot
Prediction SHA256: `dbb7282b1602fd775b220e12764a0ad12272c6ec844bc9b573c2f646c916f568`


ต้นฉบับ `cases/win_boot/input.txt`
```text
1: Log Name: System
2: Source: EventLog
3: Event ID: 6005
4: Level: Information
5: Description: The Event log service was started.
```


ข้อเสนอ AI (identity/failure/first-last/outcome/RCA):
```json
{
  "event_identity": "6005",
  "explicit_terminal_outcome": null,
  "failure_present": false,
  "failure_type": null,
  "first_observed_failure": null,
  "last_observed_failure": null,
  "legacy_signal_fields_preserved": true,
  "projection_policy": "existing _is_noise/_signal_strength >=2; last observed != explicit session outcome",
  "root_cause_status": "UNKNOWN",
  "source_family": "windows_event",
  "uncertainty_reason": "Existing signal ranks and explicit status only; possible causes are not proven root cause."
}
```


Claims และคำแนะนำที่ต้องตรวจ — ห้ามถือว่ามีหลักฐานรองรับโดยอัตโนมัติ:

- `overview` (UNCERTAIN): Event ID 6005 from EventLog is a Windows event log entry.
  Evidence proposal: `[]`

- `metadata-0-3` (DIRECTLY_OBSERVED): Event ID: 6005
  Evidence proposal: `[{"coordinate_valid": true, "file": "cases/win_boot/input.txt", "line": 3, "message": "Event ID: 6005", "origin": "native_metadata_to_source_projection"}]`

- `metadata-0-4` (DIRECTLY_OBSERVED): Level: Information
  Evidence proposal: `[{"coordinate_valid": true, "file": "cases/win_boot/input.txt", "line": 4, "message": "Level: Information", "origin": "native_metadata_to_source_projection"}]`

- `causes-0` (HYPOTHESIS): The actual root cause is unknown from the supplied evidence; inspect the full event and its context.
  Evidence proposal: `[]`

- `steps-0` (UNCERTAIN): Review full event details in Event Viewer
  Evidence proposal: `[]`

- `steps-1` (UNCERTAIN): Search this Event ID on Microsoft Learn for official guidance
  Evidence proposal: `[]`

- `steps-2` (UNCERTAIN): Verify reference product/version and symptom applicability before considering changes
  Evidence proposal: `[]`


KB references ที่ระบบเสนอ (ไม่มีรายการ = ยังไม่มีแหล่งเฉพาะ):
```json
[]
```

Human decision: ______ | reviewer alias จริง: ______ | เหตุผล/แก้ fields/claims: ______
