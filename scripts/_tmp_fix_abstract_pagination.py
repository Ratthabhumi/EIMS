"""Fix Thai/EN abstract pagination + TH SarabunPSK 16pt. Abstract section only."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.text.paragraph import Paragraph

SRC = Path(
    r"C:\Users\MewMew\.codex\.chatgpt-projects\g-p-6aa6cf8212c4819191c5d7719f82110c"
    r"\EIMS_FINAL_SUBMISSION_2026_FINAL_REVIEW_with_dotted_leaders.docx"
)

FONT = "TH SarabunPSK"
SIZE = Pt(16)

THAI_BODY = (
    "การบริหารจัดการโครงสร้างพื้นฐานในเครือข่ายองค์กรที่แยกจากเครือข่ายภายนอกมักประสบปัญหา"
    "ข้อมูลทรัพย์สินและหลักฐานกระจัดกระจาย โครงงานนี้จึงพัฒนาระบบ Enterprise Infrastructure "
    "Management System (EIMS) เพื่อรวบรวม จัดเก็บ และวิเคราะห์หลักฐานด้านโครงสร้างพื้นฐาน "
    "โดยประกอบด้วยทะเบียนทรัพย์สินบน PostgreSQL ชุดรวบรวมข้อมูล Windows แบบพกพา "
    "และระบบนำเข้าหลักฐาน JSON แบบออฟไลน์ พร้อมใช้ SHA-256 ช่วยตรวจสอบข้อมูลซ้ำ "
    "ระบบ Log Analyzer ใช้กฎและคลังความรู้แบบ catalog-supported เพื่อเสนอแนวทางตรวจสอบ "
    "โดยให้วิศวกรเป็นผู้พิจารณาผลวิเคราะห์ ส่วน Incident Workspace ช่วยเชื่อมโยงหลักฐาน"
    "และบันทึกข้อสังเกต (ขั้น semantic/RAG M2/M3 ยังเป็น NOT RUN)"
)

THAI_RESULTS = (
    "ผลการทดสอบอัตโนมัติวันที่ 20 พ.ย. 2569 ตาม backend-final-closure "
    "ชุดหลักผ่าน 1,374 รายการ (ข้าม 51 ไม่ล้มเหลว) และ Analyzer บน PostgreSQL ผ่าน 75 รายการ "
    "เป็นหลักฐานของช่วงเวลานั้น ไม่ใช่ผล finished-code ภายหลัง (2,107 ผ่าน / 51 ข้าม / 0 ล้มเหลว) "
    "และไม่ใช่ Browser end-to-end ทั้งระบบ ในวันเดียวกัน disposable HTTP บันทึกแคตตาล็อก "
    "Analyzer ที่ Gate H จำนวน 175 ระเบียน (0 อนุมัติ) ซึ่งต่างจากคลัง governed 911 ระเบียน "
    "ที่ยืนยัน ณ 2026-11-22 (Analyzer-matchable 181; อื่น 730; Class B 39 = 28+11; "
    "eligible 1; blocked 42; ineligible 868; human-approved 0; คุณภาพ 77/911 และ "
    "verify-chain ครบ 19/911) ระบบยังเป็นต้นแบบภายใต้ Open Access: Engineering Acceptance "
    "เป็น PASS แบบ inherited, Human Certification เป็น NOT RUN, Production Readiness "
    "เป็น PARTIAL และ Product Acceptance ยังไม่ถูกกล่าวอ้าง"
)

THAI_KEYWORDS_LABEL = "คำสำคัญ:"
THAI_KEYWORDS_BODY = (
    " ระบบบริหารจัดการโครงสร้างพื้นฐานองค์กร, บันทึกเหตุการณ์ Windows, "
    "การรวบรวมหลักฐานแบบออฟไลน์, การวิเคราะห์บันทึกเหตุการณ์, "
    "การจัดการทรัพย์สิน, การจัดการเหตุการณ์"
)

EN_BODY = (
    "Enterprise infrastructure management across segmented or isolated networks is "
    "complicated by fragmented asset information and operational evidence. This project "
    "develops the Enterprise Infrastructure Management System (EIMS) to collect, store, "
    "and analyze infrastructure evidence. EIMS combines a PostgreSQL asset registry, a "
    "portable Windows evidence collector (embedded CPython), and offline JSON ingestion "
    "with SHA-256 duplicate checks. The Log Analyzer uses deterministic rules and "
    "catalog-supported investigation; semantic retrieval / RAG stages (M2/M3) remain "
    "NOT RUN. Findings are advisory and require human assessment. An Incident Workspace "
    "supports evidence association and append-only engineer notes."
)

EN_RESULTS = (
    "The 20 November 2026 backend-final-closure gate reported 1,374 passed, 51 skipped, "
    "and 0 failed in the main suite, plus 75 passed in a separate Analyzer–PostgreSQL "
    "integration suite. Those dated results differ from the Knowledge Foundation main-suite "
    "run (1,903 passed) and the finished-code certification regression (2,107 passed, "
    "51 skipped, 0 failed). They are not whole-system browser end-to-end acceptance. "
    "The same day, disposable HTTP browser acceptance recorded an Analyzer Gate H catalog "
    "summary of 175 entries (0 approved), which is not the governed inventory of 911 "
    "records confirmed at evidence cutoff 2026-11-22 (Analyzer-matchable 181; other "
    "governed 730; Class B 39 = 28+11; 1 eligible; 42 blocked; 868 ineligible; "
    "0 human-approved; quality audit 77/911 engineer-ready partial and 19/911 full "
    "verify-chain). EIMS remains an engineering prototype for trusted-network Open Access "
    "use. Engineering Acceptance is PASS only as inherited prior validation; Human "
    "Certification is NOT RUN; Production Readiness is PARTIAL; Product Acceptance is "
    "NOT CLAIMED."
)

EN_KEYWORDS_LABEL = "Keywords: "
EN_KEYWORDS_BODY = (
    "Enterprise Infrastructure Management, Infrastructure Evidence, Windows Event Log, "
    "Offline Evidence Collection, AI-assisted Investigation, Asset Management, "
    "System Observability"
)


def set_run_font(run, *, bold: bool | None = None) -> None:
    run.font.name = FONT
    run.font.size = SIZE
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    if bold is not None:
        run.bold = bold


def replace_paragraph(
    paragraph: Paragraph,
    parts: list[tuple[str, bool]],
    *,
    first_indent: bool = False,
) -> None:
    """Replace paragraph content with (text, bold) parts; force 16pt SarabunPSK."""
    # Clear existing runs
    for r in paragraph.runs:
        r.text = ""
    # Remove leftover empty runs beyond first by rewriting via clear XML text
    p = paragraph._p
    for child in list(p):
        if child.tag == qn("w:r"):
            p.remove(child)
    for i, (text, bold) in enumerate(parts):
        if first_indent and i == 0 and not text.startswith("\t") and not text.startswith(" "):
            text = "        " + text  # match existing first-line indent pattern
            first_indent = False
        run = paragraph.add_run(text)
        set_run_font(run, bold=bold)


def force_heading(paragraph: Paragraph, text: str) -> None:
    for r in paragraph.runs:
        r.text = ""
    p = paragraph._p
    for child in list(p):
        if child.tag == qn("w:r"):
            p.remove(child)
    run = paragraph.add_run(text)
    set_run_font(run, bold=True)


def main() -> None:
    doc = Document(str(SRC))

    # Indices from prior inspect (stable for this file state)
    force_heading(doc.paragraphs[30], "บทคัดย่อ")
    replace_paragraph(doc.paragraphs[31], [(THAI_BODY, False)], first_indent=True)
    replace_paragraph(doc.paragraphs[32], [(THAI_RESULTS, False)])
    replace_paragraph(
        doc.paragraphs[34],
        [(THAI_KEYWORDS_LABEL, True), (THAI_KEYWORDS_BODY, False)],
    )

    force_heading(doc.paragraphs[39], "ABSTRACT")
    # Keep EN as two paragraphs like Thai (body + results) for readable pagination
    replace_paragraph(doc.paragraphs[41], [(EN_BODY + " " + EN_RESULTS, False)], first_indent=True)
    replace_paragraph(
        doc.paragraphs[42],
        [(EN_KEYWORDS_LABEL, True), (EN_KEYWORDS_BODY, False)],
    )

    # Tighten abstract-local spacing slightly without crushing line spacing
    # (do not change page margins)
    for idx in (30, 31, 32, 34, 39, 41, 42):
        pf = doc.paragraphs[idx].paragraph_format
        if idx in (30, 39):  # headings
            pf.space_before = Pt(6)
            pf.space_after = Pt(6)
        elif idx in (34, 42):  # keywords
            pf.space_before = Pt(6)
            pf.space_after = Pt(0)
        else:
            pf.space_before = Pt(0)
            pf.space_after = Pt(6)

    # Reduce space_after on cooperative metadata block before ABSTRACT if present
    # (para 38) — keep content, only spacing within abstract neighborhood
    if "Cooperative Title" in doc.paragraphs[38].text:
        doc.paragraphs[38].paragraph_format.space_after = Pt(6)

    doc.save(str(SRC))
    print("SAVED", SRC)
    print("THAI_BODY_LEN", len(THAI_BODY))
    print("THAI_RESULTS_LEN", len(THAI_RESULTS))
    print("EN_LEN", len(EN_BODY) + 1 + len(EN_RESULTS))


if __name__ == "__main__":
    main()
