# Human Review delta — 1 พฤศจิกายน 2026

สถานะ DRAFT / ไม่มีคนตรวจจริง. ใช้ packet นี้แทน hash/claims ของเคสที่ระบุเท่านั้น; source และ labels ไม่เปลี่ยน. ห้ามย้ายคำตัดสินจาก hash เก่า.
Source: `a7b52915dcc38de2618c8588546bb556fb31bac0`; snapshot `20261101-priority-full_investigation`.
คำถามคนตรวจ: ยืนยัน/แก้/ยังไม่ชัดเจนเรื่อง event identity, symptom, failure, terminal outcome และ root cause; ให้ SUPPORTED/UNSUPPORTED/UNCERTAIN ราย claim พร้อมเหตุผลและบรรทัด, alias จริง, วันเวลา. ยังไม่กรอกแทนคน.

## esxi_tracker

Old hash: `08293285d5963efc5e1ec92fe9ef8f20b66a0b493997fa1e92ca4b8a94d8297f` — STALE for new output
New hash: `55cc2d558d45e79ad7ef7e5848b2bab37adf33fd4cbb1cb35eeeb13b1e252260`

Source: `cases/esxi_tracker/input.txt`; SHA256 `63e13fb8990d50218fb88cb12ce0ad88f20e7c1fb8b887b31708bea8850c4ed1`
```text
1: 2026-10-20T06:08:11Z Er(02) vmx - DISKLIB-CTK: Could not delete change tracking file for synthetic-disk
2: 2026-10-20T06:08:12Z Er(02) vmx - CTK_CTKUNLINK result:2620
```

Log มี Er(02) ต้น record จึงแสดง Error/isCritical=true; CTK failure เดิมไม่เปลี่ยนและยังไม่ทราบสาเหตุจริง/ผลจบ job.

ข้อเสนอ typed fields (ยังไม่ใช่ Gold):
```json
{
  "event_identity": null,
  "explicit_terminal_outcome": null,
  "failure_present": true,
  "failure_type": "VMWARE-CBT-DELETE-FAILED",
  "first_observed_failure": {
    "file": "cases/esxi_tracker/input.txt",
    "line": 1
  },
  "last_observed_failure": {
    "file": "cases/esxi_tracker/input.txt",
    "line": 2
  },
  "legacy_signal_fields_preserved": true,
  "projection_policy": "existing _is_noise/_signal_strength >=2; last observed != explicit session outcome",
  "root_cause_status": "UNKNOWN",
  "source_family": "vmware",
  "uncertainty_reason": "Existing signal ranks and explicit status only; possible causes are not proven root cause."
}
```

- `overview` [UNCERTAIN/RCA_OVERVIEW]: VMware could not delete a change-tracking (.ctk) file. Result 2620 was recorded in the evidence. A CTK_CTKUNLINK operation result was recorded in the evidence.
  Evidence: [{"coordinate_valid": true, "file": "cases/esxi_tracker/input.txt", "line": 1, "message": "2026-10-20T06:08:11Z Er(02) vmx - DISKLIB-CTK: Could not delete change tracking file for synthetic-disk", "origin": "native_bundle_citation"}, {"coordinate_valid": true, "file": "cases/esxi_tracker/input.txt", "line": 2, "message": "2026-10-20T06:08:12Z Er(02) vmx - CTK_CTKUNLINK result:2620", "origin": "native_bundle_citation"}]
- `observed-0` [DIRECTLY_OBSERVED/FAILURE_DESCRIPTION]: 2026-10-20T06:08:11Z Er(02) vmx - DISKLIB-CTK: Could not delete change tracking file for synthetic-disk
  Evidence: [{"coordinate_valid": true, "file": "cases/esxi_tracker/input.txt", "line": 1, "message": "2026-10-20T06:08:11Z Er(02) vmx - DISKLIB-CTK: Could not delete change tracking file for synthetic-disk", "origin": "native_bundle_citation"}]
- `observed-1` [DIRECTLY_OBSERVED/TECHNICAL_FAILURE]: 2026-10-20T06:08:12Z Er(02) vmx - CTK_CTKUNLINK result:2620
  Evidence: [{"coordinate_valid": true, "file": "cases/esxi_tracker/input.txt", "line": 2, "message": "2026-10-20T06:08:12Z Er(02) vmx - CTK_CTKUNLINK result:2620", "origin": "native_bundle_citation"}]
- `causes-0` [HYPOTHESIS/POSSIBLE_CAUSE]: Physical root cause is UNKNOWN; an unsuccessful change-tracking deletion alone does not establish its cause
  Evidence: []
- `steps-0` [UNCERTAIN/RECOMMENDATION]: Check the related .ctk.vmdk files in a datastore listing
  Evidence: []
- `steps-1` [UNCERTAIN/RECOMMENDATION]: Inspect vmware.log and hostd.log around the failure time
  Evidence: []
- `steps-2` [UNCERTAIN/RECOMMENDATION]: Refer to official Broadcom VMware CBT troubleshooting documentation — verify scope before applying
  Evidence: []
- `limitations-0` [UNCERTAIN/UNKNOWN]: Do NOT claim the file is locked unless lock evidence exists
  Evidence: []
- `nextEvidence-0` [UNCERTAIN/EVIDENCE_COLLECTION]: VM vmware.log
  Evidence: []
- `nextEvidence-1` [UNCERTAIN/EVIDENCE_COLLECTION]: ESXi hostd.log
  Evidence: []
- `nextEvidence-2` [UNCERTAIN/EVIDENCE_COLLECTION]: Datastore file listing (.vmdk / .ctk.vmdk state)
  Evidence: []

คำตัดสิน/alias/เวลาของคน: ยังไม่มี

## fort_config

Old hash: `5d62582aac1a705c564407b857c7fe88c09a18a837a26afd27c49624c40ec00f` — STALE for new output
New hash: `3f98444886b4534c0e8e0199a1e15ee5620bdebcc97cbddf552e8f8e4a310168`

Source: `cases/fort_config/input.txt`; SHA256 `896227e964a6f31240705f9852d6e7cc6b124c7da6a1e29084ef9a54649a443e`
```text
1: date=2026-10-20 time=09:41:00 devname="FG-LAB" logid="0100044547" type="event" subtype="system" level="information" action="edit" msg="Configuration setting error-log-retention=7 updated successfully"
```

บรรทัดเดียวรายงาน configuration edit สำเร็จ จึงเพิ่ม observation citation line 1. ไม่ยืนยันสุขภาพ FortiGate ทั้งระบบหรือผลกระทบของการแก้ไข.

ข้อเสนอ typed fields (ยังไม่ใช่ Gold):
```json
{
  "event_identity": "0100044547",
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

- `overview` [UNCERTAIN/RCA_OVERVIEW]: FortiGate configuration event 0100044547: successful informational edit; no failure observed in the supplied records.
  Evidence: [{"coordinate_valid": true, "file": "cases/fort_config/input.txt", "line": 1, "message": "date=2026-10-20 time=09:41:00 devname=\"FG-LAB\" logid=\"0100044547\" type=\"event\" subtype=\"system\" level=\"information\" action=\"edit\" msg=\"Configuration setting error-log-retention=7 updated successfully\"", "origin": "native_bundle_citation"}]
- `observed-0` [DIRECTLY_OBSERVED/INFORMATIONAL]: date=2026-10-20 time=09:41:00 devname="FG-LAB" logid="0100044547" type="event" subtype="system" level="information" action="edit" msg="Configuration setting error-log-retention=7 updated successfully"
  Evidence: [{"coordinate_valid": true, "file": "cases/fort_config/input.txt", "line": 1, "message": "date=2026-10-20 time=09:41:00 devname=\"FG-LAB\" logid=\"0100044547\" type=\"event\" subtype=\"system\" level=\"information\" action=\"edit\" msg=\"Configuration setting error-log-retention=7 updated successfully\"", "origin": "native_bundle_citation"}]
- `steps-0` [UNCERTAIN/RECOMMENDATION]: For a configuration audit, obtain cfgpath/cfgattr, actor, original device context and FortiOS version.
  Evidence: []
- `limitations-0` [UNCERTAIN/UNKNOWN]: The supplied fields do not validate a particular FortiOS format/version or the operational effect of the edit.
  Evidence: []
- `nextEvidence-0` [UNCERTAIN/EVIDENCE_COLLECTION]: Configuration audit fields cfgpath/cfgattr, actor, device context and FortiOS version if audit detail is required
  Evidence: []

คำตัดสิน/alias/เวลาของคน: ยังไม่มี

## win_policy

Old hash: `5a047c3db1b5286fd0eea387a798756b8fad762cc6db16bee4dfab3270fdf075` — STALE for new output
New hash: `b324cc4ca9ecbce26320f29da962e574d8af11b7e8db131471bf9237d3151a66`

Source: `cases/win_policy/input.txt`; SHA256 `b61c82af78664356855ad74be9d8c08d5386cdc3403a49c9ecd86005d771ce1c`
```text
1: Log Name: System
2: Source: Microsoft-Windows-GroupPolicy
3: Event ID: 1129
4: Level: Error
5: Description: Group Policy could not contact a domain controller; network connectivity failed.
```

Log ระบุ Group Policy ติดต่อ DC ไม่ได้ จึงเพิ่ม symptom category จาก metadata จริง ไม่ใช่ยืนยัน DNS/firewall root cause. คนต้องตัดสินว่าหมวดนี้รองรับด้วยข้อความหรือไม่.

ข้อเสนอ typed fields (ยังไม่ใช่ Gold):
```json
{
  "event_identity": "1129",
  "explicit_terminal_outcome": null,
  "failure_present": true,
  "failure_type": "WINDOWS-GROUP-POLICY-CONNECTIVITY",
  "first_observed_failure": {
    "file": "cases/win_policy/input.txt",
    "line": 5
  },
  "last_observed_failure": {
    "file": "cases/win_policy/input.txt",
    "line": 5
  },
  "legacy_signal_fields_preserved": true,
  "projection_policy": "existing _is_noise/_signal_strength >=2; last observed != explicit session outcome",
  "root_cause_status": "UNKNOWN",
  "source_family": "windows_event",
  "uncertainty_reason": "Existing signal ranks and explicit status only; possible causes are not proven root cause."
}
```

- `overview` [UNCERTAIN/RCA_OVERVIEW]: Group Policy Event 1129 reports failure to contact a Domain Controller.
  Evidence: [{"coordinate_valid": true, "file": "cases/win_policy/input.txt", "line": 5, "message": "Description: Group Policy could not contact a domain controller; network connectivity failed.", "origin": "native_bundle_citation"}]
- `observed-0` [DIRECTLY_OBSERVED/FAILURE_DESCRIPTION]: Description: Group Policy could not contact a domain controller; network connectivity failed.
  Evidence: [{"coordinate_valid": true, "file": "cases/win_policy/input.txt", "line": 5, "message": "Description: Group Policy could not contact a domain controller; network connectivity failed.", "origin": "native_bundle_citation"}]
- `metadata-0-3` [DIRECTLY_OBSERVED/EVENT_IDENTITY]: Event ID: 1129
  Evidence: [{"coordinate_valid": true, "file": "cases/win_policy/input.txt", "line": 3, "message": "Event ID: 1129", "origin": "native_metadata_to_source_projection"}]
- `metadata-0-4` [DIRECTLY_OBSERVED/SEVERITY]: Level: Error
  Evidence: [{"coordinate_valid": true, "file": "cases/win_policy/input.txt", "line": 4, "message": "Level: Error", "origin": "native_metadata_to_source_projection"}]
- `causes-0` [HYPOTHESIS/POSSIBLE_CAUSE]: Actual root cause is UNKNOWN; this event does not establish which DNS, LDAP or network component caused the symptom.
  Evidence: []
- `steps-0` [UNCERTAIN/RECOMMENDATION]: Collect System and GroupPolicy Operational events with ActivityID and timestamps.
  Evidence: []
- `steps-1` [UNCERTAIN/RECOMMENDATION]: Check DNS/DC connectivity and contemporaneous network diagnostics to distinguish hypotheses; determine whether this occurred during startup.
  Evidence: []
- `limitations-0` [UNCERTAIN/UNKNOWN]: Transient startup/network readiness and physical causes are unconfirmed; obtain evidence before changing configuration.
  Evidence: []
- `nextEvidence-0` [UNCERTAIN/EVIDENCE_COLLECTION]: Full Event Viewer export (.evtx) around the failure time
  Evidence: []

คำตัดสิน/alias/เวลาของคน: ยังไม่มี

