import json
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from app.services.event_knowledge import EVENT_KNOWLEDGE

out_dict = {}
for evt_id, langs in EVENT_KNOWLEDGE.items():
    out_dict[evt_id] = {}
    for lang, summary in langs.items():
        out_dict[evt_id][lang] = {
            "overview": summary.overview,
            "causes": summary.causes,
            "steps": summary.steps
        }

NEW_EVENTS = {
    # Windows
    "1074": {
        "th": {
            "overview": "Event 1074 (User Initiated Shutdown) ผู้ใช้หรือแอปพลิเคชันสั่งปิดหรือรีสตาร์ทเครื่อง",
            "causes": ["มีคนกดปุ่ม Shutdown/Restart ใน Windows", "Windows Update สั่งรีสตาร์ทหลังอัปเดตเสร็จ", "โปรแกรม Third-party สั่งรีบูตเครื่อง"],
            "steps": ["ตรวจสอบฟิลด์ 'User' ว่าใครเป็นคนสั่ง", "ตรวจสอบ 'Process Name' เพื่อดูว่าโปรแกรมไหนเรียกคำสั่ง", "เป็นการปิดเครื่องปกติ หากไม่ได้ตั้งใจให้เช็ค Schedule Task"]
        },
        "en": {
            "overview": "Event 1074 (User Initiated Shutdown) indicates a user or application initiated a restart or shutdown.",
            "causes": ["User manually clicked Shutdown/Restart", "Windows Update initiated a reboot", "A third-party application triggered a reboot"],
            "steps": ["Check the 'User' field to see who initiated it", "Check 'Process Name' to identify the calling application", "This is a clean shutdown, no action required unless unexpected"]
        }
    },
    "6006": {
        "th": {
            "overview": "Event 6006 (Event Log Service Stopped) เป็นสัญลักษณ์ว่าเครื่องปิดการทำงานโดยสมบูรณ์ (Clean Shutdown)",
            "causes": ["เครื่องทำงานตามคำสั่ง Shutdown จนจบกระบวนการ"],
            "steps": ["เหตุการณ์ปกติ ไม่ต้องดำเนินการใดๆ"]
        },
        "en": {
            "overview": "Event 6006 (Event Log Service Stopped) signifies the computer performed a clean shutdown.",
            "causes": ["System successfully shut down"],
            "steps": ["Normal behavior, no action required."]
        }
    },
    "1001": {
        "th": {
            "overview": "Event 1001 (BugCheck / Blue Screen of Death) คอมพิวเตอร์เกิดจอฟ้าและสร้างไฟล์ Memory Dump",
            "causes": ["ไดรเวอร์อุปกรณ์ (Driver) พังหรือไม่เข้ากัน", "ฮาร์ดแวร์ทำงานผิดพลาด (RAM/VGA/Disk)", "ความร้อนสะสมสูงเกินไป (Overheating)"],
            "steps": ["ใช้โปรแกรม BlueScreenView เปิดไฟล์ Memory Dump เพื่อหาไดรเวอร์ต้นเหตุ", "อัปเดตไดรเวอร์ของการ์ดจอ ชิปเซ็ต หรือเน็ตเวิร์ก", "ตรวจสอบความสมบูรณ์ของ RAM ด้วย Windows Memory Diagnostic"]
        },
        "en": {
            "overview": "Event 1001 (BugCheck) indicates a Blue Screen of Death (BSOD) occurred.",
            "causes": ["Faulty or incompatible hardware drivers", "Hardware failure (RAM, GPU, Disk)", "Overheating"],
            "steps": ["Use BlueScreenView to analyze the dump file", "Update display, chipset, and network drivers", "Run Windows Memory Diagnostic"]
        }
    },
    "17": {
        "th": {
            "overview": "Event 17 (WHEA-Logger) ตรวจพบข้อผิดพลาดฮาร์ดแวร์ที่แก้ไขได้ มักเกิดกับ PCI Express",
            "causes": ["ไดรเวอร์เมนบอร์ดหรือชิปเซ็ตเก่า/มีบั๊ก", "ตั้งค่าพลังงาน PCI Express ไม่เสถียร", "การ์ดจอเสียบบนสล็อตไม่แน่น"],
            "steps": ["ปิด 'PCI Express Link State Power Management' ใน Power Options", "อัปเดต BIOS/UEFI และไดรเวอร์ชิปเซ็ต", "ถอดและเสียบการ์ด PCIe ใหม่"]
        },
        "en": {
            "overview": "Event 17 (WHEA-Logger) indicates a corrected hardware error, typically PCI Express.",
            "causes": ["Outdated BIOS or chipset drivers", "Unstable PCIe Link State Power Management", "Loose PCIe device"],
            "steps": ["Disable 'PCI Express Link State Power Management'", "Update motherboard BIOS/UEFI and chipset drivers", "Reseat the PCIe devices"]
        }
    },
    "4771": {
        "th": {
            "overview": "Event 4771 (Kerberos Pre-Authentication Failed) ยืนยันตัวตน Kerberos ล้มเหลว (รหัสผ่านผิด)",
            "causes": ["ผู้ใช้พิมพ์รหัสผ่านผิด", "รหัสถูกเปลี่ยนแต่แอปยังจำรหัสเก่าอยู่", "ถูกเดารหัสผ่าน (Brute-force)"],
            "steps": ["ดูรหัสข้อผิดพลาด เช่น 0x18 หมายถึงรหัสผิด", "หากมี Event ถี่มาก ให้บล็อก IP ต้นทาง", "ตรวจสอบอุปกรณ์ที่จำรหัสเก่า"]
        },
        "en": {
            "overview": "Event 4771 (Kerberos Pre-Authentication Failed) means authentication failed (wrong password).",
            "causes": ["User typed incorrect password", "Cached old passwords", "Brute-force attack"],
            "steps": ["Check Failure Code (0x18 = Wrong password)", "Block source IP if aggressive", "Check devices with cached credentials"]
        }
    },
    "7036": {
        "th": {
            "overview": "Event 7036 (Service State Changed) Service ของระบบถูกเปิดหรือปิด (Stopped / Started)",
            "causes": ["การเริ่มหรือหยุด Service ตามปกติของระบบ", "ผู้ใช้หรือแอปพลิเคชันสั่งเริ่ม/หยุด Service"],
            "steps": ["เหตุการณ์ปกติ หาก Service สำคัญถูกปิด ให้ตรวจสอบสาเหตุ"]
        },
        "en": {
            "overview": "Event 7036 (Service State Changed) indicates a service entered the stopped or running state.",
            "causes": ["Normal service operations", "User or application initiated the change"],
            "steps": ["Informational. Only investigate if a critical service unexpectedly stops."]
        }
    },
    
    # S1 / Security
    "7045": {
        "th": {
            "overview": "Event 7045 (New Service Installed) ตรวจพบการติดตั้ง Service ใหม่",
            "causes": ["แอดมินติดตั้ง Service ใหม่ตามปกติ", "มัลแวร์ (Ransomware/Trojan) ติดตั้งตัวเองเป็น Service ฝังลึก"],
            "steps": ["ตรวจสอบชื่อ Service และพาธไฟล์", "ถ้าน่าสงสัย ให้ใช้ Antivirus / EDR สแกนไฟล์", "กักบริเวณ (Isolate) เครื่องหากเป็นมัลแวร์"]
        },
        "en": {
            "overview": "Event 7045 (New Service Installed) indicates a new Windows service was created.",
            "causes": ["Legitimate software installation", "Malware establishing persistence"],
            "steps": ["Review the Service Name and Image Path", "If suspicious, scan the file", "If malicious, isolate the host"]
        }
    },
    "1116": {
        "th": {
            "overview": "Event 1116 (Malware Detected) โปรแกรมป้องกันไวรัสหรือ EDR ตรวจพบมัลแวร์",
            "causes": ["ผู้ใช้ดาวน์โหลดหรือรันไฟล์อันตราย", "ถูกโจมตีผ่านช่องโหว่"],
            "steps": ["ตรวจสอบ Event 1117 ว่าโปรแกรมจัดการลบไฟล์สำเร็จหรือไม่", "สแกนเครื่องแบบ Full Scan ทันที", "ตรวจสอบแหล่งที่มาของไฟล์"]
        },
        "en": {
            "overview": "Event 1116 (Malware Detected) indicates antivirus/EDR detected malicious software.",
            "causes": ["User downloaded/executed a malicious file", "System was exploited"],
            "steps": ["Check Event 1117 to ensure action was taken", "Run a full system scan", "Investigate file origin"]
        }
    },
    
    # Hitachi JP1
    "KAVT0000": {
        "th": {
            "overview": "JP1/Base หรือ JP1/AJS3 เกิดข้อผิดพลาดในการรัน Job หรือเซอร์วิสทำงานผิดปกติ",
            "causes": ["เซอร์วิส JP1/Base ล่มหรือสื่อสารไม่ได้", "Job ค้าง (Hung) ทำให้ Timeout", "Permission ของ User ที่รัน Job ไม่พอ"],
            "steps": ["ตรวจสอบหน้า JP1/AJS3 - View ว่า Job ไหนที่ Abnormal", "เปิดดู Log ของ JP1", "รีสตาร์ทเซอร์วิส JP1 หากจำเป็น"]
        },
        "en": {
            "overview": "JP1/Base or JP1/AJS3 encountered an error running a job or a service failure.",
            "causes": ["JP1/Base service down", "Job hung resulting in a timeout", "Insufficient permissions for execution user"],
            "steps": ["Check JP1/AJS3 - View for the Abnormal job", "Review specific JP1 internal logs", "Restart JP1 services if unresponsive"]
        }
    },
    "KAVT0245-E": {
        "th": {
            "overview": "JP1 Error: KAVT0245-E ไม่สามารถเชื่อมต่อกับ Agent ปลายทางได้",
            "causes": ["Agent ปลายทางปิดเครื่อง หรือ Network ตัดขาด", "JP1/Base Service บน Agent ถูกปิด", "พอร์ตถูก Firewall บล็อก"],
            "steps": ["Ping เช็คว่า Agent ออนไลน์อยู่หรือไม่", "ตรวจสอบให้แน่ใจว่าเซอร์วิส JP1/Base รันอยู่", "ตรวจสอบ Firewall"]
        },
        "en": {
            "overview": "JP1 Error KAVT0245-E: Cannot connect to the destination Agent.",
            "causes": ["Target Agent is offline", "JP1/Base service is stopped on Agent", "Firewall blocking ports"],
            "steps": ["Ping the destination Agent", "Verify JP1/Base service is running on the Agent", "Check Firewall rules"]
        }
    }
}

for evt_id, langs in NEW_EVENTS.items():
    if evt_id not in out_dict:
        out_dict[evt_id] = langs
    else:
        out_dict[evt_id].update(langs)

json_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'services', 'event_knowledge.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(out_dict, f, ensure_ascii=False, indent=2)

print(f"Generated {json_path}")
