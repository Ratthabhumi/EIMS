# ชุดตรวจหลักฐานก่อนดูคำตอบ AI

เลือก 3 เคสตามลำดับที่เจ้าของกำหนด ไม่ใช่การสุ่ม และไม่ใช่ review ครบทั้ง cohort.
หน้า HTML แสดงต้นฉบับก่อนข้อเสนอ AI แล้วจึงเปิด claim พร้อม file/line/context.
ไม่มีการส่ง decision อัตโนมัติ ไม่มี reviewer/receipt และทุก judgment ยัง NOT_REVIEWED.

| Case | Claims ที่เตรียมให้อ่าน | Prediction hash |
|---|---:|---|
| [fort_config](fort_config.html) | 9 | `1a4860702225dce055b62b6eedfbb73158fb7424e14cee33382aec91a302f091` |
| [esxi_tracker](esxi_tracker.html) | 12 | `b8851229ca3933f5fd98cb5a2027a5cbb3c5c40feb0610336821b5904be3eafe` |
| [win_policy](win_policy.html) | 15 | `de017e4a7e7e1b0159dd18f6b3668b96be0fd3405dcd8e3980b0e8b7f8187e10` |

เตรียม 36/135 claims จาก 3/12 DEV; human judgments จริงยัง 0/135.
ใช้ Human Review Packet เดิมเพื่อส่ง accept/correct/unresolved พร้อมเหตุผลและบรรทัดหลักฐาน. การยืนยัน v2 ไม่รับรอง v1 อัตโนมัติ. ใช้ claim_grounding_queue.json ของรัน 20261025-secure-checkpoint-full เท่านั้นเมื่อส่ง claim judgments; ห้ามผูกกับ queue เก่าหรือเปลี่ยน hash.
