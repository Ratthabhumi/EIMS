## Research handoff update — 26 October 2026

The three vendor investigations below have now informed production code and regression tests:
Fortinet configuration identity, CTK symptom/cause separation with KB gates, and Windows 1129
symptom-only diagnosis. Do not repeat broad research on those resolved questions.
See GROUNDED_DIAGNOSIS_CHECKPOINT_20261025.md for source URLs and measured limits.

Remaining targeted research, only when it changes an implementation decision:
1. Trusted HTTPS/reverse proxy and installed Next.js browser session behavior: cookie scope,
   Origin/Host trust, logout/back-cache and multiple-worker throttling. Deliver official sources,
   version applicability and executable negative tests; research cannot replace actual browser QA.
2. Minimal owner/service/admin permission design for shared organization endpoints, customer
   forms and WebSocket. Compare least-privilege options; preserve closed defaults until tested.
3. Institutional session/audit retention: distinguish a proposed policy from an approved one.
   There is no approved universal seven-day period. Keep Analysis History outside auth cleanup.
4. Independent claim adjudication with small denominators, disagreement and abstention;
   AI-generated candidates and regression-derived examples must not become independent HELDOUT.

Return decision / source URL / applicability / uncertainty / smallest test / cost.
Defer model training, new vendors, broad competitor surveys and large infrastructure until
reviewed evidence demonstrates a specific benefit. Older questions below are historical.

# Research handoff for ChatGPT — 25 ตุลาคม 2026

## สถานะที่ยืนยันแล้ว

EIMS มี evaluation v1 เดิมและ semantics v2 แยกกัน, synthetic DEV 12 เคส
ยัง DRAFT ทั้งหมด, HELDOUT 5 เคสยังปิดไว้ ไม่มี human-reviewed accuracy.
Offline full investigation เรียก production logic จริง แต่ใช้ memory History,
local deterministic KB และปิด network/RAG/vector export. M2/M3 ยัง NOT_RUN.
แก้ production แยก PR สำหรับ shared summary object, unsupported Failed outcome,
CTK 2620 และ successful Fortinet config suppression. รายละเอียดอยู่ใน
ANALYZER_IMPLEMENTATION_MATRIX_V2_20261025.md และ PR แก้ correctness.

## งาน Research ที่ส่งต่อได้

ใช้ข้อมูลสังเคราะห์และเอกสารทางการเท่านั้น ไม่ต้องขอ customer logs.
ส่งกลับเป็นตาราง claim / primary source URL / version applicability /
ข้อความหลักฐานสั้น / สิ่งที่อนุมานไม่ได้ / test candidate / ความคุ้มค่า.
ไม่เปลี่ยน DRAFT เป็น REVIEWED และไม่ปรับคำตอบย้อนหลังเพื่อให้คะแนนดีขึ้น.

1. **Fortinet configuration events**: ตรวจความต่าง 0100044546/47,
   format/version, successful edit กับ failed edit และคำว่า error ในชื่อ setting.
   ยืนยันว่ากฎ suppression แคบปัจจุบันมีข้อจำกัดอะไร พร้อม negative controls.
2. **VMware CTK 2620**: แยกความหมาย error code จากสาเหตุเฉพาะ vSAN/ESXi
   และ explicit final job outcome. ห้ามนำ fix เฉพาะ environment มาใช้ทั่วไป.
   เสนอเงื่อนไข KB applicability และหลักฐานขั้นต่ำก่อนเสนอ remediation.
3. **Windows Group Policy 1129**: แยก Event ID / severity / description /
   network symptom / physical RCA. ตรวจชื่อ failure taxonomy ที่เหมาะสม;
   DNS, NIC, firewall ยังเป็น hypothesis จนมีหลักฐานเพิ่ม.
4. **วิธีประเมิน**: เสนอ protocol human adjudication และ claim-level grounding
   ที่รายงาน denominator, uncertainty, abstention, inter-rater disagreement,
   และ case leakage; แยก synthetic DEV agreement จาก external validity.
   ให้แบบที่ทำได้จริงภายในเวลาที่เหลือ ไม่เสนอ infrastructure ขนาดใหญ่.

## Primary sources ที่ตรวจแล้วและข้อจำกัด

- Microsoft: https://learn.microsoft.com/en-us/troubleshoot/windows-server/group-policy/applying-group-policy-troubleshooting-guidance
- Broadcom 442155: https://knowledge.broadcom.com/external/article/442155/snapshot-usage-on-esa-cluster-is-very-hi.html
  ยืนยัน CTK/2620 ในบทความเฉพาะ vSAN; ไม่พิสูจน์ root cause ของ synthetic ESXi.
- Fortinet staff: https://community.fortinet.com/fortigate-3/technical-tip-difference-between-logid-0100044547-and-logid-0100044546-which-are-generated-when-configuration-is-changed-in-the-fortigate-203472
  หน้าคู่มือ log-id ที่เคยลองเข้าตรงตอบ 403; version applicability ยังต้องตรวจ.

## สิ่งที่ควรตัดออกจากรอบนี้

Model training/download, production vector index, dashboard redesign,
large-scale benchmark และ vendor integration ใหม่. ใช้เวลากับ evidence,
human reference quality และ isolated regression ก่อนเพิ่มขนาดระบบ.
ผล Research เป็น candidate จนตรวจ source/tests จริง และไม่ใช่ human review แทนเจ้าของงาน.

## รอบ session/privacy — คำถามแคบที่ยังต้อง Research

Code source 77603388 เพิ่ม PostgreSQL revocation, idle/absolute expiry,
fixed-window throttle และ admin gate สำหรับ organization-wide search แล้ว.
ไม่ต้อง Research framework ใหม่หรือสั่ง train/model benchmark.

ให้ ChatGPT Research ส่ง primary source + ข้อจำกัด + test ที่ทำได้ สำหรับ:

1. Retention ของ expired/revoked sessions และ hashed login windows ใน self-hosted
   university demo: เก็บนานเท่าไรและสิทธิ์ผู้ดูแลอย่างไร โดยไม่ลบ History.
2. Trusted Next.js 16 reverse proxy: TLS/Host/Origin trust และ browser back-cache
   หลัง logout; แยกสิ่งที่ต้องทดสอบ browser จริงจากสิ่งที่ handler tests พิสูจน์ได้.
3. Minimal privacy threat model: unknown/encoded/multiline secrets, ข้อมูลผู้ใช้ที่
   ต้องเก็บเพื่อ correlation และ admin access ข้ามเจ้าของ. Regex ไม่ใช่ DLP.

ห้ามเสนอคำสั่งหลบ policy ที่ปฏิเสธ Dashboard startup. ดูผลทดสอบจริงที่
SESSION_LIFECYCLE_GATE_20261025.md และ review packet ใหม่ใน
evidence/20261025-lifecycle/review/README.md. Claims ยังไม่มี human review.
