"""Apply evidence-first guardrails to legacy event_knowledge fallback advice.

This updates static event guidance only. It does not create or approve KnowledgeEntry records.
Run explicitly with --apply; default mode reports planned updates.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "backend/domain/analyzer/services/event_knowledge.json"

UPDATES = {
    "4624": {
        "th": [
            "ตรวจ LogonType, Account, Source Address, Workstation และ Process พร้อม Correlate Session ID กับเหตุการณ์ใกล้เคียง",
            "ยืนยันว่า Source และช่วงเวลาเป็นกิจกรรมที่ได้รับอนุญาตกับเจ้าของบัญชี/ระบบ",
            "หากยังสงสัย ให้เก็บหลักฐานและประสาน Incident Owner ก่อนใช้ Containment แบบจำกัด Scope; ห้ามบล็อก IP หรือ Reset Password จาก Event เดียว"
        ],
        "en": [
            "Inspect LogonType, account, source address, workstation and process; correlate the session ID with nearby events.",
            "Verify the source and time window with the account/system owner.",
            "If still suspicious, preserve evidence and coordinate scoped containment with the incident owner; do not block an IP or reset a password from one event alone."
        ],
    },
    "4720": {
        "th": [
            "ตรวจ Subject, Target, เวลา, Caller Computer และ Change Ticket/Request ที่เกี่ยวข้อง",
            "ยืนยันกับเจ้าของบัญชีและผู้อนุมัติว่าการสร้างบัญชีได้รับอนุญาตหรือไม่",
            "หากไม่ได้รับอนุญาต ให้เก็บหลักฐานและขออนุมัติ Containment ที่เหมาะสม พร้อมบันทึกผลกระทบและ Rollback ก่อนเปลี่ยนสถานะบัญชี"
        ],
        "en": [
            "Inspect Subject, Target, timestamp, caller computer and related change request.",
            "Verify authorization with the account owner and approver.",
            "If unauthorized, preserve evidence and obtain approval for proportionate containment, documenting impact and rollback before changing account state."
        ],
    },
    "7000": {
        "th": [
            "เก็บ Service Name, Start Account, Error Code, Executable Path และ Dependency State",
            "ตรวจ Service Control Manager Events และ Application Logs ในช่วงเวลาเดียวกัน",
            "เปลี่ยน Credential หรือ Permission หลังยืนยันกับ Service Owner และมีแผนทดสอบ/ย้อนกลับเท่านั้น"
        ],
        "en": [
            "Capture service name, start account, error code, executable path and dependency state.",
            "Correlate Service Control Manager events with application logs at the same time.",
            "Change credentials or permissions only after service-owner confirmation and with a test and rollback plan."
        ],
    },
    "7034": {
        "th": [
            "เก็บ Service Name, Process ID, Exit/Crash Code และ Application/System Events รอบเวลาเดียวกัน",
            "ตรวจ Dump, Resource Pressure, Dependency และการเปลี่ยนแปลงซอฟต์แวร์ก่อนระบุสาเหตุ",
            "เปลี่ยน Recovery/Auto-Restart Policy เมื่อเจ้าของระบบยืนยันความปลอดภัยของ Retry และผลกระทบต่อ Dependency แล้ว"
        ],
        "en": [
            "Capture service name, process ID, exit/crash code and adjacent application/system events.",
            "Inspect dumps, resource pressure, dependencies and recent software changes before assigning cause.",
            "Change recovery/auto-restart policy only after the service owner confirms retry safety and dependency impact."
        ],
    },
    "7009": {
        "th": [
            "เก็บชื่อ Service, Start Identity, Dependency, Startup Duration และ Event จาก Service Control Manager",
            "ตรวจ CPU/RAM, Network Dependency และ Application Logs รอบเวลาเกิดเหตุ",
            "ห้ามแก้ ServicesPipeTimeout Registry เป็นขั้นตอนแรก; ทำได้เมื่อ Microsoft/Vendor Guidance และ Change Approval ระบุชัด พร้อม Backup และ Rollback"
        ],
        "en": [
            "Capture service name, start identity, dependencies, startup duration and Service Control Manager events.",
            "Inspect CPU/RAM, network dependencies and application logs around the failure.",
            "Do not change ServicesPipeTimeout as a first response; do so only with explicit Microsoft/vendor guidance, change approval, backup and rollback."
        ],
    },
    "11": {
        "th": [
            "เก็บ Event Details, Controller/Drive Identity, Link/Path State และ Error Counters",
            "ตรวจ RAID/HBA/Array Diagnostics และ Firmware/Driver Compatibility กับผู้ผลิต",
            "อย่าอัปเดต Firmware หรือเปลี่ยนสาย/อุปกรณ์ก่อนมีหลักฐานและ Maintenance Plan ที่อนุมัติ"
        ],
        "en": [
            "Capture event details, controller/drive identity, link/path state and error counters.",
            "Review RAID/HBA/array diagnostics and firmware/driver compatibility with the vendor.",
            "Do not update firmware or replace cables/devices without evidence and an approved maintenance plan."
        ],
    },
    "51": {
        "th": [
            "ตรวจ Disk I/O Latency, Resource Monitor และ Event จาก Storage/Controller",
            "ตรวจ SAN/iSCSI Path, HBA/Array Counters และสถานะ Backup",
            "ห้ามรัน CHKDSK โหมดซ่อมเป็นขั้นตอนแรก; ประเมิน Volume, Workload, Backup และ Maintenance Impact ก่อน"
        ],
        "en": [
            "Inspect disk I/O latency, Resource Monitor and storage/controller events.",
            "Check SAN/iSCSI paths, HBA/array counters and backup status.",
            "Do not run repair-mode CHKDSK as a first response; assess volume, workload, backup and maintenance impact first."
        ],
    },
    "1014": {
        "th": [
            "เก็บ Query Name, Resolver, Timestamp และ Client ที่ได้รับผลกระทบ",
            "ทดสอบ Resolver ที่กำหนดด้วย nslookup โดยระบุ Server ให้ชัด และเทียบกับ DNS Logs",
            "ตรวจ Route, Firewall Counters และ UDP/TCP 53 ตาม Path จริง โดยยังไม่แก้ Rule",
            "ล้าง Cache เฉพาะเมื่อยืนยันว่าเป็น Cache Issue และมีผลกระทบที่เข้าใจแล้ว"
        ],
        "en": [
            "Capture query name, resolver, timestamp and affected client.",
            "Test the configured resolver explicitly with nslookup and correlate DNS logs.",
            "Inspect route, firewall counters and UDP/TCP 53 along the actual path without changing rules.",
            "Clear cache only after confirming a cache issue and understanding the impact."
        ],
    },
    "134": {
        "th": [
            "เก็บ w32tm /query /status และ /configuration พร้อม Time Source, Offset และ Domain Hierarchy",
            "ตรวจ UDP 123 Path, NTP Server Logs และเวลาอ้างอิงของ Domain Controller",
            "สั่ง Resync หลังยืนยัน Authoritative Time Source และ Change Window เท่านั้น"
        ],
        "en": [
            "Capture w32tm /query /status and /configuration, including time source, offset and domain hierarchy.",
            "Inspect UDP 123 path, NTP server logs and domain-controller reference time.",
            "Resync only after confirming the authoritative time source and change window."
        ],
    },
    "1511": {
        "th": [
            "เก็บ User Profile Service Events, User SID, ProfileImagePath และ Timestamp",
            "ตรวจ NTUSER.DAT Access, Disk Space, ACL, Roaming Profile และ Network Path",
            "สำรองข้อมูล Profile และ Registry State ก่อนใช้ขั้นตอนกู้คืนที่ Microsoft รองรับ",
            "ห้ามลบ ProfileList Key หรือ Reboot เพื่อทดลองโดยไม่มีหลักฐานและ Rollback"
        ],
        "en": [
            "Capture User Profile Service events, user SID, ProfileImagePath and timestamp.",
            "Inspect NTUSER.DAT access, disk space, ACLs, roaming profile and network path.",
            "Back up profile data and registry state before using a Microsoft-supported recovery procedure.",
            "Do not delete ProfileList keys or reboot experimentally without evidence and rollback."
        ],
    },
    "20": {
        "th": [
            "เก็บ Windows Update Error Code, WindowsUpdateClient/Servicing Logs และ Pending Reboot State",
            "ตรวจ Proxy, DNS, TLS, WSUS/Update Source และ Component Store ตาม Error ที่พบ",
            "ห้ามปิด Antivirus/Firewall ทั้งระบบ; ใช้ Exception แบบจำกัด Scope และมีเวลาเมื่อ Vendor/ทีม Security อนุมัติเท่านั้น",
            "Reset SoftwareDistribution หรือหยุด Service เมื่อมีขั้นตอน Microsoft รองรับและ Change Approval เท่านั้น"
        ],
        "en": [
            "Capture Windows Update error code, WindowsUpdateClient/servicing logs and pending reboot state.",
            "Inspect proxy, DNS, TLS, WSUS/update source and component-store health according to the observed error.",
            "Do not disable antivirus/firewall globally; use a scoped, time-bounded exception only with vendor/security approval.",
            "Reset SoftwareDistribution or stop services only under a Microsoft-supported procedure and approved change."
        ],
    },
    "1135": {
        "th": [
            "เก็บ Cluster Log, Node State, Heartbeat Network Counters, NIC/Switch Errors และ Resource State",
            "ตรวจเส้นทาง Heartbeat และ System/Application Events ของ Node ที่หลุด",
            "ห้ามปรับ SameSubnetDelay/Threshold จาก Event เดียว; ต้องมี Cluster/Vendor Guidance และ Change Plan สำหรับทุก Node"
        ],
        "en": [
            "Capture cluster log, node state, heartbeat network counters, NIC/switch errors and resource state.",
            "Inspect heartbeat paths and system/application events on the removed node.",
            "Do not change SameSubnetDelay/Threshold from one event; require cluster/vendor guidance and a change plan for every node."
        ],
    },
    "10016": {
        "th": [
            "เก็บ CLSID, APPID, Account, Permission Context และ Application ที่ได้รับผลกระทบ",
            "ตรวจ Microsoft Guidance และยืนยัน Functional Impact ก่อนสรุปว่าเป็นปัญหาที่ต้องแก้",
            "ห้ามแก้ DCOM ACL หรือ Restart เพียงเพื่อให้ Event หาย; หากจำเป็นให้ใช้ Least Privilege พร้อม Rollback"
        ],
        "en": [
            "Capture CLSID, APPID, account, permission context and affected application.",
            "Check Microsoft guidance and confirm functional impact before treating it as a fault.",
            "Do not change DCOM ACLs or reboot just to clear the event; if required, use least privilege with rollback."
        ],
    },
    "17": {
        "th": [
            "เก็บ WHEA Record, PCIe Device/Slot, Vendor Diagnostics และ Error Counters",
            "ตรวจ BIOS/UEFI, Firmware, Driver และ Hardware Compatibility ตามรุ่นจริง",
            "ห้ามเปลี่ยน Power Policy หรือถอดเสียบอุปกรณ์ก่อนมี Vendor Guidance และ Maintenance Approval"
        ],
        "en": [
            "Capture WHEA record, PCIe device/slot, vendor diagnostics and error counters.",
            "Check BIOS/UEFI, firmware, driver and hardware compatibility for the exact model.",
            "Do not change power policy or reseat devices without vendor guidance and maintenance approval."
        ],
    },
    "4771": {
        "th": [
            "ตรวจ Failure Code, Client Address, Account, DC และ Timestamp",
            "Correlate กับ Event 4768, 4625 และรูปแบบ Authentication ที่ได้รับอนุญาต",
            "เก็บหลักฐานและใช้ Containment แบบจำกัด Scope หลังยืนยัน Source/Owner; ห้าม Block IP จากจำนวน Event เพียงอย่างเดียว"
        ],
        "en": [
            "Inspect failure code, client address, account, domain controller and timestamp.",
            "Correlate with Events 4768, 4625 and expected authentication patterns.",
            "Preserve evidence and use scoped containment after source/owner validation; do not block an IP from event count alone."
        ],
    },
    "55": {
        "th": [
            "เก็บ NTFS Event, Volume ID, Disk/Controller Errors และ Storage Path",
            "ตรวจ Backup ที่กู้คืนได้และ SMART/RAID/SAN Diagnostics",
            "อย่ารัน CHKDSK /f /r ก่อนประเมิน Volume, Workload, Backup และ Maintenance Window",
            "พิจารณาเปลี่ยนอุปกรณ์เมื่อมีหลักฐานจาก Diagnostics และผู้ดูแล Storage ยืนยัน"
        ],
        "en": [
            "Capture NTFS event, volume ID, disk/controller errors and storage path.",
            "Verify a recoverable backup and inspect SMART/RAID/SAN diagnostics.",
            "Do not run CHKDSK /f /r before assessing volume, workload, backup and maintenance window.",
            "Consider hardware replacement only when diagnostics and the storage owner support it."
        ],
    },
    "4768": {
        "th": [
            "ตรวจ Failure Code, Client Address, Account State และ Domain Controller ที่บันทึก Event",
            "เปรียบเทียบ Time Offset, w32tm Status และ Domain Time Hierarchy ก่อนสั่ง Sync",
            "Reset Credential เฉพาะเมื่อยืนยันเจ้าของบัญชีและได้รับอนุมัติ",
            "Correlate กับ Event 4771, 4625 และ 4740 ตามช่วงเวลา"
        ],
        "en": [
            "Inspect failure code, client address, account state and the domain controller that logged the event.",
            "Compare time offset, w32tm status and domain time hierarchy before any resynchronization.",
            "Reset credentials only after account-owner confirmation and approval.",
            "Correlate with Events 4771, 4625 and 4740 in the relevant time window."
        ],
    },
    "1102": {
        "th": [
            "เก็บ Event XML, Subject/Account, Timestamp, Host และ Change Ticket",
            "Correlate กับ External SIEM/Central Collector และระบบสำรอง Log",
            "ตรวจ Log Retention, Clear Audit Policy และการเปลี่ยนแปลงสิทธิ์ผู้ดูแล",
            "ยกระดับ Incident เมื่อไม่พบกิจกรรมที่ได้รับอนุญาตหรือมีหลักฐานการปกปิดร่องรอย"
        ],
        "en": [
            "Preserve event XML, subject/account, timestamp, host and change ticket.",
            "Correlate with external SIEM/central collector and independent log archives.",
            "Review log retention, clear-audit policy and administrator privilege changes.",
            "Escalate when no authorized activity explains the clearing or other evidence indicates concealment."
        ],
    },
    "4672": {
        "th": [
            "Correlate Logon ID กับ Event 4624 เพื่อระบุ Session และ Account",
            "ตรวจ Token Privileges, Account Role และ Change/Task ที่ได้รับอนุญาต",
            "ตรวจ Source/Time ร่วมกับ Event อื่นก่อนสรุป Privilege Abuse",
            "ปรับ Least Privilege ผ่านกระบวนการ Access Review ที่อนุมัติเท่านั้น"
        ],
        "en": [
            "Correlate Logon ID with Event 4624 to identify the session and account.",
            "Inspect token privileges, account role and authorized change/task context.",
            "Correlate source and time with other events before concluding privilege abuse.",
            "Change privileges only through an approved least-privilege access review."
        ],
    },
    "4688": {
        "th": [
            "เก็บ Command Line, Parent Process, Process ID, User/Logon ID และ Timestamp",
            "ตรวจ Signer/Hash จากแหล่ง Threat Intelligence ที่องค์กรอนุมัติ โดยไม่ส่งไฟล์หรือข้อมูลลูกค้าออกสู่บริการสาธารณะ",
            "Correlate กับ Event 4624/4672 และ Change/Automation ที่ได้รับอนุญาต",
            "ใช้ Containment เมื่อมีหลักฐานยืนยัน Malicious Execution และได้รับการประสาน Incident Owner"
        ],
        "en": [
            "Capture command line, parent process, process ID, user/logon ID and timestamp.",
            "Check signer/hash using organization-approved threat intelligence; do not upload customer files or data to public services.",
            "Correlate with Events 4624/4672 and authorized change/automation records.",
            "Contain only when malicious execution is substantiated and coordinated with the incident owner."
        ],
    },
    "KAVT0000": {
        "th": [
            "เก็บ JP1 Job ID, Agent/Service State, Error Code และ JP1 Logs",
            "ตรวจ Dependency, Queue และผลกระทบต่อ Active Jobs",
            "Restart Service เฉพาะตาม JP1 Operations Runbook หลังได้รับอนุมัติและมี Rollback"
        ],
        "en": [
            "Capture JP1 job ID, agent/service state, error code and JP1 logs.",
            "Inspect dependencies, queue and impact on active jobs.",
            "Restart services only under the JP1 operations runbook with approval and rollback."
        ],
    },
}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    data = json.loads(TARGET.read_text(encoding="utf-8"))
    for event_id, localized in UPDATES.items():
        if event_id not in data:
            raise SystemExit(f"Missing event knowledge entry: {event_id}")
        for lang in ("th", "en"):
            data[event_id][lang]["steps"] = localized[lang]
    # Every cause is a hypothesis until the case evidence supports it.
    for localized in data.values():
        for lang in ("th", "en"):
            for index, cause in enumerate(localized.get(lang, {}).get("causes", [])):
                prefix = "สมมติฐานที่ต้องตรวจสอบ: " if lang == "th" else "Possible cause to verify: "
                if not cause.startswith(prefix):
                    localized[lang]["causes"][index] = prefix + cause
    if args.apply:
        TARGET.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"UPDATED {TARGET}; guarded {len(UPDATES)} entries; qualified all cause statements as hypotheses.")
    else:
        print(f"DRY RUN: {len(UPDATES)} targeted entries; {len(data)} total entries; no files changed.")

if __name__ == "__main__":
    main()
