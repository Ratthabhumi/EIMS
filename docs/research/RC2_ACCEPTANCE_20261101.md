# RC2 product acceptance and staged academic delivery

Starting HEAD: 7335aa24f39dab9f2fa63690838e3f89d44e59bd. Existing PR #10, no merge/retarget/rebase. Final HEAD, CI and tested checkout are recorded in the PR body after publication.

## Confirmed defects and minimal correction

Actual shared React component AnalysisResultDetail rendered Fortinet's legacy string `None` as a failure sequence, called the last observed failure `Terminal failure`, and hid Windows Event ID 1129 behind its new diagnostic category. The component is used by both analyzer/page.tsx and AnalyzerHistoryList.tsx. The same six English/Thai render assertions fail on 7335aa2 and pass after correction; before/after JSON is in docs/delivery/rc2-20261101. This is actual React server rendering, not a live browser.

The correction suppresses empty/None failure fields, labels the legacy terminalFailure field Last observed failure, explicitly distinguishes that observation from job outcome, preserves Windows identity and uses neutral investigation/next-step headings. No backend, scoring, snapshots, auth or storage behavior changed. Fixed one remaining `60 Full claims` sentence in the English abstract to 61, based on the existing snapshot.

## Acceptance matrix

| Scenario | Evidence used | Boundary and result |
|---|---|---|
| A1 Fortinet informational configuration | Existing priority route parity and PostgreSQL TH/EN roundtrip; new shared-component render test | Source/identity/context persisted; no fabricated failure UI; TESTED_IN_ISOLATION, synthetic PostgreSQL in CI |
| A2 VMware CTK | Same priority integration tests and render test | Error retained, source evidence and UNKNOWN preserved, last observed is not final outcome |
| A3 Windows 1129 | Priority integration tests; native timestamp empty; render test | Identity and category visible together, missing timestamp unchanged; no physical-cause inference |
| A4 no-failure/truncated/unrelated/duplicate/malformed | Existing reliability/investigation/counterexample suites | Reused; no new parser or labels |
| A4 missing context/redaction | EvidenceSourceReview displays missing/withheld context and escaped saved excerpt; existing source/privacy/PG tests | Source inspection + isolated contracts; actual click/focus NOT_TESTED |
| A4 ownership/revoked/expired/logout | Existing real synthetic PostgreSQL secure-session tests and BFF tests | Isolated/CI; not authenticated HTTPS browser |
| Broader 21 API setup blocks | Previous project audit: Asset/OCR/Search/Timeline | Asset/OCR/Timeline outside this demo. Shared global search authorization intersects but existing secure PostgreSQL owner/admin tests cover that boundary. Original 21 remain TEST_SETUP_BLOCKED, not relabeled PASS or production defects. |

## Scientific review and demo

Existing verifier passes: 36 prediction digests, 12 DRAFT DEV, 61 claims; zero authentic reviews; no HELDOUT execution. Backend and prediction outputs unchanged. Existing offline inspectors regenerated successfully under test-results/rc2-offline-demo. Follow OPERATOR_DEMO_20261030.md for the five-minute Fortinet → VMware → Windows → source context → uncertainty sequence; memory History is not a database test.

ผู้ตรวจให้เริ่มที่ DEV_REVIEW_PRIORITY_DELTA_20261101.md: อ่าน raw source พร้อมเลขบรรทัดก่อนข้อเสนอ AI ตรวจ fort_config (config edit ไม่ใช่ failure), esxi_tracker (CTK operation failure ยังไม่พิสูจน์สาเหตุ/ผลจบงาน), win_policy (1129 symptom, timestamp ว่าง, ไม่ยืนยัน DNS/firewall). ตัดสินทีละ typed field และ claim ว่าเห็นด้วย/แก้/หลักฐานไม่พอ พร้อมบรรทัดและเหตุผลจริง ใช้ alias จริงหลังตรวจแล้วเท่านั้น. Existing review CLI --help verified; use the working-copy commands in OPERATOR_DEMO_20261030.md. Label review and claim-support judgments are separate; do not sign the tracked DRAFT files. No reviews were entered this round. A later three-case pilot must report denominator three, not general accuracy.

## Actual staged artifacts

See docs/delivery/rc2-20261101/source_manifest.json for exact hashes, build input provenance and inspection limits. New files: report REVIEW.docx + PDF (70 pages); presentation STAGED.pptx + PDF (15 slides, 15 speaker notes). Historical accepted binaries untouched. Installed Word/PowerPoint exported PDFs; no dependencies installed. Bundled presentation package/layout/import validator passed. All 15 rendered slides inspected individually; native PDF contact sheet also inspected.

Report is PARTIALLY_INSPECTED_NOT_FINAL: first draft contact sheets scanned, title border/page breaks improved, final cover inspected; full-size review of every final page still needed. Existing Mermaid code listings and historical figure placeholders need author-approved figures. Institutional cover/signatures/biography and supplied names require human confirmation. Do not submit as an approved final thesis. Historical binaries remain STALE_PENDING_REBUILD; these new staged copies have a separate status. No wholesale documentation rewrite.

Reproduce on a new staging revision with the existing bundled runtime: tools/build_rc2_report.py, tools/build_rc2_presentation.mjs (EIMS_ARTIFACT_RUNTIME and EIMS_PRESENTATIONS_SKILL), then tools/export_rc2_office.ps1 with installed Office and no open Office process. Builders/export refuse existing final outputs; preserve old files, use a new revision rather than deleting them. Word/PPT exports are not byte-deterministic; use recorded artifact hashes for this delivery. Inspect rendered files before release.

## Remaining owner gates

SCIENTIFIC_REVIEW_PENDING: genuine judgments. BLOCKED_BY_AUTHORIZATION / RUNTIME_NOT_TESTED: previous HTTPS startup denied by policy; no approved runtime supplied, no bypass or startup retry. DEFERRED: separate infrastructure stack and recovery XFAIL; production/USB hardware certification. Owner approves core merge #2 → #3 → #4 → #5 → #10 only after fresh CI/base checks. No new general research required.
