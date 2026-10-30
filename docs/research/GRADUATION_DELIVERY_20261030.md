## Scientific review integrity closure — 30 October 2026

Source `a2707b55fb1bc867feb3f55cc1156cc042058a45` continues PR #10 from `78ee60a`.
No production Analyzer/Auth/History, infrastructure-audit, scorer formula or Gold changes.
Six new regressions failed before correction: blank reviewer, blank rationale, padded AI
alias, modified claim category, removed citation and substituted in-range citation.
Validators now reject these; review corrections belong in rationale/annotation copies,
not silently rewritten emitted claims. Whitespace handling is consistent across v1/v2
receipts, legacy manual reviews and the existing review CLI.

One hermetic integration test runs the existing pipeline on temporary copies only:
actual prediction → synthetic review receipt → reviewed-only cohort (1 case, 0 DRAFT,
0 HELDOUT) → support 1/2, unsupported 1/2, unresolved 1 → stale hash/unknown claim/
conflicting duplicate rejection → removed judgment lowers coverage → modified source
hash rejection → original corpus unchanged. Artificial test judgments are not Gold.
Alias checks are validation of an assertion, not authentication of a human reviewer.

Local relevant suite: **267 passed, 1 skipped** (Windows symlink privilege), 2 warnings.
[Before/after JUnit and mode comparison](evidence/20261030-review-integrity/).
PostgreSQL/full browser are not rerun locally; required CI supplies isolated PostgreSQL.
Final head/check-out SHA and CI artifacts are recorded in PR #10, not inferred from old CI.

M0 rule_only, M1 rule_kb and native full investigation ran 12 DEV each at the same clean
source/input/annotation/scorer controls, zero errors. M0 invokes no KB; M1 and full invoke
KB for 12 cases. Full includes synthesis and memory History, so latency boundaries differ.
No superiority or accuracy claim. Full prediction hashes unchanged 12/12, still 77 claims,
0 human judgments. Existing priority and nine-case packets remain current; no duplicates.
Snapshots: `evaluation/analyzer/results/20261030-review-integrity-{rule_only,rule_kb,full_investigation}`.
Current scorer formulas unchanged; validator/runner code hashes changed explicitly.

Scientific Chapter 4 status: **INCOMPLETE** until authentic reviews. Citation coordinates
and semantic support are separate metrics; UNCERTAIN excludes a claim from the binary
support denominator and must remain visible. Missing judgments reduce coverage rather
than become supported. Annotation review and claim review are distinct decisions.
Legacy v1 manual free-text item identifiers are not structured v2 claim IDs; use the v2
claim queue for claim-level adjudication. Do not mix these protocols as one denominator.

PR #10 still targets #5; audit #9 remains `90324cf` and is not included. GitHub returned
"Branch not protected" for main protection and no repository rulesets; this does not
supply owner merge authorization. No merge performed. Local audit ref is unavailable;
no combined-tree test is claimed. Existing remote file inventories remain the handoff.
No approved browser listener on 3009/3449; do not retry equivalent prohibited startup.
Status: **ENGINEERING_READY within covered CI contracts / SCIENTIFIC_REVIEW_PENDING /
BROWSER_ACCEPTANCE_BLOCKED** only when final CI is green. No installed-release certification.

# EIMS — ชุดส่งจบ 30 ตุลาคม 2026

## A–C. ขอบเขตและสถานะ

Graduation Core: Analyzer หลาย vendor, evidence/chronology, RCA ที่แยกข้อเท็จจริงจาก
สมมติฐาน, KB applicability, History ของเจ้าของข้อมูล, auth และ reproducible evaluation.
Extended EIMS: customer tenancy/invitations, WebSocket streaming, vendor/model/RAG ใหม่
และ Inventory redesign เลื่อนออกจากการส่งจบรอบนี้. ไม่เปิดสิทธิ์เพิ่มเพื่อให้เดโมผ่าน.

เริ่มจาก PR #5 `f777e9c5c085e1db366b410f0ea07ed6d2a82472`; main ยัง `bf634d9`.
มี PR #6–#9 เป็นสาย audit ใหม่ จึงแยก branch `codex/graduation-delivery-20261030`
จาก #5 ไม่แก้ branch ของ audit และไม่อ้างว่าทดสอบรวมกับ #6–#9 แล้ว.
ใช้ evaluator, tests, fixture, review validator และ packet เดิมทั้งหมด.

งานใหม่: regression การ upgrade ฐานทดสอบที่มี History/เจ้าของสองคนแล้ว, ตรวจ hash
packet สามเคสเดิม, packet เสริมอีกเก้าเคส, ตรวจสถานะ PR พร้อมรายการไฟล์ครบ,
ขั้นตอน operator และสคริปต์พูดเดโม. ไม่มีการแก้กฎ Analyzer รอบนี้.

## D–G. หลักฐานและความถูกต้อง

ไม่พบ defect ใหม่ที่จำเป็นต้องแก้ production จากงานรอบนี้ จึงไม่เพิ่ม rules.
ข้อมูลเดิม: DEV 12 DRAFT, 77 claims, human judgments 0, HELDOUT ไม่รัน.
prediction hashes ใน packet fort_config/esxi_tracker/win_policy ตรง snapshot
`20261026-terminal-scope-full` ทั้งสามเคส จึงไม่สร้าง packet สามเคสซ้ำ.

- [เริ่ม review สามเคส](evidence/20261025-grounded/HUMAN_REVIEW_PACKET_TH.md)
- [เก้าเคสที่เหลือ](DEV_REVIEW_REMAINDER_20261030.md)
- รายงาน claims และข้อเสนอ AI ไม่ใช่ Gold; ACCEPT/CORRECT/UNRESOLVED ต้องมาจากคนจริง
- 8 counterexamples เดิมเป็น regression-related candidates ไม่ใช่ independent Gold
- Explicit terminal positive cases มีใน candidates; ไม่มีใน frozen DEV
- v2 ยังไม่ใช่ multi-session scorer; อย่าอ้างผลด้าน association จากตัวเลข v2

Research ที่นำมาใช้แล้ว: vendor-specific evidence boundaries, UNKNOWN เมื่อหลักฐาน
ไม่พอ, source provenance, reproducibility, ownership และ deny-by-default.
ยังไม่ทดลอง: independent diagnostic quality, authenticated HTTPS browser, WSS,
customer scope และ M2/M3. ไม่ทำ broad research ซ้ำ.

## H–J. Migration และการรันจริง

เพิ่ม `test_populated_parent_upgrade_preserves_history_ownership_and_sessions`:
สร้าง schema สังเคราะห์ใหม่, upgrade จริงถึง `8a2b4d6f9c1e`, ใส่ผู้ใช้สองคนและ
History JSON คนละรายการ, เก็บ row snapshots, upgrade ถึง `e1a202610250`,
เปรียบเทียบทุก field, login ผ่าน router จริง, ตรวจ History ตามเจ้าของ,
dispose/reconnect pool, logout และ copied token ถูกปฏิเสธ แล้วตรวจ rows อีกครั้ง.
ไม่มี downgrade/drop schema/reset/operational data. Reconnect ไม่ใช่ OS restart.

Local targeted run: **SKIPPED 1** เพราะไม่มี EIMS_TEST_DATABASE_URL;
container สังเคราะห์เดิมหยุดอยู่ตั้งแต่สามวันก่อน ไม่เริ่ม runtime ซ้ำเพื่อฝืนสถานะ.
ผลรันจริงของ test นี้ต้องดู CI exact HEAD ที่แนบใน PR; ไม่ใช้ skip อ้าง PASS.
ผล local เดิม 286 passed/1 skipped เป็นหลักฐานวันที่ 26 ต.ค. ไม่ใช่ผลรันใหม่วันนี้.

ไม่พบ listener ที่ browser ports 3009/3449. Browser HTTPS = BLOCKED/NOT_TESTED.
เหตุเดิม: automatic approval ปฏิเสธ startup ว่า “blocked by policy”. ไม่ใช้ launcher,
port หรือ insecure cookie อื่นหลบ. Deployment/USB = NOT_TESTED.
Screenshot เก่าเป็น backup ของผลเก่าเท่านั้น ไม่รับรอง secure flow ปัจจุบัน.

## I. ตารางสิทธิ์ของ Graduation Core

| Actor | Resource / action | Scope ปัจจุบัน |
|---|---|---|
| Engineer/user | Analyzer History, feedback, follow-up | เฉพาะ username เจ้าของ |
| Engineer/user | Global Search | Analyzer results ตามเจ้าของ; ไม่เปิด shared providers |
| Admin | Evaluations, assets/OCR, telemetry, timeline, shared search | สิทธิ์ข้อมูลส่วนกลาง; ต้องตรวจ role/session ปัจจุบัน |
| Customer | Evaluation form | ยังปิดสำหรับผู้ไม่มี admin; scoped invitation เลื่อน |
| Collector/service | Telemetry ingestion | credential ตาม gate เดิม; ห้ามแจก admin key ให้ collector เพื่อเดโม |
| Anonymous/revoked/expired | Protected reads/writes | ปฏิเสธ |
| Demoted admin | Shared resources | ปฏิเสธ แม้ token เคยมี role เดิม |
| User | PDF จาก owned result ใน Dashboard | templates escape แล้ว; actual browser PDF ยังไม่ทดสอบ |
| Admin | Obsidian/server export | privileged export gate เดิม; ไม่รัน filesystem export รอบนี้ |
| ทุก actor | Secure WebSocket | ปิดก่อน accept; ไม่ใช่ authenticated streaming ที่เสร็จแล้ว |

## K–M. Release และสิ่งที่คุณต้องทำเอง

Engineering validation กับ scientific validation เป็นคนละ gate. Human Review ไม่ขวาง
การ merge evaluation infrastructure แต่ห้ามใช้ผล DRAFT อ้าง Accuracy.
ยังไม่มีคำอนุมัติ merge จึงไม่ merge main. รายละเอียด stack:
[merge-readiness](MERGE_READINESS_20261030.md).

1. อ่านสามเคสแรกแล้วส่ง `case_id + ACCEPT/CORRECT/UNRESOLVED + fields/claim IDs +
   เหตุผล + reviewer alias จริง` ไม่ต้องรับรองทุก claim ถ้ายังไม่ทราบ.
2. จัด runtime HTTPS ที่ได้รับอนุญาตและใช้ข้อมูลสังเคราะห์เท่านั้น จากนั้นทำตาม
   [operator runbook](OPERATOR_DEMO_20261030.md). หากเปิดไม่ได้ ให้ส่ง error ที่ลบ
   credentials แล้ว ไม่ต้องวนเปลี่ยนพอร์ตหรือปิด Secure cookie.
3. อนุมัติ merge stack เป็นขั้นตอนเมื่อพร้อม; PR #5 ยังมี browser/deployment gates.
   งาน audit #6–#9 ต้องประเมินแยก ไม่ถือว่าเป็นส่วนหนึ่งของเดโมที่ตรวจแล้ว.

Milestone ถัดไป: review จริงสามเคสพร้อม hashes → validate records → วัด pilot ตาม
denominator จริง; HTTPS flow ผ่านพร้อมหลักฐาน → freeze demo SHA เดียว.
ไม่เพิ่มฟีเจอร์หลังจุดนี้จนกว่าจะพบ defect ที่กระทบเดโม/ข้ออ้างวิจัยจริง.

## Research handoff ให้ ChatGPT

ค้นเฉพาะคำถามที่ review ตอบไม่ได้: ข้อความ log สนับสนุน claim ที่เลือกหรือไม่,
KB ใช้กับ product/version นี้หรือไม่, และหลักฐานขั้นต่ำสำหรับผูก session กับ outcome.
ส่งกลับ `claim/question | official URL | version/context | supported | not proven |
needed evidence | proposed test`. ไม่แก้ labels แทนคนและไม่สร้าง reviewer receipt.
คำถาม customer scope/WSS/tenant เลื่อน เพราะอยู่นอก Graduation Core.

## Chapter 2–5 update

2: ใช้ research เป็นหลักการออกแบบ ไม่อ้างเหนือกว่า SIEM อื่น.
3: อธิบาย production logic + isolated experiments + owned History และการแยก scope.
4: แสดง denominators/CI/source hashes; current human-reviewed denominator = 0.
   Populated migration เป็น engineering experiment; ไม่ใช่ diagnostic accuracy.
5: ข้อจำกัด synthetic selection, missing positive terminal DEV, session association,
   browser/USB และ external validity. ไม่รายงาน warm offline timing เป็น browser latency.
