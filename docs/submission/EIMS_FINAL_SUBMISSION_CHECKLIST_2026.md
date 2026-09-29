# EIMS Cooperative Education Final Submission Checklist (2026)
**Academic Year 2026 | International Program, Faculty of Engineering, KMITL**
**Project:** Development of an Enterprise Infrastructure Management System (EIMS)
**Student:** Ratthabhumi Peansukmanee (Student ID: 66011198)
**Host Organization:** KANEMATSU ELECTRONICS (THAILAND)
**Workplace Supervisor:** Mr. Chalermpol Phuangchalam
**Project Advisor:** Asst. Prof. Dr. Phongsak Keeratiwintakorn

---

## 1. Executive Status Summary

| Aspect | Status | Detail / Gate Verification |
| :--- | :---: | :--- |
| **Digital Submission Package** | **COMPLETE** | All digital documents (Report, Presentation, Defense Pack, Poster, Review Proof) generated, verified, and frozen. |
| **Physical / Human Verification** | **PENDING** | Physical A4 proof printing, supervisor review sign-off, advisor signature, and live oral rehearsal. |
| **Official KMITL Seal Asset** | **PROOF EMBEDDED** | Official seal extracted from supplied KMITL document (256.9 DPI proof asset); high-resolution faculty vector/raster seal required for final A1 print. |
| **Poster Font Compliance** | **PASS** | `Angsana New` applied consistently (verified installed in system font registry; explicitly listed in official KMITL poster guidelines). |
| **A1 Geometry & Layout** | **PASS** | 594 mm × 841 mm (ISO 216 A1 portrait), 1 page, 3-column academic layout with Abstract, Acknowledgments, and Advisor Signature block. |
| **A4 Review Proof** | **PASS** | 210 mm × 297 mm (ISO 216 A4 portrait), 1 page, exact proportional 35.36% linear scale ($1/(\sqrt{2})^3$), no cropping, no reflow. |
| **Technical Fact Lock** | **LOCKED** | 37 passed / 0 failed / 4 warnings; 49 persisted events; 10 AnalysisHistory records; HTTP 200; Gate A9 PASS; CPython 3.14.3; max 500 events / 24h window. |
| **Confidentiality Audit** | **PASS** | Zero customer hostnames, private IPs, MAC addresses, credentials, or raw unapproved field screenshots. |

---

## 2. Authoritative Final Artifacts & SHA-256 Checksums

All final binary deliverables are frozen. Checksums allow verification that printed or submitted files match these exact versions.

| Deliverable Type | Relative Repository Path | File Size | SHA-256 Checksum |
| :--- | :--- | :---: | :--- |
| **Report (DOCX)** | `docs/report/final/EIMS_FINAL_COOP_REPORT_2026.docx` | 1,148,924 B | `3b2550f8b4ee4b0a1ed6d940a690f452a7cf7bd811f5fe37573959d7e3436a6f` |
| **Report (PDF)** | `docs/report/final/EIMS_FINAL_COOP_REPORT_2026.pdf` | 1,291,971 B | `98c057c4b728eaf1352a8eaa4b461ac03f8e69c5f37286f7cb854efa2894d2a3` |
| **Presentation (PPTX)** | `docs/presentation/EIMS_COOP_PRESENTATION_2026.pptx` | 499,715 B | `026eae931f87186f2401b88eb654e74238b50536b17c3c156d83e4995b9afcdf` |
| **Presentation (PDF)** | `docs/presentation/EIMS_COOP_PRESENTATION_2026.pdf` | 548,249 B | `671930cc8b5aa1f53b0971f9b6265da12d287651e23a8e33a4ca2e9edbcaa073` |
| **Poster (PPTX)** | `docs/poster/EIMS_COOP_POSTER_2026.pptx` | 665,872 B | `73a4d5f2a504cdbfd1a45077d5db7f88a46b071a21182c2077fe18ff1b04e544` |
| **Poster (A1 PDF)** | `docs/poster/EIMS_COOP_POSTER_2026.pdf` | 487,598 B | `446569539682455b9f35aecff4b2e9ef1be90f348a410123ee39dac4c16930b9` |
| **Poster (A4 Review PDF)** | `docs/poster/EIMS_COOP_POSTER_A4_REVIEW_2026.pdf` | 642,383 B | `75f3677977afc3db8a54adab79cd1329448399419a3b43376b4b949ad24436ad` |
| **Poster (PNG Preview)** | `docs/poster/EIMS_COOP_POSTER_2026.png` | 1,340,146 B | `7c019262d5b6ccf752f63a79f6ef1329ee767fc4f243113ee66f702c28b2893e` |
| **Poster Source (MD)** | `docs/poster/EIMS_COOP_POSTER_SOURCE_2026.md` | 15,668 B | `9d9dba38dbb629f8062d96f5d35d1d0e05894399093bc13b8629b7c032234665` |
| **Defense Q&A (MD)** | `docs/presentation/EIMS_PRESENTATION_QA.md` | 12,255 B | `21cc134e800ee690e3594b2f43fe973f669e360c61ddafa1b57bb7486d3f8c0f` |
| **Defense Script (MD)** | `docs/presentation/EIMS_DEFENSE_REHEARSAL_2026.md` | 63,633 B | `56a48664fe16fcd4c4ccd2cc84c37f7c9a780928b4ef1bec40c886582ddc6fd5` |
| **Defense Cue Card (MD)** | `docs/presentation/EIMS_DEFENSE_CUE_CARD_2026.md` | 7,172 B | `d1f1513bb3c8132ab9ab762703b8f8a182759a9a91042b4ed818d703cf4396ef` |

---

## 3. Git Release & Version Control Anchors

- **Active Tracking Branch:** `main`
- **Current Base Commit:** `7d67b6bf146617edc037daea90f21f08e409ade9`
- **Canonical Release Tag:** `v0.3.0^{}` == `bb9210f06256c3adc0c7901352d08e1a026a8027` (strictly preserved and unmodified)
- **Commit Boundary Policy:** Stage only `docs/poster/*` and `docs/submission/*`. Zero modifications to `docs/report/**`, `docs/presentation/**`, or application source code.

---

## 4. Technical Fact Lock Compliance

All artifacts across Report, Slides, Q&A, Rehearsal, and Poster consistently adhere to the immutable project technical facts:

1. **Test Suite:** Hermetic Ingestion Test Suite: 37 passed, 0 failed, 4 warnings.
2. **Field Telemetry:** 49 persisted Windows Event Evidence rows (34 System channel + 15 Application channel).
3. **AI Workload Bounding:** Strictly bounded to at most 10 selected new events per import.
4. **AnalysisHistory:** 10 AnalysisHistory records associated with the selected field dataset (satisfying analyzer cap <= 10).
5. **Runtime Verification:** HTTP 200 on filtered history endpoint; Gate A9 PASS in browser runtime.
6. **Telemetry Scope:** 24-hour default query window; default maximum 500 events across combined System/Application channels.
7. **Runtime Environment:** Bundled embedded CPython 3.14.3 amd64; read-only WMI/CIM queries; no target host Python/Docker dependencies.
8. **Deduplication:** Sequential application-level SHA-256 deduplication; no concurrent database-level uniqueness guarantee.

---

## 5. Distinction: Digital Readiness vs. Outstanding Human Actions

### 5.1 Digital Work: COMPLETE (FROZEN)
- Report DOCX and PDF compiled, formatted, and verified.
- Presentation PPTX and PDF formatted with exact 23-slide timing narrative.
- Defense Pack (32-question categorized Q&A, rehearsal script, cue card) completed.
- Poster PPTX, A1 PDF, and A4 Review PDF built and verified.
- No further digital rewrites, redesigns, or code edits are permitted.

### 5.2 Physical & Human Actions: PENDING (Human Execution Only)
The remaining workflow steps require human physical action and interpersonal coordination:

1. **Print A4 Poster Proof:**
   Print `docs/poster/EIMS_COOP_POSTER_A4_REVIEW_2026.pdf` on standard A4 paper.
2. **Supervisor Visual Review:**
   Present the physical A4 print to Workplace Supervisor Mr. Chalermpol Phuangchalam for layout and content verification.
3. **Advisor Approval / Signature:**
   Obtain academic advisor signature from Asst. Prof. Dr. Phongsak Keeratiwintakorn on the designated poster approval block.
4. **Timed Defense Rehearsals:**
   Execute timed dry-runs using `docs/presentation/EIMS_DEFENSE_CUE_CARD_2026.md` and `docs/presentation/EIMS_DEFENSE_REHEARSAL_2026.md` (target: 14–15 minutes presentation, 5–10 minutes Q&A).
5. **Report Screenshot Handling:**
   Replace report screenshot placeholders only if company-sanitized, supervisor-approved field captures become available and supervisor explicitly requests them.
6. **Post-Defense Certification Sign-Off:**
   Obtain signed report certification/approval page after the formal oral defense.
7. **Final A1 Poster Printing:**
   Print the full-size 594 mm × 841 mm poster on matte paper after supervisor sign-off and faculty seal confirmation.
8. **Official Faculty Submission:**
   Submit final files through the official 2026 KMITL cooperative education submission channel once the 2026 deadline is formally announced (do NOT use the expired Dec 15, 2025 date).
