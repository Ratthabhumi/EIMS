# EIMS — ผลแก้ RCA และทดสอบ release gates (25 ตุลาคม 2026)

## A–D. งานจริงและ before/after

Source ที่ freeze: `348f892719cc0e839cd2813d344d26e672c883fd` บน PR #5 เดิม.
ก่อนแก้ regression ใหม่ล้มเหลว 11 รายการ; หลังแก้ combined suite ผ่าน **273**,
ข้าม **1** เพราะสิทธิ์ Windows symlink, warnings เดิม **19**. รวม PostgreSQL **31** tests.
หลักฐาน [JUnit ก่อน/หลัง](evidence/20261025-grounded/) และ
[per-case claim differences ทั้ง 12 เคส](evidence/20261025-grounded/before-after.json).

| เคส | ก่อนแก้ | หลังแก้ที่รันจริง |
|---|---|---|
| fort_config | เรียก logid ว่า diagnostic; มี unknowns เรื่อง CTK/VMDK/lock | configuration event 0100044547, informational edit สำเร็จ, ไม่มี observed failure/causes; ขอ cfgpath/cfgattr/version เพื่อ audit |
| esxi_tracker | เสนอ missing/corrupt/mismatch/stale cleanup จาก deletion failure | ยืนยันเพียง CTK operation failure/result 2620; physical RCA และ terminal outcome UNKNOWN; first/last failure ยังบรรทัด 1/2 |
| win_policy | fallback process crash, config corruption, CPU/Memory | Group Policy Event 1129 ติดต่อ DC ไม่ได้; ขอ Operational log/ActivityID และ diagnostics; ไม่ยืนยัน DNS/LDAP/network เป็นต้นเหตุ |

แก้ `incident_extract.py`, `summary.py`, `vendor_knowledge.py` และเพิ่ม helper
`observed_summary.py` ขนาดเล็ก. Limitations อาศัย signal จริง; informational-only
records ไม่ถูกเติม physical-cause investigation โดยอัตโนมัติ. CTK evidence ใช้
ข้อความจากต้นฉบับจริง. KB 418256 ต้องมีอาการ invalid/opening CTK หรือ lock เพิ่มเติม;
bare deletion/2620 ไม่พอ. vSAN ESA/vVOL gates เดิมคงอยู่. KB match เป็น candidate
ให้ตรวจ version/environment ไม่ใช่คำอนุญาตให้ทำ remediation.

Regressions ครอบคลุม 8 source families, failed/success/contradictory Fortinet fields,
1129 ที่ไม่มีข้อความหรือ provider ไม่ตรง, การคง explicit Success/Failed/Warning
หลัง CTK failure, unsupported physical causes และ inapplicable KB.
แก้ assertion เดิมสองจุดตามหลักฐาน: ไม่บังคับเสนอ KB 418256 จาก CTK deletion อย่างเดียว
และ evidence ต้องเป็นบรรทัดต้นฉบับเต็ม. **ไม่ได้แก้ Gold labels เพื่อให้คะแนนดีขึ้น**.

Before snapshot ใช้ `20261025-session-lifecycle-full` source `77603388` ซึ่งส่วน
Analyzer/evaluator ไม่เปลี่ยนถึง `6b368d9` (ตรวจ git diff แล้ว). After:
[20261025-grounded-diagnosis-full](../../evaluation/analyzer/results/20261025-grounded-diagnosis-full),
clean tree, PYTHONHASHSEED=0, 3 warmups/3 repeats. Input/annotation, scorer, runner,
semantics v2, investigation adapter และ grounding hashes ตรงกันทั้งหมด.
12 DEV รันครบ, 0 errors, 0 HELDOUT; v2 fields เหมือนเดิม 12/12 แต่ narrative claims
เปลี่ยน 12/12. Claims ลด 135→77 จากการตัดข้อความที่ไม่รองรับ; **จำนวนลดไม่ใช่
หลักฐานว่า semantic precision ดีขึ้น** เพราะยังไม่มีคนตัดสิน claims.

## E. Migration / retention / concurrency

PASS บน dedicated test DB เท่านั้น (`127.0.0.1:55439`, eims_integration_test).
ทดสอบสร้าง schema สังเคราะห์ใหม่ที่มี User/History, stamp parent `8a2b4d6f9c1e`,
เรียก **Alembic command.upgrade(head)** จริงผ่าน caller-owned connection,
ตรวจ version table เป็น `e1a202610250`, ตรวจตาราง/indexes, login/session/logout/replay,
dispose connection pool แล้ว reconnect และ login ใหม่. ไม่ใช่เพียง ORM create_all.
ไม่ได้จำลอง parent migrations ทั้งระบบหรือ process/OS restart; schema ขั้นก่อนหน้า
เป็น minimal auth-relevant fixture. Schema สังเคราะห์เก็บไว้ตรวจ ไม่ drop/downgrade.
Migration rehearsal ที่แก้เป็น command จริงผ่าน และรวมใน suite สุดท้ายแล้ว.

เพิ่ม `session_maintenance.py` กับ CLI `tools/maintain_analyzer_sessions.py`:
default dry-run, ต้องระบุ retention, batch 1–1000 ต่อ table, เลือกแถวหมดอายุหรือ
revoked เกิน retention; ไม่ลบ active session/current throttle window/Analysis History.
ใช้ row locks + SKIP LOCKED, transaction เดียว rollback ทั้งสองตารางเมื่อ error.
ทดสอบ rollback, dry-run, batch, active records และ worker ที่ชน lock จริงใน PostgreSQL.
ทดสอบ 20 concurrent reservations ผ่านคนละ connection: อนุญาต 8, HTTP-exception 429
อีก 12. นี่คือ shared DB contention; **multiple Next OS processes ยังไม่ได้ทดสอบ**.

CLI dry-run กับ test DB ผ่าน (eligible 0/0); ไม่รัน --apply กับฐานข้อมูลใช้งานจริง.
7 วันเป็นค่าตัวอย่างที่ใช้ใน synthetic tests ไม่ใช่ข้อกำหนด OWASP หรือมหาวิทยาลัย.
ยังไม่ติดตั้ง scheduler; operator เรียกครั้งละหนึ่ง batch เพื่อควบคุมผลกระทบ.

```powershell
# ใช้ test DB นี้สำหรับ rehearsal เท่านั้น
$env:EIMS_MAINTENANCE_DATABASE_URL='postgresql+asyncpg://eims_test:eims_synthetic_only@127.0.0.1:55439/eims_integration_test'
python tools/maintain_analyzer_sessions.py --retention-days 7 --batch-size 100
# --apply เปลี่ยนข้อมูล auth: ใช้เฉพาะ retention/DB ที่เจ้าของอนุมัติแล้ว
```

Recovery: เก็บ schema auth ใหม่ไว้, deny ingress ระหว่างแก้ migration/config,
ตรวจ Alembic version แล้วกลับไปใช้ binary ที่รองรับ schema; ไม่ drop auth tables
หรือ reset History เป็น rollback อัตโนมัติ. การ deploy จริงยังต้อง owner authorization
และ backup approval. ยังไม่ได้ apply migration บน operational DB.

## F. Browser และสิทธิ์ข้อมูลส่วนตัว

Browser/HTTPS **NOT_TESTED**: ไม่มี approved runtime บน prepared ports;
การเริ่ม Dashboard แบบเดิมเคยถูก automatic approval ปฏิเสธว่า **blocked by policy**.
รอบนี้ไม่เริ่ม equivalent listener หรือใช้ insecure cookie หลบข้อจำกัด.
สำหรับ operator: หลัง environment ได้รับอนุญาต ให้ตั้ง trusted HTTPS origin,
server-controlled backend URL, dedicated synthetic backend/DB แล้วเรียก
`node tools/verify_secure_dashboard.cjs` ด้วย EIMS_TEST_BROWSER_BASE_URL และ
EIMS_PLAYWRIGHT_MODULE ตาม environment. ตรวจ login UI→upload→evidence→History
reload→สองผู้ใช้→logout/back navigation/expiry/light-dark; อย่าแทรก bearer token.
ต้องตรวจ copied-session replay และ proxy header trust เพิ่มด้วย. ไม่มีผล browser
หรือภาพ screenshot ใหม่ที่นำมาอ้างใน checkpoint นี้.

| ทางเข้าข้อมูล | การแก้/หลักฐาน | ขอบเขต |
|---|---|---|
| Analyzer History/search/feedback/stats/follow-up/vector | regressions เดิมรันผ่านร่วม | Owner predicates และ shared-vector denial เดิม |
| Service Evaluation, Assets/OCR/image, audit, timeline, telemetry queries | Secure Mode ใช้ current admin/service credential ที่ router; สอง users ถูก 403, missing/tampered JWT ถูก 401 | admin เท่านั้นสำหรับข้อมูลส่วนกลาง; legacy/null owner ไม่แจกสิทธิ์อัตโนมัติ |
| Evaluation writes | แก้ direct call dependency ที่ signature ไม่ตรง เป็น Depends จริง; admin create/read ผ่าน | Secure external customer form ถูกจำกัดด้วย ต้องออกแบบสิทธิ์แบบเฉพาะก่อนเปิด public |
| Telemetry ingestion/EVTX | Fingerprint header อย่างเดียวไม่พอ; เพิ่ม admin/service gate และใช้ validator เดิมกับ EVTX | validator ตรวจรูปแบบ ไม่พิสูจน์ mTLS; proxy ต้อง strip header/restrict backend |
| WebSocket alerts | Secure Mode close 1008 ก่อน accept แม้ส่ง forged query token | authenticated browser transport ยังไม่พร้อม; demo mode เดิม |
| PDF/Obsidian | template escaping และ admin export gate เดิม | ไม่รัน privileged filesystem export/actual browser PDF |

Negative tests ครอบคลุม alternate direct URLs, pagination, OCR image export และ
forged certificate fingerprint. แก้ logger ที่เคย echo malformed fingerprint
ให้เป็นข้อความทั่วไป. Admin-wide access เป็น minimum closed policy ชั่วคราว;
owner ยังต้องยอมรับขอบเขต/retention ก่อน deploy. ไม่รับรองระบบ IAM ทั้งองค์กร.

## G–H. Gold / research / packet

[Human Review Packet ภาษาไทยชุดเดียว](evidence/20261025-grounded/HUMAN_REVIEW_PACKET_TH.md)
มีต้นฉบับก่อน AI, คำอธิบายศัพท์, file/line, vendor source, สิ่งที่ไม่ทราบ,
คำถาม accept/correct/unresolved และ hashes ใหม่. เตรียม 24/77 claims ของสามเคส;
reviewed จริง **0/77**, DEV reviewed **0/12**, HELDOUT 5 ยัง reserved/DRAFT.
เพิ่ม candidates terminal outcome สองเคสใน `evaluation/analyzer/candidates/`
แยกจาก DEV/HELDOUT; เป็น AI-generated/เกี่ยวข้องกับ regressions ไม่ใช่ independent Gold.

| Research ที่ใช้ | Primary source / ขอบเขต | สถานะ |
|---|---|---|
| Fortinet config event identity | [Fortinet staff](https://community.fortinet.com/fortigate-3/technical-tip-difference-between-logid-0100044547-and-logid-0100044546-which-are-generated-when-configuration-is-changed-in-the-fortigate-203472); ไม่ยืนยัน synthetic format ของ FortiOS release ใด | IMPLEMENTED + regression VERIFIED |
| CTK failure ไม่เท่ากับ physical cause | [Broadcom 442155](https://knowledge.broadcom.com/external/article/442155/snapshot-usage-on-esa-cluster-is-very-hi.html), [418256](https://knowledge.broadcom.com/external/article/418256/virtual-machine-backups-fail-due-to-lock.html); environment/อาการต้องตรงก่อนใช้แนวทาง | IMPLEMENTED + gates VERIFIED |
| Group Policy symptom vs cause | [Microsoft guidance](https://learn.microsoft.com/en-us/troubleshoot/windows-server/group-policy/applying-group-policy-troubleshooting-guidance), [startup-specific KB](https://learn.microsoft.com/en-us/troubleshoot/windows-server/group-policy/netlogon-event-id-5719-or-group-policy-event-1129); startup เป็นบริบทเฉพาะไม่ใช่เหตุของทุก 1129 | IMPLEMENTED + regression VERIFIED |
| Retention/transport trust | ไม่มี universal duration; OWASP guidance เดิมใช้เป็นกรอบ ไม่ใช่ certification | PARTIAL; institution/HTTPS decisions pending |
| Human grounding / M2 / M3 | ไม่มี independent judgments/model experiment | NOT_MEASURED / DEFERRED |

## I–L. GitHub, decisions และ release readiness

ใช้ PR #5 เดิมเพื่อหลีกเลี่ยง feature stack ใหม่. main/demo checkout/USB D: E:
และ historical snapshots เดิม preserved. CI ต้องตรวจ publication HEAD ของรอบนี้;
ผลเก่าไม่รับรอง source ใหม่. รายละเอียดผลอยู่ใน PR description/Actions.

**ยังไม่พร้อมประกาศ secure RC**. ชุดตัดสินใจที่ต้องให้คนทำจริงมีเพียง:
1. Review labels/claims ใน packet ใหม่ด้วยหลักฐาน ไม่ต้องรับรองทุกข้อรวดเดียว.
2. อนุมัติ trusted runtime/proxy, admin-only external routes, disabled secure
   WebSocket, institutional retention และ backup/migration plan ก่อน rollout.
3. อนุมัติ merge stack หลัง gates: #2 cff0008 → #3 5810a25 → #4 443676b → #5
   publication HEAD. หลังแต่ละ merge/retarget ให้รัน CI ใหม่; ไม่มี force push,
   hidden merge หรือการเปลี่ยน main ในรอบนี้.

Milestone ถัดไป: HTTPS browser flow ผ่านจริง + reviewer ตัดสินสามเคสและ claims
ด้วย current hashes. จากนั้นจึง freeze reviewed cohort/วัดคุณภาพ; ห้ามใช้ DRAFT
agreement แทน accuracy. Demo 5 นาที: 30s ขอบเขต → 60s Fortinet informational
→ 90s CTK failure/UNKNOWN RCA → 60s Windows DC symptom/source lines
→ 60s History/session artifacts + ข้อจำกัด/review packet. Offline HTML ใช้ fallback
ได้ แต่ไม่ใช่หลักฐาน login/History browser end-to-end.
