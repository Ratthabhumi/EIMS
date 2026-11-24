"""Surgical corrections to FINAL_REVIEW DOCX — preserve structure; dated claims only."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

SRC = Path(
    r"C:\Users\MewMew\.codex\.chatgpt-projects\g-p-6aa6cf8212c4819191c5d7719f82110c"
    r"\EIMS_FINAL_SUBMISSION_2026_FINAL_REVIEW_with_dotted_leaders.docx"
)
AUDIT_OUT = Path(r"C:\Users\MewMew\AppData\Local\Temp\eims_final_review_audit")
AUDIT_OUT.mkdir(exist_ok=True)

EVIDENCE_CUTOFF = "2026-11-22"


def set_paragraph_text(paragraph: Paragraph, text: str) -> None:
    """Replace paragraph text while keeping the first run's formatting when possible."""
    if paragraph.runs:
        first = paragraph.runs[0]
        first.text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(text)


def insert_paragraph_after(paragraph: Paragraph, text: str) -> Paragraph:
    """Insert a new paragraph after `paragraph`, copying paragraph properties only."""
    from docx.oxml import OxmlElement

    new_p = OxmlElement("w:p")
    pPr = paragraph._p.find(qn("w:pPr"))
    if pPr is not None:
        new_p.insert(0, deepcopy(pPr))
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    new_para.add_run(text)
    return new_para


def main() -> None:
    doc = Document(str(SRC))
    changes: list[str] = []

    # --- A1 Thai abstract ---
    thai = (
        "ผลการทดสอบอัตโนมัติในวันที่ 20 พฤศจิกายน 2569 ตามรายงาน backend-final-closure "
        "พบว่าชุดทดสอบหลักผ่าน 1,374 รายการ (ข้าม 51 รายการ ไม่มีรายการล้มเหลว) "
        "และชุดทดสอบ Analyzer บน PostgreSQL ทดลองผ่าน 75 รายการ "
        "ผลชุดนี้เป็นหลักฐานของช่วงเวลานั้น ไม่ใช่ผล regression ชุด finished-code ภายหลัง "
        "(2,107 รายการผ่าน / 51 ข้าม / 0 ล้มเหลว ตาม end_to_end_final_report) "
        "และยังไม่ใช่หลักฐานการยอมรับระบบแบบ Browser end-to-end ทั้งระบบ "
        "ในวันเดียวกัน การยอมรับแบบ disposable HTTP บันทึกสรุปแคตตาล็อกฝั่ง Analyzer "
        "ที่ Gate H จำนวน 175 ระเบียน โดยยังไม่มีรายการที่ผ่านการยืนยันแหล่งที่มาหรืออนุมัติ "
        "ตัวเลข 175 ไม่ใช่คลังความรู้แบบ governed inventory ซึ่งภายหลังตรวจยืนยันได้ 911 ระเบียน "
        "(Analyzer-matchable 181; อื่น ๆ 730; eligible สำหรับลงทะเบียนทบทวนโดยมนุษย์ 1; "
        "blocked 42; ineligible 868; human-approved 0; ณ evidence cutoff "
        f"{EVIDENCE_CUTOFF}). "
        "ระบบจึงยังเป็นต้นแบบเชิงวิศวกรรมภายใต้ Open Access ในเครือข่ายที่เชื่อถือได้ "
        "Engineering Acceptance เป็น PASS แบบ inherited จากหลักฐานก่อนหน้า "
        "Human Certification ยังเป็น NOT RUN และ Production Readiness เป็น PARTIAL "
        "โดย Product Acceptance ยังไม่ถูกกล่าวอ้าง"
    )
    set_paragraph_text(doc.paragraphs[32], thai)
    changes.append("¶32 Thai abstract: dated 1374/175; add 2107/911/eligibility/gates")

    # --- A2 English abstract (was truncated) ---
    eng = (
        "Enterprise infrastructure management across segmented or isolated networks is "
        "complicated by fragmented asset information and operational evidence. This project "
        "develops the Enterprise Infrastructure Management System (EIMS), a platform for "
        "managing infrastructure evidence and supporting engineering investigation. EIMS "
        "combines a PostgreSQL asset registry, a portable Windows evidence collector using "
        "an embedded CPython runtime, and an offline JSON ingestion workflow. The collector "
        "uses read-only Windows management queries and Windows Event Log acquisition within "
        "a defined System and Application channel scope. The backend stores event evidence "
        "with provenance metadata and applies SHA-256-based application-level duplicate "
        "checks for sequential imports. The Log Analyzer combines deterministic rules and "
        "catalog-supported investigation to help engineers prioritize work; semantic "
        "retrieval / RAG stages (M2/M3) remain NOT RUN as completed research evaluations. "
        "Generated findings remain advisory and require human assessment. An Incident "
        "Workspace supports evidence association and append-only engineer observations. "
        "The 20 November 2026 backend-final-closure gate reported 1,374 passed, 51 skipped, "
        "and 0 failed tests in the main suite, plus 75 passed in a separate Analyzer "
        "PostgreSQL integration suite on a disposable database. Those figures are dated "
        "results for that gate; they are distinct from the later Knowledge Foundation "
        "main-suite run (1,903 passed) and from the finished-code certification regression "
        "(2,107 passed, 51 skipped, 0 failed). They are not whole-system browser end-to-end "
        "acceptance. On the same day, disposable HTTP browser acceptance recorded an "
        "Analyzer catalog summary of 175 entries with 0 approved entries at Gate H. That "
        "surface is not the governed knowledge inventory of 911 records confirmed at "
        f"evidence cutoff {EVIDENCE_CUTOFF} (Analyzer-matchable 181; other governed 730; "
        "1 eligible for human-review registration; 42 blocked; 868 ineligible; "
        "0 human-approved). EIMS remains an engineering prototype for trusted-network "
        "Open Access use. Human Certification is NOT RUN; Production Readiness is PARTIAL; "
        "Engineering Acceptance is PASS only as inherited prior validation; Product "
        "Acceptance is NOT CLAIMED."
    )
    set_paragraph_text(doc.paragraphs[41], eng)
    changes.append("¶41 EN abstract: restore truncation; date numbers; gates; M2/M3 NOT RUN")

    # --- 4.3.1 inventory: qualify "latest" + add eligibility / unified surfaces ---
    set_paragraph_text(
        doc.paragraphs[678],
        (
            f"The working-tree inventory examined at evidence cutoff {EVIDENCE_CUTOFF} "
            "contained 911 records across operational context, diagnostic candidates, "
            "and technical references. Live recomputation on the same cutoff confirmed "
            "the same governed total via the Unified Catalog identity evidence path."
        ),
    )
    changes.append("¶678 qualify latest → evidence cutoff 2026-11-22")

    # Insert after ¶688 (HEAD snapshot paragraph) — eligibility / surfaces
    anchor_688 = doc.paragraphs[688]
    p_elig = insert_paragraph_after(
        anchor_688,
        (
            f"At the same evidence cutoff ({EVIDENCE_CUTOFF}), adapter eligibility against "
            "the governed inventory was 1 ELIGIBLE (cisco_asa:official_message_id:113005), "
            "42 BLOCKED, and 868 INELIGIBLE, with 0 human-approved entries. Eligible means "
            "ready for human-review registration; it is not human approval. Certification "
            "Class B counted 39 records (28 present in the Analyzer load_catalog surface "
            "and 11 not in that loader). These Class B figures are a certification class, "
            "not a separate catalog total, and must not be added to 911 or 181."
        ),
    )
    insert_paragraph_after(
        p_elig,
        (
            "Relative to the Unified Catalog projection verified in-repository: the "
            "Analyzer-matchable (load_catalog) surface is a strict subset of 181 records "
            "within the 911 governed inventory; the complementary other-governed count is "
            "730. UX and reports must not present 181 and 911 as interchangeable identities. "
            "A knowledge-quality audit at the same cutoff counted 77 of 911 rows as "
            "engineer-ready partial and 19 of 911 as having a full verify-chain field set; "
            "these quality metrics are not approval counts."
        ),
    )
    changes.append("After ¶688: eligibility 1/42/868/0; 181/730; Class B 39; quality 77/19")

    # Re-bind paragraph indices after inserts: safer to search by exact old text prefixes
    def find_para(startswith: str) -> Paragraph:
        for p in doc.paragraphs:
            if p.text.startswith(startswith):
                return p
        raise KeyError(startswith[:60])

    # --- 4.3.7 clarify 181 vs 911 vs 730 ---
    p734 = find_para(
        "These figures describe different catalog views and evidence times. The 175-entry"
    )
    set_paragraph_text(
        p734,
        (
            "These figures describe different catalog views and evidence times. The "
            "175-entry browser result should be retained as the Gate H Analyzer catalog "
            "summary observed during that acceptance journey. The 181-entry figure is the "
            "Analyzer-matchable / load_catalog surface (153 operational-context + 28 legacy "
            "diagnostic candidates) and is a strict subset of the 911 governed inventory; "
            "730 other governed records remain outside that Analyzer loader. The surfaces "
            "must not be combined or treated as contradictory counts of one snapshot."
        ),
    )
    changes.append("§4.3.7 clarify 175 vs 181⊂911 and 730 other")

    # --- 4.4.1 add test-era note after failed=0 block ---
    p750 = find_para(
        "It does not demonstrate diagnostic accuracy, universal vendor coverage, or production"
    )
    insert_paragraph_after(
        p750,
        (
            "Software test counts must be read as dated eras, not as one current total. "
            "An earlier 20 November 2026 backend-final-closure main-suite gate recorded "
            "1,374 passed, 51 skipped, and 0 failed (the Abstract figure). The Knowledge "
            "Foundation main-suite result above recorded 1,903 passed. A later finished-code "
            "certification regression documented in "
            "docs/acceptance/certification/end_to_end_final_report.md recorded 2,107 passed, "
            "51 skipped, and 0 failed under the same ignore-analyzer-PG pattern. These runs "
            "were not re-executed during the final report reconciliation on "
            f"{EVIDENCE_CUTOFF}; Engineering Acceptance PASS remains inherited from that "
            "prior validation evidence. The three main-suite figures must not be added "
            "together."
        ),
    )
    changes.append("§4.4.1 add dated test eras 1374 / 1903 / 2107")

    # --- After Secure Browser caveats: add certification browser 18/18 ---
    # Find paragraph that mentions subsequent Knowledge UI after Secure Browser
    target = None
    for p in doc.paragraphs:
        if p.text.startswith(
            "In particular, subsequent Knowledge UI and lifecycle changes were not covere"
        ):
            target = p
            break
    if target is None:
        # fallback: after Playwright 2/2 interpretation paragraph
        target = find_para(
            "These results demonstrate that the tested synthetic browser workflow passed at the time"
        )
    insert_paragraph_after(
        target,
        (
            "On 22 November 2026, Certification Browser Acceptance executed 18 synthetic "
            "demo cases against the documented local demo and webpack production-build "
            "surfaces and recorded 18/18 PASS "
            "(docs/acceptance/certification/browser_acceptance_report.md). This layer is "
            "separate from Secure Browser final16 (15 November; 33/33 checks and 2/2 "
            "Playwright) and from the 20 November disposable HTTP E2E result (ACCEPTED "
            "WITH LIMITATIONS). The three browser results must not be combined into a "
            "single browser score, and none of them constitutes Product Acceptance."
        ),
    )
    changes.append("§4.4.3+ add Certification Browser 18/18 as third dated layer")

    # --- Ch 5.2.2 technical validation ---
    p924 = find_para("The November 20, 2026 software test run completed with 1,903 tests passed")
    set_paragraph_text(
        p924,
        (
            "Dated software-test eras include: the 20 November 2026 backend-final-closure "
            "main suite (1,374 passed, 51 skipped, 0 failed); the 20 November Knowledge "
            "Foundation main suite (1,903 passed, 51 skipped, 0 failed); and the later "
            "finished-code certification regression (2,107 passed, 51 skipped, 0 failed) "
            "documented in docs/acceptance/certification/end_to_end_final_report.md. A "
            "separate PostgreSQL Analyzer integration suite completed with 75 passed tests. "
            "These results provide evidence that the tested software components and "
            "integration contracts behaved as expected under their respective disposable "
            "environments and dates. They must not be merged into one current pass count, "
            f"and they were not re-run during report reconciliation on {EVIDENCE_CUTOFF}."
        ),
    )
    changes.append("¶924 Ch5: add 1374/1903/2107 eras; no merge")

    p925 = find_para("The Secure Browser Acceptance final16 run completed 33 of 33 checks")
    set_paragraph_text(
        p925,
        (
            "The Secure Browser Acceptance final16 run completed 33 of 33 checks, with "
            "2 of 2 Playwright tests passing (15 November 2026; treat as historical until "
            "its original evidence paths are re-opened). A separate disposable HTTP browser "
            "end-to-end run on 20 November 2026 was assessed as ACCEPTED WITH LIMITATIONS. "
            "Certification Browser Acceptance on 22 November 2026 recorded 18/18 PASS on "
            "synthetic demo cases "
            "(docs/acceptance/certification/browser_acceptance_report.md). The historical "
            "A9 browser gate remains a further separate layer. These browser layers must "
            "not be conflated, and Product Acceptance remains NOT CLAIMED."
        ),
    )
    changes.append("¶925 Ch5: add 18/18; keep 33/33 and disposable E2E separate")

    p927 = find_para(
        "Therefore, the technical validation results support the conclusion that EIMS has functioning"
    )
    set_paragraph_text(
        p927,
        (
            "Therefore, the technical validation results support the conclusion that EIMS "
            "has functioning and tested workflows within the stated environments and "
            "boundaries. Relative to the Certification & Handover baseline: Engineering "
            "Acceptance is PASS only as inherited prior validation; Human Certification is "
            "NOT RUN; Production Readiness is PARTIAL. The results do not establish Product "
            "Acceptance, high availability, or complete end-to-end validation of every "
            "system function."
        ),
    )
    changes.append("¶927 Ch5: explicit Engineering/Human/Production triad")

    # --- Ch 5.2.3 knowledge ---
    p933 = find_para(
        "The project established a structured knowledge foundation to support infrastructure"
    )
    set_paragraph_text(
        p933,
        (
            "The project established a structured knowledge foundation to support "
            "infrastructure event investigation. At evidence cutoff "
            f"{EVIDENCE_CUTOFF}, the governed inventory contained 911 entries: 153 Windows "
            "operational-context entries, 28 legacy parser-linked diagnostic candidates, "
            "72 additional diagnostic candidates, and 658 technical references (100 "
            "diagnostic candidates in total). Of the 911, 181 are Analyzer-matchable and "
            "730 are other governed records. Adapter eligibility was 1 ELIGIBLE / 42 "
            "BLOCKED / 868 INELIGIBLE with 0 human-approved. Certification Class B was 39 "
            "(28 in load_catalog + 11 outside). Knowledge-quality audit counts were 77/911 "
            "engineer-ready partial and 19/911 full verify-chain — not approvals."
        ),
    )
    changes.append("¶933 Ch5 knowledge: 181/730, eligibility, Class B, quality")

    # --- Final conclusion ---
    p999 = find_para(
        "The results demonstrate meaningful progress toward an integrated infrastructure"
    )
    set_paragraph_text(
        p999,
        (
            "The results demonstrate meaningful progress toward an integrated infrastructure "
            "investigation system. They also identify clear boundaries in the current "
            "evidence: the knowledge catalog has not completed its approval lifecycle "
            "(0 human-approved; Human Certification NOT RUN), independent human gold review "
            "has not been performed, diagnostic accuracy metrics have not been measured, "
            "RAG M2/M3 remain NOT RUN, Production Readiness is PARTIAL, Product Acceptance "
            "is NOT CLAIMED, and some end-to-end workflows remain only partially validated. "
            "Catalog figures must be read with their identities: 911 governed, 181 "
            "Analyzer-matchable, 730 other, and Class B 39 as a certification class only."
        ),
    )
    changes.append("¶999 final conclusion: gates + catalog identity boundaries")

    p1000 = find_para(
        "The main outcome of this project is therefore a functioning and technically tested"
    )
    set_paragraph_text(
        p1000,
        (
            "The main outcome of this project is therefore a functioning and technically "
            "tested system foundation, together with an explicit evaluation framework and a "
            "defined path for further improvement. Completing knowledge verification, "
            "independent diagnostic evaluation (including Human Certification), and broader "
            "operational validation will be necessary before stronger claims about "
            "diagnostic effectiveness or production readiness can be made. Engineering "
            "Acceptance PASS remains inherited from dated prior evidence and must not be "
            "read as a fresh full-suite re-run at the report evidence cutoff."
        ),
    )
    changes.append("¶1000 final outcome: Human Certification + inherited Engineering PASS")

    doc.save(str(SRC))
    (AUDIT_OUT / "corrections_applied.json").write_text(
        "\n".join(f"- {c}" for c in changes), encoding="utf-8"
    )
    print("SAVED", SRC)
    print("CHANGES", len(changes))
    for c in changes:
        print(" ", c)


if __name__ == "__main__":
    main()
