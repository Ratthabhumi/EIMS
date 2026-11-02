> Update 1 Nov 2026: fort_config/esxi_tracker/win_policy changed. Use docs/research/DEV_REVIEW_PRIORITY_DELTA_20261101.md for current priority claims/hashes; this historical packet remains valid only for its original snapshot. Other unchanged case hashes remain compatible. No human review has been recorded.

# Human Adjudication Packet — 25 ตุลาคม 2026

ทุกเคสยัง DRAFT ไม่มี reviewer alias/receipt และยังไม่ใช่ Gold. อ่านต้นฉบับก่อนข้อเสนอ AI; ก่อน/หลังเป็น output ของระบบ ไม่ใช่คำตัดสินอิสระ.
Snapshot: `20261025-grounded-diagnosis-full`, source `348f892719cc0e839cd2813d344d26e672c883fd`. ใช้ queue และ prediction hashes ของรอบนี้เท่านั้น.

## fort_config

Prediction hash: `5d62582aac1a705c564407b857c7fe88c09a18a837a26afd27c49624c40ec00f`

### ต้นฉบับ (synthetic)

cases/fort_config/input.txt
```text
1 | date=2026-10-20 time=09:41:00 devname="FG-LAB" logid="0100044547" type="event" subtype="system" level="information" action="edit" msg="Configuration setting error-log-retention=7 updated successfully"
```

### หลักฐานและข้อเสนอ

บรรทัด 1 บันทึกการแก้ configuration สำเร็จ ระดับ Information คำว่า error อยู่ในชื่อ setting ไม่ใช่หลักฐานว่าล้มเหลว

logid คือรหัสชนิดเหตุการณ์ 44547 เกี่ยวกับ object attribute; ไม่มี cfgpath/cfgattr และ FortiOS version จึงยังยืนยัน format ของรุ่นจริงไม่ได้

- AI overview: FortiGate configuration event 0100044547: successful informational edit; no failure observed in the supplied records.
- Failure present: False; first line: ไม่มี; last line: ไม่มี
- Terminal outcome: UNKNOWN; RCA: UNKNOWN
- [เอกสารผู้ผลิต](https://community.fortinet.com/fortigate-3/technical-tip-difference-between-logid-0100044547-and-logid-0100044546-which-are-generated-when-configuration-is-changed-in-the-fortigate-203472) — หลักฐานประกอบ ไม่รับรองทุก environment

### สิ่งที่ต้องตัดสิน

ยืนยันหรือแก้ว่าเป็น configuration activity และไม่มี observed failure; แยกการแก้สำเร็จจากผลกระทบต่อระบบซึ่งยังไม่ทราบ

เลือก **accept / correct / unresolved** พร้อม field/claim ID, เหตุผล, source file/line และข้อจำกัดของเอกสาร. ลง reviewer alias และวันที่ด้วยตัวเองหลังตรวจจริง; เว้นว่างจนกว่าจะตรวจ.
Claim queue มี 4 claims สำหรับเคสนี้; [เปิดดู evidence ราย claim](fort_config.html).

## esxi_tracker

Prediction hash: `08293285d5963efc5e1ec92fe9ef8f20b66a0b493997fa1e92ca4b8a94d8297f`

### ต้นฉบับ (synthetic)

cases/esxi_tracker/input.txt
```text
1 | 2026-10-20T06:08:11Z Er(02) vmx - DISKLIB-CTK: Could not delete change tracking file for synthetic-disk
2 | 2026-10-20T06:08:12Z Er(02) vmx - CTK_CTKUNLINK result:2620
```

### หลักฐานและข้อเสนอ

บรรทัด 1–2 เป็นความล้มเหลวทางเทคนิคในการลบไฟล์ติดตามการเปลี่ยนแปลงดิสก์ (CTK); result 2620 เป็นรหัสผลของ operation

ยังไม่รู้ว่าไฟล์ถูกล็อก เสียหาย หรือหายไป และไม่มีผลลัพธ์สุดท้ายของ backup/job; KB 442155 มีบริบท vSAN เฉพาะ ส่วน 418256 ต้องมีอาการเปิด CTK ไม่ได้/invalid หรือ lock เพิ่มเติม

- AI overview: VMware could not delete a change-tracking (.ctk) file. Result 2620 was recorded in the evidence. A CTK_CTKUNLINK operation result was recorded in the evidence.
- Failure present: True; first line: 1; last line: 2
- Terminal outcome: UNKNOWN; RCA: UNKNOWN
- [เอกสารผู้ผลิต](https://knowledge.broadcom.com/external/article/442155/snapshot-usage-on-esa-cluster-is-very-hi.html) — หลักฐานประกอบ ไม่รับรองทุก environment

### สิ่งที่ต้องตัดสิน

ตรวจ first failure บรรทัด 1, last observed failure บรรทัด 2, terminal outcome UNKNOWN และ physical RCA UNKNOWN; อย่ายืนยัน remediation จากรหัสเพียงอย่างเดียว

เลือก **accept / correct / unresolved** พร้อม field/claim ID, เหตุผล, source file/line และข้อจำกัดของเอกสาร. ลง reviewer alias และวันที่ด้วยตัวเองหลังตรวจจริง; เว้นว่างจนกว่าจะตรวจ.
Claim queue มี 11 claims สำหรับเคสนี้; [เปิดดู evidence ราย claim](esxi_tracker.html).

## win_policy

Prediction hash: `5a047c3db1b5286fd0eea387a798756b8fad762cc6db16bee4dfab3270fdf075`

### ต้นฉบับ (synthetic)

cases/win_policy/input.txt
```text
1 | Log Name: System
2 | Source: Microsoft-Windows-GroupPolicy
3 | Event ID: 1129
4 | Level: Error
5 | Description: Group Policy could not contact a domain controller; network connectivity failed.
```

### หลักฐานและข้อเสนอ

บรรทัด 2–4 ระบุ GroupPolicy, Event 1129, Error; บรรทัด 5 ระบุติดต่อ Domain Controller ไม่ได้

Domain Controller คือเครื่องให้บริการโดเมน อาการเชื่อมต่อไม่ได้ไม่บอกว่า DNS/LDAP/อุปกรณ์ใดเป็นต้นเหตุ; startup readiness เป็นสมมติฐานที่ต้องเทียบเวลา ไม่ใช่ข้อสรุป

- AI overview: Group Policy Event 1129 reports failure to contact a Domain Controller.
- Failure present: True; first line: 5; last line: 5
- Terminal outcome: UNKNOWN; RCA: UNKNOWN
- [เอกสารผู้ผลิต](https://learn.microsoft.com/en-us/troubleshoot/windows-server/group-policy/applying-group-policy-troubleshooting-guidance) — หลักฐานประกอบ ไม่รับรองทุก environment

### สิ่งที่ต้องตัดสิน

ตรวจว่าข้อสรุปยึดอาการตามบรรทัด 5 และ physical RCA ยัง UNKNOWN; taxonomy ของ failure ให้ตัดสินแยกจาก event identity ไม่ต้องยอมรับเพียงเพราะ AI เสนอ

เลือก **accept / correct / unresolved** พร้อม field/claim ID, เหตุผล, source file/line และข้อจำกัดของเอกสาร. ลง reviewer alias และวันที่ด้วยตัวเองหลังตรวจจริง; เว้นว่างจนกว่าจะตรวจ.
Claim queue มี 9 claims สำหรับเคสนี้; [เปิดดู evidence ราย claim](win_policy.html).

## ขอบเขตการ review

คำตัดสิน label และคำตัดสิน claim เป็นคนละรายการ; ยืนยัน v2 ไม่ยืนยัน v1 อัตโนมัติ. อย่านำคำตัดสินจาก hash เก่ามาติด hash ใหม่. ข้อเสนอแก้จากเอกสารผู้ผลิตยังไม่ใช่ human-reviewed Gold.
จำนวนคำตัดสินจริง: 0/77 claims และ 0/12 DEV. HELDOUT 5 เคสยังไม่เปิดประเมิน.
