## Evidence update — 30 October: no-failure recommendations

ถาม: ระบบยังแนะนำแก้ error ที่ไม่มีหรือไม่? พบจริงใน fallback และมี 10 failing-before regressions; แก้ด้วย signal policy เดิม ให้แนะนำเก็บบริบทแทนโดยไม่ยืนยันสุขภาพระบบหรือผลจบงาน. Full DEV เปลี่ยน 8/12, emitted claims 60, human-reviewed 0. จำนวน claims ที่ลดลงไม่ใช่หลักฐาน accuracy. บท 4 ด้าน diagnostic validity ยัง INCOMPLETE; engineering, human validation และ installed acceptance แยกกัน. ดู GRADUATION_DELIVERY_20261030.md และ versioned snapshot ใหม่.

## Graduation delivery — 30 October 2026

Current scope/experiment boundaries and owner tasks:
[GRADUATION_DELIVERY_20261030.md](GRADUATION_DELIVERY_20261030.md).
Core Analyzer frozen; tenancy/WSS/new model work deferred. Priority review packet hashes
verified unchanged; supplementary nine-case packet added. No human decisions invented.
Populated synthetic parent-upgrade test added; local run skipped because DB is stopped.
Use delivery PR exact-head CI for its executed result. Prior test counts below are historical.
No trusted browser listener available; operator runbook replaces repeated startup attempts.

## Current checkpoint — 26 October 2026 publication

This update supersedes historical status below; historical measurements remain intact.
Implementation source: `348f892719cc0e839cd2813d344d26e672c883fd`.
See [grounded diagnosis report](GROUNDED_DIAGNOSIS_CHECKPOINT_20261025.md) and
[next execution instructions](NEXT_EXECUTION_PROMPT_20261026.md).

- Implemented vendor-grounded Fortinet configuration identity, Windows 1129 symptom-only summary,
  CTK cause abstention and narrower KB applicability; removed cross-vendor default assumptions.
- Local regression: 273 passed, 1 Windows skip, including 31 dedicated PostgreSQL tests.
  Actual Alembic upgrade was rehearsed from a minimal parent schema; full historical chain and
  operational migration remain untested. Bounded cleanup, rollback and concurrency verified.
- Direct organization APIs now require admin/service authorization in Secure Mode;
  customer evaluation forms are also restricted, ingestion requires service authorization,
  and secure WebSocket streaming is disabled pending an authenticated transport.
- Controlled DEV: 12 DRAFT, zero execution errors, 77 claims, zero human judgments.
  Narrative changed 12/12; typed v2 fields unchanged 12/12. Claim reduction from 135 is not accuracy.
- HTTPS browser acceptance, independent human validation, institutional retention and deployment
  acceptance remain open. M2/M3 remain NOT_RUN. Existing review packets are historical.

# EIMS — Chapter 2–5 update and defense outline (25 October 2026)

This measured-results supplement does not overwrite the frozen academic report.
It is a working defense packet, not a claim that scientific evaluation is complete.

Latest engineering source: `77603388de96324fc5dbf56e1de2cdc192cde747`.
Chapter 3: PostgreSQL-backed revocation, idle/absolute expiry and login throttling
now implemented; organization-wide search is admin-only in Secure Mode.
Chapter 4: 251 Python passes, 1 Windows skip; 18 handler checks; 6 real HTTP/PG
handler checks. Fresh full DEV snapshot retains identical semantics/claims 12/12,
but privacy policyVersion changes prediction hashes. Human-reviewed denominator
is still zero. Chapter 5: HTTPS browser, deployed migration, retention and broader
domain permission acceptance remain gates. See SESSION_LIFECYCLE_GATE_20261025.md
for evidence boundaries and the refreshed three-case Human Review Packet.

## Chapter 2: scope and related work

Position EIMS as offline-capable multi-vendor infrastructure-log investigation
with traceable evidence, uncertainty and reproducible evaluation. Structured
findings, source metadata and synthetic rule regression are design principles
adapted from the research matrix. No commercial-SIEM equivalence or superiority
is established. Research-only open questions are handed to ChatGPT through
ANALYZER_RESEARCH_HANDOFF_20261025.md; models/new vendors are deferred.

## Chapter 3: method and safeguards

Research question: can the deterministic investigation preserve observed facts
and their source coordinates through analysis and saved History while avoiding
unsupported conclusions? Software-contract hypotheses include request isolation,
coordinate preservation and authenticated row ownership. Physical-RCA correctness
requires independent human labels and cannot be inferred from contract tests.

Reuse rules-only M0, rules+KB M1 and native full investigation. No new scorer is
introduced. Full mode calls actual route/summary/evidence/local-KB logic with
explicit model/RAG/vector isolation. A second layer uses real PostgreSQL with
secure JWT verification in an isolated app; a third uses the actual Dashboard
against a separate HTTP/test-DB harness. These layers do not certify installed
EIMS, operational data, USB delivery or a real-world customer incident.

Dataset: 12 synthetic DEV and five reserved HELDOUT, all DRAFT. Inputs and initial
proposals are AI-authored, informed by existing behavior, and convenience sampled.
Reviewer independence and scenario-group separation are prerequisites to an
independent result. Preserve v1/heldout/old baselines. Never retune against heldout.

Software controls cover explicit Failed/Success/Warning, technical failure without
terminal status, config successes/failures, unknown identities, out-of-order and
incomparable clocks, cross-vendor KB controls, and parallel request isolation.
They are not independent Gold examples. DEV terminal-positive support is zero.

## Chapter 4: observed results and interpretation

Inherited checkpoint PR #3: local 189 passed / one Windows symlink privilege skip;
native coordinate overlap 3 TP, 0 FP, 1 FN against DRAFT references. The continued
source traces that FN to single-file response construction: normalized CTK line 2
exists but structured citations were absent. Reusing those records fixes source
loss without modifying labels/scorer. The final checkpoint's exact SHA, counts,
browser QA and CI are recorded in GRADUATION_INTEGRATION_20261025.md and its PR.

The first targeted inherited-source checks showed two real failures (structured
CTK citations, unsupported generic cause wording) and a passing 32-way summary
isolation control. Dedicated PostgreSQL tests exposed duplicate basename
ambiguity. An initial traversal test wrongly demanded rejection; the existing
safe-basename contract was verified instead. This test-expectation correction is
not an additional product defect. Subsequent test runs preserve historical results.

Fresh full-run source ee8cb7c executes 12 DRAFT / zero reviewed / zero heldout,
with zero execution errors. Exact coordinate overlap is 4 TP / 0 FP / 0 FN
(precision 4/4 and recall 4/4), compared with 3/3 and 3/4 at the inherited
controlled-after checkpoint. The evaluator/labels are unchanged. This is source
coverage against proposals, not human-validated accuracy or semantic support.
The claim queue now has 135 records, all NOT_REVIEWED; semantic support and
unsupported-claim rate remain null. Positive-terminal sensitivity remains null.

Qualitative controls: unknown vendor final outcomes and causes remain uncertain;
CTK 2620 is technical failure rather than proof of a failed job or vSAN cause;
successful config edits do not themselves imply operational failure; Event 1129
identifies a DC-connectivity symptom without proving DNS/NIC/firewall causality.
Windows failure taxonomy remains a research/review candidate.

Threats to validity: AI-authored labels and correlated scenarios, tiny imbalanced
cohort, no reviewed causal truth, source-prefix truncation, incomplete legacy raw
context, host-dependent timing, injected optional components, and differences
between isolated test transport and installed authentication/deployment. A narrow
successful demo establishes workflow operability, not generalization or accuracy.

## Chapter 5: conclusion and next experiment

Engineering evidence supports specific corrections and traceability contracts.
Scientific reliability of diagnosis remains unestablished. Next: independent
human review of the three priority cases and claim support, then a small balanced
20–30 reviewed cohort, protocol freeze and untouched heldout evaluation. Expand
only after review quality is demonstrated. M2/M3 remain optional.

## 10–15 minute slide and demonstration sequence

1. Problem and scope (1 min): difficult multi-vendor infrastructure evidence;
   clearly state synthetic DRAFT and lack of certified accuracy.
2. Existing architecture and boundaries (1 min): one native Analyzer, layered
   tests, local KB and optional components explicitly disabled.
3. Semantics (1 min): identity, failure, first/last observed, final outcome,
   hypothesis and proven cause are different questions.
4. Corrections (2 min): shared-object isolation, honest unknown outcome/cause,
   CTK, successful config and source/ownership preservation.
5. Hero workflow (4 min): two-file synthetic upload → MEDIUM association → exact
   source context → final Failed line → physical cause unknown → page reload →
   reopen saved History. Describe test database and synthetic authentication.
6. Results (2 min): regression/CI, coordinate denominator, zero reviewed claims;
   no fabricated scientific metric. Show the commit and actual trace.
7. Limits and next experiment (1 min): independent review, KB prerequisites,
   installed-system acceptance and optional model comparisons.

Fallback: inspected synthetic screenshots and offline inspector. Explicitly label
fallback material; it is not evidence that an unexecuted live workflow passed.

## Examiner questions: concise defensible answers

| Question | Answer boundary |
|---|---|
| Is this dataset independent? | No. Current AI-authored DEV is exploratory; reviewed and untouched cohorts remain prerequisites. |
| Why synthetic logs? | Confidentiality and controlled regression; production generalization is not claimed. |
| What does accuracy mean here? | No certified accuracy exists yet; current counts are contract checks and DRAFT agreement. |
| Why null metrics? | No reviewed support judgments or terminal-positive DEV denominator exists. Null is not success. |
| Can a correct Event ID still be a poor diagnosis? | Yes; identity does not establish operational failure or physical cause. |
| Does CTK 2620 prove root cause? | No; code meaning is distinct from environment-specific cause/remediation. |
| How are misleading citations handled? | Exact coordinates are mechanically checked; material claim support needs separate human adjudication. |
| Does the system leak data between users? | Newly scoped History endpoints are tested with two synthetic JWT identities; installed-system acceptance remains separate. |
| How is confidential data protected in this work? | Synthetic-only fixtures/test DB; no customer log export or operational DB access. |
| Why no complete RAG/LLM benchmark? | No validated isolated model/index experiment; optional components are declared NOT_RUN. |
| Can the live system reproduce this? | Isolated real HTTP/DB/Dashboard checks are reported precisely; installed EIMS/USB are not inferred from them. |


## Examiner answers — review integrity checkpoint 30 October 2026

- มากกว่า keyword search อย่างไร: มี parser/source identity, structured evidence coordinates,
  chronology, bounded correlation, vendor KB gates และ saved investigation; ไม่อ้างเข้าใจทุก log.
- Event ID กับ RCA: ID ระบุชนิดเหตุการณ์ ส่วน RCA ต้องมีหลักฐานเชิงเหตุที่เฉพาะกว่า.
- Failure แต่ outcome UNKNOWN: operation อาจล้มเหลว แต่ไม่มี final session record หรือผูก session ไม่ได้.
- ป้องกัน RCA แต่งขึ้น: จำกัด vendor context, unknown/abstention และ counterexamples;
  ยังต้อง human adjudication จึงจะวัด semantic correctness.
- Citation ถูกหรือไม่: ตรวจ file/line/span กับต้นฉบับ; semantic support ต้องคนตัดสินแยก.
- Tests พิสูจน์อะไร: contracts ของกรณีที่ทดสอบ รวม migration/auth/ownership ไม่ใช่ Accuracy.
- ทำไม DRAFT ไม่ใช่ accuracy: labels ยังเป็นข้อเสนอ AI ไม่ใช่ reference ที่ตรวจอิสระ.
- ทำไมกัน HELDOUT: ป้องกันปรับกฎตามชุดที่ใช้สรุปผลสุดท้าย; ยังไม่ได้รันชุดนั้น.
- ข้อจำกัด synthetic: รูปแบบ/สถานการณ์แคบและ selection bias; ไม่แทนข้อมูลภาคสนาม.
- ทำไมไม่ใช้ LLM ทุกจุด: เริ่มจากวิธีที่ตรวจซ้ำและผูกหลักฐานได้; M2/M3 ยัง NOT_RUN.
- เทียบ SIEM: ยืมหลักการ structured findings/evidence ไม่ได้พิสูจน์เหนือกว่า commercial tools.
- History ownership: server กรองตาม authenticated username และตรวจ session/current role;
  tests negative cross-user ไม่ใช่การรับรอง IAM ทุกระบบ.
- PostgreSQL ทดสอบอะไร: isolated persistence, ownership, session revoke และ empty/populated
  synthetic migration. Reconnect ไม่ใช่ OS restart หรือ production migration.
- Physical infrastructure: USB/installed HTTPS ยัง NOT_TESTED; Redis/EVTX audit แยกสาย.
- ทำซ้ำอย่างไร: source SHA + frozen inputs/config/scorer hashes + existing CLI + CI artifacts;
  แยก stage-only, full offline, HTTP/DB และ browser timing อย่างชัดเจน.

Chapter 4 scientific results remain INCOMPLETE: actual reviewed cases/claims = 0.
Review pipeline test uses artificial temporary judgments to prove denominators, not scientific quality.
