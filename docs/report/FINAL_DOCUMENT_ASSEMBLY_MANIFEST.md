# EIMS Final Cooperative Education Report
# Document Assembly Manifest and Pre-DOCX Audit

This manifest defines the canonical structure, file mappings, asset requirements, and styling specifications for compiling the final cooperative education report for the **Enterprise Infrastructure Management System (EIMS)** into Microsoft Word (`.docx`) and exporting the official PDF.

---

## 1. Canonical Document Structure and Page Order

The assembled report adheres to the academic guidelines of the School of Engineering, King Mongkut's Institute of Technology Ladkrabang (KMITL).

| Section Order | Section / Document Element | Source File / Input Mechanism | Pagination Style |
| :--- | :--- | :--- | :--- |
| **01** | Cover Page (Outer & Inner) | Institutional Template / Form Fields | No page number |
| **02** | Approval / Certification Page | Faculty Template / Sign-off Sheet | No page number |
| **03** | Thai Abstract (บทคัดย่อ) | `docs/report/ABSTRACT_TH.md` | Roman / Thai lowercase (ก, ข, ...) |
| **04** | English Abstract | `docs/report/ABSTRACT_EN.md` | Roman lowercase (i, ii, ...) |
| **05** | Acknowledgments (กิตติกรรมประกาศ) | `docs/report/ACKNOWLEDGMENTS.md` | Roman lowercase |
| **06** | Table of Contents (สารบัญ) | Word Automated Field (`TOC \o "1-3"`) | Roman lowercase |
| **07** | List of Figures (สารบัญรูปภาพ) | Word Automated Field (`TOF \c "Figure"`) | Roman lowercase |
| **08** | List of Tables (สารบัญตาราง) | Word Automated Field (`TOT \c "Table"`) | Roman lowercase |
| **09** | Chapter 1 — Introduction | `docs/report/CHAPTER_1_INTRODUCTION.md` | Arabic numerals (1, 2, 3, ...) |
| **10** | Chapter 2 — Concepts and Related Technologies | `docs/report/CHAPTER_2_CONCEPTS_AND_RELATED_TECHNOLOGIES.md` | Arabic numerals |
| **11** | Chapter 3 — System Design and Implementation | `docs/report/CHAPTER_3_SYSTEM_DESIGN_AND_IMPLEMENTATION.md` | Arabic numerals |
| **12** | Chapter 4 — Results and Validation | `docs/report/CHAPTER_4_RESULTS_AND_VALIDATION.md` | Arabic numerals |
| **13** | Chapter 5 — Summary and Recommendations | `docs/report/CHAPTER_5_SUMMARY_AND_RECOMMENDATIONS.md` | Arabic numerals |
| **14** | References (เอกสารอ้างอิง) | `docs/report/REFERENCES.md` | Arabic numerals |
| **15** | Appendices (if applicable) | Supplementary Code / Test Logs | Arabic numerals / Alpha |
| **16** | Author Biography (ประวัติผู้เขียน) | Institutional Form Fields | Arabic numerals |

---

## 2. Source File Inventory and Readiness Audit

All report sections have been authored, verified, and committed to git under `docs/report/`.

| File Path | Purpose | Word / Char Count | Status |
| :--- | :--- | :--- | :--- |
| `docs/report/ABSTRACT_TH.md` | Thai Academic Abstract | ~3,400 chars | READY |
| `docs/report/ABSTRACT_EN.md` | English Academic Abstract | 312 words | READY |
| `docs/report/ACKNOWLEDGMENTS.md` | Formal Acknowledgments | 4 paragraphs | READY (Placeholders preserved) |
| `docs/report/CHAPTER_1_INTRODUCTION.md` | Project Context & 7 Objectives | ~1,600 words | READY |
| `docs/report/CHAPTER_2_CONCEPTS_AND_RELATED_TECHNOLOGIES.md` | Theoretical Baseline & 18 Citations | ~5,100 words | READY |
| `docs/report/CHAPTER_3_SYSTEM_DESIGN_AND_IMPLEMENTATION.md` | Engineering Architecture & Design | ~6,500 words | READY |
| `docs/report/CHAPTER_4_RESULTS_AND_VALIDATION.md` | Empirical Validation & Evidence | ~5,600 words | READY |
| `docs/report/CHAPTER_5_SUMMARY_AND_RECOMMENDATIONS.md` | Evaluation, Limitations, Roadmap | ~2,300 words | READY |
| `docs/report/REFERENCES.md` | IEEE Bibliographic Entries [1]–[18] | 18 references | READY |

---

## 3. Human Input and Institutional Metadata Checklist

The following items must be verified or provided by the author prior to finalizing the Master DOCX and exporting the official PDF.

| Field Identifier | Description | Current Value in Repo | Action Required |
| :--- | :--- | :--- | :--- |
| `[HOST ORGANIZATION NAME]` | Name of host enterprise company / division | Explicit placeholder | Fill real company name |
| `[WORKPLACE SUPERVISOR NAME]` | Workplace mentor / supervisor title and name | Explicit placeholder | Fill mentor name and title |
| `[ACADEMIC SUPERVISOR NAME]` | KMITL faculty advisor title and name | Explicit placeholder | Fill advisor name and academic title |
| `[STUDENT_NAME]` | Student author full name (Thai and English) | Ratthabhumi ... | Confirm official spelling |
| `[STUDENT_ID]` | KMITL student registration ID | Not committed in repo | Insert on cover and bio pages |
| `[ACADEMIC_YEAR]` | Cooperative education academic year | Academic Year 2026 | Confirm semester / academic year |
| `[FACULTY_PAGE]` | KMITL Co-op Certification / Sign-off form | N/A | Bind official department form |

---

## 4. Final Figure Manifest and Insertion Plan

The report incorporates system diagrams and empirical verification screenshots. All figures must use Word Caption fields (`Figure {chapter}.{number}: {Caption}`) for automated List of Figures generation.

| Figure ID | Chapter / Section | Working Caption | Source / Technology | Current Status | Sanitization & Confidentiality |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Figure 3.1** | Section 3.2 | Multi-Tier System Architecture of the EIMS Platform | Mermaid `flowchart TB` in Chapter 3 | NEEDS RENDERING | Vector / PNG export (clean system blocks) |
| **Figure 3.2** | Section 3.4 | Relational Data Model and Entity-Relationship Architecture | Mermaid `erDiagram` in Chapter 3 | NEEDS RENDERING | Vector / PNG export (schema entities) |
| **Figure 3.3** | Section 3.6 | Disconnected USB Evidence Acquisition and Central Ingestion Sequence | Mermaid `sequenceDiagram` in Chapter 3 | NEEDS RENDERING | Vector / PNG export (runtime sequence) |
| **Figure 4.1** | Section 4.4 | Portable USB Auditor Batch Launcher Console Output | Batch execution on endpoint | NEEDS USER COPY | Console output on `ASSET-01` (synthetic host) |
| **Figure 4.2** | Section 4.5 | Operational Dashboard Detail View: Hardware Specifications and BitLocker Posture | Next.js Dashboard UI (A4/A5) | NEEDS USER COPY | Sanitized UI capture (no real MAC/serial) |
| **Figure 4.3** | Section 4.6 | Persisted Windows Event Evidence Table View (49 Ingested Events) | Next.js Dashboard UI (A6) | NEEDS USER COPY | Sanitized event table (System + Application) |
| **Figure 4.4** | Section 4.7 | Filtered Analysis History JSON API Response Payload | REST API (`/api/v1/history?asset_id=...`) | NEEDS USER COPY | JSON formatted capture (HTTP 200, 10 items) |
| **Figure 4.5** | Section 4.7 | A9 Gate Browser Verification: Simultaneous Rendering of Event Evidence and AI Findings | Next.js Dashboard UI (A9 Gate) | NEEDS USER COPY | Full browser capture with findings visible |

### Figure Preparation Rules:
1. **No Raw Production Data:** Ensure all hostnames, MAC addresses, IP addresses, and hardware serials are masked with synthetic identifiers (e.g., `ASSET-01`, `00:11:22:33:44:55`, `10.0.0.x`).
2. **Resolution:** Screenshots should be captured at 100% OS scaling (minimum 1920x1080) and inserted with clean borders.
3. **Diagrams:** Mermaid blocks should be rendered to high-resolution PNG or SVG via Mermaid CLI or headless Chromium prior to Word insertion.

---

## 5. Final Table Manifest

Tables must be formatted as native Microsoft Word tables with Word Table Captions (`Table {chapter}.{number}: {Caption}`) placed **above** the table in accordance with standard academic conventions.

| Table ID | Chapter / Section | Table Caption | Purpose | Current Repo Status |
| :--- | :--- | :--- | :--- | :--- |
| **Table 2.1** | Section 2.15 | Comparison of Infrastructure Management and Diagnostic Paradigms | Compare EIMS against SIEM, ITAM, and Monitoring | Complete in Markdown |
| **Table 4.1** | Section 4.1 | Empirical Verification Environment Specifications | Hardware, OS, and software baseline | Complete in Markdown |
| **Table 4.2** | Section 4.3 | Automated Ingestion Test Suite Execution Results (Sprint 13) | Test suite breakdown (37 pass, 0 fail, 4 warn) | Complete in Markdown |
| **Table 4.3** | Section 4.7 | A9 UI Gate Acceptance Criteria and Verification Results | 6 browser evaluation criteria | Complete in Markdown |
| **Table 4.4** | Section 4.9 | Summary of Resolved Engineering Defects and Mitigations | Defect resolution ledger (PRD, dedup, UI) | Complete in Markdown |
| **Table 4.5** | Section 4.10 | Comprehensive Summary of Validation Gates and Verification Outcomes | 6 validation domains and verdicts | Complete in Markdown |
| **Table 5.1** | Section 5.1 | Systematic Mapping of Project Objectives to Implementation and Validation Outcomes | 7/7 objectives verification mapping | Complete in Markdown |
| **Table 5.2** | Section 5.2 | Final Summary of System Contributions and Measured Engineering Results | Final synthesis of measured metrics | Complete in Markdown |

---

## 6. Microsoft Word Assembly & Styling Specifications

To guarantee consistency, the DOCX compilation script or template setup must configure native Word styles:

### 6.1 Section Break & Pagination Plan
- **Section 1 (Cover & Approval):** No header/footer, no page numbering.
- **Section 2 (Front Matter: Thai Abstract to List of Tables):**
  - Page numbering: Lowercase Roman (`i, ii, iii, ...`) or Thai characters (`ก, ข, ค, ...`) centered in the header or bottom right depending on KMITL template.
  - Numbering restarts at `i` (or `ก`) on Thai Abstract.
- **Section 3 (Body: Chapters 1–5 & References):**
  - Section break (Next Page) before Chapter 1.
  - Page numbering: Arabic numerals (`1, 2, 3, ...`) starting at `1` on Chapter 1.
  - Page number position: Top right or bottom center (as required by KMITL template).

### 6.2 Typography & Hierarchy
- **Body Text:**
  - Font: TH Sarabun PSK / TH Sarabun New (16 pt) or Times New Roman (12 pt) for English text.
  - Line Spacing: 1.15x or 1.5x (verify against KMITL faculty manual).
  - Paragraph Alignment: Justified (Thai distributed / Justify).
  - Paragraph Spacing: 0 pt Before, 6 pt After.
- **Heading 1 (Chapter Titles):**
  - Font: Bold, 18–20 pt, centered.
  - Format: `Chapter {N}` on first line, followed by `{Chapter Title}` on second line.
- **Heading 2 (Major Sections):**
  - Font: Bold, 16–18 pt, left-aligned.
  - Format: `{Chapter}.{Section} {Section Title}` (e.g., `1.1 Problem Context`).
- **Heading 3 (Subsections):**
  - Font: Bold, 16 pt, left-aligned, indented 0.5 in.
  - Format: `{Chapter}.{Section}.{Sub} {Title}` (e.g., `3.1.1 Asset Registry`).
- **Captions:**
  - Figure Caption: 14 pt, centered, placed **below** figure.
  - Table Caption: 14 pt, left-aligned or centered, placed **above** table.
- **Code / Monospace Snippets:**
  - Font: Consolas / Courier New, 10–11 pt, shaded light gray background.

---

## 7. KMITL Formatting Items Requiring Confirmation

Prior to final PDF generation, check the official School of Engineering cooperative education manual:
1. **Binding Margin:** Verify if left margin requires 1.5 inches (3.81 cm) and top/right/bottom require 1.0 inch (2.54 cm).
2. **Thai vs English Typography:** Confirm whether English reports in KMITL require standard Times New Roman (12 pt, 1.5 line spacing) or bilingual TH Sarabun PSK (16 pt).
3. **Approval Signatures:** Confirm required signatory roles (Workplace Supervisor, Faculty Advisor, Head of Department).

---

## 8. Final Report Content Consistency Verification

Audit performed across all report chapters and front-matter documents:

- **Canonical Project Title:** `Development of an Enterprise Infrastructure Management System (EIMS)` — Consistent across all files.
- **Core Objectives:** Exactly 7 objectives in Chapter 1, mapped 1:1 and achieved in Chapter 5.
- **Academic Citations:** 0 placeholders remaining in Chapter 2; exactly 18 numbered IEEE references in `REFERENCES.md`.
- **Sprint 13 Test Suite Metrics:** 37 passed, 0 failed, 4 warnings — Consistent.
- **Field Evidence Metrics:** 49 persisted Windows Event Log records (34 System, 15 Application) collected across a 24-hour window — Consistent.
- **AI Triage & Provenance:** Exactly 10 bounded AnalysisHistory records for `ASSET-01` (analyzer cap of 10); Filtered API HTTP 200 — Consistent.
- **UI Acceptance:** A9 Browser Gate PASS (simultaneous rendering of evidence and findings; placeholder absent) — Consistent.
- **Runtime Environment:** CPython 3.14.3 amd64 embedded runtime for portable acquisition — Consistent.
- **Deduplication:** Application-level sequential deduplication via SHA-256 event fingerprint — Consistent.
- **Scope & Non-Claims:** Correctly framed as an academic engineering prototype; no production HA claim, no certified forensic platform claim, no autonomous diagnosis claim, and no false assertion of a latest full USB reacquisition.
- **Confidentiality:** 0 real hostnames, 0 raw production credentials, 0 real BitLocker recovery keys, 0 private IP/MAC bindings.

---

## 9. Next Steps

1. Fill the 3 name placeholders in `docs/report/ACKNOWLEDGMENTS.md` when actual names are confirmed.
2. Render the 3 Mermaid diagrams from Chapter 3 into vector graphics or high-resolution images.
3. Collect the 5 sanitized screenshots for Chapter 4 from the field evidence archive.
4. Execute the Master DOCX assembly workflow adhering to the style parameters in this manifest.
5. Generate native Word TOC, List of Figures, and List of Tables.
6. Export official PDF and conduct final visual inspection.
