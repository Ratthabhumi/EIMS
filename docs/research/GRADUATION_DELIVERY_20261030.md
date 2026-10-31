## Targeted Analyzer corrections — 1 November 2026

Start `19df042cdb736c991bd37a1f25e521c92bce3955`; implementation `a7b52915dcc38de2618c8588546bb556fb31bac0`. Publication HEAD/final CI/tested synthetic checkout are recorded in PR #10 after completion.

| Finding | Root cause / bounded correction | Before → after |
|---|---|---|
| Windows 1129 | parser lacked canonical diagnosticCode; exact GroupPolicy provider + explicit event field + supported DC-connectivity message now set the symptom category; observed_summary shares the symptom predicate | UNCLASSIFIED_FAILURE → WINDOWS-GROUP-POLICY-CONNECTIVITY; event ID remains 1129, physical RCA UNKNOWN, explicit outcome null |
| VMware | lexical severity missed timestamped Er(02); VMware-only prefix extraction recognizes Er(02), Wa(03), In(05) at record start | Information/false → Error/true for esxi_tracker; CTK technical failure/RCA boundaries unchanged |
| Fortinet | canonical build_evidence_items(records=...) selected only failures and dropped successful configuration observations | native sourceFile/line 1 + retained source context; overview gets coordinate references; new observed-0 INFORMATIONAL claim. Recommendations/limitations still have no direct citations |

Vmware mixed-level policy is now explicitly maximum observed level across records (Error > Warning > Information); valid prefix controls that record, legacy unprefixed lines retain lexical fallback. Filename and embedded Er/Wa tokens are not prefix signals. Veeam suppression unchanged. This is coverage of supported literal formats, not vendor-version certification. No external research performed; broader prefix/version variants remain out of scope until authoritative examples are supplied.

Fortinet citation does not make a configuration event a failure. Incident signal/noise definitions are unchanged; files-only legacy evidence selector remains failure-only, native routes use canonical source records. Overview stays UNCERTAIN and human support NOT_REVIEWED. Coordinates prove provenance, not overall health or causal correctness. Existing duplicate-basename rejection and privacy/source-context tests remain in force.

**RED:** 3 targeted native/full regressions failed at the starting source (missing category, wrong level, absent citation). **GREEN:** local full hermetic 298 PASS, 1 SKIP (Windows symlink privilege), 2 dependency warnings. Added six real PostgreSQL cases (three priorities × Thai/English), testing serialized metadata/summary/aiSummary after fresh SELECT and another user's denial; executed by synthetic CI. Extended isolated FastAPI parity to all three priorities. Existing BFF/PDF/build/USB and 8 counterexamples run in final CI, not live browser acceptance. See [before/after and per-case hashes](evidence/20261101-priority/).

**Protocol decision:** semantics_v2.py, scoring.py, manifests, labels and heldout lock are byte-unchanged. v2 already projects failure_type from canonical diagnosticCode; fixing production metadata changes predictions, not the definition/scoring contract. Full instrumentation now assigns the already-defined INFORMATIONAL evidence role to the emitted configuration observation; source/config hashes track adapter change. No silent replacement of historical scores or claim judgments.

Clean-source M0/M1/Full snapshots: `evaluation/analyzer/results/20261101-priority-{rule_only,rule_kb,full_investigation}`. Each executes 12 DRAFT DEV, zero errors, zero HELDOUT, zero human reviews. M0/M1 changed esxi_tracker and win_policy; Full changed those plus fort_config. Full claims 60 → 61. Root cause UNKNOWN and terminal outcome null retained in all three. Source/manifest/input/annotation/scorer/runner/adapter hashes retained. This is no diagnostic accuracy claim; reviewed-only metrics remain undefined.

**Review action:** priority packet hashes are stale for new predictions. Use [new source-first Thai priority delta](DEV_REVIEW_PRIORITY_DELTA_20261101.md), with current binding in REVIEW_BINDING_20261030.json. Previous priority hashes preserved in previous_binding. Other nine Full predictions unchanged, including prior recommendation delta's eight cases. No genuine judgments exist to transfer. Read raw logs first, then record actual case/claim decisions, alias, timestamp and rationale.

**Boundaries:** no auth/database architecture changes, operational DB, USB devices, service startup, main merge or infra PR modifications. HTTPS remains BLOCKED_NOT_TESTED because prior startup was rejected by policy and no approved runtime is available; no workaround. Physical USB/production NOT_TESTED. Infrastructure recovery XFAILs remain separate. Academic binaries remain STALE_PENDING_REBUILD; prior source-pinned reports describe earlier revisions and must incorporate this delta when rebuilding.

Owner next steps: review the three new priority proposals; provide approved trusted HTTPS synthetic runtime; rebuild/visually approve academic files; approve core merge after gates. No new model/vendor expansion or research project required.

## Release Candidate Closure — 31 ตุลาคม 2026

Starting HEAD `70c9c5ef940a84477c3b52f554059852642406aa`. Implementation source และ dependency/fixture hashes: [RELEASE_CANDIDATE_20261031.json](RELEASE_CANDIDATE_20261031.json). Final publication HEAD, CI run และ tested synthetic checkout บันทึกใน [PR #10](https://github.com/Ratthabhumi/EIMS/pull/10) หลัง CI เสร็จ; baseline CI ใน manifest ไม่ใช่ผลของ harness ใหม่.

ไม่มี production defect ใหม่ที่ reproduce จาก integration audit จึงไม่เปลี่ยน Analyzer/auth/UI/DB หรือสร้าง snapshot ใหม่. เปลี่ยนเฉพาะ browser acceptance harness และ CI: require explicit HTTPS origin, ปฏิเสธ credentials/path/query/TLS bypass, เพิ่ม cookie replay ที่ได้จาก real login หลัง logout, protected API, back/forward/reload และ exact source coordinates. ตรวจ config แบบ offline 5 invalid + 1 valid, syntax PASS, BFF/PDF 18 PASS; **ไม่ได้ execute browser assertions**. Import harness เดิมล้มเหลวเพราะบังคับโหลด Playwright แม้ต้องการตรวจ config; แยก import-safe config ออกจาก runtime แล้ว. ไม่อ้างเป็น reproduced application vulnerability.

| Flow / invariant | Implementation | Existing test / boundary | Gap / outcome |
|---|---|---|---|
| Login / revoked session / logout | auth.py, session_security.py, AnalyzerSession.tsx | test_login_logout_revokes_copied_token_only; test_session_invalidated_by_lifecycle_boundaries; test_session_proxy.cjs | Real PostgreSQL/ASGI + synthetic BFF handlers covered; browser replay/navigation prepared only |
| Upload size/count/source | analyze.py, parser/evidence services | test_invalid_bundle_is_rejected_without_persistence; bundle limits/source classification tests | Existing coverage reused |
| Fortinet/CTK/1129, no-failure and unrelated bundles | observed_summary.py, summary.py, incident_extract.py | test_full_pipeline_really_runs_route_synthesis_and_memory_history; test_no_failure_recommendations_and_reopened_history; reliability/counterexample suite | Native route with offline dependencies; no new output change |
| API serialization and hypotheses/UNKNOWN | analyze.py, schemas/analyze.py | test_full_route_parity_against_isolated_fastapi_transport | Native ↔ isolated ASGI parity; not browser |
| Evidence/viewer/legacy data | evidence.py, EvidenceSourceReview.tsx | test_source_inspector_bounds_escapes_and_reports_missing_history_source; PostgreSQL bundle/legacy test | React escaped text/native details; keyboard/theme visually NOT_TESTED here |
| PostgreSQL commit/reopen and file identity | history.py | test_real_postgres_upload_commit_reopen_and_ownership; test_real_postgres_bundle_history_and_legacy_fields; test_no_failure_postgres_history_reopen | API JSON and saved structured/narrative fields covered; browser reload prepared |
| Alternate-user access / search / feedback / exports | auth/history/search/obsidian routes | ownership, owner-scoped feedback/search, shared route negative tests; export admin dependency | Deny-by-default preserved; no full tenant claims |
| Redaction and PDF rendering | privacy services, AnalyzerHistoryList/page PDF templates | test_sensitive_credentials_are_not_returned_or_persisted; 18 BFF/PDF checks | Stored response and escaped template covered; physical/export deployment NOT_TESTED |
| Scientific reviewed-only binding | existing runner/grounding/review CLI | test_existing_review_pipeline_end_to_end_test_only and stale/duplicate/empty assertion tests | Synthetic temporary review only, real reviewed count still 0 |

Freeze verification (UTF-8 decoding explicit): manifest/input/annotation/scorer/runner/grounding/investigation hashes match snapshot config; recomputed 12 prediction hashes (exclude only prediction_sha256/timing_seconds), regenerated in-memory claim queue equals 60 saved proposals; priority 3 and delta 8 hashes present in packets. No HELDOUT execution/tuning. M0/M1/Full snapshots remain unchanged. 12 DEV DRAFT, 5 HELDOUT reserved, 60 claims, 0 genuine cases/claims reviewed; accuracy, semantic support precision and unsupported-claim rate NOT_MEASURED.

Local full hermetic: 281 PASS, 1 Windows symlink privilege SKIP, 2 dependency deprecation warnings. Final-head CI runs Python/PostgreSQL, counterexamples and frontend checks. No dedicated local test DB or forbidden runtime was started.

GitHub refresh: #2/#3/#4/#5/#10 MERGEABLE with no review decision; main protection returned 404 Branch not protected, rulesets empty. These do not authorize merge. Technical sequence: #2→main; retarget #3→main and recheck diff/CI; repeat #4, #5, #10. Preserve original refs, inspect changed base and review before each merge. Infra #6–#9 stays separate; four recovery XFAILs remain outside this closure. No schema change here. Before operational rollback, operator must verify backup/config/source compatibility; never automatically downgrade/reset/delete History. Python requirements use ranges: manifest records local versions plus frontend lock, not identical CI/deployment environments.

Owner-only: authentic review of fort_config/esxi_tracker/win_policy; approved trusted HTTPS Dashboard+BFF + isolated synthetic backend/DB/accounts; merge approval after gates; separate operational/USB authorization if that scope is wanted. Existing offline demo is the fallback, not installed-system acceptance. No new vendor research question arose; ChatGPT research conclusions remain implemented with tests, independent diagnostic quality still unmeasured.

Next milestone: submit three genuine reviewed cases with exact hashes, rationale and claim judgments; validated reviewed-only denominator >0 with per-class support. This pilot does not establish broad accuracy. Browser must independently execute login/upload/source/reload/reopen/ownership/logout/replay/navigation/expiry before acceptance can pass.

## รอบแก้ Recommendation — 30 ตุลาคม 2026

เริ่มจาก `7edecfc4be8fa0a31b42e569cf461b77d5c75311`; production fix อยู่ที่ `a3cf8eb2823dbb61847b45c344d047574cba2c23` บน PR #10.

- ยืนยัน regression ก่อนแก้ 10 FAIL: bundle_related/esxi_heartbeat และ negative controls; fallback เคยให้ค้น primary error line ทั้งที่ไม่มี observed failure.
- `summary.py` ใช้ signal/noise policy เดิมจาก incident extraction ก่อน fallback/web/RAG; เมื่อไม่มี signal ให้ไม่มี causes, ไม่แนะนำค้น error, ระบุข้อจำกัดผลจบ session ทั้งไทย/อังกฤษ. เก็บ observed-event/curated/vendor semantics เดิมไว้. Warning ยังไป investigation path เดิม; ไม่ตีความ warning เป็น success.
- หลังแก้ local hermetic 281 PASS, 1 SKIP (Windows symlink privilege), 2 dependency deprecation warnings. Counterexamples 8/8 PASS. CI บน final HEAD เป็นหลักฐาน Linux/PostgreSQL/frontend แยกต่างหาก ดู PR checks; ไม่ใช้ผล HEAD เก่าแทน.
- เพิ่ม PostgreSQL roundtrip ไทย/อังกฤษ × single/bundle 4 เคส ตรวจ structured summary, aiSummary หลัง fresh SELECT และอีก user มองไม่เห็น. รันด้วย synthetic CI database เท่านั้น.
- Evidence viewer ตรวจ source: React text escaping, native details/summary, keyboard focus return, source provenance/redaction/legacy states. ไม่มี frontend defect ใหม่ที่ reproduce จึงไม่เปลี่ยน UI. Build/typecheck ไม่ใช่ browser acceptance.
- Clean-source M0/M1/Full ใหม่อยู่ `evaluation/analyzer/results/20261030-recommendation-*`: 12 DEV ต่อโหมด, 0 errors, 0 reviewed, 0 HELDOUT. M0/M1 prediction hashes เดิม; Full เปลี่ยน 8/12, claims 77 → 60. เป็นการเปลี่ยนข้อความ ไม่ใช่คะแนนคุณภาพที่ดีขึ้น.
- input/manifest/annotation/scorer/runner hashes อยู่ config ทุก run; old snapshots และ DRAFT labels ไม่เปลี่ยน. Full snapshots เก็บทั้งคำตอบและ History ที่เปิดซ้ำ พร้อม execution trace. ไม่เปรียบเทียบ latency ข้าม execution boundary.
- priority packet fort_config/esxi_tracker/win_policy hashes ไม่เปลี่ยน. 8 เคสที่เปลี่ยนใช้ [delta packet](DEV_REVIEW_RECOMMENDATION_DELTA_20261030.md) คู่กับ source/labels เดิม; ห้ามใช้ claims/hash เก่าสำหรับคำตอบใหม่.
- [before/after tests และ per-case hash comparison](evidence/20261030-recommendation/) เป็นหลักฐาน regression; ไม่ใช่ human accuracy.
- Research ที่ให้มา: Fortinet config, CTK technical failure/physical cause unknown, Windows 1129 symptom rules คงเดิมและ regression ผ่าน. ใช้หลัก evidence-limited recommendations โดยไม่เพิ่ม taxonomy/model. ไม่มีคำถาม vendor ใหม่ที่ต้อง Research; independent review/generalization ยังรอคนตาม handoff เดิม.
- Scope/security: ไม่แตะ auth, migration, operational DB, Gold, HELDOUT, infrastructure PR #6–#9 หรือ main. Infrastructure recovery 4 XFAIL ไม่ได้แก้/ทดสอบในรอบนี้.
- Browser: ไม่พบ approved listener 3009/3449; BROWSER_HTTPS = BLOCKED_NOT_TESTED เพราะยังไม่มี authorized runtime หลังข้อจำกัดเดิม. USB/production NOT_TESTED. ไม่เริ่ม listener แทนหรือเปลี่ยน cookies.
- Owner: review priority 3 เคสจริง; เตรียม approved HTTPS synthetic runtime ตาม Operator; อนุมัติ merge เมื่อพร้อม. Merge order #2 → #3 → #4 → #5 → #10 ต้อง retarget/recheck CI ทุกฐานที่เปลี่ยน; #6–#9 แยกสาย. ไม่ merge ในรอบนี้.
- Next milestone: reviewed-only denominator >0 พร้อม claim judgments ที่ผูก hash และ browser acceptance actual login/upload/reload/reopen/logout-replay ผ่านบน runtime ที่อนุญาต. SCIENTIFIC_REVIEW_PENDING; installed acceptance ยังไม่ผ่าน.

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
