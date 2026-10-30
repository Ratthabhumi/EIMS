# EIMS — Operator และ Demo

## ก่อนเริ่ม

ใช้ source PR #5 `f777e9c` หรือ delivery PR SHA ที่ CI ผ่านและตรวจ diff แล้ว.
ห้ามใช้ main แทนโดยไม่ตรวจ เพราะ main ยังไม่มี stack นี้. Core production code
ของ delivery branch ไม่เปลี่ยนจาก #5; เพิ่มเพียง test และเอกสาร.
Fixture frozen: `evaluation/analyzer/gold/cases/{fort_config,esxi_tracker,win_policy}/`
และ bundle `evaluation/analyzer/results/20261025-controlled-demo-after/{a-veeam,b-vmware}.txt`.
ไฟล์ synthetic เท่านั้น. อย่านำข้อมูลลูกค้าเข้าการเดโม/ภาพสำรอง.

ต้องมี approved HTTPS Dashboard/BFF, trusted certificate, backend ที่ผูก dedicated
synthetic PostgreSQL, synthetic accounts ที่ harness กำหนด, Edge และ Playwright.
อ่าน `tests/analyzer_synthetic_demo_app.py` ก่อนเลือก environment: harness นี้ไม่ใช่
operational application, ใช้ test keys และ local KB, ไม่เขียน vector/RAG.
อย่านำ harness ไป deploy หรือใช้ทดสอบกับ production DB.

เครื่องปัจจุบันไม่มี approved listener ที่ตรวจพบและ startup เคย blocked by policy.
เอกสารนี้จึงไม่สั่งเริ่ม listener ทดแทน. ผู้ใช้ต้องจัด environment ที่ได้รับอนุญาตก่อน.

## คำสั่งทำซ้ำแบบ offline (ไม่ต้องเปิด service)

จาก root ของ checkout นี้ ใช้ Python environment ที่ติดตั้ง requirements-evaluation.txt แล้ว:

```powershell
python tools/run_analyzer_counterexamples.py --output test-results/manual-counterexamples-UNIQUE
python -m pytest tests/test_analyzer_reliability.py tests/test_analyzer_evaluation.py tests/test_analyzer_investigation.py tests/test_analyzer_integration_stability.py -q
```

เปลี่ยน UNIQUE ให้ยังไม่มี folder; ไม่ลบผลเดิม. Python ในเครื่องผู้พัฒนาเดิมอยู่ที่
`C:/Users/MewMew/Desktop/Co-op/EIMS/venv/Scripts/python.exe`.
สำหรับ populated rehearsal ให้รันใน CI ที่จัด PostgreSQL สังเคราะห์เอง หรือหลัง
ผู้ใช้เตรียม test DB ที่ได้รับอนุญาตแล้วเท่านั้น:

```powershell
$env:EIMS_TEST_DATABASE_URL='postgresql+asyncpg://eims_test:eims_synthetic_only@127.0.0.1:55439/eims_integration_test'
python -m pytest tests/test_analyzer_postgres_integration.py -k populated_parent -q
```

เป็น test credentials สาธารณะสำหรับ isolated fixture เท่านั้น ไม่ใช่ production.
ไม่สั่ง migration ผ่าน application URL. Test สร้างและเก็บ schema ใหม่ ไม่ลบ History.

## Browser เมื่อมี approved runtime แล้ว

ตั้ง URL ให้ตรง HTTPS environment ที่ได้รับอนุญาตจริง และติดตั้ง Playwright ตาม
environment ของคุณ; ไม่ปิด TLS validation หรือใช้ insecure-session exception.

```powershell
$env:EIMS_TEST_BROWSER_BASE_URL='https://YOUR-APPROVED-SYNTHETIC-ORIGIN'
node tools/verify_secure_dashboard.cjs
```

หาก module อยู่ที่อื่น ให้ตั้ง EIMS_PLAYWRIGHT_MODULE เป็น module path จริง.
Script ใช้ actual login ของ named synthetic users; ไม่ใส่ bearer ให้ browser เอง.
เก็บ `test-results/secure-browser-acceptance.json` และ light/dark screenshots.
Script ครอบคลุม bundle, cookie, History reload, second user, logout และ expiry;
ยังต้องตรวจ **Windows raw-text UI, copied cookie replay หลัง logout, back navigation**
เพิ่มเติมด้วยตนเองก่อนประกาศครบ required flow. อย่าส่ง cookie/token กลับมาในรายงาน.
หาก prerequisite ขาด ให้หยุดและส่ง error ที่ปกปิดข้อมูลสำคัญ ไม่ลองเปลี่ยน policy.

## สคริปต์เดโม 5 นาที

| เวลา | แสดง | พูดให้ตรงหลักฐาน |
|---|---|---|
| 0:00–0:30 | ขอบเขตและ synthetic files | ระบบแยก observed facts, hypotheses และ unknowns |
| 0:30–1:20 | Fortinet configuration | คำว่า error ในชื่อ setting ไม่เท่ากับ failure; ดู structured fields |
| 1:20–2:30 | VMware CTK | operation ล้มเหลวที่บรรทัดนี้; code 2620 ไม่พิสูจน์ physical RCA หรือ final backup status |
| 2:30–3:20 | Windows 1129 | Group Policy/DC symptom; ยังไม่ยืนยัน DNS/firewall เป็นต้นเหตุ |
| 3:20–4:20 | Bundle + source-line viewer + History reload | correlation อาศัยหลักฐาน ไม่ใช่แค่มีไฟล์สองไฟล์; History ต้องเป็นของเจ้าของ |
| 4:20–5:00 | ผลทดลองและข้อจำกัด | CI/regression ผ่านไม่เท่ากับ Accuracy; ระบุจำนวนคนตรวจจริง |

## สคริปต์เดโม 10 นาที

ใช้ช่วงแรก 5 นาทีข้างบน แล้วเพิ่ม 2 นาทีอธิบาย unrelated/multi-session candidate,
1 นาทีสาธิต second-user/logout ที่ผ่านการซ้อมจริง, 1 นาที reproducibility/hash และ
1 นาที Human Review/ข้อจำกัด/แผน validation. ไม่สาธิต USB หรือ WebSocket ว่าผ่าน.

## Backup เมื่อ live flow ไม่พร้อม

เปิด source-first HTML ที่ `docs/research/evidence/20261025-grounded/` และผล frozen
โดยแจ้งว่าเป็น offline evidence ไม่ใช่การทดสอบ browser session ปัจจุบัน.
ไม่มี screenshot secure runtime ใหม่ใน delivery รอบนี้. ใช้ภาพเก่าได้เฉพาะเมื่อติด
วันที่/source SHA และระบุว่าเป็น historical screenshot; อย่าดัดแปลงให้ดูเป็น PASS ใหม่.

Recovery: เก็บ evidence และ schema ไว้ ตรวจ revision/config/backup กับ operator;
ไม่ downgrade/drop volume/reset History อัตโนมัติ. Production migration และ USB install
ต้องมีแผน/authorization ของ environment นั้นแยกจาก CI.
