## Runtime/RC update — 31 ตุลาคม 2026

Release source/fixtures/dependencies: `RELEASE_CANDIDATE_20261031.json`; final CI อ้างอิง PR #10 body. Harness ต้องระบุ EIMS_TEST_BROWSER_BASE_URL เป็น HTTPS origin ที่ได้รับอนุญาตและ certificate trusted เท่านั้น ไม่มี default URL และไม่รับ EIMS_TEST_IGNORE_TLS_ERRORS=1. เตรียม Playwright/Edge ก่อน execute; config/syntax checks ไม่ต้องมี browser. Test replay ใช้ cookie ที่ real login ออกให้เฉพาะ HTTP negative probe; ไม่ใส่ JWT ใน browser storage. ห้ามส่ง cookie/token เป็นหลักฐาน. Browser ยังคง BLOCKED_NOT_TESTED จนรันจริง.

คำสั่งรับ human review บน **working copy** เท่านั้น หลังคนตรวจจริง (replace ACTUAL_ALIAS):

```powershell
Copy-Item -LiteralPath evaluation/analyzer/gold -Destination test-results/review-working-copy-UNIQUE -Recurse
python tools/review_analyzer_case.py --manifest test-results/review-working-copy-UNIQUE/manifest.v1.json --annotations-v2 test-results/review-working-copy-UNIQUE/manifest.v2.dev-draft.json --case-id fort_config --reviewer-id ACTUAL_ALIAS --confirm-human-review
python tools/eval_analyzer.py --manifest test-results/review-working-copy-UNIQUE/manifest.v1.json --annotations-v2 test-results/review-working-copy-UNIQUE/manifest.v2.dev-draft.json --mode full_investigation --split dev --grounding-reviews ACTUAL_JUDGMENTS.json --output test-results/reviewed-pilot-UNIQUE
```

เลือก destination ใหม่ที่ยังไม่มี; ตรวจ/แก้ label สำเนาตามคำตัดสินจริงก่อนบันทึก. ทำซ้ำคำสั่ง review เฉพาะเคสที่ตรวจแล้ว (esxi_tracker/win_policy); judgments ต้องตรง cohort/hash และใช้ queue schema เดิม. เก็บเวลา/คำยืนยันจริงแยก provenance. ไม่รันคำสั่งเหล่านี้แทนคนหรือปรับ DRAFT ต้นฉบับ.

## เพิ่ม negative control สำหรับเดโมรอบล่าสุด

ใช้ `evaluation/analyzer/gold/cases/esxi_heartbeat/` หรือ bundle_related จาก frozen manifest. คำตอบต้องไม่สั่งค้น primary error line: ไม่พบ failure ในข้อมูลที่ให้มา ไม่ได้ยืนยันระบบทั้งหมดปกติ และต้องมี completion record ของ session ที่เกี่ยวข้องก่อนยืนยันผลจบ. เปิด History แล้วข้อความต้องตรงกัน. หากยังไม่มี approved HTTPS runtime ให้แสดง offline snapshot พร้อมบอกขอบเขต ไม่อ้างว่า UI ผ่าน. ผลใหม่อยู่ `20261030-recommendation-full_investigation`; priority 3 packet ใช้เดิม, อีก 8 เคสใช้ delta packet.

# EIMS — Operator และ Demo

## ก่อนเริ่ม

ใช้ source PR #5 `f777e9c` หรือ delivery PR SHA ที่ CI ผ่านและตรวจ diff แล้ว.
ห้ามใช้ main แทนโดยไม่ตรวจ เพราะ main ยังไม่มี stack นี้. Delivery branch เพิ่ม evidence-aware recommendation fix หลัง #5; ใช้ PR #10 HEAD ที่ CI ผ่านเท่านั้นสำหรับ negative control ใหม่.
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
harness รอบ 31 ต.ค. เพิ่ม copied-cookie replay หลัง logout, back/forward/reload และพิกัด source แล้ว แต่ยังไม่ได้ execute บน runtime จริง; **Windows raw-text UI** ยังต้องตรวจเพิ่มเติมด้วยตนเองก่อนประกาศครบ required flow. อย่าส่ง cookie/token กลับมาในรายงาน.
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


## วิธีส่ง Human Review จริง — ใช้ packet เดิม

1. อ่านบรรทัดต้นฉบับก่อนข้อเสนอ AI. Event ID เป็นตัวระบุเหตุการณ์ ไม่ใช่ physical RCA.
2. แยก observed failure / explicit final outcome / hypothesis / proven cause / KB applicability.
   Citation ที่ชี้บรรทัดถูกไม่ได้แปลว่าประโยคนั้นสนับสนุนข้อสรุปจริง.
3. ส่ง case ID, prediction hash, field/claim ID, ACCEPT/CORRECT/UNRESOLVED,
   เหตุผลพร้อมบรรทัด, reviewer alias จริง และเวลาที่ตรวจพร้อม timezone.
4. Claim judgment ใน schema ใช้ SUPPORTED / UNSUPPORTED / UNCERTAIN;
   UNRESOLVED แปลงเป็น UNCERTAIN ไม่ใช่ SUPPORTED. ถ้าคำตอบ AI ผิด ให้เก็บ claim
   เดิมไว้และเขียนคำแก้ใน rationale; อย่าแก้ text/category/evidence ของ emitted claim.
5. เก็บข้อความยืนยันจริงพร้อมเวลาเป็น provenance แยกจาก schema JSON ที่ไม่รองรับ
   reviewed_at. CLI เป็นการบันทึกคำยืนยัน ไม่ตรวจพิสูจน์ตัวตนผู้ตรวจ.
6. ก่อนแก้ annotation ให้สร้าง working copy ของ corpus พร้อม schemas และ inputs;
   เก็บ original DRAFT ไว้. แก้เฉพาะ DEV ที่คนตรวจแล้ว; ห้ามส่ง HELDOUT เข้า tuning.
7. ใช้ tools/review_analyzer_case.py กับ --manifest และ --annotations-v2 ของสำเนา
   พร้อม --case-id, --reviewer-id และ --confirm-human-review หลังมีคำยืนยันจริงเท่านั้น.
   v2 review ไม่ทำให้ v1 กลายเป็น REVIEWED อัตโนมัติ. คำสั่งนี้เขียนไฟล์ จึงห้ามชี้ original.
8. ใช้ tools/eval_analyzer.py --mode full_investigation --split dev --manifest <copy>/manifest.v1.json
   --annotations-v2 <copy>/manifest.v2.dev-draft.json --grounding-reviews <actual-judgments.json>
   --output <new-output-directory> โดยไม่ใส่ --include-draft.
   Grounding JSON ใช้ schema_version 2.0 กับ judgments ที่คัดจาก queue เดิมเฉพาะ cohort;
   เติมเฉพาะ support_judgment/reviewer/rationale. Unknown IDs, stale hashes และ duplicates
   ถูกปฏิเสธ. เก็บ records ต้นฉบับ ไม่รวมคำตัดสินขัดแย้งด้วยการเขียนทับเงียบ ๆ.
9. รายงานค่าจาก semantics_v2.reviewed แยกจาก legacy v1 และ claim grounding;
   ค่า undefined/denominator 0 ต้องคง null. Pilot สามเคสไม่ใช่ general accuracy.

ถ้าไม่สะดวกแก้ JSON ส่งคำตัดสินตามข้อ 3 มาได้ แล้วจึงบันทึกตาม protocol โดยรักษา
คำแก้ของคุณ ไม่ต้องสร้าง reviewer alias หรือกด REVIEWED ให้เคสที่ยังไม่ได้ตรวจ.
