# Consolidated DEV adjudication packet — 2026-10-25

## อ่านก่อน review

ทั้ง 12 เคสยังเป็น **DRAFT** เอกสารนี้เป็นข้อเสนอ ไม่ใช่การรับรองจากคุณ
ไม่จำเป็นต้อง review ตอนนี้ ระบบพัฒนาและทดสอบส่วนอื่นต่อได้โดยไม่เปลี่ยนสถานะ
เมื่อพร้อม ให้ระบุ case ID, fields ที่ยืนยันหรือแก้, บรรทัดหลักฐาน และเหตุผล
ช่อง Human decision ทั้งหมดด้านล่างยังว่าง และไม่มี reviewer alias/receipt ถูกสร้าง

| เคสที่ควรตรวจเป็นลำดับแรก | Log บอกอะไร | Label ที่ AI เสนอ | หลักฐาน | สิ่งที่ยังไม่แน่ชัด / เรื่องที่ให้คุณตัดสินใจ |
|---|---|---|---|---|
| fort_config | บันทึกแก้ configuration ระดับ information และข้อความ updated successfully; error-log-retention เป็นชื่อ setting | event identity 0100044547; failure=false; terminal และ RCA ไม่ทราบ | input.txt บรรทัด 1 | เห็นด้วยหรือไม่ว่าข้อความนี้ไม่มี operational failure; ตรวจ vendor/version และความหมายของ record |
| esxi_tracker | มีข้อความลบ change-tracking file ไม่ได้ ตามด้วย CTK result 2620 | failure=true; first=1, last observed failure=2; explicit terminal=null; root cause=UNKNOWN | input.txt บรรทัด 1–2 | ยืนยันบทบาท technical failure ของบรรทัด 2; ห้ามตีความว่าจบ Job แล้ว หรือเกิดจาก lock/vSAN โดยไม่มีหลักฐาน |
| win_policy | Event 1129 ระดับ Error; description ระบุ Group Policy ติดต่อ DC ไม่ได้ | identity=1129; failure=true; first/last=5; ยังไม่พิสูจน์ physical root cause | บรรทัด 3=identity, 4=severity, 5=failure description | บรรทัด 4 รองรับ severity เท่านั้นหรือไม่; บรรทัด 5 ยังไม่พิสูจน์ว่า DNS/NIC/firewall เป็นสาเหตุ |

ใน v2 `last_observed_failure` ไม่ใช่ `explicit_terminal_outcome`
ข้อเสนอประเภท failure ยังต้อง review ไม่ใช่เพียงยืนยันว่าอ่าน Event ID ถูก
ข้อมูลอีก 9 เคสและต้นฉบับทุกบรรทัดอยู่ในชุดเดียวกันด้านล่าง
v1 และผลเดิมจะไม่ถูกเขียนทับจากการยืนยัน v2

All decisions are blank. 12 DEV proposals; zero human review receipts. This packet supplements the existing v1 queue and does not certify it. v1 files/labels/heldout lock stay unchanged. Confirm or correct the complete v2 record, not just the highlighted field.

## Interpretation sources

- Microsoft Group Policy: https://learn.microsoft.com/en-us/troubleshoot/windows-server/group-policy/applying-group-policy-troubleshooting-guidance
- Broadcom CTK 2620: https://knowledge.broadcom.com/external/article/442155/snapshot-usage-on-esa-cluster-is-very-hi.html
- Fortinet configuration log identity: https://docs.fortinet.com/document/fortigate/7.2.3/fortios-log-message-reference/34314/log-id-numbers (direct access previously 403; version applicability unresolved).

Broadcom documents 2620 as DISKLIBERR_CHANGETRACK / CTK_CTKUNLINK in a vSAN context. The code meaning is evidence for a technical failure; the article environment/cause/fix must NOT be generalized to these generic ESXi lines.

## fort_config
Proposed: source=fortinet; event identity=0100044547; failure=False; failure type=None; first=None; last=None; explicit terminal=UNKNOWN; root cause=UNKNOWN.
เหตุผล: เป็น informational edit ที่แจ้งสำเร็จ; error-log-retention เป็นชื่อ setting ข้อเสนอคือเก็บ identity แต่ไม่สร้าง failure โดยต้องตรวจความเข้ากันได้กับ format/version จริง
Input `cases/fort_config/input.txt`:
```text
 1 | date=2026-10-20 time=09:41:00 devname="FG-LAB" logid="0100044547" type="event" subtype="system" level="information" action="edit" msg="Configuration setting error-log-retention=7 updated successfully"
```
Human decision: [ ] accept v2 proposal / [ ] correct (fields + exact references) / [ ] unresolved
Reviewer public alias: ______  Rationale: ______  Official prerequisites/KB decision: ______

## esxi_tracker
Proposed: source=vmware; event identity=None; failure=True; failure type=VMWARE-CBT-DELETE-FAILED; first={'file': 'cases/esxi_tracker/input.txt', 'line': 1}; last={'file': 'cases/esxi_tracker/input.txt', 'line': 2}; explicit terminal=UNKNOWN; root cause=UNKNOWN.
เหตุผล: 2620 มีเอกสารรองรับว่าเป็น CTK technical error ข้อเสนอให้ last observed failure อยู่บรรทัด 2 แต่ final session outcome ยังไม่ทราบ ห้ามอนุมาน lock, ชื่อไฟล์ที่หาย, vSAN หรือวิธีแก้เฉพาะสภาพแวดล้อม
Input `cases/esxi_tracker/input.txt`:
```text
 1 | 2026-10-20T06:08:11Z Er(02) vmx - DISKLIB-CTK: Could not delete change tracking file for synthetic-disk
 2 | 2026-10-20T06:08:12Z Er(02) vmx - CTK_CTKUNLINK result:2620
```
Human decision: [ ] accept v2 proposal / [ ] correct (fields + exact references) / [ ] unresolved
Reviewer public alias: ______  Rationale: ______  Official prerequisites/KB decision: ______

## win_policy
Proposed: source=windows_event; event identity=1129; failure=True; failure type=WINDOWS-GROUP-POLICY-CONNECTIVITY; first={'file': 'cases/win_policy/input.txt', 'line': 5}; last={'file': 'cases/win_policy/input.txt', 'line': 5}; explicit terminal=UNKNOWN; root cause=UNKNOWN.
เหตุผล: บรรทัด 3 ระบุ event; 4 รองรับ severity; 5 อธิบาย failure จึงเสนอแยก evidence roles และยังไม่รับรอง DNS/NIC/firewall ว่าเป็น root cause
Input `cases/win_policy/input.txt`:
```text
 1 | Log Name: System
 2 | Source: Microsoft-Windows-GroupPolicy
 3 | Event ID: 1129
 4 | Level: Error
 5 | Description: Group Policy could not contact a domain controller; network connectivity failed.
```
Human decision: [ ] accept v2 proposal / [ ] correct (fields + exact references) / [ ] unresolved
Reviewer public alias: ______  Rationale: ______  Official prerequisites/KB decision: ______

## bundle_related
Proposed: source=veeam_vbr; event identity=None; failure=False; failure type=None; first=None; last=None; explicit terminal=UNKNOWN; root cause=UNKNOWN.
Justification: inspect provided literal event/outcome rather than generic error keywords. Identity alone does not establish failure or root cause. Confirm all references and unknowns.
Input `cases/bundle_related/a.txt`:
```text
 1 | [2026-10-20 11:00:00] Info [Veeam.Backup.Core] JobSessionID: eval-operation-alpha
```
Input `cases/bundle_related/b.txt`:
```text
 1 | [2026-10-20 11:00:05] Info [Veeam.Backup.Core] JobSessionID: eval-operation-alpha Replica processing started
```
Human decision: [ ] accept v2 proposal / [ ] correct (fields + exact references) / [ ] unresolved
Reviewer public alias: ______  Rationale: ______  Official prerequisites/KB decision: ______

## bundle_unrelated
Proposed: source=veeam_vbr; event identity=None; failure=False; failure type=None; first=None; last=None; explicit terminal=UNKNOWN; root cause=UNKNOWN.
Justification: inspect provided literal event/outcome rather than generic error keywords. Identity alone does not establish failure or root cause. Confirm all references and unknowns.
Input `cases/bundle_unrelated/a.txt`:
```text
 1 | [2026-10-20 12:00:00] Info [Veeam.Backup.Core] JobSessionID: eval-operation-bravo
```
Input `cases/bundle_unrelated/b.txt`:
```text
 1 | [2026-10-21 12:00:00] Info [Veeam.Backup.Core] JobSessionID: eval-operation-charlie Backup started
```
Human decision: [ ] accept v2 proposal / [ ] correct (fields + exact references) / [ ] unresolved
Reviewer public alias: ______  Rationale: ______  Official prerequisites/KB decision: ______

## esxi_heartbeat
Proposed: source=vmware; event identity=None; failure=False; failure type=None; first=None; last=None; explicit terminal=UNKNOWN; root cause=UNKNOWN.
Justification: inspect provided literal event/outcome rather than generic error keywords. Identity alone does not establish failure or root cause. Confirm all references and unknowns.
Input `cases/esxi_heartbeat/input.txt`:
```text
 1 | 2026-10-20T08:22:00Z In(05) vmx - VMware ESXi hostd heartbeat received
 2 | 2026-10-20T08:22:01Z In(05) vmx - VMware ESXi idle state confirmed
```
Human decision: [ ] accept v2 proposal / [ ] correct (fields + exact references) / [ ] unresolved
Reviewer public alias: ______  Rationale: ______  Official prerequisites/KB decision: ______

## fort_accept
Proposed: source=fortinet; event identity=0000000013; failure=False; failure type=None; first=None; last=None; explicit terminal=UNKNOWN; root cause=UNKNOWN.
Justification: inspect provided literal event/outcome rather than generic error keywords. Identity alone does not establish failure or root cause. Confirm all references and unknowns.
Input `cases/fort_accept/input.txt`:
```text
 1 | date=2026-10-20 time=09:30:00 devname="FG-LAB" logid="0000000013" type="traffic" subtype="forward" level="notice" action="accept" srcip=192.0.2.1 dstip=198.51.100.2 service="HTTPS" msg="Allowed synthetic flow"
```
Human decision: [ ] accept v2 proposal / [ ] correct (fields + exact references) / [ ] unresolved
Reviewer public alias: ______  Rationale: ______  Official prerequisites/KB decision: ______

## json_info
Proposed: source=json; event identity=None; failure=False; failure type=None; first=None; last=None; explicit terminal=UNKNOWN; root cause=UNKNOWN.
Justification: inspect provided literal event/outcome rather than generic error keywords. Identity alone does not establish failure or root cause. Confirm all references and unknowns.
Input `cases/json_info/input.txt`:
```text
 1 | {"timestamp":"2026-10-20T10:00:00Z","level":"info","message":"synthetic heartbeat completed","service":"demo"}
```
Human decision: [ ] accept v2 proposal / [ ] correct (fields + exact references) / [ ] unresolved
Reviewer public alias: ______  Rationale: ______  Official prerequisites/KB decision: ______

## noise_filename
Proposed: source=unknown_text; event identity=None; failure=False; failure type=None; first=None; last=None; explicit terminal=UNKNOWN; root cause=UNKNOWN.
Justification: inspect provided literal event/outcome rather than generic error keywords. Identity alone does not establish failure or root cause. Confirm all references and unknowns.
Input `cases/noise_filename/veeam_windows.txt`:
```text
 1 | Inventory checklist for synthetic laboratory
 2 | Operator notes: storage labels will be printed tomorrow.
```
Human decision: [ ] accept v2 proposal / [ ] correct (fields + exact references) / [ ] unresolved
Reviewer public alias: ______  Rationale: ______  Official prerequisites/KB decision: ______

## veeam_options
Proposed: source=veeam_vbr; event identity=None; failure=False; failure type=None; first=None; last=None; explicit terminal=UNKNOWN; root cause=UNKNOWN.
Justification: inspect provided literal event/outcome rather than generic error keywords. Identity alone does not establish failure or root cause. Confirm all references and unknowns.
Input `cases/veeam_options/input.txt`:
```text
 1 | [2026-10-20 05:02:00] Info [Veeam.Backup.Core] Loading backup schedule
 2 | [2026-10-20 05:02:01] Info ScheduleOptions: RetryFailedJob=true; RetryCount=4; ErrorThreshold=0
 3 | [2026-10-20 05:02:02] Info Configuration read successfully
```
Human decision: [ ] accept v2 proposal / [ ] correct (fields + exact references) / [ ] unresolved
Reviewer public alias: ______  Rationale: ______  Official prerequisites/KB decision: ______

## veeam_tracker
Proposed: source=veeam_vbr; event identity=None; failure=True; failure type=VMWARE-CBT-DELETE-FAILED; first={'file': 'cases/veeam_tracker/input.txt', 'line': 2}; last={'file': 'cases/veeam_tracker/input.txt', 'line': 2}; explicit terminal=UNKNOWN; root cause=UNKNOWN.
Justification: inspect provided literal event/outcome rather than generic error keywords. Identity alone does not establish failure or root cause. Confirm all references and unknowns.
Input `cases/veeam_tracker/input.txt`:
```text
 1 | [2026-10-20 04:01:00] Info [Veeam.Backup.Core] Replica task begins for LAB-TRACKER
 2 | [2026-10-20 04:01:07] Error [CViSnapReplica] Could not delete change tracking file
```
Human decision: [ ] accept v2 proposal / [ ] correct (fields + exact references) / [ ] unresolved
Reviewer public alias: ______  Rationale: ______  Official prerequisites/KB decision: ______

## win_boot
Proposed: source=windows_event; event identity=6005; failure=False; failure type=None; first=None; last=None; explicit terminal=UNKNOWN; root cause=UNKNOWN.
Justification: inspect provided literal event/outcome rather than generic error keywords. Identity alone does not establish failure or root cause. Confirm all references and unknowns.
Input `cases/win_boot/input.txt`:
```text
 1 | Log Name: System
 2 | Source: EventLog
 3 | Event ID: 6005
 4 | Level: Information
 5 | Description: The Event log service was started.
```
Human decision: [ ] accept v2 proposal / [ ] correct (fields + exact references) / [ ] unresolved
Reviewer public alias: ______  Rationale: ______  Official prerequisites/KB decision: ______

