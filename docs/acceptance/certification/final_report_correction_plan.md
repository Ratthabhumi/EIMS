# EIMS — FINAL RESEARCH REPORT CORRECTION PLAN

**Phase:** 2 — Evidence-Based Report Reconciliation  
**Plan date:** 2026-11-22  
**Status:** Plan only — **DOCX not edited**  
**Supplied report:** `C:\Users\MewMew\.codex\.chatgpt-projects\g-p-6aa6cf8212c4819191c5d7719f82110c\EIMS_FINAL_SUBMISSION_2026_FINAL_REVIEW_with_dotted_leaders.docx`  
**Prior audit:** `docs/acceptance/certification/repository_report_audit.md`  
**Baseline lock:** `docs/acceptance/certification/final_handover_report.md`

---

## 1. Executive summary

The undergraduate report’s research caution is largely sound (prototype posture; M2/M3 NOT RUN; diagnostic accuracy NOT MEASURED; 0 approved knowledge). It is **not** ready for uncritical final submission because Abstract and main body freeze **different dated snapshots** of tests and catalog surfaces without a single reconciliation table.

| Conflict | Abstract (Thai + EN) | Main body (Ch. 3–5) | Certification / handover |
|---|---|---|---|
| Main pytest | **1,374** passed | **1,903** passed (20 Nov Knowledge Foundation) | **2,107** passed (finished-code; `end_to_end_final_report.md`) |
| Catalog surface | **175** | **911** inventory (+ 175 as Gate H observation) | **911** governed; **1 / 42 / 868**; **0** human-approved |
| Browser | not stated as score | Secure **33/33** (15 Nov) + disposable E2E **ACCEPTED WITH LIMITATIONS** (20 Nov) | Certification Browser **18/18** (22 Nov) — **omitted** from DOCX |

**Correction principle:** retain each figure with its **date, source path, and scope**. Do **not** auto-replace Abstract 1,374 / 175 with 2,107 / 911. Do **not** merge browser layers into one score. Do **not** claim the Handover round re-ran tests (Engineering PASS is **inherited**).

**Out of scope for the later DOCX edit:** source code, tests, services, Operational DB, git stage/commit/push, `EIMS_11-8-2026.md`.

---

## 2. Fixed EIMS baseline (do not change)

| Gate / figure | Locked value |
|---|---|
| Engineering Acceptance | **PASS** (inherited from earlier engineering validation; handover ran **no** tests) |
| Human Certification | **NOT RUN** |
| Production Readiness | **PARTIAL** |
| Governed catalog | **911** records |
| Eligible | **1** (`cisco_asa:official_message_id:113005`) |
| Blocked | **42** |
| Ineligible | **868** |
| Human-approved | **0** |
| Branch / HEAD | `demo/2026-11-24` · `3f2beea` |
| Staged / dirty | **0** staged · **338** dirty/untracked (preserve) |

---

## 3. Claim reconciliation matrix

### A. Test counts

| Figure | Original source (dated) | Actual scope | Appears in DOCX | Recommendation | Supports research objective |
|---|---|---|---|---|---|
| **1,374** passed / 51 skipped / 0 failed | `docs/acceptance/2026-11-20-backend-final-closure.md` (final release gate) | Main suite `pytest tests --ignore=tests/test_analyzer_postgres_integration.py` on disposable PG **before** Knowledge Foundation expansion | Thai abstract §ผลการทดสอบ; English abstract (“latest reported… 1,374”) | **Qualify, do not delete.** Relabel as **20 Nov 2026 backend-final-closure** main-suite result. Remove “latest” wording once later suites are cited. | Engineering reliability of backend contracts at that gate; **not** final finished-code regression |
| **1,903** passed / 51 skipped / 0 failed | `docs/acceptance/2026-11-20-knowledge-foundation-expansion.md` (+ consolidated audit citations) | Same main-suite command class **after** knowledge-foundation expansion (still ignore analyzer-PG) | Ch. 3 test narrative; §4.4.1; Ch. 5 conclusion (≈ paras 546, 745, 903, 924) | **Retain** with date/scope. Prefer as the body’s primary Nov-20 main-suite citation. | Supports Knowledge Foundation expansion validation |
| **2,107** passed / 51 skipped / 0 failed | `docs/acceptance/certification/end_to_end_final_report.md` §Test counts (finished code) | Finished-code certification regression; same ignore-analyzer-PG pattern; **not** handover-day | **Absent** from DOCX | **Add** as a dated certification row in Ch. 4 test table and/or Ch. 5. Do **not** silently overwrite Abstract 1,374. | Supports Engineering Acceptance (inherited) |
| **75** Analyzer-PG passed | Repeated across Nov 20 closure + certification reports | `tests/test_analyzer_postgres_integration.py` only; separate disposable DB | Abstract; §4.4.2; conclusions | **Retain.** Keep explicit “do not add to main-suite total.” | Analyzer↔PostgreSQL integration |
| **23** focused governance/draft | `final_acceptance_report.md` | Affected-only after open-access read change; full suite **not** repeated | **Absent** | **Optional add** in limitations / engineering gate note | Narrow regression after last governance UI/API tweak |

**Do not:** present 1,374 + 1,903 + 2,107 as one current total, or imply handover re-executed any of them.

### B. Record counts

| Figure | Original source | Actual scope | Appears in DOCX | Recommendation | Research meaning |
|---|---|---|---|---|---|
| **175** | `docs/acceptance/2026-11-20-final-browser-e2e-acceptance.md` Gate H catalog summary | **Analyzer/browser catalog API surface** at Gate H (0 approved) — **not** the governed eligibility inventory | Thai abstract “คลังความรู้จำนวน 175”; §4.3 Gate H (≈732); already distinguished from 911 in body | **Retain with qualification.** Abstract must say this is the **Nov 20 browser Gate H Analyzer catalog summary**, not the full governed inventory. | Snapshot of the live Analyzer-facing catalog during disposable E2E |
| **181** (153 ops + 28 legacy candidates) | Same-day knowledge expansion narrative | Parser-linked **legacy catalog surface** after expansion | §4.3 (≈733–734) | **Retain** as intermediate surface; keep “different view/time” language | Expansion of parser-linked surface |
| **911** | `catalog_import_eligibility.json` / `register.json`; DOCX §4.3 / Ch. 5 | Full **governed working-tree knowledge inventory** (ops + candidates + technical refs) | Body inventory tables/prose; **not** Abstract | **Retain** as inventory total. Add eligibility row **1 ELIGIBLE / 42 BLOCKED / 868 INELIGIBLE / 0 human-approved** where inventory is summarized (Ch. 4 and Ch. 5). | Inventory organization — **not** 911 validated diagnostics |
| **1 / 42 / 868 / 0** | Eligibility JSON + handover | Adapter eligibility for human-review registration; human-approved from repo artifacts only | Eligibility breakdown **understated** in DOCX (0 approved present; 1/42/868 largely missing) | **Add** explicitly next to 911. State sole ELIGIBLE = ASA **113005**, package ready, **not** human-reviewed | Governance readiness for review — **not** certification complete |
| **0** source-verified / validated / approved | Register lifecycle + DOCX | Human lifecycle states | Multiple Ch. 4–5 locations | **Keep unchanged** | Blocks “validated knowledge base” claims |

**Do not:** force Abstract to say “911” unless the author chooses a **new Abstract framing** that cites the governed inventory **and** still mentions 175 as a separate dated browser observation. Default recommendation: **qualify 175 in Abstract; keep 911 in body**.

### C. Browser acceptance evidence

| Layer | Date | Result | Source | In DOCX? | Recommendation |
|---|---|---|---|---|---|
| Secure Browser final16 | 15 Nov 2026 | **33/33** checks + Playwright **2/2** | DOCX claim; path re-cite outstanding in audit | Yes (§4.4.3; Ch. 5) | **Retain as historical.** Mark evidence path **NOT VERIFIED** until revision cites the Secure Browser evidence directory/report path. |
| Disposable HTTP E2E (Cursor) | 20 Nov 2026 | **ACCEPTED WITH LIMITATIONS**; Gate H catalog 175 | `docs/acceptance/2026-11-20-final-browser-e2e-acceptance.md` | Yes | **Retain.** Keep limitations (HTTP not HTTPS; not Product Accepted). |
| Certification Browser | 22 Nov 2026 | **18/18** synthetic demo + webpack build | `docs/acceptance/certification/browser_acceptance_report.md` | **No** | **Add** as third dated layer. Never fold into 33/33 or ACCEPTED WITH LIMITATIONS. |
| Historical A9 | earlier | separate | DOCX already separates | Yes | **Keep** separation language |

**Do not:** invent a combined “browser score” or claim Product Acceptance.

---

## 4. Chapter-by-chapter correction list

### Front matter / Abstract

| ID | Location | Issue | Action |
|---|---|---|---|
| A1 | Thai abstract (extract ¶32) | 1,374 + 175 presented without date/scope; can be read as current global totals | **Qualify** (preferred). Proposed wording below. |
| A2 | English abstract (extract ¶41) | Same 1,374; sentence **truncated mid-phrase** (“using a”) — content cut off before disposable-DB / catalog / prototype caveats that Thai abstract still has | **Restore/complete** EN abstract to match Thai caution structure; qualify numbers; fix truncation (**author must confirm** lost trailing text). |
| A3 | Both abstracts | “semantic retrieval” in Analyzer description without M2/M3 caveat | Soften to “catalog-supported / deterministic investigation; semantic/RAG paths not evaluated (M2/M3 NOT RUN)” **or** keep phrase but add one-clause NOT RUN boundary (body already does this). |
| A4 | Keywords / framing | No change required for Open Access | **Do not** add login as a missing requirement |

### Chapter 1 — Objectives and scope

| ID | Location | Issue | Action |
|---|---|---|---|
| C1-1 | Objectives (completed vs not) | Body already marks RAG/semantic objective incomplete (Ch. 5 ≈941) | **Preserve.** Ensure Ch. 1 objective list does not imply M2/M3 done. If Ch. 1 still lists semantic vector retrieval as an achieved outcome, **relocate** that item to “not completed / future.” |
| C1-2 | Out-of-scope / production | Already excludes full production HA/SSO certification | **Keep.** Align closing language with Production Readiness **PARTIAL**. |
| C1-3 | Evaluation methods | Disposable/synthetic testing mentioned | **Keep.** Add one sentence that certification Human Certification remains **NOT RUN**. |

### Chapter 2 — Related concepts

| ID | Location | Issue | Action |
|---|---|---|---|
| C2-1 | RAG / Sentence-BERT background | Correctly framed as related work, not EIMS results | **No change** |
| C2-2 | NIST / JWT refs | Not certification claims | **No change** |

### Chapter 3 — Methodology

| ID | Location | Issue | Action |
|---|---|---|---|
| C3-1 | ¶546 cites 1,903 + 75 | Correct for Knowledge Foundation date | **Keep**; add optional footnote/table row for later 2,107 finished-code |
| C3-2 | Secure 33/33 + disposable E2E | Correct separation | **Keep**; add certification 18/18 as third method bullet |
| C3-3 | M2/M3 NOT RUN; 0 verified/approved | Correct | **Keep** |
| C3-4 | Synthetic evidence warning | Correct | **Keep**; reinforce synthetic ≠ human approval |

### Chapter 4 — Implementation and results

| ID | Location | Issue | Action |
|---|---|---|---|
| C4-1 | §4.3 inventory 911 + Gate H 175 | Already distinguished | **Keep**; **add** eligibility 1/42/868/0 table |
| C4-2 | §4.4.1 1,903 | Correct Nov-20 KF scope | **Keep**; insert **Table: Software test eras** (1374 / 1903 / 2107) |
| C4-3 | §4.4.3 Secure Browser | Path not re-cited | **Qualify** + cite path when available; else footnote NOT VERIFIED path |
| C4-4 | Disposable E2E ACCEPTED WITH LIMITATIONS | Correct | **Keep** |
| C4-5 | Missing certification 18/18 | Gap vs locked Engineering gate | **Add** §4.4.x Certification Browser Acceptance (22 Nov) |
| C4-6 | Missing finished-code 2,107 | Gap vs engineering baseline | **Add** row in test-era table |
| C4-7 | ASA 113005 | Eligible ≠ approved | If mentioned, state package prepared / Human Certification NOT RUN |
| C4-8 | Three-reviewer rule | If any wording implies mandatory three | State **owner option**; code minimum is two distinct humans |

### Chapter 5 — Conclusions, limitations, future work

| ID | Location | Issue | Action |
|---|---|---|---|
| C5-1 | ¶903 / 924 cite 1,903 + 75 + 33/33 + ACCEPTED WITH LIMITATIONS | Internally consistent for Nov 15–20 layers | **Extend** with 2,107 finished-code + 18/18 certification browser as **later dated** evidence; state handover did **not** re-run |
| C5-2 | ¶933–934 inventory 911 | Correct caution | **Add** eligibility breakdown |
| C5-3 | M2/M3 / NOT MEASURED | Correct | **Keep unchanged** |
| C5-4 | Production readiness caveats | Align with **PARTIAL** | Explicitly name locked triad: Engineering PASS (inherited) / Human NOT RUN / Production PARTIAL |
| C5-5 | Final conclusion | Prototype + further validation needed | **Keep** research framing; do not upgrade to Product Accepted |

### References and appendices

| ID | Location | Issue | Action |
|---|---|---|---|
| R1 | Evidence citations | Prefer repo paths over undated “latest” language | Add acceptance/certification paths for 1374, 1903, 2107, 18/18, eligibility JSON |
| R2 | Screenshots appendix | UI evidence only | **Keep** disclaimer (already present ≈1063) |
| R3 | TOC / leaders / page numbers | Will drift after Abstract and Ch. 4–5 inserts | **Defer** to Final Report packaging phase after wording approval |

---

## 5. Exact paragraphs / tables / figures requiring revision

Paragraph numbers refer to the temporary DOCX text extract (`eims_docx_extract.txt` indices used during planning). Final edit should match by heading/section, not only by number.

| Ref | Extract ¶ | Section | Revision type |
|---|---:|---|---|
| P-TH-ABS | 32 | บทคัดย่อ | Qualify 1,374 and 175 |
| P-EN-ABS | 41 | ABSTRACT | Complete truncation; qualify numbers; align caution with Thai |
| P-546 | 546 | Ch. 3 testing | Optional cross-ref to 2,107 era |
| P-555–561 | 555–561 | Browser methods | Add 18/18 layer |
| P-732–734 | 732–734 | Catalog surfaces | Keep 175 vs 181 vs 911; add eligibility |
| P-740–756 | 740–756 | §4.4.1–4.4.2 | Insert test-era table including 2,107 |
| P-759–771 | 759–771 | §4.4.3 + E2E | Keep; add certification browser subsection |
| P-902–905 | 902–905 | Ch. 4 summary | Align with triad + eras |
| P-924–925 | 924–925 | Ch. 5 technical validation | Add 2107 + 18/18; ban merged scores |
| P-933–934 | 933–934 | Knowledge foundation | Add 1/42/868/0 |
| P-939–941 | 939–941 | Evaluation / RAG boundary | **Keep** |

**Figures/tables:** no DOCX figure list was re-verified against image binaries in this phase. Any figure caption that states a single “current” test or catalog total without a date must be brought into the reconciliation table above (**author visual pass required**).

---

## 6. Proposed replacement wording (material corrections)

### 6.1 Thai Abstract — test + catalog sentence (qualify; do not auto-upgrade)

**Current (¶32):** cites 1,374 main-suite passes, 75 Analyzer-PG, and 175 knowledge records without dates.

**Proposed:**

> ผลการทดสอบอัตโนมัติในวันที่ 20 พฤศจิกายน 2569 ตามรายงาน backend-final-closure พบว่าชุดทดสอบหลักผ่าน 1,374 รายการ (ข้าม 51 รายการ ไม่มีรายการล้มเหลว) และชุด Analyzer บน PostgreSQL ทดลองผ่าน 75 รายการ ผลชุดนี้เป็นหลักฐานของช่วงเวลานั้น ไม่ใช่ผล regression ชุด finished-code ภายหลัง (2,107 รายการผ่าน) และยังไม่ใช่หลักฐาน Browser end-to-end ทั้งระบบ ในวันเดียวกัน การยอมรับแบบ disposable HTTP บันทึกสรุปแคตตาล็อกฝั่ง Analyzer ที่ Gate H จำนวน 175 ระเบียน (0 รายการที่อนุมัติ) ซึ่งแตกต่างจากคลังความรู้แบบ governed inventory จำนวน 911 ระเบียนในหลักฐานรับรอง (ผ่านเงื่อนไขนำเข้าสู่การตรวจโดยมนุษย์ 1 รายการ, ถูกบล็อก 42, ไม่เข้าเงื่อนไข 868, อนุมัติโดยมนุษย์ 0) ระบบจึงยังเป็นต้นแบบเชิงวิศวกรรมภายใต้ขอบเขต Open Access / เครือข่ายที่เชื่อถือได้ และการรับรองโดยมนุษย์ (Human Certification) ยังเป็นสถานะ NOT RUN

### 6.2 English Abstract — complete + qualify (author must restore any lost clauses)

**Current (¶41):** ends abruptly at “…using a”.

**Proposed closing block:**

> The 20 November 2026 backend-final-closure gate reported 1,374 passed, 51 skipped, and 0 failed tests in the main suite, plus 75 passed in a separate Analyzer PostgreSQL integration suite. Those figures are dated results for that gate; they are distinct from the later Knowledge Foundation main-suite run (1,903 passed) and from the finished-code certification regression (2,107 passed, 51 skipped, 0 failed). They are not whole-system browser end-to-end acceptance. On the same day, disposable HTTP browser acceptance recorded an Analyzer catalog summary of 175 entries with 0 approved entries at Gate H. That surface is not the later governed knowledge inventory of 911 records (1 eligible for human-review registration, 42 blocked, 868 ineligible, 0 human-approved). EIMS remains an engineering prototype for trusted-network Open Access use. Human Certification is NOT RUN; Production Readiness is PARTIAL; Engineering Acceptance is PASS only as inherited prior validation.

### 6.3 Chapter 4 — suggested “Software test eras” table

| Date | Report | Scope | Passed | Skipped | Failed |
|---|---|---|---:|---:|---:|
| 2026-11-20 | `2026-11-20-backend-final-closure.md` | Main suite (ignore analyzer-PG) | 1,374 | 51 | 0 |
| 2026-11-20 | `2026-11-20-knowledge-foundation-expansion.md` | Main suite after knowledge expansion | 1,903 | 51 | 0 |
| 2026-11-22 | `certification/end_to_end_final_report.md` | Finished-code main suite (ignore analyzer-PG) | 2,107 | 51 | 0 |
| (paired) | Analyzer-PG file only | Disposable analyzer DB | 75 | 0 | 0 |

Caption note: *Do not sum rows. Handover documentation pass ran no tests.*

### 6.4 Chapter 4/5 — catalog surfaces table

| Surface | Date / evidence | Count | Meaning |
|---|---|---|---|
| Analyzer catalog summary (Gate H) | 2026-11-20 browser E2E | 175 (0 approved) | UI/API catalog observation during disposable E2E |
| Parser-linked legacy surface | 2026-11-20 expansion | 181 (153+28) | Expanded legacy/parser-linked view |
| Governed inventory | eligibility/register artifacts | 911 | Full inventory (not 911 diagnostics) |
| Eligibility | `catalog_import_eligibility.json` | 1 / 42 / 868 | ELIGIBLE / BLOCKED / INELIGIBLE |
| Human-approved | certification counts | 0 | Synthetic disposable approvals excluded |

### 6.5 Chapter 4 — Certification Browser subsection (new)

> On 22 November 2026, Certification Browser Acceptance executed 18 synthetic demo cases against the documented local demo and webpack production build surfaces and recorded 18/18 PASS (`docs/acceptance/certification/browser_acceptance_report.md`). This layer is separate from Secure Browser final16 (15 November; 33/33) and from the 20 November disposable HTTP E2E result (ACCEPTED WITH LIMITATIONS). The three results must not be combined into a single browser score.

### 6.6 Chapter 5 — locked acceptance triad (insert near technical-validation conclusion)

> Relative to the locked Certification & Handover baseline (`final_handover_report.md`): Engineering Acceptance is PASS based on previously completed validation evidence (including finished-code 2,107/51/0, Analyzer-PG 75, and certification browser 18/18); Human Certification is NOT RUN; Production Readiness is PARTIAL. The handover documentation pass itself did not re-execute those tests.

---

## 7. Evidence reference for each proposed change

| Change | Evidence |
|---|---|
| Qualify Abstract 1,374 | `docs/acceptance/2026-11-20-backend-final-closure.md` |
| Keep body 1,903 | `docs/acceptance/2026-11-20-knowledge-foundation-expansion.md`; DOCX §4.4.1 |
| Add 2,107 | `docs/acceptance/certification/end_to_end_final_report.md` |
| Keep 75 Analyzer-PG | closure + certification reports |
| Qualify Abstract 175 | `docs/acceptance/2026-11-20-final-browser-e2e-acceptance.md` Gate H |
| Keep / emphasize 911 | `catalog_import_eligibility.json`, `register.json`, DOCX §4.3 |
| Add 1/42/868/0 | eligibility JSON; `final_handover_report.md` |
| Keep 33/33 | DOCX §4.4.3 (path re-cite outstanding) |
| Keep ACCEPTED WITH LIMITATIONS | `2026-11-20-final-browser-e2e-acceptance.md` |
| Add 18/18 | `docs/acceptance/certification/browser_acceptance_report.md` |
| Engineering PASS inherited / handover no tests | `final_handover_report.md` §Tests |
| Human NOT RUN / 0 approved | handover; ASA package; gates policy |
| Production PARTIAL | handover checklist |
| M2/M3 NOT RUN | DOCX Ch. 3–5; evaluation materials |
| Open Access / no login requirement | product decision; do not invent login gap |
| Synthetic ≠ human | handover; end_to_end_final_report synthetic notes |
| Prior audit matrix | `repository_report_audit.md` |

---

## 8. Claims that must remain unchanged

1. Human Certification **NOT RUN** until real independent reviewers decide through the workflow.  
2. **0** human-approved knowledge (exclude synthetic disposable approvals).  
3. Eligibility **1 / 42 / 868** — do not promote blocked/ineligible.  
4. ASA 113005 ELIGIBLE + package ready ≠ source-verified/approved; search snippet ≠ page read.  
5. Open Access design — **do not** introduce application login as a missing requirement.  
6. M2/M3 RAG/LLM evaluation **NOT RUN**; diagnostic accuracy **NOT MEASURED**.  
7. Deterministic catalog-supported Analyzer path is the validated research investigation path.  
8. Inventory **911 ≠** 911 diagnostic capabilities (DOCX already warns — keep).  
9. Browser layers remain separate (33/33 ≠ disposable E2E ≠ 18/18).  
10. Production readiness remains incomplete / **PARTIAL**.  
11. Prototype / trusted-network deployment posture.  
12. Chapter organization and undergraduate research framing (do not invent new completed objectives).

---

## 9. Unverified information requiring author confirmation

| Item | Why |
|---|---|
| Exact lost English-abstract trailing text after “using a” | Extract shows truncation; author must confirm intended disposable-DB / catalog / prototype wording before Final Report edit |
| Secure Browser final16 evidence **repository path** | DOCX asserts 33/33 + 2/2; audit did not re-open original evidence tree — cite path or mark NOT VERIFIED |
| Whether Ch. 1 still lists semantic vector retrieval as a completed objective | Body Ch. 5 says incomplete; Ch. 1 wording needs author line-check |
| Figure/table captions in DOCX visuals | Text extract does not prove every caption; author visual pass required |
| Whether Abstract should **mention** 911 at all | Research choice: qualify 175 (default) vs dual-cite 175+911; **do not** silently replace 175 with 911 |
| Whether to elevate 2,107 into Abstract | Only if author wants Abstract = certification era; otherwise keep 1,374 dated and cite 2,107 in Ch. 4–5 |
| Three-reviewer wording anywhere outside audited extracts | Confirm no mandatory-three claim remains |
| Field / physical USB SHA “not re-verified” details | Keep historical qualification; do not invent new SHA verification |

---

## 10. Final consistency checklist (for after wording approval — Phase 3)

- [ ] Abstract Thai ↔ English: same dated scopes; EN sentence complete  
- [ ] One reconciliation table each for **tests**, **catalog surfaces**, **browser layers**  
- [ ] No phrase “latest” attached to 1,374 if 1,903/2,107 are also cited  
- [ ] 175 never equals 911 in the same sentence without an explicit “different surface” clause  
- [ ] 1/42/868/0 stated wherever 911 is summarized as certification-aligned  
- [ ] 33/33, ACCEPTED WITH LIMITATIONS, and 18/18 never summed or synonymized  
- [ ] Locked triad present in Ch. 5: Engineering PASS (inherited) / Human NOT RUN / Production PARTIAL  
- [ ] Handover “no tests run” stated once where Engineering PASS is explained  
- [ ] M2/M3 NOT RUN; diagnostic accuracy NOT MEASURED unchanged  
- [ ] No Product Accepted / Human Certification completed / all-911-validated claims  
- [ ] No new login requirement  
- [ ] Synthetic approvals excluded from human counts  
- [ ] TOC, dotted leaders, page numbers, table/figure lists refreshed after edit  
- [ ] Dirty tree preserved; no code/test/commit side effects  

---

## 11. Recommended next step (owner)

1. Review and approve/amend this plan (especially Abstract strategy: qualify 175/1374 vs dual-cite).  
2. Only then authorize a **single** DOCX Final Report edit pass.  
3. Do **not** reopen EIMS feature development for this closure path.

**STOP.** Correction plan created only. Supplied DOCX untouched. No source, test, service, stage, commit, or push actions in this phase.
)
