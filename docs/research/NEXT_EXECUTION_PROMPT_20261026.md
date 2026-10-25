# EIMS — คำสั่งเดินงานต่อเนื่อง (26 ตุลาคม 2026)

ทำงานต่อจาก GitHub จริงของ Ratthabhumi/EIMS โดยเริ่มตรวจ PR #2–#5, HEAD,
CI และ working tree ใหม่ทุกครั้ง อย่าอ้าง SHA หรือผลทดสอบเก่าว่าเป็นสถานะปัจจุบัน.
อ่าน GROUNDED_DIAGNOSIS_CHECKPOINT_20261025.md และ matrix ก่อนลงมือ;
ไม่ย้อนทำสิ่งที่มีหลักฐานเสร็จแล้ว. เป้าหมายคือระบบวิเคราะห์ Log ที่ตรวจสอบข้อสรุปได้
และเดโมได้จริง ใช้ token เท่าที่จำเป็น ไม่ขยาย scope เพื่อเพิ่มจำนวนฟีเจอร์.

## 1. ปิดช่องว่างคุณภาพก่อนเพิ่มความซับซ้อน

- ตรวจ narrative summary, RCA, evidence, uncertainty และ KB applicability ร่วมกัน;
  typed fields ถูกไม่ได้แปลว่าข้อความอธิบายถูก. หา counterexamples ที่หักล้างกฎได้.
- ขยาย synthetic candidates เฉพาะช่องว่าง: explicit Success/Failed/Warning,
  failure แล้ว recovered, หลาย session สลับกัน, timestamp ข้ามวัน/timezone,
  missing/truncated/multiline logs, contradictory fields และ unrelated bundle.
- แยก candidate/regression fixtures ออกจาก frozen DEV/HELDOUT และบันทึกที่มา.
  อย่าเปลี่ยน scorer/labels หลังเห็นผลเพื่อทำคะแนนให้ดีขึ้น. ถ้าต้องเปลี่ยน semantics
  ให้ version ใหม่พร้อมเหตุผลและรักษาผลเดิมไว้.
- เมื่อ reproduce defect ได้ ให้เพิ่ม regression ที่ล้มเหลวก่อนแก้ แล้วแก้ให้แคบ
  พร้อม negative controls; คง UNKNOWN เมื่อหลักฐานไม่พอ.

## 2. ทำเส้นทางเดโมให้พิสูจน์ได้

- ตรวจ approved local runtime และคำสั่งที่บันทึกไว้ ไม่เปิด service ซ้ำ.
- ถ้ามีสภาพแวดล้อม trusted HTTPS ที่ได้รับอนุญาตแล้ว ให้ทดสอบ browser จริง:
  login → Windows raw text → Veeam/VMware bundle → evidence source lines →
  History reload/retrieve → สองผู้ใช้แยกข้อมูล → logout/replay/back navigation/expiry.
- หาก runtime ยังถูก policy ปฏิเสธ ให้รายงาน BLOCKED พร้อมเหตุผลเดิม;
  ห้ามเปลี่ยน launcher/port/cookie เพื่อหลบ และทำงาน isolated ที่เหลือต่อ.
- ตรวจ catalog 163/Windows 141 กับ fixture ปัจจุบัน; หากต่างให้สืบการเปลี่ยนจริง
  ไม่บิดข้อมูลให้ตรงเลขเก่า. USB end-to-end เป็น NOT_TESTED จนรันจริงอย่างได้รับอนุญาต.

## 3. ปิดข้อจำกัดสิทธิ์อย่างมีแบบแผน

- ทำ permission matrix ที่มี actor/resource/action ชัดเจนสำหรับ customer form,
  assets/OCR, telemetry ingestion/query, timeline, evaluation และ WebSocket.
- ปัจจุบัน Secure Mode จำกัด shared APIs เป็น admin/service และปิด WebSocket;
  อย่าเรียกสิ่งนี้ว่า user workflow ที่สมบูรณ์. หากต้องเปิด ให้ใช้ scoped authorization
  พร้อม owner/tenant predicates และทดสอบ direct URLs, forged headers, pagination,
  revoke/expiry และ cross-user access ก่อน. ไม่ใช้ client identity เป็นหลักฐานสิทธิ์.
- ทดสอบ migration จาก schema lineage จริงในฐานข้อมูลสังเคราะห์แยก หาก dependencies
  พร้อม; แยกผลจาก minimal-parent rehearsal ที่ผ่านแล้ว. ทดสอบ reconnect กับ
  process restart เป็นคนละข้อ. Operational migration/cleanup ต้องได้รับอนุมัติเฉพาะงาน.

## 4. Research เฉพาะที่เปลี่ยนการตัดสินใจ

ใช้ official vendor/framework documentation และระบุ version applicability.
เริ่มจากคำถามที่ reproduce ได้หรือขาดหลักฐานจริง: trusted proxy/session browser,
least-privilege shared endpoints, retention ของสถาบัน และ independent adjudication.
ส่งคำถามที่ต้องค้นลึกให้ ChatGPT Research ในรูป decision/source/uncertainty/test/cost.
Research ให้ข้อเสนอ ไม่ได้อนุมัตินโยบายแทนเจ้าของ และไม่แทนผล runtime.
ปรับ architecture/framework/แผนได้เมื่อมีหลักฐานว่าดีกว่า พร้อม migration cost,
small experiment และ rollback; อย่ายึดของเดิมเพราะลงทุนไปแล้ว และอย่า rewrite
หรือเพิ่ม RAG/model/vector stack เพียงเพราะระบบอื่นมี.

## 5. วัดผลและส่งงานจบเป็นรอบเดียว

- รัน checks ที่เกี่ยวกับ diff และ required CI; ไม่รันทุกรายการซ้ำโดยไม่มีเหตุผล.
- Freeze source/config/input hashes; before/after ใช้ cohort และ evaluator เดียวกัน.
  รายงาน execution errors, unsupported claims ที่ตัดสินจริง, abstention และ denominators.
- คง DEV DRAFT จนเจ้าของตรวจจริง; ห้ามสร้าง reviewer alias/receipt หรืออ้าง Accuracy
  จาก DRAFT. Human review ไม่ต้องขวางงาน engineering อื่น.
- ส่ง packet ภาษาไทย source-first ของ fort_config, esxi_tracker, win_policy พร้อม
  AI proposal/บรรทัดสนับสนุน/ข้อไม่แน่ชัด/สิ่งให้คนตัดสิน. อย่าสร้าง packet ซ้ำ
  ถ้า prediction hash ไม่เปลี่ยน. เมื่อมี judgments จริง จึงวัดเฉพาะขอบเขตที่ตรวจแล้ว.
- Commit แบบแยก production fixes/evaluation evidence, push ไป branch/PR ที่เหมาะสม,
  ตรวจ CI ของ HEAD ที่ push จริง. ไม่ merge main, rewrite history หรือทับ demo changes.
  PR stack ต้องตรวจ dependency และ rerun CI หลัง retarget เมื่อได้รับอนุมัติ merge.
- อัปเดต Research matrix: IMPLEMENTED / VERIFIED / PARTIAL / NOT_RUN / DEFERRED
  พร้อม code/test/result links. สรุปสิ่งที่เปลี่ยน, SHA, PR, CI, demo sequence,
  limitations และงานค้างเรียงความสำคัญในรายงานเดียว.

ทำทุกงานที่ทำต่อได้อัตโนมัติ ไม่ถามยืนยันทีละขั้น. รวมเฉพาะการตัดสินใจของคน
ที่จำเป็นจริงไว้ท้ายรายงาน. ห้ามใช้ customer logs/credentials หรือแตะ production DB,
History, vector store, USB installations โดยไม่มี authorization ตามขอบเขตนั้น.

## เกณฑ์จบรอบ

โค้ดและหลักฐานขึ้น GitHub, exact-HEAD CI ผ่าน, งานที่รันไม่ได้ระบุ NOT_TESTED/BLOCKED
พร้อมเหตุผล, ไม่มี fabricated review/accuracy, และ next action ชัดเจน.
ยังไม่ประกาศ secure release candidate จน browser acceptance และ deployment gates ผ่าน.
